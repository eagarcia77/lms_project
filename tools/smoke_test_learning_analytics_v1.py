from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-learning-analytics-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "learning-analytics-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "learning-analytics-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "analytics.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Analytics-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Analytics Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/analytics/{kind}", include_in_schema=False)
async def smoke_analytics_user(kind: str, request: Request):
    if kind == "student":
        request.session["user"] = {"id": "analytics-student", "name": "Analytics Student", "email": "analytics.student@example.com"}
    elif kind == "admin":
        request.session.pop("user", None)
    else:
        raise RuntimeError("Unsupported analytics smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1400]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def create_item(client: TestClient, module_id: int, item_type: str, title: str) -> int:
    expect(client.post(f"/faculty/studio/modules/{module_id}/items", data={
        "item_type": item_type,
        "title": title,
        "body_html": f"<h2>{title}</h2><p>Analytics validation content.</p>",
        "external_url": "",
        "embed_url": "",
        "points": "10" if item_type == "assignment" else "",
        "due_at": "",
        "accessible_alternative": "",
        "assessment_response_type": "text",
        "attempts": "1",
        "time_limit": "0",
        "rubric": "",
    }), 303, f"create {title}")
    with db() as conn:
        return int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title=? ORDER BY id DESC LIMIT 1", (module_id, title)))[0]["id"])


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "analytics.admin@example.com", "password": "Initial-Analytics-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Analytics-2026!", "confirm": "Updated-Analytics-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "ANLY-1000",
            "title": "Learning Analytics v1",
            "description": "Instructor analytics validation.",
            "term": "Fall 2026",
            "instructor_email": "",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        expect(client.post(f"/faculty/studio/courses/{course_id}/modules", data={
            "title": "Analytics Module",
            "description": "Published module for analytics.",
            "learning_outcomes": "Interpret learning analytics responsibly.",
            "estimated_minutes": "30",
        }), 303, "module creation")
        with db() as conn:
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,)))[0]["id"])

        page_done = create_item(client, module_id, "page", "Completed Reading")
        assignment = create_item(client, module_id, "assignment", "Submitted Assignment")
        page_overdue = create_item(client, module_id, "page", "Overdue Reading")

        with db() as conn:
            now = utcnow()
            execute(conn, "UPDATE nexus_admin_courses SET status='active' WHERE id=?", (course_id,))
            execute(conn, "UPDATE nexus_modules SET status='published' WHERE id=?", (module_id,))
            execute(conn, "UPDATE nexus_content_items SET status='published' WHERE id IN (?,?,?)", (page_done, assignment, page_overdue))
            execute(conn, "UPDATE nexus_content_items SET due_at='2025-01-01T12:00:00+00:00' WHERE id=?", (page_overdue,))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "analytics.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nuvedra_content_progress (item_id,student_email,status,completed_at,updated_at) VALUES (?,?,?,?,?)", (page_done, "analytics.student@example.com", "completed", now, now))
            execute(conn, "INSERT INTO nuvedra_submissions (item_id,student_email,response_text,response_url,status,submitted_at,updated_at) VALUES (?,?,?,?,?,?,?)", (assignment, "analytics.student@example.com", "Submitted work", "", "submitted", now, now))
            submission_id = int(rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (assignment, "analytics.student@example.com")))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_grades (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at) VALUES (?,?,?,?,?,?,?)", (submission_id, 8.0, "Good progress", "graded", "analytics.admin@example.com", now, now))

        dashboard = client.get(f"/faculty/studio/courses/{course_id}/analytics")
        expect(dashboard, 200, "learning analytics dashboard")
        require(dashboard, 'data-testid="learning-analytics-v1"', "learning analytics dashboard")
        require(dashboard, "analytics.student@example.com", "student analytics row")
        require(dashboard, "67%", "student progress")
        require(dashboard, "Needs attention", "attention indicator")
        require(dashboard, "Average graded score", "graded score metric")

        export = client.get(f"/faculty/studio/courses/{course_id}/analytics.csv")
        expect(export, 200, "analytics CSV export")
        require(export, "Progress percent", "analytics CSV header")
        require(export, "analytics.student@example.com", "analytics CSV student")

        expect(client.get("/__smoke/analytics/student"), 200, "student session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/analytics"), 403, "student analytics protection")

    print("Learning Analytics v1 validated: instructor dashboard, progress, overdue attention signal, graded score, CSV export, and student protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
