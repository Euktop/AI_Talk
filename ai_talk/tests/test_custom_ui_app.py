"""Тесты HTTP API CUSTOM UI через Flask test_client."""
import pytest

from ai_talk.custom_ui.app import create_app
from ai_talk.custom_ui.storage import Storage


@pytest.fixture
def app(tmp_path):
    storage = Storage(tmp_path / "test.db")
    return create_app(storage)


@pytest.fixture
def client(app):
    return app.test_client()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_register_client(client):
    r = client.post("/api/clients/register", json={"client_id": "c1"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_register_client_missing_id(client):
    r = client.post("/api/clients/register", json={})
    assert r.status_code == 400


def test_unregister_client(client):
    client.post("/api/clients/register", json={"client_id": "c1"})
    r = client.post("/api/clients/unregister", json={"client_id": "c1"})
    assert r.status_code == 200


def test_create_and_list_requests(client):
    r = client.post(
        "/api/requests", json={"system_prompt": "sys", "user_prompt": "user"}
    )
    assert r.status_code == 200
    rid = r.get_json()["id"]
    assert rid

    r = client.get("/api/requests")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) == 1
    assert data[0]["id"] == rid
    assert "sys" in data[0]["preview"]
    assert data[0]["has_answer"] is False


def test_get_raw_returns_full_text(client):
    r = client.post(
        "/api/requests", json={"system_prompt": "S", "user_prompt": "U"}
    )
    rid = r.get_json()["id"]

    r = client.get("/api/requests/{0}/raw".format(rid))
    assert r.status_code == 200
    assert r.data.decode("utf-8") == "S\n\nU"


def test_get_raw_missing_returns_404(client):
    r = client.get("/api/requests/nonexistent/raw")
    assert r.status_code == 404


def test_answer_request(client):
    r = client.post("/api/requests", json={"system_prompt": "s", "user_prompt": "u"})
    rid = r.get_json()["id"]

    r = client.post(
        "/api/requests/{0}/answer".format(rid), json={"answer": "hello"}
    )
    assert r.status_code == 200


def test_answer_empty_rejected(client):
    r = client.post("/api/requests", json={"system_prompt": "s", "user_prompt": "u"})
    rid = r.get_json()["id"]

    r = client.post("/api/requests/{0}/answer".format(rid), json={"answer": ""})
    assert r.status_code == 400


def test_answer_whitespace_rejected(client):
    r = client.post("/api/requests", json={"system_prompt": "s", "user_prompt": "u"})
    rid = r.get_json()["id"]

    r = client.post(
        "/api/requests/{0}/answer".format(rid), json={"answer": "   \n  "}
    )
    assert r.status_code == 400


def test_answer_twice_returns_404(client):
    r = client.post("/api/requests", json={"system_prompt": "s", "user_prompt": "u"})
    rid = r.get_json()["id"]

    client.post("/api/requests/{0}/answer".format(rid), json={"answer": "first"})
    r = client.post(
        "/api/requests/{0}/answer".format(rid), json={"answer": "second"}
    )
    assert r.status_code == 404


def test_wait_returns_answer_when_already_answered(client):
    r = client.post("/api/requests", json={"system_prompt": "s", "user_prompt": "u"})
    rid = r.get_json()["id"]
    client.post("/api/requests/{0}/answer".format(rid), json={"answer": "hi"})

    r = client.get("/api/requests/{0}/wait?timeout=1".format(rid))
    assert r.status_code == 200
    body = r.get_json()
    assert body["id"] == rid
    assert body["answer"] == "hi"


def test_wait_times_out_when_unanswered(client):
    r = client.post("/api/requests", json={"system_prompt": "s", "user_prompt": "u"})
    rid = r.get_json()["id"]

    r = client.get("/api/requests/{0}/wait?timeout=0.3".format(rid))
    assert r.status_code == 504


def test_wait_missing_request_returns_404(client):
    r = client.get("/api/requests/nonexistent/wait?timeout=1")
    assert r.status_code == 404


def test_index_returns_html(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "<!doctype html>" in body
    assert "AI_Talk" in body
    assert "/static/app.js" in body


def test_static_app_js_served(client):
    r = client.get("/static/app.js")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "fetchRequests" in body
    assert "copyToClipboard" in body


def test_static_style_css_served(client):
    r = client.get("/static/style.css")
    assert r.status_code == 200
    css = r.data.decode("utf-8")
    assert ".row" in css
    assert ".modal" in css
    assert ".flash-ok" in css


def test_index_contains_modal(client):
    r = client.get("/")
    body = r.data.decode("utf-8")
    assert '<dialog id="modal"' in body
    assert 'id="modal-text"' in body
    assert 'id="modal-download"' in body


def test_app_js_has_paste_and_modal_handlers(client):
    r = client.get("/static/app.js")
    body = r.data.decode("utf-8")
    assert "handlePaste" in body
    assert "handleOpenModal" in body
    assert "readFromClipboard" in body
    assert "showModal" in body


def test_answered_request_excluded_from_list(client):
    r = client.post(
        "/api/requests", json={"system_prompt": "s", "user_prompt": "u"}
    )
    rid = r.get_json()["id"]
    client.post("/api/requests/{0}/answer".format(rid), json={"answer": "ok"})

    r = client.get("/api/requests")
    assert r.status_code == 200
    assert r.get_json() == []


def test_ack_deletes_request(client):
    r = client.post(
        "/api/requests", json={"system_prompt": "s", "user_prompt": "u"}
    )
    rid = r.get_json()["id"]

    r = client.post("/api/requests/{0}/ack".format(rid), json={})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    r = client.post("/api/requests/{0}/ack".format(rid), json={})
    assert r.status_code == 404


def test_ack_missing_request_returns_404(client):
    r = client.post("/api/requests/nonexistent/ack", json={})
    assert r.status_code == 404
