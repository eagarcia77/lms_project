from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException

DB_PATH = Path("/tmp/nuvedra-lti13-hardening-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "lti13-hardening-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "lti13-hardening-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "hardening.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-Hardening-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "Hardening Administrator"
os.environ["NUVEDRA_LTI13_ISSUER"] = "https://nuvedra.example"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.lti13_advantage as lti13  # noqa: E402

TOOL_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TOOL_KID = "hardening-tool-key"
NUMBERS = TOOL_PRIVATE.public_key().public_numbers()


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


TOOL_JWK = {
    "kty": "RSA", "use": "sig", "alg": "RS256", "kid": TOOL_KID,
    "n": b64u(NUMBERS.n.to_bytes((NUMBERS.n.bit_length() + 7) // 8, "big")),
    "e": b64u(NUMBERS.e.to_bytes((NUMBERS.e.bit_length() + 7) // 8, "big")),
}


def sign(payload: dict, *, include_kid: bool = True) -> str:
    header = {"alg": "RS256", "typ": "JWT"}
    if include_kid:
        header["kid"] = TOOL_KID
    encode = lambda value: b64u(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())
    signed = f"{encode(header)}.{encode(payload)}"
    signature = TOOL_PRIVATE.sign(signed.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return signed + "." + b64u(signature)


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}: {response.text[:1600]}")


def expect_http(callable_obj, status: int, label: str) -> None:
    try:
        callable_obj()
    except HTTPException as exc:
        if exc.status_code != status:
            raise RuntimeError(f"{label}: expected HTTP {status}, received {exc.status_code}: {exc.detail}") from exc
    else:
        raise RuntimeError(f"{label}: expected HTTP {status} but no exception was raised.")


def main() -> None:
    original_fetch = lti13._fetch_jwks
    original_dns = lti13.socket.getaddrinfo
    try:
        with TestClient(app, follow_redirects=False) as client:
            expect(client.post("/admin/login", data={"email": "hardening.admin@example.com", "password": "Initial-Hardening-2026!"}), 303, "admin login")
            expect(client.post("/admin/password", data={"password": "Updated-Hardening-2026!", "confirm": "Updated-Hardening-2026!"}), 303, "admin password update")
            created = client.post("/admin/authoring/courses", data={
                "course_code": "LTIH-7300", "title": "LTI Production Security", "description": "Production hardening validation.",
                "term": "Fall 2026", "instructor_email": "hardening.admin@example.com", "template": "blank",
            })
            expect(created, 303, "course creation")
            course_id = int(created.headers["location"].rsplit("/", 1)[-1])
            now = utcnow()
            with db() as conn:
                execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
                execute(conn, """INSERT INTO nexus_modules
                    (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "Security Module", "Hardening tests.", "Validate secure interoperability.", 30, 1, "published", now, now))

            config = client.get("/lti13/config")
            expect(config, 200, "canonical issuer config")
            if config.json().get("issuer") != "https://nuvedra.example" or config.json().get("token_endpoint") != "https://nuvedra.example/lti13/token":
                raise RuntimeError(f"Canonical LTI issuer was not applied: {config.json()}")

            security = client.get(f"/faculty/studio/courses/{course_id}/lti13/security")
            expect(security, 200, "hardening security dashboard")
            require(security, 'data-testid="lti13-production-hardening"', "hardening security dashboard")
            require(security, "NUVEDRA_LTI13_ISSUER", "hardening security dashboard")
            require(security, "DNS destination checks", "hardening security dashboard")

            expect_http(lambda: lti13._safe_https_url("https://127.0.0.1/jwks", "JWKS URL"), 400, "literal private-address rejection")
            lti13.socket.getaddrinfo = lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))]
            expect_http(lambda: lti13._assert_public_destination("https://tool.example/jwks"), 400, "DNS private-address rejection")
            lti13.socket.getaddrinfo = original_dns

            weak = rsa.generate_private_key(public_exponent=65537, key_size=1024).public_key().public_numbers()
            weak_jwk = {
                "kty": "RSA", "use": "sig", "alg": "RS256", "kid": "weak",
                "n": b64u(weak.n.to_bytes((weak.n.bit_length() + 7) // 8, "big")),
                "e": b64u(weak.e.to_bytes((weak.e.bit_length() + 7) // 8, "big")),
            }
            expect_http(lambda: lti13._rsa_public_key(weak_jwk), 401, "weak RSA key rejection")
            private_jwk = dict(TOOL_JWK); private_jwk["d"] = "not-allowed"
            expect_http(lambda: lti13._rsa_public_key(private_jwk), 401, "private JWK material rejection")

            lti13._fetch_jwks = lambda _url: {"keys": [TOOL_JWK]}
            now_epoch = int(time.time())
            tool_stub = {"jwks_url": "https://tool.example/jwks"}
            no_kid = sign({"iss": "hardening-client", "aud": "https://nuvedra.example/lti13/token", "iat": now_epoch, "exp": now_epoch + 300}, include_kid=False)
            expect_http(lambda: lti13._verify_tool_jwt(no_kid, tool_stub, audience="https://nuvedra.example/lti13/token", issuer="hardening-client"), 401, "JWT kid requirement")
            old = sign({"iss": "hardening-client", "aud": "https://nuvedra.example/lti13/token", "iat": now_epoch - 1200, "exp": now_epoch + 60})
            expect_http(lambda: lti13._verify_tool_jwt(old, tool_stub, audience="https://nuvedra.example/lti13/token", issuer="hardening-client"), 401, "JWT bounded lifetime")

            with db() as conn:
                tool_id = int(execute(conn, """INSERT INTO nuvedra_lti13_tools
                    (course_id,title,client_id,auth_login_url,jwks_url,redirect_uris,target_link_uri,deep_link_url,deployment_id,share_email,status,created_by,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,0,'active',?,?,?)""", (
                        course_id, "Hardening Tool", "hardening-client", "https://tool.example/oidc", "https://tool.example/jwks",
                        "https://tool.example/launch", "https://tool.example/launch", None, "hardening-deployment",
                        "hardening.admin@example.com", now, now,
                    )).lastrowid)
                lineitem_id = int(execute(conn, """INSERT INTO nuvedra_lti13_lineitems
                    (tool_id,course_id,item_id,label,score_maximum,resource_id,tag,created_at,updated_at)
                    VALUES (?,?,NULL,?,?,?,? ,?,?)""", (tool_id, course_id, "Hardening Score", 100, "hardening-resource", "security", now, now)).lastrowid)

            assertion = sign({
                "iss": "hardening-client", "sub": "hardening-client", "aud": "https://nuvedra.example/lti13/token",
                "iat": now_epoch, "exp": now_epoch + 300, "jti": "hardening-jti-1",
            })
            invalid_scope = client.post("/lti13/token", data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion,
                "scope": lti13.AGS_SCOPE_SCORE + " urn:example:unsupported",
            })
            expect(invalid_scope, 400, "unsupported OAuth scope rejection")

            assertion2 = sign({
                "iss": "hardening-client", "sub": "hardening-client", "aud": "https://nuvedra.example/lti13/token",
                "iat": now_epoch, "exp": now_epoch + 300, "jti": "hardening-jti-2",
            })
            token_response = client.post("/lti13/token", data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion2,
                "scope": lti13.AGS_SCOPE_SCORE,
            })
            expect(token_response, 200, "valid hardened token request")
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise RuntimeError("Hardened token endpoint did not return an access token.")

            unknown_score = client.post(
                f"/lti13/ags/lineitems/{lineitem_id}/scores",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "userId": "unknown-pseudonymous-student", "scoreGiven": 90, "scoreMaximum": 100,
                    "activityProgress": "Completed", "gradingProgress": "FullyGraded",
                },
            )
            expect(unknown_score, 400, "unknown AGS learner rejection")

            out_of_range = client.post(
                f"/lti13/ags/lineitems/{lineitem_id}/scores",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "userId": "unknown-pseudonymous-student", "scoreGiven": 110, "scoreMaximum": 100,
                    "activityProgress": "Completed", "gradingProgress": "FullyGraded",
                },
            )
            expect(out_of_range, 400, "out-of-range AGS score rejection")

        print("LTI 1.3 production hardening validated: canonical issuer, security dashboard, private-address defenses, RSA/JWT constraints, exact OAuth scopes, token issuance, and AGS learner/score validation.", flush=True)
    finally:
        lti13._fetch_jwks = original_fetch
        lti13.socket.getaddrinfo = original_dns
        if DB_PATH.exists():
            DB_PATH.unlink()


if __name__ == "__main__":
    main()
