from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-rubrics-outcomes-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "rubrics-outcomes-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "rubrics-outcomes-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "rubrics.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Rubrics-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Rubrics Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/rubrics-user/{kind}", include_in_schema=False)
async def smoke_rubrics_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "rubric-instructor", "name": "Rubric Instructor", "email": "rubric.instructor@example.com"},
        "student": {"id": "rubric-student", "name": "Rubric Student", "email": "rubric.student@example.com"},
        "observer": {"id": "rubric-observer", "name": "Rubric Observer", "email": "rubric.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported rubric smoke user.")
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
        expect(client.post("/admin/login", data={"email": "rubrics.admin@example.com", "password": "Initial-Rubrics-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Rubrics-2026!", "confirm": "Updated-Rubrics-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "RUB-5100",
            "title": "Rubrics and Outcomes v1",
            "description": "Rubric grading and learning-outcome validation.",
            "term": "Fall 2026",
            "instructor_email": "rubric.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "rubric.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "rubric.observer@example.com", "observer", "active", now))
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (course_id, "Rubric Module", "Published module.", "Demonstrate measurable performance.", 45, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND title=?", (course_id, "Rubric Module")))[0]["id"])
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_id, "assignment", "Evidence-Based Project", "<p>Submit an evidence-based project.</p>", "", "", "{}", 100, "2026-12-15T23:59", 1, "published", now, now))
            item_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title=?", (module_id, "Evidence-Based Project")))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_submissions (item_id,student_email,response_text,response_url,status,submitted_at,updated_at) VALUES (?,?,?,?,?,?,?)", (item_id, "rubric.student@example.com", "Student project response with evidence and analysis.", None, "submitted", now, now))
            submission_id = int(rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=? AND student_email=?", (item_id, "rubric.student@example.com")))[0]["id"])

        expect(client.get("/__smoke/rubrics-user/instructor"), 200, "instructor session")
        rubric_index = client.get(f"/faculty/studio/courses/{course_id}/rubrics")
        expect(rubric_index, 200, "rubric index")
        require(rubric_index, 'data-testid="rubrics-outcomes-v1"', "rubric index")

        created_rubric = client.post(f"/faculty/studio/courses/{course_id}/rubrics", data={"title": "Project Performance Rubric", "description": "Two-criterion reusable rubric."})
        expect(created_rubric, 303, "rubric creation")
        rubric_id = int(created_rubric.headers["location"].rsplit("/", 1)[-1])
        expect(client.post(f"/faculty/studio/rubrics/{rubric_id}/criteria", data={"title": "Content mastery", "description": "Accuracy and depth."}), 303, "first criterion")
        expect(client.post(f"/faculty/studio/rubrics/{rubric_id}/criteria", data={"title": "Critical thinking", "description": "Analysis and evidence."}), 303, "second criterion")

        with db() as conn:
            criteria = rows(execute(conn, "SELECT id,title FROM nuvedra_rubric_criteria WHERE rubric_id=? ORDER BY position,id", (rubric_id,)))
            if len(criteria) != 2:
                raise RuntimeError("Rubric criteria were not stored.")
            content_id = int(criteria[0]["id"])
            thinking_id = int(criteria[1]["id"])

        for criterion_id, prefix in ((content_id, "Content"), (thinking_id, "Thinking")):
            expect(client.post(f"/faculty/studio/rubrics/{rubric_id}/criteria/{criterion_id}/levels", data={"label": f"{prefix} Exemplary", "description": "Exemplary performance.", "points": "50"}), 303, f"{prefix} exemplary level")
            points = "40" if criterion_id == content_id else "45"
            expect(client.post(f"/faculty/studio/rubrics/{rubric_id}/criteria/{criterion_id}/levels", data={"label": f"{prefix} Proficient", "description": "Proficient performance.", "points": points}), 303, f"{prefix} proficient level")

        expect(client.post(f"/faculty/studio/rubrics/{rubric_id}/attach", data={"item_id": str(item_id)}), 303, "rubric attachment")
        expect(client.post(f"/faculty/studio/courses/{course_id}/outcomes", data={"code": "CLO-1", "title": "Analyze evidence", "description": "Analyze evidence to support a defensible conclusion."}), 303, "outcome creation")
        with db() as conn:
            outcome_id = int(rows(execute(conn, "SELECT id FROM nuvedra_outcomes WHERE course_id=? AND code='CLO-1'", (course_id,)))[0]["id"])
        expect(client.post(f"/faculty/studio/outcomes/{outcome_id}/attach", data={"item_id": str(item_id)}), 303, "outcome alignment")

        builder = client.get(f"/faculty/studio/rubrics/{rubric_id}")
        expect(builder, 200, "rubric builder")
        require(builder, 'data-testid="rubric-builder-v1"', "rubric builder")
        require(builder, "100 max rubric points", "rubric maximum")

        expect(client.get("/__smoke/rubrics-user/student"), 200, "student session")
        assignment = client.get(f"/learn/assignments/{item_id}")
        expect(assignment, 200, "student assignment")
        require(assignment, f'/learn/items/{item_id}/rubric', "assignment rubric link")
        student_rubric = client.get(f"/learn/items/{item_id}/rubric")
        expect(student_rubric, 200, "student rubric")
        require(student_rubric, 'data-testid="student-rubric-v1"', "student rubric")
        require(student_rubric, "Content mastery", "student rubric criteria")
        require(student_rubric, "CLO-1", "student aligned outcome")

        expect(client.get("/__smoke/rubrics-user/instructor"), 200, "instructor session for grading")
        grading = client.get(f"/faculty/studio/submissions/{submission_id}/rubric")
        expect(grading, 200, "rubric grading page")
        require(grading, 'data-testid="rubric-grading-v1"', "rubric grading page")
        with db() as conn:
            content_level = int(rows(execute(conn, "SELECT id FROM nuvedra_rubric_levels WHERE criterion_id=? AND label='Content Proficient'", (content_id,)))[0]["id"])
            thinking_level = int(rows(execute(conn, "SELECT id FROM nuvedra_rubric_levels WHERE criterion_id=? AND label='Thinking Proficient'", (thinking_id,)))[0]["id"])
        saved = client.post(f"/faculty/studio/submissions/{submission_id}/rubric", data={
            f"level_{content_id}": str(content_level),
            f"feedback_{content_id}": "Strong content with room for added depth.",
            f"level_{thinking_id}": str(thinking_level),
            f"feedback_{thinking_id}": "Good analysis supported by evidence.",
            "overall_feedback": "Good project. Continue strengthening synthesis.",
        })
        expect(saved, 303, "rubric grade save")
        with db() as conn:
            evaluation = rows(execute(conn, "SELECT raw_score,possible_raw_score,grade_points FROM nuvedra_rubric_evaluations WHERE submission_id=?", (submission_id,)))
            if len(evaluation) != 1 or float(evaluation[0].get("raw_score") or 0) != 85 or float(evaluation[0].get("possible_raw_score") or 0) != 100 or float(evaluation[0].get("grade_points") or 0) != 85:
                raise RuntimeError(f"Unexpected rubric score conversion: {evaluation}")
            grade = rows(execute(conn, "SELECT points_awarded,feedback FROM nuvedra_grades WHERE submission_id=?", (submission_id,)))
            if len(grade) != 1 or float(grade[0].get("points_awarded") or 0) != 85:
                raise RuntimeError("Rubric grading did not synchronize to Gradebook.")

        gradebook = client.get(f"/faculty/studio/courses/{course_id}/gradebook")
        expect(gradebook, 200, "gradebook after rubric grade")
        require(gradebook, "Grade with rubric", "gradebook rubric link")
        require(gradebook, 'value="85.0"', "gradebook synchronized score")

        outcomes = client.get(f"/faculty/studio/courses/{course_id}/outcomes")
        expect(outcomes, 200, "outcome attainment")
        require(outcomes, 'data-testid="course-outcomes-v1"', "outcome attainment")
        require(outcomes, "85.0% average attainment", "outcome attainment percentage")

        expect(client.get("/__smoke/rubrics-user/student"), 200, "student session for feedback")
        feedback = client.get(f"/learn/submissions/{submission_id}/rubric")
        expect(feedback, 200, "student rubric feedback")
        require(feedback, 'data-testid="student-rubric-feedback-v1"', "student rubric feedback")
        require(feedback, "85 course pts", "student course score")
        require(feedback, "Good project. Continue strengthening synthesis.", "student overall feedback")

        expect(client.get("/__smoke/rubrics-user/observer"), 200, "observer session")
        expect(client.get(f"/faculty/studio/submissions/{submission_id}/rubric"), 403, "observer instructor rubric protection")
        expect(client.get(f"/learn/submissions/{submission_id}/rubric"), 403, "observer student feedback protection")

    print("Rubrics & Outcomes v1 validated: rubric building, performance levels, activity alignment, student transparency, rubric grading, Gradebook synchronization, outcome attainment, feedback privacy, and role protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
