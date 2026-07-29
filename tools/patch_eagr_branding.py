from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "app"
BRAND = "EAGR Learning XR"
OLD_BRAND = "NEXUS EDU XR"
MARKER = "EAGR_LEARNING_XR_BRANDING_V1"

TEXT_EXTENSIONS = {".py", ".html", ".js", ".json", ".css", ".svg"}
EXCLUDED_FILES = {
    "environment_status.py",  # updated explicitly and validated separately
}

EXACT_REPLACEMENTS = (
    ("NEXUS EDU XR · STAGING", "EAGR Learning XR · STAGING"),
    ("NEXUS EDU XR STAGING", "EAGR Learning XR STAGING"),
    ("NEXUS EDU XR", "EAGR Learning XR"),
    ("NEXUS XR", "EAGR XR"),
    ("Administrador NEXUS Staging", "Administrador EAGR Learning XR Staging"),
    ("Administrador NEXUS", "Administrador EAGR Learning XR"),
    (
        '<div class="brand-mark" aria-hidden="true">NX</div>',
        '<div class="brand-mark" aria-hidden="true">EG</div>',
    ),
    (
        "<strong>NEXUS</strong><span>EDU XR</span>",
        "<strong>EAGR</strong><span>Learning XR</span>",
    ),
)

ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="EAGR Learning XR">
  <rect width="512" height="512" rx="120" fill="#007B5F"/>
  <circle cx="256" cy="256" r="154" fill="none" stroke="#FED141" stroke-width="26"/>
  <text x="256" y="286" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="150" font-weight="800" fill="#FFFFFF">EG</text>
  <path d="M180 344h152" stroke="#FED141" stroke-width="18" stroke-linecap="round"/>
</svg>
'''


def _public_brand_replace(source: str) -> str:
    revised = source
    for old, new in EXACT_REPLACEMENTS:
        revised = revised.replace(old, new)

    # Replace the standalone public word NEXUS, but preserve compatibility-sensitive
    # identifiers such as NEXUS_SESSION_SECRET, NEXUS_ADMIN_* and NEXUS-COURSE-1.0.
    revised = re.sub(r"\bNEXUS\b(?![_-])", BRAND, revised)
    return revised


def _candidate_files() -> list[Path]:
    files: list[Path] = []
    for path in APP_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if path.name in EXCLUDED_FILES:
            continue
        files.append(path)
    return sorted(files)


def patch_application_files() -> int:
    changed = 0
    for path in _candidate_files():
        source = path.read_text(encoding="utf-8")
        revised = _public_brand_replace(source)
        if revised != source:
            path.write_text(revised, encoding="utf-8")
            changed += 1
    return changed


def patch_environment_status() -> int:
    path = APP_ROOT / "environment_status.py"
    source = path.read_text(encoding="utf-8")
    revised = source.replace(
        'os.getenv("APP_NAME", "NEXUS EDU XR")',
        'os.getenv("APP_NAME", "EAGR Learning XR")',
    )
    if revised != source:
        path.write_text(revised, encoding="utf-8")
        return 1
    return 0


def patch_icon() -> int:
    path = APP_ROOT / "static" / "assets" / "icon.svg"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ICON_SVG, encoding="utf-8")
    return int(previous != ICON_SVG)


def validate_branding() -> None:
    required = {
        APP_ROOT / "static" / "index.html": (BRAND, "<strong>EAGR</strong><span>Learning XR</span>"),
        APP_ROOT / "static" / "manifest.json": (BRAND,),
        APP_ROOT / "static" / "assets" / "icon.svg": (BRAND, ">EG</text>"),
        APP_ROOT / "config.py": (BRAND,),
        APP_ROOT / "admin_portal.py": (BRAND,),
        APP_ROOT / "admin_console.py": (BRAND,),
        APP_ROOT / "environment_status.py": (BRAND,),
    }
    missing: dict[str, list[str]] = {}
    for path, markers in required.items():
        source = path.read_text(encoding="utf-8")
        absent = [marker for marker in markers if marker not in source]
        if absent:
            missing[str(path.relative_to(ROOT))] = absent
    if missing:
        raise RuntimeError(f"Cambio de marca incompleto: {missing}")

    public_files = [
        APP_ROOT / "static" / "index.html",
        APP_ROOT / "static" / "manifest.json",
        APP_ROOT / "static" / "assets" / "icon.svg",
        APP_ROOT / "admin_portal.py",
        APP_ROOT / "admin_console.py",
        APP_ROOT / "admin_system.py",
        APP_ROOT / "unified_authoring.py",
        APP_ROOT / "innovation_hub.py",
    ]
    residual: list[str] = []
    for path in public_files:
        source = path.read_text(encoding="utf-8")
        if OLD_BRAND in source or re.search(r"\bNEXUS\b(?![_-])", source):
            residual.append(str(path.relative_to(ROOT)))
    if residual:
        raise RuntimeError(f"Persisten referencias públicas a la marca anterior: {residual}")

    # Confirm that compatibility-sensitive identifiers were not renamed.
    admin_console = (APP_ROOT / "admin_console.py").read_text(encoding="utf-8")
    if "NEXUS_SESSION_SECRET" not in admin_console:
        raise RuntimeError("Se alteró la variable técnica NEXUS_SESSION_SECRET.")
    if "nexus_admin_users" not in admin_console:
        raise RuntimeError("Se alteró la tabla técnica nexus_admin_users.")

    innovation = (APP_ROOT / "innovation_hub.py").read_text(encoding="utf-8")
    if "NEXUS-COURSE-1.0" not in innovation:
        raise RuntimeError("Se alteró el formato técnico NEXUS-COURSE-1.0.")

    manifest_path = APP_ROOT / "static" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != BRAND:
        raise RuntimeError("El manifiesto no utiliza EAGR Learning XR como nombre oficial.")
    if manifest.get("short_name") != "EAGR XR":
        raise RuntimeError("El nombre corto del manifiesto debe ser EAGR XR.")


def main() -> None:
    changes = patch_application_files() + patch_environment_status() + patch_icon()
    validate_branding()
    print(
        f"{MARKER}: marca pública actualizada a {BRAND}; archivos modificados: {changes}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
