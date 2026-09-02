from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-accreditation-standards-crosswalk-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "standards-crosswalk-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "standards-crosswalk-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "standards.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Standards-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Accreditation Standards Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/standards-user/{kind}", include_in_schema=False)
async def smoke_standards_user(kind: str, request: Request):
    users = {
        "reviewer": {"id": "standards-reviewer", "name": "Standards Reviewer", "email": "standards.reviewer@example.com"},
        "student": {"id": "standards-student", "name": "Standards Student", "email": "standards.student@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported standards smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}: {response.text[:1800]}")


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "standards.admin@example.com", "password": "Initial-Standards-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Standards-2026!", "confirm": "Updated-Standards-2026!"}), 303, "admin password update")

        created_program = client.post("/faculty/programs", data={
            "program_code": "ACC-EDD", "title": "Accreditation Crosswalk Program", "description": "Program used to validate standards coverage.",
        })
        expect(created_program, 303, "program creation")
        program_id = int(created_program.headers["location"].rsplit("/", 1)[-1])

        catalog = client.get("/faculty/accreditation/standards")
        expect(catalog, 200, "standards catalog")
        require(catalog, 'data-testid="accreditation-standards-catalog-v1"', "catalog marker")

        expect(client.post("/faculty/accreditation/standards/frameworks", data={
            "code": "MSCHE", "name": "Institutional Accreditation Framework", "version": "2026 institutional catalog", "description": "Institution-configured framework metadata.", "source_url": "https://example.org/standards",
        }), 303, "framework creation")
        with db() as conn:
            framework_id = int(rows(execute(conn, "SELECT id FROM nuvedra_accreditation_frameworks WHERE code='MSCHE'"))[0]["id"])

        expect(client.post(f"/faculty/accreditation/standards/frameworks/{framework_id}/standards", data={
            "code": "V", "title": "Educational Effectiveness Assessment", "description": "Institutional assessment standard.",
        }), 303, "standard creation")
        with db() as conn:
            standard_id = int(rows(execute(conn, "SELECT id FROM nuvedra_accreditation_standards WHERE framework_id=? AND code='V'", (framework_id,)))[0]["id"])

        for code, title in [
            ("5.1", "Documented assessment process"),
            ("5.2", "Evidence used for improvement"),
            ("5.3", "Assessment context without evidence"),
            ("5.4", "Unmapped requirement"),
        ]:
            expect(client.post(f"/faculty/accreditation/standards/standards/{standard_id}/criteria", data={"code": code, "title": title, "description": f"Criterion {code}."}), 303, f"criterion {code}")

        now = utcnow()
        with db() as conn:
            criteria = {row["code"]: int(row["id"]) for row in rows(execute(conn, "SELECT id,code FROM nuvedra_accreditation_criteria WHERE standard_id=?", (standard_id,)))}
            outcome_id = int(execute(conn, """INSERT INTO nuvedra_program_outcomes
                (program_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,'active',?,?,?)""", (program_id, "PLO-1", "Integrate assessment evidence", "Program outcome for crosswalk validation.", "standards.admin@example.com", now, now)).lastrowid)
            cycle_id = int(execute(conn, """INSERT INTO nuvedra_assessment_cycles
                (program_id,label,start_date,end_date,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'open',?,?,?)""", (program_id, "2026-2027 Assessment Cycle", "2026-08-01", "2027-06-30", "standards.admin@example.com", now, now)).lastrowid)
            asset1 = int(execute(conn, """INSERT INTO nuvedra_evidence_assets
                (title,description,evidence_type,tags,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'active',?,?,?)""", ("Annual Assessment Report", "Evidence for criterion 5.1.", "report", "assessment", "standards.admin@example.com", now, now)).lastrowid)
            asset2 = int(execute(conn, """INSERT INTO nuvedra_evidence_assets
                (title,description,evidence_type,tags,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'active',?,?,?)""", ("Improvement Evidence", "Evidence without contextual mapping.", "improvement", "improvement", "standards.admin@example.com", now, now)).lastrowid)
            for asset_id in (asset1, asset2):
                execute(conn, """INSERT INTO nuvedra_evidence_links
                    (asset_id,program_id,cycle_id,program_outcome_id,improvement_action_id,standard_code,criterion_code,linked_by,linked_at)
                    VALUES (?,?,NULL,NULL,NULL,'','',?,?)""", (asset_id, program_id, "standards.admin@example.com", now))
            execute(conn, "INSERT INTO nuvedra_program_members (program_id,user_email,program_role,status,created_by,created_at) VALUES (?,?, 'reviewer','active',?,?)", (program_id, "standards.reviewer@example.com", "standards.admin@example.com", now))

        expect(client.post(f"/faculty/programs/{program_id}/standards/frameworks", data={"framework_id": str(framework_id), "review_period": "2026-2027"}), 303, "attach framework")

        expect(client.post(f"/faculty/programs/{program_id}/standards/links", data={
            "criterion_id": str(criteria["5.1"]), "link_type": "program_outcome", "program_outcome_id": str(outcome_id), "assessment_cycle_id": "", "evidence_asset_id": "", "improvement_action_id": "", "narrative": "Outcome context",
        }), 303, "covered context link")
        expect(client.post(f"/faculty/programs/{program_id}/standards/links", data={
            "criterion_id": str(criteria["5.1"]), "link_type": "evidence_asset", "program_outcome_id": "", "assessment_cycle_id": "", "evidence_asset_id": str(asset1), "improvement_action_id": "", "narrative": "Direct institutional evidence",
        }), 303, "covered evidence link")
        expect(client.post(f"/faculty/programs/{program_id}/standards/links", data={
            "criterion_id": str(criteria["5.2"]), "link_type": "evidence_asset", "program_outcome_id": "", "assessment_cycle_id": "", "evidence_asset_id": str(asset2), "improvement_action_id": "", "narrative": "Evidence awaiting alignment",
        }), 303, "partial evidence link")
        expect(client.post(f"/faculty/programs/{program_id}/standards/links", data={
            "criterion_id": str(criteria["5.3"]), "link_type": "assessment_cycle", "program_outcome_id": "", "assessment_cycle_id": str(cycle_id), "evidence_asset_id": "", "improvement_action_id": "", "narrative": "Assessment context without uploaded evidence",
        }), 303, "no-evidence context link")

        crosswalk = client.get(f"/faculty/programs/{program_id}/standards")
        expect(crosswalk, 200, "program standards crosswalk")
        require(crosswalk, 'data-testid="accreditation-standards-crosswalk-v1"', "crosswalk marker")
        require(crosswalk, "Covered", "covered status")
        require(crosswalk, "Partial", "partial status")
        require(crosswalk, "No evidence", "no-evidence status")
        require(crosswalk, "Gap", "gap status")
        require(crosswalk, "Annual Assessment Report", "mapped evidence")
        require(crosswalk, "2026-2027 Assessment Cycle", "mapped cycle")

        csv_export = client.get(f"/faculty/programs/{program_id}/standards.csv")
        expect(csv_export, 200, "crosswalk CSV")
        require(csv_export, "5.1: Documented assessment process", "CSV criterion 5.1")
        require(csv_export, "Covered", "CSV covered")
        require(csv_export, "Partial", "CSV partial")
        require(csv_export, "No evidence", "CSV no evidence")
        require(csv_export, "Gap", "CSV gap")

        program_dashboard = client.get(f"/faculty/programs/{program_id}")
        expect(program_dashboard, 200, "program dashboard")
        require(program_dashboard, 'data-accreditation-crosswalk-link="v1"', "program crosswalk navigation")

        expect(client.get("/admin/logout"), 303, "admin logout")
        expect(client.get("/__smoke/standards-user/reviewer"), 200, "reviewer session")
        expect(client.get(f"/faculty/programs/{program_id}/standards"), 200, "reviewer read-only crosswalk")
        expect(client.get(f"/faculty/programs/{program_id}/standards.csv"), 200, "reviewer CSV")
        reviewer_write = client.post(f"/faculty/programs/{program_id}/standards/frameworks", data={"framework_id": str(framework_id), "review_period": "2027-2028"})
        expect(reviewer_write, 403, "reviewer mutation protection")

        expect(client.get("/__smoke/standards-user/student"), 200, "student session")
        expect(client.get(f"/faculty/programs/{program_id}/standards"), 403, "student crosswalk protection")
        expect(client.get(f"/faculty/programs/{program_id}/standards.csv"), 403, "student CSV protection")

    print("Accreditation Standards Catalog & Crosswalk v1 validated: framework catalog, standards/criteria, program attachment, Covered/Partial/No evidence/Gap rules, evidence/context mappings, CSV export, reviewer read-only access, student denial, and program navigation.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
