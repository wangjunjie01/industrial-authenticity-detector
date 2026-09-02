from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from importlib.resources import files

from .analyzer import analyze_text


WEB_ROOT = files("industrial_authenticity").joinpath("web")
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "IndustrialAuthenticity/0.1"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        asset = ASSETS.get(self.path.split("?", 1)[0])
        if not asset:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        name, content_type = asset
        self._send(HTTPStatus.OK, WEB_ROOT.joinpath(name).read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/analyze":
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 100_000:
                raise ValueError("Request is too large.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = analyze_text(payload.get("text", ""), payload.get("platform", "general"))
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.OK, body, "application/json; charset=utf-8")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.BAD_REQUEST, body, "application/json; charset=utf-8")

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Industrial Authenticity Detector: http://{host}:{port}")
    print("Local analysis only. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

