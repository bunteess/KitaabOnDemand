"""Development and end-to-end test helpers. Only mounted when
DEV_TOOLS_ENABLED=true, which production refuses (kitaab/config.py)."""

from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kitaab.clock import OffsetClock
from kitaab.container import Services
from kitaab.jobs import JOBS
from kitaab.providers.courier import CourierState, MockCourierProvider
from kitaab.providers.push import OUTBOX_KEY as PUSH_OUTBOX
from kitaab.providers.sms import MockSmsProvider
from kitaab.security.deps import get_services

router = APIRouter(prefix="/api/v1/_dev", tags=["dev"], include_in_schema=False)


class ClockIn(BaseModel):
    offset_seconds: float | None = None
    advance_seconds: float | None = None


@router.get("/clock")
def get_clock(services: Services = Depends(get_services)) -> dict[str, Any]:
    clock = services.clock
    offset = clock.offset_seconds() if isinstance(clock, OffsetClock) else 0.0
    return {"now": clock.now().isoformat(), "offset_seconds": offset}


@router.post("/clock")
def set_clock(body: ClockIn, services: Services = Depends(get_services)) -> dict[str, Any]:
    clock = services.clock
    if not isinstance(clock, OffsetClock):
        raise HTTPException(409, "The clock is not adjustable in this process")
    offset = body.offset_seconds if body.offset_seconds is not None else clock.offset_seconds()
    offset += body.advance_seconds or 0
    clock.set_offset(offset)
    return {"now": clock.now().isoformat(), "offset_seconds": offset}


@router.get("/sms-outbox")
def sms_outbox(
    phone: str | None = None, services: Services = Depends(get_services)
) -> list[dict[str, str]]:
    if not isinstance(services.sms, MockSmsProvider):
        raise HTTPException(409, "SMS provider is not the mock")
    return services.sms.outbox(phone)


@router.get("/push-outbox")
def push_outbox(services: Services = Depends(get_services)) -> list[str]:
    return [raw.decode() for raw in cast(list[bytes], services.redis.lrange(PUSH_OUTBOX, 0, 49))]


@router.post("/jobs/{name}")
def run_job(
    name: Literal["expire_quotes", "expire_pending_payments", "poll_courier_status", "purge_files"],
    services: Services = Depends(get_services),
) -> dict[str, Any]:
    return {"job": name, "result": JOBS[name](services)}


class CourierEventIn(BaseModel):
    state: CourierState
    description: str = ""


@router.post("/mock-courier/{cn}/events")
def mock_courier_event(
    cn: str, body: CourierEventIn, services: Services = Depends(get_services)
) -> dict[str, str]:
    """Advance a mock parcel. The mock courier then posts a signed webhook to the API."""
    courier = services.couriers.get("mock")
    if not isinstance(courier, MockCourierProvider):
        raise HTTPException(409, "Mock courier is not enabled")
    raw, headers = courier.build_webhook(
        cn, body.state, body.description or body.state.replace("_", " ").title()
    )
    services.tasks.enqueue(
        "deliver_webhook", path="/api/v1/webhooks/couriers/mock", body=raw.decode(), headers=headers
    )
    return {"status": "sent"}
