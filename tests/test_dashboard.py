import hashlib
import json

import pytest
from conftest import approval_signature, auth
from cryptography.hazmat.primitives import serialization


@pytest.mark.parametrize("path", ["/overview", "/policies", "/audit", "/administrators"])
def test_dashboard_requires_authentication(system, path):
    client = system["client"]
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get(path, headers=auth(system, "admin1")).status_code == 200


def queue_and_approve(system, endpoint, payload):
    client = system["client"]
    queued = client.post(endpoint, json=payload, headers=auth(system, "admin1"))
    assert queued.status_code == 429
    pending = client.get("/quorum/pending", headers=auth(system, "admin2")).json()[0]
    response = client.post(
        "/quorum/approve", headers=auth(system, "admin2"),
        json={"request_id": queued.json()["request_id"], "signature": approval_signature(system, pending)},
    )
    assert response.status_code == 200
    return queued.json()["request_id"]


def test_overview_uses_persisted_state_and_audit_survives_reopen(system):
    client = system["client"]
    headers = auth(system, "admin1")
    initial = client.get("/overview", headers=headers).json()
    assert initial["pending_count"] == initial["approved_count"] == 0
    assert initial["limit"] is None
    assert initial["policy_integrity"] is True
    assert initial["policy_version"] == 1
    assert initial["policy_root"] == system["quorum"].compute_policy_root(
        json.loads(system["policy_path"].read_text())
    )
    request_id = queue_and_approve(system, "/limits", {"value": 321})
    overview = client.get("/overview", headers=headers).json()
    assert overview["limit"] == 321
    assert overview["approved_count"] == 1
    assert overview["pending_count"] == 0
    store = system["quorum"].STORE
    system["quorum"].STORE = system["quorum"].QuorumStore(store.db_path, store.policy_path)
    audit = client.get("/audit", headers=headers).json()
    assert audit["total"] == 2
    assert [item["event"] for item in audit["items"]] == ["request_approved", "request_enqueued"]
    assert [item["actor"] for item in audit["items"]] == ["admin2", "admin1"]
    assert all(item["request_id"] == request_id for item in audit["items"])
    assert all(item["endpoint"] == "/limits" and item["timestamp"] for item in audit["items"])
    page = client.get("/audit?limit=1&offset=1", headers=headers).json()
    assert page == {"items": [audit["items"][1]], "total": 2}
    assert client.get("/audit?offset=2", headers=headers).json()["items"] == []


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "limit=abc"])
def test_audit_rejects_invalid_pagination(system, query):
    assert system["client"].get("/audit?" + query, headers=auth(system, "admin1")).status_code == 422


def test_duplicate_enqueue_and_rejected_approvals_are_audited(system):
    client = system["client"]
    headers = auth(system, "admin1")
    first = client.post("/limits", json={"value": 42}, headers=headers).json()
    assert client.post("/limits", json={"value": 42}, headers=headers).json() == first
    assert client.get("/overview", headers=headers).json()["pending_count"] == 1
    for admin in ("admin1", "admin2"):
        rejected = client.post(
            "/quorum/approve", headers=auth(system, admin),
            json={"request_id": first["request_id"], "signature": "invalid"},
        )
        assert rejected.status_code == 403
    missing = client.post(
        "/quorum/approve", headers=headers,
        json={"request_id": "missing", "signature": "invalid"},
    )
    assert missing.status_code == 404
    events = client.get("/audit", headers=headers).json()["items"]
    assert [item["event"] for item in events].count("request_enqueued") == 1
    assert [item["event"] for item in events].count("approval_rejected") == 3
    assert all("signature" not in item["detail"] for item in events)
    assert client.get("/overview", headers=headers).json()["limit"] is None


def test_policies_history_changes_only_after_quorum(system):
    client = system["client"]
    headers = auth(system, "admin1")
    before = client.get("/policies", headers=headers).json()
    policy = {"limits": {"value": 987}, "sensitive_endpoints": ["/limits", "/policy/update"]}
    queued = client.post("/policy/update", json={"policy": policy}, headers=headers)
    assert queued.status_code == 429
    assert client.get("/policies", headers=headers).json() == before
    queue_and_approve(system, "/policy/update", {"policy": policy})
    after = client.get("/policies", headers=headers).json()
    assert after["current"] == {**policy, "version": 2}
    assert [version["version"] for version in after["versions"]] == [2, 1]
    assert after["versions"][1] == before["versions"][0]
    assert after["versions"][0]["root"] == system["quorum"].compute_policy_root(after["current"])


@pytest.mark.parametrize("tampered", ['{"version": 99}', 'invalid JSON', '[]'])
def test_tamper_is_reported_without_poll_flood_and_survives_restart(system, tampered):
    client = system["client"]
    headers = auth(system, "admin1")
    original = system["policy_path"].read_text()
    system["policy_path"].write_text(tampered)
    for _ in range(3):
        assert client.get("/overview", headers=headers).json()["policy_integrity"] is False
        assert client.get("/policies", headers=headers).status_code == 403
        assert client.get("/policy").status_code == 403
    store = system["quorum"].STORE
    system["quorum"].STORE = system["quorum"].QuorumStore(store.db_path, store.policy_path)
    assert client.get("/overview", headers=headers).json()["policy_integrity"] is False
    assert client.get("/audit", headers=headers).json()["total"] == 1
    system["policy_path"].write_text(original)
    assert client.get("/overview", headers=headers).json()["policy_integrity"] is True
    system["policy_path"].write_text(tampered)
    assert client.get("/overview", headers=headers).json()["policy_integrity"] is False
    assert client.get("/audit", headers=headers).json()["total"] == 2


def test_administrators_exposes_only_public_fingerprints(system):
    response = system["client"].get("/administrators", headers=auth(system, "admin1"))
    data = response.json()
    assert data["quorum"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        public = serialization.load_pem_public_key((system["keys_dir"] / (item["id"] + ".pub")).read_bytes())
        fingerprint = hashlib.sha256(public.public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
        )).hexdigest()
        assert item == {"id": item["id"], "public_key_fingerprint": fingerprint, "key_available": True}
    assert "PRIVATE" not in response.text and "PUBLIC KEY" not in response.text
    system["guard"].clear_key_cache()
    (system["keys_dir"] / "admin2.pub").unlink()
    missing = system["client"].get("/administrators", headers=auth(system, "admin1")).json()["items"][1]
    assert missing == {"id": "admin2", "public_key_fingerprint": None, "key_available": False}


@pytest.mark.parametrize("root", ["overview", "policies", "audit", "administrators"])
def test_unknown_dashboard_api_paths_are_not_spa_html(system, root):
    response = system["client"].get(f"/{root}/missing", headers=auth(system, "admin1"))
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_policy_approval_rejects_tamper_and_keeps_request_pending(system):
    client = system["client"]
    headers = auth(system, "admin1")
    queued = client.post("/policy/update", json={"policy": {"limits": {"value": 5}}}, headers=headers)
    pending = client.get("/quorum/pending", headers=auth(system, "admin2")).json()[0]
    system["policy_path"].write_text("not JSON")
    rejected = client.post(
        "/quorum/approve", headers=auth(system, "admin2"),
        json={"request_id": queued.json()["request_id"], "signature": approval_signature(system, pending)},
    )
    assert rejected.status_code == 403
    overview = client.get("/overview", headers=headers).json()
    assert overview["pending_count"] == 1
    assert overview["approved_count"] == 0
    assert overview["policy_version"] == 1
    events = client.get("/audit", headers=headers).json()["items"]
    assert [item["event"] for item in events] == [
        "approval_rejected", "policy_tamper", "request_enqueued",
    ]


def test_unauthenticated_approval_is_rejected_and_audited(system):
    client = system["client"]
    rejected = client.post("/quorum/approve", json={"request_id": "unknown", "signature": "secret"})
    assert rejected.status_code == 401
    event = client.get("/audit", headers=auth(system, "admin1")).json()["items"][0]
    assert event["event"] == "approval_rejected"
    assert event["actor"] is None
    assert "secret" not in json.dumps(event)
