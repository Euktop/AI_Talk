"""Тесты CustomWebClient без реального сервера.

HTTP-вызовы и проверка сервера замоканы, тестируем логику клиента.
"""
from pathlib import Path

import pytest

from ai_talk.domain.interfaces import Message
from ai_talk.infrastructure import custom_web_client as mod
from ai_talk.infrastructure.custom_web_client import CustomWebClient


@pytest.fixture
def no_server(monkeypatch):
    monkeypatch.setattr(mod, "_is_server_ready", lambda h, p: True)
    monkeypatch.setattr(
        mod, "_start_server", lambda h, p, db, open_browser=False: True
    )


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


def test_start_server_passes_open_browser_flag(monkeypatch):
    calls = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            calls.append(cmd)

    monkeypatch.setattr(mod.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        mod, "_is_server_ready", lambda h, p: len(calls) > 0
    )
    ok = mod._start_server(
        "127.0.0.1", 8765, Path("x.db"), open_browser=True
    )
    assert ok
    assert calls
    assert "--open-browser" in calls[0]


def test_start_server_skips_open_browser_flag(monkeypatch):
    calls = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            calls.append(cmd)

    monkeypatch.setattr(mod.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        mod, "_is_server_ready", lambda h, p: len(calls) > 0
    )
    ok = mod._start_server(
        "127.0.0.1", 8765, Path("x.db"), open_browser=False
    )
    assert ok
    assert calls
    assert "--open-browser" not in calls[0]


def test_ensure_registered_rechecks_after_server_death(
    no_server, monkeypatch
):
    """Если сервер умер, _ensure_registered должен перерегистрироваться."""
    # Сервер сначала жив, потом мёртв
    state = {"alive": True}
    monkeypatch.setattr(
        mod, "_is_server_ready", lambda h, p: state["alive"]
    )
    reg_count = [0]
    start_count = [0]

    def fake_post(url, payload, timeout=30.0):
        if url.endswith("/register"):
            reg_count[0] += 1
        return {"ok": True}

    def fake_start(host, port, db, open_browser=False):
        start_count[0] += 1
        state["alive"] = True
        return True

    monkeypatch.setattr(mod, "_http_post", fake_post)
    monkeypatch.setattr(mod, "_start_server", fake_start)

    client = CustomWebClient(open_browser=False)
    client._ensure_registered()
    assert reg_count[0] == 1
    assert start_count[0] == 0

    # Сервер умер — следующий вызов должен его поднять
    state["alive"] = False
    client._ensure_registered()
    assert reg_count[0] == 2
    assert start_count[0] == 1


def test_ensure_registered_skips_register_when_alive(no_server, monkeypatch):
    reg_count = [0]

    def fake_post(url, payload, timeout=30.0):
        if url.endswith("/register"):
            reg_count[0] += 1
        return {"ok": True}

    monkeypatch.setattr(mod, "_http_post", fake_post)

    client = CustomWebClient(open_browser=False)
    client._ensure_registered()
    client._ensure_registered()
    assert reg_count[0] == 1
