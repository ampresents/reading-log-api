# Alembic の autogenerate が全テーブルを検出できるよう、モデルはここで import する
from app.models.book import Book
from app.models.note import Note

__all__ = ["Book", "Note"]
