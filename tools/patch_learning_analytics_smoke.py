from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
TAG = "NUVEDRA_LEARNING_ANALYTICS_V1_SMOKE"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "import subprocess\n" not in text:
        if "import os\n" in text:
            text = text.replace("import os\n", "import os\nimport subprocess\nimport sys\n", 1)
        else:
            text = text.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nimport subprocess\nimport sys\n", 1)
    elif "import sys\n" not in text:
        text = text.replace("import subprocess\n", "import subprocess\nimport sys\n", 1)
    if TAG not in text:
        main_end = text.rfind("\n\n\nif __name__")
        if main_end < 0:
            raise RuntimeError("Could not locate the Course Studio smoke-test main boundary for Learning Analytics v1.")
        print_pos = text.rfind("\n    print(", 0, main_end)
        insert_at = print_pos if print_pos >= 0 else main_end
        block = "\n    # NUVEDRA_LEARNING_ANALYTICS_V1_SMOKE\n    subprocess.run(\n        [sys.executable, 'tools/smoke_test_learning_analytics_v1.py'],\n        check=True,\n        env={**os.environ, 'PYTHONPATH': '.'},\n    )\n"
        text = text[:insert_at] + block + text[insert_at:]
    PATH.write_text(text, encoding="utf-8")
    print("Learning Analytics v1 functional validation attached to Course Studio smoke tests.", flush=True)


if __name__ == "__main__":
    main()
