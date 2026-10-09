"""PRINT orders through the API: ordering, payment, review, printing,
dispatch, courier updates, cancellation and refunds."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from kitaab.domain.enums import LedgerEntryType
from kitaab.models import LedgerEntry, Notification, Order, OrderStatusHistory, Payment, Refund
from support import Api, Person, pdf_bytes

pytestmark = pytest.mark.integration


def _ledger(api: Api, order_id: str) -> list[tuple[LedgerEntryType, int]]:
    with api.services.session() as session:
        rows = session.execute(
            select(LedgerEntry.entry_type, LedgerEntry.amount_paisa)
            .where(LedgerEntry.order_id == order_id)
            .order_by(LedgerEntry.occurred_at, LedgerEntry.entry_type)
        ).all()
    return [(t, a) for t, a in rows]


def _steps(order: dict[str, Any]) -> dict[str, str]:
    return {entry["step"]: entry["state"] for entry in order["timeline"]}


def _through_printing(api: Api, admin: Person, order_id: str, vendor: Person) -> None:
    api.clock.advance(timedelta(minutes=5))
    api.admin_action(admin, order_id, "start-verification")
    api.clock.advance(timedelta(minutes=5))
    api.admin_action(
        admin,
        order_id,
        "approve",
        {"vendor_id": str(vendor.vendor_id), "vendor_cost_paisa": 30000},
    )
    api.later(timedelta(hours=1), vendor)
    assert api.post(f"/api/v1/vendor/orders/{order_id}/start-printing", vendor).status_code == 200
    api.later(timedelta(hours=3), vendor, admin)
    ready = api.post(f"/api/v1/vendor/orders/{order_id}/ready-for-dispatch", vendor)
    assert ready.status_code == 200, ready.text


def test_cod_order_from_upload_to_completion(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, pages=40, copies=2)
    order_id = order["id"]
    assert order["status"] == "PLACED"
    assert order["code"].startswith("KD")
    assert order["pages"] == 40
    assert order["payment"]["method"] == "COD"
    assert order["payment"]["checkout_url"] is None
    assert order["can_cancel"] is True
    assert _steps(order) == {
        "PLACED": "CURRENT",
        "VERIFYING": "UPCOMING",
        "PRINTING": "UPCOMING",
        "OUT_FOR_DELIVERY": "UPCOMING",
        "COMPLETED": "UPCOMING",
    }
    total = order["total_paisa"]
    assert total == order["price"]["total_paisa"]
    assert order["price"]["cod_fee_paisa"] > 0

    admin = api.admin()
    vendor = api.vendor_user(api.vendor())
    _through_printing(api, admin, order_id, vendor)
    api.renew(customer)

    mine = api.get(f"/api/v1/orders/{order_id}", customer).json()
    assert mine["status"] == "READY_FOR_DISPATCH"
    assert mine["can_cancel"] is False
    assert _steps(mine)["PRINTING"] == "CURRENT"
    assert _ledger(api, order_id) == [(LedgerEntryType.VENDOR_COST_ACCRUED, 30000)]

    api.later(timedelta(hours=1), admin, customer)
    dispatched = api.admin_action(admin, order_id, "dispatch", {"courier_code": "mock"})
    cn = dispatched["tracking"]["cn_number"]
    assert cn.startswith("MOCK-")
    assert dispatched["tracking"]["tracking_url"].endswith(cn)

    # The mock courier posts a signed webhook when the parcel moves.
    api.later(timedelta(days=1), admin, customer)
    moved = api.post(f"/api/v1/_dev/mock-courier/{cn}/events", json={"state": "IN_TRANSIT"})
    assert moved.status_code == 200
    mine = api.get(f"/api/v1/orders/{order_id}", customer).json()
    assert mine["status"] == "DISPATCHED"
    assert mine["tracking"]["last_status"] == "In Transit"
    api.later(timedelta(days=1), admin, customer)
    api.post(f"/api/v1/_dev/mock-courier/{cn}/events", json={"state": "DELIVERED"})

    mine = api.get(f"/api/v1/orders/{order_id}", customer).json()
    assert mine["status"] == "DELIVERED"
    # Customers see a delivered order as complete (D-013).
    assert set(_steps(mine).values()) == {"DONE"}
    assert _ledger(api, order_id) == [
        (LedgerEntryType.VENDOR_COST_ACCRUED, 30000),
        (LedgerEntryType.COD_COLLECTED, total),
        (LedgerEntryType.REVENUE, total),
    ]

    # The courier sends the cash: the COD payment is settled and the order completes.
    remitted = api.post(
        "/api/v1/admin/finance/cod-remittances",
        admin,
        {"courier_code": "mock", "order_ids": [order_id], "reference": "MOCK-REMIT-1"},
    )
    assert remitted.status_code == 201, remitted.text
    final = api.get(f"/api/v1/admin/orders/{order_id}", admin).json()
    assert final["status"] == "COMPLETED"
    assert final["payment"]["status"] == "PAID"
    assert [h["to_status"] for h in final["history"]] == [
        "PLACED",
        "VERIFYING",
        "ASSIGNED",
        "IN_PRINT",
        "READY_FOR_DISPATCH",
        "DISPATCHED",
        "DELIVERED",
        "COMPLETED",
    ]
    assert final["allowed_actions"] == []

    with api.services.session() as session:
        titles = session.scalars(
            select(Notification.title)
            .where(Notification.order_id == order_id)
            .order_by(Notification.created_at)
        ).all()
    assert titles[0] == "Order placed"
    assert "Out for delivery" in titles
    assert "Delivered" in titles


def test_digital_payment_places_the_order(api: Api) -> None:
    customer = api.customer()
    api.client.post(
        "/api/v1/me/devices",
        headers=customer.headers,
        json={"platform": "android", "push_token": "fcm-token-1234567890"},
    )
    order = api.print_order(customer, method="EASYPAISA")
    assert order["status"] == "PENDING_PAYMENT"
    assert order["awaiting_payment"] is True
    assert order["price"]["cod_fee_paisa"] == 0
    checkout = order["payment"]["checkout_url"]
    assert checkout.startswith("http://testserver/mock/payments/mockpay_")
    page = api.client.get(checkout.removeprefix("http://testserver"))
    assert page.status_code == 200
    assert order["code"] in page.text

    api.pay(order)
    paid = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert paid["status"] == "PLACED"
    assert paid["payment"]["status"] == "PAID"
    assert paid["payment"]["checkout_url"] is None
    assert paid["awaiting_payment"] is False
    assert _ledger(api, order["id"]) == [(LedgerEntryType.REVENUE, order["total_paisa"])]
    pushed = [m.title for tokens, m in api.push.sent if tokens == ["fcm-token-1234567890"]]
    assert "Payment received" in pushed
    assert "Order placed" in pushed


def test_failed_payment_can_be_retried(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="JAZZCASH")
    api.pay(order, "FAILED")
    failed = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert failed["status"] == "PENDING_PAYMENT"
    assert failed["payment"]["status"] == "FAILED"

    retry = api.post(f"/api/v1/orders/{order['id']}/payments", customer)
    assert retry.status_code == 201
    second = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert second["payment"]["checkout_url"] == retry.json()["checkout_url"]
    api.pay(second)
    assert api.get(f"/api/v1/orders/{order['id']}", customer).json()["status"] == "PLACED"
    again = api.post(f"/api/v1/orders/{order['id']}/payments", customer)
    assert again.status_code == 409
    assert again.json()["code"] == "payment-not-needed"


def test_paying_a_replaced_attempt_still_places_the_order(api: Api) -> None:
    customer = api.customer()
    first = api.print_order(customer, method="CARD")
    api.post(f"/api/v1/orders/{first['id']}/payments", customer)
    # The customer finishes the first checkout after starting a second one.
    api.pay(first)
    order = api.get(f"/api/v1/orders/{first['id']}", customer).json()
    assert order["status"] == "PLACED"
    with api.services.session() as session:
        statuses = sorted(
            p.status.value
            for p in session.scalars(select(Payment).where(Payment.order_id == first["id"]))
        )
    assert statuses == ["FAILED", "PAID"]


def test_payment_after_cancellation_is_refunded(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="EASYPAISA")
    cancelled = api.post(f"/api/v1/orders/{order['id']}/cancel", customer, {})
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["payment"]["status"] == "FAILED"
    api.pay(order)
    with api.services.session() as session:
        refund = session.scalars(select(Refund).where(Refund.order_id == order["id"])).one()
        assert refund.status.value == "PROCESSED"
        assert refund.reference is not None
        assert refund.reference.startswith("mockrefund_")
        db_order = session.get(Order, order["id"])
        assert db_order is not None
        assert db_order.status.value == "CANCELLED"
        assert db_order.payment_status is not None
        assert db_order.payment_status.value == "REFUNDED"
    assert _ledger(api, order["id"]) == [
        (LedgerEntryType.REFUND, order["total_paisa"]),
        (LedgerEntryType.REVENUE, order["total_paisa"]),
    ]


def test_cancelling_a_paid_order_refunds_it(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="EASYPAISA")
    api.pay(order)
    cancelled = api.post(f"/api/v1/orders/{order['id']}/cancel", customer, {"reason": "Wrong file"})
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "CANCELLED"
    assert body["exit"]["status"] == "CANCELLED"
    assert body["exit"]["reason"] == "Wrong file"
    assert body["payment"]["status"] == "REFUNDED"
    assert _steps(body)["PLACED"] == "DONE"
    admin = api.admin()
    refunds = api.get("/api/v1/admin/refunds", admin).json()
    assert refunds["total"] == 1
    assert refunds["items"][0]["status"] == "PROCESSED"


def test_refund_waits_for_an_admin_when_the_gateway_cannot_refund(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="EASYPAISA")
    api.pay(order)
    with api.services.session() as session:
        payment = session.scalars(select(Payment).where(Payment.order_id == order["id"])).one()
        payment.provider = "easypaisa"  # the unconfigured real gateway: no refund API
        session.commit()
    admin = api.admin()
    api.admin_action(admin, order["id"], "start-verification")
    api.admin_action(admin, order["id"], "reject", {"reason": "The file is blank"})
    pending = api.get("/api/v1/admin/refunds?status=PENDING", admin).json()
    assert pending["total"] == 1
    refund_id = pending["items"][0]["id"]
    done = api.post(
        f"/api/v1/admin/refunds/{refund_id}/mark-processed", admin, {"reference": "EP-123456"}
    )
    assert done.status_code == 200
    assert done.json()["status"] == "PROCESSED"
    again = api.post(
        f"/api/v1/admin/refunds/{refund_id}/mark-processed", admin, {"reference": "EP-123456"}
    )
    assert again.status_code == 409
    mine = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert mine["status"] == "REJECTED"
    assert mine["exit"]["reason"] == "The file is blank"


def test_unpaid_orders_are_cancelled_after_the_payment_window(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="EASYPAISA")
    api.clock.advance(timedelta(hours=23))
    assert api.post("/api/v1/_dev/jobs/expire_pending_payments").json()["result"] == 0
    api.later(timedelta(hours=1), customer)
    assert api.post("/api/v1/_dev/jobs/expire_pending_payments").json()["result"] == 1
    expired = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert expired["status"] == "CANCELLED"
    assert expired["exit"]["reason"] == "Payment was not completed in time"


def test_price_mismatch_is_refused_with_the_new_price(api: Api) -> None:
    customer = api.customer()
    upload = api.upload(customer, pdf_bytes(10))
    address = api.address(customer)
    response = api.post(
        "/api/v1/orders/print",
        customer,
        {
            "upload_id": upload["id"],
            "paper": "LOCAL_WHITE",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "address_id": str(address),
            "payment_method": "COD",
            "expected_total_paisa": 1,
        },
    )
    assert response.status_code == 409
    problem = response.json()
    assert problem["code"] == "price-mismatch"
    assert problem["extra"]["total_paisa"] > 1
    assert problem["extra"]["breakdown"]["pages"] == 10


def test_cod_limit(api: Api) -> None:
    admin = api.admin()
    settings = api.get("/api/v1/admin/settings", admin).json()
    settings["cod_max_order_value_paisa"] = 100
    assert api.put("/api/v1/admin/settings", admin, settings).status_code == 200
    customer = api.customer()
    upload = api.upload(customer)
    address = api.address(customer)
    total = api.quote_price(3, "LOCAL_WHITE", "SOFTCOVER_PAPERBACK", 1, "Lahore", "COD")
    response = api.post(
        "/api/v1/orders/print",
        customer,
        {
            "upload_id": upload["id"],
            "paper": "LOCAL_WHITE",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "address_id": str(address),
            "payment_method": "COD",
            "expected_total_paisa": total,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "cod-not-allowed"


def test_ordering_needs_terms_and_a_verified_phone(api: Api) -> None:
    customer = api.customer(terms=False)
    response = api.post(
        "/api/v1/orders/source",
        customer,
        {"book_title": "X", "copies": 1, "address_id": str(api.address(customer))},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "terms-required"

    google = api.post("/api/v1/auth/google", json={"id_token": "fake-google-nophone"}).json()
    headers = {"Authorization": f"Bearer {google['access_token']}"}
    api.client.post(
        "/api/v1/me/terms",
        headers=headers,
        json={"terms_version": api.services.settings.terms_version},
    )
    address = api.client.post(
        "/api/v1/me/addresses",
        headers=headers,
        json={
            "recipient_name": "A",
            "recipient_phone": "03001112222",
            "city_id": str(api.city_id()),
            "area": "Model Town",
            "street_address": "House 1",
            "landmark": "Park",
        },
    ).json()
    response = api.client.post(
        "/api/v1/orders/source",
        headers=headers,
        json={"book_title": "X", "copies": 1, "address_id": address["id"]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "phone-required"


def test_upload_must_be_valid_unused_and_owned(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer)
    reuse = api.post(
        "/api/v1/orders/print",
        customer,
        {
            "upload_id": order["upload"]["id"],
            "paper": "LOCAL_WHITE",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "address_id": str(api.address(customer)),
            "payment_method": "COD",
            "expected_total_paisa": order["total_paisa"],
        },
    )
    assert reuse.status_code == 409
    assert reuse.json()["code"] == "upload-already-ordered"

    stranger = api.customer()
    theirs = api.post(
        "/api/v1/orders/print",
        stranger,
        {
            "upload_id": order["upload"]["id"],
            "paper": "LOCAL_WHITE",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "address_id": str(api.address(stranger)),
            "payment_method": "COD",
            "expected_total_paisa": order["total_paisa"],
        },
    )
    assert theirs.status_code == 404

    api.tasks.eager = False
    pending = api.upload(customer)
    early = api.post(
        "/api/v1/orders/print",
        customer,
        {
            "upload_id": pending["id"],
            "paper": "LOCAL_WHITE",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "address_id": str(api.address(customer)),
            "payment_method": "COD",
            "expected_total_paisa": order["total_paisa"],
        },
    )
    assert early.status_code == 409
    assert early.json()["code"] == "upload-not-ready"


def test_customer_cannot_cancel_after_approval(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer)
    admin = api.admin()
    vendor = api.vendor()
    api.admin_action(admin, order["id"], "start-verification")
    api.admin_action(
        admin, order["id"], "approve", {"vendor_id": str(vendor), "vendor_cost_paisa": 100}
    )
    response = api.post(f"/api/v1/orders/{order['id']}/cancel", customer, {})
    assert response.status_code == 409
    assert response.json()["code"] == "cannot-cancel"
    # Admins can, with a reason.
    no_reason = api.post(f"/api/v1/admin/orders/{order['id']}/cancel", admin, {"reason": ""})
    assert no_reason.status_code == 422
    done = api.admin_action(admin, order["id"], "cancel", {"reason": "Customer asked by phone"})
    assert done["status"] == "CANCELLED"
    assert done["cancel_reason"] == "Customer asked by phone"


def test_illegal_admin_actions_return_conflict(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer)
    admin = api.admin()
    response = api.post(f"/api/v1/admin/orders/{order['id']}/start-printing", admin)
    assert response.status_code == 409
    assert response.json()["code"] == "invalid-transition"
    assert response.json()["extra"] == {"from_status": "PLACED", "to_status": "IN_PRINT"}
    dispatch = api.post(
        f"/api/v1/admin/orders/{order['id']}/dispatch", admin, {"courier_code": "mock"}
    )
    assert dispatch.status_code == 409
    quote = api.post(
        f"/api/v1/admin/orders/{order['id']}/quote",
        admin,
        {
            "pages": 10,
            "paper": "LOCAL_WHITE",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "sourcing_cost_paisa": 0,
        },
    )
    assert quote.status_code == 409
    assert quote.json()["code"] == "wrong-order-type"


def test_vendor_sees_only_assigned_orders_and_file_links_are_audited(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer)
    other = api.print_order(api.customer())
    admin = api.admin()
    vendor = api.vendor_user(api.vendor("Mine"))
    rival = api.vendor_user(api.vendor("Rival"))
    api.admin_action(admin, order["id"], "start-verification")
    api.admin_action(
        admin,
        order["id"],
        "approve",
        {"vendor_id": str(vendor.vendor_id), "vendor_cost_paisa": 100},
    )

    queue = api.get("/api/v1/vendor/orders", vendor).json()
    assert [o["id"] for o in queue["items"]] == [order["id"]]
    assert api.get("/api/v1/vendor/orders", rival).json()["total"] == 0
    assert api.get(f"/api/v1/vendor/orders/{other['id']}", vendor).status_code == 404
    assert api.get(f"/api/v1/vendor/orders/{order['id']}", rival).status_code == 404
    detail = api.get(f"/api/v1/vendor/orders/{order['id']}", vendor).json()
    # Vendors see what to print and where it goes, not what the customer paid.
    assert "total_paisa" not in detail
    assert "price" not in detail

    link = api.get(f"/api/v1/vendor/orders/{order['id']}/file-url", vendor)
    assert link.status_code == 200
    expires = link.json()["expires_at"]
    assert expires.startswith("2026-10-09T05:05:00")
    slip = api.get(f"/api/v1/vendor/orders/{order['id']}/packing-slip", vendor)
    assert slip.status_code == 200
    assert slip.headers["content-type"] == "application/pdf"
    assert slip.content.startswith(b"%PDF-")

    logs = api.get("/api/v1/admin/audit-logs?action=file.download", admin).json()
    assert logs["total"] == 1
    assert logs["items"][0]["actor_role"] == "VENDOR"


def test_manual_dispatch_with_a_typed_cn(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer)
    admin = api.admin()
    vendor = api.vendor_user(api.vendor())
    _through_printing(api, admin, order["id"], vendor)
    trax = api.post(f"/api/v1/admin/orders/{order['id']}/dispatch", admin, {"courier_code": "trax"})
    # Trax has no integration until the owner supplies its documentation.
    assert trax.status_code == 502
    assert trax.json()["code"] == "courier-unavailable"
    unknown = api.post(
        f"/api/v1/admin/orders/{order['id']}/dispatch", admin, {"courier_code": "dhl"}
    )
    assert unknown.status_code == 422
    done = api.admin_action(
        admin, order["id"], "dispatch", {"courier_code": "trax", "cn_number": " TRX-998877 "}
    )
    assert done["status"] == "DISPATCHED"
    assert done["tracking"]["cn_number"] == "TRX-998877"
    assert done["tracking"]["courier_name"] == "Trax"
    delivered = api.admin_action(admin, order["id"], "mark-delivered")
    assert delivered["status"] == "DELIVERED"


def test_failed_delivery_from_the_courier(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="EASYPAISA")
    api.pay(order)
    admin = api.admin()
    vendor = api.vendor_user(api.vendor())
    _through_printing(api, admin, order["id"], vendor)
    cn = api.admin_action(admin, order["id"], "dispatch", {"courier_code": "mock"})["tracking"][
        "cn_number"
    ]
    api.post(
        f"/api/v1/_dev/mock-courier/{cn}/events",
        json={"state": "RETURNED", "description": "Customer not at home"},
    )
    failed = api.get(f"/api/v1/admin/orders/{order['id']}", admin).json()
    assert failed["status"] == "DELIVERY_FAILED"
    assert failed["refunds"] == []
    # A manual refund after the failed delivery (D-026).
    too_much = api.post(
        f"/api/v1/admin/orders/{order['id']}/refunds",
        admin,
        {"amount_paisa": order["total_paisa"] + 1, "reason": "Parcel returned"},
    )
    assert too_much.status_code == 409
    refund = api.post(
        f"/api/v1/admin/orders/{order['id']}/refunds",
        admin,
        {"amount_paisa": order["total_paisa"], "reason": "Parcel returned"},
    )
    assert refund.status_code == 201
    assert refund.json()["status"] == "PENDING"


def test_courier_webhooks_are_signed_and_idempotent(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer)
    admin = api.admin()
    vendor = api.vendor_user(api.vendor())
    _through_printing(api, admin, order["id"], vendor)
    cn = api.admin_action(admin, order["id"], "dispatch", {"courier_code": "mock"})["tracking"][
        "cn_number"
    ]
    body, headers = api.mock_courier.build_webhook(cn, "DELIVERED", "Delivered")
    tampered = api.client.post(
        "/api/v1/webhooks/couriers/mock",
        content=body.replace(b"Delivered", b"Hijacked!"),
        headers=headers,
    )
    assert tampered.status_code == 401
    assert tampered.json()["code"] == "invalid-signature"
    unsigned = api.client.post("/api/v1/webhooks/couriers/mock", content=body)
    assert unsigned.status_code == 401

    first = api.client.post("/api/v1/webhooks/couriers/mock", content=body, headers=headers)
    assert first.json() == {"status": "processed", "applied": "1"}
    repeat = api.client.post("/api/v1/webhooks/couriers/mock", content=body, headers=headers)
    assert repeat.json() == {"status": "processed", "applied": "0"}
    with api.services.session() as session:
        delivered = session.scalars(
            select(OrderStatusHistory).where(
                OrderStatusHistory.order_id == order["id"],
                OrderStatusHistory.to_status == "DELIVERED",
            )
        ).all()
    assert len(delivered) == 1
    assert api.client.post("/api/v1/webhooks/couriers/manual", content=b"{}").status_code == 404
    assert api.client.post("/api/v1/webhooks/couriers/trax", content=b"{}").status_code == 404


def test_payment_webhooks_are_signed_and_idempotent(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="EASYPAISA")
    ref = order["payment"]["checkout_url"].rsplit("/", 1)[-1]
    body, headers = api.mock_payments.build_webhook(ref, "PAID", order["total_paisa"])

    forged = api.client.post(
        "/api/v1/webhooks/payments/mock", content=body, headers={**headers, "x-mock-signature": "0"}
    )
    assert forged.status_code == 401
    stale = dict(headers)
    stale["x-mock-timestamp"] = str(int(stale["x-mock-timestamp"]) - 3600)
    assert (
        api.client.post("/api/v1/webhooks/payments/mock", content=body, headers=stale).status_code
        == 401
    )

    first = api.client.post("/api/v1/webhooks/payments/mock", content=body, headers=headers)
    assert first.json() == {"status": "processed"}
    repeat = api.client.post("/api/v1/webhooks/payments/mock", content=body, headers=headers)
    assert repeat.json() == {"status": "duplicate"}
    assert _ledger(api, order["id"]) == [(LedgerEntryType.REVENUE, order["total_paisa"])]

    # A second, different event for the same payment changes nothing.
    other, other_headers = api.mock_payments.build_webhook(ref, "FAILED", order["total_paisa"])
    late = api.client.post("/api/v1/webhooks/payments/mock", content=other, headers=other_headers)
    assert late.json() == {"status": "ignored"}
    assert api.get(f"/api/v1/orders/{order['id']}", customer).json()["status"] == "PLACED"

    unknown, unknown_headers = api.mock_payments.build_webhook("mockpay_nope", "PAID", 100)
    assert api.client.post(
        "/api/v1/webhooks/payments/mock", content=unknown, headers=unknown_headers
    ).json() == {"status": "ignored"}
    assert api.client.post("/api/v1/webhooks/payments/stripe", content=body).status_code == 404
    unconfigured = api.client.post("/api/v1/webhooks/payments/easypaisa", content=body)
    assert unconfigured.status_code == 404


def test_paid_amount_must_match(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, method="EASYPAISA")
    ref = order["payment"]["checkout_url"].rsplit("/", 1)[-1]
    body, headers = api.mock_payments.build_webhook(ref, "PAID", order["total_paisa"] - 100)
    api.client.post("/api/v1/webhooks/payments/mock", content=body, headers=headers)
    mine = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert mine["status"] == "PENDING_PAYMENT"
    assert mine["payment"]["status"] == "FAILED"
    assert _ledger(api, order["id"]) == []


def test_order_lists(api: Api) -> None:
    customer = api.customer()
    first = api.print_order(customer)
    api.clock.advance(timedelta(minutes=1))
    second = api.source_order(customer)
    api.post(f"/api/v1/orders/{first['id']}/cancel", customer, {})
    everything = api.get("/api/v1/orders", customer).json()
    assert [o["id"] for o in everything["items"]] == [second["id"], first["id"]]
    assert everything["items"][1]["title"] == "notes.pdf"
    assert everything["items"][0]["title"] == "Pir-e-Kamil"
    active = api.get("/api/v1/orders?group=active", customer).json()
    assert [o["id"] for o in active["items"]] == [second["id"]]
    past = api.get("/api/v1/orders?group=past", customer).json()
    assert [o["id"] for o in past["items"]] == [first["id"]]
    paged = api.get("/api/v1/orders?page=2&page_size=1", customer).json()
    assert paged["total"] == 2
    assert [o["id"] for o in paged["items"]] == [first["id"]]
    assert api.get("/api/v1/orders", api.customer()).json()["total"] == 0
    assert api.get(f"/api/v1/orders/{first['id']}", api.customer()).status_code == 404


def test_admin_order_search(api: Api) -> None:
    customer = api.customer("03451234567")
    order = api.print_order(customer)
    api.source_order(api.customer())
    admin = api.admin()
    by_code = api.get(f"/api/v1/admin/orders?q={order['code'][2:6]}", admin).json()
    assert [o["id"] for o in by_code["items"]] == [order["id"]]
    by_phone = api.get("/api/v1/admin/orders?q=0345-1234567", admin).json()
    assert [o["id"] for o in by_phone["items"]] == [order["id"]]
    assert by_phone["items"][0]["customer_phone_masked"] != "+923451234567"
    by_type = api.get("/api/v1/admin/orders?type=SOURCE", admin).json()
    assert by_type["total"] == 1
    by_status = api.get("/api/v1/admin/orders?status=PLACED&status=REQUESTED", admin).json()
    assert by_status["total"] == 2
    window = api.get(
        "/api/v1/admin/orders",
        admin,
        params={"created_from": "2026-10-10T00:00:00Z"},
    ).json()
    assert window["total"] == 0
    detail = api.get(f"/api/v1/admin/orders/{order['id']}", admin).json()
    assert set(detail["allowed_actions"]) == {"start-verification", "cancel"}
    assert detail["admin_upload"]["file_available"] is True
    link = api.get(f"/api/v1/admin/orders/{order['id']}/file-url", admin)
    assert link.status_code == 200
    slip = api.get(f"/api/v1/admin/orders/{order['id']}/packing-slip", admin)
    assert slip.content.startswith(b"%PDF-")
    assert api.get(f"/api/v1/admin/orders/{customer.id}", admin).status_code == 404
