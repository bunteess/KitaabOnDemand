"""Every legal order transition, in one table (docs/ARCHITECTURE.md section 4).

Each row says which actors may move an order of a given type from one state to
another, the name of the action (used by the API and `allowed_actions`), and the
side effects to run. Anything not in the table is illegal.
"""

from dataclasses import dataclass
from enum import StrEnum

from kitaab.domain.enums import Actor, OrderStatus, OrderType

S = OrderStatus
A = Actor
PRINT = OrderType.PRINT
SOURCE = OrderType.SOURCE


class Effect(StrEnum):
    NOTIFY = "NOTIFY"  # inbox + push (+ SMS fallback for key statuses)
    REFUND_IF_PAID = "REFUND_IF_PAID"  # create a refund record for a paid digital payment
    CLOSE_PENDING_PAYMENT = "CLOSE_PENDING_PAYMENT"  # mark an unpaid digital payment failed
    MARK_TERMINAL = "MARK_TERMINAL"  # set terminal_at (purge timer for cancelled/rejected)
    MARK_DELIVERED = (
        "MARK_DELIVERED"  # set delivered_at (purge timer), COD collected, try to complete
    )
    ACCRUE_VENDOR_COST = "ACCRUE_VENDOR_COST"  # ledger: vendor cost accrued (D-015)
    CLOSE_QUOTE = "CLOSE_QUOTE"  # an open quote is cancelled or expired


@dataclass(frozen=True)
class Transition:
    type: OrderType
    source: OrderStatus
    target: OrderStatus
    actors: frozenset[Actor]
    action: str
    needs_reason: bool = False
    effects: tuple[Effect, ...] = ()


def _t(
    order_type: OrderType,
    sources: tuple[OrderStatus, ...],
    target: OrderStatus,
    actors: tuple[Actor, ...],
    action: str,
    *effects: Effect,
    needs_reason: bool = False,
) -> list[Transition]:
    return [
        Transition(order_type, source, target, frozenset(actors), action, needs_reason, effects)
        for source in sources
    ]


CANCEL_EFFECTS = (
    Effect.REFUND_IF_PAID,
    Effect.CLOSE_PENDING_PAYMENT,
    Effect.MARK_TERMINAL,
    Effect.NOTIFY,
)

TRANSITIONS: tuple[Transition, ...] = (
    # -- PRINT ----------------------------------------------------------------
    *_t(PRINT, (S.PENDING_PAYMENT,), S.PLACED, (A.SYSTEM,), "payment-received", Effect.NOTIFY),
    *_t(
        PRINT,
        (S.PENDING_PAYMENT,),
        S.CANCELLED,
        (A.USER, A.ADMIN, A.SYSTEM),
        "cancel",
        *CANCEL_EFFECTS,
    ),
    *_t(PRINT, (S.PLACED,), S.VERIFYING, (A.ADMIN,), "start-verification"),
    *_t(
        PRINT,
        (S.PLACED, S.VERIFYING),
        S.CANCELLED,
        (A.USER, A.ADMIN),
        "cancel",
        *CANCEL_EFFECTS,
    ),
    *_t(PRINT, (S.VERIFYING,), S.ASSIGNED, (A.ADMIN,), "approve", Effect.NOTIFY),
    *_t(
        PRINT,
        (S.VERIFYING,),
        S.REJECTED,
        (A.ADMIN,),
        "reject",
        Effect.REFUND_IF_PAID,
        Effect.MARK_TERMINAL,
        Effect.NOTIFY,
        needs_reason=True,
    ),
    *_t(
        PRINT,
        (S.ASSIGNED, S.IN_PRINT),
        S.CANCELLED,
        (A.ADMIN,),
        "cancel",
        *CANCEL_EFFECTS,
        needs_reason=True,
    ),
    *_t(PRINT, (S.ASSIGNED,), S.IN_PRINT, (A.VENDOR, A.ADMIN), "start-printing", Effect.NOTIFY),
    *_t(
        PRINT,
        (S.IN_PRINT,),
        S.READY_FOR_DISPATCH,
        (A.VENDOR, A.ADMIN),
        "ready-for-dispatch",
        Effect.ACCRUE_VENDOR_COST,
    ),
    *_t(PRINT, (S.READY_FOR_DISPATCH,), S.DISPATCHED, (A.ADMIN,), "dispatch", Effect.NOTIFY),
    *_t(
        PRINT,
        (S.DISPATCHED,),
        S.DELIVERED,
        (A.SYSTEM, A.ADMIN),
        "mark-delivered",
        Effect.MARK_DELIVERED,
        Effect.NOTIFY,
    ),
    *_t(
        PRINT,
        (S.DISPATCHED,),
        S.DELIVERY_FAILED,
        (A.SYSTEM, A.ADMIN),
        "mark-delivery-failed",
        Effect.MARK_TERMINAL,
        Effect.NOTIFY,
    ),
    *_t(PRINT, (S.DELIVERED,), S.COMPLETED, (A.SYSTEM,), "complete"),
    # -- SOURCE ---------------------------------------------------------------
    *_t(SOURCE, (S.REQUESTED,), S.QUOTED, (A.ADMIN,), "quote", Effect.NOTIFY),
    *_t(
        SOURCE,
        (S.REQUESTED, S.ACCEPTED, S.SOURCING),
        S.UNAVAILABLE,
        (A.ADMIN,),
        "mark-unavailable",
        Effect.REFUND_IF_PAID,
        Effect.CLOSE_PENDING_PAYMENT,
        Effect.MARK_TERMINAL,
        Effect.NOTIFY,
        needs_reason=True,
    ),
    *_t(SOURCE, (S.QUOTED,), S.ACCEPTED, (A.USER,), "accept-quote"),
    *_t(
        SOURCE,
        (S.QUOTED,),
        S.DECLINED,
        (A.USER,),
        "decline-quote",
        Effect.CLOSE_QUOTE,
        Effect.MARK_TERMINAL,
    ),
    *_t(
        SOURCE,
        (S.QUOTED,),
        S.QUOTE_EXPIRED,
        (A.SYSTEM,),
        "expire-quote",
        Effect.CLOSE_QUOTE,
        Effect.MARK_TERMINAL,
        Effect.NOTIFY,
    ),
    *_t(
        SOURCE,
        (S.REQUESTED, S.QUOTED, S.ACCEPTED),
        S.CANCELLED,
        (A.USER, A.ADMIN),
        "cancel",
        Effect.CLOSE_QUOTE,
        *CANCEL_EFFECTS,
    ),
    *_t(SOURCE, (S.ACCEPTED,), S.SOURCING, (A.ADMIN,), "start-sourcing", Effect.NOTIFY),
    *_t(
        SOURCE,
        (S.SOURCING,),
        S.CANCELLED,
        (A.ADMIN,),
        "cancel",
        *CANCEL_EFFECTS,
        needs_reason=True,
    ),
    *_t(
        SOURCE,
        (S.SOURCING,),
        S.READY_FOR_DISPATCH,
        (A.ADMIN, A.VENDOR),
        "ready-for-dispatch",
        Effect.ACCRUE_VENDOR_COST,
    ),
    *_t(SOURCE, (S.READY_FOR_DISPATCH,), S.DISPATCHED, (A.ADMIN,), "dispatch", Effect.NOTIFY),
    *_t(
        SOURCE,
        (S.DISPATCHED,),
        S.DELIVERED,
        (A.SYSTEM, A.ADMIN),
        "mark-delivered",
        Effect.MARK_DELIVERED,
        Effect.NOTIFY,
    ),
    *_t(
        SOURCE,
        (S.DISPATCHED,),
        S.DELIVERY_FAILED,
        (A.SYSTEM, A.ADMIN),
        "mark-delivery-failed",
        Effect.MARK_TERMINAL,
        Effect.NOTIFY,
    ),
    *_t(SOURCE, (S.DELIVERED,), S.COMPLETED, (A.SYSTEM,), "complete"),
)

INITIAL_STATES: dict[OrderType, frozenset[OrderStatus]] = {
    PRINT: frozenset({S.PENDING_PAYMENT, S.PLACED}),
    SOURCE: frozenset({S.REQUESTED}),
}

_INDEX: dict[tuple[OrderType, OrderStatus, OrderStatus], Transition] = {
    (t.type, t.source, t.target): t for t in TRANSITIONS
}


def find(order_type: OrderType, source: OrderStatus, target: OrderStatus) -> Transition | None:
    return _INDEX.get((order_type, source, target))


def available(order_type: OrderType, source: OrderStatus, actor: Actor) -> list[Transition]:
    return [
        t for t in TRANSITIONS if t.type == order_type and t.source == source and actor in t.actors
    ]


def actions_for(order_type: OrderType, source: OrderStatus, actor: Actor) -> list[str]:
    seen: list[str] = []
    for t in available(order_type, source, actor):
        if t.action not in seen:
            seen.append(t.action)
    return seen


def states_for(order_type: OrderType) -> set[OrderStatus]:
    states = set(INITIAL_STATES[order_type])
    for t in TRANSITIONS:
        if t.type == order_type:
            states |= {t.source, t.target}
    return states
