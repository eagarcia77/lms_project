from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-discussions-collaboration-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "discussions-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "discussions-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "discussion.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Discussion-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Discussion Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/discussion-user/{kind}", include_in_schema=False)
async def smoke_discussion_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "discussion-instructor", "name": "Discussion Instructor", "email": "discussion.instructor@example.com"},
        "student": {"id": "discussion-student", "name": "Discussion Student", "email": "discussion.student@example.com"},
        "observer": {"id": "discussion-observer", "name": "Discussion Observer", "email": "discussion.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported discussion smoke user.")
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
        expect(client.post("/admin/login", data={"email": "discussion.admin@example.com", "password": "Initial-Discussion-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Discussion-2026!", "confirm": "Updated-Discussion-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "DISC-4100",
            "title": "Discussions and Collaboration v1",
            "description": "Threaded discussion validation.",
            "term": "Fall 2026",
            "instructor_email": "discussion.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "discussion.student@example.com", "student", "active", now))
            execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, "discussion.observer@example.com", "observer", "active", now))
            execute(conn, "INSERT INTO nexus_modules (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (course_id, "Discussion Module", "Published collaboration module.", "Develop evidence-based dialogue.", 45, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=? AND title=?", (course_id, "Discussion Module")))[0]["id"])
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (module_id, "discussion", "Evidence-based Collaboration", "<p>Post an evidence-based response and engage respectfully with peers.</p>", "", "", "{}", 20, "2026-12-15T23:59", 1, "published", now, now))
            item_id = int(rows(execute(conn, "SELECT id FROM nexus_content_items WHERE module_id=? AND title=?", (module_id, "Evidence-based Collaboration")))[0]["id"])

        expect(client.get("/__smoke/discussion-user/instructor"), 200, "instructor session")
        index = client.get(f"/faculty/studio/courses/{course_id}/discussions")
        expect(index, 200, "instructor discussion index")
        require(index, 'data-testid="course-discussions-v1"', "instructor discussion index")
        require(index, "Evidence-based Collaboration", "instructor discussion index")
        moderation = client.get(f"/faculty/studio/discussions/{item_id}")
        expect(moderation, 200, "instructor discussion moderation")
        require(moderation, 'data-testid="instructor-discussion-v1"', "instructor discussion moderation")

        expect(client.get("/__smoke/discussion-user/student"), 200, "student session")
        course_page = client.get(f"/learn/courses/{course_id}")
        expect(course_page, 200, "student course")
        require(course_page, f'/learn/discussions/{item_id}', "student course discussion link")
        discussion = client.get(f"/learn/discussions/{item_id}")
        expect(discussion, 200, "student discussion")
        require(discussion, 'data-testid="student-discussion-v1"', "student discussion")
        require(discussion, "Your initial contribution", "student initial contribution")
        initial = client.post(f"/learn/discussions/{item_id}/post", data={"parent_id": "", "body": "My initial evidence-based contribution."})
        expect(initial, 303, "student initial discussion post")
        with db() as conn:
            student_posts = rows(execute(conn, "SELECT id,parent_id FROM nuvedra_discussion_posts WHERE item_id=? AND lower(author_email)=? ORDER BY id", (item_id, "discussion.student@example.com")))
            if len(student_posts) != 1 or student_posts[0].get("parent_id") is not None:
                raise RuntimeError("Student initial discussion contribution was not stored correctly.")
            initial_post_id = int(student_posts[0]["id"])
            submissions = rows(execute(conn, "SELECT id,response_text,status FROM nuvedra_submissions WHERE item_id=? AND lower(student_email)=?", (item_id, "discussion.student@example.com")))
            if len(submissions) != 1 or submissions[0].get("status") != "submitted":
                raise RuntimeError("Initial discussion contribution was not linked to Gradebook submissions.")
            instructor_notices = rows(execute(conn, "SELECT id FROM nuvedra_notifications WHERE recipient_email=? AND course_id=? AND kind='discussion'", ("discussion.instructor@example.com", course_id)))
            if not instructor_notices:
                raise RuntimeError("Instructor did not receive an in-app discussion notification.")

        expect(client.get("/__smoke/discussion-user/instructor"), 200, "instructor session for reply")
        instructor_reply = client.post(f"/faculty/studio/discussions/{item_id}/reply", data={"parent_id": str(initial_post_id), "body": "Instructor follow-up question."})
        expect(instructor_reply, 303, "instructor threaded reply")
        with db() as conn:
            replies = rows(execute(conn, "SELECT id,parent_id FROM nuvedra_discussion_posts WHERE item_id=? AND lower(author_email)=? ORDER BY id", (item_id, "discussion.instructor@example.com")))
            if len(replies) != 1 or int(replies[0].get("parent_id") or 0) != initial_post_id:
                raise RuntimeError("Instructor threaded reply was not stored correctly.")
            instructor_reply_id = int(replies[0]["id"])
            learner_notices = rows(execute(conn, "SELECT recipient_email FROM nuvedra_notifications WHERE course_id=? AND kind='discussion' AND title LIKE 'Discussion update:%'", (course_id,)))
            recipients = {str(row.get("recipient_email") or "") for row in learner_notices}
            if {"discussion.student@example.com", "discussion.observer@example.com"} - recipients:
                raise RuntimeError("Instructor discussion reply did not notify active learners and observers.")

        gradebook = client.get(f"/faculty/studio/courses/{course_id}/gradebook")
        expect(gradebook, 200, "discussion Gradebook integration")
        require(gradebook, "discussion.student@example.com", "discussion Gradebook integration")
        require(gradebook, "Evidence-based Collaboration", "discussion Gradebook integration")

        expect(client.post(f"/faculty/studio/discussions/{item_id}/state", data={"state": "closed"}), 303, "close discussion")
        expect(client.get("/__smoke/discussion-user/student"), 200, "student session closed discussion")
        closed = client.post(f"/learn/discussions/{item_id}/post", data={"parent_id": str(instructor_reply_id), "body": "This reply should be blocked while closed."})
        expect(closed, 409, "closed discussion protection")

        expect(client.get("/__smoke/discussion-user/instructor"), 200, "instructor session reopen discussion")
        expect(client.post(f"/faculty/studio/discussions/{item_id}/state", data={"state": "open"}), 303, "reopen discussion")
        expect(client.get("/__smoke/discussion-user/student"), 200, "student session threaded reply")
        reply = client.post(f"/learn/discussions/{item_id}/post", data={"parent_id": str(instructor_reply_id), "body": "Student threaded response after reopening."})
        expect(reply, 303, "student threaded reply")

        notifications = client.get("/portal/notifications")
        expect(notifications, 200, "discussion notification center")
        require(notifications, "Discussion update: Evidence-based Collaboration", "discussion notification center")

        expect(client.get("/__smoke/discussion-user/observer"), 200, "observer session")
        observer_page = client.get(f"/learn/discussions/{item_id}")
        expect(observer_page, 200, "observer discussion read access")
        require(observer_page, "Observers can read this discussion but cannot participate.", "observer read-only notice")
        observer_post = client.post(f"/learn/discussions/{item_id}/post", data={"parent_id": "", "body": "Observers cannot post."})
        expect(observer_post, 403, "observer discussion post protection")
        instructor_admin = client.get(f"/faculty/studio/discussions/{item_id}")
        expect(instructor_admin, 403, "observer instructor-discussion protection")

    print("Discussions & Collaboration v1 validated: student initial posts, threaded replies, instructor participation, close/reopen controls, notifications, observer read-only access, and Gradebook linkage.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
