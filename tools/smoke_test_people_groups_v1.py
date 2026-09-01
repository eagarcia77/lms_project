from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-people-groups-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "people-groups-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "people-groups-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "groups.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Groups-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Groups Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/people-groups-user/{kind}", include_in_schema=False)
async def smoke_people_groups_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "groups-instructor", "name": "Groups Instructor", "email": "groups.instructor@example.com"},
        "student1": {"id": "groups-student-1", "name": "Student One", "email": "student.one@example.com"},
        "student2": {"id": "groups-student-2", "name": "Student Two", "email": "student.two@example.com"},
        "student3": {"id": "groups-student-3", "name": "Student Three", "email": "student.three@example.com"},
        "observer": {"id": "groups-observer", "name": "Observer", "email": "observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported People & Groups smoke user.")
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
        expect(client.post("/admin/login", data={"email": "groups.admin@example.com", "password": "Initial-Groups-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Groups-2026!", "confirm": "Updated-Groups-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "GROUP-5100",
            "title": "Collaborative Learning",
            "description": "People and Groups functional validation.",
            "term": "Fall 2026",
            "instructor_email": "groups.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (
                ("student.one@example.com", "student"),
                ("student.two@example.com", "student"),
                ("student.three@example.com", "student"),
                ("observer@example.com", "observer"),
            ):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                        (course_id, email, role, "active", now))
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (course_id, "Team Module", "Collaborative work.", "Collaborate effectively.", 60, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)))[0]["id"])
            execute(conn, """INSERT INTO nexus_content_items
                (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (module_id, "assignment", "Team Evidence Review", "<p>Review the evidence with your group.</p>", "", "", "{}", 100,
                 "2026-09-30T23:59", 1, "published", now, now))
            item_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=?", (module_id,)))[0]["id"])

        expect(client.get("/__smoke/people-groups-user/instructor"), 200, "instructor session")
        home = client.get(f"/faculty/studio/courses/{course_id}/people")
        expect(home, 200, "people and groups home")
        require(home, 'data-testid="people-groups-v1"', "people and groups home")
        require(home, "Enrollment and course-role changes remain administrator responsibilities", "role separation notice")
        require(home, "student.three@example.com", "course roster")

        created_group = client.post(f"/faculty/studio/courses/{course_id}/groups", data={
            "name": "Team Alpha",
            "description": "Private evidence-review team.",
        })
        expect(created_group, 303, "group creation")
        group_id = int(created_group.headers["location"].rsplit("/", 1)[-1])

        expect(client.post(f"/faculty/studio/groups/{group_id}/members",
                           data={"student_email": "student.one@example.com", "member_role": "leader"}), 303, "add leader")
        expect(client.post(f"/faculty/studio/groups/{group_id}/members",
                           data={"student_email": "student.two@example.com", "member_role": "member"}), 303, "add member")
        expect(client.post(f"/faculty/studio/groups/{group_id}/activities",
                           data={"item_id": str(item_id)}), 303, "assign group activity")

        group_admin = client.get(f"/faculty/studio/groups/{group_id}")
        expect(group_admin, 200, "group management")
        require(group_admin, "Team Alpha", "group management")
        require(group_admin, "Team Evidence Review", "group activity listing")
        require(group_admin, "Submissions and grades remain individual records in v1", "group assignment scope notice")

        with db() as conn:
            links = rows(execute(conn, "SELECT * FROM nuvedra_group_item_links WHERE group_id=? AND item_id=?", (group_id, item_id)))
            if len(links) != 1:
                raise RuntimeError("The assignment was not linked to Team Alpha.")
            member_notifications = rows(execute(conn, """SELECT recipient_email,kind FROM nuvedra_notifications
                WHERE course_id=? AND kind='group' ORDER BY recipient_email,id""", (course_id,)))
            recipients = {str(row.get("recipient_email") or "") for row in member_notifications}
            if not {"student.one@example.com", "student.two@example.com"}.issubset(recipients):
                raise RuntimeError(f"Group notifications were not created for members: {member_notifications}")

        expect(client.get("/__smoke/people-groups-user/student1"), 200, "student one session")
        groups_home = client.get("/learn/groups")
        expect(groups_home, 200, "student groups dashboard")
        require(groups_home, "Team Alpha", "student groups dashboard")
        group_space = client.get(f"/learn/groups/{group_id}")
        expect(group_space, 200, "student group space")
        require(group_space, 'data-testid="student-group-space-v1"', "student group space")
        require(group_space, "Team Evidence Review", "student group activity")
        member_assignment = client.get(f"/learn/assignments/{item_id}")
        expect(member_assignment, 200, "member assignment access")
        require(member_assignment, "Group activity", "member assignment group notice")
        require(member_assignment, "Team Alpha", "member assignment group name")
        expect(client.post(f"/learn/groups/{group_id}/posts", data={"body": "I reviewed the first source and added notes."}), 303, "group post")

        expect(client.get("/__smoke/people-groups-user/student2"), 200, "student two session")
        group_after_post = client.get(f"/learn/groups/{group_id}")
        expect(group_after_post, 200, "second member group access")
        require(group_after_post, "I reviewed the first source and added notes.", "private group collaboration")
        with db() as conn:
            notifications = rows(execute(conn, """SELECT * FROM nuvedra_notifications
                WHERE recipient_email='student.two@example.com' AND kind='group'
                  AND message LIKE '%posted to your group%'"""))
            if not notifications:
                raise RuntimeError("A group post did not notify another group member.")

        expect(client.get("/__smoke/people-groups-user/student3"), 200, "outside student session")
        expect(client.get(f"/learn/groups/{group_id}"), 403, "outside student private-group protection")
        expect(client.get(f"/learn/assignments/{item_id}"), 403, "outside student group-assignment protection")
        expect(client.post(f"/learn/assignments/{item_id}/save",
                           data={"response_text": "Should be blocked.", "action": "submit"}), 403, "outside student group submission protection")

        expect(client.get("/__smoke/people-groups-user/observer"), 200, "observer session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/people"), 403, "observer instructor-tool protection")
        expect(client.get(f"/learn/groups/{group_id}"), 403, "observer private-group protection")

        expect(client.get("/__smoke/people-groups-user/instructor"), 200, "instructor return session")
        with db() as conn:
            member_two = rows(execute(conn, """SELECT id FROM nuvedra_group_members
                WHERE group_id=? AND lower(user_email)='student.two@example.com'""", (group_id,)))
            if not member_two:
                raise RuntimeError("Second group member disappeared before removal validation.")
            member_two_id = int(member_two[0]["id"])
        expect(client.post(f"/faculty/studio/groups/{group_id}/members/{member_two_id}/remove"), 303, "remove group member")

        expect(client.get("/__smoke/people-groups-user/student2"), 200, "removed student session")
        expect(client.get(f"/learn/groups/{group_id}"), 403, "removed member private-group protection")
        expect(client.get(f"/learn/assignments/{item_id}"), 403, "removed member group-assignment protection")

    print("People & Groups v1 validated: roster role separation, group creation, student membership, targeted assignment access, private collaboration, notifications, removal enforcement, and observer protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
