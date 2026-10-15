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
        assert body["status"] == "unread"
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

    def test_sorts_by_title_asc(self, client: TestClient) -> None:
        for title in ["ぶ", "あ", "い"]:
            create_book(client, title=title)

        books = client.get("/books", params={"order": "asc"}).json()

        assert [b["title"] for b in books] == ["あ", "い", "ぶ"]

    def test_sorts_by_title_desc(self, client: TestClient) -> None:
        for title in ["ぶ", "あ", "い"]:
            create_book(client, title=title)

        books = client.get("/books", params={"order": "desc"}).json()

        assert [b["title"] for b in books] == ["ぶ", "い", "あ"]

    def test_same_title_is_ordered_by_id(self, client: TestClient) -> None:
        first = create_book(client, title="同じ")["id"]
        create_book(client, title="あ")
        second = create_book(client, title="同じ")["id"]

        for order in ["asc", "desc"]:
            books = client.get("/books", params={"order": order}).json()
            same = [b["id"] for b in books if b["title"] == "同じ"]

            assert same == [first, second], order

    def test_sort_with_pagination(self, client: TestClient) -> None:
        for title in ["え", "う", "あ", "お", "い"]:
            create_book(client, title=title)

        books = client.get(
            "/books", params={"order": "desc", "limit": 2, "offset": 1}
        ).json()

        assert [b["title"] for b in books] == ["え", "う"]

    def test_invalid_order_returns_validation_error(self, client: TestClient) -> None:
        for order in ["ASC", "title", ""]:
            response = client.get("/books", params={"order": order})

            assert response.status_code == 422, order
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class TestSearchBooks:
    def test_partial_match_by_title(self, client: TestClient) -> None:
        cat = create_book(client, title="吾輩は猫である")
        create_book(client, title="こころ")

        response = client.get("/books/search", params={"title": "猫"})

        assert response.status_code == 200
        assert response.json() == [cat]

    def test_partial_match_by_author(self, client: TestClient) -> None:
        soseki = create_book(client, title="こころ", author="夏目漱石")
        create_book(client, title="羅生門", author="芥川龍之介")

        books = client.get("/books/search", params={"author": "漱石"}).json()

        assert books == [soseki]

    def test_title_and_author_are_combined_with_and(self, client: TestClient) -> None:
        target = create_book(client, title="猫の本", author="夏目漱石")
        create_book(client, title="猫の本2", author="芥川龍之介")
        create_book(client, title="こころ", author="夏目漱石")

        books = client.get(
            "/books/search", params={"title": "猫", "author": "漱石"}
        ).json()

        assert books == [target]

    def test_case_insensitive(self, client: TestClient) -> None:
        book = create_book(client, title="Python Crash Course", author="Eric Matthes")

        for params in [{"title": "python"}, {"author": "ERIC"}]:
            assert client.get("/books/search", params=params).json() == [book], params

    def test_wildcard_characters_are_literal(self, client: TestClient) -> None:
        percent = create_book(client, title="100%の本")
        create_book(client, title="100円の本")

        for q in ["%", "_"]:
            books = client.get("/books/search", params={"title": q}).json()
            assert books == ([percent] if q == "%" else []), q

    def test_strips_whitespace(self, client: TestClient) -> None:
        book = create_book(client, title="こころ")

        books = client.get("/books/search", params={"title": " ここ "}).json()

        assert books == [book]

    def test_no_match_returns_empty_list(self, client: TestClient) -> None:
        create_book(client)

        response = client.get("/books/search", params={"title": "存在しない"})

        assert response.status_code == 200
        assert response.json() == []

    def test_pagination_in_id_order(self, client: TestClient) -> None:
        ids = [create_book(client, title=f"猫{i}")["id"] for i in range(5)]
        create_book(client, title="犬")

        books = client.get(
            "/books/search", params={"title": "猫", "limit": 2, "offset": 1}
        ).json()

        assert [b["id"] for b in books] == ids[1:3]

    def test_invalid_params_return_validation_error(self, client: TestClient) -> None:
        cases = [
            {},  # 検索条件なし
            {"title": "", "author": ""},
            {"title": "   "},  # 空白のみ
            {"title": "x" * 201},
            {"author": "x" * 101},
            {"title": "猫", "limit": 0},
            {"title": "猫", "limit": 101},
            {"title": "猫", "offset": -1},
        ]
        for params in cases:
            response = client.get("/books/search", params=params)

            assert response.status_code == 422, params
            error = response.json()["error"]
            assert error["code"] == "VALIDATION_ERROR", params
            assert error["message"], params


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


class TestUpdateBookStatus:
    def test_updates_status(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        book = create_book(client)
        # Windows では時計の分解能が粗く作成直後の現在時刻が同じ値になり得るため、更新時刻を固定する
        updated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
        monkeypatch.setattr(app.routers.books, "utc_now", lambda: updated_at)

        response = client.put(f"/books/{book['id']}/status", json={"status": "reading"})

        assert response.status_code == 200
        body = response.json()
        assert body == {
            **book,
            "status": "reading",
            "updated_at": "2099-01-01T00:00:00Z",
        }
        assert client.get(f"/books/{book['id']}").json() == body

    def test_accepts_all_statuses(self, client: TestClient) -> None:
        book = create_book(client)

        for status in ["reading", "finished", "unread"]:
            response = client.put(
                f"/books/{book['id']}/status", json={"status": status}
            )

            assert response.status_code == 200, status
            assert response.json()["status"] == status

    def test_same_status_changes_nothing(self, client: TestClient) -> None:
        book = create_book(client)

        response = client.put(f"/books/{book['id']}/status", json={"status": "unread"})

        assert response.status_code == 200
        assert response.json() == book
        assert client.get(f"/books/{book['id']}").json() == book

    def test_ignores_other_fields(self, client: TestClient) -> None:
        book = create_book(client, isbn="9784101010137")

        response = client.put(
            f"/books/{book['id']}/status",
            json={"status": "reading", "title": "x", "author": "y", "isbn": None},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "reading"
        for field in ["title", "author", "isbn", "created_at"]:
            assert body[field] == book[field], field

    def test_patch_book_cannot_change_status(self, client: TestClient) -> None:
        book = create_book(client)

        response = client.patch(f"/books/{book['id']}", json={"status": "finished"})

        assert response.status_code == 200
        assert client.get(f"/books/{book['id']}").json()["status"] == "unread"

    def test_invalid_payload_returns_validation_error(self, client: TestClient) -> None:
        book = create_book(client)
        cases = [
            {},  # status なし
            {"status": None},
            {"status": ""},
            {"status": "READING"},
            {"status": "done"},
            {"status": " reading"},  # 前後の空白は取り除かない
            {"status": "reading "},
            {"status": 1},
            {"status": True},
            {"status": ["reading"]},
            {"status": {"value": "reading"}},
            [],  # オブジェクトでない
        ]
        for payload in cases:
            response = client.put(f"/books/{book['id']}/status", json=payload)

            assert response.status_code == 422, payload
            error = response.json()["error"]
            assert error["code"] == "VALIDATION_ERROR", payload
            assert error["message"], payload
        # 失敗した更新でデータが変わっていないこと
        assert client.get(f"/books/{book['id']}").json() == book

    def test_missing_or_broken_body_returns_validation_error(
        self, client: TestClient
    ) -> None:
        book = create_book(client)
        path = f"/books/{book['id']}/status"
        responses = [
            client.put(path),
            client.put(path, content="{", headers={"Content-Type": "application/json"}),
        ]
        for response in responses:
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_non_integer_book_id_returns_validation_error(
        self, client: TestClient
    ) -> None:
        response = client.put("/books/abc/status", json={"status": "reading"})

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_not_found(self, client: TestClient) -> None:
        assert_book_not_found(
            client.put("/books/999/status", json={"status": "reading"})
        )

    def test_deleted_book_not_found(self, client: TestClient) -> None:
        book = create_book(client)
        client.delete(f"/books/{book['id']}")

        assert_book_not_found(
            client.put(f"/books/{book['id']}/status", json={"status": "reading"})
        )


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
