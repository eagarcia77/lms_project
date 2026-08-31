from __future__ import annotations

from pathlib import Path


def require(path: str, markers: tuple[str, ...]) -> None:
    text = Path(path).read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise RuntimeError(f"{path} is missing required markers: {missing}")


def main() -> None:
    require(
        "app/course_editor_access.py",
        (
            'STUDIO_PREFIX = "/faculty/studio"',
            'data-testid="visual-course-studio"',
            'data-testid="visual-module-studio"',
            'data-testid="visual-item-editor"',
            'data-testid="instructor-course-preview"',
            'data-testid="instructor-item-preview"',
            'NUVEDRA_VISUAL_STUDIO_PREVIEW_V1',
            'NUVEDRA_ASSESSMENT_EDITOR_V2',
            'Structured questions',
            'visual_studio_item_created',
            'visual_studio_item_updated',
            'assessment_response_type',
            'administrator_enabled_as_instructor',
            'due_at=due_at.strip(), status="draft")',
            'due_at=str(item.get("due_at") or ""), status="draft")',
            'due_at=str(source.get("due_at") or ""), status="draft")',
        ),
    )
    require(
        "app/static/course-studio.js",
        (
            'nuvedra.studio.draft.',
            'data-rich-editor',
            'data-assessment-settings',
            'data-select-type',
            'NUVEDRA_GRADEBOOK_V1',
            'data-gradebook-link',
            'NUVEDRA_ASSESSMENTS_V2',
            'data-assessment-builder-link',
            'data-question-form',
        ),
    )
    require(
        "app/static/course-studio.css",
        (
            '.studio-shell',
            '.studio-type-grid',
            '@media(prefers-reduced-motion:reduce)',
            '@media(forced-colors:active)',
        ),
    )
    require(
        "app/gradebook.py",
        (
            'CREATE TABLE IF NOT EXISTS nuvedra_grades',
            '/courses/{{course_id}}/gradebook',
            '/submissions/{{submission_id}}/grade',
            'gradebook.csv',
            '/learn/courses/{course_id}/grades',
            'submission_graded',
            'data-testid="course-gradebook"',
            'data-testid="student-grades"',
        ),
    )
    require(
        "app/assessment_engine.py",
        (
            'CREATE TABLE IF NOT EXISTS nuvedra_assessment_questions',
            'CREATE TABLE IF NOT EXISTS nuvedra_question_bank',
            'CREATE TABLE IF NOT EXISTS nuvedra_assessment_attempts',
            'CREATE TABLE IF NOT EXISTS nuvedra_assessment_answers',
            '/items/{{item_id}}/assessment',
            '/assessment/questions',
            '/assessment/bank/{{bank_id}}/import',
            '/learn/assessments/{item_id}',
            '/learn/assessments/{item_id}/start',
            'structured_assessment_submitted',
            'NUVEDRA AutoGrade',
            'data-testid="assessment-builder"',
            'data-testid="student-assessment"',
        ),
    )
    require(
        "app/academic_portal.py",
        (
            'from app.gradebook import register_gradebook',
            'register_gradebook(app)',
            'from app.assessment_engine import register_assessment_engine',
            'register_assessment_engine(app)',
        ),
    )
    require(
        "app/student_portal.py",
        (
            'def _student_item_href',
            '/learn/assessments/{item_id}',
            'Use the structured assessment workflow for this item.',
        ),
    )
    require(
        "app/platform_upgrade.py",
        (
            'gradebook.google_user = academic_user',
            '("app.gradebook", "app.assessment_engine")',
        ),
    )
    require(
        "tools/smoke_test_course_editor_access.py",
        (
            'NUVEDRA_ASSESSMENTS_V2_SMOKE',
            'tools/smoke_test_assessments_v2.py',
        ),
    )
    require(
        "tools/smoke_test_assessments_v2.py",
        (
            'data-testid="assessment-builder"',
            'question-bank import',
            'data-assessment-timer',
            'Automatic grading expected 4 points',
            'essay question authoring',
        ),
    )
    print("Visual Course Studio, Gradebook v1, and Assessments v2 source validated with functional smoke coverage.", flush=True)


if __name__ == "__main__":
    main()
