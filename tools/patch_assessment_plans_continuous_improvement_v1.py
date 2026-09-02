from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/assessment_plans_continuous_improvement_module.py.txt")
MODULE = Path("app/assessment_plans_continuous_improvement.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
PROGRAM_MODULE = Path("app/program_outcomes_accreditation.py")
TAG = "NUVEDRA_ASSESSMENT_PLANS_CONTINUOUS_IMPROVEMENT_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.assessment_plans_continuous_improvement import register_assessment_plans_continuous_improvement\n"
    if import_line not in text:
        anchors = (
            "from app.program_outcomes_accreditation import register_program_outcomes_accreditation\n",
            "from app.mastery_competency import register_mastery_competency\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Assessment Plans & Continuous Improvement v1 could not locate an academic portal import anchor.")
    registration = "    register_assessment_plans_continuous_improvement(app)\n"
    if registration not in text:
        anchors = (
            "    register_program_outcomes_accreditation(app)\n",
            "    register_mastery_competency(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Assessment Plans & Continuous Improvement v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_program_dashboard() -> None:
    if not PROGRAM_MODULE.is_file():
        raise RuntimeError("Assessment Plans & Continuous Improvement v1 requires Program Outcomes & Accreditation v1.")
    text = PROGRAM_MODULE.read_text(encoding="utf-8")
    if TAG not in text:
        old = '<div class="studio-actions"><a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/matrix.csv">Curriculum matrix CSV</a>'
        new = '<div class="studio-actions"><a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/assessment-plans" data-assessment-plans-link="v1">Assessment Plans</a><a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/matrix.csv">Curriculum matrix CSV</a>'
        if old not in text:
            raise RuntimeError("Assessment Plans & Continuous Improvement v1 could not locate the program-dashboard action anchor.")
        text = text.replace(old, new, 1)
        text = "# NUVEDRA_ASSESSMENT_PLANS_CONTINUOUS_IMPROVEMENT_V1\n" + text
    PROGRAM_MODULE.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Assessment Plans & Continuous Improvement v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    # Avoid formatting an empty string with the numeric :g formatter when no result exists yet.
    risky = "value=\"{'' if m.get('result_value') is None else float(m.get('result_value') or 0):g}\""
    safe = "value=\"{academic_access.esc(m.get('result_value') if m.get('result_value') is not None else '', attr=True)}\""
    source = source.replace(risky, safe)
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_program_dashboard()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    compile(PROGRAM_MODULE.read_text(encoding="utf-8"), str(PROGRAM_MODULE), "exec")
    print("NUVEDRA Assessment Plans & Continuous Improvement v1 installed: assessment cycles, direct/indirect measures, findings, improvement actions, closing-the-loop verification, read-only historical cycles, CSV export, and program navigation.", flush=True)


if __name__ == "__main__":
    main()
