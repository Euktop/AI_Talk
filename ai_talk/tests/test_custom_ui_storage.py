"""Тесты SQLite-хранилища CUSTOM UI."""
import pytest

from ai_talk.custom_ui.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "test.db")


def test_create_and_get_request(storage):
    req = storage.create_request("sys", "user")
    assert req.id
    assert req.system_prompt == "sys"
    assert req.user_prompt == "user"
    assert req.answer is None
    assert req.answered_at is None

    got = storage.get_request(req.id)
    assert got is not None
    assert got.id == req.id
    assert got.system_prompt == "sys"


def test_get_missing_request_returns_none(storage):
    assert storage.get_request("nonexistent") is None


def test_list_requests_preserves_order(storage):
    r1 = storage.create_request("first", "")
    r2 = storage.create_request("second", "")
    r3 = storage.create_request("third", "")
    ids = [r.id for r in storage.list_requests()]
    assert ids == [r1.id, r2.id, r3.id]


def test_answer_request_sets_answer_and_time(storage):
    req = storage.create_request("s", "u")
    assert storage.answer_request(req.id, "ответ")
    got = storage.get_request(req.id)
    assert got.answer == "ответ"
    assert got.answered_at is not None


def test_answer_empty_string_rejected(storage):
    req = storage.create_request("s", "u")
    assert not storage.answer_request(req.id, "")
    assert not storage.answer_request(req.id, "   ")
    assert storage.get_request(req.id).answer is None


def test_answer_twice_rejected(storage):
    req = storage.create_request("s", "u")
    assert storage.answer_request(req.id, "first")
    assert not storage.answer_request(req.id, "second")
    assert storage.get_request(req.id).answer == "first"


def test_delete_request(storage):
    req = storage.create_request("s", "u")
    assert storage.delete_request(req.id)
    assert storage.get_request(req.id) is None
    assert not storage.delete_request(req.id)


def test_count_requests(storage):
    assert storage.count_requests() == 0
    storage.create_request("a", "")
    storage.create_request("b", "")
    assert storage.count_requests() == 2


def test_register_unregister_client(storage):
    assert storage.count_clients() == 0
    storage.register_client("c1")
    assert storage.count_clients() == 1
    storage.register_client("c1")
    assert storage.count_clients() == 1
    storage.register_client("c2")
    assert storage.count_clients() == 2
    storage.unregister_client("c1")
    assert storage.count_clients() == 1
    storage.unregister_client("c2")
    assert storage.count_clients() == 0


def test_list_clients(storage):
    storage.register_client("c1")
    storage.register_client("c2")
    ids = sorted(c.id for c in storage.list_clients())
    assert ids == ["c1", "c2"]


def test_full_text_with_both(storage):
    req = storage.create_request("sys", "user")
    assert req.full_text() == "sys\n\nuser"


def test_full_text_only_user(storage):
    req = storage.create_request("", "user")
    assert req.full_text() == "user"


def test_full_text_only_system(storage):
    req = storage.create_request("sys", "")
    assert req.full_text() == "sys"


def test_preview_truncates(storage):
    long_text = "a" * 200
    req = storage.create_request(long_text, "")
    assert len(req.preview(80)) == 81
    assert req.preview(80).endswith("…")


def test_preview_collapses_newlines(storage):
    req = storage.create_request("line1\nline2", "")
    assert "\n" not in req.preview()
