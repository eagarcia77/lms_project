from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-microsoft365-integration-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft365-session-secret-2026-strong"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft365-admin-secret-2026-strong"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "microsoft365-token-encryption-key-2026-strong"
os.environ["MICROSOFT_CLIENT_ID"] = "00000000-0000-0000-0000-000000000365"
os.environ["MICROSOFT_CLIENT_SECRET"] = "smoke-client-secret-not-production"
os.environ["MICROSOFT_TENANT_ID"] = "organizations"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example.edu/auth/microsoft/callback"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "microsoft.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Microsoft-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Microsoft Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.microsoft365_integration as microsoft365  # noqa: E402


@app.get("/__smoke/microsoft-user/{kind}", include_in_schema=False)
async def smoke_microsoft_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "ms-instructor", "name": "Microsoft Instructor", "email": "microsoft.instructor@example.com"},
        "student": {"id": "ms-student", "name": "Microsoft Student", "email": "microsoft.student@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported Microsoft 365 smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}: {response.text[:1800]}")


async def fake_graph(email: str, method: str, path: str, *, params=None, json_body=None):
    if email != "microsoft.instructor@example.com":
        raise RuntimeError(f"Unexpected Graph identity: {email}")
    if method == "GET" and path == "/me/drive/root/children":
        return {"value": [
            {"id": "drive-doc", "name": "Module One.docx", "webUrl": "https://tenant.sharepoint.com/personal/instructor/Documents/ModuleOne.docx", "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}},
            {"id": "drive-folder", "name": "Folder", "webUrl": "https://tenant.sharepoint.com/folder", "folder": {"childCount": 2}},
        ]}
    if method == "GET" and path == "/sites":
        return {"value": [{"id": "tenant.sharepoint.com,site,web", "name": "CETL", "displayName": "CETL Faculty", "webUrl": "https://tenant.sharepoint.com/sites/cetl"}]}
    if method == "GET" and path == "/sites/tenant.sharepoint.com,site,web/drive/root/children":
        return {"value": [{"id": "sp-ppt", "name": "Faculty Workshop.pptx", "webUrl": "https://tenant.sharepoint.com/sites/cetl/Shared%20Documents/FacultyWorkshop.pptx", "file": {"mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}}]}
    if method == "POST" and path == "/me/events":
        if not json_body or not json_body.get("isOnlineMeeting") or json_body.get("onlineMeetingProvider") != "teamsForBusiness":
            raise RuntimeError(f"Teams-enabled Outlook payload is incomplete: {json_body}")
        return {
            "id": "outlook-event-365",
            "webLink": "https://outlook.office.com/calendar/item/365",
            "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/365"},
        }
    raise RuntimeError(f"Unexpected Graph request: {method} {path} {params}")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "microsoft.admin@example.com", "password": "Initial-Microsoft-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Microsoft-2026!", "confirm": "Updated-Microsoft-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "MS365-4100",
            "title": "Microsoft 365 Integration",
            "description": "Microsoft Entra ID, Graph, OneDrive, SharePoint, Teams, and Outlook validation.",
            "term": "Fall 2026",
            "instructor_email": "microsoft.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "microsoft.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (course_id, "Microsoft Module", "Microsoft resources.", "Use Microsoft 365 resources.", 45, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND title=?", (course_id, "Microsoft Module")))[0]["id"])

        expect(client.get("/__smoke/microsoft-user/instructor"), 200, "instructor session")
        page = client.get(f"/faculty/studio/courses/{course_id}/microsoft365")
        expect(page, 200, "Microsoft 365 course hub")
        require(page, 'data-testid="microsoft365-integration-v1"', "Microsoft 365 hub marker")
        require(page, "OneDrive", "OneDrive section")
        require(page, "SharePoint", "SharePoint section")
        require(page, "Teams meeting + Outlook Calendar", "Teams/Outlook section")

        connect = client.get(f"/portal/microsoft-connect?next=/faculty/studio/courses/{course_id}/microsoft365")
        expect(connect, 303, "Microsoft connect redirect")
        if connect.headers.get("location") != "/auth/microsoft/login":
            raise RuntimeError("Microsoft connect did not route to the Entra authorization entry point.")
        oauth = client.get("/auth/microsoft/login")
        expect(oauth, 303, "Microsoft OAuth authorization redirect")
        location = oauth.headers.get("location", "")
        if "login.microsoftonline.com/organizations/oauth2/v2.0/authorize" not in location or "code_challenge=" not in location or "client_id=00000000-0000-0000-0000-000000000365" not in location:
            raise RuntimeError(f"Microsoft OAuth redirect is missing Entra/PKCE parameters: {location}")

        with db() as conn:
            microsoft365._store_connection(
                conn,
                "microsoft.instructor@example.com",
                tenant_id="tenant-smoke",
                account_id="account-smoke",
                display_name="Microsoft Instructor",
                access_token="raw-access-token-must-not-be-stored",
                refresh_token="raw-refresh-token-must-not-be-stored",
                expires_in=3600,
                scopes=microsoft365.DEFAULT_SCOPES,
            )
            stored = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_connections WHERE user_email=?", ("microsoft.instructor@example.com",)))[0]
            if "raw-access-token" in str(stored.get("access_token_enc")) or "raw-refresh-token" in str(stored.get("refresh_token_enc")):
                raise RuntimeError("Microsoft OAuth tokens were stored without encryption.")
            if microsoft365._decrypt(str(stored["access_token_enc"])) != "raw-access-token-must-not-be-stored":
                raise RuntimeError("Encrypted Microsoft access token could not be recovered by the server key.")

        microsoft365._graph_json = fake_graph

        status = client.get("/api/microsoft365/connection")
        expect(status, 200, "Microsoft connection status")
        if not status.json().get("connected"):
            raise RuntimeError("Microsoft connection status did not report the stored connection.")

        one = client.get("/api/microsoft365/onedrive/files")
        expect(one, 200, "OneDrive listing")
        if one.json()["files"][0].get("nuvedraType") != "document":
            raise RuntimeError(f"OneDrive Office type mapping failed: {one.json()}")

        sites = client.get("/api/microsoft365/sharepoint/sites?q=CETL")
        expect(sites, 200, "SharePoint site search")
        if sites.json()["sites"][0].get("displayName") != "CETL Faculty":
            raise RuntimeError("SharePoint site search did not return the mocked site.")
        sp_files = client.get("/api/microsoft365/sharepoint/sites/tenant.sharepoint.com,site,web/files")
        expect(sp_files, 200, "SharePoint file listing")
        if sp_files.json()["files"][0].get("nuvedraType") != "presentation":
            raise RuntimeError("SharePoint PowerPoint type mapping failed.")

        linked = client.post(f"/faculty/studio/courses/{course_id}/microsoft365/link", data={
            "module_id": str(module_id),
            "title": "Module One.docx",
            "url": "https://tenant.sharepoint.com/personal/instructor/Documents/ModuleOne.docx",
            "item_type": "document",
        })
        expect(linked, 303, "Microsoft module link")
        with db() as conn:
            item = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? AND title=?", (module_id, "Module One.docx")))[0]
            metadata = json.loads(str(item.get("metadata_json") or "{}"))
            if item.get("status") != "draft" or metadata.get("source") != "microsoft365":
                raise RuntimeError(f"Microsoft-linked course content did not remain draft/source-tagged: {item}")

        library = client.post("/faculty/microsoft365/library-link", data={
            "name": "Faculty Workshop.pptx",
            "source_url": "https://tenant.sharepoint.com/sites/cetl/Shared%20Documents/FacultyWorkshop.pptx",
            "asset_type": "presentation",
        })
        expect(library, 303, "Microsoft Content Library link")
        with db() as conn:
            assets = rows(execute(conn, "SELECT * FROM nuvedra_library_assets WHERE owner_email=? AND name=?", ("microsoft.instructor@example.com", "Faculty Workshop.pptx")))
            if len(assets) != 1 or assets[0].get("asset_type") != "presentation":
                raise RuntimeError("Microsoft resource was not saved to Content Library.")

        start = (datetime.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        end = start + timedelta(hours=1)
        meeting = client.post(f"/faculty/studio/courses/{course_id}/microsoft365/meetings", data={
            "title": "Teams faculty review",
            "description": "Review Microsoft 365 course integration.",
            "starts_at": start.isoformat(timespec="minutes"),
            "ends_at": end.isoformat(timespec="minutes"),
            "time_zone": "SA Western Standard Time",
        })
        expect(meeting, 303, "Teams-enabled Outlook meeting")
        with db() as conn:
            events = rows(execute(conn, "SELECT * FROM nuvedra_course_events WHERE course_id=? AND title=?", (course_id, "Teams faculty review")))
            if len(events) != 1 or "teams.microsoft.com" not in str(events[0].get("location") or ""):
                raise RuntimeError("Teams meeting was not mirrored into the NUVEDRA course calendar.")
            links = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_event_links WHERE course_event_id=?", (int(events[0]["id"]),)))
            if len(links) != 1 or links[0].get("microsoft_event_id") != "outlook-event-365":
                raise RuntimeError("Outlook event linkage was not stored.")
            notifications = rows(execute(conn, "SELECT * FROM nuvedra_notifications WHERE recipient_email=? AND course_id=? AND title=?", ("microsoft.student@example.com", course_id, "Teams faculty review")))
            if len(notifications) != 1:
                raise RuntimeError("Teams meeting did not create the student course notification.")

        expect(client.get("/__smoke/microsoft-user/student"), 200, "student session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/microsoft365"), 403, "student Microsoft faculty hub protection")
        expect(client.get("/api/microsoft365/onedrive/files"), 403, "student OneDrive faculty API protection")

        expect(client.get("/__smoke/microsoft-user/instructor"), 200, "restore instructor session")
        expect(client.post("/portal/microsoft-disconnect"), 303, "Microsoft disconnect")
        with db() as conn:
            if rows(execute(conn, "SELECT id FROM nuvedra_microsoft_connections WHERE user_email=?", ("microsoft.instructor@example.com",))):
                raise RuntimeError("Microsoft disconnect did not remove stored OAuth tokens.")

    print("Microsoft 365 Integration v1 validated: Entra OAuth/PKCE redirect, encrypted token storage, OneDrive, SharePoint, draft course links, Content Library reuse, Teams-enabled Outlook events, calendar notifications, disconnect, and role protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
