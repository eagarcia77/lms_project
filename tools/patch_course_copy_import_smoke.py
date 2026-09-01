from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
SMOKE = Path("tools/smoke_test_course_copy_import_v1.py")
TAG = "NUVEDRA_COURSE_COPY_IMPORT_V1_SMOKE"


def main() -> None:
    if not SMOKE.is_file():
        raise RuntimeError("Course Copy & Import v1 smoke test is missing.")
    compile(SMOKE.read_text(encoding="utf-8"), str(SMOKE), "exec")
    text = PATH.read_text(encoding="utf-8")
    if "import subprocess\n" not in text:
        text = text.replace("import os\n", "import os\nimport subprocess\nimport sys\n", 1)
    elif "import sys\n" not in text:
        text = text.replace("import subprocess\n", "import subprocess\nimport sys\n", 1)
    if TAG not in text:
        anchor = "    print(\n        'Visual Course Studio validated:"
        index = text.find(anchor)
        if index < 0:
            raise RuntimeError("Could not attach Course Copy & Import v1 smoke test to the Course Studio validation flow.")
        block = "    # NUVEDRA_COURSE_COPY_IMPORT_V1_SMOKE\n    subprocess.run(\n        [sys.executable, 'tools/smoke_test_course_copy_import_v1.py'],\n        check=True,\n        env={**os.environ, 'PYTHONPATH': '.'},\n    )\n\n"
        text = text[:index] + block + text[index:]
    PATH.write_text(text, encoding="utf-8")
    print("Course Copy & Import v1 functional validation attached to Course Studio smoke tests.", flush=True)


if __name__ == "__main__":
    main()
