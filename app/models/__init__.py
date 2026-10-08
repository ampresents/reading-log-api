# Alembic の autogenerate が全テーブルを検出できるよう、モデルはここで import する
from app.models.book import Book

__all__ = ["Book"]
