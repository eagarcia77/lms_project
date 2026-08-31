from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
TAG = "NUVEDRA_ASSESSMENTS_V2_SMOKE"


def main() -> None:
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
    print("Assessments v2 functional smoke test attached to Course Studio validation.", flush=True)


if __name__ == "__main__":
    main()
