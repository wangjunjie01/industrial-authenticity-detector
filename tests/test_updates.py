import base64
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile

import industrial_authenticity.updates as updates_module
from industrial_authenticity.updates import BUNDLED_DETECTOR_VERSION, REPOSITORY, UpdateManager

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


@unittest.skipUnless(HAS_CRYPTOGRAPHY, "cryptography extra is not installed")
class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private_key = Ed25519PrivateKey.generate()
        public = self.private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.public_key = self.root / "public.pem"
        self.public_key.write_bytes(public)
        self.assets = self.root / "assets"
        self.assets.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def _release(self, version="2026.10.0", tamper=False, unsafe=False):
        bundled = Path(__file__).parents[1] / "src/industrial_authenticity/models/bundled-model.json"
        model = json.loads(bundled.read_text(encoding="utf-8"))
        model["version"] = version
        package = self.assets / f"detector-bundle-{version}.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("../escape.txt" if unsafe else "model.json", json.dumps(model))
        manifest = {"repository": REPOSITORY, "version": version, "minimum_app_version": "0.2.0", "sha256": hashlib.sha256(package.read_bytes()).hexdigest(), "size": package.stat().st_size}
        manifest_path = self.assets / "detector-manifest.json"
        manifest_path.write_bytes(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
        signature = self.assets / "detector-manifest.sig"
        signature.write_bytes(base64.b64encode(self.private_key.sign(manifest_path.read_bytes())))
        if tamper:
            package.write_bytes(package.read_bytes() + b"tamper")
        assets = []
        for path in (manifest_path, signature, package):
            assets.append({"name": path.name, "browser_download_url": f"https://github.com/test/{path.name}"})
        return {"tag_name": version, "name": version, "body": "Approved benchmark", "html_url": "https://github.com/report", "draft": False, "assets": assets}

    def _manager(self, release):
        def download(url, destination):
            shutil.copyfile(self.assets / url.rsplit("/", 1)[-1], destination)
        return UpdateManager(self.root / "state", fetch_json=lambda _: release, download=download, public_key_path=self.public_key)

    def test_signed_apply_and_one_time_token_then_rollback(self):
        manager = self._manager(self._release())
        status = manager.status()
        result = manager.apply(status["confirmation_token"])
        self.assertTrue(result["installed"])
        self.assertEqual(manager.active_model().version, "2026.10.0")
        with self.assertRaises(PermissionError):
            manager.apply(status["confirmation_token"])
        rollback = manager.status(check_remote=False)
        result = manager.rollback(rollback["rollback_token"])
        self.assertEqual(result["current_version"], BUNDLED_DETECTOR_VERSION)

    def test_tampered_package_is_rejected(self):
        manager = self._manager(self._release(tamper=True))
        with self.assertRaisesRegex(ValueError, "hash"):
            manager.apply(manager.status()["confirmation_token"])

    def test_unsafe_archive_path_is_rejected(self):
        manager = self._manager(self._release(unsafe=True))
        with self.assertRaisesRegex(ValueError, "unsafe path"):
            manager.apply(manager.status()["confirmation_token"])

    def test_oversized_extracted_archive_is_rejected(self):
        archive = self.root / "large.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("model.json", b"x" * 1024)
        manager = self._manager(self._release())
        destination = self.root / "extract-large"
        destination.mkdir()
        with mock.patch.object(updates_module, "MAX_EXTRACTED_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "extracted-size"):
                manager._safe_extract(archive, destination)

    def test_symbolic_link_archive_member_is_rejected(self):
        archive = self.root / "symlink.zip"
        member = zipfile.ZipInfo("model.json")
        member.create_system = 3
        member.external_attr = 0o120777 << 16
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(member, "outside")
        manager = self._manager(self._release())
        destination = self.root / "extract-symlink"
        destination.mkdir()
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            manager._safe_extract(archive, destination)

    def test_bad_signature_is_rejected(self):
        release = self._release()
        (self.assets / "detector-manifest.sig").write_bytes(base64.b64encode(b"x" * 64))
        manager = self._manager(release)
        with self.assertRaises(Exception):
            manager.apply(manager.status()["confirmation_token"])

    def test_no_release_has_no_confirmation_token(self):
        manager = UpdateManager(self.root / "empty", fetch_json=lambda _: {"assets": [], "tag_name": "v0.1.0"}, public_key_path=self.public_key)
        status = manager.status()
        self.assertFalse(status["update_available"])
        self.assertIsNone(status["confirmation_token"])


if __name__ == "__main__":
    unittest.main()
