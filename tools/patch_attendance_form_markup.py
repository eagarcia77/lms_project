from __future__ import annotations

from pathlib import Path

MODULE = Path("app/attendance_participation.py")
TAG = "attendance-record-form-v1"


def main() -> None:
    if not MODULE.is_file():
        raise RuntimeError("Attendance form markup patch requires the generated Attendance & Participation module.")
    text = MODULE.read_text(encoding="utf-8")
    if TAG in text:
        return
    function_at = text.find("    async def attendance_session(session_id: int, request: Request):")
    if function_at < 0:
        raise RuntimeError("Attendance form markup patch could not locate the attendance-session route.")
    start = text.find('        record_rows = "".join(\n', function_at)
    end = text.find("        body = f'''", start)
    if start < 0 or end < 0:
        raise RuntimeError("Attendance form markup patch could not locate the roster-rendering block.")
    replacement = """        # attendance-record-form-v1\n        record_rows = \"\".join(\n            f'''<tr><td><strong>{academic_access.esc(record.get('student_email'))}</strong><form id=\"attendance-record-{int(record['id'])}\" method=\"post\" action=\"{STUDIO_PREFIX}/attendance/sessions/{session_id}/records/{int(record['id'])}\"></form></td><td><select name=\"status\" form=\"attendance-record-{int(record['id'])}\">{_status_options(str(record.get('status') or 'unmarked'))}</select></td><td><input type=\"number\" name=\"minutes_late\" min=\"0\" max=\"240\" value=\"{int(record.get('minutes_late') or 0)}\" form=\"attendance-record-{int(record['id'])}\"></td><td><input name=\"note\" maxlength=\"500\" value=\"{academic_access.esc(record.get('note'), attr=True)}\" form=\"attendance-record-{int(record['id'])}\"></td><td><button class=\"studio-button studio-button--quiet\" form=\"attendance-record-{int(record['id'])}\" data-i18n-en=\"Save\" data-i18n-es=\"Guardar\">Save</button></td></tr>'''\n            for record in records\n        )\n"""
    text = text[:start] + replacement + text[end:]
    compile(text, str(MODULE), "exec")
    MODULE.write_text(text, encoding="utf-8")
    print("Attendance roster forms hardened with explicit form associations across table cells.", flush=True)


if __name__ == "__main__":
    main()
