"""The customer's own data: profile, terms, addresses, devices, inbox and
account deletion. Plus the public catalog endpoints."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from kitaab.models import Address, Device, Notification, Order, RefreshToken, Upload, User
from support import Api

pytestmark = pytest.mark.integration

ADDRESS = {
    "recipient_name": "Bilal Ahmed",
    "recipient_phone": "0333-7654321",
    "area": "Saddar",
    "street_address": "Flat 3, Block B",
    "landmark": "Opposite Empress Market",
}


def test_profile_and_terms(api: Api) -> None:
    customer = api.customer(terms=False)
    updated = api.patch("/api/v1/me", customer, {"full_name": "Sana Iqbal"})
    assert updated.json()["full_name"] == "Sana Iqbal"
    outdated = api.post("/api/v1/me/terms", customer, {"terms_version": "2020-01"})
    assert outdated.status_code == 409
    assert outdated.json()["extra"]["current"] == api.services.settings.terms_version
    accepted = api.post(
        "/api/v1/me/terms", customer, {"terms_version": api.services.settings.terms_version}
    )
    assert accepted.json()["terms_accepted"] is True
    # A new terms version asks again.
    api.services.settings = api.services.settings.model_copy(update={"terms_version": "v2"})
    assert api.get("/api/v1/me", customer).json()["terms_accepted"] is False


def test_addresses(api: Api) -> None:
    customer = api.customer()
    karachi = str(api.city_id("Karachi"))
    first = api.post("/api/v1/me/addresses", customer, {**ADDRESS, "city_id": karachi})
    assert first.status_code == 201
    body = first.json()
    assert body["is_default"] is True  # the first address is the default
    assert body["recipient_phone_e164"] == "+923337654321"
    assert body["city"]["name"] == "Karachi"

    second = api.post(
        "/api/v1/me/addresses", customer, {**ADDRESS, "city_id": karachi, "is_default": True}
    ).json()
    listed = api.get("/api/v1/me/addresses", customer).json()
    assert [a["id"] for a in listed] == [second["id"], body["id"]]
    assert [a["is_default"] for a in listed] == [True, False]

    changed = api.put(
        f"/api/v1/me/addresses/{body['id']}",
        customer,
        {**ADDRESS, "city_id": karachi, "landmark": "Near Frere Hall"},
    )
    assert changed.json()["landmark"] == "Near Frere Hall"

    assert api.delete(f"/api/v1/me/addresses/{second['id']}", customer).status_code == 204
    remaining = api.get("/api/v1/me/addresses", customer).json()
    assert [(a["id"], a["is_default"]) for a in remaining] == [(body["id"], True)]

    stranger = api.customer()
    assert api.delete(f"/api/v1/me/addresses/{body['id']}", stranger).status_code == 404
    assert (
        api.put(
            f"/api/v1/me/addresses/{body['id']}", stranger, {**ADDRESS, "city_id": karachi}
        ).status_code
        == 404
    )


def test_address_validation(api: Api) -> None:
    customer = api.customer()
    bad_phone = api.post(
        "/api/v1/me/addresses",
        customer,
        {**ADDRESS, "recipient_phone": "021 1234567", "city_id": str(api.city_id())},
    )
    assert bad_phone.json()["code"] == "invalid-phone"
    unknown_city = api.post(
        "/api/v1/me/addresses", customer, {**ADDRESS, "city_id": str(customer.id)}
    )
    assert unknown_city.json()["code"] == "city-not-served"
    missing = api.post("/api/v1/me/addresses", customer, {"recipient_name": "A"})
    assert missing.status_code == 422
    fields = {e["field"] for e in missing.json()["errors"]}
    assert {"city_id", "landmark", "street_address"} <= fields


def test_address_limit(api: Api) -> None:
    customer = api.customer()
    city = str(api.city_id())
    for _ in range(20):
        api.post("/api/v1/me/addresses", customer, {**ADDRESS, "city_id": city})
    response = api.post("/api/v1/me/addresses", customer, {**ADDRESS, "city_id": city})
    assert response.status_code == 409
    assert response.json()["code"] == "too-many-addresses"


def test_devices_move_with_the_phone(api: Api) -> None:
    first = api.customer()
    second = api.customer()
    token = {"platform": "android", "push_token": "token-abcdefghijkl"}
    assert api.post("/api/v1/me/devices", first, token).status_code == 204
    assert api.post("/api/v1/me/devices", second, token).status_code == 204
    with api.services.session() as session:
        devices = session.scalars(select(Device)).all()
    assert [(d.user_id, d.platform) for d in devices] == [(second.id, "android")]
    api.post("/api/v1/me/devices/unregister", second, {"push_token": token["push_token"]})
    with api.services.session() as session:
        assert session.scalars(select(Device)).all() == []


def test_dead_push_tokens_are_dropped(api: Api) -> None:
    customer = api.customer()
    api.post(
        "/api/v1/me/devices", customer, {"platform": "android", "push_token": "dead-token-1234"}
    )
    api.push.invalid_tokens.add("dead-token-1234")
    api.print_order(customer)
    with api.services.session() as session:
        assert session.scalars(select(Device)).all() == []


def test_sms_fallback_for_key_updates(api: Api) -> None:
    api.services.settings = api.services.settings.model_copy(update={"sms_fallback_enabled": True})
    customer = api.customer()
    order = api.source_order(customer)
    admin = api.admin()
    api.admin_action(
        admin,
        order["id"],
        "quote",
        {
            "pages": 100,
            "paper": "LOCAL_WHITE",
            "binding": "SOFTCOVER_PAPERBACK",
            "copies": 1,
            "sourcing_cost_paisa": 0,
        },
    )
    texts = [t for to, t in api.sms.sent if to == customer.phone]
    assert texts[-1].startswith("Your price is ready:")


def test_inbox(api: Api) -> None:
    customer = api.customer()
    api.print_order(customer)  # "File ready", then "Order placed"
    inbox = api.get("/api/v1/notifications", customer).json()
    assert inbox["unread_count"] == 2
    assert {n["title"] for n in inbox["items"]} == {"Order placed", "File ready"}
    first = inbox["items"][0]["id"]
    assert api.post(f"/api/v1/notifications/{first}/read", customer).status_code == 204
    assert api.get("/api/v1/notifications", customer).json()["unread_count"] == 1
    # Someone else's notification ids do nothing.
    other = api.customer()
    api.post(f"/api/v1/notifications/{inbox['items'][1]['id']}/read", other)
    assert api.get("/api/v1/notifications", customer).json()["unread_count"] == 1
    api.post("/api/v1/notifications/read-all", customer)
    page = api.get("/api/v1/notifications?page_size=1", customer).json()
    assert page["unread_count"] == 0
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert page["items"][0]["read"] is True


def test_account_deletion(api: Api) -> None:
    customer = api.customer()
    api.patch("/api/v1/me", customer, {"full_name": "Hina Pervez"})
    api.post("/api/v1/me/devices", customer, {"platform": "android", "push_token": "tok-123456789"})
    open_order = api.print_order(customer, method="EASYPAISA")
    api.pay(open_order)
    spare = api.upload(customer)
    wrong = api.post("/api/v1/me/delete", customer, {"confirm": "yes"})
    assert wrong.status_code == 422

    result = api.post("/api/v1/me/delete", customer, {"confirm": "DELETE"})
    assert result.status_code == 200
    assert result.json() == {
        "cancelled_order_codes": [open_order["code"]],
        "retained_order_codes": [],
    }

    with api.services.session() as session:
        user = session.get(User, customer.id)
        assert user is not None
        assert (user.full_name, user.phone_e164, user.is_active) == (None, None, False)
        assert user.deleted_at is not None
        assert session.scalars(select(Address).where(Address.user_id == customer.id)).all() == []
        assert session.scalars(select(Device)).all() == []
        assert session.scalars(select(Notification)).all() == []
        tokens = session.scalars(select(RefreshToken)).all()
        assert all(t.revoked_at is not None for t in tokens)
        uploads = session.scalars(select(Upload)).all()
        assert {u.status.value for u in uploads} == {"PURGED"}
        assert all(u.object_key is None and u.filename is None for u in uploads)
        order = session.get(Order, open_order["id"])
        assert order is not None
        assert order.status.value == "CANCELLED"
        assert order.ship_street_address is None
        # The money stays on the books: paid, then refunded.
        assert order.total_paisa == open_order["total_paisa"]
        assert order.payment_status is not None
        assert order.payment_status.value == "REFUNDED"
    assert spare["id"] in {str(u.id) for u in uploads}

    # Signed out everywhere, and the number can sign up again as a new account.
    assert api.get("/api/v1/me", customer).status_code == 401
    assert (
        api.post("/api/v1/auth/refresh", json={"refresh_token": customer.refresh}).status_code
        == 401
    )
    api.clock.advance(timedelta(minutes=2))
    again = api.customer(customer.phone, terms=False)
    assert again.id != customer.id


# -- catalog --------------------------------------------------------------------------


def test_cities_are_public_and_sorted(api: Api) -> None:
    cities = api.get("/api/v1/cities").json()
    assert len(cities) == 20
    assert cities[0]["name"] == "Karachi"
    assert {c["zone_code"] for c in cities} == {"Z1", "Z2", "Z3"}


def test_app_config(api: Api) -> None:
    config = api.get("/api/v1/app/config").json()
    assert config["support"]["email"] == "support@example.com"
    methods = {m["method"]: m["enabled"] for m in config["payment_methods"]}
    assert methods == {"COD": True, "EASYPAISA": True, "JAZZCASH": True, "CARD": True}
    assert config["max_upload_bytes"] == 150 * 1024 * 1024


def test_legal_documents(api: Api) -> None:
    for doc in ("terms", "privacy", "copyright"):
        body = api.get(f"/api/v1/legal/{doc}").json()
        assert body["doc"] == doc
        assert body["body"]
    assert api.get("/api/v1/legal/cookies").status_code == 422


def test_public_pricing(api: Api) -> None:
    config = api.get("/api/v1/pricing/config").json()
    assert config["version"] == 1
    lahore = str(api.city_id("Lahore"))
    gwadar = str(api.city_id("Gwadar"))
    body = {"pages": 100, "paper": "LOCAL_WHITE", "binding": "SOFTCOVER_PAPERBACK"}
    near = api.post("/api/v1/pricing/quote", json={**body, "city_id": lahore}).json()
    far = api.post("/api/v1/pricing/quote", json={**body, "city_id": gwadar}).json()
    assert far["delivery_paisa"] > near["delivery_paisa"]
    assert near["total_paisa"] % 100 == 0  # whole rupees
    cod = api.post(
        "/api/v1/pricing/quote", json={**body, "city_id": lahore, "payment_method": "COD"}
    ).json()
    assert cod["total_paisa"] == near["total_paisa"] + cod["cod_fee_paisa"]
    too_many = api.post("/api/v1/pricing/quote", json={**body, "city_id": lahore, "pages": 10**6})
    assert too_many.status_code == 422
    assert too_many.json()["code"] == "pricing-error"
    nowhere = api.post("/api/v1/pricing/quote", json={**body, "city_id": str(uuid.uuid4())})
    assert nowhere.status_code == 422
