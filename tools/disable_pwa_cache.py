from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "app.js"
SW_JS = ROOT / "app" / "static" / "sw.js"
MARKER = "NEXUS_PWA_DISABLED_FOR_STABILITY"

APP_CLEANUP = r'''

// NEXUS_PWA_DISABLED_FOR_STABILITY
(function nexusDisablePwaCache() {
  async function cleanup() {
    if ("serviceWorker" in navigator) {
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map(registration => registration.unregister()));
      } catch (_) {
        // La plataforma continúa aun cuando el navegador bloquee esta operación.
      }
    }

    if ("caches" in window) {
      try {
        const keys = await caches.keys();
        await Promise.all(
          keys
            .filter(key => key.startsWith("nexus-edu-xr-"))
            .map(key => caches.delete(key))
        );
      } catch (_) {
        // La ausencia de Cache Storage no impide iniciar la plataforma.
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => void cleanup(), { once: true });
  } else {
    void cleanup();
  }
})();
'''

SELF_DESTRUCT_WORKER = r'''// NEXUS_PWA_DISABLED_FOR_STABILITY
self.addEventListener("install", event => {
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith("nexus-edu-xr-"))
          .map(key => caches.delete(key))
      ))
      .then(() => self.registration.unregister())
      .catch(() => undefined)
  );
});
'''


def remove_service_worker_registration(source: str) -> str:
    """Remove common service-worker registration forms without relying on layout."""
    patterns = (
        r'(?ms)^\s*if\s*\(\s*["\']serviceWorker["\']\s+in\s+navigator\s*\)\s*'
        r'navigator\.serviceWorker\.register\s*\(.*?\)\s*\.catch\s*\(.*?\)\s*;?\s*$',
        r'(?ms)^\s*navigator\.serviceWorker\.register\s*\(.*?\)\s*'
        r'(?:\.then\s*\(.*?\)\s*)?(?:\.catch\s*\(.*?\)\s*)?;?\s*$',
    )
    revised = source
    for pattern in patterns:
        revised = re.sub(pattern, "", revised)
    return revised


def patch_app_js(source: str) -> str:
    source = remove_service_worker_registration(source)
    if MARKER not in source:
        source = source.rstrip() + APP_CLEANUP + "\n"
    return source


def main() -> None:
    if not APP_JS.is_file():
        raise RuntimeError("No existe app/static/app.js después de aplicar la base V3.")

    app_source = APP_JS.read_text(encoding="utf-8")
    revised = patch_app_js(app_source)
    APP_JS.write_text(revised, encoding="utf-8")
    SW_JS.write_text(SELF_DESTRUCT_WORKER, encoding="utf-8")

    final_app = APP_JS.read_text(encoding="utf-8")
    final_sw = SW_JS.read_text(encoding="utf-8")
    if MARKER not in final_app or MARKER not in final_sw:
        raise RuntimeError("No se completó la desactivación de la caché PWA.")
    if re.search(r'navigator\.serviceWorker\.register\s*\(', final_app):
        raise RuntimeError("app.js todavía registra un service worker.")
    if "self.registration.unregister()" not in final_sw:
        raise RuntimeError("El service worker no quedó configurado para retirarse.")
    if "client.navigate" in final_sw:
        raise RuntimeError("El service worker todavía intenta recargar una ventana.")

    print(
        "PWA desactivada de forma independiente: registro eliminado, cachés limpiadas "
        "y service worker retirado sin recargar la página.",
        flush=True,
    )


if __name__ == "__main__":
    main()
