from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/external_accreditation_review_portal_module.py.txt")
MODULE = Path("app/external_accreditation_review_portal.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
EVIDENCE_MODULE = Path("app/institutional_evidence_portfolio.py")
TAG = "NUVEDRA_EXTERNAL_ACCREDITATION_REVIEW_PORTAL_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.external_accreditation_review_portal import register_external_accreditation_review_portal\n"
    if import_line not in text:
        anchors = (
            "from app.accreditation_standards_crosswalk import register_accreditation_standards_crosswalk\n",
            "from app.institutional_evidence_portfolio import register_institutional_evidence_portfolio\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("External Accreditation Review Portal v1 could not locate an academic portal import anchor.")
    registration = "    register_external_accreditation_review_portal(app)\n"
    if registration not in text:
        anchors = (
            "    register_accreditation_standards_crosswalk(app)\n",
            "    register_institutional_evidence_portfolio(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("External Accreditation Review Portal v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_evidence_portfolio() -> None:
    if not EVIDENCE_MODULE.is_file():
        raise RuntimeError("External Accreditation Review Portal v1 requires Institutional Evidence Portfolio v1.")
    text = EVIDENCE_MODULE.read_text(encoding="utf-8")
    if TAG in text:
        return
    item_anchor = "        item_rows = \"\".join(f'''<tr><td>{academic_access.esc(x.get('standard_code') or '—')}</td>"
    index = text.find(item_anchor)
    if index < 0:
        raise RuntimeError("External Accreditation Review Portal v1 could not locate the accreditation portfolio item table anchor.")
    body_anchor = "        body = f'''{_assets()}<main class=\"studio-shell\" data-studio-root data-testid=\"accreditation-evidence-portfolio-v1\">"
    body_index = text.find(body_anchor, index)
    if body_index < 0:
        raise RuntimeError("External Accreditation Review Portal v1 could not locate the accreditation portfolio body anchor.")
    insertion = """        # NUVEDRA_EXTERNAL_ACCREDITATION_REVIEW_PORTAL_V1\n        external_review_action = \"\"\n        if str(portfolio.get(\"status\")) == \"frozen\":\n            external_review_action = f'<a class=\"studio-button\" data-external-review-link=\"v1\" href=\"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/external-review\">External Review</a>'\n"""
    text = text[:body_index] + insertion + text[body_index:]
    old_actions = '<div class="studio-actions"><a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}.csv">Portfolio CSV</a>'
    new_actions = '<div class="studio-actions">{external_review_action}<a class="studio-button studio-button--quiet" href="/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}.csv">Portfolio CSV</a>'
    if old_actions not in text:
        raise RuntimeError("External Accreditation Review Portal v1 could not locate the portfolio action bar.")
    text = text.replace(old_actions, new_actions, 1)
    EVIDENCE_MODULE.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("External Accreditation Review Portal v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_evidence_portfolio()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    compile(EVIDENCE_MODULE.read_text(encoding="utf-8"), str(EVIDENCE_MODULE), "exec")
    print("NUVEDRA External Accreditation Review Portal v1 installed: expiring hashed review links, frozen evidence packages, protected evidence access, reviewer comments, additional-evidence requests, revocation, response workflow, audit logging, and portfolio navigation.", flush=True)


if __name__ == "__main__":
    main()
