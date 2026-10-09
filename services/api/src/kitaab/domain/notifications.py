"""The customer's inbox, delivered by push and, for key updates, SMS."""

import logging
import uuid

from sqlalchemy import delete, select

from kitaab.container import Services
from kitaab.domain import notification_texts as texts
from kitaab.domain.context import Ctx
from kitaab.domain.enums import NotificationKind
from kitaab.models import Device, Notification, Order, User
from kitaab.providers.errors import ProviderError
from kitaab.providers.push import PushMessage
from kitaab.tx import after_commit

log = logging.getLogger(__name__)


def notify(
    ctx: Ctx,
    user_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str,
    *,
    order: Order | None = None,
    sms: bool = False,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        order_id=order.id if order else None,
        created_at=ctx.now,
    )
    ctx.session.add(notification)
    ctx.session.flush()
    send_sms = sms and ctx.services.settings.sms_fallback_enabled
    notification_id = str(notification.id)
    tasks = ctx.services.tasks
    after_commit(
        ctx.session,
        lambda: tasks.enqueue(
            "deliver_notification", notification_id=notification_id, send_sms=send_sms
        ),
    )
    return notification


def notify_order_status(ctx: Ctx, order: Order) -> None:
    message = texts.for_status(
        order, courier_name=ctx.services.couriers.name_of(order.courier_code)
    )
    if message is None:
        return
    kind = (
        NotificationKind.QUOTE_READY
        if order.status.value == "QUOTED"
        else NotificationKind.ORDER_STATUS
    )
    notify(ctx, order.user_id, kind, *message, order=order, sms=order.status in texts.SMS_STATUSES)


def deliver(services: Services, notification_id: str, send_sms: bool = False) -> None:
    """Background job: push to every device, drop dead tokens, optionally SMS."""
    with services.session() as session:
        notification = session.get(Notification, uuid.UUID(notification_id))
        if notification is None:
            return
        user = session.get(User, notification.user_id)
        if user is None or user.deleted_at is not None:
            return
        tokens = list(session.scalars(select(Device.push_token).where(Device.user_id == user.id)))
        data = {"kind": notification.kind.value, "notification_id": notification_id}
        if notification.order_id:
            data["order_id"] = str(notification.order_id)
            data["link"] = f"kitaab://app/orders/{notification.order_id}"
        if tokens:
            try:
                invalid = services.push.send(
                    tokens, PushMessage(notification.title, notification.body, data)
                )
            except ProviderError:
                log.warning("push failed", extra={"notification_id": notification_id})
                invalid = []
            if invalid:
                session.execute(delete(Device).where(Device.push_token.in_(invalid)))
                session.commit()
        if send_sms and user.phone_e164:
            try:
                services.sms.send(user.phone_e164, f"{notification.title}: {notification.body}")
            except ProviderError:
                log.warning("sms fallback failed", extra={"notification_id": notification_id})
