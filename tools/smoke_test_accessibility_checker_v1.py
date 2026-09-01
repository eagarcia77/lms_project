from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-accessibility-checker-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "accessibility-checker-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "accessibility-checker-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "accessibility.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Accessibility-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Accessibility Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/accessibility/{kind}", include_in_schema=False)
async def smoke_accessibility_user(kind: str, request: Request):
    if kind == "student":
        request.session["user"] = {"id": "a11y-student", "name": "Accessibility Student", "email": "accessibility.student@example.com"}
    elif kind == "admin":
        request.session.pop("user", None)
    else:
        raise RuntimeError("Unsupported accessibility smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1400]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "accessibility.admin@example.com", "password": "Initial-Accessibility-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Accessibility-2026!", "confirm": "Updated-Accessibility-2026!"}), 303, "admin password update")

        created = client.post("/admin/authoring/courses", data={
            "course_code": "A11Y-1000",
            "title": "Accessibility Checker v1",
            "description": "Automated accessibility publication gate validation.",
            "term": "Fall 2026",
            "instructor_email": "",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])

        expect(client.post(f"/faculty/studio/courses/{course_id}/modules", data={
            "title": "Accessible Content",
            "description": "Accessibility validation module.",
            "learning_outcomes": "Apply WCAG-oriented authoring practices.",
            "estimated_minutes": "30",
        }), 303, "module creation")
        with db() as conn:
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,)))[0]["id"])

        missing_alt_html = '<h2>Orientation</h2><p>Review the diagram.</p><img src="https://example.com/diagram.png">'
        expect(client.post(f"/faculty/studio/modules/{module_id}/items", data={
            "item_type": "page",
            "title": "Orientation Page",
            "body_html": missing_alt_html,
            "external_url": "",
            "embed_url": "",
            "points": "",
            "due_at": "",
            "accessible_alternative": "",
            "assessment_response_type": "text",
            "attempts": "1",
            "time_limit": "0",
            "rubric": "",
        }), 303, "page creation")
        with db() as conn:
            page_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title=? ORDER BY id DESC LIMIT 1", (module_id, "Orientation Page")))[0]["id"])

        report = client.get(f"/faculty/studio/items/{page_id}/accessibility")
        expect(report, 200, "item accessibility report")
        require(report, 'data-testid="item-accessibility-report"', "item accessibility report")
        require(report, "IMG_ALT_MISSING", "missing alt detection")
        require(report, 'data-accessibility-status="needs-review"', "blocking accessibility status")

        blocked = client.post(f"/faculty/studio/items/{page_id}/edit", data={
            "item_type": "page",
            "title": "Orientation Page",
            "body_html": missing_alt_html,
            "external_url": "",
            "embed_url": "",
            "points": "",
            "due_at": "",
            "position": "1",
            "status": "published",
            "accessible_alternative": "",
            "assessment_response_type": "text",
            "attempts": "1",
            "time_limit": "0",
            "rubric": "",
        })
        expect(blocked, 409, "publication block for missing alt")
        require(blocked, "Accessibility check failed before publication", "publication block message")

        fixed_html = '<h2>Orientation</h2><p>Review the diagram.</p><img src="https://example.com/diagram.png" alt="Flow diagram showing the learning sequence">'
        expect(client.post(f"/faculty/studio/items/{page_id}/edit", data={
            "item_type": "page",
            "title": "Orientation Page",
            "body_html": fixed_html,
            "external_url": "",
            "embed_url": "",
            "points": "",
            "due_at": "",
            "position": "1",
            "status": "published",
            "accessible_alternative": "",
            "assessment_response_type": "text",
            "attempts": "1",
            "time_limit": "0",
            "rubric": "",
        }), 303, "accessible page publication")
        report = client.get(f"/faculty/studio/items/{page_id}/accessibility")
        expect(report, 200, "passing item accessibility report")
        require(report, 'data-accessibility-status="pass"', "passing item accessibility status")
        require(report, "Accessibility check passed", "passing accessibility message")

        expect(client.post(f"/faculty/studio/modules/{module_id}/items", data={
            "item_type": "vr",
            "title": "Virtual Lab",
            "body_html": "<h2>Virtual Lab</h2><p>Explore the immersive simulation.</p>",
            "external_url": "",
            "embed_url": "https://example.com/vr-lab",
            "points": "",
            "due_at": "",
            "accessible_alternative": "",
            "assessment_response_type": "text",
            "attempts": "1",
            "time_limit": "0",
            "rubric": "",
        }), 303, "VR item creation")
        with db() as conn:
            vr_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title=? ORDER BY id DESC LIMIT 1", (module_id, "Virtual Lab")))[0]["id"])

        expect(client.post(f"/faculty/studio/items/{vr_id}/toggle"), 409, "VR publication block without accessible alternative")
        accessible_text = "Equivalent non-immersive instructions describe every step and learning outcome in text."
        expect(client.post(f"/faculty/studio/items/{vr_id}/edit", data={
            "item_type": "vr",
            "title": "Virtual Lab",
            "body_html": "<h2>Virtual Lab</h2><p>Explore the immersive simulation.</p>",
            "external_url": "",
            "embed_url": "https://example.com/vr-lab",
            "points": "",
            "due_at": "",
            "position": "2",
            "status": "published",
            "accessible_alternative": accessible_text,
            "assessment_response_type": "text",
            "attempts": "1",
            "time_limit": "0",
            "rubric": "",
        }), 303, "VR publication with accessible alternative")

        course_report = client.get(f"/faculty/studio/courses/{course_id}/accessibility")
        expect(course_report, 200, "course accessibility report")
        require(course_report, 'data-testid="accessibility-checker-v1"', "course accessibility report")
        require(course_report, 'data-accessibility-status="pass"', "course accessibility passing status")

        with db() as conn:
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "accessibility.student@example.com", "student", "active", utcnow()))
        expect(client.get("/__smoke/accessibility/student"), 200, "student session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/accessibility"), 403, "student accessibility report protection")

    print("Accessibility Checker v1 validated: automated findings, publication blocking, corrected publication, XR alternatives, course report, and student protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
