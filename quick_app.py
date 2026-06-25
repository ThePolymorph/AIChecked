#!/usr/bin/env python3
"""Minimal local web UI for instant heuristic checks (stdlib only)."""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple

from heuristics import format_report, quick_check

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AIChecked — Quick scan</title>
  <style>
    :root { font-family: system-ui, sans-serif; color: #1a1a1a; background: #f6f6f4; }
    body { max-width: 42rem; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.35rem; font-weight: 600; }
    p.hint { color: #555; font-size: 0.9rem; }
    textarea { width: 100%; min-height: 10rem; padding: 0.75rem; font-size: 1rem;
               border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
    button { margin-top: 0.75rem; padding: 0.5rem 1.25rem; font-size: 1rem;
             border: none; border-radius: 6px; background: #222; color: #fff; cursor: pointer; }
    button:hover { background: #444; }
    pre { background: #fff; border: 1px solid #ddd; border-radius: 6px;
          padding: 1rem; white-space: pre-wrap; font-size: 0.85rem; line-height: 1.45; }
    .score { font-size: 1.5rem; font-weight: 600; margin: 1rem 0 0.25rem; }
    .low { color: #2d6a4f; } .medium { color: #b5850a; } .high { color: #9b2226; }
  </style>
</head>
<body>
  <h1>Quick AI-writing scan</h1>
  <p class="hint">Instant checks: em dashes, rule-of-three lists, buzzwords, signpost phrases.
  No models, no API keys. Weak signals only — not proof.</p>
  <form method="POST" action="/">
    <textarea name="text" placeholder="Paste text here…">{escaped_text}</textarea>
    <br />
    <button type="submit">Scan</button>
  </form>
  {result_block}
</body>
</html>
"""


def _result_html(result_block: str) -> str:
    return HTML.replace("{result_block}", result_block).replace("{escaped_text}", "")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return  # quiet

    def do_GET(self) -> None:
        page = _result_html("")
        self._respond(200, "text/html; charset=utf-8", page.encode("utf-8"))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(body)
        text = params.get("text", [""])[0]

        if self.path == "/api/check":
            result = quick_check(text)
            payload = {
                "word_count": result.word_count,
                "ai_tell_score": result.ai_tell_score,
                "verdict": result.verdict,
                "signals": [
                    {
                        "name": s.name,
                        "triggered": s.triggered,
                        "count": s.count,
                        "detail": s.detail,
                    }
                    for s in result.signals
                ],
                "report": format_report(result),
            }
            data = json.dumps(payload).encode("utf-8")
            self._respond(200, "application/json", data)
            return

        result = quick_check(text)
        report = format_report(result)
        score_class = result.verdict
        block = (
            f'<p class="score {score_class}">{result.ai_tell_score}/100 — {result.verdict}</p>'
            f"<pre>{_escape(report)}</pre>"
        )
        escaped = _escape(text)
        page = HTML.replace("{result_block}", block).replace("{escaped_text}", escaped)
        self._respond(200, "text/html; charset=utf-8", page.encode("utf-8"))

    def _respond(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = HTTPServer((host, port), Handler)
    print(f"Quick checker: http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    run_server()
