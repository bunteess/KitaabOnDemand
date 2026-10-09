import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from kitaab.domain import app_settings, audit, pricing_store
from kitaab.domain.context import Ctx
from kitaab.domain.pricing import PricingRules
from kitaab.models import AuditLog, City, PricingConfig, User
from kitaab.problems import ProblemError, conflict, not_found
from kitaab.schemas.admin import (
    AppSettings,
    AuditLogOut,
    AuditLogPage,
    CityAdminOut,
    CityIn,
    PricingConfigCreate,
    PricingConfigVersion,
)
from kitaab.security.deps import admin_ctx

router = APIRouter(prefix="/admin", tags=["admin: configuration"])


def _version_out(
    config: PricingConfig, active_version: int | None, names: dict[uuid.UUID, str | None]
) -> PricingConfigVersion:
    return PricingConfigVersion(
        version=config.version,
        effective_from=config.effective_from,
        rules=PricingRules.model_validate(config.rules),
        notes=config.notes,
        created_by_name=names.get(config.created_by_id) if config.created_by_id else None,
        created_at=config.created_at,
        active=config.version == active_version,
    )


def _names(ctx: Ctx, ids: set[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    if not ids:
        return {}
    return {
        u.id: u.full_name or u.email
        for u in ctx.session.scalars(select(User).where(User.id.in_(ids)))
    }


def _active_version(ctx: Ctx) -> int | None:
    try:
        return pricing_store.active_config(ctx).version
    except ProblemError:  # no config in effect yet
        return None


@router.get("/pricing-configs")
def admin_list_pricing_configs(ctx: Ctx = Depends(admin_ctx)) -> list[PricingConfigVersion]:
    """Every pricing version, newest first."""
    configs = ctx.session.scalars(
        select(PricingConfig).order_by(PricingConfig.version.desc())
    ).all()
    names = _names(ctx, {c.created_by_id for c in configs if c.created_by_id})
    active = _active_version(ctx)
    return [_version_out(c, active, names) for c in configs]


@router.post("/pricing-configs", status_code=status.HTTP_201_CREATED)
def admin_create_pricing_config(
    body: PricingConfigCreate, ctx: Ctx = Depends(admin_ctx)
) -> PricingConfigVersion:
    """Add a new version. Existing orders keep the version they were priced with."""
    config = pricing_store.create(ctx, body.rules, body.effective_from, body.notes)
    audit.record(
        ctx,
        "pricing.create",
        "pricing_config",
        config.version,
        effective_from=body.effective_from.isoformat(),
    )
    ctx.session.commit()
    return _version_out(
        config,
        _active_version(ctx),
        _names(ctx, {config.created_by_id} if config.created_by_id else set()),
    )


def _city_out(city: City) -> CityAdminOut:
    return CityAdminOut(
        id=city.id,
        name=city.name,
        province=city.province,
        zone_code=city.zone_code,
        is_active=city.is_active,
        sort_order=city.sort_order,
    )


def _apply_city(ctx: Ctx, city: City, body: CityIn) -> None:
    duplicate = ctx.session.scalar(
        select(City.id).where(func.lower(City.name) == body.name.lower(), City.id != city.id)
    )
    if duplicate is not None:
        raise conflict("city-exists", "A city with this name already exists")
    city.name = body.name
    city.province = body.province
    city.zone_code = body.zone_code.strip().upper()
    city.is_active = body.is_active
    city.sort_order = body.sort_order


@router.get("/cities")
def admin_list_cities(ctx: Ctx = Depends(admin_ctx)) -> list[CityAdminOut]:
    return [
        _city_out(c) for c in ctx.session.scalars(select(City).order_by(City.sort_order, City.name))
    ]


@router.post("/cities", status_code=status.HTTP_201_CREATED)
def admin_create_city(body: CityIn, ctx: Ctx = Depends(admin_ctx)) -> CityAdminOut:
    city = City(created_at=ctx.now)
    _apply_city(ctx, city, body)
    ctx.session.add(city)
    ctx.session.flush()
    audit.record(ctx, "city.create", "city", city.id, zone=city.zone_code)
    ctx.session.commit()
    return _city_out(city)


@router.put("/cities/{city_id}")
def admin_update_city(
    city_id: uuid.UUID, body: CityIn, ctx: Ctx = Depends(admin_ctx)
) -> CityAdminOut:
    city = ctx.session.get(City, city_id)
    if city is None:
        raise not_found("City")
    _apply_city(ctx, city, body)
    audit.record(ctx, "city.update", "city", city.id, zone=city.zone_code, is_active=city.is_active)
    ctx.session.commit()
    return _city_out(city)


@router.get("/settings")
def admin_get_settings(ctx: Ctx = Depends(admin_ctx)) -> AppSettings:
    return app_settings.load(ctx)


@router.put("/settings")
def admin_update_settings(body: AppSettings, ctx: Ctx = Depends(admin_ctx)) -> AppSettings:
    saved = app_settings.save(ctx, body)
    audit.record(
        ctx,
        "settings.update",
        "settings",
        None,
        cod_max_order_value_paisa=body.cod_max_order_value_paisa,
        quote_validity_hours=body.quote_validity_hours,
    )
    ctx.session.commit()
    return saved


@router.get("/audit-logs")
def admin_list_audit_logs(
    action: str | None = Query(None, max_length=60),
    entity_type: str | None = Query(None, max_length=40),
    entity_id: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ctx: Ctx = Depends(admin_ctx),
) -> AuditLogPage:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    total = ctx.session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = ctx.session.scalars(
        query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    names = _names(ctx, {r.actor_user_id for r in rows if r.actor_user_id})
    return AuditLogPage(
        items=[
            AuditLogOut(
                id=r.id,
                actor_name=names.get(r.actor_user_id) if r.actor_user_id else None,
                actor_role=r.actor_role,
                action=r.action,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                details=r.details or {},
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
