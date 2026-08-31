from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/assessment_engine_module.py.txt")
ENGINE = Path("app/assessment_engine.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDENT_PORTAL = Path("app/student_portal.py")
PLATFORM_UPGRADE = Path("app/platform_upgrade.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_ASSESSMENTS_V2"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Assessments v2 patch could not find {label}: {old[:140]!r}")
    return text.replace(old, new, 1)


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from app.gradebook import register_gradebook\n",
        "from app.gradebook import register_gradebook\nfrom app.assessment_engine import register_assessment_engine\n",
        "assessment engine import",
    )
    text = replace_once(
        text,
        '    register_gradebook(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante y Gradebook.", flush=True)\n',
        '    register_gradebook(app)\n    register_assessment_engine(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook y Assessments v2.", flush=True)\n',
        "assessment engine registration",
    )
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_student_portal() -> None:
    text = STUDENT_PORTAL.read_text(encoding="utf-8")
    helper = '''
def _student_item_href(item: dict) -> str:
    item_id = int(item["id"])
    return f"/learn/assessments/{item_id}" if str(item.get("item_type")) in {"assessment", "quiz"} else f"/learn/items/{item_id}"
'''
    if "def _student_item_href(" not in text:
        marker = "\n\ndef _module_html(module: dict, items: list[dict]) -> str:\n"
        if marker not in text:
            raise RuntimeError("Assessments v2 patch could not insert the structured-assessment link helper.")
        text = text.replace(marker, "\n" + helper + marker, 1)
    text = replace_once(
        text,
        '        f\'<li><a href="/learn/items/{item["id"]}">{esc(item["title"])}</a> <small>({esc(item.get("item_type"))})</small></li>\'\n',
        '        f\'<li><a href="{_student_item_href(item)}">{esc(item["title"])}</a> <small>({esc(item.get("item_type"))})</small></li>\'\n',
        "student structured-assessment course link",
    )
    redirect_marker = '            course_id, item, module = item_bundle(conn, item_id)\n'
    redirect_block = '''            course_id, item, module = item_bundle(conn, item_id)
            if str(item.get("item_type")) in {"assessment", "quiz"}:
                return RedirectResponse(f"/learn/assessments/{item_id}", status_code=303)
'''
    if redirect_block not in text:
        if redirect_marker not in text:
            raise RuntimeError("Assessments v2 patch could not protect the legacy assessment GET route.")
        text = text.replace(redirect_marker, redirect_block, 1)
    submit_marker = '            course_id, item, module = item_bundle(conn, item_id)\n            access = require_course_role(conn, course_id, user["email"], {"student"})\n'
    submit_block = '''            course_id, item, module = item_bundle(conn, item_id)
            if str(item.get("item_type")) in {"assessment", "quiz"}:
                raise HTTPException(409, "Use the structured assessment workflow for this item.")
            access = require_course_role(conn, course_id, user["email"], {"student"})
'''
    if submit_block not in text:
        if submit_marker not in text:
            raise RuntimeError("Assessments v2 patch could not protect the legacy assessment POST route.")
        text = text.replace(submit_marker, submit_block, 1)
    STUDENT_PORTAL.write_text(text, encoding="utf-8")


def patch_platform_upgrade() -> None:
    text = PLATFORM_UPGRADE.read_text(encoding="utf-8")
    identity_marker = "    google_hub_safe.google_user = academic_user\n"
    identity_block = '''    google_hub_safe.google_user = academic_user
    try:
        import app.gradebook as gradebook
        gradebook.google_user = academic_user
    except Exception:
        pass
'''
    if identity_block not in text:
        text = replace_once(text, identity_marker, identity_block, "Gradebook administrator-instructor identity bridge")
    renderer_marker = "    google_hub_safe.portal_page = enhanced_portal_page\n"
    renderer_block = '''    google_hub_safe.portal_page = enhanced_portal_page
    for module_name in ("app.gradebook", "app.assessment_engine"):
        try:
            module = __import__(module_name, fromlist=["portal_page"])
            if hasattr(module, "portal_page"):
                setattr(module, "portal_page", enhanced_portal_page)
        except Exception:
            continue
'''
    if renderer_block not in text:
        text = replace_once(text, renderer_marker, renderer_block, "Gradebook and assessment bilingual renderer bridge")
    PLATFORM_UPGRADE.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        functions = r'''
  // NUVEDRA_ASSESSMENTS_V2
  function initializeAssessmentBuilderLink() {
    const root = document.querySelector('[data-testid="visual-item-editor"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/items\/(\d+)\/edit$/);
    const select = root?.querySelector('[data-item-type]');
    const hero = root?.querySelector('.studio-hero');
    if (!root || !match || !select || !hero) return;
    let actions = hero.querySelector('.studio-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'studio-actions';
      hero.appendChild(actions);
    }
    let link = actions.querySelector('[data-assessment-builder-link]');
    const update = () => {
      const structured = select.value === 'assessment' || select.value === 'quiz';
      if (!structured) {
        link?.remove();
        link = null;
        return;
      }
      if (link) return;
      link = document.createElement('a');
      link.className = 'studio-button';
      link.href = `/faculty/studio/items/${match[1]}/assessment`;
      link.dataset.assessmentBuilderLink = 'v2';
      link.dataset.i18nEn = 'Question editor';
      link.dataset.i18nEs = 'Editor de preguntas';
      link.textContent = language() === 'es' ? 'Editor de preguntas' : 'Question editor';
      actions.appendChild(link);
    };
    select.addEventListener('change', update);
    update();
  }

  function initializeAssessmentQuestionForms() {
    document.querySelectorAll('[data-question-form]').forEach((form) => {
      const type = form.querySelector('[data-question-type]');
      const choices = form.querySelector('[data-question-choices]');
      const answer = form.querySelector('[data-question-answer]');
      if (!type || !choices || !answer) return;
      const update = () => {
        choices.hidden = type.value !== 'multiple_choice';
        answer.hidden = type.value === 'essay';
      };
      type.addEventListener('change', update);
      update();
    });
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Assessments v2 patch could not insert Studio functions.")
        text = text.replace(marker, functions + marker, 1)
        text = replace_once(
            text,
            "    initializeCourseGradebookLink();\n    initializeDrafts();\n",
            "    initializeCourseGradebookLink();\n    initializeAssessmentBuilderLink();\n    initializeAssessmentQuestionForms();\n    initializeDrafts();\n",
            "Assessments v2 Studio initialization",
        )
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Assessments v2 source template is missing.")
    ENGINE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_student_portal()
    patch_platform_upgrade()
    patch_studio_js()
    print(
        "NUVEDRA Assessments v2 installed: structured questions, question bank, attempts, timer, and automatic grading.",
        flush=True,
    )


if __name__ == "__main__":
    main()
