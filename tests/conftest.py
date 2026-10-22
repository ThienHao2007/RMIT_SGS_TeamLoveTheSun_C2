from __future__ import annotations

import base64
import importlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from scripts.gen_keys import create_jwt, generate_keys


@pytest.fixture
def system(tmp_path, monkeypatch):
    keys_dir = tmp_path / "keys"
    policy_path = tmp_path / "policy.json"
    db_path = tmp_path / "quorum.db"
    generate_keys(keys_dir)
    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "sensitive_endpoints": ["/limits", "/policy/update"],
                "limits": {"value": 100},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUORUM_KEYS_DIR", str(keys_dir))
    monkeypatch.setenv("QUORUM_POLICY_PATH", str(policy_path))
    monkeypatch.setenv("QUORUM_DB_PATH", str(db_path))

    import api.guard
    import api.main
    import api.quorum

    importlib.reload(api.guard)
    importlib.reload(api.quorum)
    importlib.reload(api.main)

    client = TestClient(api.main.app)
    yield {
        "client": client,
        "guard": api.guard,
        "quorum": api.quorum,
        "keys_dir": keys_dir,
        "policy_path": policy_path,
        "tokens": {
            admin: create_jwt(admin, keys_dir, lifetime_minutes=5)
            for admin in ("admin1", "admin2")
        },
    }
    client.close()


def auth(system, admin):
    return {"Authorization": f"Bearer {system['tokens'][admin]}"}


def approval_signature(system, pending, admin="admin2"):
    encoded = pending["approval_payload"]
    message = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    private_key = serialization.load_pem_private_key(
        (system["keys_dir"] / f"{admin}.pem").read_bytes(), password=None
    )
    return base64.urlsafe_b64encode(private_key.sign(message)).decode().rstrip("=")
