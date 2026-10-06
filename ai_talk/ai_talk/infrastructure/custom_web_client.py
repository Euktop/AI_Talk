"""CUSTOM-клиент: HTTP к локальному web-UI (`ai_talk.custom_ui`).

Заменяет старый файловый `CustomFileClient`. Сервер поднимается
лениво при первом запросе; один экземпляр на порт.

См. docs/CUSTOM_UI.md.
"""
import atexit
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_talk.domain.exceptions import AITalkConnectionError, AITalkGenerationError
from ai_talk.domain.interfaces import ILLMClient, Message
from ai_talk.parsers import parse_json_object


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DB = Path.home() / ".ai_talk" / "custom_ui.db"
DEFAULT_WAIT_TIMEOUT = 3600.0
SERVER_START_TIMEOUT = 5.0


def _http_get(url: str, timeout: float) -> Any:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AITalkGenerationError(
            "HTTP {0} on GET {1}: {2}".format(e.code, url, e.reason)
        ) from e


def _http_post(url: str, payload: Dict[str, Any], timeout: float = 30.0) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AITalkGenerationError(
            "HTTP {0} on POST {1}: {2}".format(e.code, url, e.reason)
        ) from e


def _is_server_ready(host: str, port: int) -> bool:
    try:
        _http_get("http://{0}:{1}/health".format(host, port), timeout=0.5)
        return True
    except Exception:
        return False


def _start_server(
    host: str, port: int, db_path: Path, open_browser: bool = False
) -> bool:
    """Запускает `python -m ai_talk.custom_ui` в фоне. True при успехе.

    open_browser=True → сервер сам откроет браузер при старте.
    """
    cmd = [
        sys.executable,
        "-m",
        "ai_talk.custom_ui",
        "--host",
        host,
        "--port",
        str(port),
        "--db",
        str(db_path),
    ]
    if open_browser:
        cmd.append("--open-browser")
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(cmd, **kwargs)
    except Exception as e:
        raise AITalkConnectionError(
            "Не удалось запустить CUSTOM UI сервер: {0}".format(e)
        ) from e

    deadline = time.monotonic() + SERVER_START_TIMEOUT
    while time.monotonic() < deadline:
        if _is_server_ready(host, port):
            return True
        time.sleep(0.1)
    return False


class CustomWebClient:
    """Реализация ILLMClient для CUSTOM-режима через локальный web-UI."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        db_path: Optional[Path] = None,
        open_browser: bool = True,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.open_browser = open_browser
        self.wait_timeout = wait_timeout
        self.base_url = "http://{0}:{1}".format(host, port)
        self.client_id = str(uuid.uuid4())
        self._registered = False
        atexit.register(self._unregister)

    # -------- lifecycle --------

    def _ensure_registered(self) -> None:
        # Перепроверяем /health на каждом вызове: сервер мог умереть
        # между вызовами chat(), например, если пользователь закрыл окно.
        if self._registered and _is_server_ready(self.host, self.port):
            return
        self._registered = False
        if not _is_server_ready(self.host, self.port):
            if not _start_server(
                self.host,
                self.port,
                self.db_path,
                open_browser=self.open_browser,
            ):
                raise AITalkConnectionError(
                    "CUSTOM UI сервер не отвечает на {0}".format(self.base_url)
                )
        _http_post(
            self.base_url + "/api/clients/register",
            {"client_id": self.client_id},
        )
        self._registered = True

    def _unregister(self) -> None:
        if not self._registered:
            return
        try:
            _http_post(
                self.base_url + "/api/clients/unregister",
                {"client_id": self.client_id},
                timeout=2.0,
            )
        except Exception:
            pass
        self._registered = False

    # -------- ILLMClient --------

    @staticmethod
    def _split_messages(messages: List[Message]):
        system = ""
        user_parts: List[str] = []
        for m in messages:
            if m.role == "system":
                system += m.content + "\n"
            elif m.role == "user":
                user_parts.append(m.content)
        return system.strip(), "\n\n".join(user_parts)

    def chat(self, messages: List[Message], temperature: float = 0.7) -> str:
        self._ensure_registered()
        system_prompt, user_prompt = self._split_messages(messages)
        resp = _http_post(
            self.base_url + "/api/requests",
            {"system_prompt": system_prompt, "user_prompt": user_prompt},
        )
        request_id = resp["id"]
        result = _http_get(
            "{0}/api/requests/{1}/wait?timeout={2}".format(
                self.base_url, request_id, int(self.wait_timeout)
            ),
            timeout=self.wait_timeout + 5.0,
        )
        answer = result.get("answer", "")
        # ACK: удаляем запрос из хранилища сервера
        try:
            _http_post(
                "{0}/api/requests/{1}/ack".format(self.base_url, request_id),
                {},
            )
        except Exception:
            pass
        return answer

    def structured_chat(
        self, messages: List[Message], response_format: str = "json"
    ) -> Dict[str, Any]:
        text = self.chat(messages)
        return parse_json_object(text)
