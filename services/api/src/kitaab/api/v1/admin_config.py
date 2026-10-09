import uuid

from fastapi import APIRouter, Query, status

from kitaab.problems import not_implemented
from kitaab.schemas.admin import (
    AppSettings,
    AuditLogPage,
    CityAdminOut,
    CityIn,
    PricingConfigCreate,
    PricingConfigVersion,
)

router = APIRouter(prefix="/admin", tags=["admin: configuration"])


@router.get("/pricing-configs")
def admin_list_pricing_configs() -> list[PricingConfigVersion]:
    """Every pricing version, newest first."""
    raise not_implemented()


@router.post("/pricing-configs", status_code=status.HTTP_201_CREATED)
def admin_create_pricing_config(body: PricingConfigCreate) -> PricingConfigVersion:
    """Add a new version. Existing orders keep the version they were priced with."""
    raise not_implemented()


@router.get("/cities")
def admin_list_cities() -> list[CityAdminOut]:
    raise not_implemented()


@router.post("/cities", status_code=status.HTTP_201_CREATED)
def admin_create_city(body: CityIn) -> CityAdminOut:
    raise not_implemented()


@router.put("/cities/{city_id}")
def admin_update_city(city_id: uuid.UUID, body: CityIn) -> CityAdminOut:
    raise not_implemented()


@router.get("/settings")
def admin_get_settings() -> AppSettings:
    raise not_implemented()


@router.put("/settings")
def admin_update_settings(body: AppSettings) -> AppSettings:
    raise not_implemented()


@router.get("/audit-logs")
def admin_list_audit_logs(
    action: str | None = Query(None, max_length=60),
    entity_type: str | None = Query(None, max_length=40),
    entity_id: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> AuditLogPage:
    raise not_implemented()
