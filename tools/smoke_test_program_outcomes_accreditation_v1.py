from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-program-outcomes-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "program-outcomes-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "program-outcomes-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "program.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Program-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Program Assessment Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/program-user/{kind}", include_in_schema=False)
async def smoke_program_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "program-instructor", "name": "Program Coordinator", "email": "program.admin@example.com"},
        "reviewer": {"id": "program-reviewer", "name": "Assessment Reviewer", "email": "program.reviewer@example.com"},
        "student": {"id": "program-student", "name": "Program Student", "email": "program.student1@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported program-outcomes smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}: {response.text[:1800]}")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "program.admin@example.com", "password": "Initial-Program-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Program-2026!", "confirm": "Updated-Program-2026!"}), 303, "admin password update")

        created1 = client.post("/admin/authoring/courses", data={
            "course_code": "PROG-6100", "title": "Program Evidence I", "description": "Introduced program evidence.",
            "term": "Fall 2026", "instructor_email": "program.admin@example.com", "template": "blank",
        })
        expect(created1, 303, "first course creation")
        course1 = int(created1.headers["location"].rsplit("/", 1)[-1])
        created2 = client.post("/admin/authoring/courses", data={
            "course_code": "PROG-7100", "title": "Program Evidence II", "description": "Mastery program evidence.",
            "term": "Spring 2027", "instructor_email": "program.admin@example.com", "template": "blank",
        })
        expect(created2, 303, "second course creation")
        course2 = int(created2.headers["location"].rsplit("/", 1)[-1])

        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id IN (?,?)", (now, course1, course2))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course1, "program.student1@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course2, "program.student2@example.com", "student", "active", now))

            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course1, "Evidence I", "Program evidence module.", "Course outcomes.", 30, 1, "published", now, now))
            module1 = int(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course1,)).fetchone()[0])
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course2, "Evidence II", "Program mastery module.", "Course outcomes.", 30, 1, "published", now, now))
            module2 = int(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course2,)).fetchone()[0])

            def add_item(module_id: int, title: str, position: int) -> int:
                cursor = execute(conn, """INSERT INTO nexus_content_items
                    (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                    VALUES (?,'assignment',?,?,'','','{}',100,NULL,?,'published',?,?)""", (module_id, title, f"<p>{title}</p>", position, now, now))
                return int(cursor.lastrowid)

            item1 = add_item(module1, "Research Evidence", 1)
            item_no_grade = add_item(module1, "Ethics Reflection", 2)
            item2 = add_item(module2, "Capstone Evidence", 1)

            def add_course_outcome(course_id: int, code: str, title: str, item_id: int) -> int:
                outcome_id = int(execute(conn, """INSERT INTO nuvedra_outcomes
                    (course_id,code,title,description,status,created_by,created_at,updated_at)
                    VALUES (?,?,?,?, 'active',?,?,?)""", (course_id, code, title, f"{title} description.", "program.admin@example.com", now, now)).lastrowid)
                execute(conn, "INSERT INTO nuvedra_outcome_links (outcome_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (outcome_id, item_id, "program.admin@example.com", now))
                return outcome_id

            co1 = add_course_outcome(course1, "CLO-1", "Analyze research evidence", item1)
            co3 = add_course_outcome(course1, "CLO-3", "Apply ethical leadership", item_no_grade)
            co2 = add_course_outcome(course2, "CLO-2", "Synthesize capstone evidence", item2)

            def add_grade(item_id: int, email: str, points: float) -> None:
                submission_id = int(execute(conn, """INSERT INTO nuvedra_submissions
                    (item_id,student_email,response_text,response_url,status,submitted_at,updated_at)
                    VALUES (?,?,?,'','submitted',?,?)""", (item_id, email, "Program evidence submission.", now, now)).lastrowid)
                execute(conn, """INSERT INTO nuvedra_grades
                    (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at)
                    VALUES (?,?,?,'graded',?,?,?)""", (submission_id, points, "Program assessment evidence.", "program.admin@example.com", now, now))

            add_grade(item1, "program.student1@example.com", 85)
            add_grade(item2, "program.student2@example.com", 95)

        expect(client.get("/admin/logout"), 303, "admin logout")
        expect(client.get("/__smoke/program-user/instructor"), 200, "instructor session")

        index = client.get("/faculty/programs")
        expect(index, 200, "program index")
        require(index, 'data-testid="program-outcomes-accreditation-index"', "program index marker")
        created_program = client.post("/faculty/programs", data={
            "program_code": "EDD-DIST", "title": "Doctoral Program in Distance Education", "description": "Program-level assessment workspace.",
        })
        expect(created_program, 303, "program creation")
        program_id = int(created_program.headers["location"].rsplit("/", 1)[-1])

        expect(client.post(f"/faculty/programs/{program_id}/courses", data={"course_id": str(course1)}), 303, "add first program course")
        expect(client.post(f"/faculty/programs/{program_id}/courses", data={"course_id": str(course2)}), 303, "add second program course")
        expect(client.post(f"/faculty/programs/{program_id}/outcomes", data={"code": "PLO-1", "title": "Integrate research evidence", "description": "Integrate research and applied evidence."}), 303, "create first program outcome")
        expect(client.post(f"/faculty/programs/{program_id}/outcomes", data={"code": "PLO-2", "title": "Demonstrate ethical leadership", "description": "Apply ethical leadership practices."}), 303, "create second program outcome")

        with db() as conn:
            po1 = int(rows(execute(conn, "SELECT id FROM nuvedra_program_outcomes WHERE program_id=? AND code='PLO-1'", (program_id,)))[0]["id"])
            po2 = int(rows(execute(conn, "SELECT id FROM nuvedra_program_outcomes WHERE program_id=? AND code='PLO-2'", (program_id,)))[0]["id"])

        expect(client.post(f"/faculty/programs/{program_id}/alignments", data={"program_outcome_id": str(po1), "course_outcome_id": str(co1), "curriculum_level": "introduced", "weight": "1"}), 303, "map introduced course outcome")
        expect(client.post(f"/faculty/programs/{program_id}/alignments", data={"program_outcome_id": str(po1), "course_outcome_id": str(co2), "curriculum_level": "mastered", "weight": "1"}), 303, "map mastered course outcome")
        expect(client.post(f"/faculty/programs/{program_id}/alignments", data={"program_outcome_id": str(po2), "course_outcome_id": str(co3), "curriculum_level": "reinforced", "weight": "1"}), 303, "map no-evidence course outcome")

        dashboard = client.get(f"/faculty/programs/{program_id}")
        expect(dashboard, 200, "program dashboard")
        require(dashboard, 'data-testid="program-outcomes-accreditation-v1"', "program dashboard marker")
        require(dashboard, "90.0%", "weighted program attainment")
        require(dashboard, "Meets benchmark", "benchmark classification")
        require(dashboard, "No evidence", "missing evidence classification")
        require(dashboard, "Curriculum matrix", "curriculum matrix")
        require(dashboard, "PROG-6100", "first course matrix header")
        require(dashboard, "PROG-7100", "second course matrix header")

        expect(client.post(f"/faculty/programs/{program_id}/settings", data={"benchmark_threshold": "101"}), 400, "invalid benchmark rejection")
        expect(client.post(f"/faculty/programs/{program_id}/settings", data={"benchmark_threshold": "80"}), 303, "valid benchmark")

        matrix_csv = client.get(f"/faculty/programs/{program_id}/matrix.csv")
        expect(matrix_csv, 200, "curriculum matrix csv")
        require(matrix_csv, "PLO-1", "matrix csv program outcome")
        require(matrix_csv, "PROG-6100", "matrix csv first course")
        require(matrix_csv, "PROG-7100", "matrix csv second course")

        evidence_csv = client.get(f"/faculty/programs/{program_id}/evidence.csv")
        expect(evidence_csv, 200, "program evidence csv")
        require(evidence_csv, "CLO-1", "evidence csv course outcome")
        require(evidence_csv, "85.0", "evidence csv first attainment")
        require(evidence_csv, "95.0", "evidence csv second attainment")
        if "program.student1@example.com" in evidence_csv.text or "program.student2@example.com" in evidence_csv.text:
            raise RuntimeError("Program evidence CSV leaked student email addresses.")

        expect(client.post(f"/faculty/programs/{program_id}/members", data={"user_email": "program.reviewer@example.com", "program_role": "reviewer"}), 303, "add program reviewer")
        snapshot = client.post(f"/faculty/programs/{program_id}/snapshots", data={"label": "Fall 2026 Accreditation Evidence"})
        expect(snapshot, 303, "capture program snapshot")
        snapshot_url = snapshot.headers["location"]
        snapshot_page = client.get(snapshot_url)
        expect(snapshot_page, 200, "program snapshot page")
        require(snapshot_page, 'data-testid="program-accreditation-snapshot-v1"', "snapshot marker")
        require(snapshot_page, "90.0%", "snapshot preserves attainment")
        if "program.student1@example.com" in snapshot_page.text or "program.student2@example.com" in snapshot_page.text:
            raise RuntimeError("Program snapshot leaked student email addresses.")

        studio_js = Path("app/static/course-studio.js").read_text(encoding="utf-8")
        if "NUVEDRA_PROGRAM_OUTCOMES_ACCREDITATION_V1" not in studio_js or "Program Alignment" not in studio_js:
            raise RuntimeError("Course Studio Program Alignment navigation was not installed.")

        expect(client.get("/__smoke/program-user/reviewer"), 200, "reviewer session")
        expect(client.get(f"/faculty/programs/{program_id}"), 200, "reviewer read-only dashboard")
        expect(client.get(f"/faculty/programs/{program_id}/evidence.csv"), 200, "reviewer evidence export")
        expect(client.post(f"/faculty/programs/{program_id}/settings", data={"benchmark_threshold": "70"}), 403, "reviewer mutation protection")

        expect(client.get("/__smoke/program-user/student"), 200, "student session")
        expect(client.get(f"/faculty/programs/{program_id}"), 403, "student program workspace protection")
        expect(client.get(f"/faculty/programs/{program_id}/matrix.csv"), 403, "student program export protection")

    print("Program Outcomes & Accreditation v1 validated: program workspace, curriculum I/R/M mapping, weighted aggregate attainment, no-evidence handling, benchmark control, privacy-preserving CSV/snapshots, reviewer permissions, student protection, and Course Studio navigation.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
