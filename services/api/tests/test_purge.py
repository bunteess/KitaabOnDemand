"""Storage purge with a frozen clock (brief section 3.11): nothing is deleted
before seven days; afterwards the file is gone and the order is intact."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from kitaab.domain.enums import LedgerEntryType
from kitaab.models import LedgerEntry, Order, Upload
from support import Api, Person, pdf_bytes

pytestmark = pytest.mark.integration

WEEK = timedelta(days=7)


def _object_key(api: Api, upload_id: str) -> str | None:
    with api.services.session() as session:
        upload = session.get(Upload, upload_id)
        assert upload is not None
        return upload.object_key


def _purge(api: Api, **params: Any) -> dict[str, Any]:
    response = api.post("/api/v1/_dev/jobs/purge_files", params=params)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()["result"]
    return result


def _deliver(api: Api, admin: Person, order_id: str) -> None:
    vendor = api.vendor()
    api.admin_action(admin, order_id, "start-verification")
    api.admin_action(
        admin, order_id, "approve", {"vendor_id": str(vendor), "vendor_cost_paisa": 20000}
    )
    api.admin_action(admin, order_id, "start-printing")
    api.admin_action(admin, order_id, "ready-for-dispatch")
    api.admin_action(admin, order_id, "dispatch", {"courier_code": "mock"})
    api.admin_action(admin, order_id, "mark-delivered")


def test_delivered_file_is_kept_for_seven_days_then_deleted(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer, pages=24)
    admin = api.admin()
    _deliver(api, admin, order["id"])
    key = _object_key(api, order["upload"]["id"])
    assert key is not None

    api.clock.advance(WEEK - timedelta(seconds=1))
    report = _purge(api)
    assert report["delivered_files"] == 0
    assert api.services.store.object_size(key) is not None

    api.clock.advance(timedelta(seconds=1))
    report = _purge(api)
    assert report["delivered_files"] == 1
    assert report["object_versions_deleted"] >= 1
    assert report["errors"] == 0
    assert api.services.store.object_size(key) is None
    assert _object_key(api, order["upload"]["id"]) is None

    # The order and its money are untouched.
    api.renew(customer, admin)
    kept = api.get(f"/api/v1/admin/orders/{order['id']}", admin).json()
    assert kept["status"] == "DELIVERED"
    assert kept["pages"] == 24
    assert kept["total_paisa"] == order["total_paisa"]
    assert kept["admin_upload"]["file_available"] is False
    assert kept["admin_upload"]["purged_at"] is not None
    assert kept["admin_upload"]["page_count"] == 24
    with api.services.session() as session:
        upload = session.get(Upload, order["upload"]["id"])
        assert upload is not None
        assert upload.sha256 is not None
        assert upload.status.value == "PURGED"
        ledger = session.scalars(
            select(LedgerEntry.entry_type).where(LedgerEntry.order_id == order["id"])
        ).all()
    assert LedgerEntryType.REVENUE in ledger
    gone = api.get(f"/api/v1/admin/orders/{order['id']}/file-url", admin)
    assert gone.status_code == 404
    mine = api.get(f"/api/v1/orders/{order['id']}", customer).json()
    assert mine["upload"]["status"] == "PURGED"
    assert mine["upload"]["page_count"] == 24

    # Running again finds nothing new.
    assert _purge(api)["delivered_files"] == 0


def test_cancelled_and_rejected_files_go_seven_days_after_the_exit(api: Api) -> None:
    customer = api.customer()
    cancelled = api.print_order(customer)
    rejected = api.print_order(customer)
    admin = api.admin()
    api.post(f"/api/v1/orders/{cancelled['id']}/cancel", customer, {})
    api.admin_action(admin, rejected["id"], "start-verification")
    api.clock.advance(timedelta(days=2))
    api.renew(admin)
    api.admin_action(admin, rejected["id"], "reject", {"reason": "Pages are unreadable"})

    api.clock.advance(timedelta(days=5))
    report = _purge(api)
    assert report["exited_files"] == 1  # only the cancelled one is a week old
    assert _object_key(api, cancelled["upload"]["id"]) is None
    assert _object_key(api, rejected["upload"]["id"]) is not None

    api.clock.advance(timedelta(days=2))
    assert _purge(api)["exited_files"] == 1
    assert _object_key(api, rejected["upload"]["id"]) is None


def test_files_of_orders_in_progress_are_never_purged(api: Api) -> None:
    customer = api.customer()
    order = api.print_order(customer)
    admin = api.admin()
    vendor = api.vendor()
    api.admin_action(admin, order["id"], "start-verification")
    api.admin_action(
        admin, order["id"], "approve", {"vendor_id": str(vendor), "vendor_cost_paisa": 100}
    )
    api.clock.advance(timedelta(days=60))
    report = _purge(api)
    assert report == {**report, "delivered_files": 0, "exited_files": 0, "unattached_uploads": 0}
    assert _object_key(api, order["upload"]["id"]) is not None


def test_unattached_uploads_go_after_a_day(api: Api) -> None:
    customer = api.customer()
    finished = api.upload(customer, pdf_bytes(2))
    started = api.post(
        "/api/v1/uploads",
        customer,
        {"filename": "half.pdf", "size_bytes": 5000, "copyright_declared": True},
    ).json()
    key = _object_key(api, finished["id"])
    assert key is not None

    api.clock.advance(timedelta(hours=23, minutes=59))
    assert _purge(api)["unattached_uploads"] == 0
    api.clock.advance(timedelta(minutes=1))
    report = _purge(api)
    assert report["unattached_uploads"] == 2
    assert report["multipart_aborted"] == 1
    assert api.services.store.object_size(key) is None
    with api.services.session() as session:
        half = session.get(Upload, started["upload"]["id"])
        assert half is not None
        assert half.status.value == "PURGED"
        assert half.s3_upload_id is None


def test_dry_run_reports_without_deleting(api: Api) -> None:
    customer = api.customer()
    upload = api.upload(customer)
    api.clock.advance(timedelta(days=2))
    from kitaab import jobs

    report = jobs.purge_files(api.services, dry_run=True)
    assert report["dry_run"] is True
    assert report["unattached_uploads"] == 1
    assert _object_key(api, upload["id"]) is not None


def test_one_storage_failure_does_not_stop_the_rest(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    customer = api.customer()
    first = api.upload(customer)
    second = api.upload(customer)
    broken = _object_key(api, first["id"])
    store = api.services.store
    original = store.delete_all_versions

    def flaky(key: str) -> int:
        if key == broken:
            raise RuntimeError("storage unavailable")
        return original(key)

    monkeypatch.setattr(store, "delete_all_versions", flaky)
    api.clock.advance(timedelta(days=2))
    report = _purge(api)
    assert report["errors"] == 1
    assert report["unattached_uploads"] == 1
    assert _object_key(api, first["id"]) == broken
    assert _object_key(api, second["id"]) is None


def test_purge_is_recorded_in_the_audit_log(api: Api) -> None:
    admin = api.admin()
    _purge(api)
    logs = api.get("/api/v1/admin/audit-logs?action=purge.run", admin).json()
    assert logs["total"] == 1
    assert logs["items"][0]["actor_name"] is None
    assert "delivered_files" in logs["items"][0]["details"]


def test_deleted_accounts_lose_shipping_details_once_orders_finish(api: Api) -> None:
    customer = api.customer()
    in_print = api.print_order(customer)
    admin = api.admin()
    vendor = api.vendor()
    api.admin_action(admin, in_print["id"], "start-verification")
    api.admin_action(
        admin, in_print["id"], "approve", {"vendor_id": str(vendor), "vendor_cost_paisa": 100}
    )
    deleted = api.post("/api/v1/me/delete", customer, {"confirm": "DELETE"})
    assert deleted.status_code == 200
    assert deleted.json()["retained_order_codes"] == [in_print["code"]]

    # The printer still needs the file and the address.
    with api.services.session() as session:
        order = session.get(Order, in_print["id"])
        assert order is not None
        assert order.ship_street_address is not None
    assert _purge(api)["shipping_scrubbed"] == 0
    assert _object_key(api, in_print["upload"]["id"]) is not None

    api.admin_action(admin, in_print["id"], "start-printing")
    api.admin_action(admin, in_print["id"], "ready-for-dispatch")
    api.admin_action(admin, in_print["id"], "dispatch", {"courier_code": "mock"})
    api.admin_action(admin, in_print["id"], "mark-delivered")
    report = _purge(api)
    assert report["shipping_scrubbed"] == 1
    with api.services.session() as session:
        order = session.get(Order, in_print["id"])
        assert order is not None
        assert order.ship_recipient_name is None
        assert order.ship_street_address is None
        assert order.ship_city_name == "Lahore"
        assert order.pii_scrubbed_at is not None
    # A deleted customer's file goes as soon as the order is done.
    assert _object_key(api, in_print["upload"]["id"]) is None
