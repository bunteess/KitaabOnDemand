import uuid
from typing import Literal

from fastapi import APIRouter, Query, status

from kitaab.problems import not_implemented
from kitaab.schemas.orders import (
    CancelRequest,
    CheckoutSession,
    OrderDetail,
    OrderPage,
    PrintOrderCreate,
    QuoteAccept,
    SourceOrderCreate,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/print", status_code=status.HTTP_201_CREATED)
def create_print_order(body: PrintOrderCreate) -> OrderDetail:
    """Order prints of a validated upload. Digital payments return a checkout URL."""
    raise not_implemented()


@router.post("/source", status_code=status.HTTP_201_CREATED)
def create_source_order(body: SourceOrderCreate) -> OrderDetail:
    """Ask us to find a book. An admin sends a quote."""
    raise not_implemented()


@router.get("")
def list_orders(
    group: Literal["active", "past", "all"] = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
) -> OrderPage:
    raise not_implemented()


@router.get("/{order_id}")
def get_order(order_id: uuid.UUID) -> OrderDetail:
    raise not_implemented()


@router.post("/{order_id}/cancel")
def cancel_order(order_id: uuid.UUID, body: CancelRequest) -> OrderDetail:
    raise not_implemented()


@router.post("/{order_id}/quote/accept")
def accept_quote(order_id: uuid.UUID, body: QuoteAccept) -> OrderDetail:
    raise not_implemented()


@router.post("/{order_id}/quote/decline")
def decline_quote(order_id: uuid.UUID) -> OrderDetail:
    raise not_implemented()


@router.post("/{order_id}/payments", status_code=status.HTTP_201_CREATED)
def retry_payment(order_id: uuid.UUID) -> CheckoutSession:
    """Start a new checkout for an order whose digital payment is still pending."""
    raise not_implemented()
