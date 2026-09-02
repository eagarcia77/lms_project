from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/mastery_competency_module.py.txt")
MODULE = Path("app/mastery_competency.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_MASTERY_COMPETENCY_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.mastery_competency import register_mastery_competency\n"
    if import_line not in text:
        anchors = (
            "from app.learning_paths_prerequisites import register_learning_paths_prerequisites\n",
            "from app.xapi_cmi5 import register_xapi_cmi5\n",
            "from app.rubrics_outcomes import register_rubrics_outcomes\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Mastery & Competency Dashboard v1 could not locate an academic portal import anchor.")
    registration = "    register_mastery_competency(app)\n"
    if registration not in text:
        anchors = (
            "    register_learning_paths_prerequisites(app)\n",
            "    register_xapi_cmi5(app)\n",
            "    register_rubrics_outcomes(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Mastery & Competency Dashboard v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_MASTERY_COMPETENCY_V1
  function initializeMasteryCompetencyLinks() {
    const faculty = document.querySelector('[data-testid="visual-course-studio"]');
    const facultyMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (faculty && facultyMatch && !faculty.querySelector('[data-mastery-competency-link]')) {
      const hero = faculty.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) { actions = document.createElement('div'); actions.className = 'studio-actions'; hero.appendChild(actions); }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = `/faculty/studio/courses/${facultyMatch[1]}/mastery`;
        link.dataset.masteryCompetencyLink = 'v1';
        link.dataset.i18nEn = 'Mastery & Competencies';
        link.dataset.i18nEs = 'Dominio y competencias';
        link.textContent = language() === 'es' ? 'Dominio y competencias' : 'Mastery & Competencies';
        actions.appendChild(link);
      }
    }
    const student = document.querySelector('[data-testid="student-course-v2"]');
    const studentMatch = window.location.pathname.match(/^\/learn\/courses\/(\d+)$/);
    if (student && studentMatch && !student.querySelector('[data-student-mastery-link]')) {
      const hero = student.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) { actions = document.createElement('div'); actions.className = 'studio-actions'; hero.appendChild(actions); }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = `/learn/courses/${studentMatch[1]}/mastery`;
        link.dataset.studentMasteryLink = 'v1';
        link.dataset.i18nEn = 'My Mastery';
        link.dataset.i18nEs = 'Mi dominio';
        link.textContent = language() === 'es' ? 'Mi dominio' : 'My Mastery';
        actions.appendChild(link);
      }
    }
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Mastery & Competency Dashboard v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeMasteryCompetencyLinks();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Mastery & Competency Dashboard v1 could not initialize navigation.")
        text = text.replace(marker, "    initializeMasteryCompetencyLinks();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Mastery & Competency Dashboard v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    print("NUVEDRA Mastery & Competency Dashboard v1 installed: outcome attainment, configurable thresholds, evidence detail, CSV export, and faculty/student navigation.", flush=True)


if __name__ == "__main__":
    main()
