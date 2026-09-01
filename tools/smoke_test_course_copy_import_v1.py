from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-course-copy-import-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "course-copy-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "course-copy-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "copy.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Copy-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Copy Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/course-copy-user/{kind}", include_in_schema=False)
async def smoke_course_copy_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "copy-instructor", "name": "Copy Instructor", "email": "copy.instructor@example.com"},
        "student": {"id": "copy-student", "name": "Copy Student", "email": "copy.student@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported course-copy smoke user.")
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
        expect(client.post("/admin/login", data={"email": "copy.admin@example.com", "password": "Initial-Copy-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Copy-2026!", "confirm": "Updated-Copy-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "COPY-4100",
            "title": "Course Copy Source",
            "description": "Reusable course design source.",
            "term": "Fall 2026",
            "instructor_email": "copy.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "source course creation")
        source_course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, source_course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (source_course_id, "copy.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (source_course_id, "copy.observer@example.com", "observer", "active", now))
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (source_course_id, "Module One", "Primary module.", "Analyze evidence.", 60, 1, "published", now, now))
            module_one = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND title='Module One'", (source_course_id,)))[0]["id"])
            execute(conn, "INSERT INTO nexus_module_drafts (module_id,title,body_html,updated_by,updated_at) VALUES (?,?,?,?,?)", (module_one, "Module One Overview", "<p>Reusable overview.</p>", "copy.instructor@example.com", now))
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (source_course_id, "Module Two", "Secondary module.", "Apply concepts.", 45, 2, "published", now, now))
            module_two = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND title='Module Two'", (source_course_id,)))[0]["id"])

            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_one, "assignment", "Research Assignment", "<p>Submit evidence.</p>", "", "", "{}", 100, "2026-09-20T23:59", 1, "published", now, now))
            assignment_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title='Research Assignment'", (module_one,)))[0]["id"])
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_one, "quiz", "Knowledge Check", "<p>Structured quiz.</p>", "", "", "{}", 10, "2026-09-18T23:59", 2, "published", now, now))
            quiz_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title='Knowledge Check'", (module_one,)))[0]["id"])
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_two, "discussion", "Module Two Discussion", "<p>Discuss the case.</p>", "", "", "{}", 20, "2026-09-25T23:59", 1, "published", now, now))
            discussion_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title='Module Two Discussion'", (module_two,)))[0]["id"])

            execute(conn, "INSERT INTO nuvedra_assessment_questions (item_id,question_type,prompt,choices_json,correct_answer,points,position,feedback_correct,feedback_incorrect,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (quiz_id, "multiple_choice", "Which choice is correct?", '["A","B"]', "B", 10, 1, "Correct.", "Review the module.", now, now))

            execute(conn, "INSERT INTO nuvedra_library_assets (owner_email,name,asset_type,mime_type,description,accessibility_text,tags,source_url,file_name,file_size,file_bytes,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("copy.instructor@example.com", "Course Guide", "pdf", "application/pdf", "Reusable guide", "", "guide", "https://example.com/course-guide.pdf", None, 0, None, "active", now, now))
            asset_id = int(rows(execute(conn, "SELECT id FROM nuvedra_library_assets WHERE name='Course Guide'"))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_library_uses (asset_id,course_id,module_id,item_id,attached_by,attached_at) VALUES (?,?,?,?,?,?)", (asset_id, source_course_id, module_one, assignment_id, "copy.instructor@example.com", now))

            execute(conn, "INSERT INTO nuvedra_rubrics (course_id,title,description,status,created_by,created_at,updated_at) VALUES (?,?,?,'active',?,?,?)", (source_course_id, "Research Rubric", "Reusable rubric", "copy.instructor@example.com", now, now))
            rubric_id = int(rows(execute(conn, "SELECT id FROM nuvedra_rubrics WHERE course_id=?", (source_course_id,)))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_rubric_criteria (rubric_id,title,description,position,created_at) VALUES (?,?,?,?,?)", (rubric_id, "Evidence", "Quality of evidence", 1, now))
            criterion_id = int(rows(execute(conn, "SELECT id FROM nuvedra_rubric_criteria WHERE rubric_id=?", (rubric_id,)))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_rubric_levels (criterion_id,label,description,points,position,created_at) VALUES (?,?,?,?,?,?)", (criterion_id, "Excellent", "Strong evidence", 100, 1, now))
            execute(conn, "INSERT INTO nuvedra_rubric_links (rubric_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (rubric_id, assignment_id, "copy.instructor@example.com", now))

            execute(conn, "INSERT INTO nuvedra_outcomes (course_id,code,title,description,status,created_by,created_at,updated_at) VALUES (?,?,?,?,'active',?,?,?)", (source_course_id, "CLO-1", "Analyze evidence", "Evaluate credible evidence.", "copy.instructor@example.com", now, now))
            outcome_id = int(rows(execute(conn, "SELECT id FROM nuvedra_outcomes WHERE course_id=?", (source_course_id,)))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_outcome_links (outcome_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (outcome_id, assignment_id, "copy.instructor@example.com", now))

            execute(conn, "INSERT INTO nuvedra_submissions (item_id,student_email,response_text,response_url,status,submitted_at,updated_at) VALUES (?,?,?,?,?,?,?)", (assignment_id, "copy.student@example.com", "Student work that must not copy.", None, "submitted", now, now))
            source_submission_id = int(rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=?", (assignment_id,)))[0]["id"])
            execute(conn, "INSERT INTO nuvedra_grades (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at) VALUES (?,?,?,'graded',?,?,?)", (source_submission_id, 95, "Source feedback", "copy.instructor@example.com", now, now))
            execute(conn, "INSERT INTO nexus_forum_posts (item_id,author_email,body,created_at) VALUES (?,?,?,?)", (discussion_id, "copy.student@example.com", "Source discussion post.", now))

        expect(client.get("/__smoke/course-copy-user/instructor"), 200, "instructor session")
        home = client.get(f"/faculty/studio/courses/{source_course_id}/copy")
        expect(home, 200, "course copy home")
        require(home, 'data-testid="course-copy-import-v1"', "course copy home")
        require(home, "Create a new course copy", "course copy home")
        require(home, "Due dates are cleared", "course copy safety notice")

        copied = client.post(f"/faculty/studio/courses/{source_course_id}/copy/new", data=[
            ("course_code", "COPY-4200"),
            ("title", "Course Copy Target"),
            ("term", "Spring 2027"),
            ("module_ids", str(module_one)),
            ("copy_questions", "1"),
            ("copy_rubrics", "1"),
            ("copy_outcomes", "1"),
        ])
        expect(copied, 303, "new course copy")
        target_course_id = int(copied.headers["location"].split("/courses/", 1)[1].split("?", 1)[0].split("/", 1)[0])

        with db() as conn:
            target = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (target_course_id,)))[0]
            if target.get("status") != "draft" or target.get("course_code") != "COPY-4200":
                raise RuntimeError("New course copy was not created as a draft with the requested identity.")
            enrollments = rows(execute(conn, "SELECT user_email,course_role FROM nexus_admin_enrollments WHERE course_id=? ORDER BY user_email", (target_course_id,)))
            if enrollments != [{"user_email": "copy.instructor@example.com", "course_role": "instructor"}]:
                raise RuntimeError(f"Learner enrollments leaked into the course copy: {enrollments}")
            target_modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (target_course_id,)))
            if len(target_modules) != 1 or target_modules[0].get("title") != "Module One" or target_modules[0].get("status") != "draft":
                raise RuntimeError("Selective module copy did not preserve exactly Module One as a draft.")
            target_module_id = int(target_modules[0]["id"])
            module_draft = rows(execute(conn, "SELECT * FROM nexus_module_drafts WHERE module_id=?", (target_module_id,)))
            if not module_draft or "Reusable overview" not in str(module_draft[0].get("body_html") or ""):
                raise RuntimeError("Module draft content was not copied.")
            target_items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (target_module_id,)))
            if len(target_items) != 2 or any(item.get("status") != "draft" for item in target_items):
                raise RuntimeError("Copied content items were not created as drafts.")
            if any(item.get("due_at") not in (None, "") for item in target_items):
                raise RuntimeError("Old due dates leaked into the copied course.")
            target_assignment = next(item for item in target_items if item.get("title") == "Research Assignment")
            target_quiz = next(item for item in target_items if item.get("title") == "Knowledge Check")
            questions = rows(execute(conn, "SELECT * FROM nuvedra_assessment_questions WHERE item_id=?", (int(target_quiz["id"]),)))
            if len(questions) != 1 or questions[0].get("correct_answer") != "B":
                raise RuntimeError("Structured assessment questions were not copied correctly.")
            uses = rows(execute(conn, "SELECT * FROM nuvedra_library_uses WHERE course_id=? AND item_id=?", (target_course_id, int(target_assignment["id"]))))
            if len(uses) != 1 or int(uses[0].get("asset_id") or 0) != asset_id:
                raise RuntimeError("Content Library reuse metadata was not remapped to the copied item.")
            rubrics = rows(execute(conn, "SELECT * FROM nuvedra_rubrics WHERE course_id=?", (target_course_id,)))
            if len(rubrics) != 1:
                raise RuntimeError("Rubric library was not duplicated into the target course.")
            rubric_links = rows(execute(conn, "SELECT * FROM nuvedra_rubric_links WHERE rubric_id=? AND item_id=?", (int(rubrics[0]["id"]), int(target_assignment["id"]))))
            if len(rubric_links) != 1:
                raise RuntimeError("Copied rubric was not linked to the remapped assignment.")
            outcomes = rows(execute(conn, "SELECT * FROM nuvedra_outcomes WHERE course_id=?", (target_course_id,)))
            if len(outcomes) != 1 or outcomes[0].get("code") != "CLO-1":
                raise RuntimeError("Learning outcomes were not copied.")
            outcome_links = rows(execute(conn, "SELECT * FROM nuvedra_outcome_links WHERE outcome_id=? AND item_id=?", (int(outcomes[0]["id"]), int(target_assignment["id"]))))
            if len(outcome_links) != 1:
                raise RuntimeError("Outcome alignment was not remapped to the copied assignment.")
            leaked_submissions = rows(execute(conn, """SELECT s.id FROM nuvedra_submissions s JOIN nexus_content_items i ON i.id=s.item_id JOIN nexus_modules m ON m.id=i.module_id WHERE m.course_id=?""", (target_course_id,)))
            leaked_grades = rows(execute(conn, """SELECT g.id FROM nuvedra_grades g JOIN nuvedra_submissions s ON s.id=g.submission_id JOIN nexus_content_items i ON i.id=s.item_id JOIN nexus_modules m ON m.id=i.module_id WHERE m.course_id=?""", (target_course_id,)))
            if leaked_submissions or leaked_grades:
                raise RuntimeError("Student submissions or grades leaked into the copied course.")

        expect(client.get("/__smoke/course-copy-user/student"), 200, "student session")
        denied = client.get(f"/faculty/studio/courses/{source_course_id}/copy")
        expect(denied, 403, "student course-copy protection")

    print("Course Copy & Import v1 validated: selective draft copy, cleared due dates, assessment questions, module drafts, Content Library uses, rubrics/outcomes remapping, and strict learner-data exclusion.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
