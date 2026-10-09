from typing import Literal

from fastapi import Depends
from sqlalchemy import select

from kitaab.api.routing import api_router
from kitaab.api.v1.presenters import city_out
from kitaab.domain import pricing_store
from kitaab.domain.app_settings import load as load_settings
from kitaab.domain.context import Ctx
from kitaab.domain.enums import PaymentMethod
from kitaab.domain.orders.service import pricing_problem
from kitaab.domain.pricing import PriceBreakdown, PriceInput, PricingError, PricingRules, calculate
from kitaab.legal import document
from kitaab.models import City
from kitaab.problems import invalid
from kitaab.schemas.catalog import (
    AppConfig,
    CityOut,
    LegalDocument,
    PaymentMethodOption,
    PriceQuoteRequest,
    PricingConfigOut,
    SupportContact,
)
from kitaab.security.deps import public_ctx

router = api_router(tags=["catalog"])


@router.get("/app/config")
def get_app_config(ctx: Ctx = Depends(public_ctx)) -> AppConfig:
    """Settings the app needs at start-up: support contact, payment methods, upload limits."""
    settings = load_settings(ctx)
    enabled = ctx.services.payments.enabled_methods()
    return AppConfig(
        terms_version=ctx.services.settings.terms_version,
        support=SupportContact(
            phone=settings.support_phone,
            whatsapp=settings.support_whatsapp,
            email=settings.support_email,
            hours=settings.support_hours,
        ),
        payment_methods=[
            PaymentMethodOption(method=m, enabled=m in enabled) for m in PaymentMethod
        ],
        max_upload_bytes=ctx.services.settings.max_upload_bytes,
        upload_part_bytes=ctx.services.settings.upload_part_bytes,
        cod_max_order_value_paisa=settings.cod_max_order_value_paisa,
    )


@router.get("/legal/{doc}")
def get_legal_document(doc: Literal["terms", "privacy", "copyright"]) -> LegalDocument:
    return document(doc)


@router.get("/cities")
def list_cities(ctx: Ctx = Depends(public_ctx)) -> list[CityOut]:
    rows = ctx.session.scalars(
        select(City).where(City.is_active).order_by(City.sort_order, City.name)
    )
    return [city_out(c) for c in rows]


@router.get("/pricing/config")
def get_pricing_config(ctx: Ctx = Depends(public_ctx)) -> PricingConfigOut:
    """The pricing rules in effect now, for the app's instant calculator."""
    config = pricing_store.active_config(ctx)
    rules = PricingRules.model_validate(config.rules)
    return PricingConfigOut(
        version=config.version, effective_from=config.effective_from, rules=rules
    )


@router.post("/pricing/quote")
def quote_price(body: PriceQuoteRequest, ctx: Ctx = Depends(public_ctx)) -> PriceBreakdown:
    """Server-side price for the given options."""
    city = ctx.session.get(City, body.city_id)
    if city is None or not city.is_active:
        raise invalid("city-not-served", "We do not deliver to this city yet")
    rules, version = pricing_store.active(ctx)
    try:
        return calculate(
            rules,
            version,
            PriceInput(
                pages=body.pages,
                paper=body.paper,
                binding=body.binding,
                copies=body.copies,
                zone=city.zone_code,
                payment_method=body.payment_method,
            ),
        )
    except PricingError as error:
        raise pricing_problem(error) from error
