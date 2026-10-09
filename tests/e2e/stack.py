"""HTTP helpers for the end-to-end scenarios. They talk to the running stack
the way the app and portal do, through the portal's proxy, and use the
development endpoints only for what a real phone or courier would do (read the
SMS, move a parcel, move the clock)."""

import io
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pikepdf
import pyotp
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")
ADMIN = ("admin@example.com", "demo-admin-password", "JBSWY3DPEHPK3PXP")
VENDOR = ("vendor@example.com", "demo-vendor-password")
MB = 1024 * 1024


def pdf_of_size(pages: int, size_bytes: int) -> bytes:
    """A valid PDF padded with an unused incompressible stream to `size_bytes`."""
    buffer = io.BytesIO()
    doc = canvas.Canvas(buffer, pagesize=A4)
    for number in range(1, pages + 1):
        doc.drawString(72, 760, f"End-to-end page {number}")
        doc.showPage()
    doc.save()
    with pikepdf.open(io.BytesIO(buffer.getvalue())) as pdf:
        padding = size_bytes - len(buffer.getvalue()) - 2048
        pdf.pages[0].obj.PieceInfo = pikepdf.Dictionary(
            Pad=pdf.make_stream(random.randbytes(max(padding, 0)))
        )
        out = io.BytesIO()
        pdf.save(out, compress_streams=False)
    return out.getvalue()


@dataclass
class Session:
    """A signed-in person. Refreshes the access token when it expires."""

    client: httpx2.Client
    access: str
    refresh: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access}"}

    def call(self, method: str, path: str, **kwargs: Any) -> httpx2.Response:
        response = self.client.request(method, path, headers=self.headers, **kwargs)
        if response.status_code == 401:
            pair = ok(
                self.client.post("/api/v1/auth/refresh", json={"refresh_token": self.refresh})
            )
            self.access, self.refresh = pair["access_token"], pair["refresh_token"]
            response = self.client.request(method, path, headers=self.headers, **kwargs)
        return response

    def get(self, path: str, **kwargs: Any) -> Any:
        return ok(self.call("GET", path, **kwargs))

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return ok(self.call("POST", path, json=json, **kwargs))


def ok(response: httpx2.Response) -> Any:
    assert response.is_success, (
        f"{response.request.method} {response.url}: {response.status_code} {response.text}"
    )
    return response.json() if response.content else None


def wait_for(check: Any, what: str, timeout: float = 60.0) -> Any:
    """Polls `check()` until it returns something truthy (jobs run in the worker)."""
    deadline = time.monotonic() + timeout
    while True:
        result = check()
        if result:
            return result
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        time.sleep(0.5)


def customer(client: httpx2.Client) -> Session:
    phone = f"0300{random.randint(0, 9_999_999):07d}"
    e164 = ok(client.post("/api/v1/auth/otp/request", json={"phone": phone}))["phone_e164"]
    outbox = ok(client.get("/api/v1/_dev/sms-outbox", params={"phone": e164}))
    code = re.search(r"\b\d{6}\b", outbox[0]["text"]).group()  # type: ignore[union-attr]
    pair = ok(client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code}))
    person = Session(client, pair["access_token"], pair["refresh_token"], {"phone": e164})
    terms = ok(client.get("/api/v1/app/config"))["terms_version"]
    person.post("/api/v1/me/terms", {"terms_version": terms})
    city = next(c for c in ok(client.get("/api/v1/cities")) if c["name"] == "Karachi")
    address = person.post(
        "/api/v1/me/addresses",
        {
            "recipient_name": "Hamza Siddiqui",
            "recipient_phone": phone,
            "city_id": city["id"],
            "area": "Clifton Block 5",
            "street_address": "Flat 7, Sea View Apartments",
            "landmark": "Opposite Dolmen Mall",
        },
    )
    person.extra.update(address_id=address["id"], city_id=city["id"])
    return person


def admin(client: httpx2.Client) -> Session:
    email, password, secret = ADMIN
    pair = ok(
        client.post(
            "/api/v1/auth/staff/login",
            json={"email": email, "password": password, "totp_code": pyotp.TOTP(secret).now()},
        )
    )
    return Session(client, pair["access_token"], pair["refresh_token"])


def vendor(client: httpx2.Client) -> Session:
    email, password = VENDOR
    pair = ok(client.post("/api/v1/auth/staff/login", json={"email": email, "password": password}))
    return Session(
        client,
        pair["access_token"],
        pair["refresh_token"],
        {"vendor_id": pair["user"]["vendor_id"]},
    )


def upload(person: Session, content: bytes, filename: str = "thesis.pdf") -> dict[str, Any]:
    """Uploads part by part through the presigned URLs, as the app does."""
    session = person.post(
        "/api/v1/uploads",
        {"filename": filename, "size_bytes": len(content), "copyright_declared": True},
    )
    size = session["part_size_bytes"]
    with httpx2.Client(timeout=120) as storage:
        for part in session["parts"]:
            chunk = content[(part["number"] - 1) * size : part["number"] * size]
            put = storage.put(part["url"], content=chunk)
            assert put.status_code == 200, put.text
    upload_id = session["upload"]["id"]
    person.post(f"/api/v1/uploads/{upload_id}/complete")
    return wait_for(
        lambda: (
            (u := person.get(f"/api/v1/uploads/{upload_id}"))["status"] in ("VALID", "REJECTED")
            and u
        ),
        "the worker to validate the upload",
    )


def order_status(person: Session, order_id: str, status: str, path: str = "/api/v1/orders") -> Any:
    return wait_for(
        lambda: (o := person.get(f"{path}/{order_id}"))["status"] == status and o,
        f"order {order_id} to reach {status}",
    )
