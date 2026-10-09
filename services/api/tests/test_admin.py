"""Admin people and configuration: vendors, staff, customers, cities,
pricing versions, settings and the audit log."""

from datetime import timedelta
from typing import Any

import pytest

from kitaab.domain.pricing import PLACEHOLDER_RULES
from kitaab.security import totp
from support import Api

pytestmark = pytest.mark.integration

VENDOR = {
    "name": "Urdu Bazaar Press",
    "contact_name": "Kamran",
    "contact_phone": "0300 9998887",
    "email": "press@example.com",
}


def test_vendors_and_their_logins(api: Api) -> None:
    admin = api.admin()
    created = api.post("/api/v1/admin/vendors", admin, VENDOR)
    assert created.status_code == 201
    vendor = created.json()
    assert vendor["contact_phone_e164"] == "+923009998887"
    bad = api.post("/api/v1/admin/vendors", admin, {**VENDOR, "contact_phone": "123"})
    assert bad.json()["code"] == "invalid-phone"
    no_city = api.post("/api/v1/admin/vendors", admin, {**VENDOR, "city_id": str(admin.id)})
    assert no_city.json()["code"] == "unknown-city"

    login = api.post(
        f"/api/v1/admin/vendors/{vendor['id']}/users",
        admin,
        {"email": "Kamran@Example.com", "full_name": "Kamran"},
    )
    assert login.status_code == 201
    new = login.json()
    assert new["user"]["role"] == "VENDOR"
    assert new["totp_provisioning_uri"] is None
    signed_in = api.staff_login("kamran@example.com", new["temporary_password"], None)
    assert signed_in.status_code == 200
    users = api.get(f"/api/v1/admin/vendors/{vendor['id']}/users", admin).json()
    assert [u["email"] for u in users] == ["kamran@example.com"]
    duplicate = api.post(
        f"/api/v1/admin/vendors/{vendor['id']}/users",
        admin,
        {"email": "kamran@example.com", "full_name": "Again"},
    )
    assert duplicate.status_code == 409
    missing = api.post(
        f"/api/v1/admin/vendors/{admin.id}/users",
        admin,
        {"email": "x@example.com", "full_name": "X"},
    )
    assert missing.status_code == 404

    paused = api.put(f"/api/v1/admin/vendors/{vendor['id']}", admin, {**VENDOR, "is_active": False})
    assert paused.json()["is_active"] is False
    assert api.get("/api/v1/admin/vendors", admin).json() == []
    everyone = api.get("/api/v1/admin/vendors?include_inactive=true", admin).json()
    assert [v["id"] for v in everyone] == [vendor["id"]]
    assert api.put(f"/api/v1/admin/vendors/{admin.id}", admin, VENDOR).status_code == 404

    # Inactive vendors cannot receive work.
    customer = api.customer()
    order = api.print_order(customer)
    api.admin_action(admin, order["id"], "start-verification")
    refused = api.post(
        f"/api/v1/admin/orders/{order['id']}/approve",
        admin,
        {"vendor_id": vendor["id"], "vendor_cost_paisa": 100},
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "vendor-not-found"


def test_new_admins_get_a_totp_secret(api: Api) -> None:
    admin = api.admin()
    created = api.post(
        "/api/v1/admin/staff", admin, {"email": "second@example.com", "full_name": "Second"}
    ).json()
    uri = created["totp_provisioning_uri"]
    assert uri.startswith("otpauth://totp/")
    secret = uri.split("secret=")[1].split("&")[0]
    login = api.staff_login(
        "second@example.com", created["temporary_password"], totp.code_at(secret, api.clock.now())
    )
    assert login.status_code == 200
    staff = api.get("/api/v1/admin/staff", admin).json()
    assert [s["email"] for s in staff] == ["admin@example.com", "second@example.com"]


def test_deactivate_and_unlock_staff(api: Api) -> None:
    admin = api.admin()
    vendor = api.vendor_user(api.vendor())
    myself = api.patch(f"/api/v1/admin/staff/{admin.id}", admin, {"is_active": False})
    assert myself.status_code == 409
    off = api.patch(f"/api/v1/admin/staff/{vendor.id}", admin, {"is_active": False}).json()
    assert off["is_active"] is False
    assert api.get("/api/v1/vendor/orders", vendor).status_code == 401
    assert (
        api.post("/api/v1/auth/refresh", json={"refresh_token": vendor.refresh}).status_code == 401
    )

    email = api.get(f"/api/v1/admin/vendors/{vendor.vendor_id}/users", admin).json()[0]["email"]
    api.patch(f"/api/v1/admin/staff/{vendor.id}", admin, {"is_active": True})
    for _ in range(api.services.settings.staff_max_failed_logins):
        api.staff_login(email, "wrong", None)
    locked = api.get(f"/api/v1/admin/vendors/{vendor.vendor_id}/users", admin).json()[0]
    assert locked["locked"] is True
    unlocked = api.patch(f"/api/v1/admin/staff/{vendor.id}", admin, {"unlock": True}).json()
    assert unlocked["locked"] is False
    customer = api.customer()
    assert (
        api.patch(f"/api/v1/admin/staff/{customer.id}", admin, {"unlock": True}).status_code == 404
    )


def test_customer_support_view(api: Api) -> None:
    admin = api.admin()
    customer = api.customer("03211112233")
    api.patch("/api/v1/me", customer, {"full_name": "Zainab Ali"})
    api.print_order(customer)
    api.customer()
    everyone = api.get("/api/v1/admin/customers", admin).json()
    assert everyone["total"] == 2
    by_name = api.get("/api/v1/admin/customers?q=zainab", admin).json()
    assert [c["id"] for c in by_name["items"]] == [str(customer.id)]
    assert by_name["items"][0]["order_count"] == 1
    assert by_name["items"][0]["phone_masked"].endswith("33")
    assert "1112" not in by_name["items"][0]["phone_masked"]
    by_phone = api.get("/api/v1/admin/customers?q=0321-1112233", admin).json()
    assert by_phone["total"] == 1
    detail = api.get(f"/api/v1/admin/customers/{customer.id}", admin).json()
    assert detail["phone_e164"] == "+923211112233"
    assert len(detail["orders"]) == 1
    # Looking at someone's details is logged.
    logs = api.get(
        f"/api/v1/admin/audit-logs?action=customer.view&entity_id={customer.id}", admin
    ).json()
    assert logs["total"] == 1
    assert api.get(f"/api/v1/admin/customers/{admin.id}", admin).status_code == 404


def test_cities(api: Api) -> None:
    admin = api.admin()
    created = api.post(
        "/api/v1/admin/cities",
        admin,
        {
            "name": "Chitral",
            "province": "Khyber Pakhtunkhwa",
            "zone_code": " z3 ",
            "sort_order": 99,
        },
    ).json()
    assert created["zone_code"] == "Z3"
    clash = api.post(
        "/api/v1/admin/cities",
        admin,
        {"name": "lahore", "province": "Punjab", "zone_code": "Z1"},
    )
    assert clash.status_code == 409
    paused = api.put(
        f"/api/v1/admin/cities/{created['id']}",
        admin,
        {
            "name": "Chitral",
            "province": "Khyber Pakhtunkhwa",
            "zone_code": "Z3",
            "is_active": False,
        },
    ).json()
    assert paused["is_active"] is False
    assert "Chitral" not in [c["name"] for c in api.get("/api/v1/cities").json()]
    assert len(api.get("/api/v1/admin/cities", admin).json()) == 21
    missing = api.put(
        f"/api/v1/admin/cities/{admin.id}",
        admin,
        {"name": "X", "province": "Y", "zone_code": "Z1"},
    )
    assert missing.status_code == 404


def _rules(**changes: Any) -> dict[str, Any]:
    return {**PLACEHOLDER_RULES.model_dump(mode="json"), **changes}


def test_pricing_versions(api: Api) -> None:
    admin = api.admin()
    customer = api.customer()
    old_order = api.print_order(customer, method="COD")
    tomorrow = (api.clock.now() + timedelta(days=1)).isoformat()
    created = api.post(
        "/api/v1/admin/pricing-configs",
        admin,
        {
            "effective_from": tomorrow,
            "rules": _rules(cod_fee_paisa=PLACEHOLDER_RULES.cod_fee_paisa + 10000),
            "notes": "COD fee up",
        },
    )
    assert created.status_code == 201
    assert created.json()["version"] == 2
    assert created.json()["active"] is False
    versions = api.get("/api/v1/admin/pricing-configs", admin).json()
    assert [(v["version"], v["active"]) for v in versions] == [(2, False), (1, True)]
    assert versions[0]["created_by_name"] == "Admin"
    assert api.get("/api/v1/pricing/config").json()["version"] == 1

    api.later(timedelta(days=1), admin, customer)
    assert api.get("/api/v1/pricing/config").json()["version"] == 2
    # Orders keep the version they were priced with.
    kept = api.get(f"/api/v1/admin/orders/{old_order['id']}", admin).json()
    assert kept["price"]["config_version"] == 1
    assert kept["total_paisa"] == old_order["total_paisa"]
    new_order = api.print_order(customer, method="COD")
    assert new_order["price"]["config_version"] == 2
    assert new_order["price"]["cod_fee_paisa"] == PLACEHOLDER_RULES.cod_fee_paisa + 10000

    invalid = api.post(
        "/api/v1/admin/pricing-configs",
        admin,
        {"effective_from": tomorrow, "rules": _rules(max_copies=0)},
    )
    assert invalid.status_code == 422


def test_settings_round_trip(api: Api) -> None:
    admin = api.admin()
    current = api.get("/api/v1/admin/settings", admin).json()
    assert current["quote_validity_hours"] == 48
    changed = api.put(
        "/api/v1/admin/settings",
        admin,
        {**current, "quote_validity_hours": 72, "support_whatsapp": "+923001234567"},
    ).json()
    assert changed["quote_validity_hours"] == 72
    assert api.get("/api/v1/app/config").json()["support"]["whatsapp"] == "+923001234567"
    too_long = api.put("/api/v1/admin/settings", admin, {**current, "quote_validity_hours": 1000})
    assert too_long.status_code == 422
    logs = api.get("/api/v1/admin/audit-logs?entity_type=settings", admin).json()
    assert logs["items"][0]["details"]["quote_validity_hours"] == 72
    assert logs["items"][0]["actor_name"] == "Admin"
    assert logs["items"][0]["actor_role"] == "ADMIN"


def test_couriers_list(api: Api) -> None:
    admin = api.admin()
    couriers = api.get("/api/v1/admin/couriers", admin).json()
    assert [(c["code"], c["has_api"]) for c in couriers] == [
        ("mock", True),
        ("trax", True),
        ("manual", False),
    ]
