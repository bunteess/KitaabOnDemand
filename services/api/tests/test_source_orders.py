"""SOURCE orders: book requests, quotes, acceptance, expiry and sourcing."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from kitaab.domain.enums import LedgerEntryType
from kitaab.models import LedgerEntry, Quote
from support import Api, Person

pytestmark = pytest.mark.integration

QUOTE = {
    "pages": 320,
    "paper": "IMPORTED_YELLOW",
    "binding": "PREMIUM_HARDCOVER",
    "copies": 1,
    "sourcing_cost_paisa": 50000,
}


def _quote(api: Api, admin: Person, order_id: str, **changes: Any) -> dict[str, Any]:
    return api.admin_action(admin, order_id, "quote", {**QUOTE, **changes})


def test_request_quote_accept_cod_and_deliver(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer, title="Raja Gidh")
    assert order["status"] == "REQUESTED"
    assert order["book"]["title"] == "Raja Gidh"
    assert order["total_paisa"] is None
    assert [t["step"] for t in order["timeline"]] == [
        "PLACED",
        "VERIFYING",
        "OUT_FOR_DELIVERY",
        "COMPLETED",
    ]
    admin = api.admin()

    preview = api.post(f"/api/v1/admin/orders/{order['id']}/quote/preview", admin, QUOTE)
    assert preview.status_code == 200
    totals = preview.json()
    assert totals["total_if_cod_paisa"] > totals["total_if_digital_paisa"]

    quoted = _quote(api, admin, order["id"], valid_hours=24)
    assert quoted["status"] == "QUOTED"
    assert quoted["quotes"][0]["status"] == "OPEN"

    mine = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    quote = mine["quote"]
    assert quote["total_if_cod_paisa"] == totals["total_if_cod_paisa"]
    assert quote["total_if_digital_paisa"] == totals["total_if_digital_paisa"]
    assert quote["valid_until"].startswith("2026-10-10T05:00:00")
    summary = api.get("/api/v1/orders", customer).json()["items"][0]
    assert summary["needs_action"] is True

    wrong = api.post(
        f"/api/v1/orders/{order['id']}/quote/accept",
        customer,
        {"payment_method": "COD", "expected_total_paisa": quote["total_if_digital_paisa"]},
    )
    assert wrong.status_code == 409
    assert wrong.json()["code"] == "price-mismatch"

    accepted = api.post(
        f"/api/v1/orders/{order['id']}/quote/accept",
        customer,
        {"payment_method": "COD", "expected_total_paisa": quote["total_if_cod_paisa"]},
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "ACCEPTED"
    assert body["total_paisa"] == quote["total_if_cod_paisa"]
    assert body["pages"] == 320
    assert body["payment"]["method"] == "COD"

    vendor = api.vendor()
    api.admin_action(
        admin,
        order["id"],
        "start-sourcing",
        {"vendor_id": str(vendor), "vendor_cost_paisa": 45000},
    )
    ready = api.admin_action(admin, order["id"], "ready-for-dispatch")
    assert ready["status"] == "READY_FOR_DISPATCH"
    cn = api.admin_action(admin, order["id"], "dispatch", {"courier_code": "mock"})["tracking"][
        "cn_number"
    ]
    api.post(f"/api/v1/_dev/mock-courier/{cn}/events", json={"state": "DELIVERED"})
    with api.services.session() as session:
        entries = sorted(
            (t.value, a)
            for t, a in session.execute(
                select(LedgerEntry.entry_type, LedgerEntry.amount_paisa).where(
                    LedgerEntry.order_id == order["id"]
                )
            )
        )
    assert entries == sorted(
        [
            (LedgerEntryType.VENDOR_COST_ACCRUED.value, 45000),
            (LedgerEntryType.COD_COLLECTED.value, body["total_paisa"]),
            (LedgerEntryType.REVENUE.value, body["total_paisa"]),
        ]
    )


def test_accept_with_online_payment(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    _quote(api, admin, order["id"])
    quote = api.get(f"/api/v1/orders/{order['id']}", customer).json()["quote"]
    accepted = api.post(
        f"/api/v1/orders/{order['id']}/quote/accept",
        customer,
        {"payment_method": "EASYPAISA", "expected_total_paisa": quote["total_if_digital_paisa"]},
    ).json()
    assert accepted["awaiting_payment"] is True
    early = api.post(f"/api/v1/admin/orders/{order['id']}/start-sourcing", admin, {})
    assert early.status_code == 409
    assert early.json()["code"] == "payment-pending"

    api.pay(accepted)
    paid = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert paid["status"] == "ACCEPTED"
    assert paid["payment"]["status"] == "PAID"
    assert api.admin_action(admin, order["id"], "start-sourcing")["status"] == "SOURCING"

    # Book not found after payment: refunded automatically.
    unavailable = api.admin_action(
        admin, order["id"], "mark-unavailable", {"reason": "Out of print"}
    )
    assert unavailable["status"] == "UNAVAILABLE"
    assert unavailable["refunds"][0]["status"] == "PROCESSED"


def test_decline(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    _quote(api, admin, order["id"])
    declined = api.post(f"/api/v1/orders/{order['id']}/quote/decline", customer)
    assert declined.status_code == 200
    assert declined.json()["status"] == "DECLINED"
    with api.services.session() as session:
        statuses = session.scalars(select(Quote.status)).all()
    assert [s.value for s in statuses] == ["DECLINED"]
    again = api.post(f"/api/v1/orders/{order['id']}/quote/decline", customer)
    assert again.status_code == 409
    accept = api.post(
        f"/api/v1/orders/{order['id']}/quote/accept",
        customer,
        {"payment_method": "COD", "expected_total_paisa": 1},
    )
    assert accept.status_code == 409
    assert accept.json()["code"] == "no-open-quote"


def test_quotes_expire(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    _quote(api, admin, order["id"])  # default validity: 48 hours
    api.clock.advance(timedelta(hours=47, minutes=59))
    assert api.post("/api/v1/_dev/jobs/expire_quotes").json()["result"] == 0
    api.later(timedelta(minutes=1), customer)
    assert api.post("/api/v1/_dev/jobs/expire_quotes").json()["result"] == 1
    expired = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert expired["status"] == "QUOTE_EXPIRED"
    assert expired["exit"]["status"] == "QUOTE_EXPIRED"
    assert api.post("/api/v1/_dev/jobs/expire_quotes").json()["result"] == 0


def test_accepting_an_expired_quote_expires_the_order(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    _quote(api, admin, order["id"], valid_hours=1)
    quote = api.get(f"/api/v1/orders/{order['id']}", customer).json()["quote"]
    api.later(timedelta(hours=1), customer)
    response = api.post(
        f"/api/v1/orders/{order['id']}/quote/accept",
        customer,
        {"payment_method": "COD", "expected_total_paisa": quote["total_if_cod_paisa"]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "quote-expired"
    assert api.get(f"/api/v1/orders/{order['id']}", customer).json()["status"] == "QUOTE_EXPIRED"


def test_quote_override_needs_a_reason_and_is_audited(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    missing = api.post(
        f"/api/v1/admin/orders/{order['id']}/quote",
        admin,
        {**QUOTE, "goods_override_paisa": 99900},
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "override-reason-required"
    quoted = _quote(
        api, admin, order["id"], goods_override_paisa=99900, override_reason="Rare edition"
    )
    stored = quoted["quotes"][0]
    assert stored["goods_paisa"] == 99900
    assert stored["calculated_goods_paisa"] != 99900
    assert stored["override_reason"] == "Rare edition"
    logs = api.get("/api/v1/admin/audit-logs?action=order.quote", admin).json()
    assert logs["items"][0]["details"]["overridden"] is True


def test_customer_cancels_a_request(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    _quote(api, admin, order["id"])
    cancelled = api.post(f"/api/v1/orders/{order['id']}/cancel", customer, {}).json()
    assert cancelled["status"] == "CANCELLED"
    with api.services.session() as session:
        assert [s.value for s in session.scalars(select(Quote.status))] == ["CANCELLED"]


def test_unavailable_before_quoting(api: Api) -> None:
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    done = api.admin_action(
        admin, order["id"], "mark-unavailable", {"reason": "No supplier has it"}
    )
    assert done["status"] == "UNAVAILABLE"
    mine = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert mine["exit"]["reason"] == "No supplier has it"
    assert mine["can_cancel"] is False


def test_too_many_copies(api: Api) -> None:
    customer = api.customer()
    response = api.post(
        "/api/v1/orders/source",
        customer,
        {"book_title": "X", "copies": 10_000, "address_id": str(api.address(customer))},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "pricing-error"
