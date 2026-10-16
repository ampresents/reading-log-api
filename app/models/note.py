from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from app.models.book import utc_now
from app.models.tag import NoteTag, Tag


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: int | None = Field(default=None, primary_key=True)
    # SQLite は外部キー制約を既定で強制しないため、本の削除時はルーター側でもメモを消す
    book_id: int = Field(foreign_key="books.id", ondelete="CASCADE", index=True)
    content: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)

    tags: list[Tag] = Relationship(link_model=NoteTag)
