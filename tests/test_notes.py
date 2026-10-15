from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, select

from app.models import Note


def create_book(client: TestClient, **overrides: object) -> dict:
    payload = {"title": "吾輩は猫である", "author": "夏目漱石", **overrides}
    response = client.post("/books", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def notes_path(book_id: int) -> str:
    return f"/books/{book_id}/notes"


def create_note(client: TestClient, book_id: int, **overrides: object) -> dict:
    payload = {"content": "面白かった", **overrides}
    response = client.post(notes_path(book_id), json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def assert_book_not_found(response: Response) -> None:
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOK_NOT_FOUND"


def assert_validation_error(response: Response, case: object = None) -> None:
    assert response.status_code == 422, case
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"]


class TestCreateNote:
    def test_creates_note(self, client: TestClient) -> None:
        book = create_book(client)

        response = client.post(notes_path(book["id"]), json={"content": "面白かった"})

        assert response.status_code == 201
        body = response.json()
        assert body["id"] >= 1
        assert body["book_id"] == book["id"]
        assert body["content"] == "面白かった"
        assert body["created_at"] is not None

    def test_book_can_have_multiple_notes(self, client: TestClient) -> None:
        book = create_book(client)

        first = create_note(client, book["id"], content="1章")
        second = create_note(client, book["id"], content="2章")

        assert first["id"] != second["id"]

    def test_strips_content(self, client: TestClient) -> None:
        book = create_book(client)

        assert create_note(client, book["id"], content="  メモ \n")["content"] == "メモ"

    def test_invalid_payload_returns_validation_error(self, client: TestClient) -> None:
        book = create_book(client)
        cases = [
            {},  # 必須項目なし
            {"content": None},
            {"content": "   "},  # 空白のみ
            {"content": "x" * 2001},  # 最大長超過
        ]
        for payload in cases:
            response = client.post(notes_path(book["id"]), json=payload)
            assert_validation_error(response, payload)
        assert client.get(notes_path(book["id"])).json() == []

    def test_book_not_found(self, client: TestClient) -> None:
        assert_book_not_found(client.post(notes_path(999), json={"content": "x"}))

    def test_non_integer_book_id_returns_validation_error(
        self, client: TestClient
    ) -> None:
        assert_validation_error(client.post("/books/abc/notes", json={"content": "x"}))


class TestListNotes:
    def test_empty(self, client: TestClient) -> None:
        book = create_book(client)

        response = client.get(notes_path(book["id"]))

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_notes_in_id_order(self, client: TestClient) -> None:
        book = create_book(client)
        notes = [create_note(client, book["id"], content=f"メモ{i}") for i in range(3)]

        assert client.get(notes_path(book["id"])).json() == notes

    def test_returns_only_notes_of_the_book(self, client: TestClient) -> None:
        book = create_book(client)
        other = create_book(client, title="こころ")
        note = create_note(client, book["id"])
        create_note(client, other["id"])

        assert client.get(notes_path(book["id"])).json() == [note]

    def test_pagination(self, client: TestClient) -> None:
        book = create_book(client)
        ids = [create_note(client, book["id"])["id"] for _ in range(5)]

        notes = client.get(
            notes_path(book["id"]), params={"limit": 2, "offset": 1}
        ).json()

        assert [n["id"] for n in notes] == ids[1:3]

    def test_default_limit_is_20(self, client: TestClient) -> None:
        book = create_book(client)
        for _ in range(25):
            create_note(client, book["id"])

        assert len(client.get(notes_path(book["id"])).json()) == 20

    def test_invalid_pagination_returns_validation_error(
        self, client: TestClient
    ) -> None:
        book = create_book(client)
        for params in [{"limit": 0}, {"limit": 101}, {"offset": -1}]:
            response = client.get(notes_path(book["id"]), params=params)
            assert_validation_error(response, params)

    def test_book_not_found(self, client: TestClient) -> None:
        assert_book_not_found(client.get(notes_path(999)))


def test_deleting_book_deletes_its_notes(client: TestClient, session: Session) -> None:
    book = create_book(client)
    other = create_book(client, title="こころ")
    create_note(client, book["id"])
    other_note = create_note(client, other["id"])

    assert client.delete(f"/books/{book['id']}").status_code == 204

    # 削除した本のメモだけが DB から消え、他の本のメモは残ること
    notes = session.exec(select(Note)).all()
    assert [note.id for note in notes] == [other_note["id"]]
