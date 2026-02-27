#!/usr/bin/env python3
"""Minimal shared runtime server used by test-train pipeline scripts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = os.environ.get("RUNTIME_HOST", "127.0.0.1")
PORT = int(os.environ.get("RUNTIME_PORT", "43173"))
STATE_DIR = Path(os.environ.get("RUNTIME_STATE_DIR", "reports/optimus-prime/runtime")).resolve()
FORCE_UNHEALTHY_PATH = STATE_DIR / "FORCE_UNHEALTHY"
DEPLOY_STATE_PATH = STATE_DIR / "DEPLOY_STATE.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_json", "path": str(path)}
    if not isinstance(payload, dict):
        return {"status": "invalid_payload", "path": str(path)}
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "OptimusRuntime/1.0"

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        return

    def do_HEAD(self) -> None:  # noqa: N802
        self._respond(head_only=True)

    def do_GET(self) -> None:  # noqa: N802
        self._respond(head_only=False)

    def _respond(self, *, head_only: bool) -> None:
        path = self.path.split("?", 1)[0]
        unhealthy = FORCE_UNHEALTHY_PATH.exists()

        status = 200
        if path == "/health":
            status = 503 if unhealthy else 200
            body = {"status": "unhealthy" if unhealthy else "ok", "timestamp": utc_now_iso()}
        elif path == "/deploy-info":
            body = _read_json(DEPLOY_STATE_PATH)
            if not body:
                body = {"status": "no_deploy_record", "timestamp": utc_now_iso()}
        else:
            body = {"service": "optimus-test-train-runtime", "status": "ok", "timestamp": utc_now_iso()}

        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if not head_only:
            self.wfile.write(raw)


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
