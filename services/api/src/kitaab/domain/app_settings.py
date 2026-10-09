"""Admin-editable settings stored in the database."""

from typing import Any

from kitaab.domain.context import Ctx
from kitaab.models import AppSetting
from kitaab.schemas.admin import AppSettings

KEY = "app"


def load(ctx: Ctx) -> AppSettings:
    row = ctx.session.get(AppSetting, KEY)
    return AppSettings.model_validate(row.value if row else {})


def save(ctx: Ctx, settings: AppSettings) -> AppSettings:
    value: dict[str, Any] = settings.model_dump(mode="json")
    row = ctx.session.get(AppSetting, KEY)
    if row is None:
        row = AppSetting(key=KEY, value=value)
        ctx.session.add(row)
    else:
        row.value = value
    row.updated_by_id = ctx.user.id if ctx.user else None
    return settings
