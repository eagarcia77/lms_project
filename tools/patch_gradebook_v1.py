from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/gradebook_module.py.txt")
GRADEBOOK = Path("app/gradebook.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDENT_PORTAL = Path("app/student_portal.py")
GOOGLE_HUB = Path("app/google_hub_safe.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_GRADEBOOK_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Gradebook patch could not find {label}: {old[:120]!r}")
    return text.replace(old, new, 1)


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from app.google_hub_safe import register_portal_home_and_google\n",
        "from app.google_hub_safe import register_portal_home_and_google\nfrom app.gradebook import register_gradebook\n",
        "academic portal import",
    )
    text = replace_once(
        text,
        "    register_student_portal(app)\n    print(\"Portal académico por roles registrado: administrador, profesor y estudiante.\", flush=True)\n",
        "    register_student_portal(app)\n    register_gradebook(app)\n    print(\"Portal académico por roles registrado: administrador, profesor, estudiante y Gradebook.\", flush=True)\n",
        "academic portal registration",
    )
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_student_portal() -> None:
    text = STUDENT_PORTAL.read_text(encoding="utf-8")
    marker = 'data-gradebook-link="student"'
    if marker not in text:
        old = "        body = f'<p><a href=\"/portal\">&larr; Mis cursos</a></p><h2>{esc(access[\"course_code\"])}: {esc(access[\"title\"])}</h2><p>{esc(access.get(\"description\"))}</p>{content}'\n"
        new = "        body = f'<p><a href=\"/portal\">&larr; My courses</a></p><h2>{esc(access[\"course_code\"])}: {esc(access[\"title\"])}</h2><p>{esc(access.get(\"description\"))}</p><p><a class=\"button ghost\" data-gradebook-link=\"student\" href=\"/learn/courses/{course_id}/grades\">Grades</a></p>{content}'\n"
        text = replace_once(text, old, new, "student course grade link")
    STUDENT_PORTAL.write_text(text, encoding="utf-8")


def patch_portal_cards() -> None:
    text = GOOGLE_HUB.read_text(encoding="utf-8")
    if 'data-gradebook-link="instructor"' not in text:
        old = "            f'<section class=\"card\"><span class=\"badge\">Profesor</span><h3>{esc(row[\"course_code\"])}: {esc(row[\"title\"])}</h3><p>{esc(row.get(\"description\"))}</p><a class=\"button\" href=\"/faculty/courses/{row[\"course_id\"]}\">Crear y editar contenido</a></section>'\n"
        new = "            f'<section class=\"card\"><span class=\"badge\">Instructor</span><h3>{esc(row[\"course_code\"])}: {esc(row[\"title\"])}</h3><p>{esc(row.get(\"description\"))}</p><a class=\"button\" href=\"/faculty/courses/{row[\"course_id\"]}\">Create and edit content</a><a class=\"button secondary\" data-gradebook-link=\"instructor\" href=\"/faculty/studio/courses/{row[\"course_id\"]}/gradebook\">Gradebook</a></section>'\n"
        text = replace_once(text, old, new, "instructor portal gradebook link")
    if 'data-gradebook-link="portal-student"' not in text:
        old = "            f'<section class=\"card\"><span class=\"badge\">Estudiante</span><h3>{esc(row[\"course_code\"])}: {esc(row[\"title\"])}</h3><p>{esc(row.get(\"description\"))}</p><a class=\"button secondary\" href=\"/learn/courses/{row[\"course_id\"]}\">Entrar al curso</a></section>'\n"
        new = "            f'<section class=\"card\"><span class=\"badge\">Student</span><h3>{esc(row[\"course_code\"])}: {esc(row[\"title\"])}</h3><p>{esc(row.get(\"description\"))}</p><a class=\"button secondary\" href=\"/learn/courses/{row[\"course_id\"]}\">Enter course</a><a class=\"button ghost\" data-gradebook-link=\"portal-student\" href=\"/learn/courses/{row[\"course_id\"]}/grades\">Grades</a></section>'\n"
        text = replace_once(text, old, new, "student portal grades link")
    GOOGLE_HUB.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        function = r'''
  // NUVEDRA_GRADEBOOK_V1
  function initializeCourseGradebookLink() {
    const root = document.querySelector('[data-testid="visual-course-studio"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!root || !match || root.querySelector('[data-gradebook-link="studio"]')) return;
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
    link.href = `/faculty/studio/courses/${match[1]}/gradebook`;
    link.dataset.gradebookLink = 'studio';
    link.dataset.i18nEn = 'Gradebook';
    link.dataset.i18nEs = 'Calificaciones';
    link.textContent = language() === 'es' ? 'Calificaciones' : 'Gradebook';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Gradebook patch could not insert the studio Gradebook link.")
        text = text.replace(marker, function + marker, 1)
        text = replace_once(
            text,
            "    applyLanguage();\n    initializeDrafts();\n",
            "    applyLanguage();\n    initializeCourseGradebookLink();\n    initializeDrafts();\n",
            "studio Gradebook initialization",
        )
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Gradebook source template is missing.")
    GRADEBOOK.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_student_portal()
    patch_portal_cards()
    patch_studio_js()
    print("NUVEDRA Gradebook v1 installed: grading, feedback, CSV export, and student grade access.", flush=True)


if __name__ == "__main__":
    main()
