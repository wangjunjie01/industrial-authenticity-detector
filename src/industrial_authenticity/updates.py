"""Signed, local-only detector bundle update manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

from .model import LightweightModel
from .private_corpus import PrivateCorpus
from .version import APP_VERSION, BUNDLED_DETECTOR_VERSION


REPOSITORY = "wangjunjie01/industrial-authenticity-detector"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com", "api.github.com", "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
MAX_PACKAGE_BYTES = 160 * 1024 * 1024
MAX_EXTRACTED_BYTES = 150 * 1024 * 1024
CHECK_INTERVAL = timedelta(hours=24)


def default_state_root() -> Path:
    configured = os.environ.get("IAD_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / "Library" / "Application Support" / "Industrial Authenticity Detector"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _version_key(value: str) -> tuple[int, ...]:
    digits = []
    for part in value.lstrip("v").split("."):
        number = "".join(char for char in part if char.isdigit())
        digits.append(int(number or 0))
    return tuple(digits)


@dataclass
class ConfirmationTokens:
    ttl_seconds: int = 600

    def __post_init__(self) -> None:
        self._tokens: dict[str, tuple[str, datetime]] = {}

    def issue(self, action: str) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = (action, _utcnow() + timedelta(seconds=self.ttl_seconds))
        return token

    def consume(self, token: str, action: str) -> bool:
        stored = self._tokens.pop(token, None)
        return bool(stored and stored[0] == action and stored[1] >= _utcnow())


class UpdateManager:
    def __init__(
        self,
        state_root: str | Path | None = None,
        fetch_json: Callable[[str], dict] | None = None,
        download: Callable[[str, Path], None] | None = None,
        public_key_path: str | Path | None = None,
    ) -> None:
        self.root = Path(state_root) if state_root else default_state_root()
        self.versions = self.root / "versions"
        self.state_path = self.root / "state.json"
        self.cache_path = self.root / "release-cache.json"
        self.tokens = ConfirmationTokens()
        self.fetch_json = fetch_json or self._fetch_json
        self.download = download or self._download
        self.public_key_path = Path(public_key_path) if public_key_path else Path(__file__).with_name("update_public_key.pem")
        self.corpus = PrivateCorpus(self.root)

    def _state(self) -> dict:
        if not self.state_path.exists():
            return {"active_version": BUNDLED_DETECTOR_VERSION, "previous_version": None}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write_state(self, payload: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def active_model(self) -> LightweightModel:
        state = self._state()
        version = state["active_version"]
        candidate = self.versions / version / "model.json"
        return LightweightModel.load(candidate if candidate.exists() else None)

    def _fetch_json(self, url: str) -> dict:
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "iad-updater"})
        with urlopen(request, timeout=12) as response:
            return json.load(response)

    def _download(self, url: str, destination: Path) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_DOWNLOAD_HOSTS:
            raise ValueError("Update download host is not allowed.")
        request = Request(url, headers={"User-Agent": "iad-updater"})
        total = 0
        with urlopen(request, timeout=30) as response, destination.open("wb") as output:
            declared = int(response.headers.get("Content-Length", "0") or 0)
            if declared > MAX_PACKAGE_BYTES:
                raise ValueError("Update package exceeds the size limit.")
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_PACKAGE_BYTES:
                    raise ValueError("Update package exceeds the size limit.")
                output.write(chunk)

    def _read_cache(self) -> dict | None:
        if not self.cache_path.exists():
            return None
        return json.loads(self.cache_path.read_text(encoding="utf-8"))

    def _release_summary(self, release: dict) -> dict:
        assets = {asset["name"]: asset for asset in release.get("assets", [])}
        manifest_asset = assets.get("detector-manifest.json")
        package_name = next((name for name in assets if name.startswith("detector-bundle-") and name.endswith(".zip")), None)
        signature_asset = assets.get("detector-manifest.sig")
        available = bool(manifest_asset and package_name and signature_asset and not release.get("draft"))
        return {
            "checked_at": _utcnow().isoformat(),
            "tag": release.get("tag_name"),
            "name": release.get("name"),
            "notes": release.get("body", ""),
            "report_url": release.get("html_url"),
            "available": available,
            "assets": {
                "manifest": manifest_asset and manifest_asset["browser_download_url"],
                "package": package_name and assets[package_name]["browser_download_url"],
                "signature": signature_asset and signature_asset["browser_download_url"],
            },
        }

    def check(self, force: bool = False) -> dict:
        cached = self._read_cache()
        if cached and not force:
            checked = datetime.fromisoformat(cached["checked_at"])
            if _utcnow() - checked < CHECK_INTERVAL:
                return cached
        release = self.fetch_json(RELEASE_API)
        summary = self._release_summary(release)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    def status(self, check_remote: bool = True) -> dict:
        state = self._state()
        release = None
        error = None
        if check_remote:
            try:
                release = self.check()
            except Exception as exc:
                error = f"Update check unavailable: {type(exc).__name__}"
        available = bool(release and release["available"] and _version_key(str(release["tag"])) > _version_key(state["active_version"]))
        return {
            "app_version": APP_VERSION,
            "current_version": state["active_version"],
            "previous_version": state.get("previous_version"),
            "update_available": available,
            "available_version": release and release.get("tag") if available else None,
            "evaluation_summary": release and release.get("notes") if available else None,
            "report_url": release and release.get("report_url") if available else None,
            "signature_status": "pending_verification" if available else "not_applicable",
            "confirmation_token": self.tokens.issue("apply") if available else None,
            "rollback_token": self.tokens.issue("rollback") if state.get("previous_version") else None,
            "auto_install": False,
            "last_check_error": error,
            "private_corpus": self.corpus.status(),
        }

    def _verify_signature(self, manifest_bytes: bytes, signature: bytes) -> None:
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError as exc:
            raise RuntimeError("Install the 'updates' extra to verify signed updates.") from exc
        public_key = serialization.load_pem_public_key(self.public_key_path.read_bytes())
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("Configured update key is not Ed25519.")
        public_key.verify(base64.b64decode(signature.strip()), manifest_bytes)

    def _safe_extract(self, archive: Path, destination: Path) -> None:
        with zipfile.ZipFile(archive) as bundle:
            total_size = 0
            for member in bundle.infolist():
                target = (destination / member.filename).resolve()
                if destination.resolve() not in target.parents and target != destination.resolve():
                    raise ValueError("Update package contains an unsafe path.")
                # Unix symlinks can otherwise escape the extraction directory.
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Update package contains a symbolic link.")
                total_size += member.file_size
                if member.file_size > MAX_EXTRACTED_BYTES or total_size > MAX_EXTRACTED_BYTES:
                    raise ValueError("Update package exceeds the extracted-size limit.")
            bundle.extractall(destination)

    def apply(self, token: str) -> dict:
        if not self.tokens.consume(token, "apply"):
            raise PermissionError("The one-time update confirmation token is invalid or expired.")
        release = self.check(force=True)
        if not release.get("available"):
            raise ValueError("No installable signed release is available.")
        with tempfile.TemporaryDirectory(prefix="iad-update-") as temp_name:
            temp = Path(temp_name)
            manifest_path = temp / "manifest.json"
            signature_path = temp / "manifest.sig"
            package_path = temp / "bundle.zip"
            self.download(release["assets"]["manifest"], manifest_path)
            self.download(release["assets"]["signature"], signature_path)
            self.download(release["assets"]["package"], package_path)
            manifest_bytes = manifest_path.read_bytes()
            self._verify_signature(manifest_bytes, signature_path.read_bytes())
            manifest = json.loads(manifest_bytes)
            if manifest.get("repository") != REPOSITORY:
                raise ValueError("Update manifest repository does not match.")
            if manifest.get("minimum_app_version") and _version_key(APP_VERSION) < _version_key(manifest["minimum_app_version"]):
                raise ValueError("Update requires a newer application version.")
            actual_hash = hashlib.sha256(package_path.read_bytes()).hexdigest()
            if not secrets.compare_digest(actual_hash, manifest.get("sha256", "")):
                raise ValueError("Update package hash verification failed.")
            if package_path.stat().st_size != int(manifest.get("size", -1)):
                raise ValueError("Update package size does not match the signed manifest.")
            version = str(manifest["version"])
            staging = temp / "extracted"
            staging.mkdir()
            self._safe_extract(package_path, staging)
            candidate_model = LightweightModel.load(staging / "model.json")
            if candidate_model.version != version:
                raise ValueError("Model and manifest versions do not match.")
            validation = self.corpus.validate(self.active_model(), candidate_model)
            if not validation["allowed"]:
                raise ValueError("Candidate failed the local private-corpus acceptance gate.")
            # Self-test before the atomic pointer switch.
            probe = candidate_model.predict({
                "statistical_layer": {"word_count": 100, "predictability_proxy": 40, "burstiness_score": 50},
                "classifier": {"ai_like_writing_risk": 35, "signals": {"formulaic_findings": 1}},
                "industrial_authenticity_engine": {"dimensions": {"decision_density": 65, "specificity": 60}},
            })
            if probe["probability"] is None:
                raise ValueError("Candidate self-test failed.")
            target = self.versions / version
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(staging, target)
            old_state = self._state()
            new_state = {"active_version": version, "previous_version": old_state["active_version"]}
            self._write_state(new_state)
            try:
                health = self.active_model()
                if health.version != version:
                    raise ValueError("Post-switch health check failed.")
            except Exception:
                self._write_state(old_state)
                raise
            return {"installed": True, "current_version": version, "validation": validation, "rolled_back": False}

    def rollback(self, token: str) -> dict:
        if not self.tokens.consume(token, "rollback"):
            raise PermissionError("The one-time rollback confirmation token is invalid or expired.")
        state = self._state()
        previous = state.get("previous_version")
        if not previous:
            raise ValueError("No previous detector version is available.")
        if previous != BUNDLED_DETECTOR_VERSION and not (self.versions / previous / "model.json").exists():
            raise ValueError("The previous detector package is missing.")
        replacement = {"active_version": previous, "previous_version": state["active_version"]}
        self._write_state(replacement)
        try:
            if self.active_model().version != previous:
                raise ValueError("Rollback health check failed.")
        except Exception:
            self._write_state(state)
            raise
        return {"rolled_back": True, "current_version": previous}
