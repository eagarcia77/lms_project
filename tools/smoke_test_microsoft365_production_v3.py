from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-microsoft365-production-v3-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft-production-v3-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft-production-v3-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "msv3.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Microsoft-V3-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Microsoft V3 Administrator"
os.environ["MICROSOFT_CLIENT_ID"] = "microsoft-v3-client"
os.environ["MICROSOFT_CLIENT_SECRET"] = "microsoft-v3-client-secret-never-render"
os.environ["MICROSOFT_TENANT_ID"] = "11111111-2222-3333-4444-555555555555"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example/auth/microsoft/callback"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "microsoft-production-v3-token-encryption-key-2026"
os.environ["MICROSOFT_ALLOW_TEAM_CREATION"] = "true"
os.environ["MICROSOFT_SCOPES"] = "openid profile email offline_access User.Read Files.Read Files.ReadWrite Sites.Read.All Calendars.ReadWrite User.ReadBasic.All Team.ReadBasic.All TeamMember.ReadWrite.All Channel.ReadBasic.All Channel.Create Team.Create"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.microsoft365_integration as m365  # noqa: E402
import app.microsoft365_production_v3 as v3  # noqa: E402


@app.get("/__smoke/microsoft-v3-user/{kind}", include_in_schema=False)
async def smoke_microsoft_v3_user(kind: str, request: Request):
    if kind == "instructor":
        request.session["user"] = {"id": "msv3-instructor", "name": "Microsoft V3 Instructor", "email": "msv3.instructor@example.com"}
    elif kind == "student":
        request.session["user"] = {"id": "msv3-student", "name": "Microsoft V3 Student", "email": "msv3.student1@example.com"}
    else:
        raise RuntimeError("Unsupported Microsoft v3 smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def create_course(client: TestClient, code: str, title: str) -> int:
    response = client.post("/admin/authoring/courses", data={
        "course_code": code,
        "title": title,
        "description": "Microsoft 365 Production v3 validation course.",
        "term": "Fall 2026",
        "instructor_email": "msv3.instructor@example.com",
        "template": "blank",
    })
    expect(response, 303, f"create {code}")
    return int(response.headers["location"].rsplit("/", 1)[-1])


def main() -> None:
    graph_calls: list[tuple[str, str]] = []
    member_posts: list[dict] = []
    folder_posts: list[dict] = []

    async def fake_raw(email: str, method: str, target: str, *, params=None, json_body=None):
        graph_calls.append((method.upper(), target))
        if method.upper() == "GET" and target == "/teams/team-existing/members":
            return 200, {}, {"value": [
                {"id": "membership-instructor", "userId": "aad-instructor", "displayName": "Instructor", "email": "msv3.instructor@example.com", "roles": ["owner"]},
                {"id": "membership-external", "userId": "aad-external", "displayName": "External Reviewer", "email": "external@example.com", "roles": []},
            ], "@odata.nextLink": "https://graph.microsoft.com/v1.0/teams/team-existing/members?$skiptoken=page2"}
        if method.upper() == "GET" and target.startswith("https://graph.microsoft.com/v1.0/teams/team-existing/members?"):
            return 200, {}, {"value": [
                {"id": "membership-student1", "userId": "aad-student1", "displayName": "Student One", "email": "msv3.student1@example.com", "roles": []},
            ]}
        if method.upper() == "POST" and target == "/teams":
            return 202, {"content-location": "/teams('team-created')", "location": "/teams('team-created')/operations('op-1')"}, {}
        if method.upper() == "GET" and "operations('op-1')" in target:
            return 200, {}, {"status": "succeeded", "targetResourceId": "team-created"}
        if method.upper() == "GET" and target == "/me":
            return 200, {}, {"id": "aad-admin", "userPrincipalName": email}
        if method.upper() == "GET" and target == "/me/joinedTeams":
            return 200, {}, {"value": [{"id": "team-existing", "displayName": "Existing Team"}]}
        if method.upper() == "GET" and target == "/users":
            return 200, {}, {"value": [{"id": "aad-user", "userPrincipalName": "sample@example.com"}]}
        if method.upper() == "GET" and target == "/teams/team-existing/channels":
            return 200, {}, {"value": [{"id": "general", "displayName": "General"}]}
        if method.upper() == "GET" and target == "/groups/team-existing/drive/root/children":
            return 200, {}, {"value": [{"id": "folder-1", "name": "Course Materials", "webUrl": "https://tenant.sharepoint.com/course-materials", "folder": {"childCount": 2}}]}
        raise RuntimeError(f"Unexpected raw Graph call: {method} {target} {params} {json_body}")

    async def fake_graph_json(email: str, method: str, path: str, *, params=None, json_body=None):
        graph_calls.append((method.upper(), path))
        if method.upper() == "GET" and path == "/users/msv3.student2%40example.com":
            return {"id": "aad-student2", "displayName": "Student Two", "mail": "msv3.student2@example.com", "userPrincipalName": "msv3.student2@example.com"}
        if method.upper() == "POST" and path == "/teams/team-existing/members":
            member_posts.append(json_body or {})
            return {"id": "membership-student2"}
        if method.upper() == "GET" and path == "/teams/team-created":
            return {"id": "team-created", "displayName": "MSV3-4200 · Provisioned Team", "webUrl": "https://teams.microsoft.com/l/team-created"}
        if method.upper() == "POST" and path == "/groups/team-existing/drive/root/children":
            folder_posts.append(json_body or {})
            return {"id": "folder-created", "name": str((json_body or {}).get("name") or "")}
        raise RuntimeError(f"Unexpected Graph JSON call: {method} {path} {params} {json_body}")

    original_raw = v3._graph_raw
    original_graph_json = m365._graph_json
    v3._graph_raw = fake_raw
    m365._graph_json = fake_graph_json
    try:
        with TestClient(app, follow_redirects=False) as client:
            expect(client.post("/admin/login", data={"email": "msv3.admin@example.com", "password": "Initial-Microsoft-V3-2026!"}), 303, "admin login")
            expect(client.post("/admin/password", data={"password": "Updated-Microsoft-V3-2026!", "confirm": "Updated-Microsoft-V3-2026!"}), 303, "admin password update")
            course1 = create_course(client, "MSV3-4100", "Existing Team Integration")
            course2 = create_course(client, "MSV3-4200", "Controlled Team Provisioning")
            now = utcnow()
            with db() as conn:
                for course_id in (course1, course2):
                    execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course1, "msv3.student1@example.com", "student", "active", now))
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course1, "msv3.student2@example.com", "student", "active", now))
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course1, "msv3.observer@example.com", "observer", "active", now))
                execute(conn, "INSERT INTO nuvedra_microsoft_course_teams (course_id,team_id,display_name,web_url,status,linked_by,linked_at,last_synced_at,last_sync_json) VALUES (?,?,?,?,'active',?,?,NULL,NULL)", (course1, "team-existing", "Existing Team", "https://teams.microsoft.com/l/team-existing", "msv3.instructor@example.com", now))
                scopes = os.environ["MICROSOFT_SCOPES"]
                m365._store_connection(conn, "msv3.admin@example.com", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="aad-admin", display_name="Microsoft V3 Administrator", access_token="admin-access-token", refresh_token="admin-refresh-token", expires_in=3600, scopes=scopes)
                m365._store_connection(conn, "msv3.instructor@example.com", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="aad-instructor", display_name="Microsoft V3 Instructor", access_token="instructor-access-token", refresh_token="instructor-refresh-token", expires_in=3600, scopes=scopes)

            admin_page = client.get("/admin/microsoft365/production")
            expect(admin_page, 200, "production admin page")
            require(admin_page, 'data-testid="microsoft365-production-admin-v3"', "production admin page")
            if os.environ["MICROSOFT_CLIENT_SECRET"] in admin_page.text or "admin-access-token" in admin_page.text:
                raise RuntimeError("Microsoft production admin page exposed a Microsoft secret/token.")
            expect(client.post("/admin/microsoft365/production/probe"), 303, "admin Graph permission probe")
            with db() as conn:
                probes = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_permission_probes WHERE user_email=?", ("msv3.admin@example.com",)))
                if len(probes) != 1:
                    raise RuntimeError("Live Graph permission probe was not persisted.")

            expect(client.get("/__smoke/microsoft-v3-user/instructor"), 200, "instructor session")
            workspace = client.get(f"/faculty/studio/courses/{course1}/microsoft365/production")
            expect(workspace, 200, "production course workspace")
            require(workspace, 'data-testid="microsoft365-production-v3"', "production course workspace")

            plan = client.get(f"/faculty/studio/courses/{course1}/microsoft365/production/plan")
            expect(plan, 200, "paginated roster plan")
            require(plan, "2 Graph page(s)", "Graph pagination")
            require(plan, "msv3.student2@example.com", "missing student")
            require(plan, "external@example.com", "preserved external Team member")
            if "msv3.observer@example.com" in plan.text:
                raise RuntimeError("Observer was incorrectly included in the Microsoft Teams provisioning target.")

            expect(client.post(f"/faculty/studio/courses/{course1}/microsoft365/production/sync"), 303, "incremental roster sync")
            if len(member_posts) != 1 or "aad-student2" not in str(member_posts[0]):
                raise RuntimeError("Incremental sync did not add exactly the missing student.")
            if any(method == "DELETE" for method, _path in graph_calls):
                raise RuntimeError("Microsoft Production v3 issued a destructive DELETE operation.")
            with db() as conn:
                state = rows(execute(conn, "SELECT status,last_action FROM nuvedra_microsoft_roster_state WHERE course_id=? AND user_email=?", (course1, "msv3.student2@example.com")))
                if not state or state[0]["status"] != "present" or state[0]["last_action"] != "added":
                    raise RuntimeError("Incremental roster state was not persisted for the added student.")

            sharepoint = client.get(f"/faculty/studio/courses/{course1}/microsoft365/production/sharepoint")
            expect(sharepoint, 200, "course SharePoint")
            require(sharepoint, 'data-testid="microsoft365-sharepoint-v3"', "course SharePoint")
            require(sharepoint, "Course Materials", "SharePoint root item")
            expect(client.post(f"/faculty/studio/courses/{course1}/microsoft365/production/sharepoint/folders", data={"name": "Assessment Evidence"}), 303, "SharePoint folder create")
            if len(folder_posts) != 1 or folder_posts[0].get("name") != "Assessment Evidence":
                raise RuntimeError("SharePoint course folder was not created through Graph.")

            create_team = client.post(f"/faculty/studio/courses/{course2}/microsoft365/production/team", data={"display_name": "MSV3-4200 · Provisioned Team"})
            expect(create_team, 303, "controlled Team creation")
            with db() as conn:
                provisioning = rows(execute(conn, "SELECT team_id,status FROM nuvedra_microsoft_team_provisioning WHERE course_id=?", (course2,)))
                if not provisioning or provisioning[0]["team_id"] != "team-created" or provisioning[0]["status"] != "accepted":
                    raise RuntimeError("Controlled Team provisioning request was not recorded.")
            expect(client.post(f"/faculty/studio/courses/{course2}/microsoft365/production/team/check"), 303, "Team provisioning verification")
            with db() as conn:
                linked = rows(execute(conn, "SELECT team_id,status FROM nuvedra_microsoft_course_teams WHERE course_id=?", (course2,)))
                if not linked or linked[0]["team_id"] != "team-created" or linked[0]["status"] != "active":
                    raise RuntimeError("Provisioned Microsoft Team was not linked to the NUVEDRA course.")

            expect(client.get("/__smoke/microsoft-v3-user/student"), 200, "student session")
            expect(client.get(f"/faculty/studio/courses/{course1}/microsoft365/production"), 403, "student production workspace protection")

        print("Microsoft 365 Production & Tenant Provisioning v3 validated: actual granted-scope diagnostics, safe Graph pagination, incremental additive roster sync, observer exclusion, external member preservation, controlled Team creation/provisioning, SharePoint folder management, secret non-disclosure, and role protection.", flush=True)
    finally:
        v3._graph_raw = original_raw
        m365._graph_json = original_graph_json
        if DB_PATH.exists():
            DB_PATH.unlink()


if __name__ == "__main__":
    main()
