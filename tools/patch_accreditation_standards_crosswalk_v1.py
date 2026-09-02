from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/accreditation_standards_crosswalk_module.py.txt")
MODULE = Path("app/accreditation_standards_crosswalk.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
PROGRAM_MODULE = Path("app/program_outcomes_accreditation.py")
TAG = "NUVEDRA_ACCREDITATION_STANDARDS_CROSSWALK_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.accreditation_standards_crosswalk import register_accreditation_standards_crosswalk\n"
    if import_line not in text:
        anchors = (
            "from app.institutional_evidence_portfolio import register_institutional_evidence_portfolio\n",
            "from app.assessment_plans_continuous_improvement import register_assessment_plans_continuous_improvement\n",
            "from app.program_outcomes_accreditation import register_program_outcomes_accreditation\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Accreditation Standards Catalog & Crosswalk v1 could not locate an academic portal import anchor.")
    registration = "    register_accreditation_standards_crosswalk(app)\n"
    if registration not in text:
        anchors = (
            "    register_institutional_evidence_portfolio(app)\n",
            "    register_assessment_plans_continuous_improvement(app)\n",
            "    register_program_outcomes_accreditation(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Accreditation Standards Catalog & Crosswalk v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_program_dashboard() -> None:
    if not PROGRAM_MODULE.is_file():
        raise RuntimeError("Accreditation Standards Catalog & Crosswalk v1 requires Program Outcomes & Accreditation v1.")
    text = PROGRAM_MODULE.read_text(encoding="utf-8")
    if TAG not in text:
        old = '<a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/evidence" data-institutional-evidence-link="v1">Evidence Repository</a>'
        new = old + '<a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/standards" data-accreditation-crosswalk-link="v1">Standards Crosswalk</a>'
        if old not in text:
            raise RuntimeError("Accreditation Standards Catalog & Crosswalk v1 could not locate the Evidence Repository program action.")
        text = text.replace(old, new, 1)
        text = "# NUVEDRA_ACCREDITATION_STANDARDS_CROSSWALK_V1\n" + text
    PROGRAM_MODULE.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Accreditation Standards Catalog & Crosswalk v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_program_dashboard()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    compile(PROGRAM_MODULE.read_text(encoding="utf-8"), str(PROGRAM_MODULE), "exec")
    print("NUVEDRA Accreditation Standards Catalog & Crosswalk v1 installed: framework catalog, standards/criteria, program crosswalks, deterministic coverage states, CSV export, and program navigation.", flush=True)


if __name__ == "__main__":
    main()
