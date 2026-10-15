import re
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, model_validator

ISBN_PATTERN = re.compile(r"\d{13}|\d{9}[\dX]")


def strip_text(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def normalize_isbn(value: object) -> object:
    """ハイフン・空白を除いて保存する。空文字は未入力(None)として扱う。"""
    if not isinstance(value, str):
        return value
    normalized = re.sub(r"[-\s]", "", value).upper()
    if normalized == "":
        return None
    if not ISBN_PATTERN.fullmatch(normalized):
        raise ValueError("ISBN must be 10 or 13 digits (hyphens allowed)")
    return normalized


Title = Annotated[str, BeforeValidator(strip_text), Field(min_length=1, max_length=200)]
Author = Annotated[
    str, BeforeValidator(strip_text), Field(min_length=1, max_length=100)
]
Isbn = Annotated[str | None, BeforeValidator(normalize_isbn)]
ReadingStatus = Literal["unread", "reading", "finished"]


class BookCreate(BaseModel):
    title: Title
    author: Author
    isbn: Isbn = None


class BookUpdate(BaseModel):
    """PATCH 用。送られた項目だけを更新する。isbn に null / "" を送ると ISBN を消す。"""

    title: Title | None = None
    author: Author | None = None
    isbn: Isbn = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for name in ("title", "author"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class BookRead(BaseModel):
    id: int
    title: str
    author: str
    isbn: str | None
    status: ReadingStatus
    created_at: datetime
    updated_at: datetime


class BookStatusUpdate(BaseModel):
    status: ReadingStatus
