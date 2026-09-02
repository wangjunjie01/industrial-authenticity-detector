"""Sign the exact canonical manifest bytes with the protected CI Ed25519 key."""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path


def sign(manifest: Path, output: Path, private_pem: bytes) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("UPDATE_SIGNING_PRIVATE_KEY must contain an Ed25519 private key.")
    output.write_bytes(base64.b64encode(key.sign(manifest.read_bytes())) + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    private_key = os.environ.get("UPDATE_SIGNING_PRIVATE_KEY")
    if not private_key:
        raise SystemExit("UPDATE_SIGNING_PRIVATE_KEY is not configured.")
    sign(args.manifest, args.output, private_key.encode())


if __name__ == "__main__":
    main()
