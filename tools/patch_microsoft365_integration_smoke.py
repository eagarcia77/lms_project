from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
TAG = "NUVEDRA_MICROSOFT365_INTEGRATION_V1_SMOKE"


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
            raise RuntimeError("Could not attach Microsoft 365 Integration v1 smoke test to the Course Studio validation flow.")
        block = """    # NUVEDRA_MICROSOFT365_INTEGRATION_V1_SMOKE
    subprocess.run(
        [sys.executable, 'tools/smoke_test_microsoft365_integration_v1.py'],
        check=True,
        env={**os.environ, 'PYTHONPATH': '.'},
    )

"""
        text = text[:index] + block + text[index:]
    PATH.write_text(text, encoding="utf-8")
    print("Microsoft 365 Integration v1 functional validation attached to Course Studio smoke tests.", flush=True)

    # Install the institutional Teams layer only after Microsoft 365 Integration v1 exists.
    from patch_microsoft365_education_v2 import main as patch_microsoft365_education_v2
    patch_microsoft365_education_v2()

    from patch_microsoft365_education_v2_smoke import main as patch_microsoft365_education_v2_smoke
    patch_microsoft365_education_v2_smoke()


if __name__ == "__main__":
    main()
