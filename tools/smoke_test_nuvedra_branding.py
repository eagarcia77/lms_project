from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def require(text: str, markers: tuple[str, ...], label: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise RuntimeError(f"{label} no contiene {missing}")


def main() -> None:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    manifest_text = (STATIC / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    icon = (STATIC / "assets" / "icon.svg").read_text(encoding="utf-8")
    admin = (ROOT / "app" / "admin_portal.py").read_text(encoding="utf-8")
    config = (ROOT / "app" / "config.py").read_text(encoding="utf-8")

    require(index, ("NUVEDRA", "LEARNING PLATFORM", 'content="#2B2D6E"'), "portada")
    require(styles, ("NUVEDRA_ACCESSIBLE_THEME_V1", ":focus-visible", "prefers-reduced-motion", "forced-colors"), "estilos")
    require(admin, ("NUVEDRA", "--green:#4338CA", "--focus:#FFB000"), "administración")
    require(config, ('os.getenv("APP_NAME", "NUVEDRA")',), "configuración")
    require(icon, ("NUVEDRA", "<title", "<desc"), "icono")

    if manifest.get("name") != "NUVEDRA" or manifest.get("short_name") != "NUVEDRA":
        raise RuntimeError(f"El manifiesto tiene una marca incorrecta: {manifest!r}")
    if manifest.get("theme_color") != "#2B2D6E" or manifest.get("background_color") != "#F7F8FC":
        raise RuntimeError(f"El manifiesto tiene colores incorrectos: {manifest!r}")

    for label, text in (("portada", index), ("manifiesto", manifest_text), ("administración", admin)):
        if "NEXUS EDU XR" in text:
            raise RuntimeError(f"{label} conserva la marca anterior.")

    for old in ("#007B5F", "#FED141", "#85714D"):
        for label, text in (("portada", index), ("estilos", styles), ("administración", admin)):
            if old.lower() in text.lower():
                raise RuntimeError(f"{label} conserva el color institucional {old}.")

    pairs = {
        "blanco sobre violeta": ("#FFFFFF", "#4338CA", 4.5),
        "blanco sobre índigo": ("#FFFFFF", "#2B2D6E", 4.5),
        "blanco sobre turquesa oscuro": ("#FFFFFF", "#006B6B", 4.5),
        "texto oscuro sobre ámbar": ("#171A2B", "#FFB000", 4.5),
        "texto principal sobre fondo": ("#171A2B", "#F7F8FC", 7.0),
        "texto secundario sobre blanco": ("#4B5563", "#FFFFFF", 4.5),
    }
    results = {}
    for label, (foreground, background, minimum) in pairs.items():
        ratio = contrast(foreground, background)
        results[label] = round(ratio, 2)
        if ratio < minimum:
            raise RuntimeError(
                f"Contraste insuficiente para {label}: {ratio:.2f}:1, mínimo {minimum}:1"
            )

    print(
        "NUVEDRA validada: marca actualizada, colores institucionales retirados, "
        f"foco visible, movimiento reducido y contrastes {results}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
