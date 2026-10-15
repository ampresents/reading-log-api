---
name: add-endpoint
description: 読書記録APIに新しいエンドポイントを追加するときに使う。
  モデル・マイグレーション・ルーター・スキーマ・テストを規約どおりに作成する。
---

# エンドポイント追加の手順
1. 新しいテーブルが必要なら app/models/ に追加し、
   .venv/Scripts/alembic.exe revision --autogenerate で新しいリビジョンを作って適用する
2. app/schemas/ にリクエスト・レスポンスのスキーマを追加する
3. app/routers/<リソース名>.py にエンドポイントを追加する
   - エラーは {"error": {"code": "...", "message": "..."}} 形式
   - code は大文字スネークケース(例: BOOK_NOT_FOUND)
4. templates/test_template.py を参考に、正常系と異常系のテストを書く
5. .venv/Scripts/python.exe -m pytest で全テストが通ることを確認する
