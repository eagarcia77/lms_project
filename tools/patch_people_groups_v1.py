from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/people_groups_module.py.txt")
MODULE = Path("app/people_groups.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
ASSIGNMENTS = Path("app/assignments_submissions.py")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
TAG = "NUVEDRA_PEOPLE_GROUPS_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"People & Groups v1 could not find {label}: {old[:160]!r}")
    return text.replace(old, new, 1)


def _insert_student_assignment_group_notice(text: str) -> str:
    """Place group context after the student assignment hero without depending on hero internals."""
    injected = '</header>{group_html}<article class="studio-panel content-body">'
    if injected in text:
        return text

    root_marker = 'data-testid="student-assignment-v2"'
    root_index = text.find(root_marker)
    if root_index < 0:
        raise RuntimeError("People & Groups v1 could not locate the student assignment view.")

    stable_boundary = '</header><article class="studio-panel content-body">'
    boundary_index = text.find(stable_boundary, root_index)
    if boundary_index < 0:
        raise RuntimeError("People & Groups v1 could not locate the student assignment hero/content boundary.")

    return text[:boundary_index] + injected + text[boundary_index + len(stable_boundary):]


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.people_groups import register_people_groups\n"
    if import_line not in text:
        anchors = (
            "from app.course_copy_import import register_course_copy_import\n",
            "from app.rubrics_outcomes import register_rubrics_outcomes\n",
            "from app.assignments_submissions import register_assignments_submissions\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("People & Groups v1 could not locate an academic portal import anchor.")
    registration = "    register_people_groups(app)\n"
    if registration not in text:
        anchors = (
            "    register_course_copy_import(app)\n",
            "    register_rubrics_outcomes(app)\n",
            "    register_assignments_submissions(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("People & Groups v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_PEOPLE_GROUPS_V1
  function initializePeopleGroupsLink() {
    const root = document.querySelector('[data-testid="visual-course-studio"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!root || !match || root.querySelector('[data-people-groups-link]')) return;
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
    link.href = `/faculty/studio/courses/${match[1]}/people`;
    link.dataset.peopleGroupsLink = 'v1';
    link.dataset.i18nEn = 'People & Groups';
    link.dataset.i18nEs = 'Personas y grupos';
    link.textContent = language() === 'es' ? 'Personas y grupos' : 'People & Groups';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("People & Groups v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializePeopleGroupsLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("People & Groups v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializePeopleGroupsLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def patch_assignments() -> None:
    if not ASSIGNMENTS.is_file():
        raise RuntimeError("People & Groups v1 requires the generated Assignments & Submissions v2 module.")
    text = ASSIGNMENTS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import app.academic_access as academic_access\n",
        "import app.academic_access as academic_access\nfrom app.people_groups import require_group_item_access\n",
        "Assignments group-access import",
    )
    get_anchor = '            access = academic_access.require_course_role(conn, course_id, user["email"], academic_access.STUDENT_ROLES)\n'
    get_block = get_anchor + '            group_context = require_group_item_access(conn, item_id, user["email"])\n'
    text = replace_once(text, get_anchor, get_block, "student assignment group-access gate")
    post_anchor = '            access = academic_access.require_course_role(conn, course_id, user["email"], {"student"})\n'
    post_block = post_anchor + '            require_group_item_access(conn, item_id, user["email"])\n'
    text = replace_once(text, post_anchor, post_block, "assignment submission group-access gate")
    due_anchor = '        due_text = _format_when(item.get("due_at")) or "No due date"\n'
    due_block = due_anchor + '''        group_html = ""
        if group_context:
            group_html = f'<section class="studio-panel"><p class="studio-notice"><strong data-i18n-en="Group activity" data-i18n-es="Actividad de grupo">Group activity</strong>: {academic_access.esc(group_context.get("name"))}. <span data-i18n-en="Your submission and grade remain individual in v1." data-i18n-es="Su entrega y calificación continúan siendo individuales en v1.">Your submission and grade remain individual in v1.</span></p></section>'
'''
    text = replace_once(text, due_anchor, due_block, "assignment group context notice")
    text = _insert_student_assignment_group_notice(text)
    ASSIGNMENTS.write_text(text, encoding="utf-8")


def patch_student_experience() -> None:
    if not STUDENT_EXPERIENCE.is_file():
        raise RuntimeError("People & Groups v1 requires the generated Student Experience v2 module.")
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    old = '<nav class="studio-breadcrumbs"><a href="/portal" data-i18n-en="My courses" data-i18n-es="Mis cursos">My courses</a></nav>'
    new = '<nav class="studio-breadcrumbs"><a href="/portal" data-i18n-en="My courses" data-i18n-es="Mis cursos">My courses</a><span>/</span><a href="/learn/groups" data-i18n-en="My Groups" data-i18n-es="Mis grupos">My Groups</a></nav>'
    if new not in text:
        if old not in text:
            raise RuntimeError("People & Groups v1 could not add My Groups to the student dashboard.")
        text = text.replace(old, new, 1)
    STUDENT_EXPERIENCE.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("People & Groups v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    patch_assignments()
    patch_student_experience()
    compile(ASSIGNMENTS.read_text(encoding="utf-8"), str(ASSIGNMENTS), "exec")
    compile(STUDENT_EXPERIENCE.read_text(encoding="utf-8"), str(STUDENT_EXPERIENCE), "exec")
    print("NUVEDRA People & Groups v1 installed: roster visibility, private groups, targeted assignment access, collaboration, notifications, and Student/Studio navigation.", flush=True)


if __name__ == "__main__":
    main()
