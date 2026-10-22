from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ADMINS = ("admin1", "admin2")
ISSUER = "tidecloak-demo"
AUDIENCE = "quorum-api"


def generate_keys(keys_dir: Path, force: bool = False) -> None:
    keys_dir.mkdir(parents=True, exist_ok=True)
    for admin in ADMINS:
        private_path = keys_dir / f"{admin}.pem"
        public_path = keys_dir / f"{admin}.pub"
        if not force and (private_path.exists() or public_path.exists()):
            if private_path.exists() and public_path.exists():
                continue
            raise RuntimeError(f"incomplete keypair for {admin}; use --force to replace it")
        private_key = Ed25519PrivateKey.generate()
        private_path.write_bytes(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        public_path.write_bytes(
            private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        print(f"generated {admin} keypair")


def create_jwt(admin: str, keys_dir: Path, lifetime_minutes: int = 60) -> str:
    if admin not in ADMINS:
        raise ValueError(f"unknown administrator: {admin}")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": admin,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=lifetime_minutes),
        },
        (keys_dir / f"{admin}.pem").read_bytes(),
        algorithm="EdDSA",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo Ed25519 administrators and JWTs")
    parser.add_argument("--keys-dir", type=Path, default=Path("keys"))
    parser.add_argument("--force", action="store_true", help="replace existing keypairs")
    parser.add_argument("--tokens", action="store_true", help="print short-lived JWTs after generation")
    parser.add_argument("--lifetime-minutes", type=int, default=60)
    args = parser.parse_args()

    generate_keys(args.keys_dir, args.force)
    if args.tokens:
        for admin in ADMINS:
            print(f"{admin}={create_jwt(admin, args.keys_dir, args.lifetime_minutes)}")


if __name__ == "__main__":
    main()
