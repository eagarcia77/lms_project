from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/content_library_v1_module.py.txt")
MODULE = Path("app/content_library.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_CONTENT_LIBRARY_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Content Library v1 patch could not find {label}: {old[:160]!r}")
    return text.replace(old, new, 1)


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from app.student_experience import register_student_experience\n",
        "from app.student_experience import register_student_experience\nfrom app.content_library import register_content_library\n",
        "Content Library import",
    )
    text = replace_once(
        text,
        '    register_student_experience(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook, Assessments v2, Gradebook v2 y Student Experience v2.", flush=True)\n',
        '    register_student_experience(app)\n    register_content_library(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook, Assessments v2, Gradebook v2, Student Experience v2 y Content Library v1.", flush=True)\n',
        "Content Library registration",
    )
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG in text:
        return
    functions = r'''
  // NUVEDRA_CONTENT_LIBRARY_V1
  function initializeContentLibraryLink() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (courseStudio && courseMatch && !courseStudio.querySelector('[data-content-library-link]')) {
      const hero = courseStudio.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) {
          actions = document.createElement('div');
          actions.className = 'studio-actions';
          hero.appendChild(actions);
        }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = `/faculty/library?course_id=${courseMatch[1]}`;
        link.dataset.contentLibraryLink = 'v1';
        link.dataset.i18nEn = 'Content Library';
        link.dataset.i18nEs = 'Biblioteca de contenido';
        link.textContent = language() === 'es' ? 'Biblioteca de contenido' : 'Content Library';
        actions.appendChild(link);
      }
    }
  }

'''
    marker = "  function start() {\n"
    if marker not in text:
        raise RuntimeError("Content Library v1 could not insert the Studio navigation link.")
    text = text.replace(marker, functions + marker, 1)
    init_old = "    initializeGradebookV2Links();\n    initializeDrafts();\n"
    init_new = "    initializeGradebookV2Links();\n    initializeContentLibraryLink();\n    initializeDrafts();\n"
    text = replace_once(text, init_old, init_new, "Content Library Studio initialization")
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Content Library v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    print("NUVEDRA Content Library v1 installed: reusable files and links, protected downloads, accessibility metadata, and course reuse.", flush=True)


if __name__ == "__main__":
    main()
