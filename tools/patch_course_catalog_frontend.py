from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "static" / "app.js"
MARKER = "NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND_V3"

ENHANCEMENT = r'''
// NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND_V3
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
    if (!button) return;
    const shouldHide = !nexusCanCreateCourses();
    if (button.hidden !== shouldHide) button.hidden = shouldHide;
  }

  function nexusRefreshCourseControls() {
    nexusEnhanceCourseCards();
    nexusSyncNewCourseButton();
  }

  if (typeof renderCourses === "function" && !renderCourses.__nexusUnifiedCatalog) {
    const originalRenderCourses = renderCourses;
    const wrappedRenderCourses = function (...args) {
      const result = originalRenderCourses.apply(this, args);
      queueMicrotask(nexusRefreshCourseControls);
      return result;
    };
    wrappedRenderCourses.__nexusUnifiedCatalog = true;
    renderCourses = wrappedRenderCourses;
  }

  document.addEventListener("click", event => {
    const target = event.target instanceof Element
      ? event.target.closest("#new-course-button")
      : null;
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

  function scheduleStableRefresh() {
    [0, 120, 450, 1200, 2500].forEach(delay => {
      window.setTimeout(nexusRefreshCourseControls, delay);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleStableRefresh, { once: true });
  } else {
    scheduleStableRefresh();
  }
  window.addEventListener("load", scheduleStableRefresh, { once: true });
  window.addEventListener("pageshow", nexusRefreshCourseControls);

  window.nexusEnhanceCourseCatalog = nexusRefreshCourseControls;
})();
'''


def _remove_older_versions(source: str) -> str:
    markers = (
        "// NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND_V2",
        "// NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND\n",
    )
    for marker in markers:
        start = source.find(marker)
        if start < 0:
            continue
        wrapper_start = source.rfind("(function () {", 0, start)
        if wrapper_start < 0:
            wrapper_start = start
        end = source.find("})();", start)
        if end >= 0:
            source = source[:wrapper_start] + source[end + 5 :]
    return source


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    original = source
    source = _remove_older_versions(source)

    if MARKER not in source:
        source = source.rstrip() + "\n\n" + ENHANCEMENT.strip() + "\n"

    TARGET.write_text(source, encoding="utf-8")

    required = (
        MARKER,
        'location.href = "/course-studio"',
        "data-edit-course",
        "nexusCanCreateCourses",
        "nexusEnhanceCourseCatalog",
        "scheduleStableRefresh",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"Integración visual de cursos incompleta: {missing}")
    if "new MutationObserver" in source:
        raise RuntimeError("El catálogo conserva un observador global que puede causar refresco continuo.")

    print(
        "Portada conectada a Course Studio con actualización finita y estable; "
        f"cambios: {int(source != original)}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
