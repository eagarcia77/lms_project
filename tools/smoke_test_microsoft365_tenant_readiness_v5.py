from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-microsoft365-tenant-readiness-v5-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft-v5-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft-v5-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "msv5.admin@example.edu"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Microsoft-V5-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Microsoft V5 Administrator"
os.environ["MICROSOFT_CLIENT_ID"] = "microsoft-v5-client"
os.environ["MICROSOFT_CLIENT_SECRET"] = "microsoft-v5-secret-never-render"
os.environ["MICROSOFT_TENANT_ID"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example/auth/microsoft/callback"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "microsoft-v5-token-encryption-key-2026"
os.environ["MICROSOFT_REQUIRE_INSTITUTION_TENANT"] = "true"
os.environ["MICROSOFT_ALLOWED_DOMAINS"] = "example.edu"
os.environ["MICROSOFT_SCOPES"] = "openid profile email offline_access User.Read Files.Read Sites.Read.All Calendars.ReadWrite User.ReadBasic.All Team.ReadBasic.All TeamMember.ReadWrite.All Channel.ReadBasic.All Channel.Create Team.Create EduRoster.ReadBasic EduAssignments.ReadBasic"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.microsoft365_integration as m365  # noqa: E402
import app.microsoft365_production_v3 as production  # noqa: E402


@app.get("/__smoke/microsoft-v5-user/{kind}", include_in_schema=False)
async def smoke_microsoft_v5_user(kind: str, request: Request):
    if kind == "instructor":
        request.session["user"] = {"id": "msv5-instructor", "name": "Microsoft V5 Instructor", "email": "msv5.instructor@example.edu"}
    elif kind == "student":
        request.session["user"] = {"id": "msv5-student", "name": "Microsoft V5 Student", "email": "msv5.student@example.edu"}
    else:
        raise RuntimeError("Unsupported Microsoft v5 smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def create_course(client: TestClient) -> int:
    response = client.post("/admin/authoring/courses", data={
        "course_code": "MSV5-5100",
        "title": "Microsoft Education Readiness",
        "description": "Microsoft 365 live tenant readiness validation course.",
        "term": "Fall 2026",
        "instructor_email": "msv5.instructor@example.edu",
        "template": "blank",
    })
    expect(response, 303, "create course")
    return int(response.headers["location"].rsplit("/", 1)[-1])


def main() -> None:
    graph_calls: list[tuple[str, str]] = []

    async def fake_graph_json(email: str, method: str, path: str, *, params=None, json_body=None):
        graph_calls.append((method.upper(), path))
        if method.upper() == "GET" and path == "/organization":
            return {"value": [{
                "id": os.environ["MICROSOFT_TENANT_ID"],
                "displayName": "Example University",
                "verifiedDomains": [
                    {"name": "example.edu", "isDefault": True, "isInitial": False},
                    {"name": "example.onmicrosoft.com", "isDefault": False, "isInitial": True},
                ],
            }]}
        raise RuntimeError(f"Unexpected Graph JSON call: {method} {path} {params} {json_body}")

    async def fake_graph_collection(email: str, path: str, *, params=None):
        graph_calls.append(("GET_COLLECTION", path))
        if path == "/education/me/taughtClasses":
            return ([{
                "id": "education-class-5100",
                "displayName": "MSV5-5100 Microsoft Education Readiness",
                "externalId": "MSV5-5100-F26",
                "classCode": "MSV5-5100",
            }], 1)
        if path == "/education/classes/education-class-5100/assignments":
            return ([{
                "id": "education-assignment-1",
                "displayName": "Microsoft Education Sample Assignment",
                "status": "assigned",
            }], 1)
        raise RuntimeError(f"Unexpected Graph collection call: {path} {params}")

    original_graph_json = m365._graph_json
    original_graph_collection = production._graph_collection
    m365._graph_json = fake_graph_json
    production._graph_collection = fake_graph_collection
    try:
        with TestClient(app, follow_redirects=False) as client:
            expect(client.post("/admin/login", data={"email": "msv5.admin@example.edu", "password": "Initial-Microsoft-V5-2026!"}), 303, "admin login")
            expect(client.post("/admin/password", data={"password": "Updated-Microsoft-V5-2026!", "confirm": "Updated-Microsoft-V5-2026!"}), 303, "admin password update")
            course_id = create_course(client)
            now = utcnow()
            scopes = os.environ["MICROSOFT_SCOPES"]
            with db() as conn:
                execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "msv5.student@example.edu", "student", "active", now))
                m365._store_connection(conn, "msv5.admin@example.edu", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="aad-admin-v5", display_name="Microsoft V5 Administrator", access_token="admin-v5-access-token", refresh_token="admin-v5-refresh-token", expires_in=3600, scopes=scopes)
                m365._store_connection(conn, "msv5.instructor@example.edu", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="aad-instructor-v5", display_name="Microsoft V5 Instructor", access_token="instructor-v5-access-token", refresh_token="instructor-v5-refresh-token", expires_in=3600, scopes=scopes)

            admin_page = client.get("/admin/microsoft365/tenant-readiness")
            expect(admin_page, 200, "tenant readiness admin page")
            require(admin_page, 'data-testid="microsoft365-tenant-readiness-v5"', "tenant readiness admin page")
            require(admin_page, "example.edu", "allowed domain display")
            if os.environ["MICROSOFT_CLIENT_SECRET"] in admin_page.text or "admin-v5-access-token" in admin_page.text:
                raise RuntimeError("Tenant readiness admin page exposed a Microsoft secret or token.")

            expect(client.post("/admin/microsoft365/tenant-readiness/probe"), 303, "live tenant readiness probe")
            with db() as conn:
                snapshots = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_tenant_readiness_snapshots ORDER BY id DESC"))
                if len(snapshots) != 1:
                    raise RuntimeError("Tenant readiness snapshot was not persisted.")
                snapshot = snapshots[0]
                if snapshot["organization_id"] != os.environ["MICROSOFT_TENANT_ID"] or snapshot["readiness_status"] != "ready_education":
                    raise RuntimeError(f"Tenant readiness did not reach ready_education: {snapshot}")
                if snapshot.get("missing_education_scopes"):
                    raise RuntimeError("Education scopes were incorrectly reported missing.")

            expect(client.get("/__smoke/microsoft-v5-user/instructor"), 200, "instructor session")
            education_page = client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education-readiness")
            expect(education_page, 200, "course education readiness")
            require(education_page, 'data-testid="microsoft365-education-readiness-v5"', "course education readiness")
            require(education_page, "MSV5-5100 Microsoft Education Readiness", "taught class discovery")
            expect(client.post(f"/faculty/studio/courses/{course_id}/microsoft365/education-readiness/link", data={"class_id": "education-class-5100"}), 303, "link taught Education class")
            linked_page = client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education-readiness")
            expect(linked_page, 200, "linked Education class page")
            require(linked_page, "Microsoft Education Sample Assignment", "read-only assignment metadata")
            with db() as conn:
                links = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_education_class_links WHERE course_id=?", (course_id,)))
                if len(links) != 1 or links[0]["class_id"] != "education-class-5100":
                    raise RuntimeError("Course-to-educationClass linkage was not persisted.")

            expect(client.get("/__smoke/microsoft-v5-user/student"), 200, "student session")
            expect(client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education-readiness"), 403, "student education readiness protection")

            os.environ["MICROSOFT_TENANT_ID"] = "organizations"
            expect(client.get("/auth/microsoft/login"), 503, "generic tenant blocked by production policy")
            os.environ["MICROSOFT_TENANT_ID"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

            if any(method in {"POST", "PUT", "PATCH", "DELETE"} for method, _path in graph_calls):
                raise RuntimeError("Microsoft Tenant Readiness v5 issued a Microsoft Graph write operation.")

        print("Microsoft 365 Live Tenant Readiness & Education v5 validated: specific-tenant policy, domain policy visibility, live organization binding, effective Education scope evidence, read-only taught-class and assignment discovery, course-to-educationClass linkage, no Microsoft Graph writes, secret non-disclosure, and role protection.", flush=True)
    finally:
        m365._graph_json = original_graph_json
        production._graph_collection = original_graph_collection
        if DB_PATH.exists():
            DB_PATH.unlink()


if __name__ == "__main__":
    main()
