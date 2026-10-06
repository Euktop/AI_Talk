"""Тесты CustomWebClient без реального сервера.

HTTP-вызовы и проверка сервера замоканы, тестируем логику клиента.
"""
import pytest

from ai_talk.domain.interfaces import Message
from ai_talk.infrastructure import custom_web_client as mod
from ai_talk.infrastructure.custom_web_client import CustomWebClient


@pytest.fixture
def no_server(monkeypatch):
    monkeypatch.setattr(mod, "_is_server_ready", lambda h, p: True)
    monkeypatch.setattr(mod, "_start_server", lambda h, p, db: True)


def test_split_messages_system_and_users(no_server):
    client = CustomWebClient(open_browser=False)
    sys_p, usr_p = CustomWebClient._split_messages([
        Message(role="system", content="S1"),
        Message(role="user", content="U1"),
        Message(role="user", content="U2"),
    ])
    assert sys_p == "S1"
    assert usr_p == "U1\n\nU2"


def test_split_messages_no_system(no_server):
    sys_p, usr_p = CustomWebClient._split_messages([
        Message(role="user", content="hello"),
    ])
    assert sys_p == ""
    assert usr_p == "hello"


def test_chat_full_flow(no_server, monkeypatch):
    calls = []

    def fake_post(url, payload, timeout=30.0):
        calls.append(("POST", url, payload))
        if url.endswith("/register"):
            return {"ok": True}
        if url.endswith("/api/requests"):
            return {"id": "req-1"}
        if url.endswith("/ack"):
            return {"ok": True}
        raise AssertionError("unexpected POST: " + url)

    def fake_get(url, timeout):
        calls.append(("GET", url, timeout))
        return {"id": "req-1", "answer": "Hi there"}

    monkeypatch.setattr(mod, "_http_post", fake_post)
    monkeypatch.setattr(mod, "_http_get", fake_get)

    client = CustomWebClient(open_browser=False)
    result = client.chat([Message(role="user", content="hello")])

    assert result == "Hi there"
    assert any(c[1].endswith("/register") for c in calls)
    assert any(
        c[0] == "POST" and c[1].endswith("/api/requests") for c in calls
    )
    assert any(c[0] == "GET" and "/wait" in c[1] for c in calls)
    assert any(c[1].endswith("/ack") for c in calls)


def test_chat_registers_only_once(no_server, monkeypatch):
    reg_count = [0]
    req_count = [0]

    def fake_post(url, payload, timeout=30.0):
        if url.endswith("/register"):
            reg_count[0] += 1
            return {"ok": True}
        if url.endswith("/api/requests"):
            req_count[0] += 1
            return {"id": "req-{0}".format(req_count[0])}
        if url.endswith("/ack"):
            return {"ok": True}
        return {}

    def fake_get(url, timeout):
        return {"answer": "x"}

    monkeypatch.setattr(mod, "_http_post", fake_post)
    monkeypatch.setattr(mod, "_http_get", fake_get)

    client = CustomWebClient(open_browser=False)
    client.chat([Message(role="user", content="a")])
    client.chat([Message(role="user", content="b")])

    assert reg_count[0] == 1
    assert req_count[0] == 2


def test_structured_chat_parses_json_from_answer(no_server, monkeypatch):
    def fake_post(url, payload, timeout=30.0):
        if url.endswith("/register"):
            return {"ok": True}
        if url.endswith("/api/requests"):
            return {"id": "r"}
        if url.endswith("/ack"):
            return {"ok": True}
        return {}

    def fake_get(url, timeout):
        return {"answer": "```json\n{\"a\": 1}\n```"}

    monkeypatch.setattr(mod, "_http_post", fake_post)
    monkeypatch.setattr(mod, "_http_get", fake_get)

    client = CustomWebClient(open_browser=False)
    result = client.structured_chat([Message(role="user", content="x")])
    assert result == {"a": 1}


def test_unregister_noop_when_not_registered(no_server, monkeypatch):
    calls = []

    def fake_post(url, payload, timeout=30.0):
        calls.append(url)
        return {"ok": True}

    monkeypatch.setattr(mod, "_http_post", fake_post)

    client = CustomWebClient(open_browser=False)
    client._unregister()
    assert calls == []
