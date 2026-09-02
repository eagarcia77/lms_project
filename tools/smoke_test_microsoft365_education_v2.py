from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

DB_PATH = Path("/tmp/nuvedra-microsoft365-education-v2-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft365-education-v2-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft365-education-v2-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "m365edu.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-M365Edu-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Microsoft 365 Education Administrator"
os.environ["MICROSOFT_CLIENT_ID"] = "m365-education-client-id"
os.environ["MICROSOFT_CLIENT_SECRET"] = "m365-education-client-secret"
os.environ["MICROSOFT_TENANT_ID"] = "11111111-2222-3333-4444-555555555555"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example.edu/auth/microsoft/callback"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "dedicated-microsoft365-token-encryption-key-v2"
os.environ["MICROSOFT_SCOPES"] = "openid profile email offline_access User.Read Files.Read Sites.Read.All Calendars.ReadWrite User.ReadBasic.All Team.ReadBasic.All TeamMember.ReadWrite.All Channel.ReadBasic.All Channel.Create"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.microsoft365_integration as m365  # noqa: E402


@app.get("/__smoke/m365edu-user/{kind}", include_in_schema=False)
async def smoke_m365edu_user(kind: str, request: Request):
    users = {
        "instructor": ("m365edu.instructor@example.com", "M365 Education Instructor"),
        "student": ("m365edu.student@example.com", "M365 Education Student"),
        "observer": ("m365edu.observer@example.com", "M365 Education Observer"),
    }
    if kind not in users:
        raise RuntimeError("Unsupported Microsoft 365 Education smoke user.")
    email, name = users[kind]
    request.session["user"] = {"id": kind, "name": name, "email": email, "_auth_source": "microsoft"}
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    team_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    graph_calls: list[tuple[str, str, dict | None]] = []
    team_members = [
        {"id": "membership-instructor", "displayName": "M365 Education Instructor", "email": "m365edu.instructor@example.com", "roles": ["owner"], "userId": "graph-instructor"},
        {"id": "membership-external", "displayName": "External Reviewer", "email": "external.person@example.com", "roles": [], "userId": "graph-external"},
    ]

    async def fake_graph(email: str, method: str, path: str, *, params=None, json_body=None):
        graph_calls.append((method.upper(), path, json_body))
        if method.upper() == "GET" and path == f"/teams/{team_id}":
            return {"id": team_id, "displayName": "NUVEDRA EDU-6100", "webUrl": f"https://teams.microsoft.com/l/team/{team_id}/conversations"}
        if method.upper() == "GET" and path == f"/teams/{team_id}/members":
            return {"value": list(team_members)}
        if method.upper() == "GET" and path.startswith("/users/"):
            target = unquote(path.split("/users/", 1)[1]).lower()
            if target == "m365edu.student@example.com":
                return {"id": "graph-student", "displayName": "M365 Education Student", "mail": target}
            if target == "m365edu.instructor@example.com":
                return {"id": "graph-instructor", "displayName": "M365 Education Instructor", "mail": target}
            raise RuntimeError(f"Unexpected Graph user resolution: {target}")
        if method.upper() == "POST" and path == f"/teams/{team_id}/members":
            bind = str((json_body or {}).get("user@odata.bind") or "")
            if "graph-student" in bind:
                team_members.append({"id": "membership-student", "displayName": "M365 Education Student", "email": "m365edu.student@example.com", "roles": [], "userId": "graph-student"})
                return {"id": "membership-student"}
            raise RuntimeError("Unexpected Teams membership payload.")
        if method.upper() == "POST" and path == f"/teams/{team_id}/channels":
            return {"id": "channel-weekly", "displayName": (json_body or {}).get("displayName")}
        raise RuntimeError(f"Unexpected Microsoft Graph smoke call: {method} {path}")

    m365._graph_json = fake_graph

    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "m365edu.admin@example.com", "password": "Initial-M365Edu-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-M365Edu-2026!", "confirm": "Updated-M365Edu-2026!"}), 303, "admin password update")
        admin_page = client.get("/admin/microsoft365")
        expect(admin_page, 200, "Microsoft 365 admin readiness")
        require(admin_page, 'data-testid="microsoft365-institutional-admin-v2"', "Microsoft 365 admin readiness")
        require(admin_page, "TeamMember.ReadWrite.All", "Teams member scope diagnostic")
        require(admin_page, "11111111-2222-3333-4444-555555555555", "tenant diagnostic")
        if "m365-education-client-secret" in admin_page.text or "dedicated-microsoft365-token-encryption-key-v2" in admin_page.text:
            raise RuntimeError("Microsoft 365 admin diagnostics exposed a secret value.")

        created = client.post("/admin/authoring/courses", data={
            "course_code": "EDU-6100",
            "title": "Microsoft 365 Institutional Collaboration",
            "description": "Microsoft Teams education integration smoke course.",
            "term": "Fall 2026",
            "instructor_email": "m365edu.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "m365edu.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "m365edu.observer@example.com", "observer", "active", now))
            m365._store_connection(conn, "m365edu.instructor@example.com", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="graph-instructor", display_name="M365 Education Instructor", access_token="fake-access-token", refresh_token="fake-refresh-token", expires_in=3600, scopes=os.environ["MICROSOFT_SCOPES"])

        expect(client.get("/__smoke/m365edu-user/instructor"), 200, "instructor session")
        workspace = client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education")
        expect(workspace, 200, "Teams education workspace")
        require(workspace, 'data-testid="microsoft365-education-v2"', "Teams education workspace")
        require(workspace, "Link an existing Microsoft Team", "existing Team linking")

        expect(client.post(f"/faculty/studio/courses/{course_id}/microsoft365/education/team", data={"team_id": "bad/team/id"}), 400, "invalid Team ID rejection")
        linked = client.post(f"/faculty/studio/courses/{course_id}/microsoft365/education/team", data={"team_id": team_id})
        expect(linked, 303, "Team link")

        plan_page = client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education/plan")
        expect(plan_page, 200, "membership preview")
        require(plan_page, 'data-testid="microsoft365-membership-plan-v2"', "membership preview")
        require(plan_page, "m365edu.student@example.com", "missing student preview")
        require(plan_page, "external.person@example.com", "external member preservation preview")
        if "m365edu.observer@example.com" in plan_page.text:
            raise RuntimeError("Observer was incorrectly included in Microsoft Teams provisioning plan.")

        plan_json = client.get(f"/api/microsoft365/courses/{course_id}/team-membership-plan")
        expect(plan_json, 200, "membership preview JSON")
        payload = plan_json.json()
        if payload.get("sync_mode") != "additive" or len(payload.get("missing") or []) != 1:
            raise RuntimeError(f"Unexpected additive membership plan: {payload}")

        synced = client.post(f"/faculty/studio/courses/{course_id}/microsoft365/education/sync")
        expect(synced, 303, "additive membership sync")
        if not any(method == "POST" and path == f"/teams/{team_id}/members" for method, path, _ in graph_calls):
            raise RuntimeError("Teams membership POST was not issued.")
        if any(method == "DELETE" for method, _, _ in graph_calls):
            raise RuntimeError("Additive Teams sync attempted a destructive DELETE.")
        if any("m365edu.observer@example.com" in str(body) for _, _, body in graph_calls):
            raise RuntimeError("Observer was sent to Microsoft Graph membership provisioning.")

        channel = client.post(f"/faculty/studio/courses/{course_id}/microsoft365/education/channels", data={"display_name": "Weekly Collaboration", "description": "Course collaboration channel."})
        expect(channel, 303, "channel creation")
        if not any(method == "POST" and path == f"/teams/{team_id}/channels" for method, path, _ in graph_calls):
            raise RuntimeError("Microsoft Teams channel creation was not issued.")

        with db() as conn:
            link = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_course_teams WHERE course_id=?", (course_id,)))
            if len(link) != 1 or link[0].get("team_id") != team_id:
                raise RuntimeError("Course Team linkage was not stored.")
            logs = rows(execute(conn, "SELECT action,summary_json FROM nuvedra_microsoft_team_sync_log WHERE course_id=? ORDER BY id", (course_id,)))
            actions = {str(x.get("action")) for x in logs}
            if "membership_additive_sync" not in actions or "channel_created" not in actions:
                raise RuntimeError(f"Microsoft Teams sync audit log is incomplete: {actions}")
            sync_summary = next(x for x in logs if x.get("action") == "membership_additive_sync")
            if "external.person@example.com" in str(sync_summary.get("summary_json")):
                raise RuntimeError("Sync summary should record unmanaged count, not copy external member identity into the audit summary.")

        expect(client.get("/__smoke/m365edu-user/student"), 200, "student session")
        student_page = client.get(f"/learn/courses/{course_id}/microsoft365")
        expect(student_page, 200, "student Microsoft 365 page")
        require(student_page, 'data-testid="student-microsoft365-v2"', "student Microsoft 365 page")
        require(student_page, "NUVEDRA EDU-6100", "student Team title")
        expect(client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education"), 403, "student faculty Teams workspace protection")
        expect(client.get(f"/api/microsoft365/courses/{course_id}/team-membership-plan"), 403, "student membership plan protection")

        expect(client.get("/__smoke/m365edu-user/observer"), 200, "observer session")
        observer_page = client.get(f"/learn/courses/{course_id}/microsoft365")
        expect(observer_page, 200, "observer read-only Team page")

    print("Microsoft 365 Institutional Setup & Teams Education v2 validated: admin readiness without secret disclosure, existing Team linking, additive roster planning/sync, observer exclusion, external-member preservation, channel creation, audit logs, and student/observer read-only Team access.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
