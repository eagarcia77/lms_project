from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "static" / "app.js"
INDEX = ROOT / "app" / "static" / "index.html"
WORKER = ROOT / "app" / "static" / "sw.js"
VERSION = "20260725-browser-stability-v7"


def main() -> None:
    app = APP.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")

    required_app = (
        "NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND_V3",
        "scheduleStableRefresh",
        "nexusEnhanceCourseCatalog",
    )
    missing = [marker for marker in required_app if marker not in app]
    if missing:
        raise RuntimeError(f"Faltan controles de estabilidad en app.js: {missing}")

    forbidden_app = (
        "new MutationObserver",
        "location.reload(",
        "window.location.reload(",
        'addEventListener("controllerchange"',
        "addEventListener('controllerchange'",
    )
    found = [marker for marker in forbidden_app if marker in app]
    if found:
        raise RuntimeError(f"Se detectaron patrones que pueden causar refresco continuo: {found}")

    if VERSION not in index or VERSION not in worker:
        raise RuntimeError("La versión estable del navegador no está activa.")
    if "NEXUS_BROWSER_STABILITY_NETWORK_ONLY" not in worker:
        raise RuntimeError("El service worker no está en modo solo red.")
    if "event.respondWith" in worker or "caches.open" in worker:
        raise RuntimeError("El service worker todavía intercepta o almacena solicitudes.")

    print(
        "Estabilidad del navegador validada: sin observador global, sin reload y sin caché interceptora.",
        flush=True,
    )


if __name__ == "__main__":
    main()
