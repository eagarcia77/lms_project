from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-microsoft365-classwork-v4-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft-classwork-v4-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft-classwork-v4-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "msv4.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Microsoft-V4-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Microsoft V4 Administrator"
os.environ["MICROSOFT_CLIENT_ID"] = "microsoft-v4-client"
os.environ["MICROSOFT_CLIENT_SECRET"] = "microsoft-v4-client-secret-never-render"
os.environ["MICROSOFT_TENANT_ID"] = "11111111-2222-3333-4444-555555555555"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example/auth/microsoft/callback"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "microsoft-classwork-v4-token-encryption-key-2026"
os.environ["MICROSOFT_SCOPES"] = "openid profile email offline_access User.Read Files.Read Sites.Read.All Calendars.ReadWrite"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
from app.unified_authoring import _insert_item  # noqa: E402
import app.microsoft365_classwork_v4 as v4  # noqa: E402
import app.microsoft365_integration as m365  # noqa: E402

TEMPLATE_URL = "https://tenant.sharepoint.com/:w:/r/sites/course/Shared%20Documents/AssignmentTemplate.docx"
STUDENT_URL = "https://tenant-my.sharepoint.com/:w:/g/personal/student/StudentWork.docx"


@app.get("/__smoke/microsoft-v4-user/{kind}", include_in_schema=False)
async def smoke_microsoft_v4_user(kind: str, request: Request):
    identities = {
        "instructor": ("msv4-instructor", "Microsoft V4 Instructor", "msv4.instructor@example.com"),
        "student": ("msv4-student", "Microsoft V4 Student", "msv4.student@example.com"),
        "observer": ("msv4-observer", "Microsoft V4 Observer", "msv4.observer@example.com"),
    }
    if kind not in identities:
        raise RuntimeError("Unsupported Microsoft v4 smoke user.")
    user_id, name, email = identities[kind]
    request.session["user"] = {"id": user_id, "name": name, "email": email}
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    graph_calls: list[tuple[str, str]] = []
    work_etag = {"value": '"student-v1"'}

    template_share = v4._share_id(TEMPLATE_URL)
    student_share = v4._share_id(STUDENT_URL)

    async def fake_graph_json(email: str, method: str, path: str, *, params=None, json_body=None):
        graph_calls.append((method.upper(), path))
        if method.upper() != "GET":
            raise RuntimeError(f"Classwork v4 unexpectedly attempted a Microsoft Graph write: {method} {path}")
        if path == f"/shares/{template_share}/driveItem":
            return {
                "id": "template-item-1",
                "name": "AssignmentTemplate.docx",
                "webUrl": TEMPLATE_URL,
                "size": 24576,
                "eTag": '"template-v1"',
                "lastModifiedDateTime": "2026-09-03T12:00:00Z",
                "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                "parentReference": {"driveId": "template-drive"},
            }
        if path == f"/shares/{student_share}/driveItem":
            return {
                "id": "student-work-item-1",
                "name": "StudentWork.docx",
                "webUrl": STUDENT_URL,
                "size": 32768,
                "eTag": work_etag["value"],
                "lastModifiedDateTime": "2026-09-03T12:30:00Z",
                "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                "parentReference": {"driveId": "student-drive"},
            }
        raise RuntimeError(f"Unexpected Microsoft Graph call: {method} {path} {params} {json_body}")

    original_graph_json = m365._graph_json
    m365._graph_json = fake_graph_json
    try:
        with TestClient(app, follow_redirects=False) as client:
            expect(client.post("/admin/login", data={"email": "msv4.admin@example.com", "password": "Initial-Microsoft-V4-2026!"}), 303, "admin login")
            expect(client.post("/admin/password", data={"password": "Updated-Microsoft-V4-2026!", "confirm": "Updated-Microsoft-V4-2026!"}), 303, "admin password update")
            response = client.post("/admin/authoring/courses", data={
                "course_code": "MSV4-4300",
                "title": "Microsoft 365 Classwork",
                "description": "Microsoft 365 Classwork v4 validation course.",
                "term": "Fall 2026",
                "instructor_email": "msv4.instructor@example.com",
                "template": "blank",
            })
            expect(response, 303, "course create")
            course_id = int(response.headers["location"].rsplit("/", 1)[-1])
            expect(client.post(f"/admin/authoring/courses/{course_id}/modules", data={
                "title": "Module 1",
                "description": "Classwork module",
                "learning_outcomes": "Complete Microsoft 365 work.",
                "estimated_minutes": "60",
                "position": "1",
            }), 303, "module create")
            now = utcnow()
            with db() as conn:
                module_rows = rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,)))
                module_id = int(module_rows[0]["id"])
                execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
                execute(conn, "UPDATE nexus_modules SET status='published',updated_at=? WHERE id=?", (now, module_id))
                _insert_item(conn, module_id, "assignment", "Microsoft 365 Analysis", body_html="<p>Complete the analysis in Microsoft 365.</p>", points=100, status="published")
                item_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? ORDER BY id DESC LIMIT 1", (module_id,)))[0]["id"])
                for email, role in [
                    ("msv4.student@example.com", "student"),
                    ("msv4.observer@example.com", "observer"),
                ]:
                    execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, email, role, "active", now))
                scopes = os.environ["MICROSOFT_SCOPES"]
                m365._store_connection(conn, "msv4.instructor@example.com", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="aad-instructor", display_name="Microsoft V4 Instructor", access_token="instructor-token", refresh_token="instructor-refresh", expires_in=3600, scopes=scopes)
                m365._store_connection(conn, "msv4.student@example.com", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="aad-student", display_name="Microsoft V4 Student", access_token="student-token", refresh_token="student-refresh", expires_in=3600, scopes=scopes)

            expect(client.get("/__smoke/microsoft-v4-user/instructor"), 200, "instructor session")
            course_page = client.get(f"/faculty/studio/courses/{course_id}/microsoft365/classwork")
            expect(course_page, 200, "faculty classwork page")
            require(course_page, 'data-testid="microsoft365-classwork-v4"', "faculty classwork page")
            assignment_page = client.get(f"/faculty/studio/assignments/{item_id}/microsoft365")
            expect(assignment_page, 200, "faculty Microsoft assignment page")
            require(assignment_page, 'data-testid="microsoft365-assignment-classwork-v4"', "faculty Microsoft assignment page")
            expect(client.post(f"/faculty/studio/assignments/{item_id}/microsoft365/template", data={
                "source_url": TEMPLATE_URL,
                "template_name": "Analysis Template",
                "distribution_mode": "personal_copy_required",
                "instructions": "Open the template, save a personal copy, complete it, and submit the personal link.",
            }), 303, "save Microsoft assignment template")
            with db() as conn:
                template = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_assignment_templates WHERE item_id=?", (item_id,)))[0]
                if template["validation_status"] != "verified" or template["source_item_id"] != "template-item-1":
                    raise RuntimeError("Instructor Microsoft template was not validated and persisted.")

            expect(client.get("/__smoke/microsoft-v4-user/student"), 200, "student session")
            normal_assignment = client.get(f"/learn/assignments/{item_id}")
            expect(normal_assignment, 200, "normal assignment page")
            require(normal_assignment, "Microsoft 365 work", "assignment Microsoft 365 navigation")
            student_page = client.get(f"/learn/assignments/{item_id}/microsoft365")
            expect(student_page, 200, "student Microsoft classwork page")
            require(student_page, 'data-testid="microsoft365-student-classwork-v4"', "student Microsoft classwork page")
            expect(client.post(f"/learn/assignments/{item_id}/microsoft365/link", data={"work_url": TEMPLATE_URL}), 409, "template-as-personal-work rejection")
            expect(client.post(f"/learn/assignments/{item_id}/microsoft365/link", data={"work_url": STUDENT_URL}), 303, "student Microsoft work validation")
            with db() as conn:
                work = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_student_work WHERE item_id=? AND student_email=?", (item_id, "msv4.student@example.com")))[0]
                if work["microsoft_item_id"] != "student-work-item-1" or work["status"] != "linked":
                    raise RuntimeError("Validated Microsoft student work was not persisted correctly.")
                if "student-token" in str(work.get("validation_json") or ""):
                    raise RuntimeError("Microsoft access token leaked into classwork validation metadata.")

            expect(client.post(f"/learn/assignments/{item_id}/microsoft365/submit"), 303, "Microsoft work turn-in")
            with db() as conn:
                submission = rows(execute(conn, "SELECT * FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, "msv4.student@example.com")))[0]
                if submission["status"] != "submitted" or submission["response_url"] != STUDENT_URL:
                    raise RuntimeError("Microsoft turn-in did not create the canonical NUVEDRA submission.")
                attempts = rows(execute(conn, "SELECT * FROM nuvedra_assignment_attempts WHERE submission_id=? ORDER BY attempt_no", (int(submission["id"]),)))
                evidence = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_work_attempts WHERE submission_id=? ORDER BY attempt_no", (int(submission["id"]),)))
                if len(attempts) != 1 or len(evidence) != 1 or evidence[0]["etag"] != '"student-v1"':
                    raise RuntimeError("Microsoft turn-in attempt metadata was not captured.")

            work_etag["value"] = '"student-v2"'
            expect(client.post(f"/learn/assignments/{item_id}/microsoft365/submit"), 303, "Microsoft work resubmission")
            with db() as conn:
                submission = rows(execute(conn, "SELECT * FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, "msv4.student@example.com")))[0]
                evidence = rows(execute(conn, "SELECT attempt_no,etag FROM nuvedra_microsoft_work_attempts WHERE submission_id=? ORDER BY attempt_no", (int(submission["id"]),)))
                if len(evidence) != 2 or evidence[1]["attempt_no"] != 2 or evidence[1]["etag"] != '"student-v2"':
                    raise RuntimeError("Microsoft 365 resubmission history was not preserved.")

            expect(client.get(f"/faculty/studio/courses/{course_id}/microsoft365/classwork"), 403, "student faculty classwork protection")
            expect(client.get("/__smoke/microsoft-v4-user/observer"), 200, "observer session")
            observer = client.get(f"/learn/assignments/{item_id}/microsoft365")
            expect(observer, 200, "observer Microsoft classwork view")
            require(observer, "Observers can view", "observer read-only message")
            expect(client.post(f"/learn/assignments/{item_id}/microsoft365/link", data={"work_url": STUDENT_URL}), 403, "observer submission protection")

            if any(method != "GET" for method, _path in graph_calls):
                raise RuntimeError("Microsoft 365 Classwork v4 performed an unexpected Graph write operation.")

        print("Microsoft 365 Classwork & Assignments v4 validated: template validation, personal-copy enforcement, Microsoft work-link validation, metadata-only evidence, canonical NUVEDRA submissions, resubmission snapshots, observer read-only behavior, and faculty role protection.", flush=True)
    finally:
        m365._graph_json = original_graph_json
        if DB_PATH.exists():
            DB_PATH.unlink()


if __name__ == "__main__":
    main()
