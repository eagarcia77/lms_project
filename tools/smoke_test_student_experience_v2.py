from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-student-experience-v2-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "student-experience-v2-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "student-experience-v2-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "student.exp.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Student-Experience-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Student Experience Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/student-experience/{kind}", include_in_schema=False)
async def smoke_user(kind: str, request: Request):
    if kind == "student":
        request.session["user"] = {"id": "student-exp", "name": "Student Experience", "email": "student.exp@example.com"}
    elif kind == "observer":
        request.session["user"] = {"id": "observer-exp", "name": "Observer Experience", "email": "observer.exp@example.com"}
    elif kind == "admin":
        request.session.pop("user", None)
    else:
        raise RuntimeError("Unsupported smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1200]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "student.exp.admin@example.com", "password": "Initial-Student-Experience-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Student-Experience-2026!", "confirm": "Updated-Student-Experience-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={"course_code": "STU-2200", "title": "Student Experience v2", "description": "Progress and to-do validation.", "term": "Fall 2026", "instructor_email": "", "template": "blank"})
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        expect(client.post(f"/faculty/studio/courses/{course_id}/modules", data={"title": "Learning Module", "description": "Published content.", "learning_outcomes": "Track learning progress.", "estimated_minutes": "30"}), 303, "module creation")
        with db() as conn:
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,)))[0]["id"])
        expect(client.post(f"/faculty/studio/modules/{module_id}/update", data={"title": "Learning Module", "description": "Published content.", "learning_outcomes": "Track learning progress.", "estimated_minutes": "30", "position": "1", "status": "published"}), 303, "module publishing")

        for position, title in ((1, "Orientation Page"), (2, "Practice Page")):
            expect(client.post(f"/faculty/studio/modules/{module_id}/items", data={"item_type": "page", "title": title, "body_html": f"<p>{title} content.</p>", "external_url": "", "embed_url": "", "points": "", "due_at": "2099-12-31T23:59", "accessible_alternative": f"{title} accessible text.", "assessment_response_type": "text", "attempts": "1", "time_limit": "0", "rubric": ""}), 303, f"{title} creation")
            with db() as conn:
                item_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title=? ORDER BY id DESC LIMIT 1", (module_id, title)))[0]["id"])
            expect(client.post(f"/faculty/studio/items/{item_id}/edit", data={"item_type": "page", "title": title, "body_html": f"<p>{title} content.</p>", "external_url": "", "embed_url": "", "points": "", "due_at": "2099-12-31T23:59", "position": str(position), "status": "published", "accessible_alternative": f"{title} accessible text.", "assessment_response_type": "text", "attempts": "1", "time_limit": "0", "rubric": ""}), 303, f"{title} publishing")

        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (utcnow(), course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "student.exp@example.com", "student", "active", utcnow()))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "observer.exp@example.com", "observer", "active", utcnow()))
            items = rows(execute(conn, "SELECT id,title FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (module_id,)))
            first_id = int(items[0]["id"])
            second_id = int(items[1]["id"])

        expect(client.get("/__smoke/student-experience/student"), 200, "student session")
        dashboard = client.get("/learn/dashboard")
        expect(dashboard, 200, "student dashboard")
        require(dashboard, 'data-testid="student-dashboard"', "student dashboard")
        require(dashboard, "0%", "initial student dashboard")
        require(dashboard, "Continue learning", "student dashboard")
        require(dashboard, "2", "student dashboard due items")

        course = client.get(f"/learn/courses/{course_id}")
        expect(course, 200, "student course")
        require(course, 'data-testid="student-course-v2"', "student course")
        require(course, "0/2", "initial course progress")

        item = client.get(f"/learn/items/{first_id}")
        expect(item, 200, "student item")
        require(item, 'data-testid="student-item-v2"', "student item")
        require(item, "Mark complete", "student item")
        expect(client.post(f"/learn/items/{first_id}/complete", data={"completed": "1"}), 303, "mark first item complete")

        dashboard = client.get("/learn/dashboard")
        expect(dashboard, 200, "student dashboard after one completion")
        require(dashboard, "50%", "student dashboard after one completion")
        todo = client.get("/learn/todo")
        expect(todo, 200, "student to-do")
        require(todo, 'data-testid="student-todo"', "student to-do")
        if "Orientation Page" in todo.text:
            raise RuntimeError("Completed content remained in the student to-do list.")
        require(todo, "Practice Page", "student to-do")

        expect(client.post(f"/learn/items/{second_id}/complete", data={"completed": "1"}), 303, "mark second item complete")
        dashboard = client.get("/learn/dashboard")
        expect(dashboard, 200, "student dashboard complete")
        require(dashboard, "100%", "completed student dashboard")
        require(dashboard, "You are caught up.", "completed student dashboard")

        expect(client.get("/__smoke/student-experience/observer"), 200, "observer session")
        expect(client.get(f"/learn/courses/{course_id}"), 200, "observer course view")
        expect(client.post(f"/learn/items/{first_id}/complete", data={"completed": "1"}), 403, "observer completion protection")

    print("Student Experience v2 validated: dashboard, course progress, continue learning, to-do filtering, completion tracking, and observer protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
