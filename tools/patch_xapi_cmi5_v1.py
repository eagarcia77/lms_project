from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/xapi_cmi5_module.py.txt")
MODULE = Path("app/xapi_cmi5.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
COURSE_EDITOR = Path("app/course_editor_access.py")
COURSE_COPY_IMPORT = Path("app/course_copy_import.py")
TAG = "NUVEDRA_XAPI_CMI5_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"xAPI & cmi5 v1 could not find {label}: {old[:180]!r}")
    return text.replace(old, new, 1)


def patch_generated_module() -> None:
    text = MODULE.read_text(encoding="utf-8")
    old_absolute = '''def _absolute(request: Request, path: str) -> str:\n    origin = (os.getenv("NUVEDRA_XAPI_ENDPOINT") or "").strip().rstrip("/")\n    if origin:\n        parsed = urllib.parse.urlparse(origin)\n        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:\n            raise HTTPException(500, "NUVEDRA_XAPI_ENDPOINT must be a canonical HTTPS origin.")\n        return origin + path\n    return str(request.base_url).rstrip("/") + path\n'''
    new_absolute = '''def _absolute(request: Request, path: str) -> str:\n    origin = (os.getenv("NUVEDRA_XAPI_ENDPOINT") or "").strip().rstrip("/")\n    if origin:\n        parsed = urllib.parse.urlparse(origin)\n        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:\n            raise HTTPException(500, "NUVEDRA_XAPI_ENDPOINT must be a canonical HTTPS origin without a path, query, fragment, or embedded credentials.")\n        return origin + path\n    inferred = str(request.base_url).rstrip("/")\n    parsed = urllib.parse.urlparse(inferred)\n    environment = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()\n    if environment in {"production", "prod"} and parsed.scheme != "https":\n        raise HTTPException(500, "xAPI/cmi5 production traffic requires HTTPS. Configure NUVEDRA_XAPI_ENDPOINT when the public origin cannot be inferred securely.")\n    return inferred + path\n'''
    text = replace_once(text, old_absolute, new_absolute, "canonical xAPI origin")

    old_rows = '''        source_rows = "".join(f\'\'\'<tr><td>{academic_access.esc(s.get(\'name\'))}</td><td><code>{academic_access.esc(s.get(\'client_key\'))}</code></td><td>{academic_access.esc(s.get(\'status\'))}</td><td>{academic_access.esc(s.get(\'last_used_at\') or \'Never\')}</td></tr>\'\'\' for s in sources) or \'<tr><td colspan="4">No external xAPI sources yet.</td></tr>\'\n'''
    new_rows = '''        source_rows = "".join(f\'\'\'<tr><td>{academic_access.esc(s.get(\'name\'))}</td><td><code>{academic_access.esc(s.get(\'client_key\'))}</code></td><td>{academic_access.esc(s.get(\'status\'))}</td><td>{academic_access.esc(s.get(\'last_used_at\') or \'Never\')}</td><td><form method="post" action="{STUDIO_PREFIX}/xapi/sources/{int(s[\'id\'])}/toggle"><button class="studio-button studio-button--quiet">{\'Disable\' if s.get(\'status\') == \'active\' else \'Enable\'}</button></form></td></tr>\'\'\' for s in sources) or \'<tr><td colspan="5">No external xAPI sources yet.</td></tr>\'\n'''
    text = replace_once(text, old_rows, new_rows, "xAPI source revocation controls")
    old_header = '<tr><th>Source</th><th>Client key</th><th>Status</th><th>Last used</th></tr>'
    new_header = '<tr><th>Source</th><th>Client key</th><th>Status</th><th>Last used</th><th>Action</th></tr>'
    text = replace_once(text, old_header, new_header, "xAPI source action column")

    route_anchor = '''    @app.post(f"{STUDIO_PREFIX}/courses/{{course_id}}/xapi/cmi5", response_model=None)\n'''
    route_block = '''    @app.post(f"{STUDIO_PREFIX}/xapi/sources/{{source_id}}/toggle", response_model=None)\n    async def toggle_xapi_source(source_id: int, request: Request):\n        user = _user(request, "/portal")\n        if isinstance(user, RedirectResponse): return user\n        with db() as conn:\n            found = rows(execute(conn, "SELECT * FROM nuvedra_xapi_sources WHERE id=?", (source_id,)))\n            if not found: raise HTTPException(404, "xAPI source credential not found.")\n            source = found[0]\n            _course_author(conn, int(source["course_id"]), user["email"])\n            new_status = "disabled" if str(source.get("status")) == "active" else "active"\n            execute(conn, "UPDATE nuvedra_xapi_sources SET status=? WHERE id=?", (new_status, source_id))\n            audit(conn, user["email"], "xapi_source_status_changed", "xapi_source", str(source_id), new_status, request.client.host if request.client else "")\n        return RedirectResponse(f"{STUDIO_PREFIX}/courses/{int(source['course_id'])}/xapi", status_code=303)\n\n'''
    if route_block not in text:
        if route_anchor not in text:
            raise RuntimeError("xAPI & cmi5 v1 could not locate the source-toggle route anchor.")
        text = text.replace(route_anchor, route_block + route_anchor, 1)
    MODULE.write_text(text, encoding="utf-8")


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.xapi_cmi5 import register_xapi_cmi5\n"
    if import_line not in text:
        anchors = (
            "from app.lti13_production_hardening import register_lti13_production_hardening\n",
            "from app.lti13_advantage import register_lti13_advantage\n",
            "from app.interoperability import register_interoperability\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("xAPI & cmi5 v1 could not locate an academic portal import anchor.")
    registration = "    register_xapi_cmi5(app)\n"
    if registration not in text:
        anchors = (
            "    register_lti13_production_hardening(app)\n",
            "    register_lti13_advantage(app)\n",
            "    register_interoperability(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("xAPI & cmi5 v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_XAPI_CMI5_V1
  function initializeXapiCmi5Link() {
    const root = document.querySelector('[data-testid="visual-course-studio"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!root || !match || root.querySelector('[data-xapi-cmi5-link]')) return;
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
    link.href = `/faculty/studio/courses/${match[1]}/xapi`;
    link.dataset.xapiCmi5Link = 'v1';
    link.dataset.i18nEn = 'xAPI & cmi5';
    link.dataset.i18nEs = 'xAPI y cmi5';
    link.textContent = language() === 'es' ? 'xAPI y cmi5' : 'xAPI & cmi5';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("xAPI & cmi5 v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeXapiCmi5Link();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("xAPI & cmi5 v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeXapiCmi5Link();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def patch_student_experience() -> None:
    if not STUDENT_EXPERIENCE.is_file():
        raise RuntimeError("xAPI & cmi5 v1 requires the generated Student Experience v2 module.")
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    redirect_anchor = '            if str(item.get("item_type")) == "lti13" and item.get("external_url"): return RedirectResponse(str(item.get("external_url")),status_code=303)\n'
    redirect_new = '            if str(item.get("item_type")) == "cmi5" and item.get("external_url"): return RedirectResponse(str(item.get("external_url")),status_code=303)\n' + redirect_anchor
    text = replace_once(text, redirect_anchor, redirect_new, "cmi5 student launch redirect")
    completion_anchor = '            if str(item.get("item_type")) == "lti13": raise HTTPException(409,"LTI 1.3 completion is determined by the external tool and AGS activity state.")\n'
    completion_new = '            if str(item.get("item_type")) == "cmi5": raise HTTPException(409,"cmi5 completion is determined by xAPI activity state and MoveOn rules.")\n' + completion_anchor
    text = replace_once(text, completion_anchor, completion_new, "cmi5 managed completion")
    STUDENT_EXPERIENCE.write_text(text, encoding="utf-8")


def patch_course_editor() -> None:
    text = COURSE_EDITOR.read_text(encoding="utf-8")
    anchor = '    "lti13": "LTI 1.3 / Advantage tool",\n'
    new = anchor + '    "cmi5": "cmi5 / xAPI activity",\n'
    text = replace_once(text, anchor, new, "Course Studio cmi5 item type")
    COURSE_EDITOR.write_text(text, encoding="utf-8")


def patch_course_copy_import() -> None:
    if not COURSE_COPY_IMPORT.is_file():
        raise RuntimeError("xAPI & cmi5 v1 requires the generated Course Copy & Import v1 module.")
    text = COURSE_COPY_IMPORT.read_text(encoding="utf-8")
    helper_anchor = "def _copy_content(\n"
    helper = '''def _copy_cmi5_au(conn: Any, source_item_id: int, target_course_id: int, target_module_id: int, target_item_id: int, actor: str) -> None:
    found = rows(execute(conn, "SELECT * FROM nuvedra_cmi5_aus WHERE item_id=?", (source_item_id,)))
    if not found:
        return
    source = found[0]
    now = utcnow()
    new_au_id = _insert_id(conn, """INSERT INTO nuvedra_cmi5_aus
        (course_id,module_id,item_id,title,launch_url,activity_id,move_on,mastery_score,status,created_by,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?, 'draft',?,?,?)""", (
            target_course_id, target_module_id, target_item_id, source.get("title"), source.get("launch_url"),
            source.get("activity_id"), source.get("move_on") or "CompletedOrPassed", source.get("mastery_score"),
            actor, now, now,
        ))
    execute(conn, "UPDATE nexus_content_items SET external_url=?,status='draft',updated_at=? WHERE id=?", (
        f"/learn/cmi5/{new_au_id}/launch", now, target_item_id,
    ))


'''
    if "def _copy_cmi5_au(" not in text:
        if helper_anchor not in text:
            raise RuntimeError("xAPI & cmi5 v1 could not locate the course-copy helper anchor.")
        text = text.replace(helper_anchor, helper + helper_anchor, 1)
    call_anchor = "            _copy_library_use(conn, source_item_id, target_course_id, target_module_id, target_item_id, actor)\n"
    call_new = call_anchor + "            if str(source_item.get(\"item_type\") or \"\") == \"cmi5\":\n                _copy_cmi5_au(conn, source_item_id, target_course_id, target_module_id, target_item_id, actor)\n"
    text = replace_once(text, call_anchor, call_new, "cmi5 course-copy association")
    COURSE_COPY_IMPORT.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("xAPI & cmi5 v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_generated_module()
    patch_academic_portal()
    patch_studio_js()
    patch_student_experience()
    patch_course_editor()
    patch_course_copy_import()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    compile(STUDENT_EXPERIENCE.read_text(encoding="utf-8"), str(STUDENT_EXPERIENCE), "exec")
    compile(COURSE_EDITOR.read_text(encoding="utf-8"), str(COURSE_EDITOR), "exec")
    compile(COURSE_COPY_IMPORT.read_text(encoding="utf-8"), str(COURSE_COPY_IMPORT), "exec")
    print("NUVEDRA xAPI & cmi5 v1 installed: course-scoped LRS endpoints, revocable source credentials, cmi5 launch/fetch flow, progress and Gradebook synchronization, safe course-copy preservation, Studio navigation, and student routing.", flush=True)


if __name__ == "__main__":
    main()
