"""
auth.py — Clerk JWT verification middleware for FastAPI.

Verifies the Bearer token in Authorization header using Clerk's JWKS endpoint.
Attaches user_id and email to request.state for use in route handlers.
"""

from __future__ import annotations

import os
import httpx

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "")

_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch and cache Clerk's public JWKS (refreshed on process restart)."""
    if not CLERK_JWKS_URL:
        raise RuntimeError("CLERK_JWKS_URL not set in environment")
    resp = httpx.get(CLERK_JWKS_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _verify_token(token: str) -> dict:
    """
    Decode and verify a Clerk JWT.
    Returns the decoded payload on success.
    Raises HTTPException 401 on failure.
    """
    try:
        jwks = _get_jwks()
        # python-jose accepts JWKS dict directly
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk tokens don't use standard aud
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    FastAPI dependency that extracts and verifies the Clerk JWT.

    Usage:
        @router.get("/protected")
        async def route(user: dict = Depends(get_current_user)):
            user_id = user["sub"]
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _verify_token(credentials.credentials)
    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email", ""),
        "org_id": payload.get("org_id", ""),
        "role": payload.get("org_role", "member"),
    }


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency that requires the user to have admin role.
    """
    if user.get("role") not in ("admin", "org:admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
