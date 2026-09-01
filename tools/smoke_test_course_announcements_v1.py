from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-course-announcements-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "announcements-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "announcements-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "announcements.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Announcements-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Announcements Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/announcements-user/{kind}", include_in_schema=False)
async def smoke_announcements_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "ann-inst", "name": "Announcements Instructor", "email": "announcements.instructor@example.com"},
        "student": {"id": "ann-student", "name": "Announcements Student", "email": "announcements.student@example.com"},
        "observer": {"id": "ann-observer", "name": "Announcements Observer", "email": "announcements.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported announcements smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1600]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "announcements.admin@example.com", "password": "Initial-Announcements-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Announcements-2026!", "confirm": "Updated-Announcements-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "ANN-4100",
            "title": "Course Announcements v1",
            "description": "Announcement publishing and notification validation.",
            "term": "Fall 2026",
            "instructor_email": "announcements.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "announcements.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "announcements.observer@example.com", "observer", "active", now))

        expect(client.get("/__smoke/announcements-user/instructor"), 200, "instructor session")
        page = client.get(f"/faculty/studio/courses/{course_id}/announcements")
        expect(page, 200, "instructor announcements")
        require(page, 'data-testid="course-announcements-v1"', "instructor announcements")

        draft = client.post(f"/faculty/studio/courses/{course_id}/announcements", data={
            "title": "Welcome to ANN-4100",
            "message": "Please review the course orientation before beginning Module 1.",
            "priority": "important",
            "status": "draft",
        })
        expect(draft, 303, "draft announcement creation")
        with db() as conn:
            announcement = rows(execute(conn, "SELECT * FROM nuvedra_course_announcements WHERE course_id=? AND title=?", (course_id, "Welcome to ANN-4100")))[0]
            announcement_id = int(announcement["id"])
            if announcement["status"] != "draft":
                raise RuntimeError("Announcement was not stored as draft.")
            notifications = rows(execute(conn, "SELECT id FROM nuvedra_notifications WHERE course_id=?", (course_id,)))
            if notifications:
                raise RuntimeError("Draft announcement generated notifications before publication.")

        expect(client.post(f"/faculty/studio/announcements/{announcement_id}/publish"), 303, "announcement publication")
        with db() as conn:
            announcement = rows(execute(conn, "SELECT status,published_at FROM nuvedra_course_announcements WHERE id=?", (announcement_id,)))[0]
            if announcement["status"] != "published" or not announcement.get("published_at"):
                raise RuntimeError("Announcement was not published correctly.")
            notifications = rows(execute(conn, "SELECT recipient_email,kind,read_at FROM nuvedra_notifications WHERE course_id=? ORDER BY recipient_email", (course_id,)))
            recipients = [row["recipient_email"] for row in notifications]
            if recipients != ["announcements.observer@example.com", "announcements.student@example.com"]:
                raise RuntimeError(f"Published announcement did not notify both enrolled viewers: {recipients}")
            if any(row.get("read_at") for row in notifications) or any(row.get("kind") != "announcement" for row in notifications):
                raise RuntimeError("Announcement notifications were not created as unread announcement notifications.")

        expect(client.get("/__smoke/announcements-user/student"), 200, "student session")
        student_page = client.get("/learn/announcements")
        expect(student_page, 200, "student announcements")
        require(student_page, 'data-testid="student-announcements-v1"', "student announcements")
        require(student_page, "Welcome to ANN-4100", "published student announcement")
        notification_page = client.get("/portal/notifications")
        expect(notification_page, 200, "student notification center")
        require(notification_page, "Welcome to ANN-4100", "announcement notification")
        expect(client.get(f"/faculty/studio/courses/{course_id}/announcements"), 403, "student instructor-announcements protection")

        expect(client.get("/__smoke/announcements-user/observer"), 200, "observer session")
        observer_page = client.get("/learn/announcements")
        expect(observer_page, 200, "observer announcements")
        require(observer_page, "Welcome to ANN-4100", "observer announcement visibility")

        expect(client.get("/__smoke/announcements-user/instructor"), 200, "return instructor session")
        expect(client.post(f"/faculty/studio/announcements/{announcement_id}/archive"), 303, "announcement archive")
        expect(client.get("/__smoke/announcements-user/student"), 200, "return student session")
        archived_page = client.get("/learn/announcements")
        expect(archived_page, 200, "student announcements after archive")
        if "Welcome to ANN-4100" in archived_page.text:
            raise RuntimeError("Archived announcement is still visible in the student announcement feed.")

    print("Course Announcements v1 validated: draft/publish workflow, student and observer visibility, notification fan-out, archive behavior, and role protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
