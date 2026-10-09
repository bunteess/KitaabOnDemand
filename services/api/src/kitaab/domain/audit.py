"""Audit trail. Details must never contain personal data."""

from typing import Any

from kitaab.domain.context import Ctx
from kitaab.models import AuditLog


def record(
    ctx: Ctx, action: str, entity_type: str, entity_id: object | None = None, **details: Any
) -> None:
    ctx.session.add(
        AuditLog(
            actor_user_id=ctx.user.id if ctx.user else None,
            actor_role=ctx.user.role if ctx.user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
            created_at=ctx.now,
        )
    )
