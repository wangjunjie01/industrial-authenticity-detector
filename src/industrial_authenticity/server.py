from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from importlib.resources import files
from urllib.parse import urlsplit

from .analyzer import analyze_text
from .updates import UpdateManager
from .version import APP_VERSION


WEB_ROOT = files("industrial_authenticity").joinpath("web")
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class DetectorServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], manager: UpdateManager):
        super().__init__(address, handler)
        self.update_manager = manager


class Handler(BaseHTTPRequestHandler):
    server_version = f"IndustrialAuthenticity/{APP_VERSION}"

    @property
    def manager(self) -> UpdateManager:
        return self.server.update_manager  # type: ignore[attr-defined]

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _is_local(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _trusted_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlsplit(origin)
        return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}

    def _require_local(self) -> bool:
        if not self._is_local() or not self._trusted_origin():
            self._json(HTTPStatus.FORBIDDEN, {"error": "This endpoint accepts local requests only."})
            return False
        return True

    def _payload(self, maximum: int = 100_000) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > maximum:
            raise ValueError("Request is too large.")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object.")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/update/status":
            if self._require_local():
                self._json(HTTPStatus.OK, self.manager.status(check_remote=True))
            return
        if path == "/api/private-corpus/status":
            if self._require_local():
                self._json(HTTPStatus.OK, self.manager.corpus.status())
            return
        asset = ASSETS.get(path)
        if not asset:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
            return
        name, content_type = asset
        self._send(HTTPStatus.OK, WEB_ROOT.joinpath(name).read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/analyze":
                payload = self._payload()
                result = analyze_text(payload.get("text", ""), payload.get("platform", "general"), self.manager.active_model())
                self._json(HTTPStatus.OK, result)
                return
            if path == "/api/private-corpus/import":
                if not self._require_local():
                    return
                payload = self._payload(maximum=2_000_000)
                samples = payload.get("samples", [])
                if not isinstance(samples, list):
                    raise ValueError("Samples must be a list.")
                self._json(HTTPStatus.OK, self.manager.corpus.import_samples(samples))
                return
            if path == "/api/update/apply":
                if not self._require_local():
                    return
                self._json(HTTPStatus.OK, self.manager.apply(str(self._payload().get("confirmation_token", ""))))
                return
            if path == "/api/update/rollback":
                if not self._require_local():
                    return
                self._json(HTTPStatus.OK, self.manager.rollback(str(self._payload().get("confirmation_token", ""))))
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except PermissionError as exc:
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Operation failed safely: {type(exc).__name__}"})

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8765, state_root: str | None = None) -> None:
    manager = UpdateManager(state_root=state_root)
    server = DetectorServer((host, port), Handler, manager)
    print(f"Industrial Authenticity Detector: http://{host}:{port}")
    print("Text analysis is offline. Network is used only for signed release checks and confirmed downloads.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
