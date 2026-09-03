from __future__ import annotations

import json
import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-microsoft365-go-live-v8-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft-v8-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft-v8-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "msv8.admin@example.edu"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Microsoft-V8-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Microsoft V8 Administrator"
os.environ["MICROSOFT_CLIENT_ID"] = "microsoft-v8-client-id"
os.environ["MICROSOFT_CLIENT_SECRET"] = "microsoft-v8-client-secret-never-render"
os.environ["MICROSOFT_TENANT_ID"] = "88888888-9999-aaaa-bbbb-cccccccccccc"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example/auth/microsoft/callback"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "microsoft-v8-encryption-key-never-render"
os.environ["MICROSOFT_REQUIRE_INSTITUTION_TENANT"] = "true"
os.environ["MICROSOFT_ALLOWED_DOMAINS"] = "example.edu"
os.environ["MICROSOFT_SCOPES"] = "openid profile email offline_access User.Read Files.Read Files.ReadWrite Sites.Read.All Calendars.ReadWrite User.ReadBasic.All Team.ReadBasic.All TeamMember.ReadWrite.All Channel.ReadBasic.All Channel.Create Team.Create EduRoster.ReadBasic EduAssignments.ReadBasic EduAssignments.ReadWrite"
os.environ["MICROSOFT_ALLOW_TEAM_CREATION"] = "true"
os.environ["MICROSOFT_ALLOW_EDUCATION_WRITES"] = "true"
os.environ["MICROSOFT_ALLOW_EDUCATION_PUBLISH"] = "true"
os.environ["MICROSOFT_ALLOW_GRADE_EXPORT"] = "true"
os.environ["MICROSOFT_ALLOW_GRADE_RETURN"] = "true"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import HTTPException, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.microsoft365_go_live_governance_v8 as go_live  # noqa: E402


@app.get("/__smoke/microsoft-v8-user/{kind}", include_in_schema=False)
async def smoke_microsoft_v8_user(kind: str, request: Request):
    if kind == "instructor":
        request.session["user"] = {"id": "microsoft-v8-instructor", "name": "Microsoft V8 Instructor", "email": "v8.instructor@example.edu"}
    elif kind == "student":
        request.session["user"] = {"id": "microsoft-v8-student", "name": "Microsoft V8 Student", "email": "v8.student@example.edu"}
    else:
        raise RuntimeError("Unsupported Microsoft v8 smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def insert_id(conn, sql: str, params: tuple) -> int:
    return int(execute(conn, sql, params).lastrowid)


def require_blocked(conn, course_id: int, operation: str, label: str) -> None:
    try:
        go_live.require_course_write_access(conn, course_id, operation)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise RuntimeError(f"{label}: expected 403 governance block, received {exc.status_code}.") from exc
        return
    raise RuntimeError(f"{label}: expected Microsoft 365 governance block.")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "msv8.admin@example.edu", "password": "Initial-Microsoft-V8-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Microsoft-V8-2026!", "confirm": "Updated-Microsoft-V8-2026!"}), 303, "admin password update")

        now = utcnow()
        with db() as conn:
            course_id = insert_id(conn, """INSERT INTO nexus_admin_courses
                (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (
                "MSV8-8001", "Microsoft 365 Pilot Course", "Controlled pilot governance smoke test.", "Fall 2026", "active",
                "v8.instructor@example.edu", "msv8.admin@example.edu", now, now,
            ))
            other_course_id = insert_id(conn, """INSERT INTO nexus_admin_courses
                (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (
                "MSV8-8002", "Microsoft 365 Nonpilot Course", "Must remain blocked during pilot.", "Fall 2026", "active",
                "v8.instructor@example.edu", "msv8.admin@example.edu", now, now,
            ))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "v8.instructor@example.edu", "instructor", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "v8.student@example.edu", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (other_course_id, "v8.instructor@example.edu", "instructor", "active", now))
            execute(conn, """INSERT INTO nuvedra_microsoft_consent_wizard_snapshots
                (user_email,tenant_id,effective_scopes,missing_recommended_scopes,configuration_json,checks_json,readiness_status,created_at)
                VALUES (?,?,?,?,?,?,?,?)""", (
                "msv8.admin@example.edu", os.environ["MICROSOFT_TENANT_ID"], os.environ["MICROSOFT_SCOPES"], "",
                json.dumps({"tenant": os.environ["MICROSOFT_TENANT_ID"], "redirect_https": True}),
                json.dumps({"identity": {"ok": True}, "organization": {"ok": True}, "education": {"ok": True}}),
                "writes_enabled", now,
            ))
            require_blocked(conn, course_id, "education_assignment", "default read-only mode")

        admin_page = client.get("/admin/microsoft365/go-live")
        expect(admin_page, 200, "go-live admin page")
        require(admin_page, 'data-testid="microsoft365-go-live-v8"', "go-live admin page")
        require(admin_page, "Read-only", "default rollout mode")
        if os.environ["MICROSOFT_CLIENT_SECRET"] in admin_page.text or os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] in admin_page.text:
            raise RuntimeError("Go-Live Governance v8 exposed Microsoft secret material.")

        missing_acks = client.post("/admin/microsoft365/go-live/mode", data={"mode": "pilot"})
        expect(missing_acks, 409, "pilot acknowledgement gate")

        expect(client.post("/admin/microsoft365/go-live/pilots", data={"course_id": course_id}), 303, "approve pilot course")
        expect(client.post("/admin/microsoft365/go-live/mode", data={
            "mode": "pilot",
            "acknowledge_consent": "yes",
            "acknowledge_governance": "yes",
            "acknowledge_support": "yes",
            "notes": "Approved limited Microsoft 365 pilot.",
        }), 303, "activate pilot mode")

        with db() as conn:
            allowed = go_live.require_course_write_access(conn, course_id, "education_assignment")
            if not allowed.get("allowed") or allowed.get("mode") != "pilot":
                raise RuntimeError("Approved pilot course was not allowed during pilot mode.")
            require_blocked(conn, other_course_id, "education_assignment", "nonpilot course")
            require_blocked(conn, other_course_id, "team_creation", "nonpilot Team creation")

        expect(client.get("/__smoke/microsoft-v8-user/instructor"), 200, "set instructor session")
        faculty_page = client.get(f"/faculty/studio/courses/{course_id}/microsoft365/go-live")
        expect(faculty_page, 200, "faculty go-live status")
        require(faculty_page, 'data-testid="microsoft365-course-go-live-v8"', "faculty go-live status")
        require(faculty_page, "Approved", "pilot write approval")

        expect(client.get("/__smoke/microsoft-v8-user/student"), 200, "set student session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/microsoft365/go-live"), 403, "student faculty governance denial")

        expect(client.post(f"/admin/microsoft365/go-live/pilots/{course_id}/validate", data={"review_notes": "Pilot passed operational validation."}), 303, "validate pilot")
        expect(client.post("/admin/microsoft365/go-live/mode", data={
            "mode": "production",
            "acknowledge_consent": "yes",
            "acknowledge_governance": "yes",
            "acknowledge_support": "yes",
            "notes": "Production approved after validated pilot.",
        }), 303, "activate production mode")
        with db() as conn:
            state = go_live.require_course_write_access(conn, other_course_id, "education_grade_export")
            if state.get("mode") != "production" or not state.get("allowed"):
                raise RuntimeError("Production mode did not allow high-impact Microsoft writes for the nonpilot course.")

        expect(client.post("/admin/microsoft365/go-live/mode", data={"mode": "read_only", "notes": "Emergency rollback to read-only."}), 303, "rollback to read-only")
        with db() as conn:
            require_blocked(conn, course_id, "education_grade_export", "read-only rollback")
            active_profiles = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_go_live_profiles WHERE status='active'"))
            all_profiles = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_go_live_profiles ORDER BY id"))
            if len(active_profiles) != 1 or active_profiles[0]["mode"] != "read_only":
                raise RuntimeError("Go-Live v8 did not preserve exactly one active rollout profile after rollback.")
            if len(all_profiles) != 3:
                raise RuntimeError("Go-Live v8 rollout profile history is not immutable across pilot, production, and rollback transitions.")
            pilots = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_pilot_courses WHERE course_id=?", (course_id,)))
            if not pilots or pilots[0]["status"] != "validated":
                raise RuntimeError("Validated pilot evidence was not preserved across rollout mode changes.")

        education_text = Path("app/microsoft365_education_sync_v6.py").read_text(encoding="utf-8")
        production_text = Path("app/microsoft365_production_v3.py").read_text(encoding="utf-8")
        required_education = [
            'go_live.require_course_write_access(conn, course_id, "education_assignment")',
            'go_live.require_course_write_access(conn, course_id, "education_grade_export")',
        ]
        if any(marker not in education_text for marker in required_education):
            raise RuntimeError("Go-Live v8 was not wired into Microsoft Education assignment/grade write paths.")
        if 'go_live.require_course_write_access(conn, course_id, "team_creation")' not in production_text:
            raise RuntimeError("Go-Live v8 was not wired into controlled Microsoft Team creation.")

    print("Microsoft 365 Go-Live Governance & Pilot v8 validated: read-only default, explicit institutional acknowledgements, course pilot allowlisting, nonpilot blocking, pilot validation, production promotion, emergency read-only rollback, immutable rollout history, faculty visibility, student denial, secret non-disclosure, and high-impact write-path enforcement.", flush=True)
    if DB_PATH.exists():
        DB_PATH.unlink()


if __name__ == "__main__":
    main()
