from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .guard import ADMIN_IDS, _public_key, quorum_required, require_admin

router = APIRouter()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_policy_root(policy: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(policy)).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PolicyTamperedError(RuntimeError):
    pass


@dataclass(frozen=True)
class PendingRequest:
    id: str
    requester: str
    endpoint: str
    payload: dict[str, Any]
    payload_hash: str
    created_at: str


class QuorumStore:
    def __init__(self, db_path: Path, policy_path: Path):
        self.db_path = db_path
        self.policy_path = policy_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()
        self._initialize_policy()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def database(self):
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self.database() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS policy_versions (
                    version INTEGER PRIMARY KEY,
                    root TEXT NOT NULL UNIQUE,
                    document TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_requests (
                    id TEXT PRIMARY KEY,
                    requester TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(requester, endpoint, payload_hash)
                );
                CREATE TABLE IF NOT EXISTS approved_grants (
                    requester TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    result TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    PRIMARY KEY(requester, endpoint, payload_hash)
                );
                CREATE TABLE IF NOT EXISTS settings (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    actor TEXT,
                    request_id TEXT,
                    endpoint TEXT,
                    timestamp TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                """
            )

    def _initialize_policy(self) -> None:
        with self.database() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM policy_versions").fetchone()
            if row["count"] == 0:
                policy = self._read_policy_file()
                version = int(policy.get("version", 1))
                connection.execute(
                    "INSERT INTO policy_versions(version, root, document, created_at) VALUES (?, ?, ?, ?)",
                    (version, compute_policy_root(policy), canonical_json(policy).decode(), _utc_now()),
                )

    def _read_policy_file(self) -> dict[str, Any]:
        value = json.loads(self.policy_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError("policy must be a JSON object")
        return value

    @staticmethod
    def append_audit(
        connection: sqlite3.Connection, event: str, actor: str | None = None,
        request_id: str | None = None, endpoint: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO audit_events(event, actor, request_id, endpoint, timestamp, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event, actor, request_id, endpoint, _utc_now(), canonical_json(detail or {}).decode()),
        )

    def current_policy(self) -> dict[str, Any]:
        try:
            policy = self._read_policy_file()
            actual_root = compute_policy_root(policy)
        except (OSError, ValueError, TypeError):
            policy = None
            actual_root = None
        with self.database() as connection:
            row = connection.execute(
                "SELECT root FROM policy_versions ORDER BY version DESC LIMIT 1"
            ).fetchone()
            intact = row is not None and row["root"] == actual_root
            incident = connection.execute(
                "SELECT value FROM settings WHERE name='policy_tamper_active'"
            ).fetchone()
            active = incident is not None and incident["value"] == "1"
            if not intact and not active:
                self.append_audit(
                    connection, "policy_tamper", endpoint="/policy",
                    detail={"expected_root": row["root"] if row else None, "actual_root": actual_root},
                )
            if active != (not intact):
                connection.execute(
                    "INSERT OR REPLACE INTO settings(name, value) VALUES ('policy_tamper_active', ?)",
                    ("0" if intact else "1",),
                )
        if not intact:
            raise PolicyTamperedError("policy immutable without quorum")
        return policy

    def update_policy(self, policy: dict[str, Any]) -> tuple[int, str]:
        self.current_policy()
        with self.database() as connection:
            current = connection.execute(
                "SELECT version FROM policy_versions ORDER BY version DESC LIMIT 1"
            ).fetchone()
            version = int(current["version"]) + 1
        updated = dict(policy)
        updated["version"] = version
        root = compute_policy_root(updated)
        previous = self.policy_path.read_bytes()
        temporary = self.policy_path.with_suffix(self.policy_path.suffix + ".tmp")
        temporary.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.policy_path)
        try:
            with self.database() as connection:
                connection.execute(
                    "INSERT INTO policy_versions(version, root, document, created_at) VALUES (?, ?, ?, ?)",
                    (version, root, canonical_json(updated).decode(), _utc_now()),
                )
        except Exception:
            self.policy_path.write_bytes(previous)
            raise
        return version, root

    def create_pending(self, requester: str, endpoint: str, payload: dict[str, Any]) -> PendingRequest:
        payload_hash = hashlib.sha256(canonical_json(payload)).hexdigest()
        with self.database() as connection:
            row = connection.execute(
                "SELECT * FROM pending_requests WHERE requester=? AND endpoint=? AND payload_hash=?",
                (requester, endpoint, payload_hash),
            ).fetchone()
            if row is None:
                request_id = str(uuid4())
                created_at = _utc_now()
                connection.execute(
                    "INSERT INTO pending_requests(id, requester, endpoint, payload, payload_hash, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (request_id, requester, endpoint, canonical_json(payload).decode(), payload_hash, created_at),
                )
                self.append_audit(
                    connection, "request_enqueued", requester, request_id, endpoint,
                    {"payload_hash": payload_hash},
                )
                return PendingRequest(request_id, requester, endpoint, payload, payload_hash, created_at)
        return self._pending_from_row(row)

    def list_pending(self) -> list[PendingRequest]:
        with self.database() as connection:
            rows = connection.execute(
                "SELECT * FROM pending_requests ORDER BY created_at, id"
            ).fetchall()
        return [self._pending_from_row(row) for row in rows]

    def get_pending(self, request_id: str) -> PendingRequest | None:
        with self.database() as connection:
            row = connection.execute(
                "SELECT * FROM pending_requests WHERE id=?", (request_id,)
            ).fetchone()
        return None if row is None else self._pending_from_row(row)

    @staticmethod
    def _pending_from_row(row: sqlite3.Row) -> PendingRequest:
        return PendingRequest(
            row["id"], row["requester"], row["endpoint"], json.loads(row["payload"]),
            row["payload_hash"], row["created_at"],
        )

    def approval_message(self, pending: PendingRequest) -> bytes:
        return canonical_json(
            {
                "request_id": pending.id,
                "requester": pending.requester,
                "endpoint": pending.endpoint,
                "payload_hash": pending.payload_hash,
                "created_at": pending.created_at,
            }
        )

    def get_grant(self, requester: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        payload_hash = hashlib.sha256(canonical_json(payload)).hexdigest()
        with self.database() as connection:
            row = connection.execute(
                "SELECT result FROM approved_grants WHERE requester=? AND endpoint=? AND payload_hash=?",
                (requester, endpoint, payload_hash),
            ).fetchone()
        return None if row is None else json.loads(row["result"])

    def approve(self, pending: PendingRequest, approver: str, result: dict[str, Any]) -> None:
        with self.database() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO approved_grants"
                "(requester, endpoint, payload_hash, result, approved_by, approved_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    pending.requester,
                    pending.endpoint,
                    pending.payload_hash,
                    canonical_json(result).decode(),
                    approver,
                    _utc_now(),
                ),
            )
            connection.execute("DELETE FROM pending_requests WHERE id=?", (pending.id,))
            self.append_audit(
                connection, "request_approved", approver, pending.id, pending.endpoint,
                {"requester": pending.requester, "result": result},
            )

    def set_limit(self, value: int) -> None:
        with self.database() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO settings(name, value) VALUES ('limit', ?)", (str(value),)
            )


STORE = QuorumStore(
    Path(os.environ.get("QUORUM_DB_PATH", "quorum.db")),
    Path(os.environ.get("QUORUM_POLICY_PATH", "policy.json")),
)


class ApprovalBody(BaseModel):
    request_id: str
    signature: str


def _payload_from_call(kwargs: dict[str, Any]) -> dict[str, Any]:
    payload = kwargs.get("payload", {})
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    raise HTTPException(status_code=400, detail="request payload must be an object")


async def authorize_or_enqueue(
    request: Request,
    admin: str,
    function: Callable[..., Awaitable[Any]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
):
    payload = _payload_from_call(kwargs)
    grant = STORE.get_grant(admin, request.url.path, payload)
    if grant is not None:
        return grant
    pending = STORE.create_pending(admin, request.url.path, payload)
    return JSONResponse(
        status_code=429,
        content={"error": "Quorum required", "request_id": pending.id},
    )


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_approval_signature(pending: PendingRequest, approver: str, signature: str) -> None:
    if approver == pending.requester:
        raise HTTPException(status_code=403, detail="a second administrator must approve")
    try:
        public_key = serialization.load_pem_public_key(_public_key(approver))
        public_key.verify(_b64url_decode(signature), STORE.approval_message(pending))
    except (OSError, ValueError, TypeError, InvalidSignature) as exc:
        raise HTTPException(status_code=403, detail="invalid approval signature") from exc


def _execute_pending(pending: PendingRequest) -> dict[str, Any]:
    if pending.endpoint == "/limits":
        value = pending.payload.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise HTTPException(status_code=422, detail="limit must be a positive integer")
        STORE.set_limit(value)
        return {"result": f"limit set to {value}"}
    if pending.endpoint == "/policy/update":
        policy = pending.payload.get("policy")
        if not isinstance(policy, dict):
            raise HTTPException(status_code=422, detail="policy must be an object")
        version, root = STORE.update_policy(policy)
        return {"result": "policy updated", "version": version, "root": root}
    raise HTTPException(status_code=400, detail="unsupported pending endpoint")


@router.get("/policy")
async def get_policy():
    try:
        return STORE.current_policy()
    except PolicyTamperedError:
        return JSONResponse(status_code=403, content={"error": "policy immutable without quorum"})


@router.get("/quorum/pending")
async def list_pending(request: Request):
    require_admin(request)
    return [
        {
            "id": pending.id,
            "admin": pending.requester,
            "endpoint": pending.endpoint,
            "payload": pending.payload,
            "timestamp": pending.created_at,
            "approval_payload": base64.urlsafe_b64encode(STORE.approval_message(pending)).decode().rstrip("="),
        }
        for pending in STORE.list_pending()
    ]


@router.post("/quorum/approve")
async def approve(request: Request, body: ApprovalBody):
    approver = None
    pending = None
    try:
        approver = require_admin(request)
        pending = STORE.get_pending(body.request_id)
        if pending is None:
            raise HTTPException(status_code=404, detail="pending request not found")
        verify_approval_signature(pending, approver, body.signature)
        result = _execute_pending(pending)
        STORE.approve(pending, approver, result)
    except PolicyTamperedError as exc:
        with STORE.database() as connection:
            STORE.append_audit(
                connection, "approval_rejected", approver, body.request_id,
                pending.endpoint if pending else None, {"reason": str(exc)},
            )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException as exc:
        with STORE.database() as connection:
            STORE.append_audit(
                connection, "approval_rejected", approver, body.request_id,
                pending.endpoint if pending else None, {"reason": exc.detail},
            )
        raise
    return {"status": "approved"}


@router.post("/limits")
@quorum_required
async def set_limits(request: Request, payload: dict[str, Any]):
    value = payload.get("value")
    return {"result": f"limit set to {value}"}


@router.post("/policy/update")
@quorum_required
async def update_policy(request: Request, payload: dict[str, Any]):
    return {"result": "policy updated"}


@router.get("/overview")
async def overview(request: Request):
    require_admin(request)
    try:
        STORE.current_policy()
        integrity = True
    except PolicyTamperedError:
        integrity = False
    with STORE.database() as connection:
        pending_count = connection.execute("SELECT COUNT(*) FROM pending_requests").fetchone()[0]
        approved_count = connection.execute("SELECT COUNT(*) FROM approved_grants").fetchone()[0]
        policy = connection.execute(
            "SELECT version, root FROM policy_versions ORDER BY version DESC LIMIT 1"
        ).fetchone()
        limit = connection.execute("SELECT value FROM settings WHERE name='limit'").fetchone()
    return {
        "pending_count": pending_count, "approved_count": approved_count,
        "policy_version": policy["version"] if policy else None,
        "policy_root": policy["root"] if policy else None,
        "policy_integrity": integrity, "limit": int(limit["value"]) if limit else None,
    }


@router.get("/policies")
async def policies(request: Request):
    require_admin(request)
    try:
        current = STORE.current_policy()
    except PolicyTamperedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    with STORE.database() as connection:
        versions = connection.execute(
            "SELECT version, root, created_at FROM policy_versions ORDER BY version DESC"
        ).fetchall()
    return {"current": current, "versions": [dict(row) for row in versions]}


@router.get("/audit")
async def audit(request: Request, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    require_admin(request)
    with STORE.database() as connection:
        total = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        rows = connection.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()
    items = [{**dict(row), "detail": json.loads(row["detail"])} for row in rows]
    return {"items": items, "total": total}


@router.get("/administrators")
async def administrators(request: Request):
    require_admin(request)
    items = []
    for admin_id in sorted(ADMIN_IDS):
        try:
            public_key = serialization.load_pem_public_key(_public_key(admin_id))
            encoded = public_key.public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            fingerprint = hashlib.sha256(encoded).hexdigest()
        except (OSError, ValueError, TypeError):
            fingerprint = None
        items.append({
            "id": admin_id, "public_key_fingerprint": fingerprint,
            "key_available": fingerprint is not None,
        })
    return {"items": items, "quorum": 2}
