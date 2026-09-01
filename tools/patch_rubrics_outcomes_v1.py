from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/rubrics_outcomes_module.py.txt")
MODULE = Path("app/rubrics_outcomes.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
ASSIGNMENTS = Path("app/assignments_submissions.py")
GRADEBOOK = Path("app/gradebook.py")
TAG = "NUVEDRA_RUBRICS_OUTCOMES_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.rubrics_outcomes import register_rubrics_outcomes\n"
    if import_line not in text:
        anchors = (
            "from app.assignments_submissions import register_assignments_submissions\n",
            "from app.discussions_collaboration import register_discussions_collaboration\n",
            "from app.course_announcements import register_course_announcements\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Rubrics & Outcomes v1 could not locate an academic portal import anchor.")

    registration = "    register_rubrics_outcomes(app)\n"
    if registration not in text:
        anchors = (
            "    register_assignments_submissions(app)\n",
            "    register_discussions_collaboration(app)\n",
            "    register_course_announcements(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Rubrics & Outcomes v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_RUBRICS_OUTCOMES_V1
  function initializeRubricsOutcomesLink() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!courseStudio || !courseMatch || courseStudio.querySelector('[data-rubrics-outcomes-link]')) return;
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
    link.href = `/faculty/studio/courses/${courseMatch[1]}/rubrics`;
    link.dataset.rubricsOutcomesLink = 'v1';
    link.dataset.i18nEn = 'Rubrics & Outcomes';
    link.dataset.i18nEs = 'Rúbricas y resultados';
    link.textContent = language() === 'es' ? 'Rúbricas y resultados' : 'Rubrics & Outcomes';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Rubrics & Outcomes v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeRubricsOutcomesLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Rubrics & Outcomes v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeRubricsOutcomesLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def patch_assignment_student_link() -> None:
    if not ASSIGNMENTS.is_file():
        raise RuntimeError("Assignments & Submissions v2 must exist before Rubrics & Outcomes v1 is installed.")
    text = ASSIGNMENTS.read_text(encoding="utf-8")
    marker = "NUVEDRA_RUBRICS_OUTCOMES_V1_ASSIGNMENT_LINK"
    if marker in text:
        return
    old = "        body = f'''{_assets()}<main class=\"studio-shell\" data-studio-root data-testid=\"student-assignment-v2\"><nav class=\"studio-breadcrumbs\"><a href=\"/learn/courses/{course_id}\" data-i18n-en=\"Back to course\" data-i18n-es=\"Volver al curso\">Back to course</a></nav><header class=\"studio-hero studio-hero--module\"><div><p class=\"studio-eyebrow\" data-i18n-en=\"Assignment\" data-i18n-es=\"Asignación\">Assignment</p><h2>{academic_access.esc(item.get('title'))}</h2><p>{academic_access.esc(module.get('title'))} · <span data-i18n-en=\"Due\" data-i18n-es=\"Entrega\">Due</span>: {academic_access.esc(due_text)} · {academic_access.esc(item.get('points') or '—')} pts</p></div></header><article class=\"studio-panel content-body\">"
    new = "        # NUVEDRA_RUBRICS_OUTCOMES_V1_ASSIGNMENT_LINK\n        body = f'''{_assets()}<main class=\"studio-shell\" data-studio-root data-testid=\"student-assignment-v2\"><nav class=\"studio-breadcrumbs\"><a href=\"/learn/courses/{course_id}\" data-i18n-en=\"Back to course\" data-i18n-es=\"Volver al curso\">Back to course</a></nav><header class=\"studio-hero studio-hero--module\"><div><p class=\"studio-eyebrow\" data-i18n-en=\"Assignment\" data-i18n-es=\"Asignación\">Assignment</p><h2>{academic_access.esc(item.get('title'))}</h2><p>{academic_access.esc(module.get('title'))} · <span data-i18n-en=\"Due\" data-i18n-es=\"Entrega\">Due</span>: {academic_access.esc(due_text)} · {academic_access.esc(item.get('points') or '—')} pts</p></div><div class=\"studio-actions\"><a class=\"studio-button studio-button--quiet\" href=\"/learn/items/{item_id}/rubric\" data-i18n-en=\"View rubric\" data-i18n-es=\"Ver rúbrica\">View rubric</a></div></header><article class=\"studio-panel content-body\">"
    if old not in text:
        raise RuntimeError("Rubrics & Outcomes v1 could not add the student rubric link to Assignments v2.")
    ASSIGNMENTS.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_gradebook_link() -> None:
    if not GRADEBOOK.is_file():
        raise RuntimeError("Gradebook must exist before Rubrics & Outcomes v1 is installed.")
    text = GRADEBOOK.read_text(encoding="utf-8")
    marker = "NUVEDRA_RUBRICS_OUTCOMES_V1_GRADEBOOK_LINK"
    if marker in text:
        return
    old = "{esc(max_points) if max_points not in (None, \"\") else \"—\"} pts</small></td>\n                  <td><details>"
    new = "{esc(max_points) if max_points not in (None, \"\") else \"—\"} pts</small><br><a href=\"{GRADEBOOK_PREFIX}/submissions/{int(row['submission_id'])}/rubric\" data-i18n-en=\"Grade with rubric\" data-i18n-es=\"Calificar con rúbrica\">Grade with rubric</a><!-- NUVEDRA_RUBRICS_OUTCOMES_V1_GRADEBOOK_LINK --></td>\n                  <td><details>"
    if old not in text:
        raise RuntimeError("Rubrics & Outcomes v1 could not add rubric grading to Gradebook.")
    GRADEBOOK.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Rubrics & Outcomes v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    patch_assignment_student_link()
    patch_gradebook_link()
    print("NUVEDRA Rubrics & Outcomes v1 installed: reusable rubric builder, course outcomes, student criteria visibility, rubric grading, and Gradebook synchronization.", flush=True)


if __name__ == "__main__":
    main()
