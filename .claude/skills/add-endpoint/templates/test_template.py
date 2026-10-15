"""エンドポイントのテスト雛形(tests/test_books.py をもとにしている)。

使い方:
1. tests/test_<リソース名>.py にコピーする
2. 次の名前を置き換える
   - items / /items      → リソースのパス(例: reading-logs)
   - Item / item         → リソース名(例: ReadingLog / reading_log)
   - ITEM_NOT_FOUND      → ルーターで返すエラーコード
   - create_item の payload → 必須項目だけを埋めた正常な入力
3. 不要なクラス(使わない HTTP メソッド)は削除する

方針:
- client フィクスチャ(tests/conftest.py)はテストごとに空のインメモリ DB を使う
- 前提データは POST 経由で作る(DB を直接いじらない)
- エラーは {"error": {"code": ..., "message": ...}} 形式なので code を検証する
- 入力バリデーションの失敗は 422 / VALIDATION_ERROR
- 複数の不正入力は cases をループし、assert に入力値を添えてどれが落ちたか分かるようにする
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from httpx import Response

import app.routers.items  # TODO: 対象のルーターモジュール(utc_now を差し替える場合のみ必要)

PATH = "/items"


def create_item(client: TestClient, **overrides: object) -> dict:
    payload = {"name": "サンプル", **overrides}  # TODO: 必須項目を埋める
    response = client.post(PATH, json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def assert_item_not_found(response: Response) -> None:
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


def assert_validation_error(response: Response, case: object = None) -> None:
    assert response.status_code == 422, case
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"]


class TestCreateItem:
    def test_creates_item(self, client: TestClient) -> None:
        response = client.post(PATH, json={"name": "サンプル"})

        assert response.status_code == 201
        body = response.json()
        assert body["id"] >= 1
        assert body["name"] == "サンプル"
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_strips_strings(self, client: TestClient) -> None:
        assert create_item(client, name="  サンプル ")["name"] == "サンプル"

    def test_duplicate_returns_409(self, client: TestClient) -> None:
        # 一意制約がある項目(ISBN、1冊につき1つの読書記録など)があれば書く
        create_item(client)

        response = client.post(PATH, json={"name": "サンプル"})

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ITEM_ALREADY_EXISTS"

    def test_invalid_payload_returns_validation_error(self, client: TestClient) -> None:
        cases = [
            {},  # 必須項目なし
            {"name": "   "},  # 空白のみ
            {"name": "x" * 201},  # 最大長超過
        ]
        for payload in cases:
            assert_validation_error(client.post(PATH, json=payload), payload)


class TestListItems:
    def test_empty(self, client: TestClient) -> None:
        response = client.get(PATH)

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_items_in_id_order(self, client: TestClient) -> None:
        ids = [create_item(client, name=f"項目{i}")["id"] for i in range(3)]

        items = client.get(PATH).json()

        assert [i["id"] for i in items] == ids

    def test_pagination(self, client: TestClient) -> None:
        ids = [create_item(client, name=f"項目{i}")["id"] for i in range(5)]

        items = client.get(PATH, params={"limit": 2, "offset": 1}).json()

        assert [i["id"] for i in items] == ids[1:3]

    def test_default_limit_is_20(self, client: TestClient) -> None:
        for i in range(25):
            create_item(client, name=f"項目{i}")

        assert len(client.get(PATH).json()) == 20

    def test_invalid_pagination_returns_validation_error(
        self, client: TestClient
    ) -> None:
        for params in [{"limit": 0}, {"limit": 101}, {"offset": -1}]:
            assert_validation_error(client.get(PATH, params=params), params)


class TestGetItem:
    def test_returns_item(self, client: TestClient) -> None:
        item = create_item(client)

        response = client.get(f"{PATH}/{item['id']}")

        assert response.status_code == 200
        assert response.json() == item

    def test_not_found(self, client: TestClient) -> None:
        assert_item_not_found(client.get(f"{PATH}/999"))

    def test_non_integer_id_returns_validation_error(self, client: TestClient) -> None:
        assert_validation_error(client.get(f"{PATH}/abc"))


class TestUpdateItem:
    def test_updates_only_given_fields(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        item = create_item(client)
        # Windows では時計の分解能が粗く作成直後の現在時刻が同じ値になり得るため、更新時刻を固定する
        updated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
        monkeypatch.setattr(app.routers.items, "utc_now", lambda: updated_at)

        response = client.patch(f"{PATH}/{item['id']}", json={"name": " 新しい名前 "})

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "新しい名前"
        assert body["created_at"] == item["created_at"]
        assert body["updated_at"] == "2099-01-01T00:00:00Z"
        assert client.get(f"{PATH}/{item['id']}").json() == body

    def test_empty_body_changes_nothing(self, client: TestClient) -> None:
        item = create_item(client)

        response = client.patch(f"{PATH}/{item['id']}", json={})

        assert response.status_code == 200
        assert response.json() == item

    def test_invalid_payload_returns_validation_error(self, client: TestClient) -> None:
        item = create_item(client)
        cases = [
            {"name": None},  # 必須項目は null にできない
            {"name": "  "},
            {"name": "x" * 201},
        ]
        for payload in cases:
            response = client.patch(f"{PATH}/{item['id']}", json=payload)
            assert_validation_error(response, payload)
        # 失敗した更新でデータが変わっていないこと
        assert client.get(f"{PATH}/{item['id']}").json() == item

    def test_not_found(self, client: TestClient) -> None:
        assert_item_not_found(client.patch(f"{PATH}/999", json={"name": "x"}))


class TestDeleteItem:
    def test_deletes_item(self, client: TestClient) -> None:
        item = create_item(client, name="消す")
        other = create_item(client, name="残す")

        response = client.delete(f"{PATH}/{item['id']}")

        assert response.status_code == 204
        assert response.content == b""
        assert_item_not_found(client.get(f"{PATH}/{item['id']}"))
        assert client.get(PATH).json() == [other]

    def test_not_found(self, client: TestClient) -> None:
        assert_item_not_found(client.delete(f"{PATH}/999"))
