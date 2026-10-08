from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Book(SQLModel, table=True):
    __tablename__ = "books"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)
    author: str = Field(max_length=100)
    # 任意項目。NULL は複数行で許容され、値が入った場合のみ一意になる
    isbn: str | None = Field(default=None, max_length=13, unique=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
