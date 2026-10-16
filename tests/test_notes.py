from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, select

from app.models import Note, NoteTag, Tag


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


class TestNoteTags:
    def test_tags_default_to_empty(self, client: TestClient) -> None:
        book = create_book(client)

        assert create_note(client, book["id"])["tags"] == []

    def test_creates_note_with_tags_sorted_by_name(self, client: TestClient) -> None:
        book = create_book(client)

        note = create_note(client, book["id"], tags=["名言", "1章", "伏線"])

        assert note["tags"] == sorted(["名言", "1章", "伏線"])
        assert client.get(notes_path(book["id"])).json() == [note]

    def test_strips_and_dedupes_tags(self, client: TestClient) -> None:
        book = create_book(client)

        note = create_note(client, book["id"], tags=[" 名言 ", "名言", "伏線"])

        assert note["tags"] == sorted(["名言", "伏線"])

    def test_tags_are_case_sensitive(self, client: TestClient) -> None:
        book = create_book(client)

        assert create_note(client, book["id"], tags=["SF", "sf"])["tags"] == [
            "SF",
            "sf",
        ]

    def test_same_tag_is_shared_between_notes(
        self, client: TestClient, session: Session
    ) -> None:
        book = create_book(client)
        create_note(client, book["id"], tags=["名言"])
        create_note(client, book["id"], tags=["名言", "伏線"])

        names = [tag.name for tag in session.exec(select(Tag)).all()]
        assert sorted(names) == sorted(["名言", "伏線"])
        # 既存タグと新規タグが混ざっても、それぞれ正しく紐づくこと
        notes = client.get(notes_path(book["id"]), params={"tag": "伏線"}).json()
        assert [n["tags"] for n in notes] == [sorted(["名言", "伏線"])]

    def test_boundary_values_are_accepted(self, client: TestClient) -> None:
        book = create_book(client)
        long_name = "x" * 50
        tags = [f"tag{i}" for i in range(9)] + [long_name]

        assert len(create_note(client, book["id"], tags=tags)["tags"]) == 10
        notes = client.get(notes_path(book["id"]), params={"tag": long_name}).json()
        assert len(notes) == 1

    def test_max_tags_is_counted_after_dedupe(self, client: TestClient) -> None:
        book = create_book(client)
        tags = [f"tag{i}" for i in range(10)] + ["tag0"]

        assert len(create_note(client, book["id"], tags=tags)["tags"]) == 10

    def test_invalid_tags_return_validation_error(
        self, client: TestClient, session: Session
    ) -> None:
        book = create_book(client)
        cases = [
            {"tags": None},
            {"tags": "名言"},  # 配列でない
            {"tags": [""]},
            {"tags": ["   "]},  # 空白のみ
            {"tags": ["名言", ""]},  # 正しいタグと混在
            {"tags": [None]},
            {"tags": [1]},
            {"tags": ["x" * 51]},  # 最大長超過
            {"tags": [f"tag{i}" for i in range(11)]},  # 個数超過
        ]
        for case in cases:
            response = client.post(
                notes_path(book["id"]), json={"content": "x", **case}
            )
            assert_validation_error(response, case)
        assert client.get(notes_path(book["id"])).json() == []
        assert session.exec(select(Tag)).all() == []

    def test_filters_by_tag(self, client: TestClient) -> None:
        book = create_book(client)
        first = create_note(client, book["id"], tags=["名言", "伏線"])
        create_note(client, book["id"], tags=["伏線"])
        create_note(client, book["id"])
        third = create_note(client, book["id"], tags=["名言"])

        notes = client.get(notes_path(book["id"]), params={"tag": "名言"}).json()

        # 絞り込んでもタグは全件返す
        assert notes == [first, third]

    def test_filter_strips_tag(self, client: TestClient) -> None:
        book = create_book(client)
        note = create_note(client, book["id"], tags=["名言"])

        notes = client.get(notes_path(book["id"]), params={"tag": " 名言 "}).json()

        assert notes == [note]

    def test_filter_is_exact_and_case_sensitive(self, client: TestClient) -> None:
        book = create_book(client)
        create_note(client, book["id"], tags=["SF小説"])
        upper = create_note(client, book["id"], tags=["SF"])

        for tag, expected in [("SF", [upper]), ("sf", []), ("小説", [])]:
            notes = client.get(notes_path(book["id"]), params={"tag": tag}).json()
            assert notes == expected, tag

    def test_blank_tag_filter_is_ignored(self, client: TestClient) -> None:
        book = create_book(client)
        notes = [create_note(client, book["id"]), create_note(client, book["id"])]

        for tag in ["", "   "]:
            response = client.get(notes_path(book["id"]), params={"tag": tag})
            assert response.json() == notes, repr(tag)

    def test_filter_returns_only_notes_of_the_book(self, client: TestClient) -> None:
        book = create_book(client)
        other = create_book(client, title="こころ")
        note = create_note(client, book["id"], tags=["名言"])
        create_note(client, other["id"], tags=["名言"])

        notes = client.get(notes_path(book["id"]), params={"tag": "名言"}).json()

        assert notes == [note]

    def test_filter_with_pagination(self, client: TestClient) -> None:
        book = create_book(client)
        ids = []
        for i in range(5):
            create_note(client, book["id"])  # タグなしは対象外
            ids.append(create_note(client, book["id"], tags=["名言"])["id"])

        notes = client.get(
            notes_path(book["id"]), params={"tag": "名言", "limit": 2, "offset": 1}
        ).json()

        assert [n["id"] for n in notes] == ids[1:3]

    def test_too_long_tag_filter_returns_validation_error(
        self, client: TestClient
    ) -> None:
        book = create_book(client)

        response = client.get(notes_path(book["id"]), params={"tag": "x" * 51})

        assert_validation_error(response)


def test_deleting_book_deletes_its_notes(client: TestClient, session: Session) -> None:
    book = create_book(client)
    other = create_book(client, title="こころ")
    create_note(client, book["id"])
    other_note = create_note(client, other["id"])

    assert client.delete(f"/books/{book['id']}").status_code == 204

    # 削除した本のメモだけが DB から消え、他の本のメモは残ること
    notes = session.exec(select(Note)).all()
    assert [note.id for note in notes] == [other_note["id"]]


def test_deleting_book_deletes_its_note_tags(
    client: TestClient, session: Session
) -> None:
    book = create_book(client)
    other = create_book(client, title="こころ")
    create_note(client, book["id"], tags=["名言", "伏線"])
    other_note = create_note(client, other["id"], tags=["名言"])

    assert client.delete(f"/books/{book['id']}").status_code == 204

    # 削除した本のメモのタグ付けだけが消え、タグ自体は残ること
    links = session.exec(select(NoteTag)).all()
    assert [link.note_id for link in links] == [other_note["id"]]
    names = [tag.name for tag in session.exec(select(Tag)).all()]
    assert sorted(names) == sorted(["名言", "伏線"])
