from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/attendance_participation_module.py.txt")
MODULE = Path("app/attendance_participation.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
LEARNING_ANALYTICS = Path("app/learning_analytics.py")
TAG = "NUVEDRA_ATTENDANCE_PARTICIPATION_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Attendance & Participation v1 could not find {label}: {old[:180]!r}")
    return text.replace(old, new, 1)


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.attendance_participation import register_attendance_participation\n"
    if import_line not in text:
        anchors = (
            "from app.people_groups import register_people_groups\n",
            "from app.course_copy_import import register_course_copy_import\n",
            "from app.learning_analytics import register_learning_analytics\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Attendance & Participation v1 could not locate an academic portal import anchor.")
    registration = "    register_attendance_participation(app)\n"
    if registration not in text:
        anchors = (
            "    register_people_groups(app)\n",
            "    register_course_copy_import(app)\n",
            "    register_learning_analytics(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Attendance & Participation v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_ATTENDANCE_PARTICIPATION_V1
  function initializeAttendanceParticipationLink() {
    const root = document.querySelector('[data-testid="visual-course-studio"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!root || !match || root.querySelector('[data-attendance-participation-link]')) return;
    const hero = root.querySelector('.studio-hero');
    if (!hero) return;
    let actions = hero.querySelector('.studio-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'studio-actions';
      hero.appendChild(actions);
    }
    const link = document.createElement('a');
    link.className = 'studio-button studio-button--quiet';
    link.href = `/faculty/studio/courses/${match[1]}/attendance`;
    link.dataset.attendanceParticipationLink = 'v1';
    link.dataset.i18nEn = 'Attendance';
    link.dataset.i18nEs = 'Asistencia';
    link.textContent = language() === 'es' ? 'Asistencia' : 'Attendance';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Attendance & Participation v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeAttendanceParticipationLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Attendance & Participation v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeAttendanceParticipationLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def patch_student_experience() -> None:
    if not STUDENT_EXPERIENCE.is_file():
        raise RuntimeError("Attendance & Participation v1 requires the generated Student Experience v2 module.")
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    old = '<nav class="studio-breadcrumbs"><a href="/portal" data-i18n-en="My courses" data-i18n-es="Mis cursos">My courses</a><span>/</span><a href="/learn/groups" data-i18n-en="My Groups" data-i18n-es="Mis grupos">My Groups</a></nav>'
    new = '<nav class="studio-breadcrumbs"><a href="/portal" data-i18n-en="My courses" data-i18n-es="Mis cursos">My courses</a><span>/</span><a href="/learn/groups" data-i18n-en="My Groups" data-i18n-es="Mis grupos">My Groups</a><span>/</span><a href="/learn/attendance" data-i18n-en="My Attendance" data-i18n-es="Mi asistencia">My Attendance</a></nav>'
    if new not in text:
        if old not in text:
            raise RuntimeError("Attendance & Participation v1 could not add My Attendance to the student dashboard.")
        text = text.replace(old, new, 1)
    STUDENT_EXPERIENCE.write_text(text, encoding="utf-8")


def patch_learning_analytics() -> None:
    if not LEARNING_ANALYTICS.is_file():
        raise RuntimeError("Attendance & Participation v1 requires the generated Learning Analytics v1 module.")
    text = LEARNING_ANALYTICS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from app.admin_console import db, execute, rows\n",
        "from app.admin_console import db, execute, rows\nfrom app.attendance_participation import attendance_summary_for_student\n",
        "Learning Analytics attendance import",
    )
    text = replace_once(
        text,
        "        submissions = _submission_count(conn, course_id, email)\n",
        "        submissions = _submission_count(conn, course_id, email)\n        attendance = attendance_summary_for_student(conn, course_id, email)\n",
        "Learning Analytics student attendance calculation",
    )
    text = replace_once(
        text,
        '            "submissions": submissions,\n            "grade_percent": grade_percent,\n',
        '            "submissions": submissions,\n            "attendance_rate": attendance["attendance_rate"],\n            "participation_points": attendance["participation_points"],\n            "grade_percent": grade_percent,\n',
        "Learning Analytics attendance metric fields",
    )
    text = replace_once(
        text,
        "<td>{int(row['submissions'])}</td><td>{academic_access.esc(grade_text)}</td>",
        "<td>{int(row['submissions'])}</td><td>{'—' if row['attendance_rate'] is None else f\"{float(row['attendance_rate']):.1f}%\"}</td><td>{float(row['participation_points']):.1f}</td><td>{academic_access.esc(grade_text)}</td>",
        "Learning Analytics attendance table values",
    )
    text = replace_once(
        text,
        '<tr><td colspan="6" data-i18n-en="No active students are enrolled yet."',
        '<tr><td colspan="8" data-i18n-en="No active students are enrolled yet."',
        "Learning Analytics empty-table colspan",
    )
    text = replace_once(
        text,
        '<th data-i18n-en="Submissions" data-i18n-es="Entregas">Submissions</th><th data-i18n-en="Graded score"',
        '<th data-i18n-en="Submissions" data-i18n-es="Entregas">Submissions</th><th data-i18n-en="Attendance" data-i18n-es="Asistencia">Attendance</th><th data-i18n-en="Participation" data-i18n-es="Participación">Participation</th><th data-i18n-en="Graded score"',
        "Learning Analytics attendance table headers",
    )
    text = replace_once(
        text,
        'href="{STUDIO_PREFIX}/courses/{course_id}/analytics.csv" data-i18n-en="Export CSV"',
        'href="{STUDIO_PREFIX}/courses/{course_id}/attendance" data-i18n-en="Attendance & Participation" data-i18n-es="Asistencia y participación">Attendance & Participation</a><a class="studio-button studio-button--quiet" href="{STUDIO_PREFIX}/courses/{course_id}/analytics.csv" data-i18n-en="Export CSV"',
        "Learning Analytics attendance action",
    )
    text = replace_once(
        text,
        'writer.writerow(["Student", "Progress percent", "Completed", "Published items", "Overdue", "Submissions", "Graded score percent", "Instructor review"])',
        'writer.writerow(["Student", "Progress percent", "Completed", "Published items", "Overdue", "Submissions", "Attendance rate percent", "Participation points", "Graded score percent", "Instructor review"])',
        "Learning Analytics CSV headers",
    )
    text = replace_once(
        text,
        'writer.writerow([row["email"], row["progress"], row["completed"], row["total"], row["overdue"], row["submissions"], "" if row["grade_percent"] is None else round(float(row["grade_percent"]), 2), row["label_en"]])',
        'writer.writerow([row["email"], row["progress"], row["completed"], row["total"], row["overdue"], row["submissions"], "" if row["attendance_rate"] is None else round(float(row["attendance_rate"]), 2), round(float(row["participation_points"]), 2), "" if row["grade_percent"] is None else round(float(row["grade_percent"]), 2), row["label_en"]])',
        "Learning Analytics CSV attendance values",
    )
    LEARNING_ANALYTICS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Attendance & Participation v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    patch_student_experience()
    patch_learning_analytics()
    compile(STUDENT_EXPERIENCE.read_text(encoding="utf-8"), str(STUDENT_EXPERIENCE), "exec")
    compile(LEARNING_ANALYTICS.read_text(encoding="utf-8"), str(LEARNING_ANALYTICS), "exec")
    print("NUVEDRA Attendance & Participation v1 installed: attendance sessions, student records, participation evidence, CSV export, student transparency, and Learning Analytics integration.", flush=True)


if __name__ == "__main__":
    main()
