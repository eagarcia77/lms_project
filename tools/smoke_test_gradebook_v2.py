from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-gradebook-v2-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "gradebook-v2-session-secret-at-least-thirty-two"
os.environ["NEXUS_SESSION_SECRET"] = "gradebook-v2-admin-secret-at-least-thirty-two"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "gradebook.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Gradebook-V2-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Gradebook V2 Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/gradebook-v2-user/{kind}", include_in_schema=False)
async def smoke_gradebook_v2_user(kind: str, request: Request):
    if kind == "student":
        request.session["user"] = {
            "id": "gradebook-v2-student",
            "name": "Gradebook V2 Student",
            "email": "gradebook.student@example.com",
        }
    elif kind == "admin":
        request.session.pop("user", None)
    else:
        raise RuntimeError("Unsupported Gradebook v2 smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f"{label}: expected {status}, received {response.status_code}: {response.text[:1200]}"
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={
            "email": "gradebook.admin@example.com",
            "password": "Initial-Gradebook-V2-2026!",
        }), 303, "administrator login")
        expect(client.post("/admin/password", data={
            "password": "Updated-Gradebook-V2-2026!",
            "confirm": "Updated-Gradebook-V2-2026!",
        }), 303, "administrator password update")

        created = client.post("/admin/authoring/courses", data={
            "course_code": "GRADE-2002",
            "title": "Gradebook V2 Course",
            "description": "Manual essay review validation.",
            "term": "Fall 2026",
            "instructor_email": "",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])

        expect(client.post(f"/faculty/studio/courses/{course_id}/modules", data={
            "title": "Review Module",
            "description": "Manual review module.",
            "learning_outcomes": "Complete and review a mixed assessment.",
            "estimated_minutes": "30",
        }), 303, "module creation")
        with db() as conn:
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,)))[0]["id"])

        expect(client.post(f"/faculty/studio/modules/{module_id}/update", data={
            "title": "Review Module",
            "description": "Manual review module.",
            "learning_outcomes": "Complete and review a mixed assessment.",
            "estimated_minutes": "30",
            "position": "1",
            "status": "published",
        }), 303, "module publishing")

        expect(client.post(f"/faculty/studio/modules/{module_id}/items", data={
            "item_type": "assessment",
            "title": "Mixed Assessment",
            "body_html": "<p>Complete the objective and essay questions.</p>",
            "external_url": "",
            "embed_url": "",
            "points": "3",
            "due_at": "",
            "accessible_alternative": "All prompts are text-based.",
            "assessment_response_type": "structured",
            "attempts": "1",
            "time_limit": "0",
            "rubric": "Objective item plus short essay.",
        }), 303, "assessment creation")
        with db() as conn:
            item_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? ORDER BY id DESC LIMIT 1", (module_id,)))[0]["id"])

        expect(client.post(f"/faculty/studio/items/{item_id}/edit", data={
            "item_type": "assessment",
            "title": "Mixed Assessment",
            "body_html": "<p>Complete the objective and essay questions.</p>",
            "external_url": "",
            "embed_url": "",
            "points": "3",
            "due_at": "",
            "position": "1",
            "status": "published",
            "accessible_alternative": "All prompts are text-based.",
            "assessment_response_type": "structured",
            "attempts": "1",
            "time_limit": "0",
            "rubric": "Objective item plus short essay.",
        }), 303, "assessment publishing")

        expect(client.post(f"/faculty/studio/items/{item_id}/assessment/questions", data={
            "question_type": "multiple_choice",
            "prompt": "Which environment is immersive?",
            "choices": "Virtual reality\nPlain text only",
            "correct_answer": "Virtual reality",
            "points": "1",
            "position": "1",
            "feedback_correct": "Correct objective response.",
            "feedback_incorrect": "Review immersive environments.",
        }), 303, "objective question")
        expect(client.post(f"/faculty/studio/items/{item_id}/assessment/questions", data={
            "question_type": "essay",
            "prompt": "Explain one educational benefit of immersive learning.",
            "choices": "",
            "correct_answer": "",
            "points": "2",
            "position": "2",
            "feedback_correct": "",
            "feedback_incorrect": "",
        }), 303, "essay question")

        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (utcnow(), course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "gradebook.student@example.com", "student", "active", utcnow()))
            questions = rows(execute(conn, "SELECT id,question_type FROM nuvedra_assessment_questions WHERE item_id=? ORDER BY position,id", (item_id,)))
            objective_id = int(next(row["id"] for row in questions if row["question_type"] == "multiple_choice"))
            essay_question_id = int(next(row["id"] for row in questions if row["question_type"] == "essay"))

        expect(client.get("/__smoke/gradebook-v2-user/student"), 200, "student session")
        expect(client.post(f"/learn/assessments/{item_id}/start"), 303, "attempt start")
        with db() as conn:
            attempt_id = int(rows(execute(conn, "SELECT id FROM nuvedra_assessment_attempts WHERE item_id=? AND lower(student_email)='gradebook.student@example.com'", (item_id,)))[0]["id"])

        expect(client.post(f"/learn/assessments/{item_id}/attempts/{attempt_id}/submit", data={
            f"q_{objective_id}": "Virtual reality",
            f"q_{essay_question_id}": "It lets students practice concepts in realistic interactive environments.",
        }), 303, "mixed assessment submission")

        with db() as conn:
            attempt = rows(execute(conn, "SELECT * FROM nuvedra_assessment_attempts WHERE id=?", (attempt_id,)))[0]
            if float(attempt.get("score_auto") or 0) != 1 or attempt.get("score_total") is not None or int(attempt.get("has_manual_items") or 0) != 1:
                raise RuntimeError("Mixed assessment did not remain pending manual essay review.")
            essay_answer = rows(execute(conn, "SELECT id FROM nuvedra_assessment_answers WHERE attempt_id=? AND question_id=?", (attempt_id, essay_question_id)))
            if not essay_answer:
                raise RuntimeError("Essay answer was not stored.")
            essay_answer_id = int(essay_answer[0]["id"])

        expect(client.get("/__smoke/gradebook-v2-user/admin"), 200, "administrator-instructor session")
        attempts_page = client.get(f"/faculty/studio/courses/{course_id}/attempts")
        expect(attempts_page, 200, "structured attempts review list")
        if 'data-testid="structured-attempts-review"' not in attempts_page.text or "Pending manual review" not in attempts_page.text:
            raise RuntimeError("Gradebook v2 did not list the pending structured attempt.")

        review = client.get(f"/faculty/studio/attempts/{attempt_id}/review")
        expect(review, 200, "attempt review")
        if 'data-testid="attempt-review"' not in review.text or "Explain one educational benefit" not in review.text:
            raise RuntimeError("Attempt review did not show the essay response.")

        expect(client.post(f"/faculty/studio/attempts/{attempt_id}/answers/{essay_answer_id}/review", data={
            "points_awarded": "2",
            "feedback": "Clear explanation with a practical educational benefit.",
        }), 303, "manual essay grading")

        with db() as conn:
            attempt = rows(execute(conn, "SELECT * FROM nuvedra_assessment_attempts WHERE id=?", (attempt_id,)))[0]
            if float(attempt.get("score_total") or 0) != 3 or int(attempt.get("has_manual_items") or 0) != 0:
                raise RuntimeError(f"Manual review expected final score 3, got {attempt.get('score_total')!r}.")
            grade = rows(execute(conn, """SELECT g.points_awarded,g.feedback FROM nuvedra_grades g JOIN nuvedra_submissions s ON s.id=g.submission_id WHERE s.item_id=? AND lower(s.student_email)='gradebook.student@example.com'""", (item_id,)))
            if not grade or float(grade[0].get("points_awarded") or 0) != 3:
                raise RuntimeError("The manually completed assessment score was not synchronized to Gradebook.")
            feedback = rows(execute(conn, "SELECT feedback FROM nuvedra_assessment_answer_reviews WHERE answer_id=?", (essay_answer_id,)))
            if not feedback or "practical educational benefit" not in str(feedback[0].get("feedback") or ""):
                raise RuntimeError("Per-question instructor feedback was not saved.")

        expect(client.get("/__smoke/gradebook-v2-user/student"), 200, "student returns")
        feedback_page = client.get(f"/learn/assessments/{item_id}/attempts/{attempt_id}/feedback")
        expect(feedback_page, 200, "student attempt feedback")
        if 'data-testid="student-attempt-feedback"' not in feedback_page.text or "Clear explanation" not in feedback_page.text or "2 / 2" not in feedback_page.text:
            raise RuntimeError("Student feedback view did not show the manual essay score and feedback.")

        grades = client.get(f"/learn/courses/{course_id}/grades")
        expect(grades, 200, "student Gradebook after manual review")
        if "3 / 3" not in grades.text:
            raise RuntimeError("Student My Grades did not show the final mixed-assessment score.")

    print("Gradebook v2 validated: pending essay review, manual per-question scoring, feedback, final score recomputation, Gradebook synchronization, and student feedback access.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
