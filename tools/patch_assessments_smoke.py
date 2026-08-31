from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
ROLE_SMOKE = Path("tools/smoke_test_academic_roles.py")
TAG = "NUVEDRA_ASSESSMENTS_V2_SMOKE"


def main() -> None:
    from patch_assessment_editor_settings import main as patch_assessment_editor_settings
    patch_assessment_editor_settings()

    # The academic-role smoke test validates the legacy free-text assessment path.
    # Assessments v2 reserves item_type=assessment/quiz for the structured runner,
    # so keep that older smoke scenario on assignment where the free-text workflow remains valid.
    role_text = ROLE_SMOKE.read_text(encoding="utf-8")
    role_text = role_text.replace("'item_type': 'assessment'", "'item_type': 'assignment'")
    ROLE_SMOKE.write_text(role_text, encoding="utf-8")

    text = PATH.read_text(encoding="utf-8")
    if "import subprocess\n" not in text:
        text = text.replace("import os\n", "import os\nimport subprocess\nimport sys\n", 1)
    if TAG not in text:
        marker = "    print(\n        'Visual Course Studio validated: administrator-to-instructor access, visual module and content editing, assessment settings, publishing, and duplication.',\n        flush=True,\n    )\n"
        if marker not in text:
            raise RuntimeError("Could not attach Assessments v2 smoke test to the existing Docker validation flow.")
        block = "    # NUVEDRA_ASSESSMENTS_V2_SMOKE\n    subprocess.run(\n        [sys.executable, 'tools/smoke_test_assessments_v2.py'],\n        check=True,\n        env={**os.environ, 'PYTHONPATH': '.'},\n    )\n\n"
        text = text.replace(marker, block + marker, 1)
    PATH.write_text(text, encoding="utf-8")
    print("Assessments v2 editor settings and functional smoke validation attached to Course Studio.", flush=True)


if __name__ == "__main__":
    main()
