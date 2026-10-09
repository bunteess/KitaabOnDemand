from typing import Literal

from fastapi import APIRouter

from kitaab.domain.pricing import PriceBreakdown
from kitaab.problems import not_implemented
from kitaab.schemas.catalog import (
    AppConfig,
    CityOut,
    LegalDocument,
    PriceQuoteRequest,
    PricingConfigOut,
)

router = APIRouter(tags=["catalog"])


@router.get("/app/config")
def get_app_config() -> AppConfig:
    """Settings the app needs at start-up: support contact, payment methods, upload limits."""
    raise not_implemented()


@router.get("/legal/{doc}")
def get_legal_document(doc: Literal["terms", "privacy", "copyright"]) -> LegalDocument:
    raise not_implemented()


@router.get("/cities")
def list_cities() -> list[CityOut]:
    raise not_implemented()


@router.get("/pricing/config")
def get_pricing_config() -> PricingConfigOut:
    """The pricing rules in effect now, for the app's instant calculator."""
    raise not_implemented()


@router.post("/pricing/quote")
def quote_price(body: PriceQuoteRequest) -> PriceBreakdown:
    """Server-side price for the given options."""
    raise not_implemented()
