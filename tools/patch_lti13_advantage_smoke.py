from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
TAG = "NUVEDRA_LTI13_ADVANTAGE_V1_SMOKE"


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
            raise RuntimeError("Could not attach LTI 1.3 / Advantage v1 smoke test to the Course Studio validation flow.")
        block = """    # NUVEDRA_LTI13_ADVANTAGE_V1_SMOKE
    subprocess.run(
        [sys.executable, 'tools/smoke_test_lti13_advantage_v1.py'],
        check=True,
        env={**os.environ, 'PYTHONPATH': '.'},
    )

"""
        text = text[:index] + block + text[index:]
    PATH.write_text(text, encoding="utf-8")

    # LTI 1.3 production hardening is intentionally installed after the full
    # Advantage v1 module has been generated and its baseline smoke is wired.
    from patch_lti13_production_hardening import main as patch_lti13_production_hardening
    patch_lti13_production_hardening()

    from patch_lti13_production_hardening_smoke import main as patch_lti13_production_hardening_smoke
    patch_lti13_production_hardening_smoke()

    print("LTI 1.3 / Advantage v1 and production hardening functional validation attached to Course Studio smoke tests.", flush=True)


if __name__ == "__main__":
    main()
