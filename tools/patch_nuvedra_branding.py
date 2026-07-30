from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
ASSETS = STATIC / "assets"
MARKER = "NUVEDRA_ACCESSIBLE_THEME_V1"

PUBLIC_FILES = (
    ROOT / "app" / "config.py",
    ROOT / "app" / "main.py",
    ROOT / "app" / "db.py",
    ROOT / "app" / "admin_portal.py",
    ROOT / "app" / "admin_console.py",
    ROOT / "app" / "admin_system.py",
    ROOT / "app" / "unified_authoring.py",
    ROOT / "app" / "innovation_hub.py",
    ROOT / "app" / "production_entry.py",
)

ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-labelledby="title desc">
  <title id="title">NUVEDRA</title>
  <desc id="desc">Letra N geométrica que representa conexión, aprendizaje y experiencias inmersivas.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#090B2B"/><stop offset="1" stop-color="#2B2D6E"/></linearGradient>
    <linearGradient id="n" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7C3AED"/><stop offset=".5" stop-color="#4338CA"/><stop offset="1" stop-color="#00B8C8"/></linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#bg)"/>
  <path d="M116 374V138h70l140 145V138h70v236h-66L186 228v146z" fill="none" stroke="url(#n)" stroke-width="42" stroke-linejoin="round"/>
  <circle cx="256" cy="256" r="16" fill="#FFB000"/>
</svg>
'''


def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"No existe {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_public_brand(text: str) -> str:
    replacements = (
        ("NEXUS EDU XR", "NUVEDRA"),
        ("NEXUS XR", "NUVEDRA"),
        ("NEXUS Unified Authoring Router", "NUVEDRA Unified Authoring Router"),
        ("Administrador NEXUS", "Administrador NUVEDRA"),
        ("· NEXUS", "· NUVEDRA"),
        ("portal Administrador de NEXUS", "portal Administrador de NUVEDRA"),
        ("administración de NEXUS", "administración de NUVEDRA"),
        ("Utilice la cuenta administrativa protegida de NEXUS.", "Utilice su cuenta administrativa protegida de NUVEDRA."),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def patch_index() -> None:
    path = STATIC / "index.html"
    text = replace_public_brand(read(path))
    text = text.replace('content="#007B5F"', 'content="#2B2D6E"')
    text = text.replace("#007B5F", "#4338CA").replace("#FED141", "#FFB000").replace("#85714D", "#006B6B")
    write(path, text)


def patch_styles() -> None:
    path = STATIC / "styles.css"
    text = read(path)
    replacements = {
        "#007B5F": "#4338CA",
        "#007b5f": "#4338CA",
        "#075947": "#2B2D6E",
        "#FED141": "#FFB000",
        "#fed141": "#FFB000",
        "#85714D": "#006B6B",
        "#0B3329": "#171A2B",
        "#0b3329": "#171A2B",
        "#0A4D3E": "#2B2D6E",
        "#073127": "#171A2B",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    if MARKER not in text:
        text = f"/* {MARKER} */\n" + text
    if "prefers-reduced-motion" not in text:
        text += "\n@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important}}\n"
    if "forced-colors" not in text:
        text += "\n@media(forced-colors:active){button,.button,.nav-item,.panel{border:1px solid CanvasText}}\n"
    write(path, text)


def patch_app_js() -> None:
    path = STATIC / "app.js"
    text = replace_public_brand(read(path))
    if "NEXUS_PWA_DISABLED_FOR_STABILITY" not in text:
        text = "/* NEXUS_PWA_DISABLED_FOR_STABILITY */\n" + text
    text = text.replace('navigator.serviceWorker.register("/static/sw.js").catch(() => {});', 'navigator.serviceWorker.getRegistrations().then(items => items.forEach(item => item.unregister())).catch(() => {});')
    write(path, text)


def patch_manifest() -> None:
    path = STATIC / "manifest.json"
    data = json.loads(read(path)) if path.is_file() else {}
    data.update(
        {
            "name": "NUVEDRA",
            "short_name": "NUVEDRA",
            "description": "Plataforma de aprendizaje inteligente, inmersivo y conectado.",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#F7F8FC",
            "theme_color": "#2B2D6E",
        }
    )
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def ensure_home_content_navigation(text: str) -> str:
    if '"/admin/home-content"' in text:
        return text

    role_aware = "def _navigation(role:" in text
    insertion = (
        '("/admin/home-content", "Portada y anuncios", "Banners, avisos y programación", {"superadmin", "course_admin"}),' 
        if role_aware
        else '("/admin/home-content", "Portada y anuncios", "Banners, avisos y programación"),'
    )
    markers = (
        '("/admin", "Panel general", "Inicio y operaciones", all_roles),',
        '("/admin", "Panel general", "Inicio y operaciones"),',
    )
    for marker in markers:
        if marker in text:
            text = text.replace(marker, f"{marker}\n        {insertion}", 1)
            break

    if '"/admin/home-content"' not in text:
        pattern = re.compile(
            r'(?P<line>\(\s*["\']/admin["\']\s*,\s*["\']Panel general["\']\s*,\s*["\']Inicio y operaciones["\'](?:\s*,\s*all_roles)?\s*\),)'
        )
        text, count = pattern.subn(lambda match: f"{match.group('line')}\n        {insertion}", text, count=1)
        if count == 0:
            raise RuntimeError("No se encontró el punto de inserción para Portada y anuncios.")

    if '"/admin/home-content"' not in text:
        raise RuntimeError("No se pudo incorporar Portada y anuncios a la navegación administrativa.")
    return text


def patch_python_files() -> None:
    for path in PUBLIC_FILES:
        if not path.is_file():
            continue
        text = replace_public_brand(read(path))
        if path.name == "config.py":
            text = text.replace('os.getenv("APP_NAME", "NEXUS")', 'os.getenv("APP_NAME", "NUVEDRA")')
        if path.name == "admin_portal.py":
            text = ensure_home_content_navigation(text)
            text = text.replace(
                ':root{--navy:#09283d;--green:#007b5f;--gold:#fed141;--blue:#185adb;--ink:#172033;--muted:#586b7d;--soft:#f3f7f8;--line:#cbd7df;--white:#fff;--danger:#a61b1b;--focus:#ffbf47}',
                ':root{--navy:#171A2B;--green:#4338CA;--gold:#FFB000;--blue:#4338CA;--ink:#171A2B;--muted:#4B5563;--soft:#F7F8FC;--line:#D7DBE8;--white:#fff;--danger:#A61B1B;--focus:#FFB000}',
            )
            text = text.replace("linear-gradient(180deg,var(--navy),#0c3d4b 58%,var(--green))", "linear-gradient(180deg,#090B2B,#171A4A 58%,#2B2D6E)")
            if "prefers-reduced-motion" not in text:
                text = text.replace(
                    "@media(max-width:920px){",
                    "@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}"
                    "@media(forced-colors:active){button,.button,.card,.portal-link{border:1px solid CanvasText}}"
                    "@media(max-width:920px){",
                    1,
                )
        write(path, text)


def validate() -> None:
    index = read(STATIC / "index.html")
    styles = read(STATIC / "styles.css")
    app_js = read(STATIC / "app.js")
    manifest = read(STATIC / "manifest.json")
    icon = read(ASSETS / "icon.svg")
    admin = read(ROOT / "app" / "admin_portal.py")
    config = read(ROOT / "app" / "config.py")

    required = {
        "index": ("NUVEDRA", "#2B2D6E", "/admin/home-content", "hero-carousel", "announcement-cards"),
        "styles": (MARKER, ":focus-visible", "prefers-reduced-motion", "forced-colors"),
        "app_js": ("/api/home-content", "NEXUS_PWA_DISABLED_FOR_STABILITY", "renderHomeContent"),
        "manifest": ('"name": "NUVEDRA"', '"theme_color": "#2B2D6E"'),
        "icon": ("NUVEDRA", "<title", "<desc"),
        "admin": ("NUVEDRA", "--green:#4338CA", "--focus:#FFB000", '"/admin/home-content"'),
        "config": ('os.getenv("APP_NAME", "NUVEDRA")',),
    }
    values = {"index": index, "styles": styles, "app_js": app_js, "manifest": manifest, "icon": icon, "admin": admin, "config": config}
    missing = {name: [item for item in items if item not in values[name]] for name, items in required.items()}
    missing = {name: items for name, items in missing.items() if items}
    if missing:
        raise RuntimeError(f"Actualización de NUVEDRA incompleta: {missing}")

    for label, text in (("portada", index), ("manifiesto", manifest), ("administración", admin)):
        if "NEXUS EDU XR" in text:
            raise RuntimeError(f"{label} todavía muestra la marca anterior.")
    for old in ("#007B5F", "#FED141", "#85714D"):
        for label, text in (("portada", index), ("estilos", styles), ("administración", admin)):
            if old.lower() in text.lower():
                raise RuntimeError(f"{label} conserva el color anterior {old}.")
    if 'register("/static/sw.js")' in app_js:
        raise RuntimeError("La portada volvió a registrar el service worker anterior.")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    patch_index()
    patch_styles()
    patch_app_js()
    patch_manifest()
    write(ASSETS / "icon.svg", ICON_SVG)
    patch_python_files()
    validate()
    print("Portada HTML de NUVEDRA y gestor de anuncios aplicados correctamente.", flush=True)


if __name__ == "__main__":
    main()
