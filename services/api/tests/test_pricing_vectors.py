"""Runs packages/contracts/pricing_vectors.json, the cases the Dart calculator also runs."""

import json
from pathlib import Path
from typing import Any

import pytest

from kitaab.domain.pricing import PriceInput, PricingError, PricingRules, calculate
from kitaab.money import format_pkr
from kitaab.phone import InvalidPhoneError, normalize_pk_mobile

VECTORS = json.loads(
    (Path(__file__).resolve().parents[3] / "packages/contracts/pricing_vectors.json").read_text()
)


def _config(name: str) -> tuple[PricingRules, int]:
    config = VECTORS["configs"][name]
    return PricingRules.model_validate(config["rules"]), config["version"]


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_pricing_case(case: dict[str, Any]) -> None:
    rules, version = _config(case["config"])
    item = PriceInput.model_validate(case["input"])
    if "expected_error" in case:
        with pytest.raises(PricingError) as caught:
            calculate(rules, version, item)
        assert caught.value.code == case["expected_error"]
        return
    breakdown = calculate(rules, version, item).model_dump(mode="json")
    for key, value in case["expected"].items():
        assert breakdown[key] == value, f"{key}: {breakdown[key]} != {value}"
    assert breakdown["config_version"] == version


@pytest.mark.parametrize("case", VECTORS["format_cases"], ids=lambda c: str(c["paisa"]))
def test_format_case(case: dict[str, Any]) -> None:
    assert format_pkr(case["paisa"]) == case["text"]


@pytest.mark.parametrize("case", VECTORS["phone_cases"], ids=lambda c: c["input"] or "empty")
def test_phone_case(case: dict[str, Any]) -> None:
    if case["e164"] is None:
        with pytest.raises(InvalidPhoneError):
            normalize_pk_mobile(case["input"])
    else:
        assert normalize_pk_mobile(case["input"]) == case["e164"]
