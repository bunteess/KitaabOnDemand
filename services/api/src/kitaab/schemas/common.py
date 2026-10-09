from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Paisa = Annotated[int, Field(ge=0, description="Amount in paisa (1 rupee = 100 paisa)")]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageMeta(Schema):
    total: int
    page: int
    page_size: int


class FileUrl(Schema):
    url: str
    expires_at: datetime
