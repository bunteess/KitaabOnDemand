"""Real responses from the server, saved as examples for the clients.

The Android app's tests parse every file in packages/contracts/examples with
its models, so a field the app expects but the server does not send fails
there. This test fails when the shape of a response changes; refresh the
examples with `make contract-examples`.

Volatile values (ids, tokens, order codes, signed URLs) are replaced with
stable placeholders so the files only change when the API does.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from support import Api, pdf_bytes

pytestmark = pytest.mark.integration

EXAMPLES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "examples"
UPDATE = os.environ.get("KITAAB_UPDATE_EXAMPLES") == "1"

# Volatile values and the stable placeholder for the nth distinct one.
_PLACEHOLDERS = [
    (
        re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
        "00000000-0000-4000-8000-{n:012d}",
    ),
    (re.compile(r"\bKD[2-9A-Z]{7}\b"), "KD{n:07d}"),
    (re.compile(r"\bMOCK-\d{6}\b"), "MOCK-1{n:05d}"),
    (re.compile(r"mockpay_[0-9a-f]{20}"), "mockpay_{n:020d}"),
    (re.compile(r"mockrefund_[0-9a-f]{16}"), "mockrefund_{n:016d}"),
]


class _Normalizer:
    def __init__(self) -> None:
        self.seen: dict[str, str] = {}

    def _stable(self, value: str, template: str) -> str:
        if value not in self.seen:
            self.seen[value] = template.format(n=len(self.seen) + 1)
        return self.seen[value]

    def text(self, key: str, value: str) -> str:
        if key == "access_token":
            return "<access-token>"
        if key == "refresh_token":
            return "<refresh-token>"
        if "X-Amz-" in value:
            return "https://storage.example/presigned"
        for pattern, template in _PLACEHOLDERS:
            value = pattern.sub(lambda m, t=template: self._stable(m.group(), t), value)
        return value

    def __call__(self, value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {k: self(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [self(v, key) for v in value]
        if isinstance(value, str):
            return self.text(key, value)
        return value


def shape(value: Any) -> Any:
    """Keys and value types, ignoring the values themselves."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


def _ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def _capture(api: Api) -> dict[str, Any]:
    examples: dict[str, Any] = {}
    phone = "0300 1234567"
    examples["otp_requested"] = _ok(
        api.post("/api/v1/auth/otp/request", json={"phone": phone}), 202
    )
    wrong = api.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": "000001"})
    examples["problem_otp_invalid"] = wrong.json()
    pair = _ok(
        api.post(
            "/api/v1/auth/otp/verify",
            json={"phone": phone, "code": api.last_code("+923001234567")},
        )
    )
    examples["token_pair"] = pair
    from support import Person

    customer = Person(pair["user"]["id"], pair["access_token"], pair["refresh_token"])
    examples["me"] = _ok(
        api.post(
            "/api/v1/me/terms",
            customer,
            {"terms_version": api.services.settings.terms_version},
        )
    )
    examples["app_config"] = _ok(api.get("/api/v1/app/config"))
    examples["cities"] = _ok(api.get("/api/v1/cities"))[:3]
    examples["pricing_config"] = _ok(api.get("/api/v1/pricing/config"))
    examples["legal_terms"] = _ok(api.get("/api/v1/legal/terms"))
    address_id = api.address(customer)
    examples["addresses"] = _ok(api.get("/api/v1/me/addresses", customer))

    content = pdf_bytes(12)
    session = _ok(
        api.post(
            "/api/v1/uploads",
            customer,
            {
                "filename": "notes.pdf",
                "size_bytes": len(content),
                "client_page_count": 12,
                "copyright_declared": True,
            },
        ),
        201,
    )
    examples["upload_session"] = session
    import httpx2

    httpx2.put(session["parts"][0]["url"], content=content).raise_for_status()
    upload_id = session["upload"]["id"]
    examples["upload_part_urls"] = _ok(
        api.post(f"/api/v1/uploads/{upload_id}/parts", customer, {"part_numbers": [1]})
    )
    _ok(api.post(f"/api/v1/uploads/{upload_id}/complete", customer), 202)
    examples["upload_valid"] = _ok(api.get(f"/api/v1/uploads/{upload_id}", customer))
    examples["upload_rejected"] = api.upload(customer, b"%PDF-1.7 broken", "broken.pdf")

    total = api.quote_price(12, "LOCAL_WHITE", "SOFTCOVER_PAPERBACK", 1, "Lahore", "EASYPAISA")
    body = {
        "upload_id": upload_id,
        "paper": "LOCAL_WHITE",
        "binding": "SOFTCOVER_PAPERBACK",
        "copies": 1,
        "address_id": str(address_id),
        "payment_method": "EASYPAISA",
        "expected_total_paisa": total + 100,
    }
    examples["problem_price_mismatch"] = api.post("/api/v1/orders/print", customer, body).json()
    pending = _ok(
        api.post("/api/v1/orders/print", customer, {**body, "expected_total_paisa": total}),
        201,
    )
    examples["order_print_pending_payment"] = pending
    examples["checkout_session"] = _ok(
        api.post(f"/api/v1/orders/{pending['id']}/payments", customer), 201
    )
    pending = _ok(api.get(f"/api/v1/orders/{pending['id']}", customer))
    api.pay(pending)

    admin = api.admin()
    vendor = api.vendor()
    for action, payload in (
        ("start-verification", {}),
        ("approve", {"vendor_id": str(vendor), "vendor_cost_paisa": 20000}),
        ("start-printing", {}),
        ("ready-for-dispatch", {}),
        ("dispatch", {"courier_code": "mock"}),
    ):
        api.admin_action(admin, pending["id"], action, payload)
    examples["order_print_dispatched"] = _ok(api.get(f"/api/v1/orders/{pending['id']}", customer))

    cod = api.print_order(customer, method="COD", pages=4)
    examples["order_print_cancelled"] = _ok(
        api.post(f"/api/v1/orders/{cod['id']}/cancel", customer, {"reason": "Changed my mind"})
    )

    source = api.source_order(customer, title="Aab-e-Hayat")
    examples["order_source_requested"] = source
    api.admin_action(
        admin,
        source["id"],
        "quote",
        {
            "pages": 450,
            "paper": "IMPORTED_YELLOW",
            "binding": "PREMIUM_HARDCOVER",
            "copies": 1,
            "sourcing_cost_paisa": 60000,
        },
    )
    quoted = _ok(api.get(f"/api/v1/orders/{source['id']}", customer))
    examples["order_source_quoted"] = quoted
    examples["order_source_accepted"] = _ok(
        api.post(
            f"/api/v1/orders/{source['id']}/quote/accept",
            customer,
            {
                "payment_method": "COD",
                "expected_total_paisa": quoted["quote"]["total_if_cod_paisa"],
            },
        )
    )
    examples["orders_page"] = _ok(api.get("/api/v1/orders?page_size=2", customer))
    examples["notifications_page"] = _ok(api.get("/api/v1/notifications?page_size=3", customer))
    examples["account_deletion"] = _ok(
        api.post("/api/v1/me/delete", customer, {"confirm": "DELETE"})
    )
    return examples


def test_examples_match_the_server(api: Api) -> None:
    normalize = _Normalizer()
    fresh = {name: normalize(value) for name, value in _capture(api).items()}
    if UPDATE:
        EXAMPLES.mkdir(parents=True, exist_ok=True)
        for old in EXAMPLES.glob("*.json"):
            old.unlink()
        for name, value in fresh.items():
            text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
            (EXAMPLES / f"{name}.json").write_text(text, encoding="utf-8")
        return
    saved = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in EXAMPLES.glob("*.json")}
    assert set(saved) == set(fresh), "run 'make contract-examples'"
    changed = [name for name in fresh if shape(fresh[name]) != shape(saved[name])]
    assert not changed, f"response shapes changed: {changed}; run 'make contract-examples'"
