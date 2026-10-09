"""The ledger: append-only entries and the finance reports built from them."""

import csv
import datetime as dt
import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from kitaab.domain import ledger
from kitaab.domain.context import Ctx
from kitaab.domain.enums import (
    OrderStatus,
    OrderType,
    PaymentMethod,
    PaymentStatus,
    RefundStatus,
    Role,
)
from kitaab.domain.orders import service
from kitaab.models import LedgerEntry, Order, Payment, Refund, User, Vendor
from kitaab.problems import ProblemError
from support import Api

pytestmark = pytest.mark.integration


@pytest.fixture
def customer(ctx: Ctx) -> User:
    user = User(role=Role.CUSTOMER, phone_e164="+923001234567", created_at=ctx.now)
    ctx.session.add(user)
    ctx.session.flush()
    return user


@pytest.fixture
def vendor(ctx: Ctx) -> Vendor:
    v = Vendor(name="Press One", contact_name="A", contact_phone_e164="+923211234567")
    ctx.session.add(v)
    ctx.session.flush()
    return v


def _order(
    ctx: Ctx,
    customer: User,
    *,
    method: PaymentMethod = PaymentMethod.COD,
    total: int = 125000,
    vendor: Vendor | None = None,
    vendor_cost: int | None = None,
    courier: str | None = "mock",
) -> tuple[Order, Payment]:
    order = Order(
        code=service.new_order_code(ctx.session),
        user_id=customer.id,
        type=OrderType.PRINT,
        status=OrderStatus.DELIVERED,
        copies=1,
        ship_city_name="Lahore",
        ship_zone_code="Z1",
        payment_method=method,
        payment_status=PaymentStatus.PENDING,
        total_paisa=total,
        vendor_id=vendor.id if vendor else None,
        vendor_cost_paisa=vendor_cost,
        courier_code=courier,
        cn_number="MOCK-100001",
        delivered_at=ctx.now,
        created_at=ctx.now,
        updated_at=ctx.now,
    )
    ctx.session.add(order)
    ctx.session.flush()
    payment = Payment(
        order_id=order.id,
        method=method,
        provider="cod" if method == PaymentMethod.COD else "mock",
        amount_paisa=total,
        status=PaymentStatus.PENDING,
        created_at=ctx.now,
    )
    ctx.session.add(payment)
    ctx.session.flush()
    return order, payment


def test_entries_cannot_be_changed_or_deleted(ctx: Ctx, customer: User) -> None:
    order, payment = _order(ctx, customer, method=PaymentMethod.EASYPAISA)
    ledger.record_revenue(ctx, order, payment)
    ctx.session.commit()
    for statement in ("UPDATE ledger_entries SET amount_paisa = 1", "DELETE FROM ledger_entries"):
        with pytest.raises(DBAPIError, match="append-only"):
            ctx.session.execute(text(statement))
        ctx.session.rollback()
    assert ctx.session.query(LedgerEntry).count() == 1


def test_amounts_are_never_negative(ctx: Ctx, customer: User) -> None:
    order, payment = _order(ctx, customer, total=-5)
    with pytest.raises(ValueError):
        ledger.record_revenue(ctx, order, payment)


def test_recording_twice_records_once(ctx: Ctx, customer: User, vendor: Vendor) -> None:
    order, payment = _order(ctx, customer, vendor=vendor, vendor_cost=40000)
    for _ in range(2):
        ledger.record_cod_collected(ctx, order, payment)
        ledger.accrue_vendor_cost(ctx, order)
    types = sorted(e.entry_type.value for e in ctx.session.query(LedgerEntry))
    assert types == ["COD_COLLECTED", "REVENUE", "VENDOR_COST_ACCRUED"]


def test_no_vendor_cost_without_a_vendor(ctx: Ctx, customer: User) -> None:
    order, _ = _order(ctx, customer, vendor_cost=40000)
    ledger.accrue_vendor_cost(ctx, order)
    assert ctx.session.query(LedgerEntry).count() == 0


def test_daily_revenue_uses_pakistan_days_and_nets_refunds(ctx: Ctx, customer: User) -> None:
    # 18:30 UTC on 9 October is 23:30 in Karachi; 19:30 UTC is already 10 October.
    ctx.services.clock.set(datetime(2026, 10, 9, 18, 30, tzinfo=UTC))  # type: ignore[attr-defined]
    late, late_pay = _order(ctx, customer, method=PaymentMethod.EASYPAISA, total=100000)
    ledger.record_revenue(ctx, late, late_pay)
    cod, cod_pay = _order(ctx, customer, total=50000)
    ledger.record_cod_collected(ctx, cod, cod_pay)
    ctx.services.clock.set(datetime(2026, 10, 9, 19, 30, tzinfo=UTC))  # type: ignore[attr-defined]
    after, after_pay = _order(ctx, customer, method=PaymentMethod.EASYPAISA, total=70000)
    ledger.record_revenue(ctx, after, after_pay)
    refund = Refund(
        order_id=late.id,
        payment_id=late_pay.id,
        amount_paisa=30000,
        status=RefundStatus.PROCESSED,
        reason="r",
        created_at=ctx.now,
    )
    ctx.session.add(refund)
    ctx.session.flush()
    ledger.record_refund(ctx, refund, late)

    rows = ledger.daily_revenue(ctx, dt.date(2026, 10, 9), dt.date(2026, 10, 10))
    summary = [
        (r.date.isoformat(), r.payment_method.value, r.orders, r.gross_paisa, r.net_paisa)
        for r in rows
    ]
    assert summary == [
        ("2026-10-09", "COD", 1, 50000, 50000),
        ("2026-10-09", "EASYPAISA", 1, 100000, 100000),
        ("2026-10-10", "EASYPAISA", 1, 70000, 40000),
    ]
    only_ninth = ledger.daily_revenue(ctx, dt.date(2026, 10, 9), dt.date(2026, 10, 9))
    assert sum(r.gross_paisa for r in only_ninth) == 150000


def test_revenue_range_is_checked(ctx: Ctx) -> None:
    with pytest.raises(ProblemError):
        ledger.daily_revenue(ctx, dt.date(2026, 10, 9), dt.date(2026, 10, 8))
    with pytest.raises(ProblemError):
        ledger.daily_revenue(ctx, dt.date(2025, 1, 1), dt.date(2026, 10, 8))


def test_cod_remittance(ctx: Ctx, customer: User) -> None:
    first, first_pay = _order(ctx, customer, total=100000)
    second, second_pay = _order(ctx, customer, total=60000)
    other, other_pay = _order(ctx, customer, total=1000, courier="trax")
    for order, payment in ((first, first_pay), (second, second_pay), (other, other_pay)):
        ledger.record_cod_collected(ctx, order, payment)
    ctx.session.commit()
    assert sum(p.amount_paisa for p in ledger.cod_pending(ctx)) == 161000

    with pytest.raises(ProblemError) as mismatch:
        ledger.record_cod_remittance(ctx, "mock", [first.id, other.id], "REF-1")
    assert mismatch.value.code == "courier-mismatch"
    ctx.session.rollback()

    first, second = ctx.session.get(Order, first.id), ctx.session.get(Order, second.id)
    assert first is not None
    assert second is not None
    remittance = ledger.record_cod_remittance(ctx, "mock", [first.id, second.id], "REF-1")
    assert remittance.total_paisa == 160000
    assert first.payment_status == PaymentStatus.PAID
    assert [p.order_code for p in ledger.cod_pending(ctx)] == [other.code]
    with pytest.raises(ProblemError) as twice:
        ledger.record_cod_remittance(ctx, "mock", [first.id], "REF-2")
    assert twice.value.code == "already-remitted"


def test_remittance_needs_collected_cash(ctx: Ctx, customer: User) -> None:
    order, _ = _order(ctx, customer)
    with pytest.raises(ProblemError) as error:
        ledger.record_cod_remittance(ctx, "mock", [order.id], "REF")
    assert error.value.code == "cod-not-collected"


def test_vendor_balances_and_payout_batches(ctx: Ctx, customer: User, vendor: Vendor) -> None:
    for cost in (40000, 25000):
        order, _ = _order(ctx, customer, vendor=vendor, vendor_cost=cost)
        ledger.accrue_vendor_cost(ctx, order)
    (balance,) = ledger.vendor_balances(ctx)
    assert (balance.accrued_paisa, balance.paid_paisa, balance.owed_paisa) == (65000, 0, 65000)

    batch = ledger.create_payout_batch(ctx, vendor.id)
    assert batch.total_paisa == 65000
    (balance,) = ledger.vendor_balances(ctx)
    assert balance.in_open_batches_paisa == 65000
    with pytest.raises(ProblemError) as empty:
        ledger.create_payout_batch(ctx, vendor.id)
    assert empty.value.code == "nothing-to-pay"

    # New work after the batch goes into the next one.
    later, _ = _order(ctx, customer, vendor=vendor, vendor_cost=10000)
    ledger.accrue_vendor_cost(ctx, later)

    ledger.mark_batch_paid(ctx, batch.id, "IBFT-778899")
    (balance,) = ledger.vendor_balances(ctx)
    assert (balance.accrued_paisa, balance.paid_paisa, balance.owed_paisa) == (75000, 65000, 10000)
    assert balance.in_open_batches_paisa == 0
    with pytest.raises(ProblemError) as again:
        ledger.mark_batch_paid(ctx, batch.id, "IBFT-778899")
    assert again.value.code == "already-paid"
    assert ledger.create_payout_batch(ctx, vendor.id).total_paisa == 10000


def test_inactive_vendors_without_costs_are_hidden(ctx: Ctx, vendor: Vendor) -> None:
    vendor.is_active = False
    assert ledger.vendor_balances(ctx) == []


def test_finance_endpoints_and_csv(api: Api) -> None:
    customer = api.customer()
    admin = api.admin()
    vendor = api.vendor("Press Two")
    order = api.print_order(customer, method="EASYPAISA")
    api.pay(order)
    api.admin_action(admin, order["id"], "start-verification")
    api.admin_action(
        admin, order["id"], "approve", {"vendor_id": str(vendor), "vendor_cost_paisa": 12345}
    )
    api.admin_action(admin, order["id"], "start-printing")
    api.admin_action(admin, order["id"], "ready-for-dispatch")
    cod = api.print_order(customer)
    for action, body in (
        ("start-verification", {}),
        ("approve", {"vendor_id": str(vendor), "vendor_cost_paisa": 100}),
        ("start-printing", {}),
        ("ready-for-dispatch", {}),
        ("dispatch", {"courier_code": "mock"}),
        ("mark-delivered", {}),
    ):
        api.admin_action(admin, cod["id"], action, body)

    report = api.get(
        "/api/v1/admin/finance/daily-revenue?from_date=2026-10-09&to_date=2026-10-09", admin
    ).json()
    assert report["total_gross_paisa"] == order["total_paisa"] + cod["total_paisa"]
    assert {r["payment_method"] for r in report["rows"]} == {"EASYPAISA", "COD"}
    bad = api.get(
        "/api/v1/admin/finance/daily-revenue?from_date=2026-10-09&to_date=2026-10-01", admin
    )
    assert bad.status_code == 422

    exported = api.get(
        "/api/v1/admin/finance/daily-revenue.csv?from_date=2026-10-09&to_date=2026-10-09", admin
    )
    assert exported.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert {r["payment_method"] for r in rows} == {"EASYPAISA", "COD"}
    easypaisa = next(r for r in rows if r["payment_method"] == "EASYPAISA")
    assert easypaisa["gross_pkr"] == f"{order['total_paisa'] / 100:.2f}"

    pending = api.get("/api/v1/admin/finance/cod-pending", admin).json()
    assert pending[0]["courier_name"] == "Mock Courier"
    assert pending[0]["total_paisa"] == cod["total_paisa"]
    pending_csv = api.get("/api/v1/admin/finance/cod-pending.csv", admin)
    assert cod["code"] in pending_csv.text

    payouts = api.get("/api/v1/admin/finance/vendor-payouts", admin).json()
    assert payouts[0]["owed_paisa"] == 12445
    assert "Press Two" in api.get("/api/v1/admin/finance/vendor-payouts.csv", admin).text

    batch = api.post(
        "/api/v1/admin/finance/payout-batches", admin, {"vendor_id": str(vendor)}
    ).json()
    assert batch["total_paisa"] == 12445
    assert len(batch["items"]) == 2
    listed = api.get(f"/api/v1/admin/finance/payout-batches?vendor_id={vendor}", admin).json()
    assert [b["id"] for b in listed] == [batch["id"]]
    paid = api.post(
        f"/api/v1/admin/finance/payout-batches/{batch['id']}/mark-paid",
        admin,
        {"reference": "IBFT-1"},
    ).json()
    assert paid["status"] == "PAID"
    batch_csv = api.get(f"/api/v1/admin/finance/payout-batches/{batch['id']}.csv", admin)
    assert order["code"] in batch_csv.text
    missing = api.get(f"/api/v1/admin/finance/payout-batches/{order['id']}.csv", admin)
    assert missing.status_code == 404
    api.clock.advance(timedelta(seconds=1))
    assert api.get("/api/v1/admin/finance/vendor-payouts", admin).json()[0]["owed_paisa"] == 0
