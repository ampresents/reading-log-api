from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field

from app.schemas.book import strip_text

MAX_TAGS_PER_NOTE = 10

Content = Annotated[
    str, BeforeValidator(strip_text), Field(min_length=1, max_length=2000)
]
TagName = Annotated[
    str, BeforeValidator(strip_text), Field(min_length=1, max_length=50)
]


def dedupe_tags(names: list[str]) -> list[str]:
    """重複指定は1つにまとめ(最初に現れた順を保つ)、まとめた後の個数で上限を判定する。"""
    unique = list(dict.fromkeys(names))
    if len(unique) > MAX_TAGS_PER_NOTE:
        raise ValueError(f"A note can have at most {MAX_TAGS_PER_NOTE} tags")
    return unique


Tags = Annotated[list[TagName], AfterValidator(dedupe_tags)]


class NoteCreate(BaseModel):
    content: Content
    tags: Tags = []


class NoteRead(BaseModel):
    id: int
    book_id: int
    content: str
    # タグ名の昇順
    tags: list[str]
    created_at: datetime
