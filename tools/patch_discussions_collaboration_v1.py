from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/discussions_collaboration_module.py.txt")
MODULE = Path("app/discussions_collaboration.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
TAG = "NUVEDRA_DISCUSSIONS_COLLABORATION_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.discussions_collaboration import register_discussions_collaboration\n"
    if import_line not in text:
        anchors = (
            "from app.course_announcements import register_course_announcements\n",
            "from app.calendar_notifications import register_calendar_notifications\n",
            "from app.learning_analytics import register_learning_analytics\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Discussions & Collaboration v1 could not locate an academic portal import anchor.")

    registration = "    register_discussions_collaboration(app)\n"
    if registration not in text:
        anchors = (
            "    register_course_announcements(app)\n",
            "    register_calendar_notifications(app)\n",
            "    register_learning_analytics(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Discussions & Collaboration v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_student_discussion_links() -> None:
    if not STUDENT_EXPERIENCE.is_file():
        raise RuntimeError("Student Experience v2 must exist before Discussions & Collaboration v1 is installed.")
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    if TAG not in text:
        old = '''def _item_href(item: dict[str, Any]) -> str:\n    item_id = int(item["id"])\n    return f"/learn/assessments/{item_id}" if str(item.get("item_type")) in STRUCTURED_TYPES else f"/learn/items/{item_id}"\n'''
        new = '''def _item_href(item: dict[str, Any]) -> str:\n    # NUVEDRA_DISCUSSIONS_COLLABORATION_V1\n    item_id = int(item["id"])\n    item_type = str(item.get("item_type") or "")\n    if item_type == "discussion":\n        return f"/learn/discussions/{item_id}"\n    return f"/learn/assessments/{item_id}" if item_type in STRUCTURED_TYPES else f"/learn/items/{item_id}"\n'''
        if old not in text:
            raise RuntimeError("Discussions & Collaboration v1 could not patch Student Experience discussion links.")
        text = text.replace(old, new, 1)

        old_direct = '''            if str(item.get("item_type")) in STRUCTURED_TYPES: return RedirectResponse(f"/learn/assessments/{item_id}",status_code=303)\n'''
        new_direct = '''            if str(item.get("item_type")) == "discussion": return RedirectResponse(f"/learn/discussions/{item_id}",status_code=303)\n            if str(item.get("item_type")) in STRUCTURED_TYPES: return RedirectResponse(f"/learn/assessments/{item_id}",status_code=303)\n'''
        if old_direct not in text:
            raise RuntimeError("Discussions & Collaboration v1 could not add the direct discussion redirect.")
        text = text.replace(old_direct, new_direct, 1)
    STUDENT_EXPERIENCE.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_DISCUSSIONS_COLLABORATION_V1
  function initializeDiscussionCollaborationLinks() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!courseStudio || !courseMatch || courseStudio.querySelector('[data-discussions-collaboration-link]')) return;
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
    link.href = `/faculty/studio/courses/${courseMatch[1]}/discussions`;
    link.dataset.discussionsCollaborationLink = 'v1';
    link.dataset.i18nEn = 'Discussions';
    link.dataset.i18nEs = 'Foros';
    link.textContent = language() === 'es' ? 'Foros' : 'Discussions';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Discussions & Collaboration v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeDiscussionCollaborationLinks();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Discussions & Collaboration v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeDiscussionCollaborationLinks();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Discussions & Collaboration v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_student_discussion_links()
    patch_studio_js()
    print("NUVEDRA Discussions & Collaboration v1 installed: threaded discussions, instructor moderation, student participation, notifications, and Gradebook linkage.", flush=True)


if __name__ == "__main__":
    main()
