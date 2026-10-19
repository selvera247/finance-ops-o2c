"""Local HITL stub — approve/reject pending approvals over HTTP (Slack stand-in)."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from finance_ops.runtime.hitl import DEFAULT_STORE


HTML = """<!doctype html>
<html><head><title>HITL Approvals</title></head>
<body style="font-family:sans-serif;max-width:800px;margin:2rem auto">
<h1>HITL Approval Gate (local stub)</h1>
<p>Stand-in for Slack/Teams approve buttons.</p>
{body}
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/approvals"}:
            rows = DEFAULT_STORE.list("pending")
            if not rows:
                body = "<p>No pending approvals.</p>"
            else:
                parts = ["<ul>"]
                for r in rows:
                    parts.append(
                        "<li>"
                        f"<strong>{r.approval_id}</strong> — {r.summary} "
                        f"(${r.amount:,.2f} {r.currency}) "
                        f"<a href='/approve?id={r.approval_id}&token={r.resume_token}'>Approve</a> | "
                        f"<a href='/reject?id={r.approval_id}&token={r.resume_token}'>Reject</a>"
                        "</li>"
                    )
                parts.append("</ul>")
                body = "".join(parts)
            self._html(HTML.format(body=body))
            return
        if parsed.path in {"/approve", "/reject"}:
            qs = parse_qs(parsed.query)
            approval_id = (qs.get("id") or [""])[0]
            token = (qs.get("token") or [""])[0]
            decision = "approved" if parsed.path == "/approve" else "rejected"
            try:
                item = DEFAULT_STORE.decide(
                    approval_id, decision=decision, actor="hitl_web", resume_token=token
                )
                self._html(HTML.format(body=f"<p>{decision}: {item.approval_id}</p><p><a href='/'>Back</a></p>"))
            except Exception as exc:  # noqa: BLE001
                self._html(HTML.format(body=f"<p>Error: {exc}</p>"), code=400)
            return
        if parsed.path == "/health":
            self._json({"status": "ok"})
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json({"error": "invalid json"}, code=400)
            return
        if parsed.path == "/api/decide":
            try:
                item = DEFAULT_STORE.decide(
                    body["approval_id"],
                    decision=body["decision"],
                    actor=body.get("actor", "api"),
                    resume_token=body.get("resume_token"),
                )
                self._json(item.model_dump())
            except Exception as exc:  # noqa: BLE001
                self._json({"error": str(exc)}, code=400)
            return
        self.send_error(404)

    def _html(self, content: str, code: int = 200) -> None:
        data = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict, code: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"HITL stub at http://{args.host}:{args.port}/")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
