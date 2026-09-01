from __future__ import annotations

from pathlib import Path

STYLES = Path("app/static/styles.css")
LOGO = Path("app/static/assets/nuvedra-logo.svg")
TAG = "NUVEDRA_LOGO_VISIBILITY_V2"

LOGO_CSS = r'''
/* NUVEDRA_LOGO_VISIBILITY_V2 */
.site-header .brand{
  min-width:280px;
  flex:0 0 280px;
  padding:7px 0;
  overflow:visible;
}
.site-header .brand img{
  width:272px;
  height:auto;
  max-width:none;
  max-height:90px;
  object-fit:contain;
  object-position:left center;
  overflow:visible;
}
@media(max-width:1450px){
  .site-header{gap:16px;padding-left:24px;padding-right:24px}
  .site-header .brand{min-width:250px;flex-basis:250px}
  .site-header .brand img{width:246px}
  .header-features{gap:12px}
}
@media(max-width:1180px){
  .site-header .brand{min-width:230px;flex-basis:230px}
  .site-header .brand img{width:226px}
}
'''


def main() -> None:
    # Final post-V3 feature installation happens here after the Studio, Gradebook,
    # Assessments, Student Experience, and Content Library patches are complete.
    from patch_accessibility_checker_v1 import main as patch_accessibility_checker_v1
    patch_accessibility_checker_v1()

    from patch_accessibility_checker_smoke import main as patch_accessibility_checker_smoke
    patch_accessibility_checker_smoke()

    from patch_learning_analytics_v1 import main as patch_learning_analytics_v1
    patch_learning_analytics_v1()

    from patch_learning_analytics_smoke import main as patch_learning_analytics_smoke
    patch_learning_analytics_smoke()

    from patch_calendar_notifications_v1 import main as patch_calendar_notifications_v1
    patch_calendar_notifications_v1()

    from patch_calendar_notifications_smoke import main as patch_calendar_notifications_smoke
    patch_calendar_notifications_smoke()

    from patch_course_announcements_v1 import main as patch_course_announcements_v1
    patch_course_announcements_v1()

    from patch_course_announcements_smoke import main as patch_course_announcements_smoke
    patch_course_announcements_smoke()

    if not STYLES.is_file() or not LOGO.is_file():
        raise RuntimeError("NUVEDRA logo visibility patch requires the homepage styles and logo asset.")
    css = STYLES.read_text(encoding="utf-8")
    if TAG not in css:
        css += "\n" + LOGO_CSS.strip() + "\n"
        STYLES.write_text(css, encoding="utf-8")
    svg = LOGO.read_text(encoding="utf-8")
    required = ('viewBox="-8 -6 288 92"', 'preserveAspectRatio="xMinYMid meet"', '>NUVEDRA</text>')
    missing = [marker for marker in required if marker not in svg]
    if missing:
        raise RuntimeError(f"NUVEDRA logo asset is not using the expanded safe viewport: {missing}")
    print("NUVEDRA Accessibility Checker v1, Learning Analytics v1, Calendar and Notifications v1, Course Announcements v1, and logo visibility finalized for production.", flush=True)


if __name__ == "__main__":
    main()
