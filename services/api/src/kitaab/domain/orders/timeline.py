"""The customer-facing timeline (docs/ARCHITECTURE.md section 4.4).

Customers always see the same steps. The server computes them so the app holds
no mapping logic. Exit states keep the steps already reached.
"""

from dataclasses import dataclass
from datetime import datetime

from kitaab.domain.enums import TERMINAL_STATUSES, OrderStatus, OrderType, StepState, TimelineStep

S = OrderStatus

PRINT_STEPS = (
    TimelineStep.PLACED,
    TimelineStep.VERIFYING,
    TimelineStep.PRINTING,
    TimelineStep.OUT_FOR_DELIVERY,
    TimelineStep.COMPLETED,
)
SOURCE_STEPS = (
    TimelineStep.PLACED,
    TimelineStep.VERIFYING,
    TimelineStep.OUT_FOR_DELIVERY,
    TimelineStep.COMPLETED,
)

_STEP_OF: dict[OrderType, dict[OrderStatus, TimelineStep]] = {
    OrderType.PRINT: {
        S.PLACED: TimelineStep.PLACED,
        S.VERIFYING: TimelineStep.VERIFYING,
        S.ASSIGNED: TimelineStep.VERIFYING,
        S.IN_PRINT: TimelineStep.PRINTING,
        S.READY_FOR_DISPATCH: TimelineStep.PRINTING,
        S.DISPATCHED: TimelineStep.OUT_FOR_DELIVERY,
        S.DELIVERED: TimelineStep.COMPLETED,
        S.COMPLETED: TimelineStep.COMPLETED,
    },
    OrderType.SOURCE: {
        S.REQUESTED: TimelineStep.PLACED,
        S.QUOTED: TimelineStep.VERIFYING,
        S.ACCEPTED: TimelineStep.VERIFYING,
        S.SOURCING: TimelineStep.VERIFYING,
        S.READY_FOR_DISPATCH: TimelineStep.VERIFYING,
        S.DISPATCHED: TimelineStep.OUT_FOR_DELIVERY,
        S.DELIVERED: TimelineStep.COMPLETED,
        S.COMPLETED: TimelineStep.COMPLETED,
    },
}

EXIT_STATUSES = TERMINAL_STATUSES - {S.COMPLETED}


@dataclass(frozen=True)
class Step:
    step: TimelineStep
    state: StepState
    at: datetime | None


def steps_for(order_type: OrderType) -> tuple[TimelineStep, ...]:
    return PRINT_STEPS if order_type == OrderType.PRINT else SOURCE_STEPS


def step_of(order_type: OrderType, status: OrderStatus) -> TimelineStep | None:
    return _STEP_OF[order_type].get(status)


def build_timeline(
    order_type: OrderType, status: OrderStatus, history: list[tuple[OrderStatus, datetime]]
) -> list[Step]:
    """`history` is (to_status, when) in time order, starting with the creation row."""
    steps = steps_for(order_type)
    reached_at: dict[TimelineStep, datetime] = {}
    last_step_index = -1
    for to_status, when in history:
        step = step_of(order_type, to_status)
        if step is None:
            continue
        reached_at.setdefault(step, when)
        last_step_index = max(last_step_index, steps.index(step))

    exited = status in EXIT_STATUSES
    finished = step_of(order_type, status) == TimelineStep.COMPLETED
    timeline = []
    for index, step in enumerate(steps):
        if index < last_step_index or (index == last_step_index and (finished or exited)):
            state = StepState.DONE
        elif index == last_step_index:
            state = StepState.CURRENT
        else:
            state = StepState.UPCOMING
        timeline.append(Step(step, state, reached_at.get(step)))
    return timeline
