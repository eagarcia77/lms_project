from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-attendance-participation-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "attendance-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "attendance-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "attendance.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Attendance-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Attendance Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.attendance_participation import attendance_summary_for_student  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/attendance-user/{kind}", include_in_schema=False)
async def smoke_attendance_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "attendance-instructor", "name": "Attendance Instructor", "email": "attendance.instructor@example.com"},
        "student1": {"id": "attendance-student-1", "name": "Student One", "email": "attendance.student1@example.com"},
        "student2": {"id": "attendance-student-2", "name": "Student Two", "email": "attendance.student2@example.com"},
        "observer": {"id": "attendance-observer", "name": "Observer", "email": "attendance.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported Attendance smoke user.")
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
        expect(client.post("/admin/login", data={"email": "attendance.admin@example.com", "password": "Initial-Attendance-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Attendance-2026!", "confirm": "Updated-Attendance-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "ATT-6100",
            "title": "Attendance Validation",
            "description": "Attendance and participation functional validation.",
            "term": "Fall 2026",
            "instructor_email": "attendance.instructor@example.com",
            "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (
                ("attendance.student1@example.com", "student"),
                ("attendance.student2@example.com", "student"),
                ("attendance.observer@example.com", "observer"),
            ):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)",
                        (course_id, email, role, "active", now))

        expect(client.get("/__smoke/attendance-user/instructor"), 200, "instructor session")
        home = client.get(f"/faculty/studio/courses/{course_id}/attendance")
        expect(home, 200, "attendance home")
        require(home, 'data-testid="attendance-participation-v1"', "attendance home")
        require(home, "Excused sessions are excluded", "attendance calculation notice")

        first = client.post(f"/faculty/studio/courses/{course_id}/attendance/sessions", data={
            "title": "Class Meeting 1",
            "session_date": "2026-09-01",
            "notes": "Opening seminar",
        })
        expect(first, 303, "first attendance session")
        session1 = int(first.headers["location"].rsplit("/", 1)[-1])
        with db() as conn:
            records = rows(execute(conn, "SELECT id,student_email FROM nuvedra_attendance_records WHERE session_id=? ORDER BY student_email", (session1,)))
            record_ids = {str(row["student_email"]): int(row["id"]) for row in records}
        expect(client.post(f"/faculty/studio/attendance/sessions/{session1}/records/{record_ids['attendance.student1@example.com']}", data={"status": "present", "minutes_late": "0", "note": "On time"}), 303, "student one present")
        expect(client.post(f"/faculty/studio/attendance/sessions/{session1}/records/{record_ids['attendance.student2@example.com']}", data={"status": "absent", "minutes_late": "0", "note": "No attendance"}), 303, "student two absent")

        second = client.post(f"/faculty/studio/courses/{course_id}/attendance/sessions", data={
            "title": "Class Meeting 2",
            "session_date": "2026-09-02",
            "notes": "Case workshop",
        })
        expect(second, 303, "second attendance session")
        session2 = int(second.headers["location"].rsplit("/", 1)[-1])
        with db() as conn:
            records = rows(execute(conn, "SELECT id,student_email FROM nuvedra_attendance_records WHERE session_id=? ORDER BY student_email", (session2,)))
            record_ids = {str(row["student_email"]): int(row["id"]) for row in records}
        expect(client.post(f"/faculty/studio/attendance/sessions/{session2}/records/{record_ids['attendance.student1@example.com']}", data={"status": "late", "minutes_late": "12", "note": "Arrived after opening"}), 303, "student one late")
        expect(client.post(f"/faculty/studio/attendance/sessions/{session2}/records/{record_ids['attendance.student2@example.com']}", data={"status": "excused", "minutes_late": "0", "note": "Approved excuse"}), 303, "student two excused")

        expect(client.post(f"/faculty/studio/courses/{course_id}/participation", data={
            "student_email": "attendance.student1@example.com", "category": "discussion", "points": "3.5", "note": "Connected two readings during discussion."
        }), 303, "student one participation")
        expect(client.post(f"/faculty/studio/courses/{course_id}/participation", data={
            "student_email": "attendance.student2@example.com", "category": "teamwork", "points": "1.0", "note": "Contributed to team planning."
        }), 303, "student two participation")

        with db() as conn:
            summary1 = attendance_summary_for_student(conn, course_id, "attendance.student1@example.com")
            summary2 = attendance_summary_for_student(conn, course_id, "attendance.student2@example.com")
        if summary1["attendance_rate"] != 100.0 or summary1["present"] != 1 or summary1["late"] != 1 or summary1["participation_points"] != 3.5:
            raise RuntimeError(f"Student one attendance summary is incorrect: {summary1}")
        if summary2["attendance_rate"] != 0.0 or summary2["absent"] != 1 or summary2["excused"] != 1 or summary2["participation_points"] != 1.0:
            raise RuntimeError(f"Student two attendance summary is incorrect: {summary2}")

        summary_page = client.get(f"/faculty/studio/courses/{course_id}/attendance")
        expect(summary_page, 200, "attendance summary page")
        require(summary_page, "100.0%", "student one attendance rate")
        require(summary_page, "3.5", "participation points")

        analytics = client.get(f"/faculty/studio/courses/{course_id}/analytics")
        expect(analytics, 200, "learning analytics integration")
        require(analytics, "Attendance & Participation", "analytics attendance action")
        require(analytics, "100.0%", "analytics attendance rate")
        require(analytics, "3.5", "analytics participation metric")

        csv_export = client.get(f"/faculty/studio/courses/{course_id}/attendance.csv")
        expect(csv_export, 200, "attendance CSV export")
        require(csv_export, "Attendance rate percent", "attendance CSV header")
        require(csv_export, "attendance.student1@example.com", "attendance CSV student")

        expect(client.get("/__smoke/attendance-user/student1"), 200, "student one session")
        student_home = client.get("/learn/attendance")
        expect(student_home, 200, "student attendance home")
        require(student_home, 'data-testid="student-attendance-v1"', "student attendance home")
        details = client.get(f"/learn/courses/{course_id}/attendance")
        expect(details, 200, "student attendance details")
        require(details, "Opening seminar", "student attendance history")
        require(details, "Connected two readings", "student participation evidence")
        if "attendance.student2@example.com" in details.text:
            raise RuntimeError("Student attendance view leaked another student's record.")
        expect(client.get(f"/faculty/studio/courses/{course_id}/attendance"), 403, "student instructor-tool protection")

        expect(client.get("/__smoke/attendance-user/observer"), 200, "observer session")
        expect(client.get("/learn/attendance"), 200, "observer attendance landing")
        expect(client.get(f"/learn/courses/{course_id}/attendance"), 403, "observer private attendance protection")
        expect(client.get(f"/faculty/studio/courses/{course_id}/attendance"), 403, "observer instructor attendance protection")

    print("Attendance & Participation v1 validated: session creation, Present/Absent/Late/Excused records, excused-rate handling, participation evidence, CSV export, student privacy, observer protection, and Learning Analytics integration.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
