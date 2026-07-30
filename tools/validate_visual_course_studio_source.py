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
            'visual_studio_item_created',
            'visual_studio_item_updated',
            'assessment_response_type',
            'administrator_enabled_as_instructor',
        ),
    )
    require(
        "app/static/course-studio.js",
        (
            'nuvedra.studio.draft.',
            'data-rich-editor',
            'data-assessment-settings',
            'data-select-type',
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
    print("Visual Course Studio source validated.", flush=True)


if __name__ == "__main__":
    main()
