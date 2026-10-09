"""The order state machine (docs/ARCHITECTURE.md section 4): every legal
transition works and writes a history row; every other move is refused."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import select

from kitaab.domain.context import Ctx
from kitaab.domain.enums import (
    TERMINAL_STATUSES,
    Actor,
    LedgerEntryType,
    OrderStatus,
    OrderType,
    PaymentMethod,
    PaymentStatus,
    Role,
)
from kitaab.domain.orders import service
from kitaab.domain.orders import state_machine as sm
from kitaab.models import LedgerEntry, Notification, Order, OrderStatusHistory, User, Vendor
from kitaab.problems import ProblemError
from support import START

S = OrderStatus


def test_table_has_one_row_per_move() -> None:
    keys = [(t.type, t.source, t.target) for t in sm.TRANSITIONS]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("order_type", list(OrderType))
def test_every_state_is_reachable_from_an_initial_state(order_type: OrderType) -> None:
    reached = set(sm.INITIAL_STATES[order_type])
    frontier = list(reached)
    while frontier:
        state = frontier.pop()
        for t in sm.TRANSITIONS:
            if t.type == order_type and t.source == state and t.target not in reached:
                reached.add(t.target)
                frontier.append(t.target)
    assert reached == sm.states_for(order_type)


def test_terminal_states_have_no_way_out() -> None:
    assert not [t for t in sm.TRANSITIONS if t.source in TERMINAL_STATUSES]


def test_every_non_terminal_state_has_a_way_out() -> None:
    for order_type in OrderType:
        for state in sm.states_for(order_type) - TERMINAL_STATUSES:
            assert [t for t in sm.TRANSITIONS if t.type == order_type and t.source == state], state


def test_types_do_not_share_states_they_should_not() -> None:
    assert S.QUOTED not in sm.states_for(OrderType.PRINT)
    assert S.IN_PRINT not in sm.states_for(OrderType.SOURCE)
    assert S.PENDING_PAYMENT not in sm.states_for(OrderType.SOURCE)


def test_actions_for_admin_reviewing_a_file() -> None:
    assert set(sm.actions_for(OrderType.PRINT, S.VERIFYING, Actor.ADMIN)) == {
        "approve",
        "reject",
        "cancel",
    }
    assert sm.actions_for(OrderType.PRINT, S.VERIFYING, Actor.VENDOR) == []
    assert sm.actions_for(OrderType.PRINT, S.ASSIGNED, Actor.VENDOR) == ["start-printing"]
    assert sm.actions_for(OrderType.PRINT, S.ASSIGNED, Actor.USER) == []


def test_customers_cannot_cancel_once_printing_is_assigned() -> None:
    assert sm.find(OrderType.PRINT, S.VERIFYING, S.CANCELLED) is not None
    rule = sm.find(OrderType.PRINT, S.ASSIGNED, S.CANCELLED)
    assert rule is not None
    assert Actor.USER not in rule.actors
    assert rule.needs_reason


def test_reasons_are_required_for_every_rejection_and_staff_cancellation() -> None:
    for target in (S.REJECTED, S.UNAVAILABLE):
        assert all(t.needs_reason for t in sm.TRANSITIONS if t.target == target)


# -- illegal moves never touch the database -----------------------------------------


class _NoDatabase:
    def __getattr__(self, name: str) -> object:
        raise AssertionError("an illegal transition touched the database")


@dataclass
class _StubCtx:
    session: object = field(default_factory=_NoDatabase)
    services: object = None
    user: object = None
    now: datetime = START


@pytest.mark.parametrize("order_type", list(OrderType))
def test_every_illegal_move_is_refused(order_type: OrderType) -> None:
    checked = 0
    for source in sm.states_for(order_type):
        for target in OrderStatus:
            rule = sm.find(order_type, source, target)
            for actor in Actor:
                if rule is not None and actor in rule.actors:
                    continue
                order = Order(type=order_type, status=source)
                stub: Any = _StubCtx()
                with pytest.raises(ProblemError) as error:
                    service.transition(stub, order, target, actor=actor, reason="x")
                assert error.value.status == 409
                assert error.value.code == "invalid-transition"
                assert order.status == source
                checked += 1
    assert checked > 500


# -- every legal move, against the database -----------------------------------------

LEGAL = [(t, actor) for t in sm.TRANSITIONS for actor in sorted(t.actors)]


def _id(case: tuple[sm.Transition, Actor]) -> str:
    t, actor = case
    return f"{t.type.value}:{t.source.value}->{t.target.value}:{actor.value}"


def _person(ctx: Ctx, role: Role, vendor: Vendor | None = None) -> User:
    user = User(
        role=role,
        phone_e164="+923001234567" if role == Role.CUSTOMER else None,
        email=None if role == Role.CUSTOMER else f"{role.value.lower()}@example.com",
        vendor_id=vendor.id if vendor else None,
        created_at=ctx.now,
        updated_at=ctx.now,
    )
    ctx.session.add(user)
    ctx.session.flush()
    return user


def make_order(
    ctx: Ctx, customer: User, order_type: OrderType, status: OrderStatus, **fields: object
) -> Order:
    values: dict[str, Any] = {
        "copies": 1,
        "ship_city_name": "Lahore",
        "ship_zone_code": "Z1",
        "payment_method": PaymentMethod.COD,
        "payment_status": PaymentStatus.PENDING,
        "total_paisa": 100000,
        **fields,
    }
    order = Order(
        code=service.new_order_code(ctx.session),
        user_id=customer.id,
        type=order_type,
        status=status,
        created_at=ctx.now,
        updated_at=ctx.now,
        **values,
    )
    ctx.session.add(order)
    ctx.session.flush()
    return order


@pytest.mark.integration
@pytest.mark.parametrize("case", LEGAL, ids=[_id(c) for c in LEGAL])
def test_legal_move_changes_status_and_writes_history(
    ctx: Ctx, case: tuple[sm.Transition, Actor]
) -> None:
    rule, actor = case
    vendor = Vendor(name="V", contact_name="C", contact_phone_e164="+923211234567")
    ctx.session.add(vendor)
    ctx.session.flush()
    customer = _person(ctx, Role.CUSTOMER)
    ctx.user = {
        Actor.USER: customer,
        Actor.ADMIN: _person(ctx, Role.ADMIN),
        Actor.VENDOR: _person(ctx, Role.VENDOR, vendor),
        Actor.SYSTEM: None,
    }[actor]
    order = make_order(
        ctx, customer, rule.type, rule.source, vendor_id=vendor.id, vendor_cost_paisa=40000
    )

    service.transition(ctx, order, rule.target, actor=actor, reason="Checked by the test")
    ctx.session.commit()

    assert order.status == rule.target
    history = ctx.session.scalars(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
    ).all()
    assert [(h.from_status, h.to_status, h.actor) for h in history] == [
        (rule.source, rule.target, actor)
    ]
    assert history[0].actor_user_id == (ctx.user.id if ctx.user else None)
    assert history[0].reason == "Checked by the test"
    notified = ctx.session.scalar(select(Notification.id).where(Notification.order_id == order.id))
    assert (notified is not None) == (sm.Effect.NOTIFY in rule.effects)
    if sm.Effect.MARK_TERMINAL in rule.effects:
        assert order.terminal_at == START
    if rule.target in (S.REJECTED, S.CANCELLED, S.UNAVAILABLE, S.DELIVERY_FAILED):
        assert order.exit_reason == "Checked by the test"
    if sm.Effect.ACCRUE_VENDOR_COST in rule.effects:
        accrued = ctx.session.scalar(
            select(LedgerEntry.amount_paisa).where(
                LedgerEntry.order_id == order.id,
                LedgerEntry.entry_type == LedgerEntryType.VENDOR_COST_ACCRUED,
            )
        )
        assert accrued == 40000


@pytest.mark.integration
def test_reason_is_required_where_the_table_says_so(ctx: Ctx) -> None:
    customer = _person(ctx, Role.CUSTOMER)
    ctx.user = _person(ctx, Role.ADMIN)
    order = make_order(ctx, customer, OrderType.PRINT, S.VERIFYING)
    for reason in (None, "", "   "):
        with pytest.raises(ProblemError) as error:
            service.transition(ctx, order, S.REJECTED, reason=reason)
        assert error.value.code == "reason-required"
    assert order.status == S.VERIFYING


@pytest.mark.integration
def test_delivery_of_a_paid_order_completes_it(ctx: Ctx) -> None:
    customer = _person(ctx, Role.CUSTOMER)
    order = make_order(
        ctx,
        customer,
        OrderType.PRINT,
        S.DISPATCHED,
        payment_method=PaymentMethod.EASYPAISA,
    )
    order.payment_status = PaymentStatus.PAID
    service.transition(ctx, order, S.DELIVERED, actor=Actor.SYSTEM)
    assert order.status == S.COMPLETED
    assert order.delivered_at == START
    assert order.completed_at == START
    steps = ctx.session.scalars(
        select(OrderStatusHistory.to_status)
        .where(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.id)
    ).all()
    assert set(steps) == {S.DELIVERED, S.COMPLETED}


@pytest.mark.integration
def test_actor_defaults_to_the_signed_in_user(ctx: Ctx) -> None:
    customer = _person(ctx, Role.CUSTOMER)
    ctx.user = customer
    order = make_order(ctx, customer, OrderType.PRINT, S.PLACED)
    service.transition(ctx, order, S.CANCELLED)
    assert order.status == S.CANCELLED
    ctx.user = None
    with pytest.raises(ProblemError):
        # The system may not cancel a placed order (only an unpaid one).
        service.transition(ctx, make_order(ctx, customer, OrderType.PRINT, S.PLACED), S.CANCELLED)
