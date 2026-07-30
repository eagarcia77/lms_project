from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-platform-upgrade-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "platform-upgrade-session-secret-at-least-thirty-two"
os.environ["NEXUS_SESSION_SECRET"] = "platform-upgrade-admin-secret-at-least-thirty-two"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "admin.instructor@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Platform-Password-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Admin Instructor"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows  # noqa: E402
from app.production_entry import app  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(
            f"{label}: expected {status}, received {response.status_code}: {response.text[:900]}"
        )


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        login_page = client.get("/login")
        expect(login_page, 200, "bilingual public login")
        if '/static/i18n.js' not in login_page.text or '<html lang="en">' not in login_page.text:
            raise RuntimeError("The public login did not load the English-first language layer.")

        i18n = client.get("/static/i18n.js")
        expect(i18n, 200, "language asset")
        for marker in ('DEFAULT_LANGUAGE = "en"', '"Español"', 'nuvedra.language'):
            if marker not in i18n.text:
                raise RuntimeError(f"The language asset did not include {marker!r}.")

        login = client.post(
            "/admin/login",
            data={
                "email": "admin.instructor@example.com",
                "password": "Initial-Platform-Password-2026!",
            },
        )
        expect(login, 303, "administrator login")
        password = client.post(
            "/admin/password",
            data={
                "password": "Updated-Platform-Password-2026!",
                "confirm": "Updated-Platform-Password-2026!",
            },
        )
        expect(password, 303, "administrator password change")

        workspace = client.get("/admin/authoring")
        expect(workspace, 200, "course administration workspace")
        if '/static/i18n.js' not in workspace.text:
            raise RuntimeError("The administration workspace did not load the language switcher.")
        if 'value="admin.instructor@example.com"' not in workspace.text:
            raise RuntimeError("The administrator email was not offered as the default instructor.")

        created = client.post(
            "/admin/authoring/courses",
            data={
                "course_code": "ADMIN-TEACH-1001",
                "title": "Administrator as Instructor",
                "description": "Role separation with an administrator who also teaches.",
                "term": "Fall 2026",
                "instructor_email": "",
                "template": "blank",
            },
        )
        expect(created, 303, "course creation with administrator as instructor")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])

        with db() as conn:
            enrollment = rows(
                execute(
                    conn,
                    """SELECT course_role,status FROM nexus_admin_enrollments
                       WHERE course_id=? AND lower(user_email)=?""",
                    (course_id, "admin.instructor@example.com"),
                )
            )
        if not enrollment or enrollment[0]["course_role"] != "instructor" or enrollment[0]["status"] != "active":
            raise RuntimeError("The administrator was not enrolled as an active instructor.")

        portal = client.get("/portal")
        expect(portal, 200, "administrator academic portal")
        if "Administrator as Instructor" not in portal.text or f'/faculty/courses/{course_id}' not in portal.text:
            raise RuntimeError("The administrator could not see the assigned instructor workspace.")

        faculty = client.get(f"/faculty/courses/{course_id}")
        expect(faculty, 200, "administrator using instructor tools")

        module = client.post(
            f"/faculty/courses/{course_id}/modules",
            data={
                "title": "Instructor Module",
                "description": "Created through the simplified instructor workflow.",
                "learning_outcomes": "Create and publish accessible course content.",
                "estimated_minutes": "60",
                "position": "1",
            },
        )
        expect(module, 303, "module creation by administrator-instructor")

        with db() as conn:
            module_rows = rows(
                execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? ORDER BY id DESC LIMIT 1", (course_id,))
            )
        if not module_rows:
            raise RuntimeError("The instructor module was not saved.")
        module_id = int(module_rows[0]["id"])

        drive = client.get(f"/admin/authoring/modules/{module_id}/drive")
        expect(drive, 200, "safe Google Hub without OAuth")
        if "Google Hub sencillo" not in drive.text or "pegar enlace compartido" not in drive.text:
            raise RuntimeError("The safe Google Hub did not display the shared-link workflow.")

    print(
        "Platform upgrade validated: English-first language switch, safe Google Hub, and administrator-instructor workflow.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
