from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/xapi_cmi5_module.py.txt")
MODULE = Path("app/xapi_cmi5.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
COURSE_EDITOR = Path("app/course_editor_access.py")
TAG = "NUVEDRA_XAPI_CMI5_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"xAPI & cmi5 v1 could not find {label}: {old[:180]!r}")
    return text.replace(old, new, 1)


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


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("xAPI & cmi5 v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    patch_student_experience()
    patch_course_editor()
    compile(MODULE.read_text(encoding="utf-8"), str(MODULE), "exec")
    compile(STUDENT_EXPERIENCE.read_text(encoding="utf-8"), str(STUDENT_EXPERIENCE), "exec")
    compile(COURSE_EDITOR.read_text(encoding="utf-8"), str(COURSE_EDITOR), "exec")
    print("NUVEDRA xAPI & cmi5 v1 installed: course-scoped LRS endpoints, cmi5 launch/fetch flow, progress and Gradebook synchronization, Studio navigation, and student routing.", flush=True)


if __name__ == "__main__":
    main()
