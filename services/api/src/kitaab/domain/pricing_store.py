"""Versioned pricing configs. The active config is the highest version already in effect."""

from sqlalchemy import func, select

from kitaab.domain.context import Ctx
from kitaab.domain.pricing import PricingRules
from kitaab.models import PricingConfig
from kitaab.problems import ProblemError

CONFIG_MISSING = ProblemError(503, "pricing-unavailable", "Prices are not set up yet")


def active_config(ctx: Ctx) -> PricingConfig:
    config = ctx.session.scalar(
        select(PricingConfig)
        .where(PricingConfig.effective_from <= ctx.now)
        .order_by(PricingConfig.version.desc())
        .limit(1)
    )
    if config is None:
        raise CONFIG_MISSING
    return config


def active(ctx: Ctx) -> tuple[PricingRules, int]:
    config = active_config(ctx)
    return PricingRules.model_validate(config.rules), config.version


def by_version(ctx: Ctx, version: int) -> PricingRules:
    config = ctx.session.scalar(select(PricingConfig).where(PricingConfig.version == version))
    if config is None:
        raise CONFIG_MISSING
    return PricingRules.model_validate(config.rules)


def create(
    ctx: Ctx, rules: PricingRules, effective_from: object, notes: str | None
) -> PricingConfig:
    latest = ctx.session.scalar(select(func.max(PricingConfig.version))) or 0
    config = PricingConfig(
        version=latest + 1,
        effective_from=effective_from,
        rules=rules.model_dump(mode="json"),
        notes=notes,
        created_by_id=ctx.user.id if ctx.user else None,
        created_at=ctx.now,
    )
    ctx.session.add(config)
    ctx.session.flush()
    return config
