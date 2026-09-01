from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/calendar_notifications_module.py.txt")
MODULE = Path("app/calendar_notifications.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_CALENDAR_NOTIFICATIONS_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.calendar_notifications import register_calendar_notifications\n"
    if import_line not in text:
        anchors = (
            "from app.learning_analytics import register_learning_analytics\n",
            "from app.accessibility_checker import register_accessibility_checker\n",
            "from app.content_library import register_content_library\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Calendar and Notifications v1 could not locate an academic portal import anchor.")

    registration = "    register_calendar_notifications(app)\n"
    if registration not in text:
        anchors = (
            "    register_learning_analytics(app)\n",
            "    register_accessibility_checker(app)\n",
            "    register_content_library(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Calendar and Notifications v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_CALENDAR_NOTIFICATIONS_V1
  function initializeCalendarNotificationsLinks() {
    const courseStudio = document.querySelector('[data-testid="visual-course-studio"]');
    const courseMatch = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (courseStudio && courseMatch && !courseStudio.querySelector('[data-course-calendar-link]')) {
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
        link.href = `/faculty/studio/courses/${courseMatch[1]}/calendar`;
        link.dataset.courseCalendarLink = 'v1';
        link.dataset.i18nEn = 'Course Calendar';
        link.dataset.i18nEs = 'Calendario del curso';
        link.textContent = language() === 'es' ? 'Calendario del curso' : 'Course Calendar';
        actions.appendChild(link);
      }
    }

    const studentDashboard = document.querySelector('[data-testid="student-dashboard"]');
    if (studentDashboard && !studentDashboard.querySelector('[data-student-calendar-link]')) {
      const hero = studentDashboard.querySelector('.studio-hero');
      if (hero) {
        let actions = hero.querySelector('.studio-actions');
        if (!actions) {
          actions = document.createElement('div');
          actions.className = 'studio-actions';
          hero.appendChild(actions);
        }
        const calendar = document.createElement('a');
        calendar.className = 'studio-button studio-button--quiet';
        calendar.href = '/learn/calendar';
        calendar.dataset.studentCalendarLink = 'v1';
        calendar.dataset.i18nEn = 'Calendar';
        calendar.dataset.i18nEs = 'Calendario';
        calendar.textContent = language() === 'es' ? 'Calendario' : 'Calendar';
        actions.appendChild(calendar);

        const notifications = document.createElement('a');
        notifications.className = 'studio-button studio-button--quiet';
        notifications.href = '/portal/notifications';
        notifications.dataset.notificationsLink = 'v1';
        notifications.dataset.i18nEn = 'Notifications';
        notifications.dataset.i18nEs = 'Notificaciones';
        notifications.textContent = language() === 'es' ? 'Notificaciones' : 'Notifications';
        actions.appendChild(notifications);
      }
    }
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Calendar and Notifications v1 could not insert Studio navigation functions.")
        text = text.replace(marker, block + marker, 1)
    init = "    initializeCalendarNotificationsLinks();\n"
    if init not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Calendar and Notifications v1 could not initialize navigation links.")
        text = text.replace(marker, init + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Calendar and Notifications v1 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    print("NUVEDRA Calendar and Notifications v1 installed: course events, due-date calendar, student notifications, and Studio navigation.", flush=True)


if __name__ == "__main__":
    main()
