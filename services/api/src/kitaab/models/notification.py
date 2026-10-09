import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from kitaab.db import Base
from kitaab.domain.enums import NotificationKind
from kitaab.models.base import default_now, enum_column, timestamp, uuid_pk


class Notification(Base):
    """The customer's in-app inbox. Push and SMS are delivery channels for these."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[NotificationKind] = mapped_column(enum_column(NotificationKind))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(500))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    read_at: Mapped[datetime | None] = timestamp()
    created_at: Mapped[datetime] = default_now()
