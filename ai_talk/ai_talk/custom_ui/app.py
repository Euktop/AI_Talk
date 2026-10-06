"""Flask-приложение CUSTOM UI.

Фаза 1: только API. UI (HTML/CSS/JS) добавляется в Фазе 3.
"""
import argparse
import os
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request as flask_request

from ai_talk.custom_ui.storage import Storage


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DB = Path.home() / ".ai_talk" / "custom_ui.db"
DEFAULT_SHUTDOWN_DELAY = 5.0
DEFAULT_WAIT_TIMEOUT = 3600.0


def create_app(storage: Storage, static_dir: Optional[Path] = None) -> Flask:
    """Создаёт Flask-приложение. Без запуска сервера — для тестов."""
    app = Flask(__name__, static_folder=None)
    app.config["STORAGE"] = storage
    app.config["STATIC_DIR"] = static_dir

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    # -------- clients --------

    @app.route("/api/clients/register", methods=["POST"])
    def register_client():
        data = flask_request.get_json(silent=True) or {}
        client_id = data.get("client_id")
        if not client_id:
            return jsonify({"error": "client_id required"}), 400
        storage.register_client(client_id)
        return jsonify({"ok": True})

    @app.route("/api/clients/unregister", methods=["POST"])
    def unregister_client():
        data = flask_request.get_json(silent=True) or {}
        client_id = data.get("client_id")
        if not client_id:
            return jsonify({"error": "client_id required"}), 400
        storage.unregister_client(client_id)
        return jsonify({"ok": True})

    # -------- requests --------

    @app.route("/api/requests", methods=["POST"])
    def create_request():
        data = flask_request.get_json(silent=True) or {}
        system_prompt = data.get("system_prompt", "") or ""
        user_prompt = data.get("user_prompt", "") or ""
        req = storage.create_request(system_prompt, user_prompt)
        return jsonify({"id": req.id})

    @app.route("/api/requests", methods=["GET"])
    def list_requests():
        reqs = storage.list_requests(pending_only=True)
        return jsonify(
            [
                {
                    "id": r.id,
                    "preview": r.preview(),
                    "created_at": r.created_at.isoformat(),
                    "has_answer": r.answer is not None,
                }
                for r in reqs
            ]
        )

    @app.route("/api/requests/<request_id>/raw")
    def get_raw(request_id):
        req = storage.get_request(request_id)
        if req is None:
            return "not found", 404
        return (
            req.full_text(),
            200,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    @app.route("/api/requests/<request_id>/wait")
    def wait_for_answer(request_id):
        try:
            timeout = float(flask_request.args.get("timeout", DEFAULT_WAIT_TIMEOUT))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid timeout"}), 400

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            req = storage.get_request(request_id)
            if req is None:
                return jsonify({"error": "not found"}), 404
            if req.answer is not None:
                return jsonify({"id": req.id, "answer": req.answer})
            time.sleep(0.2)
        return jsonify({"error": "timeout"}), 504

    @app.route("/api/requests/<request_id>/answer", methods=["POST"])
    def answer_request(request_id):
        data = flask_request.get_json(silent=True) or {}
        answer = data.get("answer", "") or ""
        if not answer.strip():
            return jsonify({"error": "empty answer"}), 400
        ok = storage.answer_request(request_id, answer)
        if not ok:
            return jsonify({"error": "not found or already answered"}), 404
        return jsonify({"ok": True})

    @app.route("/api/requests/<request_id>/ack", methods=["POST"])
    def ack_request(request_id):
        ok = storage.delete_request(request_id)
        if not ok:
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})

    # -------- root (placeholder until phase 3) --------

    @app.route("/")
    def index():
        return (
            "<!doctype html><html><body>"
            "<h1>AI_Talk CUSTOM UI</h1>"
            "<p>Фаза 1: сервер работает. UI появится в Фазе 3.</p>"
            "</body></html>"
        )

    return app


def _shutdown_monitor(
    storage: Storage,
    delay: float,
    stop_event: threading.Event,
) -> None:
    """Следит, когда клиентов и запросов нет. Ждёт delay секунд → выход."""
    had_client = False
    idle_since = None
    while not stop_event.is_set():
        time.sleep(1.0)
        n_clients = storage.count_clients()
        n_requests = storage.count_requests()
        if n_clients > 0:
            had_client = True
            idle_since = None
            continue
        if had_client and n_requests == 0:
            if idle_since is None:
                idle_since = time.monotonic()
            elif time.monotonic() - idle_since >= delay:
                os._exit(0)
        else:
            idle_since = None


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="ai_talk.custom_ui")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument(
        "--open-browser", action="store_true", help="открыть браузер при старте"
    )
    parser.add_argument(
        "--shutdown-delay",
        type=float,
        default=DEFAULT_SHUTDOWN_DELAY,
        help="секунд простоя перед выходом (0 = не выходить)",
    )
    args = parser.parse_args(argv)

    storage = Storage(Path(args.db))
    app = create_app(storage)

    if args.shutdown_delay > 0:
        stop_event = threading.Event()
        t = threading.Thread(
            target=_shutdown_monitor,
            args=(storage, args.shutdown_delay, stop_event),
            daemon=True,
        )
        t.start()

    if args.open_browser:
        webbrowser.open("http://{0}:{1}/".format(args.host, args.port))

    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
