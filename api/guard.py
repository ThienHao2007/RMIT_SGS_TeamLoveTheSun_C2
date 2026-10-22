from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from functools import lru_cache, wraps
from pathlib import Path
from typing import ParamSpec, TypeVar

import jwt
from fastapi import HTTPException, Request

JWT_ISSUER = "tidecloak-demo"
JWT_AUDIENCE = "quorum-api"
ADMIN_IDS = frozenset({"admin1", "admin2"})

P = ParamSpec("P")
R = TypeVar("R")


def _keys_dir() -> Path:
    return Path(os.environ.get("QUORUM_KEYS_DIR", "keys"))


@lru_cache(maxsize=2)
def _public_key(admin_id: str) -> bytes:
    if admin_id not in ADMIN_IDS:
        raise ValueError("unknown administrator")
    return (_keys_dir() / f"{admin_id}.pub").read_bytes()


def clear_key_cache() -> None:
    _public_key.cache_clear()


def verify_admin_token(token: str) -> str:
    try:
        unverified = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
        admin_id = unverified.get("sub")
        if not isinstance(admin_id, str):
            raise jwt.InvalidTokenError("missing subject")
        claims = jwt.decode(
            token,
            _public_key(admin_id),
            algorithms=["EdDSA"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["sub", "iat", "exp"]},
        )
    except (OSError, ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(status_code=401, detail="invalid administrator token") from exc

    verified_admin = claims["sub"]
    if verified_admin not in ADMIN_IDS:
        raise HTTPException(status_code=401, detail="invalid administrator token")
    return verified_admin


async def admin_middleware(request: Request, call_next):
    request.state.admin = None
    request.state.auth_error = None
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            request.state.auth_error = "invalid authorization header"
        else:
            try:
                request.state.admin = verify_admin_token(token)
            except HTTPException as exc:
                request.state.auth_error = exc.detail
    return await call_next(request)


def require_admin(request: Request) -> str:
    admin = getattr(request.state, "admin", None)
    if admin is None:
        raise HTTPException(
            status_code=401,
            detail=getattr(request.state, "auth_error", None) or "administrator token required",
        )
    return admin


def quorum_required(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    @wraps(function)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        request = kwargs.get("request")
        if not isinstance(request, Request):
            request = next((arg for arg in args if isinstance(arg, Request)), None)
        if request is None:
            raise RuntimeError("quorum-protected endpoint requires Request")
        admin = require_admin(request)
        from .quorum import authorize_or_enqueue

        return await authorize_or_enqueue(request, admin, function, args, kwargs)

    return wrapper
