from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
MARKER = "NUVEDRA_ACCESSIBLE_THEME_V1"

PUBLIC_FILES = (
    ROOT / "app" / "config.py",
    ROOT / "app" / "main.py",
    ROOT / "app" / "admin_portal.py",
    ROOT / "app" / "admin_console.py",
    ROOT / "app" / "admin_system.py",
    ROOT / "app" / "unified_authoring.py",
    ROOT / "app" / "innovation_hub.py",
    ROOT / "app" / "production_entry.py",
)

THEME_CSS = r'''
/* NUVEDRA_ACCESSIBLE_THEME_V1
   Paleta independiente con contrastes WCAG AA/AAA para texto principal. */
:root{
  --green:#4338CA;
  --green-dark:#2B2D6E;
  --yellow:#FFB000;
  --gold:#006B6B;
  --ink:#171A2B;
  --muted:#4B5563;
  --surface:#FFFFFF;
  --canvas:#F7F8FC;
  --line:#D7DBE8;
  --danger:#A61B1B;
  --focus:#FFB000;
  --shadow:0 18px 45px rgba(23,26,43,.12);
}
body{background:var(--canvas);color:var(--ink)}
.sidebar{background:#171A2B;color:#FFFFFF}
.brand-mark{background:#FFB000;color:#171A2B}
.brand span,.sidebar-footer{color:#D7DBE8}
.nav-item{color:#E5E7EB}
.nav-item:hover,.nav-item:focus-visible{background:#2B2D6E;color:#FFFFFF}
.nav-item.active{background:#FFFFFF;color:#2B2D6E}
.topbar{background:rgba(255,255,255,.96)}
.hero{background:radial-gradient(circle at 80% 30%,rgba(255,176,0,.22),transparent 30%),linear-gradient(135deg,#2B2D6E,#171A2B)}
.hero p{color:#F1F5F9}
.hero .eyebrow{color:#FFD166}
.button.primary{background:#4338CA;color:#FFFFFF}
.button.primary:hover{background:#2B2D6E}
.button.secondary{background:#FFFFFF;color:#2B2D6E;border:2px solid #4338CA}
.text-button,.data-row a,.course-code{color:#4338CA}
.chip{background:#EDE9FE;color:#2B2D6E;border:1px solid #C4B5FD}
.avatar{background:#4338CA;color:#FFFFFF}
.status-dot i{background:#00A6A6;box-shadow:0 0 0 5px rgba(0,166,166,.18)}
.notice.info{background:#E8F1FF;color:#173B6C;border-color:#AFCBFF}
.notice.success{background:#E7F7F4;color:#004F4F;border-color:#8ED7D0}
.notice.error{background:#FFF0F0;color:#7F1D1D;border-color:#F2B8B8}
.progress{background:#E5E7EB}
.bar-chart div{background:linear-gradient(180deg,#4338CA,#006B6B)}
.ar-button{background:#FFB000;color:#171A2B}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,[tabindex]:focus-visible{
  outline:3px solid #FFB000!important;
  outline-offset:3px!important;
  box-shadow:0 0 0 2px #171A2B!important;
}
a{text-underline-offset:.18em}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important}
}
@media (forced-colors:active){
  .button,.nav-item,.chip,.panel,.course-card{border:1px solid CanvasText}
  .button:focus-visible,.nav-item:focus-visible{outline:3px solid Highlight!important}
}
'''

ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-labelledby="title desc">
  <title id="title">NUVEDRA</title>
  <desc id="desc">Letra N geométrica que representa conexión, aprendizaje y una puerta hacia experiencias inmersivas.</desc>
  <rect width="512" height="512" rx="112" fill="#171A2B"/>
  <path d="M126 370V142h58l144 150V142h58v228h-56L184 220v150z" fill="#FFFFFF"/>
  <path d="M150 110h212" stroke="#FFB000" stroke-width="24" stroke-linecap="round"/>
  <circle cx="386" cy="126" r="32" fill="#00A6A6" stroke="#FFFFFF" stroke-width="8"/>
</svg>
'''


def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"No existe {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str) -> None:
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
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def patch_index() -> None:
    path = STATIC / "index.html"
    text = replace_public_brand(read(path))
    text = text.replace('content="#007B5F"', 'content="#2B2D6E"')
    text = text.replace('<div class="brand-mark" aria-hidden="true">NX</div>', '<div class="brand-mark" aria-hidden="true">NV</div>')
    text = text.replace(
        '<div><strong>NEXUS</strong><span>EDU XR</span></div>',
        '<div><strong>NUVEDRA</strong><span>LEARNING PLATFORM</span></div>',
    )
    text = re.sub(
        r'<div><strong>NEXUS</strong><span>[^<]*</span></div>',
        '<div><strong>NUVEDRA</strong><span>LEARNING PLATFORM</span></div>',
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    color_map = {
        "#007B5F": "#4338CA",
        "#FED141": "#FFB000",
        "#12332C": "#171A2B",
        "#EAF2F0": "#F1F5F9",
        "#D6E4E0": "#D7DBE8",
        "#F7FAF9": "#F7F8FC",
    }
    for old, new in color_map.items():
        text = text.replace(old, new)
    write(path, text)


def patch_styles() -> None:
    path = STATIC / "styles.css"
    text = read(path)
    color_map = {
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
    for old, new in color_map.items():
        text = text.replace(old, new)
    if MARKER not in text:
        text = text.rstrip() + THEME_CSS + "\n"
    write(path, text)


def patch_manifest() -> None:
    path = STATIC / "manifest.json"
    data = json.loads(read(path))
    data["name"] = "NUVEDRA"
    data["short_name"] = "NUVEDRA"
    data["description"] = "Plataforma de aprendizaje inteligente, inmersivo y conectado."
    data["background_color"] = "#F7F8FC"
    data["theme_color"] = "#2B2D6E"
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def patch_python_files() -> None:
    for path in PUBLIC_FILES:
        if not path.is_file():
            continue
        text = replace_public_brand(read(path))
        if path.name == "config.py":
            text = text.replace('os.getenv("APP_NAME", "NEXUS")', 'os.getenv("APP_NAME", "NUVEDRA")')
        if path.name == "admin_portal.py":
            old = ':root{--navy:#09283d;--green:#007b5f;--gold:#fed141;--blue:#185adb;--ink:#172033;--muted:#586b7d;--soft:#f3f7f8;--line:#cbd7df;--white:#fff;--danger:#a61b1b;--focus:#ffbf47}'
            new = ':root{--navy:#171A2B;--green:#4338CA;--gold:#FFB000;--blue:#4338CA;--ink:#171A2B;--muted:#4B5563;--soft:#F7F8FC;--line:#D7DBE8;--white:#fff;--danger:#A61B1B;--focus:#FFB000}'
            text = text.replace(old, new)
            text = text.replace(
                '@media(max-width:920px){',
                '@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}'
                '@media(forced-colors:active){button,.button,.card,.portal-link{border:1px solid CanvasText}}'
                '@media(max-width:920px){',
                1,
            )
        write(path, text)


def validate() -> None:
    index = read(STATIC / "index.html")
    styles = read(STATIC / "styles.css")
    manifest = read(STATIC / "manifest.json")
    icon = read(STATIC / "assets" / "icon.svg")
    admin = read(ROOT / "app" / "admin_portal.py")
    config = read(ROOT / "app" / "config.py")

    required = {
        "index": ("NUVEDRA", "LEARNING PLATFORM"),
        "styles": (MARKER, "#4338CA", "#2B2D6E", "#FFB000", "prefers-reduced-motion", "forced-colors"),
        "manifest": ('"name": "NUVEDRA"', '"theme_color": "#2B2D6E"'),
        "icon": ("NUVEDRA", "#171A2B", "#FFB000"),
        "admin": ("NUVEDRA", "--green:#4338CA", "--focus:#FFB000"),
        "config": ('os.getenv("APP_NAME", "NUVEDRA")',),
    }
    values = {
        "index": index,
        "styles": styles,
        "manifest": manifest,
        "icon": icon,
        "admin": admin,
        "config": config,
    }
    missing = {
        name: [item for item in items if item not in values[name]]
        for name, items in required.items()
    }
    missing = {name: items for name, items in missing.items() if items}
    if missing:
        raise RuntimeError(f"Cambio de identidad incompleto: {missing}")

    for label, text in (("portada", index), ("manifiesto", manifest), ("administración", admin)):
        if "NEXUS EDU XR" in text:
            raise RuntimeError(f"{label} todavía muestra la marca anterior.")

    old_colors = ("#007B5F", "#FED141", "#85714D")
    for label, text in (("portada", index), ("estilos", styles), ("administración", admin)):
        remaining = [color for color in old_colors if color.lower() in text.lower()]
        if remaining:
            raise RuntimeError(f"{label} conserva colores institucionales anteriores: {remaining}")


def main() -> None:
    patch_index()
    patch_styles()
    patch_manifest()
    write(STATIC / "assets" / "icon.svg", ICON_SVG)
    patch_python_files()
    validate()
    print("NUVEDRA aplicada con identidad visual independiente y accesible.", flush=True)


if __name__ == "__main__":
    main()
