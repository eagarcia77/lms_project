from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-assignments-submissions-v2-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "assignments-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "assignments-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "assignment.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Assignment-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Assignment Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/assignment-user/{kind}", include_in_schema=False)
async def smoke_assignment_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "assignment-instructor", "name": "Assignment Instructor", "email": "assignment.instructor@example.com"},
        "student": {"id": "assignment-student", "name": "Assignment Student", "email": "assignment.student@example.com"},
        "observer": {"id": "assignment-observer", "name": "Assignment Observer", "email": "assignment.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported assignment smoke user.")
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
        expect(client.post("/admin/login", data={"email": "assignment.admin@example.com", "password": "Initial-Assignment-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Assignment-2026!", "confirm": "Updated-Assignment-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "ASSIGN-4200",
            "title": "Assignments and Submissions v2",
            "description": "Assignment workflow validation.",
            "term": "Fall 2026",
            "instructor_email": "assignment.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "assignment.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "assignment.observer@example.com", "observer", "active", now))
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (course_id, "Assignment Module", "Published assignment module.", "Submit evidence in multiple formats.", 45, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND title=?", (course_id, "Assignment Module")))[0]["id"])
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_id, "assignment", "Multimodal Evidence Assignment", "<p>Submit a written explanation, link, or attachment.</p>", "", "", "{}", 40, "2026-12-15T23:59", 1, "published", now, now))
            item_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title=?", (module_id, "Multimodal Evidence Assignment")))[0]["id"])

        expect(client.get("/__smoke/assignment-user/student"), 200, "student session")
        course_page = client.get(f"/learn/courses/{course_id}")
        expect(course_page, 200, "student course")
        require(course_page, f'/learn/assignments/{item_id}', "assignment-aware student course link")

        assignment_page = client.get(f"/learn/assignments/{item_id}")
        expect(assignment_page, 200, "student assignment")
        require(assignment_page, 'data-testid="student-assignment-v2"', "student assignment")
        require(assignment_page, 'enctype="multipart/form-data"', "assignment file form")
        require(assignment_page, "Save draft", "assignment draft action")

        draft = client.post(f"/learn/assignments/{item_id}/save", data={
            "response_text": "Draft response before final submission.",
            "response_url": "",
            "action": "draft",
        })
        expect(draft, 303, "assignment draft save")
        with db() as conn:
            submission = rows(execute(conn, "SELECT * FROM nuvedra_submissions WHERE item_id=? AND lower(student_email)=?", (item_id, "assignment.student@example.com")))[0]
            submission_id = int(submission["id"])
            if submission.get("status") != "draft":
                raise RuntimeError("Assignment draft did not remain in draft status.")
            attempts = rows(execute(conn, "SELECT id FROM nuvedra_assignment_attempts WHERE submission_id=?", (submission_id,)))
            if attempts:
                raise RuntimeError("Saving a draft incorrectly created a submitted attempt.")

        first_file = b"NUVEDRA assignment evidence version one"
        submitted = client.post(
            f"/learn/assignments/{item_id}/save",
            data={"response_text": "Final response version one.", "response_url": "https://example.edu/evidence", "action": "submit"},
            files={"attachment": ("evidence.pdf", first_file, "application/pdf")},
        )
        expect(submitted, 303, "assignment first submission")
        with db() as conn:
            submission = rows(execute(conn, "SELECT * FROM nuvedra_submissions WHERE id=?", (submission_id,)))[0]
            if submission.get("status") != "submitted":
                raise RuntimeError("Assignment was not marked submitted.")
            attempts = rows(execute(conn, "SELECT * FROM nuvedra_assignment_attempts WHERE submission_id=? ORDER BY attempt_no", (submission_id,)))
            if len(attempts) != 1 or int(attempts[0].get("attempt_no") or 0) != 1:
                raise RuntimeError("First assignment attempt was not recorded.")
            files = rows(execute(conn, "SELECT id,filename,size_bytes FROM nuvedra_assignment_files WHERE submission_id=? ORDER BY id", (submission_id,)))
            if len(files) != 1 or files[0].get("filename") != "evidence.pdf" or int(files[0].get("size_bytes") or 0) != len(first_file):
                raise RuntimeError("First assignment attachment was not stored correctly.")
            first_file_id = int(files[0]["id"])
            notices = rows(execute(conn, "SELECT id FROM nuvedra_notifications WHERE recipient_email=? AND course_id=? AND kind='assignment'", ("assignment.instructor@example.com", course_id)))
            if not notices:
                raise RuntimeError("Instructor did not receive an assignment-submission notification.")

        own_file = client.get(f"/learn/assignment-files/{first_file_id}")
        expect(own_file, 200, "student attachment download")
        if own_file.content != first_file:
            raise RuntimeError("Student attachment download did not preserve file bytes.")

        second_file = b"NUVEDRA assignment evidence version two"
        resubmitted = client.post(
            f"/learn/assignments/{item_id}/save",
            data={"response_text": "Updated final response.", "response_url": "", "action": "submit"},
            files={"attachment": ("evidence-v2.docx", second_file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        expect(resubmitted, 303, "assignment resubmission")
        with db() as conn:
            attempts = rows(execute(conn, "SELECT attempt_no FROM nuvedra_assignment_attempts WHERE submission_id=? ORDER BY attempt_no", (submission_id,)))
            if [int(row["attempt_no"]) for row in attempts] != [1, 2]:
                raise RuntimeError("Assignment resubmission history did not preserve both attempts.")
            files = rows(execute(conn, "SELECT id,filename FROM nuvedra_assignment_files WHERE submission_id=? ORDER BY id", (submission_id,)))
            if len(files) != 2:
                raise RuntimeError("Assignment resubmission did not preserve attachment history.")
            second_file_id = int(files[-1]["id"])

        assignment_page = client.get(f"/learn/assignments/{item_id}")
        expect(assignment_page, 200, "student assignment after resubmission")
        require(assignment_page, "Submission history", "assignment history")
        require(assignment_page, "evidence-v2.docx", "latest assignment attachment")

        expect(client.get("/__smoke/assignment-user/instructor"), 200, "instructor session")
        course_assignments = client.get(f"/faculty/studio/courses/{course_id}/assignments")
        expect(course_assignments, 200, "instructor assignment index")
        require(course_assignments, 'data-testid="course-assignments-v2"', "instructor assignment index")
        require(course_assignments, "Multimodal Evidence Assignment", "instructor assignment index")
        inbox = client.get(f"/faculty/studio/assignments/{item_id}")
        expect(inbox, 200, "assignment submission inbox")
        require(inbox, 'data-testid="assignment-submission-inbox-v2"', "assignment submission inbox")
        require(inbox, "assignment.student@example.com", "assignment student submission")
        require(inbox, "evidence-v2.docx", "assignment latest attachment")
        instructor_file = client.get(f"/learn/assignment-files/{second_file_id}")
        expect(instructor_file, 200, "instructor attachment download")
        if instructor_file.content != second_file:
            raise RuntimeError("Instructor attachment download did not preserve file bytes.")

        gradebook = client.get(f"/faculty/studio/courses/{course_id}/gradebook")
        expect(gradebook, 200, "assignment Gradebook integration")
        require(gradebook, "assignment.student@example.com", "assignment Gradebook student")
        require(gradebook, "Multimodal Evidence Assignment", "assignment Gradebook item")

        expect(client.get("/__smoke/assignment-user/observer"), 200, "observer session")
        observer_page = client.get(f"/learn/assignments/{item_id}")
        expect(observer_page, 200, "observer assignment view")
        require(observer_page, "Observers can view assignment instructions but cannot submit work.", "observer assignment read-only notice")
        observer_submit = client.post(f"/learn/assignments/{item_id}/save", data={"response_text": "Observers cannot submit.", "response_url": "", "action": "submit"})
        expect(observer_submit, 403, "observer assignment submit protection")
        observer_file = client.get(f"/learn/assignment-files/{second_file_id}")
        expect(observer_file, 403, "observer attachment privacy")
        instructor_admin = client.get(f"/faculty/studio/assignments/{item_id}")
        expect(instructor_admin, 403, "observer assignment inbox protection")

    print("Assignments & Submissions v2 validated: draft saving, multimodal submission, protected attachments, resubmission history, instructor notifications/inbox, Gradebook linkage, and observer privacy.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
