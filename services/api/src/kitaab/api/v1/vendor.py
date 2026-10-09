import uuid
from datetime import timedelta

from fastapi import Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select

from kitaab.api.routing import api_router
from kitaab.api.v1.presenters import vendor_order_detail, vendor_order_summary
from kitaab.domain import audit
from kitaab.domain.context import Ctx
from kitaab.domain.enums import Actor, OrderStatus
from kitaab.domain.orders import service as orders
from kitaab.models import Order
from kitaab.pdf.packing_slip import render_packing_slip
from kitaab.problems import PDF_RESPONSE, not_found
from kitaab.schemas.common import FileUrl
from kitaab.schemas.vendor import VendorOrderDetail, VendorOrderPage
from kitaab.security.deps import me, vendor_ctx

router = api_router(prefix="/vendor", tags=["vendor"])


def _assigned(ctx: Ctx, order_id: uuid.UUID, *, lock: bool = False) -> Order:
    order = orders.lock(ctx, order_id) if lock else ctx.session.get(Order, order_id)
    if order is None:
        raise not_found("Order")
    orders.ensure_vendor(order, me(ctx))
    return order


@router.get("/orders")
def vendor_list_orders(
    status: list[OrderStatus] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    ctx: Ctx = Depends(vendor_ctx),
) -> VendorOrderPage:
    """The print queue: only orders assigned to the signed-in vendor."""
    query = select(Order).where(Order.vendor_id == me(ctx).vendor_id)
    if status:
        query = query.where(Order.status.in_(status))
    total = ctx.session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = ctx.session.scalars(
        query.order_by(Order.assigned_at.desc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return VendorOrderPage(
        items=[vendor_order_summary(o) for o in rows], total=total, page=page, page_size=page_size
    )


@router.get("/orders/{order_id}")
def vendor_get_order(order_id: uuid.UUID, ctx: Ctx = Depends(vendor_ctx)) -> VendorOrderDetail:
    return vendor_order_detail(_assigned(ctx, order_id))


@router.get("/orders/{order_id}/file-url")
def vendor_file_url(order_id: uuid.UUID, ctx: Ctx = Depends(vendor_ctx)) -> FileUrl:
    """Five-minute download link. Every request is logged."""
    order = _assigned(ctx, order_id)
    if order.upload is None or order.upload.object_key is None:
        raise not_found("File")
    ttl = ctx.services.settings.download_url_ttl_seconds
    url = ctx.services.store.presign_get(order.upload.object_key, ttl, f"{order.code}.pdf")
    audit.record(
        ctx,
        "file.download",
        "order",
        order.id,
        upload_id=str(order.upload.id),
        vendor_id=str(me(ctx).vendor_id),
    )
    ctx.session.commit()
    return FileUrl(url=url, expires_at=ctx.now + timedelta(seconds=ttl))


@router.get("/orders/{order_id}/packing-slip", response_class=Response, responses=PDF_RESPONSE)
def vendor_packing_slip(order_id: uuid.UUID, ctx: Ctx = Depends(vendor_ctx)) -> Response:
    order = _assigned(ctx, order_id)
    pdf = render_packing_slip(order, ctx.services.couriers.name_of(order.courier_code))
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="packing-slip-{order.code}.pdf"'},
    )


def _advance(ctx: Ctx, order_id: uuid.UUID, target: OrderStatus, action: str) -> VendorOrderDetail:
    order = _assigned(ctx, order_id, lock=True)
    orders.transition(ctx, order, target, actor=Actor.VENDOR)
    audit.record(ctx, f"order.{action}", "order", order.id, status=order.status.value)
    ctx.session.commit()
    ctx.session.refresh(order)
    return vendor_order_detail(order)


@router.post("/orders/{order_id}/start-printing")
def vendor_start_printing(order_id: uuid.UUID, ctx: Ctx = Depends(vendor_ctx)) -> VendorOrderDetail:
    return _advance(ctx, order_id, OrderStatus.IN_PRINT, "start-printing")


@router.post("/orders/{order_id}/ready-for-dispatch")
def vendor_ready_for_dispatch(
    order_id: uuid.UUID, ctx: Ctx = Depends(vendor_ctx)
) -> VendorOrderDetail:
    return _advance(ctx, order_id, OrderStatus.READY_FOR_DISPATCH, "ready-for-dispatch")
