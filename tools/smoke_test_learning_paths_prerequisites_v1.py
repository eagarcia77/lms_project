from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-learning-paths-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "learning-path-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "learning-path-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "paths.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Paths-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Learning Paths Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/paths-user/{kind}", include_in_schema=False)
async def smoke_paths_user(kind: str, request: Request):
    users = {
        "student": {"id": "paths-student", "name": "Paths Student", "email": "paths.student@example.com"},
        "observer": {"id": "paths-observer", "name": "Paths Observer", "email": "paths.observer@example.com"},
        "instructor": {"id": "paths-instructor", "name": "Paths Instructor", "email": "paths.admin@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported learning-path smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}: {response.text[:1600]}")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "paths.admin@example.com", "password": "Initial-Paths-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Paths-2026!", "confirm": "Updated-Paths-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "PATH-7500", "title": "Adaptive Learning Paths", "description": "Prerequisite validation course.",
            "term": "Fall 2026", "instructor_email": "paths.admin@example.com", "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (("paths.student@example.com", "student"), ("paths.observer@example.com", "observer")):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, email, role, "active", now))
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "Foundation", "Complete foundation work first.", "Build foundational evidence.", 30, 1, "published", now, now))
            module1 = int(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND position=1", (course_id,)).fetchone()[0])
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "Advanced", "Unlocked through prerequisites.", "Apply advanced evidence.", 45, 2, "published", now, now))
            module2 = int(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND position=2", (course_id,)).fetchone()[0])

            def add_item(module_id: int, item_type: str, title: str, position: int, points: float | None = None) -> int:
                cursor = execute(conn, """INSERT INTO nexus_content_items
                    (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                    VALUES (?,?,?,?,'','','{}',?,NULL,?,'published',?,?)""", (module_id, item_type, title, f"<p>{title} content.</p>", points, position, now, now))
                return int(cursor.lastrowid)

            intro_id = add_item(module1, "content", "Foundation Orientation", 1)
            grade_source_id = add_item(module1, "assignment", "Foundation Evidence", 2, 100)
            locked_assignment_id = add_item(module2, "assignment", "Advanced Applied Project", 1, 100)
            cycle_a = add_item(module1, "content", "Cycle A", 3)
            cycle_b = add_item(module1, "content", "Cycle B", 4)

            outcome_id = int(execute(conn, """INSERT INTO nuvedra_outcomes
                (course_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'active',?,?,?)""", (course_id, "OUT-1", "Foundation mastery", "Demonstrate foundational mastery.", "paths.admin@example.com", now, now)).lastrowid)
            execute(conn, "INSERT INTO nuvedra_outcome_links (outcome_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (outcome_id, grade_source_id, "paths.admin@example.com", now))

        expect(client.get("/__smoke/paths-user/instructor"), 200, "instructor session")
        workspace = client.get(f"/faculty/studio/courses/{course_id}/paths")
        expect(workspace, 200, "learning-path workspace")
        require(workspace, 'data-testid="learning-paths-prerequisites-v1"', "learning-path workspace")

        rules = [
            {"target": f"module:{module2}", "rule_type": "item_completed", "source": f"item:{intro_id}", "threshold": ""},
            {"target": f"item:{locked_assignment_id}", "rule_type": "item_grade", "source": f"item:{grade_source_id}", "threshold": "80"},
            {"target": f"item:{locked_assignment_id}", "rule_type": "outcome_attainment", "source": f"outcome:{outcome_id}", "threshold": "80"},
        ]
        for index, data in enumerate(rules, 1):
            expect(client.post(f"/faculty/studio/courses/{course_id}/paths/rules", data=data), 303, f"prerequisite rule {index}")

        expect(client.post(f"/faculty/studio/courses/{course_id}/paths/rules", data={
            "target": f"item:{cycle_a}", "rule_type": "item_completed", "source": f"item:{cycle_b}", "threshold": "",
        }), 303, "first cycle edge")
        expect(client.post(f"/faculty/studio/courses/{course_id}/paths/rules", data={
            "target": f"item:{cycle_b}", "rule_type": "item_completed", "source": f"item:{cycle_a}", "threshold": "",
        }), 409, "cycle prevention")

        expect(client.get("/__smoke/paths-user/student"), 200, "student session")
        path_view = client.get(f"/learn/courses/{course_id}/path")
        expect(path_view, 200, "student learning path")
        require(path_view, 'data-testid="student-learning-path-v1"', "student learning path")
        require(path_view, "Locked", "student learning path locked state")

        gateway_locked = client.get(f"/learn/paths/items/{locked_assignment_id}")
        expect(gateway_locked, 200, "locked learning-path gateway")
        require(gateway_locked, 'data-testid="learning-path-locked-item"', "locked gateway")
        require(gateway_locked, "Foundation Orientation", "locked gateway completion reason")
        expect(client.get(f"/learn/assignments/{locked_assignment_id}"), 403, "direct assignment bypass protection")

        expect(client.get(f"/learn/items/{intro_id}"), 200, "available prerequisite item")
        expect(client.post(f"/learn/items/{intro_id}/complete", data={"completed": "1"}), 303, "complete prerequisite item")
        still_locked = client.get(f"/learn/paths/items/{locked_assignment_id}")
        expect(still_locked, 200, "grade-gated learning-path gateway")
        require(still_locked, "Foundation Evidence", "minimum-grade reason")
        require(still_locked, "Foundation mastery", "outcome-attainment reason")

        with db() as conn:
            submission_id = int(execute(conn, """INSERT INTO nuvedra_submissions
                (item_id,student_email,response_text,response_url,status,submitted_at,updated_at)
                VALUES (?,?,?,'','submitted',?,?)""", (grade_source_id, "paths.student@example.com", "Foundation evidence submitted.", now, now)).lastrowid)
            execute(conn, """INSERT INTO nuvedra_grades
                (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at)
                VALUES (?,?,?,'graded',?,?,?)""", (submission_id, 85, "Meets prerequisite threshold.", "paths.admin@example.com", now, now))

        unlocked = client.get(f"/learn/paths/items/{locked_assignment_id}")
        expect(unlocked, 303, "unlocked learning-path gateway")
        if unlocked.headers.get("location") != f"/learn/assignments/{locked_assignment_id}":
            raise RuntimeError(f"Learning-path gateway redirected to the wrong route: {unlocked.headers.get('location')}")
        expect(client.get(f"/learn/assignments/{locked_assignment_id}"), 200, "unlocked direct assignment")

        expect(client.get("/__smoke/paths-user/observer"), 200, "observer session")
        expect(client.get(f"/learn/assignments/{locked_assignment_id}"), 200, "observer read-only progression bypass")
        expect(client.get(f"/faculty/studio/courses/{course_id}/paths"), 403, "observer instructor-tool protection")

        expect(client.get("/__smoke/paths-user/instructor"), 200, "instructor return session")
        copied = client.post(f"/faculty/studio/courses/{course_id}/copy/new", data={
            "course_code": "PATH-7500-COPY", "title": "Adaptive Learning Paths Copy", "term": "Spring 2027",
            "module_ids": [str(module1), str(module2)], "copy_questions": "1", "copy_rubrics": "1", "copy_outcomes": "1",
        })
        expect(copied, 303, "course copy with learning paths")
        target_course_id = int(copied.headers["location"].rsplit("/", 1)[-1])
        with db() as conn:
            copied_rules = rows(execute(conn, "SELECT * FROM nuvedra_learning_path_rules WHERE course_id=? AND status='active'", (target_course_id,)))
            if len(copied_rules) < 4:
                raise RuntimeError(f"Course Copy did not preserve expected prerequisite rules: {copied_rules}")
            copied_items = {int(row["id"]) for row in rows(execute(conn, "SELECT i.id FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id WHERE m.course_id=?", (target_course_id,)))}
            copied_modules = {int(row["id"]) for row in rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (target_course_id,)))}
            for rule in copied_rules:
                if rule["target_type"] == "item" and int(rule["target_id"]) not in copied_items:
                    raise RuntimeError("Copied prerequisite item target still references the source course.")
                if rule["target_type"] == "module" and int(rule["target_id"]) not in copied_modules:
                    raise RuntimeError("Copied prerequisite module target still references the source course.")

    print("Learning Paths & Prerequisites v1 validated: instructor rule builder, cycle prevention, transparent locked gateway, direct-route enforcement, item completion, grade/outcome thresholds, observer semantics, and Course Copy remapping.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
