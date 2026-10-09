import uuid
from datetime import datetime

from kitaab.domain.enums import NotificationKind
from kitaab.schemas.common import PageMeta, Schema


class NotificationOut(Schema):
    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str
    order_id: uuid.UUID | None
    read: bool
    created_at: datetime


class NotificationPage(PageMeta):
    items: list[NotificationOut]
    unread_count: int
