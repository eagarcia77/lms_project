from __future__ import annotations

import json
import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-assessments-v2-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "assessment-v2-session-secret-at-least-thirty-two"
os.environ["NEXUS_SESSION_SECRET"] = "assessment-v2-admin-secret-at-least-thirty-two"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "assessment.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Assessment-V2-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Assessment Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/assessment-user/{kind}", include_in_schema=False)
async def smoke_assessment_user(kind: str, request: Request):
    if kind == "student":
        request.session["user"] = {
            "id": "student-v2",
            "name": "Assessment Student",
            "email": "student.v2@example.com",
        }
    elif kind == "admin":
        request.session.pop("user", None)
    else:
        raise RuntimeError("Unsupported smoke-test user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f"{label}: expected {status}, received {response.status_code}: {response.text[:1200]}"
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(
            client.post(
                "/admin/login",
                data={
                    "email": "assessment.admin@example.com",
                    "password": "Initial-Assessment-V2-2026!",
                },
            ),
            303,
            "administrator login",
        )
        expect(
            client.post(
                "/admin/password",
                data={
                    "password": "Updated-Assessment-V2-2026!",
                    "confirm": "Updated-Assessment-V2-2026!",
                },
            ),
            303,
            "administrator password update",
        )

        created = client.post(
            "/admin/authoring/courses",
            data={
                "course_code": "ASSESS-2001",
                "title": "Assessments v2 Course",
                "description": "Validates structured assessment authoring.",
                "term": "Fall 2026",
                "instructor_email": "",
                "template": "blank",
            },
        )
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])

        expect(
            client.post(
                f"/faculty/studio/courses/{course_id}/modules",
                data={
                    "title": "Assessment Module",
                    "description": "Structured assessment module.",
                    "learning_outcomes": "Complete structured assessments.",
                    "estimated_minutes": "45",
                },
            ),
            303,
            "module creation",
        )
        with db() as conn:
            module_id = int(
                rows(
                    execute(
                        conn,
                        "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1",
                        (course_id,),
                    )
                )[0]["id"]
            )

        expect(
            client.post(
                f"/faculty/studio/modules/{module_id}/update",
                data={
                    "title": "Assessment Module",
                    "description": "Structured assessment module.",
                    "learning_outcomes": "Complete structured assessments.",
                    "estimated_minutes": "45",
                    "position": "1",
                    "status": "published",
                },
            ),
            303,
            "module publishing",
        )

        expect(
            client.post(
                f"/faculty/studio/modules/{module_id}/items",
                data={
                    "item_type": "assessment",
                    "title": "Structured Assessment",
                    "body_html": "<p>Answer every question.</p>",
                    "external_url": "",
                    "embed_url": "",
                    "points": "4",
                    "due_at": "",
                    "accessible_alternative": "All questions are available as text.",
                    "assessment_response_type": "structured",
                    "attempts": "2",
                    "time_limit": "30",
                    "rubric": "Automatic questions are scored by NUVEDRA.",
                },
            ),
            303,
            "assessment creation",
        )
        with db() as conn:
            item = rows(
                execute(
                    conn,
                    "SELECT * FROM nexus_content_items WHERE module_id=? AND title='Structured Assessment'",
                    (module_id,),
                )
            )[0]
            item_id = int(item["id"])
            settings = json.loads(item["metadata_json"])["assessment"]
            if int(settings.get("attempts") or 0) != 2 or int(settings.get("time_limit") or 0) != 30:
                raise RuntimeError("Assessment attempts or timer settings were not stored.")

        expect(
            client.post(
                f"/faculty/studio/items/{item_id}/edit",
                data={
                    "item_type": "assessment",
                    "title": "Structured Assessment",
                    "body_html": "<p>Answer every question.</p>",
                    "external_url": "",
                    "embed_url": "",
                    "points": "4",
                    "due_at": "",
                    "position": "1",
                    "status": "published",
                    "accessible_alternative": "All questions are available as text.",
                    "assessment_response_type": "structured",
                    "attempts": "2",
                    "time_limit": "30",
                    "rubric": "Automatic questions are scored by NUVEDRA.",
                },
            ),
            303,
            "assessment publishing",
        )
        with db() as conn:
            execute(
                conn,
                "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?",
                (utcnow(), course_id),
            )
            execute(
                conn,
                "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                (course_id, "student.v2@example.com", "student", "active", utcnow()),
            )

        builder = client.get(f"/faculty/studio/items/{item_id}/assessment")
        expect(builder, 200, "Assessment Builder")
        for marker in ('data-testid="assessment-builder"', "My question bank", "Multiple choice"):
            if marker not in builder.text:
                raise RuntimeError(f"Assessment Builder did not show {marker!r}.")

        expect(
            client.post(
                f"/faculty/studio/items/{item_id}/assessment/questions",
                data={
                    "question_type": "multiple_choice",
                    "prompt": "Capital of Puerto Rico?",
                    "choices": "San Juan\nPonce\nMayagüez",
                    "correct_answer": "San Juan",
                    "points": "1",
                    "position": "1",
                    "feedback_correct": "Correct.",
                    "feedback_incorrect": "Review Puerto Rico geography.",
                    "save_to_bank": "1",
                },
            ),
            303,
            "multiple-choice question",
        )
        expect(
            client.post(
                f"/faculty/studio/items/{item_id}/assessment/questions",
                data={
                    "question_type": "true_false",
                    "prompt": "NUVEDRA supports structured assessments.",
                    "choices": "",
                    "correct_answer": "True",
                    "points": "1",
                    "position": "2",
                    "feedback_correct": "Correct.",
                    "feedback_incorrect": "Review the assessment instructions.",
                },
            ),
            303,
            "true-false question",
        )
        expect(
            client.post(
                f"/faculty/studio/items/{item_id}/assessment/questions",
                data={
                    "question_type": "short_answer",
                    "prompt": "Type the word alpha.",
                    "choices": "",
                    "correct_answer": "alpha||Alpha",
                    "points": "1",
                    "position": "3",
                    "feedback_correct": "Correct.",
                    "feedback_incorrect": "Try again.",
                },
            ),
            303,
            "short-answer question",
        )

        with db() as conn:
            bank = rows(
                execute(
                    conn,
                    "SELECT id FROM nuvedra_question_bank WHERE lower(owner_email)='assessment.admin@example.com' ORDER BY id DESC LIMIT 1",
                )
            )
            if not bank:
                raise RuntimeError("The question was not saved to the question bank.")
            bank_id = int(bank[0]["id"])

        expect(
            client.post(f"/faculty/studio/items/{item_id}/assessment/bank/{bank_id}/import"),
            303,
            "question-bank import",
        )

        expect(client.get("/__smoke/assessment-user/student"), 200, "student session")
        course = client.get(f"/learn/courses/{course_id}")
        expect(course, 200, "student course")
        if f'/learn/assessments/{item_id}' not in course.text:
            raise RuntimeError("The student course did not link to the structured assessment.")

        expect(client.post(f"/learn/assessments/{item_id}/start"), 303, "first attempt start")
        active = client.get(f"/learn/assessments/{item_id}")
        expect(active, 200, "active structured assessment")
        if "data-assessment-timer" not in active.text:
            raise RuntimeError("The assessment timer was not rendered.")

        with db() as conn:
            attempt_id = int(
                rows(
                    execute(
                        conn,
                        """SELECT id FROM nuvedra_assessment_attempts
                           WHERE item_id=? AND lower(student_email)='student.v2@example.com'
                           ORDER BY attempt_number DESC LIMIT 1""",
                        (item_id,),
                    )
                )[0]["id"]
            )
            questions = rows(
                execute(
                    conn,
                    "SELECT id,prompt FROM nuvedra_assessment_questions WHERE item_id=? ORDER BY position,id",
                    (item_id,),
                )
            )

        answers = {}
        for question in questions:
            prompt = str(question["prompt"])
            if prompt == "Capital of Puerto Rico?":
                answers[f"q_{int(question['id'])}"] = "San Juan"
            elif prompt == "NUVEDRA supports structured assessments.":
                answers[f"q_{int(question['id'])}"] = "True"
            elif prompt == "Type the word alpha.":
                answers[f"q_{int(question['id'])}"] = "alpha"
            else:
                raise RuntimeError(f"Unexpected assessment question during smoke test: {prompt}")

        expect(
            client.post(f"/learn/assessments/{item_id}/attempts/{attempt_id}/submit", data=answers),
            303,
            "automatic assessment submission",
        )

        with db() as conn:
            attempt = rows(execute(conn, "SELECT * FROM nuvedra_assessment_attempts WHERE id=?", (attempt_id,)))[0]
            if float(attempt.get("score_total") or 0) != 4:
                raise RuntimeError(f"Automatic grading expected 4 points, got {attempt.get('score_total')!r}.")
            grade = rows(
                execute(
                    conn,
                    """SELECT g.points_awarded FROM nuvedra_grades g
                       JOIN nuvedra_submissions s ON s.id=g.submission_id
                       WHERE s.item_id=? AND lower(s.student_email)='student.v2@example.com'""",
                    (item_id,),
                )
            )
            if not grade or float(grade[0].get("points_awarded") or 0) != 4:
                raise RuntimeError("The automatic score was not synchronized with Gradebook.")

        grades = client.get(f"/learn/courses/{course_id}/grades")
        expect(grades, 200, "student grades")
        if "4 / 4" not in grades.text:
            raise RuntimeError("The student's automatic assessment score did not appear in My Grades.")

        expect(client.get("/__smoke/assessment-user/admin"), 200, "administrator-instructor session")
        expect(
            client.post(
                f"/faculty/studio/items/{item_id}/assessment/questions",
                data={
                    "question_type": "essay",
                    "prompt": "Explain one benefit of structured assessment.",
                    "choices": "",
                    "correct_answer": "",
                    "points": "0",
                    "position": "5",
                    "feedback_correct": "",
                    "feedback_incorrect": "",
                },
            ),
            303,
            "essay question authoring",
        )
        with db() as conn:
            essay = rows(
                execute(
                    conn,
                    "SELECT id FROM nuvedra_assessment_questions WHERE item_id=? AND question_type='essay'",
                    (item_id,),
                )
            )
            if not essay:
                raise RuntimeError("The essay question was not saved.")

    print(
        "Assessments v2 validated: question bank, multiple choice, true/false, short answer, essay authoring, attempts, timer, student delivery, and automatic Gradebook scoring.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
