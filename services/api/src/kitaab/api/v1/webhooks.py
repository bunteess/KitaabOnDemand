import logging

from fastapi import Depends, Request

from kitaab.api.routing import api_router
from kitaab.domain import payments, shipping
from kitaab.domain.context import Ctx
from kitaab.problems import ProblemError, not_found
from kitaab.providers.errors import InvalidSignature, NotConfigured
from kitaab.security.deps import public_ctx

router = api_router(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)

BAD_SIGNATURE = ProblemError(401, "invalid-signature", "Signature check failed")


async def raw_body(request: Request) -> bytes:
    """The exact bytes the provider signed. Reading them is the only async step,
    so the endpoints stay sync and their database work runs on a request thread,
    never on the event loop (D-051)."""
    return await request.body()


@router.post("/payments/{provider}")
def payment_webhook(
    provider: str,
    request: Request,
    body: bytes = Depends(raw_body),
    ctx: Ctx = Depends(public_ctx),
) -> dict[str, str]:
    """Signed payment notifications. Idempotent: repeats return 200 and change nothing."""
    gateway = ctx.services.payments.get(provider)
    if gateway is None:
        raise not_found("Payment provider")
    try:
        event = gateway.parse_webhook(dict(request.headers), body)
    except InvalidSignature as error:
        log.warning("payment webhook rejected", extra={"provider": provider})
        raise BAD_SIGNATURE from error
    except NotConfigured as error:
        raise not_found("Payment provider") from error
    result = payments.apply_payment_event(ctx, provider, event)
    ctx.session.commit()
    return {"status": result}


@router.post("/couriers/{provider}")
def courier_webhook(
    provider: str,
    request: Request,
    body: bytes = Depends(raw_body),
    ctx: Ctx = Depends(public_ctx),
) -> dict[str, str]:
    """Signed courier status updates. Idempotent."""
    courier = ctx.services.couriers.get(provider)
    if courier is None or not courier.supports_webhooks:
        raise not_found("Courier")
    try:
        events = courier.parse_webhook(dict(request.headers), body)
    except InvalidSignature as error:
        log.warning("courier webhook rejected", extra={"provider": provider})
        raise BAD_SIGNATURE from error
    applied = shipping.apply_courier_events(ctx, provider, events)
    ctx.session.commit()
    return {"status": "processed", "applied": str(applied)}
