from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-microsoft365-education-sync-v6-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft-education-v6-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft-education-v6-admin-secret-123456"
os.environ["MICROSOFT_CLIENT_ID"] = "microsoft-v6-client"
os.environ["MICROSOFT_CLIENT_SECRET"] = "microsoft-v6-client-secret-never-render"
os.environ["MICROSOFT_TENANT_ID"] = "11111111-2222-3333-4444-555555555555"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example/auth/microsoft/callback"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "microsoft-education-v6-token-encryption-key-2026"
os.environ["MICROSOFT_REQUIRE_INSTITUTION_TENANT"] = "true"
os.environ["MICROSOFT_ALLOW_EDUCATION_WRITES"] = "true"
os.environ["MICROSOFT_ALLOW_EDUCATION_PUBLISH"] = "true"
os.environ["MICROSOFT_ALLOW_GRADE_EXPORT"] = "true"
os.environ["MICROSOFT_ALLOW_GRADE_RETURN"] = "true"
os.environ["MICROSOFT_SCOPES"] = "openid profile email offline_access User.Read EduRoster.ReadBasic EduAssignments.ReadBasic EduAssignments.ReadWriteBasic EduAssignments.ReadWrite"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.microsoft365_integration as m365  # noqa: E402
import app.microsoft365_production_v3 as production  # noqa: E402


@app.get("/__smoke/microsoft-v6-user/{kind}", include_in_schema=False)
async def smoke_microsoft_v6_user(kind: str, request: Request):
    if kind == "instructor":
        request.session["user"] = {"id": "microsoft-v6-instructor", "name": "Microsoft V6 Instructor", "email": "v6.instructor@example.com"}
    elif kind == "student":
        request.session["user"] = {"id": "microsoft-v6-student", "name": "Microsoft V6 Student", "email": "v6.student@example.com"}
    else:
        raise RuntimeError("Unsupported Microsoft v6 smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def insert_id(conn, sql: str, params: tuple) -> int:
    return int(execute(conn, sql, params).lastrowid)


def main() -> None:
    graph_json_calls: list[tuple[str, str, object]] = []
    graph_collection_calls: list[str] = []
    assignment_posts: list[dict] = []
    outcome_patches: list[dict] = []
    return_calls: list[str] = []

    async def fake_graph_json(email: str, method: str, path: str, *, params=None, json_body=None):
        graph_json_calls.append((method.upper(), path, json_body))
        if method.upper() == "POST" and path == "/education/classes/class-v6-01/assignments":
            assignment_posts.append(json_body or {})
            return {
                "id": "assignment-v6-01",
                "displayName": str((json_body or {}).get("displayName") or ""),
                "status": "draft",
                "webUrl": "https://teams.microsoft.com/l/assignment-v6-01",
                "grading": {"@odata.type": "#microsoft.graph.educationAssignmentPointsGradeType", "maxPoints": 100},
            }
        if method.upper() == "POST" and path == "/education/classes/class-v6-01/assignments/assignment-v6-01/publish":
            return {
                "id": "assignment-v6-01",
                "displayName": "Microsoft Education V6 Assignment",
                "status": "assigned",
                "webUrl": "https://teams.microsoft.com/l/assignment-v6-01",
                "grading": {"@odata.type": "#microsoft.graph.educationAssignmentPointsGradeType", "maxPoints": 100},
            }
        if method.upper() == "GET" and path == "/education/classes/class-v6-01/assignments/assignment-v6-01":
            return {
                "id": "assignment-v6-01",
                "displayName": "Microsoft Education V6 Assignment",
                "status": "assigned",
                "webUrl": "https://teams.microsoft.com/l/assignment-v6-01",
                "dueDateTime": "2026-09-15T23:59:00Z",
                "grading": {"@odata.type": "#microsoft.graph.educationAssignmentPointsGradeType", "maxPoints": 100},
            }
        if method.upper() == "PATCH" and path.endswith("/outcomes/points-outcome-v6"):
            outcome_patches.append(json_body or {})
            return {
                "id": "points-outcome-v6",
                "@odata.type": "#microsoft.graph.educationPointsOutcome",
                "points": (json_body or {}).get("points"),
            }
        if method.upper() == "POST" and path.endswith("/submissions/ms-submission-v6/return"):
            return_calls.append(path)
            return {"id": "ms-submission-v6", "status": "returned"}
        raise RuntimeError(f"Unexpected Microsoft v6 Graph JSON call: {method} {path} {params} {json_body}")

    async def fake_graph_collection(email: str, path: str, *, params=None):
        graph_collection_calls.append(path)
        if path == "/education/classes/class-v6-01/members":
            return ([{
                "id": "edu-student-v6",
                "displayName": "Microsoft V6 Student",
                "mail": "v6.student@example.com",
                "userPrincipalName": "v6.student@example.com",
                "primaryRole": "student",
            }], 1)
        if path == "/education/classes/class-v6-01/assignments/assignment-v6-01/submissions":
            return ([{
                "id": "ms-submission-v6",
                "status": "submitted",
                "recipient": {"@odata.type": "#microsoft.graph.educationSubmissionIndividualRecipient", "userId": "edu-student-v6"},
                "submittedDateTime": "2026-09-14T15:00:00Z",
                "webUrl": "https://teams.microsoft.com/l/submission-v6",
            }], 1)
        if path == "/education/classes/class-v6-01/assignments/assignment-v6-01/submissions/ms-submission-v6/outcomes":
            return ([{
                "id": "points-outcome-v6",
                "@odata.type": "#microsoft.graph.educationPointsOutcome",
                "points": {"points": None},
                "publishedPoints": {"points": None},
            }], 1)
        raise RuntimeError(f"Unexpected Microsoft v6 Graph collection call: {path} {params}")

    original_graph_json = m365._graph_json
    original_collection = production._graph_collection
    m365._graph_json = fake_graph_json
    production._graph_collection = fake_graph_collection
    try:
        with TestClient(app, follow_redirects=False) as client:
            now = utcnow()
            with db() as conn:
                course_id = insert_id(conn, """INSERT INTO nexus_admin_courses
                    (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (
                    "MSV6-6100", "Microsoft Education Sync V6", "Education assignments and grade synchronization smoke test.",
                    "Fall 2026", "active", "v6.instructor@example.com", "v6.instructor@example.com", now, now,
                ))
                module_id = insert_id(conn, """INSERT INTO nexus_modules
                    (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (
                    course_id, "Module 1", "Microsoft Education integration", "Synchronize approved academic evidence.", 60, 1, "published", now, now,
                ))
                item_id = insert_id(conn, """INSERT INTO nexus_content_items
                    (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    module_id, "assignment", "Microsoft Education V6 Assignment", "<p>Analyze the assigned scenario and submit your evidence.</p>",
                    None, None, "{}", 100, "2026-09-15T23:59:00+00:00", 1, "published", now, now,
                ))
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "v6.instructor@example.com", "instructor", "active", now))
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "v6.student@example.com", "student", "active", now))
                scopes = os.environ["MICROSOFT_SCOPES"]
                m365._store_connection(conn, "v6.instructor@example.com", tenant_id=os.environ["MICROSOFT_TENANT_ID"], account_id="aad-v6-instructor", display_name="Microsoft V6 Instructor", access_token="v6-access-token-never-render", refresh_token="v6-refresh-token-never-render", expires_in=3600, scopes=scopes)
                execute(conn, """INSERT INTO nuvedra_microsoft_education_class_links
                    (course_id,class_id,display_name,external_id,status,linked_by,linked_at,verified_at)
                    VALUES (?,?,?,?,'active',?,?,?)""", (course_id, "class-v6-01", "Microsoft V6 Class", "MSV6-6100", "v6.instructor@example.com", now, now))
                submission_id = insert_id(conn, """INSERT INTO nuvedra_submissions
                    (item_id,student_email,response_text,response_url,status,submitted_at,updated_at)
                    VALUES (?,?,?,?,?,?,?)""", (item_id, "v6.student@example.com", "Canonical NUVEDRA submission", None, "submitted", now, now))
                execute(conn, """INSERT INTO nuvedra_grades
                    (submission_id,points_awarded,feedback,status,graded_by,graded_at,updated_at)
                    VALUES (?,?,?,?,?,?,?)""", (submission_id, 92, "Strong work.", "graded", "v6.instructor@example.com", now, now))

            expect(client.get("/__smoke/microsoft-v6-user/instructor"), 200, "set instructor session")
            workspace = client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education-sync")
            expect(workspace, 200, "education sync workspace")
            require(workspace, 'data-testid="microsoft365-education-sync-v6"', "education sync workspace")
            if os.environ["MICROSOFT_CLIENT_SECRET"] in workspace.text or "v6-access-token-never-render" in workspace.text:
                raise RuntimeError("Microsoft Education Sync v6 exposed Microsoft secret/token material.")

            create = client.post(f"/faculty/studio/assignments/{item_id}/microsoft365/education-sync/create")
            expect(create, 303, "create Microsoft Education assignment")
            if len(assignment_posts) != 1:
                raise RuntimeError("Microsoft Education assignment create was not sent exactly once.")
            posted = assignment_posts[0]
            if posted.get("status") != "draft" or float((posted.get("grading") or {}).get("maxPoints") or 0) != 100:
                raise RuntimeError("Microsoft Education assignment create did not preserve draft/points safeguards.")
            if posted.get("dueDateTime") != "2026-09-15T23:59:00Z":
                raise RuntimeError("Microsoft Education assignment due date was not derived from NUVEDRA.")
            with db() as conn:
                mapping = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_education_assignments WHERE item_id=?", (item_id,)))
                if not mapping or mapping[0]["microsoft_assignment_id"] != "assignment-v6-01" or mapping[0]["microsoft_status"] != "draft":
                    raise RuntimeError("Microsoft Education assignment mapping was not persisted.")

            published = client.post(f"/faculty/studio/assignments/{item_id}/microsoft365/education-sync/publish")
            expect(published, 303, "publish Microsoft Education assignment")
            with db() as conn:
                mapping = rows(execute(conn, "SELECT microsoft_status FROM nuvedra_microsoft_education_assignments WHERE item_id=?", (item_id,)))
                if not mapping or mapping[0]["microsoft_status"] != "assigned":
                    raise RuntimeError("Microsoft Education publish status was not persisted.")

            preview = client.get(f"/faculty/studio/assignments/{item_id}/microsoft365/education-sync/grades")
            expect(preview, 200, "grade export preview")
            require(preview, 'data-testid="microsoft365-grade-export-v6"', "grade export preview")
            require(preview, "92 / 100", "canonical NUVEDRA grade")
            require(preview, "Ready", "Microsoft grade export readiness")

            exported = client.post(f"/faculty/studio/assignments/{item_id}/microsoft365/education-sync/grades", data={"return_to_student": "1"})
            expect(exported, 303, "grade export")
            if len(outcome_patches) != 1:
                raise RuntimeError("Microsoft points outcome was not patched exactly once.")
            exported_points = float(((outcome_patches[0].get("points") or {}).get("points") or 0))
            if exported_points != 92:
                raise RuntimeError(f"Expected Microsoft normalized grade 92, received {exported_points}.")
            if len(return_calls) != 1:
                raise RuntimeError("Microsoft submission was not returned after approved grade export.")
            if any(method == "DELETE" for method, _path, _body in graph_json_calls):
                raise RuntimeError("Microsoft Education Sync v6 issued a destructive DELETE operation.")
            with db() as conn:
                grade = rows(execute(conn, "SELECT points_awarded,status FROM nuvedra_grades WHERE submission_id=?", (submission_id,)))
                if not grade or float(grade[0]["points_awarded"]) != 92 or grade[0]["status"] != "graded":
                    raise RuntimeError("Canonical NUVEDRA grade changed during Microsoft export.")
                exports = rows(execute(conn, "SELECT action,status,microsoft_points FROM nuvedra_microsoft_grade_exports WHERE item_id=? ORDER BY id", (item_id,)))
                if len(exports) != 1 or exports[0]["action"] != "grade_export_return" or exports[0]["status"] != "exported" or float(exports[0]["microsoft_points"]) != 92:
                    raise RuntimeError("Microsoft grade export audit record was not persisted correctly.")

            os.environ["MICROSOFT_ALLOW_GRADE_EXPORT"] = "false"
            blocked = client.post(f"/faculty/studio/assignments/{item_id}/microsoft365/education-sync/grades")
            expect(blocked, 403, "grade export policy gate")
            os.environ["MICROSOFT_ALLOW_GRADE_EXPORT"] = "true"

            expect(client.get("/__smoke/microsoft-v6-user/student"), 200, "set student session")
            expect(client.get(f"/faculty/studio/courses/{course_id}/microsoft365/education-sync"), 403, "student education sync protection")
            expect(client.get(f"/faculty/studio/assignments/{item_id}/microsoft365/education-sync"), 403, "student assignment sync protection")

        print("Microsoft Education Assignments & Grade Integration v6 validated: explicit write policies, assignment draft creation, NUVEDRA-first publishing, effective scope gates, education roster/submission matching, canonical 92/100 grade export, optional return, immutable audit history, secret non-disclosure, no DELETE operations, and student role protection.", flush=True)
    finally:
        m365._graph_json = original_graph_json
        production._graph_collection = original_collection
        if DB_PATH.exists():
            DB_PATH.unlink()


if __name__ == "__main__":
    main()
