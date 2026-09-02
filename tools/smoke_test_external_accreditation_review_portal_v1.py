from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-external-accreditation-review-portal-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "external-review-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "external-review-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "external.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-External-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "External Review Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402


@app.get("/__smoke/external-review-user/{kind}", include_in_schema=False)
async def smoke_external_review_user(kind: str, request: Request):
    users = {
        "reviewer": {"id": "external-reviewer", "name": "Internal Program Reviewer", "email": "internal.reviewer@example.com"},
        "student": {"id": "external-student", "name": "External Review Student", "email": "external.student@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported external-review smoke user.")
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
        expect(client.post("/admin/login", data={"email": "external.admin@example.com", "password": "Initial-External-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-External-2026!", "confirm": "Updated-External-2026!"}), 303, "admin password update")

        created_program = client.post("/faculty/programs", data={
            "program_code": "EXT-EDD", "title": "External Review Program", "description": "Program used to validate external accreditation review.",
        })
        expect(created_program, 303, "program creation")
        program_id = int(created_program.headers["location"].rsplit("/", 1)[-1])

        now = utcnow()
        with db() as conn:
            outcome_id = int(execute(conn, """INSERT INTO nuvedra_program_outcomes
                (program_id,code,title,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,'active',?,?,?)""", (program_id, "PLO-1", "Evaluate institutional evidence", "External review outcome.", "external.admin@example.com", now, now)).lastrowid)
            cycle_id = int(execute(conn, """INSERT INTO nuvedra_assessment_cycles
                (program_id,label,start_date,end_date,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'closed',?,?,?)""", (program_id, "2026-2027 Assessment Cycle", "2026-08-01", "2027-06-30", "external.admin@example.com", now, now)).lastrowid)

            framework_id = int(execute(conn, """INSERT INTO nuvedra_accreditation_frameworks
                (code,name,version,description,source_url,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,?,'active',?,?,?)""", ("MSCHE", "Institution-configured MSCHE Framework", "2026 institutional copy", "Smoke framework.", "https://example.com/msche", "external.admin@example.com", now, now)).lastrowid)
            standard_id = int(execute(conn, """INSERT INTO nuvedra_accreditation_standards
                (framework_id,code,title,description,position,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,1,'active',?,?,?)""", (framework_id, "V", "Educational Effectiveness Assessment", "Smoke standard.", "external.admin@example.com", now, now)).lastrowid)
            criterion_id = int(execute(conn, """INSERT INTO nuvedra_accreditation_criteria
                (standard_id,code,title,description,position,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,1,'active',?,?,?)""", (standard_id, "5.2", "Assessment evidence criterion", "Smoke criterion.", "external.admin@example.com", now, now)).lastrowid)
            execute(conn, "INSERT INTO nuvedra_program_frameworks (program_id,framework_id,review_period,status,added_by,added_at) VALUES (?,?,?,'active',?,?)", (program_id, framework_id, "2026-2027", "external.admin@example.com", now))

            asset_id = int(execute(conn, """INSERT INTO nuvedra_evidence_assets
                (title,description,evidence_type,tags,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?, 'active',?,?,?)""", ("Annual Assessment Policy", "Frozen review evidence.", "policy", "assessment, policy", "external.admin@example.com", now, now)).lastrowid)
            version1_id = int(execute(conn, """INSERT INTO nuvedra_evidence_versions
                (asset_id,version_no,file_name,mime_type,file_size,file_bytes,source_url,change_note,created_by,created_at)
                VALUES (?,1,?,?,?,?,NULL,?,?,?)""", (asset_id, "annual-assessment-policy-v1.pdf", "application/pdf", 34, b"%PDF-1.4\nexternal review evidence\n", "Frozen review version", "external.admin@example.com", now)).lastrowid)
            version2_id = int(execute(conn, """INSERT INTO nuvedra_evidence_versions
                (asset_id,version_no,file_name,mime_type,file_size,file_bytes,source_url,change_note,created_by,created_at)
                VALUES (?,2,?,?,?,?,NULL,?,?,?)""", (asset_id, "annual-assessment-policy-v2.pdf", "application/pdf", 35, b"%PDF-1.4\nnewer repository evidence\n", "Newer unpinned version", "external.admin@example.com", now)).lastrowid)
            execute(conn, """INSERT INTO nuvedra_evidence_links
                (asset_id,program_id,cycle_id,program_outcome_id,improvement_action_id,standard_code,criterion_code,linked_by,linked_at)
                VALUES (?,?,?,?,NULL,?,?,?,?)""", (asset_id, program_id, cycle_id, outcome_id, "V", "5.2", "external.admin@example.com", now))

            draft_portfolio_id = int(execute(conn, """INSERT INTO nuvedra_accreditation_portfolios
                (program_id,title,accreditor,review_period,description,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,?,'draft',?,?,?)""", (program_id, "Draft External Review Portfolio", "External Review Body", "2026-2027", "Draft cannot be shared.", "external.admin@example.com", now, now)).lastrowid)

            portfolio_id = int(execute(conn, """INSERT INTO nuvedra_accreditation_portfolios
                (program_id,title,accreditor,review_period,description,status,created_by,created_at,updated_at,frozen_at,frozen_by)
                VALUES (?,?,?,?,?,'frozen',?,?,?,?,?)""", (program_id, "2027 External Accreditation Portfolio", "External Review Body", "2026-2027", "Frozen package for external review.", "external.admin@example.com", now, now, now, "external.admin@example.com")).lastrowid)
            execute(conn, """INSERT INTO nuvedra_accreditation_portfolio_items
                (portfolio_id,asset_id,evidence_version_id,narrative,position,added_by,added_at)
                VALUES (?,?,?,?,1,?,?)""", (portfolio_id, asset_id, version1_id, "Policy demonstrates documented annual assessment.", "external.admin@example.com", now))
            execute(conn, "INSERT INTO nuvedra_program_members (program_id,user_email,program_role,status,created_by,created_at) VALUES (?,?, 'reviewer','active',?,?)", (program_id, "internal.reviewer@example.com", "external.admin@example.com", now))

        draft_share = client.post(f"/faculty/programs/{program_id}/evidence/portfolios/{draft_portfolio_id}/external-review/invites", data={
            "reviewer_name": "Draft Reviewer", "reviewer_email": "draft@example.org", "organization": "Review Team", "expires_at": "2030-01-01T00:00",
        })
        expect(draft_share, 409, "draft portfolio external-share protection")

        expired_create = client.post(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/external-review/invites", data={
            "reviewer_name": "Expired Reviewer", "reviewer_email": "expired@example.org", "organization": "Review Team", "expires_at": "2020-01-01T00:00",
        })
        expect(expired_create, 400, "past expiration rejection")

        invite_create = client.post(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/external-review/invites", data={
            "reviewer_name": "Dr. External Reviewer", "reviewer_email": "reviewer@example.org", "organization": "External Review Team", "expires_at": "2030-01-01T00:00",
        })
        expect(invite_create, 303, "external review invitation creation")

        management = client.get(invite_create.headers["location"])
        expect(management, 200, "external review management")
        require(management, 'data-testid="external-accreditation-review-management-v1"', "management marker")
        require(management, 'data-testid="external-review-generated-link"', "one-time generated link marker")
        require(management, "Dr. External Reviewer", "reviewer name")
        match = re.search(r"/external/review/([A-Za-z0-9_-]{20,})", management.text)
        if not match:
            raise RuntimeError(f"Could not recover generated external review token from one-time management response: {management.text[:1800]}")
        token = match.group(1)

        management_again = client.get(invite_create.headers["location"])
        expect(management_again, 200, "management after token display")
        if 'data-testid="external-review-generated-link"' in management_again.text or token in management_again.text:
            raise RuntimeError("External review token was displayed more than once in the authenticated management UI.")

        with db() as conn:
            invite = rows(execute(conn, "SELECT * FROM nuvedra_external_review_invites WHERE program_id=? AND portfolio_id=? ORDER BY id DESC LIMIT 1", (program_id, portfolio_id)))[0]
            invite_id = int(invite["id"])
            stored_hash = str(invite.get("token_hash") or "")
            if stored_hash != hashlib.sha256(token.encode("utf-8")).hexdigest() or token in stored_hash:
                raise RuntimeError("External review token was not stored as the expected SHA-256 hash.")
            if str(invite.get("token_hint") or "") != token[-6:]:
                raise RuntimeError("External review token hint is incorrect.")

        external = client.get(f"/external/review/{token}")
        expect(external, 200, "external reviewer portal")
        require(external, 'data-testid="external-accreditation-review-portal-v1"', "external portal marker")
        require(external, "2027 External Accreditation Portfolio", "frozen portfolio title")
        require(external, "Annual Assessment Policy", "frozen evidence title")
        require(external, "v1", "pinned evidence version")
        require(external, "V / 5.2", "criterion review scope")
        if external.headers.get("cache-control") != "no-store":
            raise RuntimeError("External review portal must disable caching.")
        if "noindex" not in str(external.headers.get("x-robots-tag") or ""):
            raise RuntimeError("External review portal must prevent search indexing.")

        pinned_evidence = client.get(f"/external/review/{token}/evidence/{version1_id}")
        expect(pinned_evidence, 200, "pinned external evidence access")
        if b"external review evidence" not in pinned_evidence.content:
            raise RuntimeError("External reviewer did not receive the pinned evidence bytes.")
        expect(client.get(f"/external/review/{token}/evidence/{version2_id}"), 404, "unpinned evidence protection")

        invalid_scope = client.post(f"/external/review/{token}/comments", data={"scope": "X|9.9", "comment_text": "Invalid scope should not be accepted."})
        expect(invalid_scope, 400, "invalid accreditation scope protection")

        comment = client.post(f"/external/review/{token}/comments", data={"scope": "V|5.2", "comment_text": "Evidence is clear, but please document how annual review decisions are approved."})
        expect(comment, 303, "external reviewer comment")
        evidence_request = client.post(f"/external/review/{token}/requests", data={"scope": "V|5.2", "request_text": "Please provide the most recent faculty approval minutes for this policy."})
        expect(evidence_request, 303, "external evidence request")

        external_after_feedback = client.get(f"/external/review/{token}")
        expect(external_after_feedback, 200, "external portal after feedback")
        require(external_after_feedback, "Evidence is clear", "reviewer comment visibility")
        require(external_after_feedback, "Please provide the most recent faculty approval minutes", "evidence request visibility")

        with db() as conn:
            request_row = rows(execute(conn, "SELECT * FROM nuvedra_external_evidence_requests WHERE invite_id=? ORDER BY id DESC LIMIT 1", (invite_id,)))[0]
            request_id = int(request_row["id"])
            actions = {str(x["action"]) for x in rows(execute(conn, "SELECT action FROM nuvedra_external_review_access_log WHERE invite_id=?", (invite_id,)))}
            required_actions = {"portal_view", "evidence_open", "comment_created", "evidence_request_created"}
            if not required_actions.issubset(actions):
                raise RuntimeError(f"External review audit log is missing actions: {required_actions - actions}")

        response = client.post(f"/faculty/programs/{program_id}/external-review/requests/{request_id}/status", data={
            "status": "addressed", "response_note": "Faculty approval minutes were added to the institutional evidence repository for follow-up review.",
        })
        expect(response, 303, "institution response to evidence request")
        external_after_response = client.get(f"/external/review/{token}")
        expect(external_after_response, 200, "external portal after institutional response")
        require(external_after_response, "Faculty approval minutes were added", "institution response visibility")
        require(external_after_response, "addressed", "addressed request state")

        portfolio_page = client.get(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}")
        expect(portfolio_page, 200, "frozen portfolio navigation")
        require(portfolio_page, 'data-external-review-link="v1"', "External Review portfolio navigation")
        draft_page = client.get(f"/faculty/programs/{program_id}/evidence/portfolios/{draft_portfolio_id}")
        expect(draft_page, 200, "draft portfolio page")
        if 'data-external-review-link="v1"' in draft_page.text:
            raise RuntimeError("Draft accreditation portfolio exposed an External Review action.")

        expect(client.get("/admin/logout"), 303, "admin logout")
        expect(client.get("/__smoke/external-review-user/reviewer"), 200, "internal reviewer session")
        expect(client.get(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/external-review"), 200, "internal reviewer read access")
        reviewer_write = client.post(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/external-review/invites", data={
            "reviewer_name": "Unauthorized Invite", "reviewer_email": "no@example.org", "organization": "No", "expires_at": "2030-01-01T00:00",
        })
        expect(reviewer_write, 403, "internal reviewer invitation mutation protection")

        expect(client.get("/__smoke/external-review-user/student"), 200, "student session")
        expect(client.get(f"/faculty/programs/{program_id}/evidence/portfolios/{portfolio_id}/external-review"), 403, "student management protection")

        # Restore coordinator session and revoke the capability link.
        expect(client.post("/admin/login", data={"email": "external.admin@example.com", "password": "Updated-External-2026!"}), 303, "coordinator relogin")
        revoke = client.post(f"/faculty/programs/{program_id}/external-review/invites/{invite_id}/revoke")
        expect(revoke, 303, "external review revocation")
        expect(client.get(f"/external/review/{token}"), 410, "revoked external review link")
        expect(client.get(f"/external/review/{token}/evidence/{version1_id}"), 410, "revoked evidence access")

    print("External Accreditation Review Portal v1 validated: frozen-only sharing, one-time token display, SHA-256 token storage, expiration controls, no-store/noindex external pages, pinned evidence isolation, reviewer comments, evidence requests and institutional responses, audit logging, reviewer/student permissions, portfolio navigation, and immediate revocation.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
