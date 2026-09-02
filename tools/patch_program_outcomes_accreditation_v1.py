from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/program_outcomes_accreditation_module.py.txt")
MODULE = Path("app/program_outcomes_accreditation.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_PROGRAM_OUTCOMES_ACCREDITATION_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.program_outcomes_accreditation import register_program_outcomes_accreditation\n"
    if import_line not in text:
        anchors = (
            "from app.mastery_competency import register_mastery_competency\n",
            "from app.learning_paths_prerequisites import register_learning_paths_prerequisites\n",
            "from app.rubrics_outcomes import register_rubrics_outcomes\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Program Outcomes & Accreditation v1 could not locate an academic portal import anchor.")
    registration = "    register_program_outcomes_accreditation(app)\n"
    if registration not in text:
        anchors = (
            "    register_mastery_competency(app)\n",
            "    register_learning_paths_prerequisites(app)\n",
            "    register_rubrics_outcomes(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Program Outcomes & Accreditation v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_PROGRAM_OUTCOMES_ACCREDITATION_V1
  function initializeProgramOutcomesLink() {
    const root = document.querySelector('[data-testid="visual-course-studio"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!root || !match || root.querySelector('[data-program-outcomes-link]')) return;
    const hero = root.querySelector('.studio-hero');
    if (!hero) return;
    let actions = hero.querySelector('.studio-actions');
    if (!actions) { actions = document.createElement('div'); actions.className = 'studio-actions'; hero.appendChild(actions); }
    const link = document.createElement('a');
    link.className = 'studio-button studio-button--quiet';
    link.href = `/faculty/programs?course_id=${match[1]}`;
    link.dataset.programOutcomesLink = 'v1';
    link.dataset.i18nEn = 'Program Alignment';
    link.dataset.i18nEs = 'Alineación de programa';
    link.textContent = language() === 'es' ? 'Alineación de programa' : 'Program Alignment';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Program Outcomes & Accreditation v1 could not insert Course Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeProgramOutcomesLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Program Outcomes & Accreditation v1 could not initialize Course Studio navigation.")
        text = text.replace(marker, "    initializeProgramOutcomesLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Program Outcomes & Accreditation v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    print("NUVEDRA Program Outcomes & Accreditation v1 installed: program workspaces, curriculum matrix, aggregate evidence, benchmark review, snapshots, CSV export, and Course Studio navigation.", flush=True)


if __name__ == "__main__":
    main()
