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
            'def _content_resource_url(value: Any)',
            '/library/assets/',
        ),
    )
    require(
        "app/unified_authoring.py",
        (
            'def _content_resource_url(value: Any)',
            '_content_resource_url(external_url) or None',
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
            'NUVEDRA_GRADEBOOK_V2',
            'data-attempt-review-link',
            'NUVEDRA_CONTENT_LIBRARY_V1',
            'data-content-library-link',
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
            'NUVEDRA_GRADEBOOK_V2_FEEDBACK_LINK',
            'View feedback',
        ),
    )
    require(
        "app/gradebook_v2.py",
        (
            'CREATE TABLE IF NOT EXISTS nuvedra_assessment_answer_reviews',
            '/courses/{{course_id}}/attempts',
            '/attempts/{{attempt_id}}/review',
            '/answers/{{answer_id}}/review',
            '/learn/assessments/{item_id}/attempts/{attempt_id}/feedback',
            'assessment_answer_reviewed',
            'data-testid="structured-attempts-review"',
            'data-testid="attempt-review"',
            'data-testid="student-attempt-feedback"',
        ),
    )
    require(
        "app/student_experience.py",
        (
            'data-testid="student-dashboard"',
            'data-testid="student-course-v2"',
            'data-testid="student-item-v2"',
            '/learn/todo',
            'student_content_completion_changed',
        ),
    )
    require(
        "app/content_library.py",
        (
            'CREATE TABLE IF NOT EXISTS nuvedra_library_assets',
            'CREATE TABLE IF NOT EXISTS nuvedra_library_uses',
            'data-testid="content-library-v1"',
            '/library/assets/{asset_id}/download',
            'content_library_asset_created',
            'content_library_asset_attached',
            'MAX_UPLOAD_BYTES = 20 * 1024 * 1024',
            'ACCESSIBILITY_REQUIRED',
        ),
    )
    require(
        "app/academic_portal.py",
        (
            'from app.gradebook import register_gradebook',
            'register_gradebook(app)',
            'from app.assessment_engine import register_assessment_engine',
            'register_assessment_engine(app)',
            'from app.gradebook_v2 import register_gradebook_v2',
            'register_gradebook_v2(app)',
            'from app.student_experience import register_student_experience',
            'register_student_experience(app)',
            'from app.content_library import register_content_library',
            'register_content_library(app)',
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
            'NUVEDRA_GRADEBOOK_V2_SMOKE',
            'tools/smoke_test_gradebook_v2.py',
            'NUVEDRA_STUDENT_EXPERIENCE_V2_SMOKE',
            'tools/smoke_test_student_experience_v2.py',
            'NUVEDRA_CONTENT_LIBRARY_V1_SMOKE',
            'tools/smoke_test_content_library_v1.py',
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
    require(
        "tools/smoke_test_gradebook_v2.py",
        (
            'data-testid="structured-attempts-review"',
            'data-testid="attempt-review"',
            'manual essay grading',
            'data-testid="student-attempt-feedback"',
            '3 / 3',
        ),
    )
    require(
        "tools/smoke_test_content_library_v1.py",
        (
            'data-testid="content-library-v1"',
            'accessibility requirement',
            'library file upload',
            'attach library asset',
            'protected student download',
            'unrelated user download protection',
        ),
    )
    require(
        "app/static/styles.css",
        (
            'NUVEDRA_LOGO_VISIBILITY_V2',
            '.site-header .brand img',
            'max-width:none',
        ),
    )
    require(
        "app/static/assets/nuvedra-logo.svg",
        (
            'viewBox="-8 -6 288 92"',
            'preserveAspectRatio="xMinYMid meet"',
            '>NUVEDRA</text>',
        ),
    )
    print("Visual Course Studio, Gradebook v1/v2, Assessments v2, Student Experience v2, Content Library v1, and full NUVEDRA logo source validated with functional smoke coverage.", flush=True)


if __name__ == "__main__":
    main()
