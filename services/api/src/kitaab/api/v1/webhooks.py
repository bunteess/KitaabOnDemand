from fastapi import APIRouter, Request

from kitaab.problems import not_implemented

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/payments/{provider}")
async def payment_webhook(provider: str, request: Request) -> dict[str, str]:
    """Signed payment notifications. Idempotent: repeats return 200 and change nothing."""
    raise not_implemented()


@router.post("/couriers/{provider}")
async def courier_webhook(provider: str, request: Request) -> dict[str, str]:
    """Signed courier status updates. Idempotent."""
    raise not_implemented()
