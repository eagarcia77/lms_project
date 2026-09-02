from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-institutional-evidence-portfolio-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "evidence-portfolio-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "evidence-portfolio-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "evidence.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Evidence-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Institutional Evidence Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/evidence-user/{kind}", include_in_schema=False)
async def smoke_evidence_user(kind: str, request: Request):
    users = {
        "reviewer": {"id": "evidence-reviewer", "name": "Evidence Reviewer", "email": "evidence.reviewer@example.com"},
        "student": {"id": "evidence-student", "name": "Evidence Student", "email": "evidence.student@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported institutional-evidence smoke user.")
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
        expect(client.post("/admin/login", data={"email": "evidence.admin@example.com", "password": "Initial-Evidence-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-Evidence-2026!", "confirm": "Updated-Evidence-2026!"}), 303, "admin password update")

        created_program = client.post("/faculty/programs", data={
            "program_code": "EVID-EDD", "title": "Evidence and Accreditation Program", "description": "Program used for institutional evidence validation.",
        })
        expect(created_program, 303, "program creation")
        program_id = int(created_program.headers["location"].rsplit("/", 1)[-1])

        now = utcnow()
        with db() as conn:
            outcome_id = int(execute(conn, """INSERT INTO nuvedra_program_outcomes
                (program_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,'active',?,?,?)""", (program_id, "PLO-1", "Integrate evidence for continuous improvement", "Program evidence outcome.", "evidence.admin@example.com", now, now)).lastrowid)
            cycle_id = int(execute(conn, """INSERT INTO nuvedra_assessment_cycles
                (program_id,label,start_date,end_date,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'open',?,?,?)""", (program_id, "2026-2027 Assessment Cycle", "2026-08-01", "2027-06-30", "evidence.admin@example.com", now, now)).lastrowid)
            action_id = int(execute(conn, """INSERT INTO nuvedra_improvement_actions
                (cycle_id,program_outcome_id,measure_id,title,action_plan,responsible_email,due_date,status,evidence_note,follow_up_result,closing_note,created_by,created_at,updated_at)
                VALUES (?,?,NULL,?,?,?,?, 'in_progress','','','',?,?,?)""", (cycle_id, outcome_id, "Strengthen evidence review", "Revise the annual evidence review workflow.", "evidence.admin@example.com", "2027-03-15", "evidence.admin@example.com", now, now)).lastrowid)
            execute(conn, "INSERT INTO nuvedra_program_members (program_id,user_email,program_role,status,created_by,created_at) VALUES (?,?, 'reviewer','active',?,?)", (program_id, "evidence.reviewer@example.com", "evidence.admin@example.com", now))

        repository = client.get(f"/faculty/programs/{program_id}/evidence")
        expect(repository, 200, "evidence repository")
        require(repository, 'data-testid="institutional-evidence-repository-v1"', "repository marker")
        require(repository, "Create accreditation portfolio", "portfolio creation control")

        create_evidence = client.post(
            f"/faculty/programs/{program_id}/evidence/assets",
            data={
                "title": "Annual Assessment Policy",
                "evidence_type": "policy",
                "description": "Approved policy documenting the program assessment process.",
                "tags": "assessment, accreditation, policy",
                "standard_code": "MSCHE V",
                "criterion_code": "5.2",
                "cycle_id": str(cycle_id),
                "program_outcome_id": str(outcome_id),
                "improvement_action_id": str(action_id),
                "source_url": "",
                "change_note": "Initial approved policy",
            },
            files={"upload": ("assessment-policy-v1.pdf", b"%PDF-1.4\nNUVEDRA evidence version one\n", "application/pdf")},
        )
        expect(create_evidence, 303, "initial evidence upload")
        asset_url = create_evidence.headers["location"]
        asset_id = int(asset_url.rsplit("/", 1)[-1])

        detail = client.get(asset_url)
        expect(detail, 200, "evidence detail")
        require(detail, 'data-testid="institutional-evidence-version-history-v1"', "version history marker")
        require(detail, "v1", "first version")
        require(detail, "MSCHE V", "standard mapping")
        require(detail, "2026-2027 Assessment Cycle", "assessment cycle context")
        require(detail, "Strengthen evidence review", "improvement action context")

        version2 = client.post(
            f"/faculty/programs/{program_id}/evidence/assets/{asset_id}/versions",
            data={"source_url": "", "change_note": "Faculty-approved revision"},
            files={"upload": ("assessment-policy-v2.pdf", b"%PDF-1.4\nNUVEDRA evidence version two\n", "application/pdf")},
        )
        expect(version2, 303, "second evidence version")
        with db() as conn:
            versions = rows(execute(conn, "SELECT id,version_no,file_name FROM nuvedra_evidence_versions WHERE asset_id=? ORDER BY version_no", (asset_id,)))
        if [int(v["version_no"]) for v in versions] != [1, 2]:
            raise RuntimeError(f"Evidence version history is incorrect: {versions}")
        version2_id = int(versions[-1]["id"])

        create_portfolio = client.post(f"/faculty/programs/{program_id}/evidence/portfolios", data={
            "title": "2027 Accreditation Review Portfolio",
            "accreditor": "Institutional Review Body",
            "review_period": "2026-2027",
            "description": "Evidence package for institutional accreditation review.",
        })
        expect(create_portfolio, 303, "portfolio creation")
        portfolio_url = create_portfolio.headers["location"]
        portfolio_id = int(portfolio_url.rsplit("/", 1)[-1])

        expect(client.post(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/items", data={
            "asset_id": str(asset_id), "narrative": "Evidence demonstrates a documented annual assessment process.", "position": "1",
        }), 303, "pin evidence in portfolio")

        portfolio = client.get(portfolio_url)
        expect(portfolio, 200, "portfolio detail")
        require(portfolio, 'data-testid="accreditation-evidence-portfolio-v1"', "portfolio marker")
        require(portfolio, "v2", "portfolio pins current version")
        require(portfolio, "Evidence demonstrates a documented annual assessment process.", "portfolio narrative")

        expect(client.post(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/freeze"), 303, "freeze portfolio")
        frozen = client.get(portfolio_url)
        expect(frozen, 200, "frozen portfolio")
        require(frozen, "frozen accreditation evidence portfolio", "frozen status")

        version3 = client.post(
            f"/faculty/programs/{program_id}/evidence/assets/{asset_id}/versions",
            data={"source_url": "", "change_note": "Post-review repository revision"},
            files={"upload": ("assessment-policy-v3.pdf", b"%PDF-1.4\nNUVEDRA evidence version three\n", "application/pdf")},
        )
        expect(version3, 303, "third repository version after portfolio freeze")
        with db() as conn:
            latest = rows(execute(conn, "SELECT version_no FROM nuvedra_evidence_versions WHERE asset_id=? ORDER BY version_no DESC LIMIT 1", (asset_id,)))[0]
        if int(latest["version_no"]) != 3:
            raise RuntimeError("Latest repository evidence version was not advanced to v3.")

        frozen_after_v3 = client.get(portfolio_url)
        expect(frozen_after_v3, 200, "frozen portfolio after newer repository evidence")
        require(frozen_after_v3, "v2", "frozen portfolio preserves pinned version")
        if "v3" in frozen_after_v3.text:
            raise RuntimeError("Frozen portfolio silently replaced its pinned v2 evidence with v3.")
        expect(client.post(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/items", data={"asset_id": str(asset_id), "narrative": "Attempted refresh", "position": "1"}), 409, "frozen portfolio mutation protection")

        csv_export = client.get(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}.csv")
        expect(csv_export, 200, "portfolio CSV")
        require(csv_export, "MSCHE V", "CSV standard")
        require(csv_export, "5.2", "CSV criterion")
        require(csv_export, "Annual Assessment Policy", "CSV evidence title")
        require(csv_export, "assessment-policy-v2.pdf", "CSV pinned version resource")
        if "evidence.student@example.com" in csv_export.text:
            raise RuntimeError("Portfolio CSV leaked a learner email address.")

        program_dashboard = client.get(f"/faculty/programs/{program_id}")
        expect(program_dashboard, 200, "program dashboard navigation")
        require(program_dashboard, 'data-institutional-evidence-link="v1"', "Evidence Repository program navigation")
        assessment_dashboard = client.get(f"/faculty/programs/{program_id}/assessment-plans?cycle_id={cycle_id}")
        expect(assessment_dashboard, 200, "assessment plan evidence navigation")
        require(assessment_dashboard, 'data-evidence-repository-link="v1"', "assessment workspace evidence navigation")

        expect(client.get("/admin/logout"), 303, "admin logout")
        expect(client.get("/__smoke/evidence-user/reviewer"), 200, "reviewer session")
        expect(client.get(f"/faculty/programs/{program_id}/evidence"), 200, "reviewer repository read access")
        expect(client.get(portfolio_url), 200, "reviewer portfolio read access")
        expect(client.get(f"/faculty/programs/{program_id}/evidence/versions/{version2_id}/download"), 200, "reviewer protected evidence download")
        expect(client.get(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}.csv"), 200, "reviewer portfolio export")
        reviewer_write = client.post(f"/faculty/programs/{program_id}/evidence/assets", data={
            "title": "Reviewer cannot add", "evidence_type": "report", "description": "", "tags": "", "standard_code": "", "criterion_code": "", "cycle_id": "", "program_outcome_id": "", "improvement_action_id": "", "source_url": "https://example.com/evidence", "change_note": "Attempt",
        })
        expect(reviewer_write, 403, "reviewer mutation protection")

        expect(client.get("/__smoke/evidence-user/student"), 200, "student session")
        expect(client.get(f"/faculty/programs/{program_id}/evidence"), 403, "student repository protection")
        expect(client.get(portfolio_url), 403, "student portfolio protection")
        expect(client.get(f"/faculty/programs/{program_id}/evidence/versions/{version2_id}/download"), 403, "student evidence download protection")

    print("Institutional Evidence Repository & Accreditation Portfolio v1 validated: protected program repository, standards/criterion mapping, assessment-cycle/outcome/action context, DB-backed file versions, reviewer access, student denial, pinned portfolio versions, freeze integrity, CSV export, and program/assessment navigation.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
