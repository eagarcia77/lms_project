from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import connection, initialize_database
from .google_api import (
    TOKEN_STORE,
    build_authorization_url,
    exchange_code,
    google_get,
    google_is_configured,
    google_post,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="LMS inmersivo con Google Workspace, realidad virtual y realidad aumentada.",
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.cookie_secure,
    same_site="lax",
    max_age=60 * 60 * 8,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class MeetRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    start_iso: str | None = None
    duration_minutes: int = Field(default=60, ge=15, le=480)
    attendees: list[str] = Field(default_factory=list)


class AnnouncementRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=3, max_length=2000)
    author: str = Field(default="Facultad", min_length=2, max_length=100)


def rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": settings.app_name, "version": "0.1.0"}


@app.get("/api/config")
def config() -> dict[str, Any]:
    return {
        "appName": settings.app_name,
        "environment": settings.app_env,
        "googleConfigured": google_is_configured(),
        "features": {
            "googleWorkspace": True,
            "classroomSync": True,
            "drivePicker": True,
            "calendarMeet": True,
            "virtualReality": True,
            "augmentedReality": True,
            "analytics": True,
            "accessibility": True,
        },
    }


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    with connection() as conn:
        course_count = conn.execute("SELECT COUNT(*) AS n FROM courses").fetchone()["n"]
        activity_count = conn.execute("SELECT COUNT(*) AS n FROM activities").fetchone()["n"]
        xr_count = conn.execute("SELECT COUNT(*) AS n FROM xr_experiences").fetchone()["n"]
        upcoming = rows_to_dicts(
            conn.execute(
                """
                SELECT a.id, a.title, a.activity_type, a.due_date, a.points,
                       c.code AS course_code, c.title AS course_title
                FROM activities a
                JOIN modules m ON m.id = a.module_id
                JOIN courses c ON c.id = m.course_id
                WHERE a.due_date IS NOT NULL
                ORDER BY a.due_date ASC LIMIT 5
                """
            ).fetchall()
        )
        announcements = rows_to_dicts(
            conn.execute(
                """
                SELECT a.*, c.code AS course_code
                FROM announcements a
                LEFT JOIN courses c ON c.id = a.course_id
                ORDER BY published_at DESC LIMIT 5
                """
            ).fetchall()
        )
    return {
        "stats": {
            "courses": course_count,
            "activities": activity_count,
            "xrExperiences": xr_count,
            "engagement": 84,
        },
        "upcoming": upcoming,
        "announcements": announcements,
    }


@app.get("/api/courses")
def courses() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM modules m WHERE m.course_id = c.id) AS module_count,
                   (SELECT COUNT(*) FROM activities a JOIN modules m2 ON m2.id=a.module_id WHERE m2.course_id=c.id) AS activity_count
            FROM courses c ORDER BY c.id
            """
        ).fetchall()
    return rows_to_dicts(rows)


@app.get("/api/courses/{course_id}")
def course_detail(course_id: int) -> dict[str, Any]:
    with connection() as conn:
        course = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        if not course:
            raise HTTPException(status_code=404, detail="Curso no encontrado.")
        modules = rows_to_dicts(
            conn.execute(
                "SELECT * FROM modules WHERE course_id=? ORDER BY position", (course_id,)
            ).fetchall()
        )
        for module in modules:
            module["activities"] = rows_to_dicts(
                conn.execute(
                    "SELECT * FROM activities WHERE module_id=? ORDER BY id", (module["id"],)
                ).fetchall()
            )
    return {"course": dict(course), "modules": modules}


@app.post("/api/courses/{course_id}/announcements", status_code=201)
def create_announcement(course_id: int, payload: AnnouncementRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        exists = conn.execute("SELECT 1 FROM courses WHERE id=?", (course_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Curso no encontrado.")
        cursor = conn.execute(
            "INSERT INTO announcements(course_id,title,body,author,published_at) VALUES (?,?,?,?,?)",
            (course_id, payload.title, payload.body, payload.author, now),
        )
        row = conn.execute("SELECT * FROM announcements WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.get("/api/xr")
def xr_experiences() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM xr_experiences ORDER BY id").fetchall()
    return rows_to_dicts(rows)


@app.get("/auth/google/login")
def google_login(request: Request) -> RedirectResponse:
    return RedirectResponse(build_authorization_url(request))


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str, state: str) -> RedirectResponse:
    await exchange_code(request, code, state)
    return RedirectResponse("/?google=connected")


@app.post("/auth/logout")
def logout(request: Request) -> dict[str, bool]:
    sid = request.session.get("sid")
    if sid:
        TOKEN_STORE.pop(sid, None)
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request) -> dict[str, Any]:
    user = request.session.get("user")
    return {"authenticated": bool(user), "user": user}


@app.get("/api/google/classroom/courses")
async def classroom_courses(request: Request) -> dict[str, Any]:
    return await google_get(
        request,
        "https://classroom.googleapis.com/v1/courses",
        params={"courseStates": ["ACTIVE"], "pageSize": 50},
    )


@app.get("/api/google/drive/files")
async def drive_files(request: Request) -> dict[str, Any]:
    return await google_get(
        request,
        "https://www.googleapis.com/drive/v3/files",
        params={
            "pageSize": 20,
            "q": "trashed=false",
            "orderBy": "modifiedTime desc",
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink,iconLink)",
        },
    )


@app.get("/api/google/calendar/events")
async def calendar_events(request: Request) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return await google_get(
        request,
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        params={
            "timeMin": now,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 20,
        },
    )


@app.post("/api/google/meet/create")
async def create_google_meet(request: Request, payload: MeetRequest) -> dict[str, Any]:
    if payload.start_iso:
        try:
            start = datetime.fromisoformat(payload.start_iso.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="start_iso no es una fecha ISO válida.") from exc
    else:
        start = datetime.now(timezone.utc) + timedelta(minutes=15)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=payload.duration_minutes)
    event = {
        "summary": payload.title,
        "description": "Videoclase creada desde NEXUS EDU XR.",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "attendees": [{"email": email} for email in payload.attendees],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    return await google_post(
        request,
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        event,
        params={"conferenceDataVersion": 1, "sendUpdates": "all"},
    )
