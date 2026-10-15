from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

from app.schemas.book import strip_text

Content = Annotated[
    str, BeforeValidator(strip_text), Field(min_length=1, max_length=2000)
]


class NoteCreate(BaseModel):
    content: Content


class NoteRead(BaseModel):
    id: int
    book_id: int
    content: str
    created_at: datetime
