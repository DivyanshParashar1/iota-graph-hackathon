"""Host-side bridge so the Docker API container can use Claude Code (which runs on the host, on its login).

    .venv/bin/python -m ripple.claude_code_bridge            # 127.0.0.1:8765

POST /run {system, prompt, schema, model, effort} -> the structured output of one `claude -p` call (Claude Code's
own tools off). GET /health -> {"ok": true}. Listens on loopback only; when CLAUDE_CODE_BRIDGE_TOKEN is set,
requests must carry it as a bearer token. Docker Desktop reaches it at http://host.docker.internal:8765.
"""

from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ripple.agents.claude_code import run_claude
from ripple.config import get_settings

log = logging.getLogger("claude_code_bridge")


class Handler(BaseHTTPRequestHandler):
    token: str | None = None
    binary = "claude"
    timeout = 300.0

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._send(200, {"ok": True}) if self.path == "/health" else self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/run":
            return self._send(404, {"error": "not found"})
        if self.token and self.headers.get("Authorization") != f"Bearer {self.token}":
            return self._send(401, {"error": "bad token"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            out = run_claude(req["system"], req["prompt"], req["schema"], req.get("model") or "opus",
                             req.get("effort"), binary=self.binary, timeout=self.timeout)
        except Exception as e:  # noqa: BLE001 - reported to the caller, which falls back to scripted
            log.warning("claude call failed: %s", e)
            return self._send(502, {"error": str(e)})
        self._send(200, out)


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    Handler.token = s.claude_code_bridge_token or None
    Handler.binary = s.claude_code_bin
    Handler.timeout = s.claude_code_timeout
    logging.basicConfig(level=logging.INFO)
    log.info("Claude Code bridge on http://%s:%d (token %s)", a.host, a.port, "on" if Handler.token else "off")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
