from sqlmodel import Field, SQLModel


class NoteTag(SQLModel, table=True):
    """感想メモとタグの中間テーブル(多対多)。"""

    __tablename__ = "note_tags"

    note_id: int = Field(foreign_key="notes.id", ondelete="CASCADE", primary_key=True)
    tag_id: int = Field(foreign_key="tags.id", ondelete="CASCADE", primary_key=True)


class Tag(SQLModel, table=True):
    __tablename__ = "tags"

    id: int | None = Field(default=None, primary_key=True)
    # 大文字小文字は区別する。同名タグは1行にまとめ、メモ間で共有する
    name: str = Field(max_length=50, unique=True)
