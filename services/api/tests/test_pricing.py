import pytest
from pydantic import ValidationError

from kitaab.domain.enums import Binding, Paper, PaymentMethod
from kitaab.domain.pricing import (
    PLACEHOLDER_RULES,
    PaperRate,
    PriceInput,
    PricingError,
    PricingRules,
    VolumeBracket,
    calculate,
    ceil_to_rupee,
    rate_for,
)
from kitaab.phone import mask_phone


@pytest.mark.parametrize(
    ("paisa", "expected"), [(0, 0), (1, 100), (99, 100), (100, 100), (101, 200), (38735, 38800)]
)
def test_ceil_to_rupee(paisa: int, expected: int) -> None:
    assert ceil_to_rupee(paisa) == expected


def test_brackets_are_order_independent() -> None:
    paper = PaperRate(
        rate_per_page_paisa=300,
        brackets=[
            VolumeBracket(min_printed_pages=5000, rate_per_page_paisa=200),
            VolumeBracket(min_printed_pages=1000, rate_per_page_paisa=250),
        ],
    )
    assert rate_for(paper, 999) == 300
    assert rate_for(paper, 1000) == 250
    assert rate_for(paper, 4999) == 250
    assert rate_for(paper, 5000) == 200


def test_duplicate_brackets_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PaperRate(
            rate_per_page_paisa=1,
            brackets=[
                VolumeBracket(min_printed_pages=10, rate_per_page_paisa=1),
                VolumeBracket(min_printed_pages=10, rate_per_page_paisa=2),
            ],
        )


def test_config_must_cover_every_paper_and_binding() -> None:
    data = PLACEHOLDER_RULES.model_dump()
    del data["papers"][Paper.IMPORTED_YELLOW]
    with pytest.raises(ValidationError, match="IMPORTED_YELLOW"):
        PricingRules.model_validate(data)


def test_negative_delivery_fee_is_rejected() -> None:
    data = PLACEHOLDER_RULES.model_dump()
    data["delivery_fees_paisa"]["Z1"] = -1
    with pytest.raises(ValidationError, match="negative"):
        PricingRules.model_validate(data)


def test_negative_override_is_rejected() -> None:
    item = PriceInput(
        pages=10,
        paper=Paper.LOCAL_WHITE,
        binding=Binding.SOFTCOVER_PAPERBACK,
        zone="Z1",
        goods_override_paisa=-1,
    )
    with pytest.raises(PricingError) as caught:
        calculate(PLACEHOLDER_RULES, 1, item)
    assert caught.value.code == "INVALID_OVERRIDE"


def test_cod_fee_only_for_cod() -> None:
    base = {"pages": 10, "paper": Paper.LOCAL_WHITE, "binding": Binding.SOFTCOVER_PAPERBACK}
    for method in PaymentMethod:
        result = calculate(
            PLACEHOLDER_RULES, 1, PriceInput(**base, zone="Z1", payment_method=method)
        )
        expected = PLACEHOLDER_RULES.cod_fee_paisa if method == PaymentMethod.COD else 0
        assert result.cod_fee_paisa == expected


@pytest.mark.parametrize(
    ("e164", "masked"), [("+923001234567", "+92300*****67"), (None, ""), ("+92", "***")]
)
def test_mask_phone(e164: str | None, masked: str) -> None:
    assert mask_phone(e164) == masked
