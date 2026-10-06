"""Адаптер ILLMClient над AI_Talk. Backends: local / web / custom.

Custom-режим (batch):
- ask_json_batch принимает N user_prompt'ов (N файлов).
- Adapter режет их на чанки по files_per_batch (по умолчанию 16).
- Чанки выполняются волнами по max_parallel (по умолчанию 8).
- На каждый чанк создаётся один custom-файл с JSON-запросом.
- Пользователь заполняет 8 файлов параллельно, сохраняет.
- Адаптер парсит JSON-ответы и возвращает плоский список из N результатов.

Формат custom-файла:
    # Tag Summary — пакетный запрос
    ## 📋 ЗАПРОС (скопируй в LLM)
    ```json
    {"task": "generate_tags_for_files", "instruction": "...",
     "files": [{"idx":1,"content":"..."}, ...],
     "response_format": {"responses": [["tag1"], ...]}}
    ```
    ## 🟢 ОТВЕТ (вставь JSON от LLM)
    ```json
    {"responses": [[], [], ...]}
    ```

Ответ LLM — один JSON на весь запрос.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_talk import AITalk, ModelRole

from tag_summary.domain.exceptions import LLMError, LLMFormatError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SEC = 240.0
BATCH_POLL_INTERVAL_SEC = 2.0

_RETRY_HINT = (
    "\n\n=== ВАЖНО ===\n"
    "Твой предыдущий ответ не прошёл валидацию JSON. "
    "Верни ТОЛЬКО валидный JSON без markdown-обёртки, без комментариев, "
    "без текста до или после."
)

_LOCAL_ROLE_MAP: dict[str, ModelRole] = {
    "fast": ModelRole.FAST,
    "smart": ModelRole.SMART,
}

_WEB_ROLE_MAP: dict[str, ModelRole] = {
    "deepseek": ModelRole.WEB_DEEPSEEK,
    "chatgpt": ModelRole.WEB_CHATGPT,
}

_ANSWER_START = "## 🟢 ОТВЕТ"
_ANSWER_JSON_RE = re.compile(r"```json\s*([\{\[].*?[\}\]])`\s*```", re.DOTALL)


class AITalkLLMClient:
    """Реализация ILLMClient через AITalk."""

    def __init__(
        self,
        *,
        backend: str = "local",
        web_provider: str = "deepseek",
        custom_dir: str = "custom_queue",
        files_per_batch: int = 16,
        max_parallel: int = 8,
        default_system_prompt: str = (
            "Ты — точный классификатор. Отвечай строго в формате JSON "
            "без пояснений и без markdown."
        ),
        llm_logger: Any | None = None,
        request_timeout_sec: float = REQUEST_TIMEOUT_SEC,
    ) -> None:
        if backend not in ("local", "web", "custom"):
            raise LLMError(
                f"Unknown backend: {backend!r}. Use 'local', 'web' or 'custom'."
            )
        if backend == "web" and web_provider not in _WEB_ROLE_MAP:
            raise LLMError(
                f"Unknown web_provider: {web_provider!r}. "
                f"Use one of {list(_WEB_ROLE_MAP.keys())}."
            )
        self._backend = backend
        self._web_provider = web_provider
        self._custom_dir = Path(custom_dir).resolve()
        self._files_per_batch = max(1, files_per_batch)
        self._max_parallel = max(1, max_parallel)
        self._default_system_prompt = default_system_prompt
        self._clients: dict[str, AITalk] = {}
        self._clients_lock = threading.Lock()
        self._log = llm_logger
        self._timeout = request_timeout_sec
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_parallel, thread_name_prefix="llm_call"
        )
        if self._backend == "custom":
            self._custom_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "AITalkLLMClient initialised backend=%s web_provider=%s "
            "custom_dir=%s files_per_batch=%d max_parallel=%d timeout=%.0fs",
            backend, web_provider, self._custom_dir,
            self._files_per_batch, self._max_parallel, request_timeout_sec,
        )

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def supports_batch(self) -> bool:
        return self._backend == "custom"

    def ask_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_retries: int = 3,
    ) -> str:
        if self._backend == "custom":
            return self._custom_raw(system_prompt, user_prompt)
        return self._single_local_web(
            system_prompt, user_prompt, model, max_retries
        )

    def ask_json_batch(
        self,
        *,
        system_prompt: str,
        user_prompts: list[str],
        model: str,
    ) -> list[str]:
        """N запросов одним вызовом.

        custom  — один custom-файл на весь chunk. Use case сам режет
                  большие партии на chunks и параллелит их.
        local/web — параллельно через внутренний пул.
        """
        if not user_prompts:
            return []
        if self._backend == "custom":
            return self._custom_batch(system_prompt, user_prompts)
        return self._parallel_local_web(system_prompt, user_prompts, model)

    # --- local/web ------------------------------------------------------

    def _parallel_local_web(
        self, system_prompt: str, user_prompts: list[str], model: str
    ) -> list[str]:
        with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
            futures = [
                pool.submit(
                    self._single_local_web,
                    system_prompt, up, model, 3,
                )
                for up in user_prompts
            ]
            return [f.result() for f in futures]

    def _single_local_web(
        self, system_prompt: str, user_prompt: str, model: str, max_retries: int
    ) -> str:
        role = self._resolve_role(model)
        client = self._get_client(role)
        effective_system = system_prompt or self._default_system_prompt

        for attempt in range(1, max_retries + 1):
            current_user = (
                user_prompt if attempt == 1 else user_prompt + _RETRY_HINT
            )
            started = time.monotonic()
            try:
                raw = self._call_with_timeout(
                    client, current_user, effective_system
                )
            except FuturesTimeoutError as exc:
                duration = time.monotonic() - started
                self._log_exchange(
                    model=model, attempt=attempt,
                    system_prompt=effective_system,
                    user_prompt=current_user,
                    raw_response=f"<TIMEOUT {duration:.1f}s>",
                    duration=duration, parse_ok=False,
                    parse_error=f"timeout {self._timeout:.0f}s",
                )
                raise LLMError(
                    f"LLM timed out after {self._timeout:.0f}s "
                    f"(backend={self._backend}, model={model}, attempt={attempt})"
                ) from exc
            except Exception as exc:  # noqa: BLE001
                duration = time.monotonic() - started
                self._log_exchange(
                    model=model, attempt=attempt,
                    system_prompt=effective_system,
                    user_prompt=current_user,
                    raw_response=f"<EXCEPTION {type(exc).__name__}: {exc}>",
                    duration=duration, parse_ok=False,
                    parse_error=f"transport: {type(exc).__name__}",
                )
                raise LLMError(
                    f"LLM generation failed: {exc}"
                ) from exc
            duration = time.monotonic() - started
            cleaned = _strip_code_fence(raw)
            is_valid = _is_valid_json(cleaned)
            self._log_exchange(
                model=model, attempt=attempt,
                system_prompt=effective_system,
                user_prompt=current_user,
                raw_response=raw, duration=duration,
                parse_ok=is_valid,
                parse_error=None if is_valid else "invalid JSON",
            )
            if is_valid:
                logger.info(
                    "LLM valid JSON backend=%s attempt=%d (%.1fs)",
                    self._backend, attempt, duration,
                )
                return cleaned
            logger.warning(
                "LLM invalid JSON (backend=%s, model=%s, attempt=%d/%d)",
                self._backend, model, attempt, max_retries,
            )
        raise LLMFormatError(
            f"LLM did not return valid JSON after {max_retries} attempts"
        )

    # --- custom ---------------------------------------------------------

    def _custom_parallel_batch(
        self, system_prompt: str, user_prompts: list[str]
    ) -> list[str]:
        """Оставлено для совместимости. Просто один chunk."""
        return self._custom_batch(system_prompt, user_prompts)

    def _custom_batch(
        self, system_prompt: str, chunk: list[str]
    ) -> list[str]:
        n = len(chunk)
        request_payload: dict[str, Any] = {
            "task": "generate_tags_for_files",
            "instruction": system_prompt,
            "files": [
                {"idx": i + 1, "content": chunk[i]}
                for i in range(n)
            ],
            "response_format": {
                "description": (
                    f"Верни JSON-объект с ключом responses. "
                    f"responses — массив длиной {n}. "
                    f"Каждый элемент — массив тегов (строк) для файла с тем же idx."
                ),
                "example": {
                    "responses": [
                        [f"tech/example-{i+1}", f"topic/example-{i+1}"]
                        for i in range(min(n, 3))
                    ]
                },
            },
        }
        answer_template = {
            "responses": [[] for _ in range(n)]
        }
        content = _render_custom_json_file(request_payload, answer_template)
        path = self._build_custom_file_path()
        path.write_text(content, encoding="utf-8")
        logger.info("Custom batch file: %s (n=%d)", path, n)
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cannot open %s: %s", path, exc)
        _wait_for_change(path)
        raw = path.read_text(encoding="utf-8")
        return _parse_custom_answer(raw, n)

    def _custom_raw(self, system_prompt: str, user_prompt: str) -> str:
        content = _render_custom_raw_file(system_prompt, user_prompt)
        path = self._build_custom_file_path()
        path.write_text(content, encoding="utf-8")
        logger.info("Custom raw file: %s", path)
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cannot open %s: %s", path, exc)
        _wait_for_change(path)
        raw = path.read_text(encoding="utf-8")
        return _parse_custom_raw_answer(raw)

    def _build_custom_file_path(self) -> Path:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = self._custom_dir / f"batch_{ts}.md"
        counter = 1
        while path.exists():
            path = self._custom_dir / f"batch_{ts}_{counter:02d}.md"
            counter += 1
        return path

    # --- общее ----------------------------------------------------------

    def close(self) -> None:
        for client in self._clients.values():
            try:
                client.close()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to close AITalk client")
        self._clients.clear()
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to shutdown executor")

    def _resolve_role(self, model: str) -> ModelRole:
        if self._backend == "web":
            return _WEB_ROLE_MAP[self._web_provider]
        if self._backend == "custom":
            return ModelRole.CUSTOM
        if model not in _LOCAL_ROLE_MAP:
            raise LLMError(
                f"Unknown model role: {model!r}. Use 'fast' or 'smart'."
            )
        return _LOCAL_ROLE_MAP[model]

    def _get_client(self, role: ModelRole) -> AITalk:
        key = role.value
        with self._clients_lock:
            if key not in self._clients:
                logger.info("Creating AITalk client for role=%s", key)
                if role == ModelRole.CUSTOM:
                    self._clients[key] = AITalk(
                        model=role, custom_dir=str(self._custom_dir)
                    )
                else:
                    self._clients[key] = AITalk(model=role)
            return self._clients[key]

    def _call_with_timeout(
        self, client: AITalk, user_prompt: str, system_prompt: str
    ) -> str:
        future = self._executor.submit(
            client.ask_ai,
            source=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return future.result(timeout=self._timeout)

    def _log_exchange(
        self,
        *,
        model: str,
        attempt: int,
        system_prompt: str,
        user_prompt: str,
        raw_response: str,
        duration: float,
        parse_ok: bool,
        parse_error: str | None,
    ) -> None:
        if self._log is None:
            return
        self._log.log_exchange(
            model=model, attempt=attempt,
            system_prompt=system_prompt, user_prompt=user_prompt,
            raw_response=raw_response, duration_sec=duration,
            parse_ok=parse_ok, parse_error=parse_error,
        )


# --- helpers -----------------------------------------------------------


def _render_custom_json_file(request: dict, answer: dict) -> str:
    req_json = json.dumps(request, ensure_ascii=False, indent=2)
    ans_json = json.dumps(answer, ensure_ascii=False, indent=2)
    return (
        "# Tag Summary — пакетный запрос\n\n"
        "## 📋 ЗАПРОС (скопируй в LLM)\n\n"
        "```json\n" + req_json + "\n```\n\n"
        "## 🟢 ОТВЕТ (вставь JSON от LLM)\n\n"
        "```json\n" + ans_json + "\n```\n"
    )


def _wait_for_change(path: Path) -> None:
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        mtime = 0.0
    logger.info("Waiting for user input: %s", path)
    while True:
        time.sleep(BATCH_POLL_INTERVAL_SEC)
        try:
            cur = path.stat().st_mtime
        except FileNotFoundError:
            continue
        if cur > mtime:
            logger.info("File changed: %s", path)
            return


def _parse_custom_answer(raw: str, n: int) -> list[str]:
    """Извлекает JSON-ответ из секции `## 🟢 ОТВЕТ`.

    Толерантен к мусору до/после JSON (markdown-обёртки, лишние буквы,
    многоточие). Ищет первый `{` после маркера, балансирует скобки.
    """
    idx = raw.find(_ANSWER_START)
    if idx == -1:
        raise LLMFormatError(
            "Custom file: section '## 🟢 ОТВЕТ' not found"
        )
    answer_part = raw[idx:]

    # Убираем markdown-обёртку ```json ... ``` (если есть).
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", answer_part, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        candidate = answer_part

    # Ищем первый { и балансируем скобки.
    start = candidate.find("{")
    if start == -1:
        raise LLMFormatError(
            "Custom file: no '{' in answer section. "
            f"Tail: {candidate[-200:]!r}"
        )
    depth = 0
    end = -1
    in_string = False
    escape = False
    for i in range(start, len(candidate)):
        ch = candidate[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        raise LLMFormatError(
            "Custom file: unbalanced braces in answer. "
            f"Tail: {candidate[-200:]!r}"
        )

    json_text = candidate[start:end]
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise LLMFormatError(
            f"Custom file: invalid JSON: {exc}. "
            f"Snippet: {json_text[:200]!r}"
        ) from exc

    responses = data.get("responses")
    if not isinstance(responses, list):
        raise LLMFormatError(
            "Custom file: response.responses not a list. "
            f"Keys: {list(data.keys())}"
        )
    if len(responses) != n:
        raise LLMFormatError(
            f"Custom file: expected {n} responses, got {len(responses)}"
        )
    result: list[str] = []
    for i, r in enumerate(responses):
        if not isinstance(r, list) or not all(isinstance(x, str) for x in r):
            raise LLMFormatError(
                f"Custom file: response[{i}] is not a list of strings: {r!r}"
            )
        result.append(json.dumps(r, ensure_ascii=False))
    return result


def _render_custom_raw_file(system_prompt: str, user_prompt: str) -> str:
    return (
        "# Tag Summary — одиночный запрос\n\n"
        "## 📋 SYSTEM\n\n"
        f"{system_prompt}\n\n"
        "## 📥 USER\n\n"
        f"{user_prompt}\n\n"
        "## 🟢 ОТВЕТ\n\n"
        "```json\n"
        "{}\n"
        "```\n"
    )


def _parse_custom_raw_answer(raw: str) -> str:
    """Извлекает JSON из одиночного ответа. Толерантен к мусору."""
    idx = raw.find(_ANSWER_START)
    if idx == -1:
        raise LLMFormatError(
            "Custom file: section '## 🟢 ОТВЕТ' not found"
        )
    answer_part = raw[idx:]

    fence_match = re.search(
        r"```(?:json)?\s*(.*?)\s*```", answer_part, re.DOTALL
    )
    if fence_match:
        candidate = fence_match.group(1)
    else:
        candidate = answer_part

    # Ищем первый { или [.
    start_obj = candidate.find("{")
    start_arr = candidate.find("[")
    starts = [x for x in (start_obj, start_arr) if x != -1]
    if not starts:
        raise LLMFormatError(
            "Custom file: no JSON start in answer. "
            f"Tail: {candidate[-200:]!r}"
        )
    start = min(starts)
    open_ch = candidate[start]
    close_ch = "}" if open_ch == "{" else "]"

    depth = 0
    end = -1
    in_string = False
    escape = False
    for i in range(start, len(candidate)):
        ch = candidate[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        raise LLMFormatError(
            "Custom file: unbalanced brackets in answer. "
            f"Tail: {candidate[-200:]!r}"
        )

    json_text = candidate[start:end]
    if not _is_valid_json(json_text):
        raise LLMFormatError(
            f"Custom file: extracted text is not valid JSON. "
            f"Snippet: {json_text[:200]!r}"
        )
    return json_text


def _strip_code_fence(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if len(lines) < 2:
        return s
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _is_valid_json(text: str) -> bool:
    if not text:
        return False
    try:
        parsed: Any = json.loads(text)
    except (ValueError, TypeError):
        return False
    return isinstance(parsed, (dict, list))
