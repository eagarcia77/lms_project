from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
TAG = "NUVEDRA_EXTERNAL_ACCREDITATION_REVIEW_PORTAL_V1_SMOKE"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "import subprocess\n" not in text:
        text = text.replace("import os\n", "import os\nimport subprocess\nimport sys\n", 1)
    elif "import sys\n" not in text:
        text = text.replace("import subprocess\n", "import subprocess\nimport sys\n", 1)
    if TAG not in text:
        anchor = "    print(\n        'Visual Course Studio validated:"
        index = text.find(anchor)
        if index < 0:
            raise RuntimeError("Could not attach External Accreditation Review Portal v1 smoke test to the Course Studio validation flow.")
        block = """    # NUVEDRA_EXTERNAL_ACCREDITATION_REVIEW_PORTAL_V1_SMOKE
    subprocess.run(
        [sys.executable, 'tools/smoke_test_external_accreditation_review_portal_v1.py'],
        check=True,
        env={**os.environ, 'PYTHONPATH': '.'},
    )

"""
        text = text[:index] + block + text[index:]
    PATH.write_text(text, encoding="utf-8")
    print("External Accreditation Review Portal v1 functional validation attached to Course Studio smoke tests.", flush=True)


if __name__ == "__main__":
    main()
