# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

The repository has no application code yet. So far it holds only `requirements.txt` and `.gitignore`. Once source code, tests, or Alembic migrations exist, update this file with the real architecture and entry points.

## Stack (from requirements.txt)

- **FastAPI** (with `fastapi-cli`, `uvicorn`) for the HTTP API
- **SQLModel** / **SQLAlchemy 2.x** for models and the ORM; **Alembic** for migrations
- **pydantic-settings** + **python-dotenv** for configuration; `.env` is gitignored
- **pytest** + **httpx** for tests (FastAPI `TestClient`)
- **ruff** for linting and formatting
- SQLite is the likely local database, since `*.db` is gitignored

## Environment

- Windows. The virtualenv is at `.venv/` and runs Python 3.11.
- Activate it in PowerShell with `.venv\Scripts\Activate.ps1`, or in Git Bash with `source .venv/Scripts/activate`.
- Install dependencies with `pip install -r requirements.txt`. The file is a full `pip freeze`, so regenerate it with `pip freeze > requirements.txt` after adding packages.

## Commands

These assume the venv is active. Adjust the app path once the entry module exists.

```
fastapi dev <path/to/main.py>        # dev server with reload
pytest                               # all tests
pytest path/to/test_file.py::test_name   # single test
ruff check .                         # lint (ruff check --fix . to autofix)
ruff format .                        # format
alembic revision --autogenerate -m "msg"   # after `alembic init` has been run
alembic upgrade head
```

## プロジェクト概要
自分専用の読書記録REST API(学習用)。認証・フロントエンド・デプロイは扱わない。

## 技術スタック
FastAPI / SQLModel / SQLite(reading_log.db)/ Alembic / pytest / ruff / venv + pip

## よく使うコマンド(Windows・仮想環境は .venv。Git Bash で実行できる / 区切りで記載)
- 起動: .venv/Scripts/fastapi.exe dev app/main.py
- テスト: .venv/Scripts/python.exe -m pytest
- フォーマット: .venv/Scripts/ruff.exe format .
- マイグレーション作成: .venv/Scripts/alembic.exe revision --autogenerate -m "<内容>"
- マイグレーション適用: .venv/Scripts/alembic.exe upgrade head
- パッケージ追加後は requirements.txt を pip freeze で更新

## ディレクトリ構成
app/routers/(リソースごとに1ファイル)・app/models/・app/schemas/
tests/・migrations/・mcp_server/

## 規約
- エラーは {"error": {"code": "BOOK_NOT_FOUND", "message": "..."}} 形式に統一
- ISBN は任意。入力された場合は一意
- 読書記録は1冊につき1つ
- 一覧は limit / offset で簡易ページネーション
