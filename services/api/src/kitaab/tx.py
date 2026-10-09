"""Run work after the database transaction commits (queue jobs, send pushes).

Side effects that leave the database must only happen once the data they refer
to is committed, and must not happen at all if the transaction rolls back.
"""

import logging
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)
_KEY = "after_commit"


def after_commit(session: Session, callback: Callable[[], None]) -> None:
    session.info.setdefault(_KEY, []).append(callback)


@event.listens_for(Session, "after_commit")
def _run(session: Session) -> None:
    callbacks: list[Callable[[], None]] = session.info.pop(_KEY, [])
    for callback in callbacks:
        try:
            callback()
        except Exception:
            log.exception("after-commit callback failed")


@event.listens_for(Session, "after_rollback")
def _discard(session: Session) -> None:
    session.info.pop(_KEY, None)
