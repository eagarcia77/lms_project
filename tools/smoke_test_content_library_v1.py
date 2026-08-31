from __future__ import annotations

import json
import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-content-library-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "content-library-session-secret-at-least-thirty-two"
os.environ["NEXUS_SESSION_SECRET"] = "content-library-admin-secret-at-least-thirty-two"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "library.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Library-V1-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Library Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/library-user/{kind}", include_in_schema=False)
async def smoke_library_user(kind: str, request: Request):
    if kind == "student":
        request.session["user"] = {"id": "library-student", "name": "Library Student", "email": "library.student@example.com"}
    elif kind == "stranger":
        request.session["user"] = {"id": "library-stranger", "name": "Library Stranger", "email": "library.stranger@example.com"}
    elif kind == "admin":
        request.session.pop("user", None)
    else:
        raise RuntimeError("Unsupported Content Library smoke user.")
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1200]}")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "library.admin@example.com", "password": "Initial-Library-V1-2026!"}), 303, "administrator login")
        expect(client.post("/admin/password", data={"password": "Updated-Library-V1-2026!", "confirm": "Updated-Library-V1-2026!"}), 303, "administrator password update")

        created = client.post("/admin/authoring/courses", data={
            "course_code": "LIB-1001", "title": "Content Library Course", "description": "Reusable resource validation.",
            "term": "Fall 2026", "instructor_email": "library.admin@example.com", "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])

        expect(client.post(f"/faculty/studio/courses/{course_id}/modules", data={
            "title": "Library Module", "description": "Reusable resources.", "learning_outcomes": "Use a library resource.", "estimated_minutes": "30",
        }), 303, "module creation")
        with db() as conn:
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,)))[0]["id"])

        library = client.get(f"/faculty/library?course_id={course_id}")
        expect(library, 200, "Content Library")
        for marker in ('data-testid="content-library-v1"', "Reusable teaching resources", "Save to library"):
            if marker not in library.text:
                raise RuntimeError(f"Content Library did not show {marker!r}.")

        missing_alt = client.post("/faculty/library/assets", data={
            "name": "Image without alt text", "asset_type": "image", "description": "Should fail.", "accessibility_text": "", "tags": "test", "source_url": "https://example.com/image.png",
        })
        expect(missing_alt, 400, "accessibility requirement")

        uploaded = client.post(
            "/faculty/library/assets",
            data={"name": "Accessible Course Guide", "asset_type": "pdf", "description": "Reusable PDF guide.", "accessibility_text": "Tagged PDF with equivalent text.", "tags": "guide, accessibility", "source_url": ""},
            files={"upload": ("course-guide.pdf", b"%PDF-1.4\nNUVEDRA CONTENT LIBRARY TEST\n", "application/pdf")},
        )
        expect(uploaded, 303, "library file upload")

        with db() as conn:
            assets = rows(execute(conn, "SELECT * FROM nuvedra_library_assets WHERE lower(owner_email)='library.admin@example.com' AND name='Accessible Course Guide'"))
            if not assets:
                raise RuntimeError("Uploaded Content Library asset was not stored.")
            asset = assets[0]
            asset_id = int(asset["id"])
            if int(asset.get("file_size") or 0) <= 0 or asset.get("file_bytes") is None:
                raise RuntimeError("Uploaded Content Library bytes were not stored.")

        attached = client.post(f"/faculty/library/assets/{asset_id}/attach", data={"module_id": str(module_id)})
        expect(attached, 303, "attach library asset")
        with db() as conn:
            uses = rows(execute(conn, "SELECT * FROM nuvedra_library_uses WHERE asset_id=? AND module_id=?", (asset_id, module_id)))
            if not uses:
                raise RuntimeError("Content Library reuse record was not created.")
            item_id = int(uses[0]["item_id"])
            item = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE id=?", (item_id,)))[0]
            meta = json.loads(str(item.get("metadata_json") or "{}"))
            if int(meta.get("library_asset_id") or 0) != asset_id or meta.get("source") != "nuvedra_content_library":
                raise RuntimeError("Course item did not preserve Content Library metadata.")
            if str(item.get("external_url")) != f"/library/assets/{asset_id}/download":
                raise RuntimeError("Uploaded library item did not use the protected download route.")

        expect(client.post(f"/faculty/studio/modules/{module_id}/update", data={
            "title": "Library Module", "description": "Reusable resources.", "learning_outcomes": "Use a library resource.", "estimated_minutes": "30", "position": "1", "status": "published",
        }), 303, "module publishing")
        expect(client.post(f"/faculty/studio/items/{item_id}/edit", data={
            "item_type": "pdf", "title": "Accessible Course Guide", "body_html": "<p>Reusable PDF guide.</p>",
            "external_url": f"/library/assets/{asset_id}/download", "embed_url": "", "points": "", "due_at": "", "position": "1", "status": "published",
            "accessible_alternative": "Tagged PDF with equivalent text.", "assessment_response_type": "text", "attempts": "1", "time_limit": "0", "rubric": "",
        }), 303, "library item publishing")

        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (utcnow(), course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "library.student@example.com", "student", "active", utcnow()))

        expect(client.get("/__smoke/library-user/student"), 200, "student session")
        course = client.get(f"/learn/courses/{course_id}")
        expect(course, 200, "student course")
        if "Accessible Course Guide" not in course.text:
            raise RuntimeError("Reused Content Library asset did not appear in the student course.")
        download = client.get(f"/library/assets/{asset_id}/download")
        expect(download, 200, "protected student download")
        if not download.content.startswith(b"%PDF-1.4"):
            raise RuntimeError("Protected Content Library download returned unexpected bytes.")
        if "application/pdf" not in str(download.headers.get("content-type") or ""):
            raise RuntimeError("Protected Content Library download did not preserve the PDF content type.")

        expect(client.get("/__smoke/library-user/stranger"), 200, "stranger session")
        expect(client.get(f"/library/assets/{asset_id}/download"), 403, "unrelated user download protection")

        expect(client.get("/__smoke/library-user/admin"), 200, "administrator-instructor session")
        expect(client.post(f"/faculty/library/assets/{asset_id}/archive"), 303, "archive library asset")
        expect(client.get(f"/library/assets/{asset_id}/download"), 200, "owner archived asset access")

    print("Content Library v1 validated: upload, accessibility requirement, reusable course attachment, protected student download, unauthorized-user denial, and archive behavior.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
