from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-certificates-completion-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "completion-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "completion-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "completion.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Completion-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Completion Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/completion-user/{kind}", include_in_schema=False)
async def smoke_completion_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "completion-instructor", "name": "Completion Instructor", "email": "completion.instructor@example.com"},
        "student1": {"id": "completion-student-1", "name": "Eligible Student", "email": "eligible.student@example.com"},
        "student2": {"id": "completion-student-2", "name": "Pending Student", "email": "pending.student@example.com"},
        "observer": {"id": "completion-observer", "name": "Completion Observer", "email": "completion.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported completion smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "completion.admin@example.com", "password": "Initial-Completion-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Completion-2026!", "confirm": "Updated-Completion-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "COMP-6200",
            "title": "Course Completion Design",
            "description": "Certificates and completion functional validation.",
            "term": "Fall 2026",
            "instructor_email": "completion.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (
                ("eligible.student@example.com", "student"),
                ("pending.student@example.com", "student"),
                ("completion.observer@example.com", "observer"),
            ):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                        (course_id, email, role, "active", now))
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (course_id, "Completion Module", "Finish both activities.", "Demonstrate course completion.", 60, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)))[0]["id"])
            execute(conn, """INSERT INTO nexus_content_items
                (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (module_id, "page", "Completion Reading", "<p>Read this page.</p>", "", "", "{}", None, None, 1, "published", now, now))
            page_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title='Completion Reading'", (module_id,)))[0]["id"])
            execute(conn, """INSERT INTO nexus_content_items
                (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (module_id, "assignment", "Completion Assignment", "<p>Submit final evidence.</p>", "", "", "{}", 100, None, 2, "published", now, now))
            assignment_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title='Completion Assignment'", (module_id,)))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_content_progress (item_id,student_email,status,completed_at,updated_at) VALUES (?,?,?,?,?)",
                    (page_id, "eligible.student@example.com", "completed", now, now))
            execute(conn, "INSERT INTO nuvedra_submissions (item_id,student_email,response_text,response_url,status,submitted_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (assignment_id, "eligible.student@example.com", "Final evidence", None, "submitted", now, now))
            submission_id = int(rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (assignment_id, "eligible.student@example.com")))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_grades (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (submission_id, 85, "Completion criteria met.", "graded", "completion.instructor@example.com", now, now))
            execute(conn, "INSERT INTO nuvedra_content_progress (item_id,student_email,status,completed_at,updated_at) VALUES (?,?,?,?,?)",
                    (page_id, "pending.student@example.com", "completed", now, now))

        expect(client.get("/__smoke/completion-user/instructor"), 200, "instructor session")
        workspace = client.get(f"/faculty/studio/courses/{course_id}/completion")
        expect(workspace, 200, "completion workspace")
        require(workspace, 'data-testid="certificates-completion-v1"', "completion workspace")
        require(workspace, "NUVEDRA does not award certificates automatically in v1", "human award notice")

        expect(client.post(f"/faculty/studio/courses/{course_id}/completion/rules", data={
            "min_progress_percent": "100",
            "min_grade_percent": "80",
            "certificate_title": "NUVEDRA Course Completion Certificate",
            "certificate_enabled": "1",
        }), 303, "save completion rules")
        expect(client.post(f"/faculty/studio/courses/{course_id}/completion/required/{assignment_id}/toggle"), 303, "require assignment")

        review = client.get(f"/faculty/studio/courses/{course_id}/completion")
        expect(review, 200, "completion review")
        require(review, "eligible.student@example.com", "eligible learner row")
        require(review, "Award certificate", "eligible award action")
        require(review, "pending.student@example.com", "pending learner row")

        blocked = client.post(f"/faculty/studio/courses/{course_id}/completion/pending.student@example.com/award")
        expect(blocked, 409, "ineligible award protection")
        awarded = client.post(f"/faculty/studio/courses/{course_id}/completion/eligible.student@example.com/award")
        expect(awarded, 303, "eligible certificate award")

        with db() as conn:
            certificates = rows(execute(conn, "SELECT * FROM nuvedra_course_completions WHERE course_id=? AND student_email=?", (course_id, "eligible.student@example.com")))
            if len(certificates) != 1 or str(certificates[0].get("status")) != "active":
                raise RuntimeError(f"Certificate award was not stored correctly: {certificates}")
            cert = certificates[0]
            code = str(cert["verification_code"])
            if float(cert.get("progress_percent") or 0) != 100.0 or round(float(cert.get("grade_percent") or 0), 1) != 85.0:
                raise RuntimeError(f"Certificate snapshot did not preserve progress/grade: {cert}")
            notifications = rows(execute(conn, "SELECT * FROM nuvedra_notifications WHERE recipient_email=? AND kind='completion'", ("eligible.student@example.com",)))
            if not notifications:
                raise RuntimeError("Certificate award did not create a completion notification.")

        verification = client.get(f"/verify/certificate/{code}")
        expect(verification, 200, "public certificate verification")
        require(verification, "Valid certificate", "verification status")
        require(verification, "e***@example.com", "masked learner identity")
        if "eligible.student@example.com" in verification.text:
            raise RuntimeError("Public verification leaked the full learner email.")

        expect(client.get("/__smoke/completion-user/student1"), 200, "eligible student session")
        student_home = client.get("/learn/completions")
        expect(student_home, 200, "student completion dashboard")
        require(student_home, "View certificate", "student certificate link")
        own_certificate = client.get(f"/learn/certificates/{code}")
        expect(own_certificate, 200, "student certificate")
        require(own_certificate, "eligible.student@example.com", "student certificate owner")
        require(own_certificate, "85.0%", "student certificate grade snapshot")

        expect(client.get("/__smoke/completion-user/student2"), 200, "pending student session")
        pending_home = client.get("/learn/completions")
        expect(pending_home, 200, "pending student completion dashboard")
        require(pending_home, "Completion criteria pending", "pending criteria state")
        expect(client.get(f"/learn/certificates/{code}"), 403, "other student certificate privacy")

        expect(client.get("/__smoke/completion-user/observer"), 200, "observer session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/completion"), 403, "observer instructor completion protection")
        expect(client.get("/learn/completions"), 200, "observer completion route shell")
        # Observers have no student courses and therefore receive no private learner completion details.
        observer_home = client.get("/learn/completions")
        if "eligible.student@example.com" in observer_home.text:
            raise RuntimeError("Observer completion page leaked a student's completion data.")

        expect(client.get("/__smoke/completion-user/instructor"), 200, "instructor return session")
        expect(client.post(f"/faculty/studio/courses/{course_id}/completion/eligible.student@example.com/revoke"), 303, "certificate revocation")
        revoked = client.get(f"/verify/certificate/{code}")
        expect(revoked, 200, "revoked public verification")
        require(revoked, "Revoked certificate", "revoked verification state")
        expect(client.get("/__smoke/completion-user/student1"), 200, "student return session")
        expect(client.get(f"/learn/certificates/{code}"), 410, "revoked student certificate protection")

    print("Certificates & Course Completion v1 validated: configurable criteria, required activities, eligibility enforcement, instructor-reviewed awards, certificate snapshots, masked public verification, student privacy, notifications, and revocation.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
