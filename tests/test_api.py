import json

from conftest import approval_signature, auth
from fastapi import HTTPException


def test_jwt_validation_accepts_valid_and_rejects_tampered(system):
    assert system["guard"].verify_admin_token(system["tokens"]["admin1"]) == "admin1"
    token = system["tokens"]["admin1"]
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    try:
        system["guard"].verify_admin_token(tampered)
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("tampered JWT was accepted")


def test_multisig_requires_second_admin_with_valid_signature(system):
    client = system["client"]
    blocked = client.post("/limits", json={"value": 1000}, headers=auth(system, "admin1"))
    request_id = blocked.json()["request_id"]
    pending = client.get("/quorum/pending", headers=auth(system, "admin2")).json()[0]

    same_admin = client.post(
        "/quorum/approve",
        json={"request_id": request_id, "signature": "invalid"},
        headers=auth(system, "admin1"),
    )
    assert same_admin.status_code == 403

    invalid = client.post(
        "/quorum/approve",
        json={"request_id": request_id, "signature": "invalid"},
        headers=auth(system, "admin2"),
    )
    assert invalid.status_code == 403

    approved = client.post(
        "/quorum/approve",
        json={"request_id": request_id, "signature": approval_signature(system, pending)},
        headers=auth(system, "admin2"),
    )
    assert approved.status_code == 200
    assert approved.json() == {"status": "approved"}


def test_guard_blocks_single_admin(system):
    response = system["client"].post(
        "/limits", json={"value": 1000}, headers=auth(system, "admin1")
    )
    assert response.status_code == 429
    assert response.json()["error"] == "Quorum required"
    assert response.json()["request_id"]


def test_guard_allows_after_quorum(system):
    client = system["client"]
    first = client.post("/limits", json={"value": 1000}, headers=auth(system, "admin1"))
    pending = client.get("/quorum/pending", headers=auth(system, "admin2")).json()[0]
    approved = client.post(
        "/quorum/approve",
        json={
            "request_id": first.json()["request_id"],
            "signature": approval_signature(system, pending),
        },
        headers=auth(system, "admin2"),
    )
    assert approved.json() == {"status": "approved"}

    repeated = client.post("/limits", json={"value": 1000}, headers=auth(system, "admin1"))
    assert repeated.status_code == 200
    assert repeated.json() == {"result": "limit set to 1000"}


def test_direct_policy_edit_returns_403(system):
    client = system["client"]
    assert client.get("/policy").status_code == 200
    policy = json.loads(system["policy_path"].read_text(encoding="utf-8"))
    policy["limits"]["value"] = 9999
    system["policy_path"].write_text(json.dumps(policy), encoding="utf-8")

    response = client.get("/policy")
    assert response.status_code == 403
    assert response.json() == {"error": "policy immutable without quorum"}
