"""End-to-end scenarios over HTTP against the full stack with mock providers.

1. PRINT, cash on delivery: OTP sign-in, a 20 MB PDF uploaded in parts, the
   order, admin review and assignment, the vendor's download and printing,
   dispatch with the mock courier, delivery by courier webhook. Then the clock
   moves seven days and the purge deletes the file, leaving the order intact.
2. SOURCE, paid online: a book request, the admin's quote, acceptance, payment
   on the mock hosted checkout (webhook back through the worker), sourcing,
   dispatch and delivery, ending COMPLETED.
"""

import hashlib
import time
from collections.abc import Iterator

import httpx2
import pytest
import stack
from stack import MB, Session, ok, order_status, wait_for


@pytest.fixture(scope="module")
def client() -> Iterator[httpx2.Client]:
    with httpx2.Client(base_url=stack.BASE_URL, timeout=60) as http:
        ok(http.get("/healthz"))
        yield http


@pytest.fixture(scope="module")
def admin(client: httpx2.Client) -> Session:
    return stack.admin(client)


@pytest.fixture(scope="module")
def vendor(client: httpx2.Client) -> Session:
    return stack.vendor(client)


def move_clock(client: httpx2.Client, offset_seconds: int) -> None:
    ok(client.post("/api/v1/_dev/clock", json={"offset_seconds": offset_seconds}))
    # Each API process re-reads the shared offset at most a second later.
    time.sleep(1.2)


@pytest.fixture
def clock(client: httpx2.Client) -> Iterator[None]:
    """Always put the shared development clock back, even if a test fails."""
    yield
    move_clock(client, 0)


def test_print_order_with_cash_on_delivery_then_purge(
    client: httpx2.Client, admin: Session, vendor: Session, clock: None
) -> None:
    customer = stack.customer(client)
    content = stack.pdf_of_size(pages=30, size_bytes=20 * MB)
    uploaded = stack.upload(customer, content)
    assert uploaded["status"] == "VALID", uploaded
    assert uploaded["page_count"] == 30
    assert uploaded["size_bytes"] == len(content)

    options = {"paper": "IMPORTED_YELLOW", "binding": "PREMIUM_HARDCOVER", "copies": 2}
    price = ok(
        client.post(
            "/api/v1/pricing/quote",
            json={
                **options,
                "pages": 30,
                "city_id": customer.extra["city_id"],
                "payment_method": "COD",
            },
        )
    )
    order = customer.post(
        "/api/v1/orders/print",
        {
            **options,
            "upload_id": uploaded["id"],
            "address_id": customer.extra["address_id"],
            "payment_method": "COD",
            "expected_total_paisa": price["total_paisa"],
        },
    )
    assert order["status"] == "PLACED"
    order_id = order["id"]

    admin.post(f"/api/v1/admin/orders/{order_id}/start-verification")
    reviewed = admin.post(
        f"/api/v1/admin/orders/{order_id}/approve",
        {"vendor_id": vendor.extra["vendor_id"], "vendor_cost_paisa": 120000},
    )
    assert reviewed["status"] == "ASSIGNED"

    # The vendor downloads exactly the file the customer uploaded.
    link = vendor.get(f"/api/v1/vendor/orders/{order_id}/file-url")["url"]
    with httpx2.Client(timeout=120) as storage:
        downloaded = storage.get(link)
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == hashlib.sha256(content).hexdigest()
    slip = vendor.call("GET", f"/api/v1/vendor/orders/{order_id}/packing-slip")
    assert slip.content.startswith(b"%PDF-")
    vendor.post(f"/api/v1/vendor/orders/{order_id}/start-printing")
    vendor.post(f"/api/v1/vendor/orders/{order_id}/ready-for-dispatch")

    dispatched = admin.post(f"/api/v1/admin/orders/{order_id}/dispatch", {"courier_code": "mock"})
    cn = dispatched["tracking"]["cn_number"]
    assert cn.startswith("MOCK-")
    for state in ("PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"):
        ok(client.post(f"/api/v1/_dev/mock-courier/{cn}/events", json={"state": state}))
    delivered = order_status(customer, order_id, "DELIVERED")
    assert {step["state"] for step in delivered["timeline"]} == {"DONE"}
    inbox = customer.get("/api/v1/notifications")
    assert any(n["title"] == "Delivered" for n in inbox["items"])

    # Six days later the file is still there.
    move_clock(client, 6 * 86400)
    ok(client.post("/api/v1/_dev/jobs/purge_files"))
    assert admin.call("GET", f"/api/v1/admin/orders/{order_id}/file-url").status_code == 200

    # Seven days after delivery the purge deletes every copy; the order stays.
    move_clock(client, 7 * 86400 + 3600)
    report = ok(client.post("/api/v1/_dev/jobs/purge_files"))["result"]
    assert report["delivered_files"] >= 1
    assert report["errors"] == 0
    with httpx2.Client(timeout=30) as storage:
        assert storage.get(link).status_code in (403, 404)
    assert admin.call("GET", f"/api/v1/admin/orders/{order_id}/file-url").status_code == 404
    kept = admin.get(f"/api/v1/admin/orders/{order_id}")
    assert kept["status"] == "DELIVERED"
    assert kept["total_paisa"] == price["total_paisa"]
    assert kept["admin_upload"]["file_available"] is False
    assert kept["admin_upload"]["page_count"] == 30
    assert customer.get(f"/api/v1/uploads/{uploaded['id']}")["status"] == "PURGED"


def test_book_request_paid_online(client: httpx2.Client, admin: Session, vendor: Session) -> None:
    customer = stack.customer(client)
    order = customer.post(
        "/api/v1/orders/source",
        {
            "book_title": "Jannat Kay Pattay",
            "author": "Nemrah Ahmed",
            "copies": 1,
            "address_id": customer.extra["address_id"],
        },
    )
    order_id = order["id"]
    assert order["status"] == "REQUESTED"

    admin.post(
        f"/api/v1/admin/orders/{order_id}/quote",
        {
            "pages": 420,
            "paper": "IMPORTED_YELLOW",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "sourcing_cost_paisa": 90000,
        },
    )
    quote = customer.get(f"/api/v1/orders/{order_id}")["quote"]
    accepted = customer.post(
        f"/api/v1/orders/{order_id}/quote/accept",
        {"payment_method": "JAZZCASH", "expected_total_paisa": quote["total_if_digital_paisa"]},
    )
    checkout_url = accepted["payment"]["checkout_url"]
    assert "/mock/payments/" in checkout_url

    # The customer pays on the hosted page; the gateway's webhook comes back via the worker.
    ref = checkout_url.rsplit("/", 1)[-1]
    page = client.post(f"/mock/payments/{ref}/complete", data={"outcome": "PAID"})
    assert page.status_code == 200
    wait_for(
        lambda: customer.get(f"/api/v1/orders/{order_id}")["payment"]["status"] == "PAID",
        "the payment webhook",
    )

    admin.post(
        f"/api/v1/admin/orders/{order_id}/start-sourcing",
        {"vendor_id": vendor.extra["vendor_id"], "vendor_cost_paisa": 95000},
    )
    vendor.post(f"/api/v1/vendor/orders/{order_id}/ready-for-dispatch")
    cn = admin.post(f"/api/v1/admin/orders/{order_id}/dispatch", {"courier_code": "mock"})[
        "tracking"
    ]["cn_number"]
    ok(client.post(f"/api/v1/_dev/mock-courier/{cn}/events", json={"state": "DELIVERED"}))
    done = order_status(customer, order_id, "COMPLETED")
    assert done["total_paisa"] == quote["total_if_digital_paisa"]

    revenue = admin.get(
        "/api/v1/admin/finance/daily-revenue",
        params={"from_date": "2020-01-01", "to_date": "2020-12-31"},
    )
    assert revenue["rows"] == []  # nothing on a day long past
