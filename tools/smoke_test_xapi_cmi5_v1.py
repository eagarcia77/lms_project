from __future__ import annotations

import json
import os
import re
import urllib.parse
import uuid
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-xapi-cmi5-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "xapi-cmi5-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "xapi-cmi5-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "xapi.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-XAPI-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "xAPI Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)
os.environ.pop("NUVEDRA_XAPI_ENDPOINT", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/xapi-user/{kind}", include_in_schema=False)
async def smoke_xapi_user(kind: str, request: Request):
    users = {
        "student": {"id": "xapi-student", "name": "xAPI Student", "email": "xapi.student@example.com"},
        "observer": {"id": "xapi-observer", "name": "xAPI Observer", "email": "xapi.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported xAPI smoke user.")
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
        expect(client.post("/admin/login", data={"email": "xapi.admin@example.com", "password": "Initial-XAPI-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-XAPI-2026!", "confirm": "Updated-XAPI-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "XAPI-7400", "title": "Experience Data and cmi5", "description": "xAPI and cmi5 validation course.",
            "term": "Fall 2026", "instructor_email": "xapi.admin@example.com", "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (("xapi.student@example.com", "student"), ("xapi.observer@example.com", "observer")):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, email, role, "active", now))
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "Experience Module", "External learning experiences.", "Use tracked interoperable learning experiences.", 45, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)))[0]["id"])

        home = client.get(f"/faculty/studio/courses/{course_id}/xapi")
        expect(home, 200, "xAPI and cmi5 workspace")
        require(home, 'data-testid="xapi-cmi5-v1"', "xAPI and cmi5 workspace")
        require(home, "does not claim 1EdTech cmi5 certification", "cmi5 scope disclosure")

        credential = client.post(f"/faculty/studio/courses/{course_id}/xapi/sources", data={"name": "Approved Simulation Source"})
        expect(credential, 201, "xAPI source credential creation")
        require(credential, 'data-testid="xapi-credential-created"', "xAPI source credential creation")
        match = re.search(r"Basic ([A-Za-z0-9+/=]+)", credential.text)
        if not match:
            raise RuntimeError("xAPI source credential page did not expose the one-time Basic credential.")
        source_auth = "Basic " + match.group(1)
        statement_id = str(uuid.uuid4())
        generic_statement = {
            "id": statement_id,
            "actor": {"objectType": "Agent", "mbox": "mailto:source.user@example.com"},
            "verb": {"id": "http://adlnet.gov/expapi/verbs/experienced"},
            "object": {"id": "https://activity.example/external-simulation"},
        }
        generic_post = client.post("/xapi/statements", headers={
            "Authorization": source_auth, "X-Experience-API-Version": "1.0.3", "Content-Type": "application/json",
        }, json=generic_statement)
        expect(generic_post, 200, "course-scoped xAPI statement write")
        if generic_post.json() != [statement_id] or generic_post.headers.get("x-experience-api-version") != "1.0.3":
            raise RuntimeError("xAPI statement write did not return the expected statement id/version header.")
        generic_read = client.get("/xapi/statements", params={"statementId": statement_id}, headers={"Authorization": source_auth})
        expect(generic_read, 200, "course-scoped xAPI statement read")
        if generic_read.json().get("id") != statement_id:
            raise RuntimeError("xAPI statement read returned the wrong statement.")

        cmi5_created = client.post(f"/faculty/studio/courses/{course_id}/xapi/cmi5", data={
            "module_id": str(module_id), "title": "Evidence cmi5 Activity",
            "launch_url": "https://au.example/launch", "activity_id": "https://activity.example/cmi5/evidence",
            "move_on": "CompletedOrPassed", "points": "100",
        })
        expect(cmi5_created, 303, "cmi5 activity creation")
        with db() as conn:
            au = rows(execute(conn, "SELECT * FROM nuvedra_cmi5_aus WHERE course_id=?", (course_id,)))[0]
            au_id = int(au["id"]); item_id = int(au["item_id"])
            item = rows(execute(conn, "SELECT item_type,external_url,status,points FROM nexus_content_items WHERE id=?", (item_id,)))[0]
            if item.get("item_type") != "cmi5" or item.get("external_url") != f"/learn/cmi5/{au_id}/launch" or float(item.get("points") or 0) != 100:
                raise RuntimeError(f"cmi5 content item linkage failed: {item}")
        expect(client.post(f"/faculty/studio/xapi/cmi5/{au_id}/toggle"), 303, "cmi5 publish")

        expect(client.get("/__smoke/xapi-user/student"), 200, "student session")
        item_route = client.get(f"/learn/items/{item_id}")
        expect(item_route, 303, "student cmi5 item redirect")
        if item_route.headers.get("location") != f"/learn/cmi5/{au_id}/launch":
            raise RuntimeError(f"cmi5 item redirect is wrong: {item_route.headers.get('location')}")
        launch = client.get(f"/learn/cmi5/{au_id}/launch")
        expect(launch, 303, "cmi5 launch")
        parsed = urllib.parse.urlparse(launch.headers["location"])
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.scheme != "https" or parsed.netloc != "au.example" or query.get("activityId") != ["https://activity.example/cmi5/evidence"]:
            raise RuntimeError(f"cmi5 launch parameters are invalid: {launch.headers['location']}")
        registration = query["registration"][0]
        actor = json.loads(query["actor"][0])
        fetch_url = urllib.parse.urlparse(query["fetch"][0])
        fetch_path = fetch_url.path + (("?" + fetch_url.query) if fetch_url.query else "")
        fetched = client.get(fetch_path)
        expect(fetched, 200, "cmi5 one-time credential fetch")
        cmi5_auth = fetched.json().get("auth-token")
        if not isinstance(cmi5_auth, str) or not cmi5_auth.startswith("Basic "):
            raise RuntimeError(f"cmi5 fetch did not return Basic xAPI authorization: {fetched.text}")
        expect(client.get(fetch_path), 409, "cmi5 fetch replay protection")

        state_params = {
            "activityId": "https://activity.example/cmi5/evidence",
            "agent": json.dumps(actor, separators=(",", ":")),
            "registration": registration,
            "stateId": "bookmark",
        }
        state_write = client.post("/xapi/activities/state", params=state_params, headers={"Authorization": cmi5_auth, "Content-Type": "application/json"}, json={"location": "page-2"})
        expect(state_write, 204, "cmi5 xAPI state write")
        state_read = client.get("/xapi/activities/state", params=state_params, headers={"Authorization": cmi5_auth})
        expect(state_read, 200, "cmi5 xAPI state read")
        if state_read.json().get("location") != "page-2":
            raise RuntimeError("cmi5 xAPI state document was not preserved.")

        completion_id = str(uuid.uuid4())
        completion_statement = {
            "id": completion_id,
            "actor": actor,
            "verb": {"id": "http://adlnet.gov/expapi/verbs/completed"},
            "object": {"id": "https://activity.example/cmi5/evidence"},
            "context": {"registration": registration},
            "result": {"completion": True, "success": True, "score": {"raw": 90, "min": 0, "max": 100}},
        }
        completed = client.post("/xapi/statements", headers={"Authorization": cmi5_auth, "Content-Type": "application/json"}, json=completion_statement)
        expect(completed, 200, "cmi5 completion statement")
        expect(client.post(f"/learn/items/{item_id}/complete", data={"completed": "1"}), 409, "manual cmi5 completion block")

        with db() as conn:
            progress = rows(execute(conn, "SELECT status FROM nuvedra_content_progress WHERE item_id=? AND lower(student_email)=?", (item_id, "xapi.student@example.com")))
            if not progress or progress[0].get("status") != "completed":
                raise RuntimeError(f"cmi5 completion did not synchronize to Student Experience progress: {progress}")
            registration_row = rows(execute(conn, "SELECT completed_at FROM nuvedra_cmi5_registrations WHERE au_id=? AND lower(student_email)=?", (au_id, "xapi.student@example.com")))
            if not registration_row or not registration_row[0].get("completed_at"):
                raise RuntimeError("cmi5 registration did not record completion.")
            submission = rows(execute(conn, "SELECT id FROM nuvedra_submissions WHERE item_id=? AND lower(student_email)=?", (item_id, "xapi.student@example.com")))
            if not submission:
                raise RuntimeError("cmi5 result did not create the canonical Gradebook submission.")
            grade = rows(execute(conn, "SELECT points_awarded,status FROM nuvedra_grades WHERE submission_id=?", (int(submission[0]["id"]),)))
            if not grade or grade[0].get("status") != "graded" or abs(float(grade[0].get("points_awarded") or 0) - 90.0) > 0.01:
                raise RuntimeError(f"cmi5 score did not synchronize to Gradebook: {grade}")

        cmi5_read = client.get("/xapi/statements", headers={"Authorization": cmi5_auth})
        expect(cmi5_read, 200, "cmi5 registration statement read")
        statement_ids = {row.get("id") for row in cmi5_read.json().get("statements", [])}
        if completion_id not in statement_ids or statement_id in statement_ids:
            raise RuntimeError("cmi5 credentials did not remain scoped to the learner registration.")

        expect(client.get("/__smoke/xapi-user/observer"), 200, "observer session")
        expect(client.get(f"/learn/cmi5/{au_id}/launch"), 403, "observer cmi5 launch protection")
        expect(client.get(f"/faculty/studio/courses/{course_id}/xapi"), 403, "observer xAPI management protection")

        expect(client.get("/__smoke/xapi-user/student"), 200, "student return session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/xapi"), 403, "student xAPI management protection")

    print("xAPI & cmi5 v1 validated: course-scoped source credentials, statement read/write, cmi5 launch/fetch replay protection, state persistence, pseudonymous learner binding, MoveOn progress, Gradebook synchronization, and role protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
