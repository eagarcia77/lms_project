from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "static" / "app.js"
MARKER = "NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND_V2"

ENHANCEMENT = r'''
// NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND_V2
(function () {
  function nexusCatalogState() {
    return typeof state === "object" && state ? state : {};
  }

  function nexusCanCreateCourses() {
    const me = nexusCatalogState().me || {};
    return Boolean(me.isAdmin || me.isInstructor);
  }

  function nexusCourseById(id) {
    const courses = Array.isArray(nexusCatalogState().courses)
      ? nexusCatalogState().courses
      : [];
    return courses.find(course => Number(course.id) === Number(id)) || null;
  }

  function nexusEnhanceCourseCards() {
    document.querySelectorAll(".course-card[data-course-id]").forEach(card => {
      const course = nexusCourseById(card.dataset.courseId);
      const existing = card.querySelector("[data-edit-course]");

      if (!course || !course.can_edit) {
        if (existing) existing.remove();
        return;
      }
      if (existing) return;

      const link = document.createElement("a");
      link.className = "button secondary course-edit-link";
      link.setAttribute("data-edit-course", "true");
      link.href = course.edit_url || `/admin/authoring/courses/${course.id}`;
      link.textContent = "Editar curso";
      link.addEventListener("click", event => event.stopPropagation());
      (card.querySelector(".course-body") || card).appendChild(link);
    });
  }

  function nexusSyncNewCourseButton() {
    const button = document.querySelector("#new-course-button");
    if (button) button.hidden = !nexusCanCreateCourses();
  }

  function nexusRefreshCourseControls() {
    nexusEnhanceCourseCards();
    nexusSyncNewCourseButton();
  }

  if (typeof renderCourses === "function" && !renderCourses.__nexusUnifiedCatalog) {
    const originalRenderCourses = renderCourses;
    const wrappedRenderCourses = function (...args) {
      const result = originalRenderCourses.apply(this, args);
      Promise.resolve().then(nexusRefreshCourseControls);
      return result;
    };
    wrappedRenderCourses.__nexusUnifiedCatalog = true;
    renderCourses = wrappedRenderCourses;
  }

  document.addEventListener("click", event => {
    const target = event.target instanceof Element ? event.target.closest("#new-course-button") : null;
    if (!target) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (nexusCanCreateCourses()) {
      location.href = "/course-studio";
      return;
    }
    if (typeof toast === "function") {
      toast("Solo administradores académicos e instructores pueden crear cursos.");
    }
  }, true);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", nexusRefreshCourseControls, { once: true });
  } else {
    nexusRefreshCourseControls();
  }

  const observer = new MutationObserver(() => nexusRefreshCourseControls());
  const startObserver = () => {
    if (document.body) observer.observe(document.body, { childList: true, subtree: true });
  };
  if (document.body) startObserver();
  else document.addEventListener("DOMContentLoaded", startObserver, { once: true });

  window.nexusEnhanceCourseCatalog = nexusRefreshCourseControls;
})();
'''


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    changes = 0

    if MARKER not in source:
        source = source.rstrip() + "\n\n" + ENHANCEMENT.strip() + "\n"
        changes += 1

    TARGET.write_text(source, encoding="utf-8")

    required = (
        MARKER,
        'location.href = "/course-studio"',
        "data-edit-course",
        "nexusCanCreateCourses",
        "nexusEnhanceCourseCatalog",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"Integración visual de cursos incompleta: {missing}")

    print(
        "Portada conectada a Course Studio sin depender de renderCourses(); "
        f"cambios: {changes}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
