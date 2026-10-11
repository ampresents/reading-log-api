from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlmodel import Session, select

from app.database import get_session
from app.errors import AppError
from app.models import Book
from app.models.book import utc_now
from app.schemas.book import BookCreate, BookRead, BookUpdate

router = APIRouter(prefix="/books", tags=["books"])

SessionDep = Annotated[Session, Depends(get_session)]


def get_book_or_404(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            "BOOK_NOT_FOUND",
            f"Book {book_id} not found",
        )
    return book


def ensure_isbn_available(
    session: Session, isbn: str, exclude_id: int | None = None
) -> None:
    statement = select(Book).where(Book.isbn == isbn)
    if exclude_id is not None:
        statement = statement.where(Book.id != exclude_id)
    if session.exec(statement).first() is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "ISBN_ALREADY_EXISTS",
            f"Book with ISBN {isbn} already exists",
        )


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def create_book(payload: BookCreate, session: SessionDep) -> Book:
    if payload.isbn is not None:
        ensure_isbn_available(session, payload.isbn)

    book = Book.model_validate(payload)
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.get("", response_model=list[BookRead])
def list_books(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    order: Annotated[Literal["asc", "desc"] | None, Query()] = None,
) -> list[Book]:
    # order 未指定なら id 順。指定時は書名順で、同じ書名どうしは id 順に並べる
    if order is None:
        order_by = [Book.id]
    elif order == "asc":
        order_by = [Book.title.asc(), Book.id]
    else:
        order_by = [Book.title.desc(), Book.id]
    statement = select(Book).order_by(*order_by).offset(offset).limit(limit)
    return list(session.exec(statement).all())


@router.get("/{book_id}", response_model=BookRead)
def get_book(book_id: int, session: SessionDep) -> Book:
    return get_book_or_404(session, book_id)


@router.patch("/{book_id}", response_model=BookRead)
def update_book(book_id: int, payload: BookUpdate, session: SessionDep) -> Book:
    book = get_book_or_404(session, book_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return book

    if changes.get("isbn") is not None:
        ensure_isbn_available(session, changes["isbn"], exclude_id=book_id)

    book.sqlmodel_update(changes)
    book.updated_at = utc_now()
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, session: SessionDep) -> Response:
    book = get_book_or_404(session, book_id)
    session.delete(book)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
