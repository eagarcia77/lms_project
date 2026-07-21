from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request

from .config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Demo token store. Replace with an encrypted database or managed secret store in production.
TOKEN_STORE: dict[str, dict[str, Any]] = {}


def google_is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def build_authorization_url(request: Request) -> str:
    if not google_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Google OAuth no está configurado. Complete GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET.",
        )
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    if settings.google_workspace_domain:
        params["hd"] = settings.google_workspace_domain
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(request: Request, code: str, state: str) -> dict[str, Any]:
    expected = request.session.pop("oauth_state", None)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Estado OAuth inválido.")

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_response.is_error:
            raise HTTPException(status_code=400, detail="Google no pudo completar la autenticación.")
        token_data = token_response.json()
        user_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        user_response.raise_for_status()
        user = user_response.json()

    session_id = secrets.token_urlsafe(32)
    token_data["expires_at"] = (
        datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))
    ).isoformat()
    TOKEN_STORE[session_id] = token_data
    request.session["sid"] = session_id
    request.session["user"] = {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "picture": user.get("picture"),
    }
    return request.session["user"]


def get_access_token(request: Request) -> str:
    sid = request.session.get("sid")
    token = TOKEN_STORE.get(sid or "")
    if not token:
        raise HTTPException(status_code=401, detail="Conecta tu cuenta de Google primero.")
    return str(token["access_token"])


async def google_get(request: Request, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_access_token(request)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="La sesión de Google expiró. Vuelve a conectarla.")
    if response.is_error:
        raise HTTPException(status_code=response.status_code, detail="Google API devolvió un error.")
    return response.json()


async def google_post(
    request: Request, url: str, payload: dict[str, Any], params: dict[str, Any] | None = None
) -> dict[str, Any]:
    token = get_access_token(request)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            url,
            params=params,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="La sesión de Google expiró. Vuelve a conectarla.")
    if response.is_error:
        raise HTTPException(status_code=response.status_code, detail=response.text[:500])
    return response.json()
