from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "static" / "app.js"
MARKER = "NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND"

RENDER_FUNCTION = r'''function renderCourses() {
  // NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND
  $("#course-grid").innerHTML = state.courses.map(c => {
    const edit = c.can_edit
      ? `<a class="button secondary course-edit-link" data-edit-course href="${c.edit_url || `/admin/authoring/courses/${c.id}`}">Editar curso</a>`
      : "";
    return `<article class="course-card" data-course-id="${c.id}" tabindex="0" role="button" aria-label="Abrir ${c.title}"><div class="course-band" style="--accent:${c.accent};background:${c.accent}"></div><div class="course-body"><span class="course-code">${c.code}${c.xr_enabled ? " · XR" : ""}</span><h2>${c.title}</h2><p>${c.description}</p><div class="course-meta"><span>${c.module_count} módulos</span><span>${c.activity_count} actividades</span><span>${c.progress}%</span></div><div class="progress" style="--accent:${c.accent};--progress:${c.progress}%"><i></i></div>${edit}</div></article>`;
  }).join("");
  $$('[data-edit-course]').forEach(link => link.addEventListener('click', event => event.stopPropagation()));
  $$(".course-card").forEach(card => {
    const open = event => {
      if (event?.target instanceof Element && event.target.closest('[data-edit-course]')) return;
      openCourse(Number(card.dataset.courseId));
    };
    card.addEventListener("click", open);
    card.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") open(event);
    });
  });
}
'''

NEW_COURSE_HANDLER = r'''  const newCourseButton = $("#new-course-button");
  newCourseButton?.addEventListener("click", () => {
    if (state.me?.isAdmin || state.me?.isInstructor) {
      location.href = "/course-studio";
      return;
    }
    toast("Solo administradores académicos e instructores pueden crear cursos.");
  });'''

ROLE_VISIBILITY = r'''
    const newCourseButton = $("#new-course-button");
    if (newCourseButton) newCourseButton.hidden = !(state.me.isAdmin || state.me.isInstructor);
'''


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    changes = 0

    if MARKER not in source:
        pattern = re.compile(r"function renderCourses\(\) \{.*?\n\}\n\nasync function openCourse", re.DOTALL)
        match = pattern.search(source)
        if not match:
            raise RuntimeError("No se encontró renderCourses() en app.js.")
        source = source[: match.start()] + RENDER_FUNCTION + "\nasync function openCourse" + source[match.end() :]
        changes += 1

    old_handler = '  $("#new-course-button").addEventListener("click", () => toast("El diseñador visual de cursos se incorpora en la siguiente fase."));'
    if NEW_COURSE_HANDLER not in source:
        if old_handler not in source:
            raise RuntimeError("No se encontró el controlador anterior de Nuevo curso.")
        source = source.replace(old_handler, NEW_COURSE_HANDLER, 1)
        changes += 1

    role_anchor = '    $(".profile-text small").textContent = state.me.platformRoleLabel || "Cuenta conectada";'
    if ROLE_VISIBILITY.strip() not in source:
        if role_anchor not in source:
            role_anchor = '    $(".profile-text small").textContent = "Cuenta conectada";'
        if role_anchor not in source:
            raise RuntimeError("No se encontró el bloque del perfil para controlar Nuevo curso.")
        source = source.replace(role_anchor, role_anchor + ROLE_VISIBILITY, 1)
        changes += 1

    TARGET.write_text(source, encoding="utf-8")
    compile_markers = (MARKER, "/course-studio", "data-edit-course", "state.me?.isInstructor")
    missing = [marker for marker in compile_markers if marker not in source]
    if missing:
        raise RuntimeError(f"Integración visual de cursos incompleta: {missing}")
    print(f"Portada conectada a Course Studio; cambios: {changes}.", flush=True)


if __name__ == "__main__":
    main()
