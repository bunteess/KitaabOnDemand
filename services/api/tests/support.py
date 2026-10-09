"""Shared test helpers: test services, an API client with sign-in helpers,
order factories and PDF fixtures generated in code."""

import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pikepdf
import redis
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select

from kitaab.clock import FrozenClock
from kitaab.config import Settings
from kitaab.container import InlineTaskQueue, Services
from kitaab.db import get_session_factory
from kitaab.domain import auth
from kitaab.domain.context import Ctx
from kitaab.domain.enums import Role
from kitaab.main import create_app
from kitaab.models import City, User, Vendor
from kitaab.providers.courier import MockCourierProvider, build_couriers
from kitaab.providers.id_tokens import FakeIdTokenVerifier
from kitaab.providers.payment import MockPaymentProvider, build_payments
from kitaab.providers.push import FakePushProvider
from kitaab.providers.sms import MockSmsProvider
from kitaab.providers.storage import S3ObjectStore
from kitaab.security import totp
from kitaab.security.ratelimit import RateLimiter

# 10:00 in Pakistan.
START = datetime(2026, 10, 9, 5, 0, tzinfo=UTC)
ADMIN_TOTP = "JBSWY3DPEHPK3PXP"
ADMIN_PASSWORD = "correct horse battery staple"
VENDOR_PASSWORD = "vendor password 123"


def build_test_services(
    settings: Settings, clock: FrozenClock, client: "redis.Redis", store: S3ObjectStore
) -> Services:
    secret = settings.mock_webhook_secret.get_secret_value()
    tasks = InlineTaskQueue()
    services = Services(
        settings=settings,
        clock=clock,
        session_factory=get_session_factory(),
        redis=client,
        store=store,
        sms=MockSmsProvider(None),
        payments=build_payments(
            settings.payment_providers,
            public_base_url=settings.public_base_url,
            secret=secret,
            failure_rate=0.0,
            latency_ms=0,
        ),
        couriers=build_couriers(
            settings.courier_providers,
            public_base_url=settings.public_base_url,
            secret=secret,
            client=None,
            failure_rate=0.0,
            latency_ms=0,
        ),
        push=FakePushProvider(None),
        scanner=None,
        id_tokens=FakeIdTokenVerifier(),
        rate_limiter=RateLimiter(client),
        tasks=tasks,
    )
    tasks.services = services
    return services


# -- PDFs ---------------------------------------------------------------------------


def pdf_bytes(pages: int = 3) -> bytes:
    buffer = io.BytesIO()
    doc = canvas.Canvas(buffer, pagesize=A4)
    for number in range(1, pages + 1):
        doc.drawString(72, 760, f"Test page {number}")
        doc.showPage()
    doc.save()
    return buffer.getvalue()


def _save(pdf: pikepdf.Pdf, **kwargs: Any) -> bytes:
    buffer = io.BytesIO()
    pdf.save(buffer, **kwargs)
    return buffer.getvalue()


def encrypted_pdf_bytes() -> bytes:
    with pikepdf.open(io.BytesIO(pdf_bytes(2))) as pdf:
        return _save(pdf, encryption=pikepdf.Encryption(user="secret", owner="owner"))


def owner_locked_pdf_bytes() -> bytes:
    """Encrypted with an owner password only: opens without a password."""
    with pikepdf.open(io.BytesIO(pdf_bytes(2))) as pdf:
        return _save(pdf, encryption=pikepdf.Encryption(user="", owner="owner"))


def javascript_pdf_bytes() -> bytes:
    with pikepdf.open(io.BytesIO(pdf_bytes(2))) as pdf:
        action = pdf.make_indirect(
            pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert('hi')"))
        )
        pdf.Root.OpenAction = action
        return _save(pdf)


def launch_action_pdf_bytes() -> bytes:
    with pikepdf.open(io.BytesIO(pdf_bytes(1))) as pdf:
        pdf.Root.OpenAction = pikepdf.Dictionary(
            S=pikepdf.Name.Launch, F=pikepdf.String("calc.exe")
        )
        return _save(pdf)


def attachment_pdf_bytes() -> bytes:
    with pikepdf.open(io.BytesIO(pdf_bytes(1))) as pdf:
        pdf.attachments["note.txt"] = pikepdf.AttachedFileSpec(pdf, b"hello")
        return _save(pdf)


def goto_open_action_pdf_bytes() -> bytes:
    """An OpenAction that only jumps to the first page is harmless."""
    with pikepdf.open(io.BytesIO(pdf_bytes(2))) as pdf:
        pdf.Root.OpenAction = pikepdf.Array([pdf.pages[0].obj, pikepdf.Name.Fit])
        return _save(pdf)


def zero_page_pdf_bytes() -> bytes:
    pdf = pikepdf.new()
    return _save(pdf)


def corrupt_pdf_bytes() -> bytes:
    return b"%PDF-1.7\n" + b"\x00garbage that is not a pdf body\n" * 50 + b"%%EOF\n"


def exe_bytes() -> bytes:
    return b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200


# -- the API harness ----------------------------------------------------------------


@dataclass
class Person:
    """A signed-in user and the headers for their requests."""

    id: uuid.UUID
    token: str
    refresh: str
    phone: str | None = None
    vendor_id: uuid.UUID | None = None

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


class Api:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.app = create_app(services)
        self.client = TestClient(self.app)
        self.webhook_client = TestClient(self.app)
        services.extras["http_post"] = self._deliver
        self._phones = 0

    # -- plumbing

    def _deliver(self, path: str, body: bytes, headers: dict[str, str]) -> None:
        response = self.webhook_client.post(
            path, content=body, headers={**headers, "Content-Type": "application/json"}
        )
        assert response.status_code < 400, response.text

    def close(self) -> None:
        self.client.close()
        self.webhook_client.close()

    @property
    def clock(self) -> FrozenClock:
        clock = self.services.clock
        assert isinstance(clock, FrozenClock)
        return clock

    @property
    def sms(self) -> MockSmsProvider:
        sms = self.services.sms
        assert isinstance(sms, MockSmsProvider)
        return sms

    @property
    def push(self) -> FakePushProvider:
        push = self.services.push
        assert isinstance(push, FakePushProvider)
        return push

    @property
    def tasks(self) -> InlineTaskQueue:
        tasks = self.services.tasks
        assert isinstance(tasks, InlineTaskQueue)
        return tasks

    @property
    def mock_payments(self) -> MockPaymentProvider:
        provider = self.services.payments.get("mock")
        assert isinstance(provider, MockPaymentProvider)
        return provider

    @property
    def mock_courier(self) -> MockCourierProvider:
        courier = self.services.couriers.get("mock")
        assert isinstance(courier, MockCourierProvider)
        return courier

    def ctx(self) -> Ctx:
        return Ctx(self.services.session(), self.services)

    def get(self, path: str, who: Person | None = None, **kwargs: Any) -> httpx2.Response:
        return self.client.get(path, headers=who.headers if who else None, **kwargs)

    def post(
        self, path: str, who: Person | None = None, json: Any = None, **kwargs: Any
    ) -> httpx2.Response:
        return self.client.post(path, headers=who.headers if who else None, json=json, **kwargs)

    def put(self, path: str, who: Person | None = None, json: Any = None) -> httpx2.Response:
        return self.client.put(path, headers=who.headers if who else None, json=json)

    def patch(self, path: str, who: Person | None = None, json: Any = None) -> httpx2.Response:
        return self.client.patch(path, headers=who.headers if who else None, json=json)

    def delete(self, path: str, who: Person | None = None) -> httpx2.Response:
        return self.client.delete(path, headers=who.headers if who else None)

    # -- data

    def seed(self) -> None:
        from kitaab.cli import seed_base

        ctx = self.ctx()
        with ctx.session:
            seed_base(ctx)
            ctx.session.commit()

    def city_id(self, name: str = "Lahore") -> uuid.UUID:
        with self.services.session() as session:
            city_id = session.scalar(select(City.id).where(City.name == name))
        assert city_id is not None
        return city_id

    def next_phone(self) -> str:
        self._phones += 1
        return f"0300{1000000 + self._phones:07d}"

    def last_code(self, phone_e164: str) -> str:
        text = next(t for to, t in reversed(self.sms.sent) if to == phone_e164)
        return next(word for word in text.split() if word.isdigit() and len(word) == 6)

    # -- people

    def customer(self, phone: str | None = None, *, terms: bool = True) -> Person:
        phone = phone or self.next_phone()
        sent = self.post("/api/v1/auth/otp/request", json={"phone": phone})
        assert sent.status_code == 202, sent.text
        e164 = sent.json()["phone_e164"]
        verified = self.post(
            "/api/v1/auth/otp/verify", json={"phone": phone, "code": self.last_code(e164)}
        )
        assert verified.status_code == 200, verified.text
        data = verified.json()
        person = Person(
            uuid.UUID(data["user"]["id"]), data["access_token"], data["refresh_token"], e164
        )
        if terms:
            accepted = self.post(
                "/api/v1/me/terms",
                person,
                {"terms_version": self.services.settings.terms_version},
            )
            assert accepted.status_code == 200, accepted.text
        return person

    def _staff(
        self, email: str, role: Role, password: str, vendor_id: uuid.UUID | None = None
    ) -> None:
        ctx = self.ctx()
        with ctx.session:
            auth.create_staff(
                ctx,
                email=email,
                full_name=email.split("@")[0].title(),
                role=role,
                vendor_id=vendor_id,
                password=password,
                totp_secret=ADMIN_TOTP if role == Role.ADMIN else None,
            )
            ctx.session.commit()

    def staff_login(self, email: str, password: str, totp_code: str | None) -> httpx2.Response:
        return self.post(
            "/api/v1/auth/staff/login",
            json={"email": email, "password": password, "totp_code": totp_code},
        )

    def admin(self, email: str = "admin@example.com") -> Person:
        self._staff(email, Role.ADMIN, ADMIN_PASSWORD)
        response = self.staff_login(
            email, ADMIN_PASSWORD, totp.code_at(ADMIN_TOTP, self.clock.now())
        )
        assert response.status_code == 200, response.text
        data = response.json()
        return Person(uuid.UUID(data["user"]["id"]), data["access_token"], data["refresh_token"])

    def vendor(self, name: str = "Print House") -> uuid.UUID:
        with self.services.session() as session:
            vendor = Vendor(
                name=name,
                contact_name="Contact",
                contact_phone_e164="+923211234567",
                is_active=True,
            )
            session.add(vendor)
            session.commit()
            return vendor.id

    def vendor_user(self, vendor_id: uuid.UUID, email: str | None = None) -> Person:
        email = email or f"vendor-{uuid.uuid4().hex[:6]}@example.com"
        self._staff(email, Role.VENDOR, VENDOR_PASSWORD, vendor_id)
        response = self.staff_login(email, VENDOR_PASSWORD, None)
        assert response.status_code == 200, response.text
        data = response.json()
        return Person(
            uuid.UUID(data["user"]["id"]),
            data["access_token"],
            data["refresh_token"],
            vendor_id=vendor_id,
        )

    def renew(self, *people: Person) -> None:
        """Refresh access tokens, as the clients do, after moving the clock a long way."""
        for person in people:
            response = self.post("/api/v1/auth/refresh", json={"refresh_token": person.refresh})
            assert response.status_code == 200, response.text
            person.token = response.json()["access_token"]
            person.refresh = response.json()["refresh_token"]

    def later(self, delta: timedelta, *people: Person) -> None:
        self.clock.advance(delta)
        self.renew(*people)

    def user(self, person: Person) -> User:
        with self.services.session() as session:
            user = session.get(User, person.id)
            assert user is not None
            return user

    # -- customer flows

    def address(self, who: Person, city: str = "Lahore") -> uuid.UUID:
        response = self.post(
            "/api/v1/me/addresses",
            who,
            {
                "recipient_name": "Ayesha Khan",
                "recipient_phone": "0321 7654321",
                "city_id": str(self.city_id(city)),
                "area": "Gulberg",
                "street_address": "House 12, Street 4",
                "landmark": "Near Liberty Market",
                "is_default": True,
            },
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["id"])

    def upload(
        self, who: Person, content: bytes | None = None, filename: str = "notes.pdf"
    ) -> dict[str, Any]:
        """Upload through presigned URLs and complete; validation runs inline."""
        content = pdf_bytes() if content is None else content
        created = self.post(
            "/api/v1/uploads",
            who,
            {"filename": filename, "size_bytes": len(content), "copyright_declared": True},
        )
        assert created.status_code == 201, created.text
        session = created.json()
        size = session["part_size_bytes"]
        for part in session["parts"]:
            chunk = content[(part["number"] - 1) * size : part["number"] * size]
            put = httpx2.put(part["url"], content=chunk)
            assert put.status_code == 200, put.text
        upload_id = session["upload"]["id"]
        completed = self.post(f"/api/v1/uploads/{upload_id}/complete", who)
        assert completed.status_code == 202, completed.text
        result = self.get(f"/api/v1/uploads/{upload_id}", who)
        assert result.status_code == 200
        data: dict[str, Any] = result.json()
        return data

    def quote_price(self, pages: int, paper: str, binding: str, copies: int, city: str,
                    method: str) -> int:  # fmt: skip
        response = self.post(
            "/api/v1/pricing/quote",
            json={
                "pages": pages,
                "paper": paper,
                "binding": binding,
                "copies": copies,
                "city_id": str(self.city_id(city)),
                "payment_method": method,
            },
        )
        assert response.status_code == 200, response.text
        total: int = response.json()["total_paisa"]
        return total

    def print_order(
        self,
        who: Person,
        *,
        method: str = "COD",
        pages: int = 3,
        copies: int = 1,
        paper: str = "LOCAL_WHITE",
        binding: str = "SOFTCOVER_PAPERBACK",
        city: str = "Lahore",
    ) -> dict[str, Any]:
        upload = self.upload(who, pdf_bytes(pages))
        assert upload["status"] == "VALID", upload
        address = self.address(who, city)
        total = self.quote_price(pages, paper, binding, copies, city, method)
        response = self.post(
            "/api/v1/orders/print",
            who,
            {
                "upload_id": upload["id"],
                "paper": paper,
                "binding": binding,
                "copies": copies,
                "address_id": str(address),
                "payment_method": method,
                "expected_total_paisa": total,
            },
        )
        assert response.status_code == 201, response.text
        data: dict[str, Any] = response.json()
        return data

    def source_order(self, who: Person, *, title: str = "Pir-e-Kamil") -> dict[str, Any]:
        address = self.address(who)
        response = self.post(
            "/api/v1/orders/source",
            who,
            {"book_title": title, "author": "Umera Ahmed", "copies": 1, "address_id": str(address)},
        )
        assert response.status_code == 201, response.text
        data: dict[str, Any] = response.json()
        return data

    def pay(self, order: dict[str, Any], outcome: str = "PAID") -> None:
        """Press a button on the mock gateway's hosted page."""
        ref = order["payment"]["checkout_url"].rsplit("/", 1)[-1]
        response = self.client.post(f"/mock/payments/{ref}/complete", data={"outcome": outcome})
        assert response.status_code == 200, response.text

    def admin_action(
        self, admin: Person, order_id: str, action: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = self.post(f"/api/v1/admin/orders/{order_id}/{action}", admin, body or {})
        assert response.status_code == 200, response.text
        data: dict[str, Any] = response.json()
        return data
