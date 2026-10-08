from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from httpx import Response

import app.routers.books


def create_book(client: TestClient, **overrides: object) -> dict:
    payload = {"title": "吾輩は猫である", "author": "夏目漱石", **overrides}
    response = client.post("/books", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


class TestCreateBook:
    def test_creates_book(self, client: TestClient) -> None:
        response = client.post(
            "/books",
            json={"title": "こころ", "author": "夏目漱石", "isbn": "978-4-10-101013-7"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["id"] >= 1
        assert body["title"] == "こころ"
        assert body["author"] == "夏目漱石"
        assert body["isbn"] == "9784101010137"  # ハイフンは除去して保存
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_isbn_is_optional(self, client: TestClient) -> None:
        assert create_book(client)["isbn"] is None
        assert create_book(client, isbn="")["isbn"] is None

    def test_books_without_isbn_can_coexist(self, client: TestClient) -> None:
        create_book(client)
        create_book(client)

        assert len(client.get("/books").json()) == 2

    def test_accepts_isbn10_with_x(self, client: TestClient) -> None:
        assert create_book(client, isbn="4-00-310101-x")["isbn"] == "400310101X"

    def test_duplicate_isbn_returns_409(self, client: TestClient) -> None:
        create_book(client, isbn="9784101010137")

        # 表記が違っても正規化後に同じなら重複とみなす
        response = client.post(
            "/books",
            json={"title": "別の本", "author": "誰か", "isbn": "978-4101010137"},
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ISBN_ALREADY_EXISTS"

    def test_strips_title_and_author(self, client: TestClient) -> None:
        book = create_book(client, title="  こころ ", author=" 夏目漱石  ")

        assert book["title"] == "こころ"
        assert book["author"] == "夏目漱石"

    def test_invalid_payload_returns_validation_error(self, client: TestClient) -> None:
        cases = [
            {"author": "夏目漱石"},  # title なし
            {"title": "   ", "author": "夏目漱石"},  # 空白のみ
            {"title": "x" * 201, "author": "夏目漱石"},
            {"title": "こころ", "author": "夏目漱石", "isbn": "12345"},
        ]
        for payload in cases:
            response = client.post("/books", json=payload)

            assert response.status_code == 422, payload
            error = response.json()["error"]
            assert error["code"] == "VALIDATION_ERROR"
            assert error["message"]


class TestListBooks:
    def test_empty(self, client: TestClient) -> None:
        response = client.get("/books")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_books_in_id_order(self, client: TestClient) -> None:
        ids = [create_book(client, title=f"本{i}")["id"] for i in range(3)]

        books = client.get("/books").json()

        assert [b["id"] for b in books] == ids

    def test_pagination(self, client: TestClient) -> None:
        ids = [create_book(client, title=f"本{i}")["id"] for i in range(5)]

        books = client.get("/books", params={"limit": 2, "offset": 1}).json()

        assert [b["id"] for b in books] == ids[1:3]

    def test_default_limit_is_20(self, client: TestClient) -> None:
        for i in range(25):
            create_book(client, title=f"本{i}")

        assert len(client.get("/books").json()) == 20

    def test_invalid_pagination_returns_validation_error(
        self, client: TestClient
    ) -> None:
        for params in [{"limit": 0}, {"limit": 101}, {"offset": -1}]:
            response = client.get("/books", params=params)

            assert response.status_code == 422, params
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def assert_book_not_found(response: Response) -> None:
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOK_NOT_FOUND"


class TestGetBook:
    def test_returns_book(self, client: TestClient) -> None:
        book = create_book(client, isbn="9784101010137")

        response = client.get(f"/books/{book['id']}")

        assert response.status_code == 200
        assert response.json() == book

    def test_not_found(self, client: TestClient) -> None:
        assert_book_not_found(client.get("/books/999"))

    def test_non_integer_id_returns_validation_error(self, client: TestClient) -> None:
        response = client.get("/books/abc")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class TestUpdateBook:
    def test_updates_only_given_fields(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        book = create_book(client, isbn="9784101010137")
        # Windows では時計の分解能が粗く作成直後の現在時刻が同じ値になり得るため、更新時刻を固定する
        updated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
        monkeypatch.setattr(app.routers.books, "utc_now", lambda: updated_at)

        response = client.patch(f"/books/{book['id']}", json={"title": " こころ "})

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "こころ"
        assert body["author"] == book["author"]
        assert body["isbn"] == book["isbn"]
        assert body["created_at"] == book["created_at"]
        assert body["updated_at"] == "2099-01-01T00:00:00Z"
        assert client.get(f"/books/{book['id']}").json() == body

    def test_sets_and_clears_isbn(self, client: TestClient) -> None:
        book = create_book(client)

        set_response = client.patch(
            f"/books/{book['id']}", json={"isbn": "978-4-10-101013-7"}
        )
        assert set_response.json()["isbn"] == "9784101010137"

        for cleared in [None, ""]:
            client.patch(f"/books/{book['id']}", json={"isbn": "9784101010137"})
            response = client.patch(f"/books/{book['id']}", json={"isbn": cleared})

            assert response.status_code == 200
            assert response.json()["isbn"] is None

    def test_empty_body_changes_nothing(self, client: TestClient) -> None:
        book = create_book(client)

        response = client.patch(f"/books/{book['id']}", json={})

        assert response.status_code == 200
        assert response.json() == book

    def test_keeping_own_isbn_is_not_a_conflict(self, client: TestClient) -> None:
        book = create_book(client, isbn="9784101010137")

        response = client.patch(
            f"/books/{book['id']}", json={"title": "新", "isbn": "9784101010137"}
        )

        assert response.status_code == 200

    def test_isbn_of_another_book_returns_409(self, client: TestClient) -> None:
        create_book(client, isbn="9784101010137")
        book = create_book(client)

        response = client.patch(f"/books/{book['id']}", json={"isbn": "9784101010137"})

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ISBN_ALREADY_EXISTS"
        assert client.get(f"/books/{book['id']}").json()["isbn"] is None

    def test_invalid_payload_returns_validation_error(self, client: TestClient) -> None:
        book = create_book(client)
        cases = [
            {"title": None},
            {"author": None},
            {"title": "  "},
            {"author": "x" * 101},
            {"isbn": "12345"},
        ]
        for payload in cases:
            response = client.patch(f"/books/{book['id']}", json=payload)

            assert response.status_code == 422, payload
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert client.get(f"/books/{book['id']}").json() == book

    def test_not_found(self, client: TestClient) -> None:
        assert_book_not_found(client.patch("/books/999", json={"title": "x"}))


class TestDeleteBook:
    def test_deletes_book(self, client: TestClient) -> None:
        book = create_book(client)
        other = create_book(client)

        response = client.delete(f"/books/{book['id']}")

        assert response.status_code == 204
        assert response.content == b""
        assert_book_not_found(client.get(f"/books/{book['id']}"))
        assert client.get("/books").json() == [other]

    def test_isbn_can_be_reused_after_delete(self, client: TestClient) -> None:
        book = create_book(client, isbn="9784101010137")
        client.delete(f"/books/{book['id']}")

        create_book(client, isbn="9784101010137")

    def test_not_found(self, client: TestClient) -> None:
        assert_book_not_found(client.delete("/books/999"))


def test_unknown_path_uses_error_format(client: TestClient) -> None:
    response = client.get("/no-such-path")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}
