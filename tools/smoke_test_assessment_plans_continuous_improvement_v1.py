from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-assessment-plans-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "assessment-plans-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "assessment-plans-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "assessment.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Assessment-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Assessment Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/assessment-plan-user/{kind}", include_in_schema=False)
async def smoke_assessment_plan_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "assessment-instructor", "name": "Program Coordinator", "email": "assessment.admin@example.com"},
        "reviewer": {"id": "assessment-reviewer", "name": "Assessment Reviewer", "email": "assessment.reviewer@example.com"},
        "student": {"id": "assessment-student", "name": "Assessment Student", "email": "assessment.student@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported assessment-plan smoke user.")
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
        expect(client.post("/admin/login", data={"email": "assessment.admin@example.com", "password": "Initial-Assessment-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Assessment-2026!", "confirm": "Updated-Assessment-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "ASSESS-7000", "title": "Program Assessment Evidence", "description": "Assessment evidence course.",
            "term": "Fall 2026", "instructor_email": "assessment.admin@example.com", "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "assessment.student@example.com", "student", "active", now))
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "Assessment Evidence", "Program assessment evidence.", "Analyze evidence.", 30, 1, "published", now, now))
            module_id = int(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)).fetchone()[0])
            item_id = int(execute(conn, """INSERT INTO nexus_content_items
                (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                VALUES (?,'assignment','Signature Evidence','<p>Signature evidence.</p>','','','{}',100,NULL,1,'published',?,?)""", (module_id, now, now)).lastrowid)
            course_outcome_id = int(execute(conn, """INSERT INTO nuvedra_outcomes
                (course_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,'CLO-1','Analyze assessment evidence','Analyze assessment evidence.','active',?,?,?)""", (course_id, "assessment.admin@example.com", now, now)).lastrowid)
            execute(conn, "INSERT INTO nuvedra_outcome_links (outcome_id,item_id,created_by,created_at) VALUES (?,?,?,?)", (course_outcome_id, item_id, "assessment.admin@example.com", now))
            submission_id = int(execute(conn, """INSERT INTO nuvedra_submissions
                (item_id,student_email,response_text,response_url,status,submitted_at,updated_at)
                VALUES (?,?,'Signature evidence submitted.','','submitted',?,?)""", (item_id, "assessment.student@example.com", now, now)).lastrowid)
            execute(conn, """INSERT INTO nuvedra_grades
                (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at)
                VALUES (?,88,'Meets course outcome evidence expectations.','graded',?,?,?)""", (submission_id, "assessment.admin@example.com", now, now))

        expect(client.get("/admin/logout"), 303, "admin logout")
        expect(client.get("/__smoke/assessment-plan-user/instructor"), 200, "instructor session")
        created_program = client.post("/faculty/programs", data={
            "program_code": "EDD-CI", "title": "Continuous Improvement Doctoral Program", "description": "Continuous improvement evidence workspace.",
        })
        expect(created_program, 303, "program creation")
        program_id = int(created_program.headers["location"].rsplit("/", 1)[-1])
        expect(client.post(f"/faculty/programs/{program_id}/courses", data={"course_id": str(course_id)}), 303, "add program course")
        expect(client.post(f"/faculty/programs/{program_id}/outcomes", data={"code": "PLO-1", "title": "Integrate assessment evidence", "description": "Integrate direct and indirect evidence for improvement."}), 303, "create program outcome")
        with db() as conn:
            program_outcome_id = int(rows(execute(conn, "SELECT id FROM nuvedra_program_outcomes WHERE program_id=? AND code='PLO-1'", (program_id,)))[0]["id"])
        expect(client.post(f"/faculty/programs/{program_id}/alignments", data={
            "program_outcome_id": str(program_outcome_id), "course_outcome_id": str(course_outcome_id), "curriculum_level": "mastered", "weight": "1",
        }), 303, "align course outcome to program outcome")

        plans = client.get(f"/faculty/programs/{program_id}/assessment-plans")
        expect(plans, 200, "assessment plans workspace")
        require(plans, 'data-testid="assessment-plans-continuous-improvement-v1"', "assessment plans marker")
        require(plans, "Create assessment cycle", "assessment cycle creation")

        cycle = client.post(f"/faculty/programs/{program_id}/assessment-plans/cycles", data={
            "label": "2026–2027 Assessment Cycle", "start_date": "2026-08-01", "end_date": "2027-07-31",
        })
        expect(cycle, 303, "assessment cycle creation")
        cycle_id = int(cycle.headers["location"].split("cycle_id=")[-1])

        direct = client.post(f"/faculty/programs/{program_id}/assessment-plans/measures", data={
            "cycle_id": str(cycle_id), "program_outcome_id": str(program_outcome_id), "title": "Signature assignment evidence",
            "measure_type": "direct", "method": "Faculty scoring of signature assignment", "data_source": "NUVEDRA Gradebook",
            "frequency": "Annual", "target_threshold": "80", "responsible_email": "assessment.admin@example.com",
        })
        expect(direct, 303, "direct measure creation")
        indirect = client.post(f"/faculty/programs/{program_id}/assessment-plans/measures", data={
            "cycle_id": str(cycle_id), "program_outcome_id": str(program_outcome_id), "title": "Graduating student survey",
            "measure_type": "indirect", "method": "Program survey", "data_source": "Annual graduating student survey",
            "frequency": "Annual", "target_threshold": "75", "responsible_email": "assessment.admin@example.com",
        })
        expect(indirect, 303, "indirect measure creation")
        with db() as conn:
            measures = rows(execute(conn, "SELECT id,title FROM nuvedra_assessment_measures WHERE cycle_id=? ORDER BY id", (cycle_id,)))
            direct_id = next(int(row["id"]) for row in measures if row["title"] == "Signature assignment evidence")
            indirect_id = next(int(row["id"]) for row in measures if row["title"] == "Graduating student survey")

        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/measures/{direct_id}/result", data={
            "result_value": "85", "sample_size": "20", "finding_summary": "Direct benchmark achieved.", "evidence_reference": "Signature assignment annual summary",
        }), 303, "direct measure result")
        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/measures/{indirect_id}/result", data={
            "result_value": "70", "sample_size": "25", "finding_summary": "Survey result fell below the 75% target.", "evidence_reference": "Graduating student survey report",
        }), 303, "indirect measure result")

        action = client.post(f"/faculty/programs/{program_id}/assessment-plans/actions", data={
            "cycle_id": str(cycle_id), "program_outcome_id": str(program_outcome_id), "measure_id": str(indirect_id),
            "title": "Revise research-support orientation", "action_plan": "Add an applied evidence workshop and advisor checkpoint before the capstone sequence.",
            "responsible_email": "assessment.admin@example.com", "due_date": "2027-01-31",
        })
        expect(action, 303, "improvement action creation")
        with db() as conn:
            action_id = int(rows(execute(conn, "SELECT id FROM nuvedra_improvement_actions WHERE cycle_id=?", (cycle_id,)))[0]["id"])

        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/actions/{action_id}/status", data={
            "status": "verified", "evidence_note": "Workshop implemented.", "follow_up_result": "Post-change survey 82%.", "closing_note": "",
        }), 400, "verification requires closing-the-loop note")
        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/actions/{action_id}/status", data={
            "status": "in_progress", "evidence_note": "Workshop and advisor checkpoint implemented.", "follow_up_result": "", "closing_note": "",
        }), 303, "action in progress")
        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/actions/{action_id}/status", data={
            "status": "verified", "evidence_note": "Workshop and advisor checkpoint implemented.",
            "follow_up_result": "Post-change survey reached 82%.",
            "closing_note": "Follow-up exceeded the 75% target; retain the change and monitor the next cycle.",
        }), 303, "closing the loop verification")

        dashboard = client.get(f"/faculty/programs/{program_id}/assessment-plans?cycle_id={cycle_id}")
        expect(dashboard, 200, "assessment cycle dashboard")
        require(dashboard, "Direct measures", "direct measure summary")
        require(dashboard, "Indirect measures", "indirect measure summary")
        require(dashboard, "Target met", "target met classification")
        require(dashboard, "Target not met", "target gap classification")
        require(dashboard, "85.0%", "recorded direct result")
        require(dashboard, "70.0%", "recorded indirect result")
        require(dashboard, "88.0%", "current program evidence context")
        require(dashboard, "Post-change survey reached 82%", "follow-up result")
        require(dashboard, "Follow-up exceeded the 75% target", "closing-the-loop note")

        export = client.get(f"/faculty/programs/{program_id}/assessment-plans.csv?cycle_id={cycle_id}")
        expect(export, 200, "continuous improvement CSV")
        require(export, "Signature assignment evidence", "direct measure export")
        require(export, "Graduating student survey", "indirect measure export")
        require(export, "Revise research-support orientation", "improvement action export")
        require(export, "Post-change survey reached 82%", "follow-up export")
        if "assessment.student@example.com" in export.text:
            raise RuntimeError("Continuous-improvement CSV leaked a student email address.")

        expect(client.post(f"/faculty/programs/{program_id}/members", data={"user_email": "assessment.reviewer@example.com", "program_role": "reviewer"}), 303, "add reviewer")
        program_page = client.get(f"/faculty/programs/{program_id}")
        expect(program_page, 200, "program page with assessment plans navigation")
        require(program_page, 'data-assessment-plans-link="v1"', "assessment plans program navigation")

        expect(client.get("/__smoke/assessment-plan-user/reviewer"), 200, "reviewer session")
        expect(client.get(f"/faculty/programs/{program_id}/assessment-plans?cycle_id={cycle_id}"), 200, "reviewer read-only workspace")
        expect(client.get(f"/faculty/programs/{program_id}/assessment-plans.csv?cycle_id={cycle_id}"), 200, "reviewer CSV access")
        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/measures/{direct_id}/result", data={
            "result_value": "90", "sample_size": "20", "finding_summary": "Unauthorized update", "evidence_reference": "",
        }), 403, "reviewer mutation protection")

        expect(client.get("/__smoke/assessment-plan-user/student"), 200, "student session")
        expect(client.get(f"/faculty/programs/{program_id}/assessment-plans?cycle_id={cycle_id}"), 403, "student workspace protection")
        expect(client.get(f"/faculty/programs/{program_id}/assessment-plans.csv?cycle_id={cycle_id}"), 403, "student export protection")

        expect(client.get("/__smoke/assessment-plan-user/instructor"), 200, "instructor return session")
        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/cycles/{cycle_id}/close"), 303, "close assessment cycle")
        expect(client.post(f"/faculty/programs/{program_id}/assessment-plans/measures/{direct_id}/result", data={
            "result_value": "91", "sample_size": "20", "finding_summary": "Attempt after close", "evidence_reference": "",
        }), 409, "closed cycle read-only protection")
        closed = client.get(f"/faculty/programs/{program_id}/assessment-plans?cycle_id={cycle_id}")
        expect(closed, 200, "closed cycle view")
        require(closed, "closed", "closed cycle status")
        if "Add assessment measure" in closed.text or "Create improvement action" in closed.text:
            raise RuntimeError("Closed assessment cycle still exposed mutation forms.")

    print("Assessment Plans & Continuous Improvement v1 validated: annual cycle, direct/indirect measures, target findings, current program-evidence context, improvement action, closing-the-loop verification, privacy-preserving CSV, reviewer/student permissions, program navigation, and read-only closed-cycle history.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
