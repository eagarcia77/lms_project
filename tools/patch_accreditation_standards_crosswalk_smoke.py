from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
TAG = "NUVEDRA_ACCREDITATION_STANDARDS_CROSSWALK_V1_SMOKE"


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
            raise RuntimeError("Could not attach Accreditation Standards Catalog & Crosswalk v1 smoke test to the Course Studio validation flow.")
        block = """    # NUVEDRA_ACCREDITATION_STANDARDS_CROSSWALK_V1_SMOKE
    subprocess.run(
        [sys.executable, 'tools/smoke_test_accreditation_standards_crosswalk_v1.py'],
        check=True,
        env={**os.environ, 'PYTHONPATH': '.'},
    )

"""
        text = text[:index] + block + text[index:]
    PATH.write_text(text, encoding="utf-8")
    print("Accreditation Standards Catalog & Crosswalk v1 functional validation attached to Course Studio smoke tests.", flush=True)

    # Install the external review layer only after standards and frozen evidence portfolios exist.
    from patch_external_accreditation_review_portal_v1 import main as patch_external_accreditation_review_portal_v1
    patch_external_accreditation_review_portal_v1()

    from patch_external_accreditation_review_portal_smoke import main as patch_external_accreditation_review_portal_smoke
    patch_external_accreditation_review_portal_smoke()


if __name__ == "__main__":
    main()
