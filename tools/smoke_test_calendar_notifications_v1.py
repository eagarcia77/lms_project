from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-calendar-notifications-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "calendar-notifications-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "calendar-notifications-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "calendar.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Calendar-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Calendar Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/calendar-user/{kind}", include_in_schema=False)
async def smoke_calendar_user(kind: str, request: Request):
    if kind == "instructor":
        request.session["user"] = {"id": "calendar-instructor", "name": "Calendar Instructor", "email": "calendar.instructor@example.com"}
    elif kind == "student":
        request.session["user"] = {"id": "calendar-student", "name": "Calendar Student", "email": "calendar.student@example.com"}
    else:
        raise RuntimeError("Unsupported calendar smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1600]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "calendar.admin@example.com", "password": "Initial-Calendar-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Calendar-2026!", "confirm": "Updated-Calendar-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "CAL-3100",
            "title": "Calendar and Notifications v1",
            "description": "Course calendar and in-app notification validation.",
            "term": "Fall 2026",
            "instructor_email": "calendar.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])

        due_at = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat(timespec="minutes")
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "calendar.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (course_id, "Calendar Module", "Published module.", "Coordinate deadlines.", 30, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND title=?", (course_id, "Calendar Module")))[0]["id"])
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_id, "assignment", "Calendar Assignment", "<p>Submit the calendar assignment.</p>", "", "", "{}", 10, due_at, 1, "published", now, now))

        expect(client.get("/__smoke/calendar-user/instructor"), 200, "instructor session")
        page = client.get(f"/faculty/studio/courses/{course_id}/calendar")
        expect(page, 200, "instructor calendar")
        require(page, 'data-testid="course-calendar-v1"', "instructor calendar")
        require(page, "Calendar Assignment", "published due date")

        starts_at = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat(timespec="minutes")
        event = client.post(f"/faculty/studio/courses/{course_id}/calendar/events", data={
            "title": "Live review session",
            "description": "Review course progress and answer questions.",
            "event_type": "meeting",
            "starts_at": starts_at,
            "ends_at": "",
            "location": "https://meet.example.edu/calendar",
        })
        expect(event, 303, "event creation")
        with db() as conn:
            event_rows = rows(execute(conn, "SELECT id FROM nuvedra_course_events WHERE course_id=? AND title=? AND status='active'", (course_id, "Live review session")))
            if len(event_rows) != 1:
                raise RuntimeError("Calendar event was not stored.")
            notifications = rows(execute(conn, "SELECT id,read_at FROM nuvedra_notifications WHERE recipient_email=? AND course_id=?", ("calendar.student@example.com", course_id)))
            if len(notifications) != 1 or notifications[0].get("read_at"):
                raise RuntimeError("Student notification was not created as unread.")
            notification_id = int(notifications[0]["id"])

        expect(client.get("/__smoke/calendar-user/student"), 200, "student session")
        student_calendar = client.get("/learn/calendar")
        expect(student_calendar, 200, "student calendar")
        require(student_calendar, 'data-testid="student-calendar-v1"', "student calendar")
        require(student_calendar, "Live review session", "student course event")
        require(student_calendar, "Calendar Assignment", "student due date")

        notification_page = client.get("/portal/notifications")
        expect(notification_page, 200, "notification center")
        require(notification_page, 'data-testid="notifications-center-v1"', "notification center")
        require(notification_page, "Live review session", "notification title")
        require(notification_page, "Unread", "unread notification summary")

        expect(client.post(f"/portal/notifications/{notification_id}/read"), 303, "mark notification read")
        notification_page = client.get("/portal/notifications")
        expect(notification_page, 200, "notification center after read")
        require(notification_page, ": 0</h2>", "zero unread notifications")

        expect(client.get(f"/faculty/studio/courses/{course_id}/calendar"), 403, "student instructor-calendar protection")

    print("Calendar and Notifications v1 validated: instructor events, published due dates, student calendar, in-app notifications, read state, and role protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
