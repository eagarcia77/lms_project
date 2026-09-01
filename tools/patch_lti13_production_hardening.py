from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/lti13_production_hardening_module.py.txt")
HARDENING = Path("app/lti13_production_hardening.py")
LTI13 = Path("app/lti13_advantage.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_LTI13_PRODUCTION_HARDENING_V1"


def _replace_function(text: str, name: str, replacement: str) -> str:
    start = text.find(f"def {name}(")
    if start < 0:
        raise RuntimeError(f"LTI 1.3 hardening could not find function {name}.")
    next_def = text.find("\ndef ", start + 1)
    if next_def < 0:
        raise RuntimeError(f"LTI 1.3 hardening could not find the end of function {name}.")
    return text[:start] + replacement.rstrip() + "\n\n" + text[next_def + 1:]


def patch_lti13_core() -> None:
    text = LTI13.read_text(encoding="utf-8")
    if TAG in text:
        return
    if "import socket\n" not in text:
        text = text.replace("import secrets\n", "import secrets\nimport socket\n", 1)
    text = text.replace(
        "ALLOWED_SCOPES = {AGS_SCOPE_LINEITEM, AGS_SCOPE_LINEITEM_READ, AGS_SCOPE_RESULT, AGS_SCOPE_SCORE}\n",
        "ALLOWED_SCOPES = {AGS_SCOPE_LINEITEM, AGS_SCOPE_LINEITEM_READ, AGS_SCOPE_RESULT, AGS_SCOPE_SCORE}\nMAX_JWKS_BYTES = 512 * 1024\nMAX_JWKS_KEYS = 25\nJWT_CLOCK_SKEW_SECONDS = 30\nJWT_MAX_LIFETIME_SECONDS = 600\n# NUVEDRA_LTI13_PRODUCTION_HARDENING_V1\n",
        1,
    )

    text = _replace_function(text, "_platform_issuer", '''def _platform_issuer(request: Request) -> str:
    configured = os.getenv("NUVEDRA_LTI13_ISSUER", "").strip().rstrip("/")
    if configured:
        parsed = urllib.parse.urlparse(configured)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise HTTPException(500, "NUVEDRA_LTI13_ISSUER must be a canonical HTTPS origin without a path, query, fragment, or embedded credentials.")
        return configured
    origin = str(request.base_url).rstrip("/")
    parsed = urllib.parse.urlparse(origin)
    environment = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    if environment in {"production", "prod"} and parsed.scheme != "https":
        raise HTTPException(500, "LTI 1.3 production traffic requires HTTPS. Configure NUVEDRA_LTI13_ISSUER when the public origin cannot be inferred securely.")
    return origin''')

    text = _replace_function(text, "_absolute", '''def _absolute(request: Request, path: str) -> str:
    if not path.startswith("/"):
        raise ValueError("LTI 1.3 platform paths must be absolute application paths.")
    return _platform_issuer(request) + path''')

    helper_anchor = "def _fetch_jwks(url: str) -> dict[str, Any]:\n"
    if helper_anchor not in text:
        raise RuntimeError("LTI 1.3 hardening could not find the JWKS retrieval anchor.")
    dns_helper = '''def _assert_public_destination(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = str(parsed.hostname or "")
    port = parsed.port or 443
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(502, "Unable to resolve the external tool host.") from exc
    if not answers:
        raise HTTPException(502, "Unable to resolve the external tool host.")
    for answer in answers:
        address = str(answer[4][0]).split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise HTTPException(502, "External tool DNS resolution returned an invalid address.") from exc
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise HTTPException(400, "External tool endpoints cannot resolve to private, local, reserved, multicast, or unspecified addresses.")


'''
    text = text.replace(helper_anchor, dns_helper + helper_anchor, 1)

    text = _replace_function(text, "_fetch_jwks", '''def _fetch_jwks(url: str) -> dict[str, Any]:
    safe = _safe_https_url(url, "JWKS URL")
    _assert_public_destination(safe)
    timeout = httpx.Timeout(5.0, connect=3.0, read=5.0, write=5.0, pool=3.0)
    limits = httpx.Limits(max_connections=5, max_keepalive_connections=2)
    try:
        with httpx.Client(timeout=timeout, limits=limits, follow_redirects=False, trust_env=False, headers={"Accept": "application/json"}) as client:
            response = client.get(safe)
            response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and int(declared) > MAX_JWKS_BYTES:
                raise HTTPException(502, "External tool JWKS response is too large.")
            raw = response.content
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, "Unable to retrieve the external tool JWKS.") from exc
    if len(raw) > MAX_JWKS_BYTES:
        raise HTTPException(502, "External tool JWKS response is too large.")
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise HTTPException(502, "External tool JWKS is not valid JSON.") from exc
    keys = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(keys, list) or not keys or len(keys) > MAX_JWKS_KEYS or not all(isinstance(key, dict) for key in keys):
        raise HTTPException(502, "External tool JWKS is invalid or exceeds the supported key count.")
    return data''')

    text = _replace_function(text, "_rsa_public_key", '''def _rsa_public_key(jwk: dict[str, Any]):
    if jwk.get("kty") != "RSA" or not jwk.get("n") or not jwk.get("e"):
        raise HTTPException(401, "Unsupported external tool signing key.")
    if jwk.get("alg") not in (None, "", "RS256") or jwk.get("use") not in (None, "", "sig"):
        raise HTTPException(401, "External tool signing key is not authorized for RS256 signatures.")
    key_ops = jwk.get("key_ops")
    if key_ops is not None and (not isinstance(key_ops, list) or "verify" not in key_ops):
        raise HTTPException(401, "External tool signing key does not permit signature verification.")
    if any(jwk.get(name) not in (None, "") for name in ("d", "p", "q", "dp", "dq", "qi")):
        raise HTTPException(401, "External JWKS must not expose RSA private-key material.")
    try:
        n = int.from_bytes(_b64ud(str(jwk["n"])), "big")
        e = int.from_bytes(_b64ud(str(jwk["e"])), "big")
    except Exception as exc:
        raise HTTPException(401, "External tool RSA key is malformed.") from exc
    if n.bit_length() < 2048 or e < 3 or e % 2 == 0:
        raise HTTPException(401, "External tool RSA key does not meet minimum signing-key requirements.")
    try:
        return rsa.RSAPublicNumbers(e, n).public_key()
    except Exception as exc:
        raise HTTPException(401, "External tool RSA key is invalid.") from exc''')

    text = _replace_function(text, "_verify_tool_jwt", '''def _verify_tool_jwt(token: str, tool: dict[str, Any], *, audience: str, issuer: str | None = None) -> dict[str, Any]:
    header, payload, signed, signature = _jwt_parts(token)
    if header.get("alg") != "RS256":
        raise HTTPException(401, "Only RS256 tool assertions are supported.")
    kid = str(header.get("kid") or "").strip()
    if not kid or len(kid) > 255:
        raise HTTPException(401, "External tool JWT must include a valid kid header.")
    keys = _fetch_jwks(str(tool["jwks_url"])).get("keys", [])
    candidates = [key for key in keys if str(key.get("kid") or "") == kid]
    if len(candidates) != 1:
        raise HTTPException(401, "External tool signing key was not found uniquely by kid.")
    key = candidates[0]
    try:
        _rsa_public_key(key).verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(401, "External tool JWT signature is invalid.") from exc
    now = int(time.time())
    try:
        exp = int(payload.get("exp"))
        iat = int(payload.get("iat"))
        nbf = int(payload.get("nbf")) if payload.get("nbf") is not None else iat
    except Exception as exc:
        raise HTTPException(401, "External tool JWT must include valid iat and exp timestamps.") from exc
    if exp <= now - JWT_CLOCK_SKEW_SECONDS or exp > now + JWT_MAX_LIFETIME_SECONDS:
        raise HTTPException(401, "External tool JWT expiration is invalid.")
    if iat > now + JWT_CLOCK_SKEW_SECONDS or iat < now - JWT_MAX_LIFETIME_SECONDS:
        raise HTTPException(401, "External tool JWT issued-at time is invalid.")
    if nbf > now + JWT_CLOCK_SKEW_SECONDS:
        raise HTTPException(401, "External tool JWT is not yet valid.")
    if exp <= iat or exp - iat > JWT_MAX_LIFETIME_SECONDS:
        raise HTTPException(401, "External tool JWT lifetime is invalid.")
    if issuer is not None and str(payload.get("iss") or "") != issuer:
        raise HTTPException(401, "External tool JWT issuer is invalid.")
    if not _audience_matches(payload.get("aud"), audience):
        raise HTTPException(401, "External tool JWT audience is invalid.")
    return payload''')

    prune_anchor = "def _lineitem_json(request: Request, row: dict[str, Any]) -> dict[str, Any]:\n"
    if prune_anchor not in text:
        raise RuntimeError("LTI 1.3 hardening could not locate the AGS helper anchor.")
    prune_helper = '''def _prune_security_state(conn: Any) -> None:
    now = datetime.now(timezone.utc).isoformat()
    execute(conn, "DELETE FROM nuvedra_lti13_tokens WHERE expires_at < ?", (now,))
    execute(conn, "DELETE FROM nuvedra_lti13_assertion_jtis WHERE expires_at < ?", (now,))


'''
    text = text.replace(prune_anchor, prune_helper + prune_anchor, 1)

    old_requested = '''            requested = set(scope.split()) & ALLOWED_SCOPES
            if not requested: raise HTTPException(400, "No supported LTI Advantage scope was requested.")
            now = datetime.now(timezone.utc); expires = datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc)
'''
    new_requested = '''            requested = set(scope.split())
            if not requested: raise HTTPException(400, "No LTI Advantage scope was requested.")
            unsupported = requested - ALLOWED_SCOPES
            if unsupported: raise HTTPException(400, "One or more requested LTI Advantage scopes are not supported.")
            _prune_security_state(conn)
            now = datetime.now(timezone.utc); expires = datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc)
'''
    if old_requested not in text:
        raise RuntimeError("LTI 1.3 hardening could not patch token scope validation.")
    text = text.replace(old_requested, new_requested, 1)

    score_anchor = '''        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "scoreGiven and scoreMaximum must be numeric when supplied.") from exc
        with db() as conn:
'''
    score_new = '''        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "scoreGiven and scoreMaximum must be numeric when supplied.") from exc
        if maximum is not None and maximum <= 0:
            raise HTTPException(400, "scoreMaximum must be greater than zero.")
        if given is not None and given < 0:
            raise HTTPException(400, "scoreGiven cannot be negative.")
        if given is not None and maximum is not None and given > maximum:
            raise HTTPException(400, "scoreGiven cannot exceed scoreMaximum.")
        with db() as conn:
'''
    if score_anchor not in text:
        raise RuntimeError("LTI 1.3 hardening could not patch AGS score range validation.")
    text = text.replace(score_anchor, score_new, 1)

    score_identity_anchor = '''            lineitem = _lineitem(conn, lineitem_id)
            if token.get("client_id") != lineitem.get("client_id"): raise HTTPException(403, "Token does not belong to this line item.")
            now = utcnow(); activity = str(body.get("activityProgress") or ""); grading = str(body.get("gradingProgress") or ""); comment = str(body.get("comment") or "")[:4000]; timestamp = str(body.get("timestamp") or now)[:120]
'''
    score_identity_new = '''            lineitem = _lineitem(conn, lineitem_id)
            if token.get("client_id") != lineitem.get("client_id"): raise HTTPException(403, "Token does not belong to this line item.")
            if _student_email_for_subject(conn, int(lineitem["course_id"]), str(lineitem["client_id"]), user_id) is None:
                raise HTTPException(400, "AGS userId does not resolve to an active student in this course.")
            now = utcnow(); activity = str(body.get("activityProgress") or ""); grading = str(body.get("gradingProgress") or ""); comment = str(body.get("comment") or "")[:4000]; timestamp = str(body.get("timestamp") or now)[:120]
            if activity not in {"Initialized", "Started", "InProgress", "Submitted", "Completed"}:
                raise HTTPException(400, "Unsupported AGS activityProgress value.")
            if grading not in {"NotReady", "Failed", "Pending", "PendingManual", "FullyGraded"}:
                raise HTTPException(400, "Unsupported AGS gradingProgress value.")
'''
    if score_identity_anchor not in text:
        raise RuntimeError("LTI 1.3 hardening could not patch AGS learner and progress validation.")
    text = text.replace(score_identity_anchor, score_identity_new, 1)

    LTI13.write_text(text, encoding="utf-8")


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.lti13_production_hardening import register_lti13_production_hardening\n"
    if import_line not in text:
        anchor = "from app.lti13_advantage import register_lti13_advantage\n"
        if anchor not in text:
            raise RuntimeError("LTI 1.3 hardening could not locate the LTI 1.3 portal import.")
        text = text.replace(anchor, anchor + import_line, 1)
    registration = "    register_lti13_production_hardening(app)\n"
    if registration not in text:
        anchor = "    register_lti13_advantage(app)\n"
        if anchor not in text:
            raise RuntimeError("LTI 1.3 hardening could not locate the LTI 1.3 portal registration.")
        text = text.replace(anchor, anchor + registration, 1)
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_LTI13_PRODUCTION_HARDENING_V1
  function initializeLti13SecurityLink() {
    const root = document.querySelector('[data-testid="lti13-advantage-v1"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)\/lti13$/);
    if (!root || !match || root.querySelector('[data-lti13-security-link]')) return;
    const hero = root.querySelector('.studio-hero');
    if (!hero) return;
    let actions = hero.querySelector('.studio-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'studio-actions';
      hero.appendChild(actions);
    }
    const link = document.createElement('a');
    link.className = 'studio-button studio-button--quiet';
    link.href = `/faculty/studio/courses/${match[1]}/lti13/security`;
    link.dataset.lti13SecurityLink = 'v1';
    link.dataset.i18nEn = 'Security status';
    link.dataset.i18nEs = 'Estado de seguridad';
    link.textContent = language() === 'es' ? 'Estado de seguridad' : 'Security status';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("LTI 1.3 hardening could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeLti13SecurityLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("LTI 1.3 hardening could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeLti13SecurityLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file() or not LTI13.is_file():
        raise RuntimeError("LTI 1.3 production hardening requires the LTI 1.3 / Advantage v1 generated module.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(HARDENING), "exec")
    HARDENING.write_text(source, encoding="utf-8")
    patch_lti13_core()
    patch_academic_portal()
    patch_studio_js()
    compile(LTI13.read_text(encoding="utf-8"), str(LTI13), "exec")
    compile(HARDENING.read_text(encoding="utf-8"), str(HARDENING), "exec")
    print("NUVEDRA LTI 1.3 production hardening installed: canonical-origin controls, outbound JWKS defenses, stricter JWT validation, scoped token hygiene, AGS learner validation, and security-status tooling.", flush=True)


if __name__ == "__main__":
    main()
