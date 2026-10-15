from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlmodel import select

from app.models import Note
from app.routers.books import SessionDep, get_book_or_404
from app.schemas.note import NoteCreate, NoteRead

router = APIRouter(prefix="/books/{book_id}/notes", tags=["notes"])


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(book_id: int, payload: NoteCreate, session: SessionDep) -> Note:
    get_book_or_404(session, book_id)

    note = Note(book_id=book_id, content=payload.content)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.get("", response_model=list[NoteRead])
def list_notes(
    book_id: int,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Note]:
    get_book_or_404(session, book_id)

    statement = (
        select(Note)
        .where(Note.book_id == book_id)
        .order_by(Note.id)
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())
