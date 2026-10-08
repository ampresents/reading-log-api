import os
from collections.abc import Iterator

from sqlmodel import Session, create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///reading_log.db")

# SQLite は既定で作成スレッド以外からの接続利用を禁止するため、FastAPI のスレッドプールで使えるよう解除する
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)


def get_session() -> Iterator[Session]:
    """FastAPI の Depends で使うセッション。リクエストごとに開いて閉じる。"""
    with Session(engine) as session:
        yield session
