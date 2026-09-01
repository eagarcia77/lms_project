from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

DB_PATH = Path("/tmp/nuvedra-lti13-advantage-v1-test.db")
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["APP_ENV"] = "development"
os.environ["APP_NAME"] = "NUVEDRA"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_SECRET"] = "lti13-session-secret-2026"
os.environ["NEXUS_SESSION_SECRET"] = "lti13-admin-secret-2026"
os.environ["NEXUS_BOOTSTRAP_ADMIN_EMAIL"] = "lti13.admin@example.com"
os.environ["NEXUS_BOOTSTRAP_ADMIN_PASSWORD"] = "Initial-LTI13-2026!"
os.environ["NEXUS_BOOTSTRAP_ADMIN_NAME"] = "LTI13 Administrator"
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)
os.environ.pop("NUVEDRA_LTI13_ISSUER", None)

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.admin_console import db, execute, rows, utcnow  # noqa: E402
from app.production_entry import app  # noqa: E402
import app.lti13_advantage as lti13  # noqa: E402

TOOL_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TOOL_KID = "nuvedra-smoke-tool-key"
TOOL_NUMBERS = TOOL_PRIVATE.public_key().public_numbers()


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


TOOL_JWK = {
    "kty": "RSA",
    "use": "sig",
    "alg": "RS256",
    "kid": TOOL_KID,
    "n": b64u(TOOL_NUMBERS.n.to_bytes((TOOL_NUMBERS.n.bit_length() + 7) // 8, "big")),
    "e": b64u(TOOL_NUMBERS.e.to_bytes((TOOL_NUMBERS.e.bit_length() + 7) // 8, "big")),
}
lti13._fetch_jwks = lambda _url: {"keys": [TOOL_JWK]}


@app.get("/__smoke/lti13-user/{kind}", include_in_schema=False)
async def smoke_lti13_user(kind: str, request: Request):
    users = {
        "instructor": {"id": "lti13-instructor", "name": "LTI13 Instructor", "email": "lti13.instructor@example.com"},
        "student": {"id": "lti13-student", "name": "LTI13 Student", "email": "lti13.student@example.com"},
        "observer": {"id": "lti13-observer", "name": "LTI13 Observer", "email": "lti13.observer@example.com"},
    }
    if kind not in users:
        raise RuntimeError("Unsupported LTI 1.3 smoke user.")
    request.session["user"] = users[kind]
    return {"ok": True}


def expect(response, status: int, label: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{label}: expected {status}, received {response.status_code}: {response.text[:1800]}")


def require(response, marker: str, label: str) -> None:
    if marker not in response.text:
        raise RuntimeError(f"{label} did not contain {marker!r}: {response.text[:1500]}")


def sign_tool(payload: dict) -> str:
    header = {"alg": "RS256", "typ": "JWT", "kid": TOOL_KID}
    encode = lambda value: b64u(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())
    signed = f"{encode(header)}.{encode(payload)}"
    signature = TOOL_PRIVATE.sign(signed.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return signed + "." + b64u(signature)


def hidden_value(html: str, name: str) -> str:
    match = re.search(rf'name="{re.escape(name)}" value="([^"]+)"', html)
    if not match:
        raise RuntimeError(f"Hidden form value {name!r} was not found.")
    import html as html_module
    return html_module.unescape(match.group(1))


def verify_platform_jwt(token: str, jwk: dict) -> dict:
    header, payload, signed, signature = lti13._jwt_parts(token)
    if header.get("kid") != jwk.get("kid"):
        raise RuntimeError("Platform JWT kid did not match JWKS.")
    lti13._rsa_public_key(jwk).verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
    return payload


def main() -> None:
    with TestClient(app, follow_redirects=False) as client:
        expect(client.post("/admin/login", data={"email": "lti13.admin@example.com", "password": "Initial-LTI13-2026!"}), 303, "admin login")
        expect(client.post("/admin/password", data={"password": "Updated-LTI13-2026!", "confirm": "Updated-LTI13-2026!"}), 303, "admin password update")
        created = client.post("/admin/authoring/courses", data={
            "course_code": "LTI3-7200", "title": "Modern Learning Interoperability", "description": "LTI 1.3 and Advantage validation.",
            "term": "Fall 2026", "instructor_email": "lti13.instructor@example.com", "template": "blank",
        })
        expect(created, 303, "course creation")
        course_id = int(created.headers["location"].rsplit("/", 1)[-1])
        now = utcnow()
        with db() as conn:
            execute(conn, "UPDATE nexus_admin_courses SET status='active',updated_at=? WHERE id=?", (now, course_id))
            for email, role in (("lti13.student@example.com", "student"), ("lti13.observer@example.com", "observer")):
                execute(conn, "INSERT INTO nexus_admin_enrollments (course_id,user_email,course_role,status,created_at) VALUES (?,?,?,?,?)", (course_id, email, role, "active", now))
            execute(conn, """INSERT INTO nexus_modules
                (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (course_id, "LTI Advantage Module", "Modern external tool resources.", "Use standards-based learning tools.", 45, 1, "published", now, now))
            module_id = int(rows(execute(conn, "SELECT id FROM nexus_modules WHERE course_id=?", (course_id,)))[0]["id"])

        expect(client.get("/__smoke/lti13-user/instructor"), 200, "instructor session")
        home = client.get(f"/faculty/studio/courses/{course_id}/lti13")
        expect(home, 200, "LTI 1.3 workspace")
        require(home, 'data-testid="lti13-advantage-v1"', "LTI 1.3 workspace")
        require(home, "does not claim 1EdTech certification", "LTI certification disclosure")

        registered = client.post(f"/faculty/studio/courses/{course_id}/lti13/tools", data={
            "title": "Modern Research Tool",
            "client_id": "nuvedra-modern-tool-client",
            "auth_login_url": "https://tool.example/oidc",
            "jwks_url": "https://tool.example/jwks",
            "redirect_uris": "https://tool.example/launch\nhttps://tool.example/deep",
            "target_link_uri": "https://tool.example/launch",
            "deep_link_url": "https://tool.example/deep",
        })
        expect(registered, 303, "LTI 1.3 tool registration")
        with db() as conn:
            tool = rows(execute(conn, "SELECT * FROM nuvedra_lti13_tools WHERE course_id=?", (course_id,)))[0]
            tool_id = int(tool["id"])
            deployment_id = str(tool["deployment_id"])

        resource_created = client.post(f"/faculty/studio/courses/{course_id}/lti13/resources", data={
            "tool_id": str(tool_id), "module_id": str(module_id), "title": "LTI 1.3 Research Activity",
            "target_link_uri": "", "points": "100", "custom_parameters": "mode=research\ncohort=fall-2026",
        })
        expect(resource_created, 303, "LTI 1.3 resource creation")
        with db() as conn:
            resource = rows(execute(conn, "SELECT * FROM nuvedra_lti13_resources WHERE tool_id=? ORDER BY id LIMIT 1", (tool_id,)))[0]
            resource_id = int(resource["id"]); item_id = int(resource["item_id"])
            lineitem_id = int(rows(execute(conn, "SELECT id FROM nuvedra_lti13_lineitems WHERE item_id=?", (item_id,)))[0]["id"])
            item = rows(execute(conn, "SELECT item_type,external_url,status,points FROM nexus_content_items WHERE id=?", (item_id,)))[0]
            if item.get("item_type") != "lti13" or item.get("external_url") != f"/learn/lti13/{resource_id}/login" or float(item.get("points") or 0) != 100:
                raise RuntimeError(f"LTI 1.3 content item linkage failed: {item}")
        expect(client.post(f"/faculty/studio/lti13/resources/{resource_id}/toggle"), 303, "LTI 1.3 resource publish")

        config = client.get("/lti13/config")
        expect(config, 200, "platform LTI configuration")
        if config.json().get("issuer") != "http://testserver":
            raise RuntimeError(f"Unexpected platform issuer: {config.json()}")
        jwks = client.get("/lti13/jwks")
        expect(jwks, 200, "platform JWKS")
        platform_jwk = jwks.json()["keys"][0]

        expect(client.get("/__smoke/lti13-user/student"), 200, "student session")
        student_item = client.get(f"/learn/items/{item_id}")
        expect(student_item, 303, "student LTI 1.3 item redirect")
        if student_item.headers.get("location") != f"/learn/lti13/{resource_id}/login":
            raise RuntimeError(f"LTI 1.3 item redirect is wrong: {student_item.headers.get('location')}")
        login = client.get(f"/learn/lti13/{resource_id}/login")
        expect(login, 303, "OIDC login initiation")
        parsed = urllib.parse.urlparse(login.headers["location"]); query = urllib.parse.parse_qs(parsed.query)
        if parsed.scheme != "https" or parsed.netloc != "tool.example" or query.get("iss") != ["http://testserver"]:
            raise RuntimeError(f"OIDC login initiation is invalid: {login.headers['location']}")
        hint = query["login_hint"][0]
        authorize = client.get("/lti13/authorize", params={
            "response_type": "id_token", "scope": "openid", "client_id": "nuvedra-modern-tool-client",
            "redirect_uri": "https://tool.example/launch", "login_hint": hint, "lti_message_hint": hint,
            "state": "state-student-1", "nonce": "nonce-student-1", "prompt": "none",
        })
        expect(authorize, 200, "OIDC authorization")
        id_token = hidden_value(authorize.text, "id_token")
        launch_claims = verify_platform_jwt(id_token, platform_jwk)
        if launch_claims.get(lti13.LTI_CLAIM + "message_type") != "LtiResourceLinkRequest":
            raise RuntimeError(f"Resource launch message type is wrong: {launch_claims}")
        if launch_claims.get("aud") != "nuvedra-modern-tool-client" or launch_claims.get("nonce") != "nonce-student-1":
            raise RuntimeError("Resource launch audience or nonce is incorrect.")
        if "lti13.student@example.com" in authorize.text or "email" in launch_claims:
            raise RuntimeError("LTI 1.3 launch leaked learner email while email sharing was disabled.")
        if "Learner" not in " ".join(launch_claims.get(lti13.LTI_CLAIM + "roles", [])):
            raise RuntimeError("LTI 1.3 learner role was not emitted.")
        ags_endpoint = launch_claims.get(lti13.AGS_CLAIM + "endpoint", {})
        if not ags_endpoint.get("lineitems") or not ags_endpoint.get("lineitem"):
            raise RuntimeError("LTI 1.3 launch did not advertise AGS endpoints.")
        expect(client.get("/lti13/authorize", params={
            "response_type": "id_token", "scope": "openid", "client_id": "nuvedra-modern-tool-client",
            "redirect_uri": "https://tool.example/launch", "login_hint": hint, "lti_message_hint": hint,
            "state": "state-replay", "nonce": "nonce-replay",
        }), 409, "OIDC login-hint replay protection")
        expect(client.post(f"/learn/items/{item_id}/complete", data={"completed": "1"}), 409, "LTI 1.3 manual completion block")

        expect(client.get("/__smoke/lti13-user/instructor"), 200, "instructor return session")
        deep_start = client.post(f"/faculty/studio/lti13/{tool_id}/deep-link", data={"module_id": str(module_id)})
        expect(deep_start, 303, "Deep Linking initiation")
        deep_query = urllib.parse.parse_qs(urllib.parse.urlparse(deep_start.headers["location"]).query)
        deep_hint = deep_query["login_hint"][0]
        deep_authorize = client.get("/lti13/authorize", params={
            "response_type": "id_token", "scope": "openid", "client_id": "nuvedra-modern-tool-client",
            "redirect_uri": "https://tool.example/deep", "login_hint": deep_hint, "lti_message_hint": deep_hint,
            "state": "state-deep-1", "nonce": "nonce-deep-1", "prompt": "none",
        })
        expect(deep_authorize, 200, "Deep Linking authorization")
        deep_request = verify_platform_jwt(hidden_value(deep_authorize.text, "id_token"), platform_jwk)
        settings = deep_request.get(lti13.DL_CLAIM + "deep_linking_settings", {})
        if deep_request.get(lti13.LTI_CLAIM + "message_type") != "LtiDeepLinkingRequest" or settings.get("data") != deep_hint:
            raise RuntimeError("Deep Linking request claims are invalid.")
        now_epoch = int(time.time())
        deep_response = sign_tool({
            "iss": "nuvedra-modern-tool-client", "aud": "http://testserver", "iat": now_epoch, "exp": now_epoch + 300,
            lti13.LTI_CLAIM + "message_type": "LtiDeepLinkingResponse",
            lti13.LTI_CLAIM + "version": lti13.LTI_VERSION,
            lti13.LTI_CLAIM + "deployment_id": deployment_id,
            lti13.DL_CLAIM + "data": deep_hint,
            lti13.DL_CLAIM + "content_items": [{
                "type": "ltiResourceLink", "title": "Deep Linked Simulation", "url": "https://tool.example/simulation",
                "custom": {"mode": "simulation"}, "lineItem": {"label": "Simulation Score", "scoreMaximum": 50, "resourceId": "simulation-1", "tag": "simulation"},
            }],
        })
        returned = client.post(f"/lti13/deep-link/return/{tool_id}", data={"JWT": deep_response})
        expect(returned, 303, "Deep Linking response")
        with db() as conn:
            deep_items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? AND title='Deep Linked Simulation'", (module_id,)))
            if len(deep_items) != 1 or deep_items[0].get("item_type") != "lti13" or deep_items[0].get("status") != "draft" or float(deep_items[0].get("points") or 0) != 50:
                raise RuntimeError(f"Deep Linking did not create the expected draft resource: {deep_items}")

        assertion_payload = {
            "iss": "nuvedra-modern-tool-client", "sub": "nuvedra-modern-tool-client",
            "aud": "http://testserver/lti13/token", "iat": now_epoch, "exp": now_epoch + 300, "jti": "assertion-jti-1",
        }
        assertion = sign_tool(assertion_payload)
        requested_scopes = " ".join([lti13.AGS_SCOPE_LINEITEM, lti13.AGS_SCOPE_LINEITEM_READ, lti13.AGS_SCOPE_RESULT, lti13.AGS_SCOPE_SCORE])
        token_response = client.post("/lti13/token", data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": requested_scopes,
        })
        expect(token_response, 200, "LTI Advantage access token")
        access_token = token_response.json()["access_token"]
        expect(client.post("/lti13/token", data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": requested_scopes,
        }), 401, "client assertion replay protection")
        headers = {"Authorization": f"Bearer {access_token}"}
        lineitems = client.get(f"/lti13/ags/tools/{tool_id}/lineitems", headers=headers)
        expect(lineitems, 200, "AGS line items")
        if not any(str(entry.get("id", "")).endswith(f"/{lineitem_id}") for entry in lineitems.json()):
            raise RuntimeError(f"AGS line item collection omitted the resource line item: {lineitems.json()}")
        user_id = lti13._subject("nuvedra-modern-tool-client", "lti13.student@example.com")
        score = client.post(f"/lti13/ags/lineitems/{lineitem_id}/scores", headers=headers, json={
            "userId": user_id, "scoreGiven": 92, "scoreMaximum": 100,
            "activityProgress": "Completed", "gradingProgress": "FullyGraded", "comment": "Standards-based score sync.",
        })
        expect(score, 200, "AGS score write")
        results = client.get(f"/lti13/ags/lineitems/{lineitem_id}/results", headers=headers)
        expect(results, 200, "AGS results")
        if not results.json() or float(results.json()[0].get("resultScore") or 0) != 92:
            raise RuntimeError(f"AGS result was not stored correctly: {results.json()}")
        with db() as conn:
            grades = rows(execute(conn, """SELECT g.points_awarded,g.graded_by FROM nuvedra_grades g
                JOIN nuvedra_submissions s ON s.id=g.submission_id WHERE s.item_id=? AND lower(s.student_email)=?""", (item_id, "lti13.student@example.com")))
            if len(grades) != 1 or abs(float(grades[0].get("points_awarded") or 0) - 92.0) > 0.001 or not str(grades[0].get("graded_by") or "").startswith("lti13:"):
                raise RuntimeError(f"AGS score did not synchronize to Gradebook: {grades}")
            progress = rows(execute(conn, "SELECT status FROM nuvedra_content_progress WHERE item_id=? AND lower(student_email)=?", (item_id, "lti13.student@example.com")))
            if not progress or progress[0].get("status") != "completed":
                raise RuntimeError(f"AGS completion did not synchronize to Student Experience: {progress}")

        expect(client.get("/__smoke/lti13-user/observer"), 200, "observer session")
        observer_login = client.get(f"/learn/lti13/{resource_id}/login")
        expect(observer_login, 303, "observer LTI 1.3 launch")
        expect(client.get(f"/faculty/studio/courses/{course_id}/lti13"), 403, "observer instructor-tool protection")

        expect(client.get("/__smoke/lti13-user/student"), 200, "student return session")
        expect(client.get(f"/faculty/studio/courses/{course_id}/lti13"), 403, "student instructor-tool protection")

    print("LTI 1.3 / Advantage v1 validated: platform JWKS, OIDC/JWT resource launch, nonce/state handling, one-time login hints, Deep Linking import, private-key JWT client authentication, AGS line items/scores/results, Gradebook/progress synchronization, privacy defaults, and role protection.", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if DB_PATH.exists():
            DB_PATH.unlink()
