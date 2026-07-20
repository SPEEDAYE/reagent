"""Authentication and project-ownership helpers.

The API can receive identity in either of two production-safe ways:

1. a token signed with ``AUTH_TOKEN_SECRET``; or
2. identity headers injected by a trusted API gateway when
   ``AUTH_TRUST_PROXY_HEADERS=1``.

During migration, ``AUTH_REQUIRED=0`` keeps legacy calls available.  If an
authenticated identity is present, ownership is still enforced immediately.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings
from backend.db.mongo import projects_col


_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str = ""
    roles: tuple[str, ...] = ()


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _claim_user_id(claims: dict) -> str:
    value = (
        claims.get("userCode")
        or claims.get("user_code")
        or claims.get("user_id")
        or claims.get("sub")
    )
    return str(value or "").strip()


def _claims_to_user(claims: dict) -> CurrentUser:
    user_id = _claim_user_id(claims)
    if not user_id:
        raise ValueError("token has no user identity claim")

    expires_at = claims.get("exp") or claims.get("expiresAt")
    if expires_at and float(expires_at) < time.time():
        raise ValueError("token has expired")

    raw_roles = claims.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [item.strip() for item in raw_roles.split(",") if item.strip()]
    return CurrentUser(
        user_id=user_id,
        username=str(claims.get("username") or ""),
        roles=tuple(str(role) for role in raw_roles),
    )


def _decode_two_part_token(token: str, secret: str) -> dict:
    """Verify the gateway's ``base64(payload).signature`` token format.

    The signature may be URL-safe base64 or hexadecimal HMAC-SHA256.
    """

    payload_part, signature_part = token.split(".", 1)
    expected = hmac.new(
        secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256
    ).digest()
    valid = False
    try:
        valid = hmac.compare_digest(_b64decode(signature_part), expected)
    except Exception:
        pass
    if not valid:
        valid = hmac.compare_digest(signature_part.lower(), expected.hex())
    if not valid:
        raise ValueError("invalid token signature")
    return json.loads(_b64decode(payload_part))


def decode_access_token(token: str) -> CurrentUser:
    if not settings.AUTH_TOKEN_SECRET:
        raise ValueError("AUTH_TOKEN_SECRET is not configured")

    parts = token.split(".")
    if len(parts) == 3:
        claims = jwt.decode(
            token,
            settings.AUTH_TOKEN_SECRET,
            algorithms=[settings.AUTH_TOKEN_ALGORITHM],
            options={"require": []},
        )
    elif len(parts) == 2:
        claims = _decode_two_part_token(token, settings.AUTH_TOKEN_SECRET)
    else:
        raise ValueError("unsupported token format")
    return _claims_to_user(claims)


def _user_from_proxy_headers(request: Request) -> CurrentUser | None:
    if not settings.AUTH_TRUST_PROXY_HEADERS:
        return None
    # Merely trusting X-User-* headers would let a caller impersonate anyone
    # whenever the backend is reachable directly. Require a gateway-only
    # shared secret as proof that the headers were injected by our proxy.
    proxy_secret = request.headers.get(settings.AUTH_PROXY_SECRET_HEADER, "")
    if not settings.AUTH_PROXY_SHARED_SECRET or not hmac.compare_digest(
        proxy_secret, settings.AUTH_PROXY_SHARED_SECRET
    ):
        return None
    user_id = request.headers.get(settings.AUTH_USER_HEADER, "").strip()
    if not user_id:
        return None
    username = request.headers.get(settings.AUTH_USERNAME_HEADER, "").strip()
    roles_value = request.headers.get(settings.AUTH_ROLES_HEADER, "")
    roles = tuple(item.strip() for item in roles_value.split(",") if item.strip())
    return CurrentUser(user_id=user_id, username=username, roles=roles)


async def optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser | None:
    proxy_user = _user_from_proxy_headers(request)
    if proxy_user:
        return proxy_user

    if credentials:
        try:
            return decode_access_token(credentials.credentials)
        except Exception as exc:
            if settings.AUTH_REQUIRED:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired access token",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc
            # Compatibility mode deliberately ignores tokens it cannot yet
            # verify. Ownership becomes mandatory when AUTH_REQUIRED is enabled.
            return None

    if settings.AUTH_REQUIRED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None


async def require_current_user(
    user: CurrentUser | None = Depends(optional_current_user),
) -> CurrentUser:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def resolve_user_id(user: CurrentUser | None, legacy_user_id: str | None) -> str:
    """Resolve a user id while preventing authenticated identity spoofing."""

    legacy = str(legacy_user_id or "").strip()
    if user:
        if legacy and legacy != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="user_id does not match authenticated user",
            )
        return user.user_id
    if legacy and not settings.AUTH_REQUIRED:
        return legacy
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authenticated user identity is required",
    )


async def require_project_owner(
    project_id: str, user: CurrentUser | None
) -> dict:
    """Return a project only when it belongs to the authenticated user.

    A 404 is used for both missing and foreign projects so callers cannot use
    this endpoint to discover another user's project ids.
    """

    query = {"project_id": project_id}
    if user:
        query["user_id"] = user.user_id
    elif settings.AUTH_REQUIRED:
        raise HTTPException(status_code=401, detail="Authentication required")

    project = await projects_col().find_one(query, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
