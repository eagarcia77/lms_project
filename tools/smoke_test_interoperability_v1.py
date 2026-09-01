from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-interoperability-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "interop-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "interop-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "interop.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Interop-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Interop Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/interop-user/{kind}", include_in_schema=False)
async def smoke_interop_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "interop-instructor", "name": "Interop Instructor", "email": "interop.instructor@example.com"},
        "student": {"id": "interop-student", "name": "Interop Student", "email": "interop.student@example.com"},
        "observer": {"id": "interop-observer", "name": "Interop Observer", "email": "interop.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported interoperability smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def scorm_zip() -> bytes:
    manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="nuvedra-smoke" xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2">
  <metadata><schema>ADL SCORM</schema><schemaversion>1.2</schemaversion></metadata>
  <organizations default="ORG1"><organization identifier="ORG1"><title>NUVEDRA SCORM Smoke</title><item identifier="ITEM1" identifierref="RES1"><title>Lesson</title></item></organization></organizations>
  <resources><resource identifier="RES1" type="webcontent" href="./index.html"><file href="index.html"/></resource></resources>
</manifest>'''
    lesson = '''<!doctype html><html><body><h1>NUVEDRA SCORM Smoke Lesson</h1><script>if(window.parent.API){window.parent.API.LMSInitialize('');}</script></body></html>'''
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("imsmanifest.xml", manifest)
        archive.writestr("index.html", lesson)
    return stream.getvalue()


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "interop.admin@example.com", "password": "Initial-Interop-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Interop-2026!", "confirm": "Updated-Interop-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "INTOP-6100", "title": "Learning Interoperability", "description": "SCORM and LTI functional validation.",
            "term": "Fall 2026", "instructor_email": "interop.instructor@example.com", "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (("interop.student@example.com", "student"), ("interop.observer@example.com", "observer")):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, email, role, "active", now))
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "Interop Module", "External learning resources.", "Use interoperable learning resources.", 45, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)))[0]["id"])

        expect(client.get("/__smoke/interop-user/instructor"), 200, "instructor session")
        home = client.get(f"/faculty/studio/courses/{course_id}/interoperability")
        expect(home, 200, "interoperability workspace")
        require(home, 'data-testid="interoperability-v1"', "interoperability workspace")
        require(home, "LTI 1.3 / Advantage is not claimed in v1", "LTI scope disclosure")

        uploaded = client.post(
            f"/faculty/studio/courses/{course_id}/interop/scorm",
            data={"module_id": str(module_id), "title": "SCORM Evidence Lesson"},
            files={"package": ("lesson.zip", scorm_zip(), "application/zip")},
        )
        expect(uploaded, 303, "SCORM upload")
        with db() as conn:
            packages = rows(execute(conn, "SELECT * FROM nuvedra_scorm_packages WHERE course_id=?", (course_id,)))
            if len(packages) != 1:
                raise RuntimeError("SCORM package was not stored.")
            package_id = int(packages[0]["id"])
            scorm_item_id = int(packages[0]["item_id"])
            if str(packages[0].get("launch_path")) != "index.html" or str(packages[0].get("version")) != "1.2":
                raise RuntimeError(f"SCORM manifest parsing failed: {packages[0]}")
            item = rows(execute(conn, "SELECT item_type,external_url,status FROM nexus_content_items WHERE id=?", (scorm_item_id,)))[0]
            if item.get("item_type") != "scorm" or item.get("external_url") != f"/learn/scorm/{package_id}":
                raise RuntimeError(f"SCORM content item was not linked to its launch route: {item}")
        expect(client.post(f"/faculty/studio/interop/scorm/{package_id}/toggle"), 303, "SCORM publish")

        lti_created = client.post(f"/faculty/studio/courses/{course_id}/interop/lti", data={
            "module_id": str(module_id), "title": "Legacy Research Tool", "launch_url": "https://example.com/lti",
            "consumer_key": "nuvedra-key", "shared_secret": "nuvedra-secret", "custom_parameters": "mode=research\ncohort=fall-2026",
        })
        expect(lti_created, 303, "LTI tool creation")
        with db() as conn:
            tools = rows(execute(conn, "SELECT * FROM nuvedra_lti_tools WHERE course_id=?", (course_id,)))
            if len(tools) != 1:
                raise RuntimeError("LTI tool was not stored.")
            tool_id = int(tools[0]["id"])
            lti_item_id = int(tools[0]["item_id"])
            item = rows(execute(conn, "SELECT item_type,external_url,status FROM nexus_content_items WHERE id=?", (lti_item_id,)))[0]
            if item.get("item_type") != "lti" or item.get("external_url") != f"/learn/lti/{tool_id}/launch":
                raise RuntimeError(f"LTI content item was not linked to its launch route: {item}")
        expect(client.post(f"/faculty/studio/interop/lti/{tool_id}/toggle"), 303, "LTI publish")

        expect(client.get("/__smoke/interop-user/student"), 200, "student session")
        scorm_redirect = client.get(f"/learn/items/{scorm_item_id}")
        expect(scorm_redirect, 303, "SCORM item redirect")
        if scorm_redirect.headers.get("location") != f"/learn/scorm/{package_id}":
            raise RuntimeError(f"SCORM item redirect target is wrong: {scorm_redirect.headers.get('location')}")
        launch = client.get(f"/learn/scorm/{package_id}")
        expect(launch, 200, "SCORM launch wrapper")
        require(launch, "window.API=", "SCORM 1.2 API")
        require(launch, "window.API_1484_11=", "SCORM 2004 API")
        asset = client.get(f"/learn/scorm/{package_id}/asset/index.html")
        expect(asset, 200, "SCORM launch asset")
        require(asset, "NUVEDRA SCORM Smoke Lesson", "SCORM asset content")
        state = client.post(f"/learn/scorm/{package_id}/state", data={
            "completion": "completed", "success": "passed", "score_raw": "88", "score_min": "0", "score_max": "100",
            "location": "lesson-1", "suspend_data": "checkpoint", "total_time": "00:12:30",
        })
        expect(state, 204, "SCORM state commit")
        with db() as conn:
            saved = rows(execute(conn, "SELECT * FROM nuvedra_scorm_states WHERE package_id=? AND lower(student_email)=?", (package_id, "interop.student@example.com")))
            if len(saved) != 1 or float(saved[0].get("score_raw") or 0) != 88 or saved[0].get("completion_status") != "completed":
                raise RuntimeError(f"SCORM learner state was not stored correctly: {saved}")
            progress = rows(execute(conn, "SELECT status FROM nuvedra_content_progress WHERE item_id=? AND lower(student_email)=?", (scorm_item_id, "interop.student@example.com")))
            if not progress or progress[0].get("status") != "completed":
                raise RuntimeError(f"SCORM completion did not synchronize to course progress: {progress}")

        lti_item = client.get(f"/learn/items/{lti_item_id}")
        expect(lti_item, 200, "LTI student item")
        require(lti_item, f"/learn/lti/{tool_id}/launch", "LTI student launch link")
        lti_launch = client.get(f"/learn/lti/{tool_id}/launch")
        expect(lti_launch, 200, "LTI launch form")
        require(lti_launch, 'name="oauth_signature"', "LTI OAuth signature")
        require(lti_launch, 'name="roles" value="Learner"', "LTI learner role")
        require(lti_launch, 'name="custom_mode" value="research"', "LTI custom parameter")
        if "interop.student@example.com" in lti_launch.text:
            raise RuntimeError("LTI launch leaked learner email while email sharing was disabled.")
        expect(client.post(f"/learn/items/{lti_item_id}/complete", data={"completed": "1"}), 303, "manual LTI completion")

        expect(client.get("/__smoke/interop-user/observer"), 200, "observer session")
        observer_launch = client.get(f"/learn/lti/{tool_id}/launch")
        expect(observer_launch, 200, "observer LTI launch")
        require(observer_launch, 'name="roles" value="Observer"', "LTI observer role")
        expect(client.get(f"/faculty/studio/courses/{course_id}/interoperability"), 403, "observer instructor-tool protection")

        expect(client.get("/__smoke/interop-user/student"), 200, "student return session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/interoperability"), 403, "student instructor-tool protection")

    print("SCORM & LTI v1 validated: SCORM 1.2 manifest discovery, secure database-backed launch assets, runtime state/progress sync, LTI 1.1 signed launch, privacy controls, manual LTI completion, and role protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
