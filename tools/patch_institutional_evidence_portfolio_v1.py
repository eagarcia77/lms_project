from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/institutional_evidence_portfolio_module.py.txt")
MODULE = Path("app/institutional_evidence_portfolio.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
PROGRAM_MODULE = Path("app/program_outcomes_accreditation.py")
ASSESSMENT_MODULE = Path("app/assessment_plans_continuous_improvement.py")
TAG = "NUVEDRA_INSTITUTIONAL_EVIDENCE_PORTFOLIO_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.institutional_evidence_portfolio import register_institutional_evidence_portfolio\n"
    if import_line not in text:
        anchors = (
            "from app.assessment_plans_continuous_improvement import register_assessment_plans_continuous_improvement\n",
            "from app.program_outcomes_accreditation import register_program_outcomes_accreditation\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Institutional Evidence Portfolio v1 could not locate an academic portal import anchor.")
    registration = "    register_institutional_evidence_portfolio(app)\n"
    if registration not in text:
        anchors = (
            "    register_assessment_plans_continuous_improvement(app)\n",
            "    register_program_outcomes_accreditation(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Institutional Evidence Portfolio v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_program_dashboard() -> None:
    if not PROGRAM_MODULE.is_file():
        raise RuntimeError("Institutional Evidence Portfolio v1 requires Program Outcomes & Accreditation v1.")
    text = PROGRAM_MODULE.read_text(encoding="utf-8")
    if TAG not in text:
        old = '<a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/assessment-plans" data-assessment-plans-link="v1">Assessment Plans</a>'
        new = old + '<a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/evidence" data-institutional-evidence-link="v1">Evidence Repository</a>'
        if old not in text:
            raise RuntimeError("Institutional Evidence Portfolio v1 could not locate the program dashboard Assessment Plans anchor.")
        text = text.replace(old, new, 1)
        text = "# NUVEDRA_INSTITUTIONAL_EVIDENCE_PORTFOLIO_V1\n" + text
    PROGRAM_MODULE.write_text(text, encoding="utf-8")


def patch_assessment_dashboard() -> None:
    if not ASSESSMENT_MODULE.is_file():
        raise RuntimeError("Institutional Evidence Portfolio v1 requires Assessment Plans & Continuous Improvement v1.")
    text = ASSESSMENT_MODULE.read_text(encoding="utf-8")
    marker = '<nav class="studio-breadcrumbs"><a href="/faculty/programs/{program_id}">Program Outcomes & Accreditation</a></nav>'
    replacement = '<nav class="studio-breadcrumbs"><a href="/faculty/programs/{program_id}">Program Outcomes & Accreditation</a><span>/</span><a href="/faculty/programs/{program_id}/evidence" data-evidence-repository-link="v1">Evidence Repository</a></nav>'
    if replacement not in text:
        if marker not in text:
            raise RuntimeError("Institutional Evidence Portfolio v1 could not locate the assessment workspace breadcrumb anchor.")
        text = text.replace(marker, replacement, 1)
    ASSESSMENT_MODULE.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Institutional Evidence Repository & Accreditation Portfolio v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_program_dashboard()
    patch_assessment_dashboard()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    compile(PROGRAM_MODULE.read_text(encoding="utf-8"), str(PROGRAM_MODULE), "exec")
    compile(ASSESSMENT_MODULE.read_text(encoding="utf-8"), str(ASSESSMENT_MODULE), "exec")
    print("NUVEDRA Institutional Evidence Repository & Accreditation Portfolio v1 installed: protected version history, standards mapping, assessment context, pinned portfolio evidence, freeze controls, CSV export, printable review packages, and program navigation.", flush=True)


if __name__ == "__main__":
    main()
