import uuid

from fastapi import APIRouter, Query, status

from kitaab.problems import not_implemented
from kitaab.schemas.notifications import NotificationPage

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)
) -> NotificationPage:
    raise not_implemented()


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(notification_id: uuid.UUID) -> None:
    raise not_implemented()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read() -> None:
    raise not_implemented()
