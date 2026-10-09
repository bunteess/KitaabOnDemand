import uuid

from fastapi import Depends, Query, status
from sqlalchemy import func, select, update

from kitaab.api.routing import api_router
from kitaab.api.v1.presenters import notification_out
from kitaab.domain.context import Ctx
from kitaab.models import Notification
from kitaab.schemas.notifications import NotificationPage
from kitaab.security.deps import customer_ctx, me

router = api_router(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    ctx: Ctx = Depends(customer_ctx),
) -> NotificationPage:
    mine = Notification.user_id == me(ctx).id
    total = ctx.session.scalar(select(func.count()).select_from(Notification).where(mine)) or 0
    unread = (
        ctx.session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(mine, Notification.read_at.is_(None))
        )
        or 0
    )
    rows = ctx.session.scalars(
        select(Notification)
        .where(mine)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return NotificationPage(
        items=[notification_out(n) for n in rows],
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread,
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(notification_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> None:
    ctx.session.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == me(ctx).id,
            Notification.read_at.is_(None),
        )
        .values(read_at=ctx.now)
    )
    ctx.session.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(ctx: Ctx = Depends(customer_ctx)) -> None:
    ctx.session.execute(
        update(Notification)
        .where(Notification.user_id == me(ctx).id, Notification.read_at.is_(None))
        .values(read_at=ctx.now)
    )
    ctx.session.commit()
