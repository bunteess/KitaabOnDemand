"""What every business function receives: the session, the services and who is acting."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from kitaab.container import Services
from kitaab.models import User


@dataclass
class Ctx:
    session: Session
    services: Services
    user: User | None = None

    @property
    def now(self) -> datetime:
        return self.services.clock.now()
