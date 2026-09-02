from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-mastery-competency-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "mastery-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "mastery-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "mastery.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Mastery-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Mastery Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/mastery-user/{kind}", include_in_schema=False)
async def smoke_mastery_user(kind: str, request: Request):
    users = {
        "student1": {"id": "mastery-student-1", "name": "Mastery Student One", "email": "mastery.student1@example.com"},
        "student2": {"id": "mastery-student-2", "name": "Mastery Student Two", "email": "mastery.student2@example.com"},
        "observer": {"id": "mastery-observer", "name": "Mastery Observer", "email": "mastery.observer@example.com"},
        "instructor": {"id": "mastery-instructor", "name": "Mastery Instructor", "email": "mastery.admin@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported mastery smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}: {response.text[:1800]}")


def insert_id(conn, sql: str, params: tuple) -> int:
    cursor = execute(conn, sql, params)
    return int(cursor.lastrowid)


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "mastery.admin@example.com", "password": "Initial-Mastery-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Mastery-2026!", "confirm": "Updated-Mastery-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "MAST-7600", "title": "Competency Evidence", "description": "Mastery dashboard validation course.",
            "term": "Fall 2026", "instructor_email": "mastery.admin@example.com", "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()

        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (
                ("mastery.student1@example.com", "student"),
                ("mastery.student2@example.com", "student"),
                ("mastery.observer@example.com", "observer"),
            ):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, email, role, "active", now))
            module_id = insert_id(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "Evidence Module", "Competency evidence.", "Demonstrate applied mastery.", 45, 1, "published", now, now))

            item1 = insert_id(conn, """INSERT INTO nexus_content_items
                (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                VALUES (?,?,?,?,'','','{}',?,NULL,?,'published',?,?)""", (module_id, "assignment", "Applied Evidence", "<p>Applied evidence.</p>", 100, 1, now, now))
            item2 = insert_id(conn, """INSERT INTO nexus_content_items
                (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                VALUES (?,?,?,?,'','','{}',?,NULL,?,'published',?,?)""", (module_id, "project", "Strategic Project", "<p>Strategic project.</p>", 100, 2, now, now))

            outcome1 = insert_id(conn, """INSERT INTO nuvedra_outcomes
                (course_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'active',?,?,?)""", (course_id, "OUT-1", "Applied evidence", "Apply course concepts.", "mastery.admin@example.com", now, now))
            outcome2 = insert_id(conn, """INSERT INTO nuvedra_outcomes
                (course_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'active',?,?,?)""", (course_id, "OUT-2", "Strategic mastery", "Demonstrate strategic mastery.", "mastery.admin@example.com", now, now))
            outcome3 = insert_id(conn, """INSERT INTO nuvedra_outcomes
                (course_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'active',?,?,?)""", (course_id, "OUT-3", "Future evidence", "Evidence not yet collected.", "mastery.admin@example.com", now, now))
            execute(conn, "INSERT INTO nuvedra_outcome_links (outcome_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (outcome1, item1, "mastery.admin@example.com", now))
            execute(conn, "INSERT INTO nuvedra_outcome_links (outcome_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (outcome2, item2, "mastery.admin@example.com", now))

            submission1 = insert_id(conn, """INSERT INTO nuvedra_submissions
                (item_id,student_email,response_text,response_url,status,submitted_at,updated_at)
                VALUES (?,?,?,'','submitted',?,?)""", (item1, "mastery.student1@example.com", "Applied evidence response.", now, now))
            submission2 = insert_id(conn, """INSERT INTO nuvedra_submissions
                (item_id,student_email,response_text,response_url,status,submitted_at,updated_at)
                VALUES (?,?,?,'','submitted',?,?)""", (item2, "mastery.student1@example.com", "Strategic project response.", now, now))
            execute(conn, """INSERT INTO nuvedra_grades
                (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at)
                VALUES (?,?,?,'graded',?,?,?)""", (submission1, 85, "Proficient applied evidence.", "mastery.admin@example.com", now, now))
            execute(conn, """INSERT INTO nuvedra_grades
                (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at)
                VALUES (?,?,?,'graded',?,?,?)""", (submission2, 95, "Mastered strategic evidence.", "mastery.admin@example.com", now, now))

            rubric_id = insert_id(conn, """INSERT INTO nuvedra_rubrics
                (course_id,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,'active',?,?,?)""", (course_id, "Applied Competency Rubric", "Rubric evidence for OUT-1.", "mastery.admin@example.com", now, now))
            criterion_id = insert_id(conn, """INSERT INTO nuvedra_rubric_criteria
                (rubric_id,title,description,position,created_at) VALUES (?,?,?,?,?)""", (rubric_id, "Application", "Applies course concepts.", 1, now))
            level_id = insert_id(conn, """INSERT INTO nuvedra_rubric_levels
                (criterion_id,label,description,points,position,created_at) VALUES (?,?,?,?,?,?)""", (criterion_id, "Proficient", "Meets expected application level.", 85, 1, now))
            execute(conn, "INSERT INTO nuvedra_rubric_links (rubric_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (rubric_id, item1, "mastery.admin@example.com", now))
            evaluation_id = insert_id(conn, """INSERT INTO nuvedra_rubric_evaluations
                (submission_id,rubric_id,raw_score,possible_raw_score,grade_points,feedback,status,graded_by,graded_at,updated_at)
                VALUES (?,?,?,?,?,?,'graded',?,?,?)""", (submission1, rubric_id, 85, 100, 85, "Rubric supports proficiency.", "mastery.admin@example.com", now, now))
            execute(conn, """INSERT INTO nuvedra_rubric_scores
                (evaluation_id,criterion_id,level_id,points_awarded,feedback) VALUES (?,?,?,?,?)""", (evaluation_id, criterion_id, level_id, 85, "Proficient application."))

        expect(client.get("/__smoke/mastery-user/instructor"), 200, "instructor session")
        dashboard = client.get(f"/faculty/studio/courses/{course_id}/mastery")
        expect(dashboard, 200, "mastery instructor dashboard")
        require(dashboard, 'data-testid="mastery-competency-dashboard-v1"', "mastery instructor dashboard")
        require(dashboard, "OUT-1: Applied evidence", "outcome summary")
        require(dashboard, "100.0%", "proficiency summary")
        require(dashboard, "mastery.student1@example.com", "student summary")

        expect(client.post(f"/faculty/studio/courses/{course_id}/mastery/settings", data={"proficient_threshold": "95", "mastery_threshold": "90"}), 400, "invalid mastery thresholds")
        expect(client.post(f"/faculty/studio/courses/{course_id}/mastery/settings", data={"proficient_threshold": "80", "mastery_threshold": "90"}), 303, "valid mastery thresholds")

        detail = client.get(f"/faculty/studio/courses/{course_id}/mastery?student=mastery.student1%40example.com")
        expect(detail, 200, "instructor student mastery detail")
        require(detail, "85.0%", "proficient outcome attainment")
        require(detail, "95.0%", "mastered outcome attainment")
        require(detail, "85/100 rubric points", "rubric-supported evidence")

        export = client.get(f"/faculty/studio/courses/{course_id}/mastery.csv")
        expect(export, 200, "mastery CSV export")
        require(export, "mastery.student1@example.com", "mastery CSV student")
        require(export, "OUT-2", "mastery CSV outcome")
        require(export, "Mastered", "mastery CSV level")

        expect(client.get("/__smoke/mastery-user/student1"), 200, "student one session")
        student1 = client.get(f"/learn/courses/{course_id}/mastery")
        expect(student1, 200, "student mastery dashboard")
        require(student1, 'data-testid="student-mastery-dashboard-v1"', "student mastery dashboard")
        require(student1, "Proficient", "student proficient level")
        require(student1, "Mastered", "student mastered level")
        require(student1, "85/100 rubric points", "student rubric evidence")
        require(student1, "No evidence", "student unmeasured outcome")

        expect(client.get("/__smoke/mastery-user/student2"), 200, "student two session")
        student2 = client.get(f"/learn/courses/{course_id}/mastery")
        expect(student2, 200, "student two mastery dashboard")
        require(student2, "No evidence", "student two no evidence state")

        expect(client.get("/__smoke/mastery-user/observer"), 200, "observer session")
        expect(client.get(f"/learn/courses/{course_id}/mastery"), 403, "observer mastery privacy")
        expect(client.get(f"/faculty/studio/courses/{course_id}/mastery"), 403, "observer faculty mastery protection")

        js = Path("app/static/course-studio.js").read_text(encoding="utf-8")
        if "NUVEDRA_MASTERY_COMPETENCY_V1" not in js or "My Mastery" not in js:
            raise RuntimeError("Mastery navigation was not installed into Course Studio JavaScript.")

    print("Mastery & Competency Dashboard v1 validated: configurable thresholds, outcome attainment, rubric-supported evidence, instructor/student views, CSV export, privacy protection, and Studio navigation.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
