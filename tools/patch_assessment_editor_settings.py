from __future__ import annotations

from pathlib import Path

EDITOR = Path("app/course_editor_access.py")
STUDIO_JS = Path("app/static/course-studio.js")
TAG = "NUVEDRA_ASSESSMENT_EDITOR_V2"


def main() -> None:
    text = EDITOR.read_text(encoding="utf-8")
    text = text.replace(
        'if item_type == "assessment" else {}',
        'if item_type in {"assessment", "quiz"} else {}',
    )
    text = text.replace(
        "str(item.get('item_type')) != 'assessment'",
        "str(item.get('item_type')) not in ('assessment', 'quiz')",
    )
    old = '<option value="true_false"{_selected(assessment.get(\'response_type\'), \'true_false\')}>True or false</option></select>'
    new = '<option value="true_false"{_selected(assessment.get(\'response_type\'), \'true_false\')}>True or false</option><option value="structured"{_selected(assessment.get(\'response_type\'), \'structured\')}>Structured questions</option></select>'
    if new not in text:
        if old not in text:
            raise RuntimeError("Could not add the structured response option to the visual item editor.")
        text = text.replace(old, new, 1)
    if TAG not in text:
        text = text.replace(
            'STUDIO_ASSETS = """',
            f'# {TAG}\nSTUDIO_ASSETS = """',
            1,
        )
    EDITOR.write_text(text, encoding="utf-8")

    js = STUDIO_JS.read_text(encoding="utf-8")
    js = js.replace(
        'const update = () => { settings.hidden = select.value !== "assessment"; };',
        'const update = () => { settings.hidden = !["assessment", "quiz"].includes(select.value); };',
    )
    STUDIO_JS.write_text(js, encoding="utf-8")
    print("Assessment editor settings upgraded for structured assessments and quizzes.", flush=True)


if __name__ == "__main__":
    main()
