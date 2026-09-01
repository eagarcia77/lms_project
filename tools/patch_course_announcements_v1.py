from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/course_announcements_module.py.txt")
MODULE = Path("app/course_announcements.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_COURSE_ANNOUNCEMENTS_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.course_announcements import register_course_announcements\n"
    if import_line not in text:
        anchors = (
            "from app.calendar_notifications import register_calendar_notifications\n",
            "from app.learning_analytics import register_learning_analytics\n",
            "from app.accessibility_checker import register_accessibility_checker\n",
            "from app.content_library import register_content_library\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Course Announcements v1 could not locate an academic portal import anchor.")

    registration = "    register_course_announcements(app)\n"
    if registration not in text:
        anchors = (
            "    register_calendar_notifications(app)\n",
            "    register_learning_analytics(app)\n",
            "    register_accessibility_checker(app)\n",
            "    register_content_library(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Course Announcements v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_COURSE_ANNOUNCEMENTS_V1
  function initializeCourseAnnouncementsLinks() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (courseStudio && courseMatch && !courseStudio.querySelector('[data-course-announcements-link]')) {
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
        link.href = `/faculty/studio/courses/${courseMatch[1]}/announcements`;
        link.dataset.courseAnnouncementsLink = 'v1';
        link.dataset.i18nEn = 'Announcements';
        link.dataset.i18nEs = 'Anuncios';
        link.textContent = language() === 'es' ? 'Anuncios' : 'Announcements';
        actions.appendChild(link);
      }
    }

    const studentDashboard = document.querySelector('[data-testid="student-dashboard"]');
    if (studentDashboard && !studentDashboard.querySelector('[data-student-announcements-link]')) {
      const hero = studentDashboard.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) {
          actions = document.createElement('div');
          actions.className = 'studio-actions';
          hero.appendChild(actions);
        }
        const link = document.createElement('a');
        link.className = 'studio-button studio-button--quiet';
        link.href = '/learn/announcements';
        link.dataset.studentAnnouncementsLink = 'v1';
        link.dataset.i18nEn = 'Announcements';
        link.dataset.i18nEs = 'Anuncios';
        link.textContent = language() === 'es' ? 'Anuncios' : 'Announcements';
        actions.appendChild(link);
      }
    }
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Course Announcements v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    if "    initializeCourseAnnouncementsLinks();\n" not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Course Announcements v1 could not initialize Studio navigation.")
        text = text.replace(marker, "    initializeCourseAnnouncementsLinks();\n" + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Course Announcements v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    print("NUVEDRA Course Announcements v1 installed: instructor publishing, student/observer visibility, in-app notifications, and Studio navigation.", flush=True)


if __name__ == "__main__":
    main()
