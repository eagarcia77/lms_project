from __future__ import annotations

from pathlib import Path

PATH = Path("tools/smoke_test_course_editor_access.py")
ASSESSMENTS_SMOKE = Path("tools/smoke_test_assessments_v2.py")
TAG = "NUVEDRA_LEARNING_PATHS_PREREQUISITES_V1_SMOKE"
ASSESSMENTS_TAG = "NUVEDRA_LEARNING_PATHS_ASSESSMENTS_V2_SMOKE"


def patch_assessments_smoke() -> None:
    """Keep Assessments v2 validation aligned with the learner gateway introduced by Learning Paths."""
    text = ASSESSMENTS_SMOKE.read_text(encoding="utf-8")
    if ASSESSMENTS_TAG in text:
        return

    old = '''        course = client.get(f"/learn/courses/{course_id}")
        expect(course, 200, "student course")
        if f'/learn/assessments/{item_id}' not in course.text:
            raise RuntimeError("The student course did not link to the structured assessment.")

        expect(client.post(f"/learn/assessments/{item_id}/start"), 303, "first attempt start")
'''
    new = f'''        course = client.get(f"/learn/courses/{{course_id}}")
        expect(course, 200, "student course")
        # {ASSESSMENTS_TAG}
        gateway = f"/learn/paths/items/{{item_id}}"
        canonical_assessment = f"/learn/assessments/{{item_id}}"
        if gateway not in course.text:
            raise RuntimeError("The student course did not link the structured assessment through the learning-path gateway.")
        gateway_response = client.get(gateway)
        expect(gateway_response, 303, "learning-path gateway for unlocked structured assessment")
        if gateway_response.headers.get("location", "") != canonical_assessment:
            raise RuntimeError(
                "The unlocked learning-path gateway did not redirect to Assessments v2: "
                f"{{gateway_response.headers.get('location', '')!r}}."
            )

        expect(client.post(canonical_assessment + "/start"), 303, "first attempt start")
'''
    if old not in text:
        raise RuntimeError(
            "Learning Paths smoke integration could not locate the Assessments v2 student-course link assertion."
        )
    ASSESSMENTS_SMOKE.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    patch_assessments_smoke()

    text = PATH.read_text(encoding="utf-8")
    if "import subprocess\n" not in text:
        text = text.replace("import os\n", "import os\nimport subprocess\nimport sys\n", 1)
    elif "import sys\n" not in text:
        text = text.replace("import subprocess\n", "import subprocess\nimport sys\n", 1)
    if TAG not in text:
        anchor = "    print(\n        'Visual Course Studio validated:"
        index = text.find(anchor)
        if index < 0:
            raise RuntimeError("Could not attach Learning Paths & Prerequisites v1 smoke test to the Course Studio validation flow.")
        block = """    # NUVEDRA_LEARNING_PATHS_PREREQUISITES_V1_SMOKE
    subprocess.run(
        [sys.executable, 'tools/smoke_test_learning_paths_prerequisites_v1.py'],
        check=True,
        env={**os.environ, 'PYTHONPATH': '.'},
    )

"""
        text = text[:index] + block + text[index:]
    PATH.write_text(text, encoding="utf-8")
    print("Learning Paths & Prerequisites v1 functional validation attached to Course Studio smoke tests, including Assessments v2 learner-gateway compatibility.", flush=True)


if __name__ == "__main__":
    main()
