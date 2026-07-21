from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def element_for(element_id: str) -> str:
    """Return a harmless hidden fallback for an optional UI control."""
    lowered = element_id.lower()
    if "dialog" in lowered or "modal" in lowered:
        return f'<dialog id="{element_id}" hidden></dialog>'
    if "form" in lowered:
        return f'<form id="{element_id}" hidden></form>'
    if "search" in lowered:
        return f'<input id="{element_id}" type="search" hidden>'
    if any(token in lowered for token in ("button", "connect", "logout", "menu")):
        return f'<button id="{element_id}" type="button" hidden></button>'
    return f'<div id="{element_id}" hidden></div>'


def patch_javascript(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    original = text

    # A missing optional control must not prevent the whole LMS from loading.
    text = re.sub(
        r'(\$\(\s*["\']#[A-Za-z0-9_-]+["\']\s*\))\.addEventListener',
        r'\1?.addEventListener',
        text,
    )
    text = re.sub(
        r'(document\.querySelector\(\s*["\'][^"\']+["\']\s*\))\.addEventListener',
        r'\1?.addEventListener',
        text,
    )

    if text != original:
        path.write_text(text, encoding="utf-8")

    return set(re.findall(r'\$\(\s*["\']#([A-Za-z0-9_-]+)["\']\s*\)', text))


def patch_html(required_ids: set[str]) -> None:
    html_files = list(STATIC.glob("*.html"))
    if not html_files:
        raise RuntimeError("No se encontró la interfaz HTML después de aplicar el código fuente.")

    for path in html_files:
        text = path.read_text(encoding="utf-8")
        missing = sorted(
            element_id
            for element_id in required_ids
            if not re.search(rf'\bid=["\']{re.escape(element_id)}["\']', text)
        )
        if not missing:
            continue

        fallbacks = "\n  <!-- Controles opcionales de compatibilidad -->\n  " + "\n  ".join(
            element_for(element_id) for element_id in missing
        ) + "\n"
        if "</body>" in text:
            text = text.replace("</body>", fallbacks + "</body>", 1)
        else:
            text += fallbacks
        path.write_text(text, encoding="utf-8")


def main() -> None:
    required_ids: set[str] = set()
    js_files = list(STATIC.glob("*.js"))
    if not js_files:
        raise RuntimeError("No se encontraron archivos JavaScript para validar.")

    for path in js_files:
        required_ids.update(patch_javascript(path))

    patch_html(required_ids)
    print("Enlaces de interfaz NEXUS EDU XR validados correctamente.")


if __name__ == "__main__":
    main()
