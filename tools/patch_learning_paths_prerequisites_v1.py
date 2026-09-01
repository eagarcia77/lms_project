from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/learning_paths_prerequisites_module.py.txt")
MODULE = Path("app/learning_paths_prerequisites.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
ASSESSMENT_ENGINE = Path("app/assessment_engine.py")
ASSIGNMENTS = Path("app/assignments_submissions.py")
DISCUSSIONS = Path("app/discussions_collaboration.py")
INTEROP = Path("app/interoperability.py")
LTI13 = Path("app/lti13_advantage.py")
XAPI = Path("app/xapi_cmi5.py")
COURSE_COPY = Path("app/course_copy_import.py")
TAG = "NUVEDRA_LEARNING_PATHS_PREREQUISITES_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Learning Paths & Prerequisites v1 could not find {label}: {old[:180]!r}")
    return text.replace(old, new, 1)


def replace_all_required(text: str, old: str, new: str, label: str, minimum: int = 1) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count < minimum:
        raise RuntimeError(f"Learning Paths & Prerequisites v1 expected at least {minimum} {label} anchors, found {count}.")
    return text.replace(old, new)


def replace_function(text: str, name: str, replacement: str) -> str:
    start = text.find(f"def {name}(")
    if start < 0:
        raise RuntimeError(f"Learning Paths & Prerequisites v1 could not find function {name}.")
    next_def = text.find("\ndef ", start + 1)
    if next_def < 0:
        raise RuntimeError(f"Learning Paths & Prerequisites v1 could not find the end of function {name}.")
    return text[:start] + replacement.rstrip() + "\n\n" + text[next_def + 1:]


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.learning_paths_prerequisites import register_learning_paths_prerequisites\n"
    if import_line not in text:
        anchors = (
            "from app.xapi_cmi5 import register_xapi_cmi5\n",
            "from app.lti13_production_hardening import register_lti13_production_hardening\n",
            "from app.lti13_advantage import register_lti13_advantage\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Learning Paths & Prerequisites v1 could not locate an academic portal import anchor.")
    registration = "    register_learning_paths_prerequisites(app)\n"
    if registration not in text:
        anchors = (
            "    register_xapi_cmi5(app)\n",
            "    register_lti13_production_hardening(app)\n",
            "    register_lti13_advantage(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Learning Paths & Prerequisites v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_LEARNING_PATHS_PREREQUISITES_V1
  function initializeLearningPathsLinks() {
    const faculty = document.querySelector('[data-testid="visual-course-studio"]');
    const facultyMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (faculty && facultyMatch && !faculty.querySelector('[data-learning-paths-link]')) {
      const hero = faculty.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) { actions = document.createElement('div'); actions.className = 'studio-actions'; hero.appendChild(actions); }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = `/faculty/studio/courses/${facultyMatch[1]}/paths`;
        link.dataset.learningPathsLink = 'v1';
        link.dataset.i18nEn = 'Learning Paths';
        link.dataset.i18nEs = 'Rutas de aprendizaje';
        link.textContent = language() === 'es' ? 'Rutas de aprendizaje' : 'Learning Paths';
        actions.appendChild(link);
      }
    }
    const student = document.querySelector('[data-testid="student-course-v2"]');
    const studentMatch = window.location.pathname.match(/^\/learn\/courses\/(\d+)$/);
    if (student && studentMatch && !student.querySelector('[data-student-learning-path-link]')) {
      const hero = student.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) { actions = document.createElement('div'); actions.className = 'studio-actions'; hero.appendChild(actions); }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = `/learn/courses/${studentMatch[1]}/path`;
        link.dataset.studentLearningPathLink = 'v1';
        link.dataset.i18nEn = 'My Learning Path';
        link.dataset.i18nEs = 'Mi ruta de aprendizaje';
        link.textContent = language() === 'es' ? 'Mi ruta de aprendizaje' : 'My Learning Path';
        actions.appendChild(link);
      }
    }
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Learning Paths & Prerequisites v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeLearningPathsLinks();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Learning Paths & Prerequisites v1 could not initialize navigation.")
        text = text.replace(marker, "    initializeLearningPathsLinks();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def patch_student_experience() -> None:
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    text = replace_function(text, "_item_href", '''def _item_href(item: dict[str, Any]) -> str:
    return f"/learn/paths/items/{int(item['id'])}"''')
    get_anchor = '''            access=academic_access.require_course_role(conn,course_id,user["email"],academic_access.STUDENT_ROLES)\n            if str(access.get("course_status"))!="active" or str(item.get("status"))!="published" or str(module.get("status"))!="published": raise HTTPException(403,"This content is not published.")\n'''
    get_new = '''            access=academic_access.require_course_role(conn,course_id,user["email"],academic_access.STUDENT_ROLES)\n            if str(access.get("course_status"))!="active" or str(item.get("status"))!="published" or str(module.get("status"))!="published": raise HTTPException(403,"This content is not published.")\n            academic_access.require_learning_path_item_access(conn,item_id,user["email"])\n'''
    text = replace_once(text, get_anchor, get_new, "student content access gate")
    post_anchor = '''            access=academic_access.require_course_role(conn,course_id,user["email"],{"student"})\n            if str(access.get("course_status"))!="active" or str(item.get("status"))!="published" or str(module.get("status"))!="published": raise HTTPException(403,"This content is not available.")\n'''
    post_new = '''            access=academic_access.require_course_role(conn,course_id,user["email"],{"student"})\n            if str(access.get("course_status"))!="active" or str(item.get("status"))!="published" or str(module.get("status"))!="published": raise HTTPException(403,"This content is not available.")\n            academic_access.require_learning_path_item_access(conn,item_id,user["email"])\n'''
    text = replace_once(text, post_anchor, post_new, "student completion access gate")
    STUDENT_EXPERIENCE.write_text(text, encoding="utf-8")


def patch_assessment_engine() -> None:
    text = ASSESSMENT_ENGINE.read_text(encoding="utf-8")
    anchor = '''    if (\n        str(access.get("course_status")) != "active"\n        or str(module.get("status")) != "published"\n        or str(item.get("status")) != "published"\n    ):\n        raise HTTPException(403, "This assessment is not available.")\n    return course_id, item, module, access\n'''
    new = '''    if (\n        str(access.get("course_status")) != "active"\n        or str(module.get("status")) != "published"\n        or str(item.get("status")) != "published"\n    ):\n        raise HTTPException(403, "This assessment is not available.")\n    academic_access.require_learning_path_item_access(conn, item_id, user["email"])\n    return course_id, item, module, access\n'''
    text = replace_once(text, anchor, new, "assessment student access helper")
    ASSESSMENT_ENGINE.write_text(text, encoding="utf-8")


def patch_assignments() -> None:
    text = ASSIGNMENTS.read_text(encoding="utf-8")
    anchor = '''            if str(access.get("course_status")) != "active" or str(module.get("status")) != "published" or str(item.get("status")) != "published":\n                raise HTTPException(403, "This assignment is not available.")\n'''
    new = anchor + '''            academic_access.require_learning_path_item_access(conn, item_id, user["email"])\n'''
    text = replace_all_required(text, anchor, new, "assignment availability", minimum=2)
    ASSIGNMENTS.write_text(text, encoding="utf-8")


def patch_discussions() -> None:
    text = DISCUSSIONS.read_text(encoding="utf-8")
    anchor = '''            if str(access.get("course_status")) != "active" or str(module.get("status")) != "published" or str(item.get("status")) != "published":\n                raise HTTPException(403, "This discussion is not available.")\n'''
    new = anchor + '''            academic_access.require_learning_path_item_access(conn, item_id, user["email"])\n'''
    text = replace_all_required(text, anchor, new, "discussion availability", minimum=2)
    DISCUSSIONS.write_text(text, encoding="utf-8")


def patch_interoperability() -> None:
    text = INTEROP.read_text(encoding="utf-8")
    scorm_anchor = '''            access = _learning_access(conn, int(package["course_id"]), user["email"])\n            is_author = str(access.get("course_role")) in academic_access.AUTHOR_ROLES\n            if not is_author and not _published_interop(package): raise HTTPException(403, "This SCORM package is not available.")\n'''
    scorm_new = '''            access = _learning_access(conn, int(package["course_id"]), user["email"])\n            is_author = str(access.get("course_role")) in academic_access.AUTHOR_ROLES\n            if not is_author and not _published_interop(package): raise HTTPException(403, "This SCORM package is not available.")\n            if str(access.get("course_role")) == "student": academic_access.require_learning_path_item_access(conn, int(package["item_id"]), user["email"])\n'''
    text = replace_all_required(text, scorm_anchor, scorm_new, "SCORM learner gate", minimum=2)
    state_anchor = '''            access = _learning_access(conn, int(package["course_id"]), user["email"])\n            if str(access.get("course_role")) != "student": return Response(status_code=204)\n            if not _published_interop(package): raise HTTPException(403, "This SCORM package is not available.")\n'''
    state_new = state_anchor + '''            academic_access.require_learning_path_item_access(conn, int(package["item_id"]), user["email"])\n'''
    text = replace_once(text, state_anchor, state_new, "SCORM state learner gate")
    lti_anchor = '''            access = _learning_access(conn, int(tool["course_id"]), user["email"])\n            is_author = str(access.get("course_role")) in academic_access.AUTHOR_ROLES\n            if not is_author and not _published_interop(tool): raise HTTPException(403, "This LTI tool is not available.")\n'''
    lti_new = lti_anchor + '''            if str(access.get("course_role")) == "student": academic_access.require_learning_path_item_access(conn, int(tool["item_id"]), user["email"])\n'''
    text = replace_once(text, lti_anchor, lti_new, "LTI 1.1 learner gate")
    INTEROP.write_text(text, encoding="utf-8")


def patch_lti13() -> None:
    text = LTI13.read_text(encoding="utf-8")
    anchor = '''            access = academic_access.require_course_role(conn, int(resource["course_id"]), user["email"], academic_access.AUTHOR_ROLES | academic_access.STUDENT_ROLES)\n            is_author = str(access.get("course_role")) in academic_access.AUTHOR_ROLES\n            if resource.get("tool_status") != "active": raise HTTPException(403, "This LTI 1.3 tool is disabled.")\n'''
    new = '''            access = academic_access.require_course_role(conn, int(resource["course_id"]), user["email"], academic_access.AUTHOR_ROLES | academic_access.STUDENT_ROLES)\n            is_author = str(access.get("course_role")) in academic_access.AUTHOR_ROLES\n            if resource.get("tool_status") != "active": raise HTTPException(403, "This LTI 1.3 tool is disabled.")\n            if str(access.get("course_role")) == "student": academic_access.require_learning_path_item_access(conn, int(resource["item_id"]), user["email"])\n'''
    text = replace_once(text, anchor, new, "LTI 1.3 learner gate")
    LTI13.write_text(text, encoding="utf-8")


def patch_xapi() -> None:
    text = XAPI.read_text(encoding="utf-8")
    anchor = '''            access = academic_access.require_course_role(conn, int(au["course_id"]), user["email"], {"student"})\n            if str(access.get("course_role")) != "student":\n                raise HTTPException(403, "cmi5 activities require a student enrollment.")\n'''
    new = anchor + '''            academic_access.require_learning_path_item_access(conn, int(au["item_id"]), user["email"])\n'''
    text = replace_once(text, anchor, new, "cmi5 learner gate")
    XAPI.write_text(text, encoding="utf-8")


def patch_course_copy() -> None:
    text = COURSE_COPY.read_text(encoding="utf-8")
    helper_anchor = "def _copy_content(\n"
    helper = '''def _copy_learning_path_rules(conn: Any, source_course_id: int, target_course_id: int, module_map: dict[int, int], item_map: dict[int, int], actor: str) -> int:\n    copied = 0\n    rules = rows(execute(conn, "SELECT * FROM nuvedra_learning_path_rules WHERE course_id=? AND status='active' ORDER BY position,id", (source_course_id,)))\n    for rule in rules:\n        target_type = str(rule.get("target_type") or "")\n        source_target_id = int(rule["target_id"])\n        target_id = module_map.get(source_target_id) if target_type == "module" else item_map.get(source_target_id)\n        if not target_id:\n            continue\n        kind = str(rule.get("rule_type") or "")\n        source_id = int(rule["source_id"]) if rule.get("source_id") not in (None, "") else None\n        mapped_source = None\n        if kind in {"item_completed", "item_grade"}:\n            mapped_source = item_map.get(source_id or -1)\n            if not mapped_source: continue\n        elif kind == "module_completed":\n            mapped_source = module_map.get(source_id or -1)\n            if not mapped_source: continue\n        elif kind == "outcome_attainment":\n            outcome = rows(execute(conn, "SELECT code,title FROM nuvedra_outcomes WHERE id=? AND course_id=?", (source_id, source_course_id)))\n            if not outcome: continue\n            match = rows(execute(conn, "SELECT id FROM nuvedra_outcomes WHERE course_id=? AND code=? AND title=? ORDER BY id LIMIT 1", (target_course_id, outcome[0].get("code"), outcome[0].get("title"))))\n            if not match: continue\n            mapped_source = int(match[0]["id"])\n        elif kind != "course_progress":\n            continue\n        now = utcnow()\n        execute(conn, """INSERT INTO nuvedra_learning_path_rules\n            (course_id,target_type,target_id,rule_type,source_id,threshold,position,status,created_by,created_at,updated_at)\n            VALUES (?,?,?,?,?,?,?,'active',?,?,?)""", (\n                target_course_id, target_type, target_id, kind, mapped_source, rule.get("threshold"), rule.get("position") or 1, actor, now, now,\n            ))\n        copied += 1\n    return copied\n\n\n'''
    if "def _copy_learning_path_rules(" not in text:
        if helper_anchor not in text:
            raise RuntimeError("Learning Paths & Prerequisites v1 could not locate the course-copy helper anchor.")
        text = text.replace(helper_anchor, helper + helper_anchor, 1)
    return_anchor = '''    rubric_count = _copy_rubrics(conn, source_course_id, target_course_id, item_map, actor) if copy_rubrics else 0\n    outcome_count = _copy_outcomes(conn, source_course_id, target_course_id, item_map, actor) if copy_outcomes else 0\n    return {"modules": module_count, "items": item_count, "rubrics": rubric_count, "outcomes": outcome_count}\n'''
    return_new = '''    rubric_count = _copy_rubrics(conn, source_course_id, target_course_id, item_map, actor) if copy_rubrics else 0\n    outcome_count = _copy_outcomes(conn, source_course_id, target_course_id, item_map, actor) if copy_outcomes else 0\n    _copy_learning_path_rules(conn, source_course_id, target_course_id, module_map, item_map, actor)\n    return {"modules": module_count, "items": item_count, "rubrics": rubric_count, "outcomes": outcome_count}\n'''
    text = replace_once(text, return_anchor, return_new, "course-copy learning-path preservation")
    COURSE_COPY.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Learning Paths & Prerequisites v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    patch_student_experience()
    patch_assessment_engine()
    patch_assignments()
    patch_discussions()
    patch_interoperability()
    patch_lti13()
    patch_xapi()
    patch_course_copy()
    for path in (MODULE, STUDENT_EXPERIENCE, ASSESSMENT_ENGINE, ASSIGNMENTS, DISCUSSIONS, INTEROP, LTI13, XAPI, COURSE_COPY):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("NUVEDRA Learning Paths & Prerequisites v1 installed: transparent learner gateway, route-level prerequisite enforcement, Studio navigation, and safe Course Copy preservation.", flush=True)


if __name__ == "__main__":
    main()
