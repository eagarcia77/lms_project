from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/certificates_completion_module.py.txt")
MODULE = Path("app/certificates_completion.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
STUDIO_JS = Path("app/static/course-studio.js")
STUDENT_EXPERIENCE = Path("app/student_experience.py")
TAG = "NUVEDRA_CERTIFICATES_COMPLETION_V1"


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    import_line = "from app.certificates_completion import register_certificates_completion\n"
    if import_line not in text:
        anchors = (
            "from app.attendance_participation import register_attendance_participation\n",
            "from app.people_groups import register_people_groups\n",
            "from app.course_copy_import import register_course_copy_import\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + import_line, 1)
                break
        else:
            raise RuntimeError("Certificates & Completion v1 could not locate an academic portal import anchor.")
    registration = "    register_certificates_completion(app)\n"
    if registration not in text:
        anchors = (
            "    register_attendance_participation(app)\n",
            "    register_people_groups(app)\n",
            "    register_course_copy_import(app)\n",
        )
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, anchor + registration, 1)
                break
        else:
            raise RuntimeError("Certificates & Completion v1 could not locate an academic portal registration anchor.")
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_studio_js() -> None:
    text = STUDIO_JS.read_text(encoding="utf-8")
    if TAG not in text:
        block = r'''
  // NUVEDRA_CERTIFICATES_COMPLETION_V1
  function initializeCertificatesCompletionLink() {
    const root = document.querySelector('[data-testid="visual-course-studio"]');
    const match = window.location.pathname.match(/^\/faculty\/studio\/courses\/(\d+)$/);
    if (!root || !match || root.querySelector('[data-certificates-completion-link]')) return;
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
    link.href = `/faculty/studio/courses/${match[1]}/completion`;
    link.dataset.certificatesCompletionLink = 'v1';
    link.dataset.i18nEn = 'Completion & Certificates';
    link.dataset.i18nEs = 'Finalización y certificados';
    link.textContent = language() === 'es' ? 'Finalización y certificados' : 'Completion & Certificates';
    actions.appendChild(link);
  }

'''
        marker = "  function start() {\n"
        if marker not in text:
            raise RuntimeError("Certificates & Completion v1 could not insert Studio navigation.")
        text = text.replace(marker, block + marker, 1)
    call = "    initializeCertificatesCompletionLink();\n"
    if call not in text:
        marker = "    initializeDrafts();\n"
        if marker not in text:
            raise RuntimeError("Certificates & Completion v1 could not initialize Studio navigation.")
        text = text.replace(marker, call + marker, 1)
    STUDIO_JS.write_text(text, encoding="utf-8")


def patch_student_experience() -> None:
    if not STUDENT_EXPERIENCE.is_file():
        raise RuntimeError("Certificates & Completion v1 requires the generated Student Experience v2 module.")
    text = STUDENT_EXPERIENCE.read_text(encoding="utf-8")
    if 'href="/learn/completions"' not in text:
        attendance_link = '<a href="/learn/attendance" data-i18n-en="My Attendance" data-i18n-es="Mi asistencia">My Attendance</a>'
        replacement = attendance_link + '<span>/</span><a href="/learn/completions" data-i18n-en="My Completion" data-i18n-es="Mi finalización">My Completion</a>'
        if attendance_link in text:
            text = text.replace(attendance_link, replacement, 1)
        else:
            groups_link = '<a href="/learn/groups" data-i18n-en="My Groups" data-i18n-es="Mis grupos">My Groups</a>'
            if groups_link not in text:
                raise RuntimeError("Certificates & Completion v1 could not add My Completion to the student dashboard.")
            text = text.replace(groups_link, groups_link + '<span>/</span><a href="/learn/completions" data-i18n-en="My Completion" data-i18n-es="Mi finalización">My Completion</a>', 1)
    STUDENT_EXPERIENCE.write_text(text, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Certificates & Completion v1 source template is missing.")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(MODULE), "exec")
    MODULE.write_text(source, encoding="utf-8")
    patch_academic_portal()
    patch_studio_js()
    patch_student_experience()
    compile(STUDENT_EXPERIENCE.read_text(encoding="utf-8"), str(STUDENT_EXPERIENCE), "exec")
    print("NUVEDRA Certificates & Course Completion v1 installed: configurable criteria, required activities, instructor-reviewed awards, verification, revocation, notifications, and student navigation.", flush=True)


if __name__ == "__main__":
    main()
