"""Load profile for the API (make load, docs/PERF.md).

Three kinds of user, weighted like expected traffic: people browsing prices
without signing in, signed-in customers checking their orders, and a few
admins working the order queue.

Sign-in is rate-limited per address (OTP and staff logins), so a small pool of
customers and one admin are signed in once at the start and shared, the way
many phones behind one carrier NAT would look to the API.
"""

import random
import re
from typing import Any

import httpx2
import pyotp
from locust import HttpUser, between, events, task
from locust.env import Environment

ADMIN = ("admin@example.com", "demo-admin-password", "JBSWY3DPEHPK3PXP")
POOL_SIZE = 8
pool: dict[str, Any] = {"customers": [], "admin": None, "cities": []}


def _customer(client: httpx2.Client) -> dict[str, Any]:
    phone = f"0333{random.randint(0, 9_999_999):07d}"
    e164 = client.post("/api/v1/auth/otp/request", json={"phone": phone}).json()["phone_e164"]
    text = client.get("/api/v1/_dev/sms-outbox", params={"phone": e164}).json()[0]["text"]
    code = re.search(r"\b\d{6}\b", text).group()  # type: ignore[union-attr]
    pair = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code}).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    terms = client.get("/api/v1/app/config").json()["terms_version"]
    client.post("/api/v1/me/terms", headers=headers, json={"terms_version": terms})
    city = pool["cities"][0]
    address = client.post(
        "/api/v1/me/addresses",
        headers=headers,
        json={
            "recipient_name": "Load Test",
            "recipient_phone": phone,
            "city_id": city["id"],
            "area": "Saddar",
            "street_address": "Shop 3, Main Bazaar",
            "landmark": "Near the clock tower",
        },
    ).json()
    order = client.post(
        "/api/v1/orders/source",
        headers=headers,
        json={"book_title": "Load test request", "copies": 1, "address_id": address["id"]},
    ).json()
    return {"headers": headers, "address_id": address["id"], "order_id": order["id"]}


@events.test_start.add_listener
def sign_in(environment: Environment, **_: Any) -> None:
    with httpx2.Client(base_url=environment.host or "", timeout=30) as client:
        pool["cities"] = client.get("/api/v1/cities").json()
        pool["customers"] = [_customer(client) for _ in range(POOL_SIZE)]
        email, password, secret = ADMIN
        pair = client.post(
            "/api/v1/auth/staff/login",
            json={"email": email, "password": password, "totp_code": pyotp.TOTP(secret).now()},
        ).json()
        pool["admin"] = {"Authorization": f"Bearer {pair['access_token']}"}


class Browser(HttpUser):
    """Opens the app and uses the price calculator without signing in."""

    weight = 6
    wait_time = between(1, 4)

    @task(3)
    def calculator(self) -> None:
        city = random.choice(pool["cities"])
        self.client.post(
            "/api/v1/pricing/quote",
            json={
                "pages": random.randint(20, 800),
                "paper": random.choice(["LOCAL_WHITE", "IMPORTED_YELLOW"]),
                "binding": "SOFTCOVER_PAPERBACK",
                "copies": random.randint(1, 5),
                "city_id": city["id"],
                "payment_method": random.choice(["COD", "EASYPAISA"]),
            },
            name="/api/v1/pricing/quote",
        )

    @task(2)
    def start_up(self) -> None:
        self.client.get("/api/v1/app/config")
        self.client.get("/api/v1/pricing/config")
        self.client.get("/api/v1/cities")


class Customer(HttpUser):
    """Checks orders and the inbox; sometimes asks for a book."""

    weight = 3
    wait_time = between(2, 6)

    def on_start(self) -> None:
        self.me = random.choice(pool["customers"])

    @task(4)
    def orders(self) -> None:
        self.client.get("/api/v1/orders?group=active", headers=self.me["headers"])
        self.client.get(
            f"/api/v1/orders/{self.me['order_id']}",
            headers=self.me["headers"],
            name="/api/v1/orders/{id}",
        )

    @task(2)
    def inbox(self) -> None:
        self.client.get("/api/v1/notifications", headers=self.me["headers"])
        self.client.get("/api/v1/me", headers=self.me["headers"])

    @task(1)
    def request_book(self) -> None:
        self.client.post(
            "/api/v1/orders/source",
            headers=self.me["headers"],
            json={
                "book_title": f"Requested title {random.randint(1, 10_000)}",
                "copies": 1,
                "address_id": self.me["address_id"],
            },
        )


class Admin(HttpUser):
    """Works the order queue in the portal."""

    weight = 1
    wait_time = between(2, 5)

    @task(3)
    def queue(self) -> None:
        response = self.client.get(
            "/api/v1/admin/orders?status=REQUESTED&page_size=25",
            headers=pool["admin"],
            name="/api/v1/admin/orders",
        )
        items = response.json().get("items", []) if response.ok else []
        if items:
            self.client.get(
                f"/api/v1/admin/orders/{random.choice(items)['id']}",
                headers=pool["admin"],
                name="/api/v1/admin/orders/{id}",
            )

    @task(1)
    def search(self) -> None:
        self.client.get(
            "/api/v1/admin/orders?q=Load",
            headers=pool["admin"],
            name="/api/v1/admin/orders?q",
        )
