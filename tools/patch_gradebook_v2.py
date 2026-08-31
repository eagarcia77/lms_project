from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/gradebook_v2_module.py.txt")
MODULE = Path("app/gradebook_v2.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
ASSESSMENT_ENGINE = Path("app/assessment_engine.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_GRADEBOOK_V2"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Gradebook v2 patch could not find {label}: {old[:160]!r}")
    return text.replace(old, new, 1)


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from app.assessment_engine import register_assessment_engine\n",
        "from app.assessment_engine import register_assessment_engine\nfrom app.gradebook_v2 import register_gradebook_v2\n",
        "Gradebook v2 import",
    )
    text = replace_once(
        text,
        '    register_assessment_engine(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook y Assessments v2.", flush=True)\n',
        '    register_assessment_engine(app)\n    register_gradebook_v2(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook, Assessments v2 y Gradebook v2.", flush=True)\n',
        "Gradebook v2 registration",
    )
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_assessment_history() -> None:
    text = ASSESSMENT_ENGINE.read_text(encoding="utf-8")
    marker = "NUVEDRA_GRADEBOOK_V2_FEEDBACK_LINK"
    if marker in text:
        return
    old = '''        history = "".join(
            f'<li><strong>Attempt {int(row.get("attempt_number") or 1)}</strong> · {_esc(row.get("status"))} · '
            f'{("Pending manual grading" if row.get("score_total") is None else f"{float(row.get("score_total") or 0):g} pts")} · {_esc(row.get("submitted_at") or "")}</li>'
            for row in submitted
        ) or '<li data-i18n-en="No submitted attempts yet." data-i18n-es="Todavía no hay intentos entregados.">No submitted attempts yet.</li>'
'''
    new = '''        # NUVEDRA_GRADEBOOK_V2_FEEDBACK_LINK
        history = "".join(
            f'<li><strong>Attempt {int(row.get("attempt_number") or 1)}</strong> · {_esc(row.get("status"))} · '
            f'{("Pending manual grading" if row.get("score_total") is None else f"{float(row.get("score_total") or 0):g} pts")} · {_esc(row.get("submitted_at") or "")} · '
            f'<a href="/learn/assessments/{item_id}/attempts/{int(row["id"])}/feedback" data-i18n-en="View feedback" data-i18n-es="Ver retroalimentación">View feedback</a></li>'
            for row in submitted
        ) or '<li data-i18n-en="No submitted attempts yet." data-i18n-es="Todavía no hay intentos entregados.">No submitted attempts yet.</li>'
'''
    if old not in text:
        raise RuntimeError("Gradebook v2 could not add feedback links to assessment history.")
    ASSESSMENT_ENGINE.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        functions = r'''
  // NUVEDRA_GRADEBOOK_V2
  function initializeGradebookV2Links() {
    const gradebook = document.querySelector('[data-testid="course-gradebook"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)\/gradebook$/);
    if (gradebook && match && !gradebook.querySelector('[data-attempt-review-link]')) {
      const hero = gradebook.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) {
          actions = document.createElement('div');
          actions.className = 'studio-actions';
          hero.appendChild(actions);
        }
        const link = document.createElement('a');
        link.className = 'studio-button';
        link.href = `/faculty/studio/courses/${match[1]}/attempts`;
        link.dataset.attemptReviewLink = 'gradebook-v2';
        link.dataset.i18nEn = 'Review assessment attempts';
        link.dataset.i18nEs = 'Revisar intentos de evaluación';
        link.textContent = language() === 'es' ? 'Revisar intentos de evaluación' : 'Review assessment attempts';
        actions.prepend(link);
      }
    }

    const builder = document.querySelector('[data-testid="assessment-builder"]');
    const builderMatch = window.location.pathname.match(/^\/faculty\/studio\/items\/(\d+)\/assessment$/);
    if (builder && builderMatch && !builder.querySelector('[data-course-attempts-link]')) {
      const courseLink = builder.querySelector('.studio-hero .studio-actions a[href*="/gradebook"]');
      if (courseLink) {
        const courseMatch = courseLink.getAttribute('href')?.match(/\/courses\/(\d+)\/gradebook$/);
        if (courseMatch) {
          const link = document.createElement('a');
          link.className = 'studio-button studio-button--quiet';
          link.href = `/faculty/studio/courses/${courseMatch[1]}/attempts`;
          link.dataset.courseAttemptsLink = 'v2';
          link.dataset.i18nEn = 'Review attempts';
          link.dataset.i18nEs = 'Revisar intentos';
          link.textContent = language() === 'es' ? 'Revisar intentos' : 'Review attempts';
          courseLink.after(link);
        }
      }
    }
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Gradebook v2 could not insert Studio links.")
        text = text.replace(marker, functions + marker, 1)
        text = replace_once(
            text,
            "    initializeAssessmentQuestionForms();\n    initializeDrafts();\n",
            "    initializeAssessmentQuestionForms();\n    initializeGradebookV2Links();\n    initializeDrafts();\n",
            "Gradebook v2 Studio initialization",
        )
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Gradebook v2 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_assessment_history()
    patch_studio_js()
    print("NUVEDRA Gradebook v2 installed: manual attempt review, essay scoring, per-question feedback, and student feedback history.", flush=True)


if __name__ == "__main__":
    main()
