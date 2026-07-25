from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
WORKER = ROOT / "app" / "static" / "sw.js"
VERSION = "20260725-browser-stability-v7"

WORKER_CONTENT = f'''// NEXUS_BROWSER_STABILITY_NETWORK_ONLY
const VERSION = "{VERSION}";

self.addEventListener("install", event => {{
  self.skipWaiting();
}});

self.addEventListener("activate", event => {{
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key.startsWith("nexus-edu-xr-")).map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
}});

// No se interceptan solicitudes. La portada, la API y los archivos estáticos
// se obtienen directamente de Render para evitar ciclos causados por caché vieja.
'''


def update_index(source: str) -> str:
    for asset in ("app.js", "styles.css"):
        pattern = re.compile(
            rf'(?P<prefix>(?:src|href)=["\']/static/{re.escape(asset)})(?:\?[^"\']*)?(?P<quote>["\'])',
            flags=re.IGNORECASE,
        )
        source, count = pattern.subn(
            rf'\g<prefix>?v={VERSION}\g<quote>',
            source,
            count=1,
        )
        if count != 1:
            raise RuntimeError(f"No se encontró la referencia a {asset} en index.html.")
    return source


def main() -> None:
    index = INDEX.read_text(encoding="utf-8")
    revised = update_index(index)
    INDEX.write_text(revised, encoding="utf-8")
    WORKER.write_text(WORKER_CONTENT, encoding="utf-8")

    final_index = INDEX.read_text(encoding="utf-8")
    final_worker = WORKER.read_text(encoding="utf-8")
    if VERSION not in final_index or VERSION not in final_worker:
        raise RuntimeError("La versión estable del navegador no quedó aplicada.")
    if "event.respondWith" in final_worker or "caches.open" in final_worker:
        raise RuntimeError("El service worker todavía intercepta o almacena solicitudes.")

    print(
        "Navegador estabilizado: cachés antiguas eliminadas y service worker en modo solo red.",
        flush=True,
    )


if __name__ == "__main__":
    main()
