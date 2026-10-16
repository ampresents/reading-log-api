from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models import Note, Tag
from app.routers.books import SessionDep, get_book_or_404
from app.schemas.note import NoteCreate, NoteRead

router = APIRouter(prefix="/books/{book_id}/notes", tags=["notes"])


def get_or_create_tags(session: Session, names: list[str]) -> list[Tag]:
    if not names:
        return []
    existing = session.exec(select(Tag).where(Tag.name.in_(names))).all()
    by_name = {tag.name: tag for tag in existing}
    return [by_name.get(name) or Tag(name=name) for name in names]


def to_note_read(note: Note) -> NoteRead:
    # Note を直接返すと relationship の tags がレスポンスに含まれないため、明示的に組み立てる
    return NoteRead(
        id=note.id,
        book_id=note.book_id,
        content=note.content,
        tags=sorted(tag.name for tag in note.tags),
        created_at=note.created_at,
    )


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(book_id: int, payload: NoteCreate, session: SessionDep) -> NoteRead:
    get_book_or_404(session, book_id)

    note = Note(
        book_id=book_id,
        content=payload.content,
        tags=get_or_create_tags(session, payload.tags),
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    return to_note_read(note)


@router.get("", response_model=list[NoteRead])
def list_notes(
    book_id: int,
    session: SessionDep,
    tag: Annotated[str | None, Query(max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NoteRead]:
    get_book_or_404(session, book_id)

    statement = (
        select(Note).where(Note.book_id == book_id).options(selectinload(Note.tags))
    )
    # 指定したタグ(完全一致・大文字小文字を区別)が付いたメモだけに絞る。空白だけなら未指定扱い
    tag = tag.strip() if tag else None
    if tag:
        statement = statement.where(Note.tags.any(Tag.name == tag))
    statement = statement.order_by(Note.id).offset(offset).limit(limit)
    return [to_note_read(note) for note in session.exec(statement).all()]
