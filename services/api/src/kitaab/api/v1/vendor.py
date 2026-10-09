import uuid

from fastapi import APIRouter, Query
from fastapi.responses import Response

from kitaab.domain.enums import OrderStatus
from kitaab.problems import PDF_RESPONSE, not_implemented
from kitaab.schemas.common import FileUrl
from kitaab.schemas.vendor import VendorOrderDetail, VendorOrderPage

router = APIRouter(prefix="/vendor", tags=["vendor"])


@router.get("/orders")
def vendor_list_orders(
    status: list[OrderStatus] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> VendorOrderPage:
    """The print queue: only orders assigned to the signed-in vendor."""
    raise not_implemented()


@router.get("/orders/{order_id}")
def vendor_get_order(order_id: uuid.UUID) -> VendorOrderDetail:
    raise not_implemented()


@router.get("/orders/{order_id}/file-url")
def vendor_file_url(order_id: uuid.UUID) -> FileUrl:
    """Five-minute download link. Every request is logged."""
    raise not_implemented()


@router.get("/orders/{order_id}/packing-slip", response_class=Response, responses=PDF_RESPONSE)
def vendor_packing_slip(order_id: uuid.UUID) -> Response:
    raise not_implemented()


@router.post("/orders/{order_id}/start-printing")
def vendor_start_printing(order_id: uuid.UUID) -> VendorOrderDetail:
    raise not_implemented()


@router.post("/orders/{order_id}/ready-for-dispatch")
def vendor_ready_for_dispatch(order_id: uuid.UUID) -> VendorOrderDetail:
    raise not_implemented()
