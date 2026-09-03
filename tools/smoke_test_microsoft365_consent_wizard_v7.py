from __future__ import annotations

import os
from pathlib import Path

DB_PATH = Path("/tmp/nuvedra-microsoft365-consent-wizard-v7-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "microsoft-v7-session-secret-123456"
os.environ["NEXUS_SESSION_SECRET"] = "microsoft-v7-admin-secret-123456"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "msv7.admin@example.edu"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Microsoft-V7-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Microsoft V7 Administrator"
os.environ["MICROSOFT_CLIENT_ID"] = "microsoft-v7-public-client-id"
os.environ["MICROSOFT_CLIENT_SECRET"] = "microsoft-v7-client-secret-never-render"
os.environ["MICROSOFT_TENANT_ID"] = "77777777-8888-9999-aaaa-bbbbbbbbbbbb"
os.environ["MICROSOFT_REDIRECT_URI"] = "https://nuvedra.example/auth/microsoft/callback"
os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"] = "microsoft-v7-token-encryption-key-never-render"
os.environ["MICROSOFT_REQUIRE_INSTITUTION_TENANT"] = "true"
os.environ["MICROSOFT_ALLOWED_DOMAINS"] = "example.edu"
os.environ["MICROSOFT_SCOPES"] = "openid profile email offline_access User.Read Files.Read Files.ReadWrite Sites.Read.All Calendars.ReadWrite User.ReadBasic.All Team.ReadBasic.All TeamMember.ReadWrite.All Channel.ReadBasic.All Channel.Create Team.Create EduRoster.ReadBasic EduAssignments.ReadBasic EduAssignments.ReadWrite"
os.environ["MICROSOFT_ALLOW_TEAM_CREATION"] = "false"
os.environ["MICROSOFT_ALLOW_EDUCATION_WRITES"] = "false"
os.environ["MICROSOFT_ALLOW_EDUCATION_PUBLISH"] = "false"
os.environ["MICROSOFT_ALLOW_GRADE_EXPORT"] = "false"
os.environ["MICROSOFT_ALLOW_GRADE_RETURN"] = "false"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.microsoft365_integration as m365  # noqa: E402
import app.microsoft365_production_v3 as production  # noqa: E402


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}.")


def main() -> None:
    graph_calls: list[tuple[str, str]] = []

    async def fake_graph_json(email: str, method: str, path: str, *, params=None, json_body=None):
        method = method.upper()
        graph_calls.append((method, path))
        if method != "GET":
            raise RuntimeError(f"Consent Wizard v7 must remain read-only: {method} {path}")
        if path == "/me":
            return {"id": "aad-admin-v7", "displayName": "Microsoft V7 Administrator", "mail": "msv7.admin@example.edu"}
        if path == "/organization":
            return {"value": [{
                "id": os.environ["MICROSOFT_TENANT_ID"],
                "displayName": "Example University",
                "verifiedDomains": [{"name": "example.edu", "isDefault": True}],
            }]}
        if path == "/me/drive/root":
            return {"id": "drive-root-v7", "name": "OneDrive", "webUrl": "https://example.sharepoint.com/personal/admin"}
        if path == "/sites/root":
            return {"id": "site-root-v7", "displayName": "Example University", "webUrl": "https://example.sharepoint.com"}
        if path == "/me/calendar":
            return {"id": "calendar-v7", "name": "Calendar"}
        if path == "/me/joinedTeams":
            return {"value": [{"id": "team-v7", "displayName": "Example Team"}]}
        raise RuntimeError(f"Unexpected Graph call: {method} {path} {params} {json_body}")

    async def fake_graph_collection(email: str, path: str, *, params=None):
        graph_calls.append(("GET_COLLECTION", path))
        if path == "/education/me/taughtClasses":
            return ([{"id": "education-class-v7", "displayName": "Example Education Class"}], 1)
        raise RuntimeError(f"Unexpected Graph collection call: {path} {params}")

    original_graph_json = m365._graph_json
    original_graph_collection = production._graph_collection
    m365._graph_json = fake_graph_json
    production._graph_collection = fake_graph_collection
    try:
        with TestClient(app, follow_redirects=False) as client:
            expect(client.post("/admin/login", data={"email": "msv7.admin@example.edu", "password": "Initial-Microsoft-V7-2026!"}), 303, "admin login")
            expect(client.post("/admin/password", data={"password": "Updated-Microsoft-V7-2026!", "confirm": "Updated-Microsoft-V7-2026!"}), 303, "admin password update")
            scopes = os.environ["MICROSOFT_SCOPES"]
            with db() as conn:
                m365._store_connection(
                    conn,
                    "msv7.admin@example.edu",
                    tenant_id=os.environ["MICROSOFT_TENANT_ID"],
                    account_id="aad-admin-v7",
                    display_name="Microsoft V7 Administrator",
                    access_token="microsoft-v7-access-token-never-render",
                    refresh_token="microsoft-v7-refresh-token-never-render",
                    expires_in=3600,
                    scopes=scopes,
                )

            page = client.get("/admin/microsoft365/consent-wizard")
            expect(page, 200, "consent wizard page")
            require(page, 'data-testid="microsoft365-consent-wizard-v7"', "consent wizard page")
            require(page, os.environ["MICROSOFT_REDIRECT_URI"], "redirect URI display")
            require(page, "adminconsent", "Microsoft admin-consent handoff")
            require(page, "EduAssignments.ReadWrite", "education write scope guidance")
            require(page, "MICROSOFT_ALLOW_GRADE_EXPORT=false", "safe Render template")
            forbidden = [
                os.environ["MICROSOFT_CLIENT_SECRET"],
                os.environ["MICROSOFT_TOKEN_ENCRYPTION_KEY"],
                "microsoft-v7-access-token-never-render",
                "microsoft-v7-refresh-token-never-render",
            ]
            if any(secret in page.text for secret in forbidden):
                raise RuntimeError("Consent Wizard v7 exposed Microsoft secret/token material.")

            expect(client.post("/admin/microsoft365/consent-wizard/probe"), 303, "read-only final verification")
            with db() as conn:
                snapshots = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_consent_wizard_snapshots ORDER BY id"))
                if len(snapshots) != 1:
                    raise RuntimeError("Consent Wizard v7 did not persist exactly one readiness snapshot.")
                first = snapshots[0]
                if first["readiness_status"] != "ready_for_governed_enablement":
                    raise RuntimeError(f"Expected ready_for_governed_enablement with write gates off: {first}")
                if first.get("missing_recommended_scopes"):
                    raise RuntimeError("Consent Wizard v7 incorrectly reported missing effective scopes.")
                checks = str(first.get("checks_json") or "")
                for marker in ("identity", "organization", "onedrive", "sharepoint", "calendar", "teams", "education"):
                    if marker not in checks:
                        raise RuntimeError(f"Consent Wizard v7 snapshot is missing {marker} probe evidence.")

            os.environ["MICROSOFT_ALLOW_EDUCATION_WRITES"] = "true"
            os.environ["MICROSOFT_ALLOW_EDUCATION_PUBLISH"] = "true"
            os.environ["MICROSOFT_ALLOW_GRADE_EXPORT"] = "true"
            expect(client.post("/admin/microsoft365/consent-wizard/probe"), 303, "governed write-enabled verification")
            with db() as conn:
                latest = rows(execute(conn, "SELECT * FROM nuvedra_microsoft_consent_wizard_snapshots ORDER BY id DESC LIMIT 1"))[0]
                if latest["readiness_status"] != "writes_enabled":
                    raise RuntimeError(f"Consent Wizard v7 did not reflect approved write gates: {latest}")

            if any(method in {"POST", "PUT", "PATCH", "DELETE"} for method, _path in graph_calls):
                raise RuntimeError("Consent Wizard v7 issued a Microsoft Graph write operation.")

        print("Microsoft 365 Production Configuration & Consent Wizard v7 validated: secret-safe Entra/Render guidance, tenant-specific admin-consent handoff, requested-vs-effective scope evidence, read-only OneDrive/SharePoint/Calendar/Teams/Education probes, governed write-gate states, snapshot persistence, and zero Microsoft Graph writes.", flush=True)
    finally:
        m365._graph_json = original_graph_json
        production._graph_collection = original_graph_collection
        if DB_PATH.exists():
            DB_PATH.unlink()


if __name__ == "__main__":
    main()
