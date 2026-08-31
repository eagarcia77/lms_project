from __future__ import annotations

from pathlib import Path

SOURCE = Path("tools/student_experience_v2_module.py.txt")
MODULE = Path("app/student_experience.py")
ACADEMIC_PORTAL = Path("app/academic_portal.py")
PORTAL_HOME = Path("app/google_hub_safe.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Student Experience v2 patch could not find {label}: {old[:160]!r}")
    return text.replace(old, new, 1)


def patch_module_legacy_submissions() -> None:
    text = MODULE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '            completion=_completion_map(conn,course_id,user["email"]); completed=completion.get(item_id,False)\n        external=',
        '            completion=_completion_map(conn,course_id,user["email"]); completed=completion.get(item_id,False)\n            submissions=rows(execute(conn,"SELECT * FROM nuvedra_submissions WHERE item_id=? AND lower(student_email)=?",(item_id,user["email"].lower())))\n        external=',
        "legacy submission lookup",
    )
    marker = '        completion_button=""\n'
    block = """        assessment=""
        if str(item.get("item_type")) in academic_access.ASSESSMENT_TYPES and str(access.get("course_role"))=="student":
            existing=submissions[0] if submissions else {}
            saved='<p class="studio-notice" data-i18n-en="Your response has been submitted. You can update it while the activity remains available." data-i18n-es="Su respuesta está entregada. Puede actualizarla mientras la actividad esté disponible.">Your response has been submitted. You can update it while the activity remains available.</p>' if submissions else ""
            assessment=f'''<section class="studio-panel"><h3 data-i18n-en="Submit response" data-i18n-es="Entregar respuesta">Submit response</h3>{saved}<form method="post" action="/learn/items/{item_id}/submit"><label><span data-i18n-en="Response" data-i18n-es="Respuesta">Response</span><textarea name="response_text" required>{_esc(existing.get('response_text'))}</textarea></label><label><span data-i18n-en="Evidence link (optional)" data-i18n-es="Enlace de evidencia (opcional)">Evidence link (optional)</span><input type="url" name="response_url" value="{_esc(existing.get('response_url'),attr=True)}"></label><button class="studio-button" data-i18n-en="Save and submit" data-i18n-es="Guardar y entregar">Save and submit</button></form></section>'''
        elif str(item.get("item_type")) in academic_access.ASSESSMENT_TYPES:
            assessment='<p class="studio-notice" data-i18n-en="Observers can view this activity but cannot submit responses." data-i18n-es="Los observadores pueden consultar esta actividad, pero no enviar respuestas.">Observers can view this activity but cannot submit responses.</p>'
"""
    if block not in text:
        if marker not in text:
            raise RuntimeError("Student Experience v2 could not restore legacy assessment submissions.")
        text = text.replace(marker, block + marker, 1)
    text = replace_once(
        text,
        "</article></main>'''\n        return academic_access.portal_page(\"Content\",body,user)",
        "</article>{assessment}</main>'''\n        return academic_access.portal_page(\"Content\",body,user)",
        "legacy assessment content render",
    )
    MODULE.write_text(text, encoding="utf-8")


def patch_academic_portal() -> None:
    text = ACADEMIC_PORTAL.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from app.gradebook_v2 import register_gradebook_v2\n",
        "from app.gradebook_v2 import register_gradebook_v2\nfrom app.student_experience import register_student_experience\n",
        "student experience import",
    )
    text = replace_once(
        text,
        '    register_gradebook_v2(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook, Assessments v2 y Gradebook v2.", flush=True)\n',
        '    register_gradebook_v2(app)\n    register_student_experience(app)\n    print("Portal académico por roles registrado: administrador, profesor, estudiante, Gradebook, Assessments v2, Gradebook v2 y Student Experience v2.", flush=True)\n',
        "student experience registration",
    )
    ACADEMIC_PORTAL.write_text(text, encoding="utf-8")


def patch_portal_dashboard_link() -> None:
    text = PORTAL_HOME.read_text(encoding="utf-8")
    marker = "NUVEDRA_STUDENT_EXPERIENCE_V2_PORTAL_LINK"
    if marker in text:
        return
    old = "        if author_cards:\n"
    new = '''        # NUVEDRA_STUDENT_EXPERIENCE_V2_PORTAL_LINK
        if student_cards:
            body += '<p><a class="button secondary" href="/learn/dashboard" data-i18n-en="Student dashboard" data-i18n-es="Panel del estudiante">Student dashboard</a></p>'
        if author_cards:
'''
    if old not in text:
        raise RuntimeError("Student Experience v2 could not add the dashboard link to /portal.")
    PORTAL_HOME.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise RuntimeError("Student Experience v2 source template is missing.")
    MODULE.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    patch_module_legacy_submissions()
    patch_academic_portal()
    patch_portal_dashboard_link()
    print("NUVEDRA Student Experience v2 installed: dashboard, progress, continue learning, to-do, and completion tracking.", flush=True)


if __name__ == "__main__":
    main()
