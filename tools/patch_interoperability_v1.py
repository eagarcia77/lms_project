from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/interoperability_module.py.txt")
MODULE = Path("app/interoperability.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
COURSE_EDITOR = Path("app/course_editor_access.py")
TAG = "NUVEDRA_SCORM_LTI_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"SCORM & LTI v1 could not find {label}: {old[:180]!r}")
    return text.replace(old, new, 1)


def patch_generated_module() -> None:
    text = MODULE.read_text(encoding="utf-8")
    old_safe = '''def _safe_zip_name(value: str) -> str:\n    clean = value.replace("\\\\", "/").lstrip("/")\n    path = PurePosixPath(clean)\n    if not clean or any(part in {"", ".", ".."} for part in path.parts):\n        raise HTTPException(400, "The SCORM package contains an unsafe file path.")\n    return str(path)\n'''
    new_safe = '''def _safe_zip_name(value: str) -> str:\n    clean = value.replace("\\\\", "/").lstrip("/")\n    parts = []\n    for part in PurePosixPath(clean).parts:\n        if part in {"", "."}:\n            continue\n        if part == "..":\n            raise HTTPException(400, "The SCORM package contains an unsafe file path.")\n        parts.append(part)\n    if not parts:\n        raise HTTPException(400, "The SCORM package contains an unsafe file path.")\n    return "/".join(parts)\n'''
    text = replace_once(text, old_safe, new_safe, "safe SCORM path normalization")
    text = replace_once(
        text,
        '                names = {name.replace("\\\\", "/"): name for name in archive.namelist()}\n',
        '                names = {_safe_zip_name(name): name for name in archive.namelist() if name and not name.endswith("/")}\n',
        "SCORM asset path normalization",
    )
    text = replace_once(
        text,
        '            audit(conn, user["email"], "scorm_package_uploaded", "scorm_package", str(package_id), f"SCORM {version}", request.client.host if request.client else "")\n',
        '            execute(conn, "UPDATE nexus_content_items SET external_url=?,updated_at=? WHERE id=?", (f"/learn/scorm/{package_id}", now, item_id))\n            audit(conn, user["email"], "scorm_package_uploaded", "scorm_package", str(package_id), f"SCORM {version}", request.client.host if request.client else "")\n',
        "SCORM student launch URL",
    )
    text = replace_once(
        text,
        '        if parsed.scheme not in {"http", "https"} or not parsed.netloc: raise HTTPException(400, "LTI launch URL must use http or https.")\n',
        '        if parsed.scheme not in {"http", "https"} or not parsed.netloc: raise HTTPException(400, "LTI launch URL must use http or https.")\n        if parsed.query or parsed.fragment: raise HTTPException(400, "LTI 1.1 launch URLs with query strings or fragments are not supported in v1.")\n',
        "LTI launch URL normalization",
    )
    text = replace_once(
        text,
        '            audit(conn, user["email"], "lti_tool_created", "lti_tool", str(tool_id), "LTI 1.1 Basic Launch", request.client.host if request.client else "")\n',
        '            execute(conn, "UPDATE nexus_content_items SET external_url=?,updated_at=? WHERE id=?", (f"/learn/lti/{tool_id}/launch", now, item_id))\n            audit(conn, user["email"], "lti_tool_created", "lti_tool", str(tool_id), "LTI 1.1 Basic Launch", request.client.host if request.client else "")\n',
        "LTI student launch URL",
    )
    MODULE.write_text(text, encoding="utf-8")


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.interoperability import register_interoperability\n"
    if import_line not in text:
        anchors = (
            "from app.certificates_completion import register_certificates_completion\n",
            "from app.attendance_participation import register_attendance_participation\n",
            "from app.people_groups import register_people_groups\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("SCORM & LTI v1 could not locate an academic portal import anchor.")
    registration = "    register_interoperability(app)\n"
    if registration not in text:
        anchors = (
            "    register_certificates_completion(app)\n",
            "    register_attendance_participation(app)\n",
            "    register_people_groups(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("SCORM & LTI v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_SCORM_LTI_V1
  function initializeInteroperabilityLink() {
    const root = document.querySelector('[data-testid="visual-course-studio"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!root || !match || root.querySelector('[data-interoperability-link]')) return;
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
    link.href = `/faculty/studio/courses/${match[1]}/interoperability`;
    link.dataset.interoperabilityLink = 'v1';
    link.dataset.i18nEn = 'SCORM & LTI';
    link.dataset.i18nEs = 'SCORM y LTI';
    link.textContent = language() === 'es' ? 'SCORM y LTI' : 'SCORM & LTI';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("SCORM & LTI v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeInteroperabilityLink();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("SCORM & LTI v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeInteroperabilityLink();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def patch_student_experience() -> None:
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    redirect_anchor = '            if str(item.get("item_type")) in {"assignment","project","presentation"}: return RedirectResponse(f"/learn/assignments/{item_id}",status_code=303)\n'
    redirect_new = '            if str(item.get("item_type")) == "scorm" and item.get("external_url"): return RedirectResponse(str(item.get("external_url")),status_code=303)\n' + redirect_anchor
    text = replace_once(text, redirect_anchor, redirect_new, "SCORM student launch redirect")
    completion_anchor = '            if str(item.get("item_type")) in academic_access.ASSESSMENT_TYPES: raise HTTPException(409,"Assessment completion is determined by submission status.")\n'
    completion_new = '            if str(item.get("item_type")) == "scorm": raise HTTPException(409,"SCORM completion is determined by the package runtime.")\n' + completion_anchor
    text = replace_once(text, completion_anchor, completion_new, "SCORM managed completion")
    STUDENT_EXPERIENCE.write_text(text, encoding="utf-8")


def patch_course_editor() -> None:
    text = COURSE_EDITOR.read_text(encoding="utf-8")
    anchor = '    "360": "360° experience",\n'
    new = anchor + '    "scorm": "SCORM package",\n    "lti": "LTI external tool",\n'
    text = replace_once(text, anchor, new, "Course Studio interoperability item types")
    COURSE_EDITOR.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("SCORM & LTI v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_generated_module()
    patch_academic_portal()
    patch_studio_js()
    patch_student_experience()
    patch_course_editor()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    compile(STUDENT_EXPERIENCE.read_text(encoding="utf-8"), str(STUDENT_EXPERIENCE), "exec")
    compile(COURSE_EDITOR.read_text(encoding="utf-8"), str(COURSE_EDITOR), "exec")
    print("NUVEDRA SCORM & LTI v1 installed: SCORM 1.2/2004 runtime launch/state tracking, legacy LTI 1.1 Basic Launch, Studio navigation, and student routing.", flush=True)


if __name__ == "__main__":
    main()
