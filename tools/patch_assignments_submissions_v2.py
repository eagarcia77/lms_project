from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/assignments_submissions_module.py.txt")
MODULE = Path("app/assignments_submissions.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_ASSIGNMENTS_SUBMISSIONS_V2"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.assignments_submissions import register_assignments_submissions\n"
    if import_line not in text:
        anchors = (
            "from app.discussions_collaboration import register_discussions_collaboration\n",
            "from app.course_announcements import register_course_announcements\n",
            "from app.calendar_notifications import register_calendar_notifications\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Assignments & Submissions v2 could not locate an academic portal import anchor.")

    registration = "    register_assignments_submissions(app)\n"
    if registration not in text:
        anchors = (
            "    register_discussions_collaboration(app)\n",
            "    register_course_announcements(app)\n",
            "    register_calendar_notifications(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Assignments & Submissions v2 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_student_assignment_links() -> None:
    if not STUDENT_EXPERIENCE.is_file():
        raise RuntimeError("Student Experience v2 must exist before Assignments & Submissions v2 is installed.")
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    if TAG in text:
        return
    discussion_version = '''def _item_href(item: dict[str, Any]) -> str:\n    # NUVEDRA_DISCUSSIONS_COLLABORATION_V1\n    item_id = int(item["id"])\n    item_type = str(item.get("item_type") or "")\n    if item_type == "discussion":\n        return f"/learn/discussions/{item_id}"\n    return f"/learn/assessments/{item_id}" if item_type in STRUCTURED_TYPES else f"/learn/items/{item_id}"\n'''
    assignment_version = '''def _item_href(item: dict[str, Any]) -> str:\n    # NUVEDRA_DISCUSSIONS_COLLABORATION_V1\n    # NUVEDRA_ASSIGNMENTS_SUBMISSIONS_V2\n    item_id = int(item["id"])\n    item_type = str(item.get("item_type") or "")\n    if item_type == "discussion":\n        return f"/learn/discussions/{item_id}"\n    if item_type in {"assignment", "project", "presentation"}:\n        return f"/learn/assignments/{item_id}"\n    return f"/learn/assessments/{item_id}" if item_type in STRUCTURED_TYPES else f"/learn/items/{item_id}"\n'''
    if discussion_version not in text:
        raise RuntimeError("Assignments & Submissions v2 could not patch the discussion-aware Student Experience item router.")
    STUDENT_EXPERIENCE.write_text(text.replace(discussion_version, assignment_version, 1), encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_ASSIGNMENTS_SUBMISSIONS_V2
  function initializeAssignmentsSubmissionsLink() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!courseStudio || !courseMatch || courseStudio.querySelector('[data-assignments-submissions-link]')) return;
    const hero = courseStudio.querySelector('.studio-hero');
    if (!hero) return;
    let actions = hero.querySelector('.studio-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'studio-actions';
      hero.appendChild(actions);
    }
    const link = document.createElement('a');
    link.className = 'studio-button studio-button--quiet';
    link.href = `/faculty/studio/courses/${courseMatch[1]}/assignments`;
    link.dataset.assignmentsSubmissionsLink = 'v2';
    link.dataset.i18nEn = 'Assignments';
    link.dataset.i18nEs = 'Asignaciones';
    link.textContent = language() === 'es' ? 'Asignaciones' : 'Assignments';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Assignments & Submissions v2 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeAssignmentsSubmissionsLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Assignments & Submissions v2 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeAssignmentsSubmissionsLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Assignments & Submissions v2 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_student_assignment_links()
    patch_studio_js()
    print("NUVEDRA Assignments & Submissions v2 installed: student drafts, file evidence, resubmission history, instructor inbox, notifications, and Gradebook integration.", flush=True)


if __name__ == "__main__":
    main()
