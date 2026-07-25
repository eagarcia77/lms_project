from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "app.js"
SW_JS = ROOT / "app" / "static" / "sw.js"
MARKER = "NEXUS_PWA_DISABLED_FOR_STABILITY"

APP_CLEANUP = r'''
    // NEXUS_PWA_DISABLED_FOR_STABILITY
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.getRegistrations()
        .then(registrations => Promise.all(registrations.map(registration => registration.unregister())))
        .catch(() => undefined);
    }
    if ("caches" in window) {
      caches.keys()
        .then(keys => Promise.all(keys.filter(key => key.startsWith("nexus-edu-xr-")).map(key => caches.delete(key))))
        .catch(() => undefined);
    }
'''

SELF_DESTRUCT_WORKER = r'''// NEXUS_PWA_DISABLED_FOR_STABILITY
self.addEventListener("install", event => {
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith("nexus-edu-xr-")).map(key => caches.delete(key))))
      .then(() => self.registration.unregister())
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(fetch(event.request));
});
'''


def patch_app_js(source: str) -> str:
    if MARKER in source:
        return source

    patterns = (
        r'\s*if \("serviceWorker" in navigator\) navigator\.serviceWorker\.register\("/static/sw\.js"\)\.catch\(\(\) => \{\}\);',
        r'\s*if \(["\']serviceWorker["\'] in navigator\) navigator\.serviceWorker\.register\(["\']/static/sw\.js["\']\)\.catch\([^;]+;',
    )
    for pattern in patterns:
        revised, count = re.subn(pattern, "\n" + APP_CLEANUP.rstrip(), source, count=1)
        if count:
            return revised

    anchor = '    if (new URLSearchParams(location.search).get("google") === "connected") {'
    if anchor not in source:
        raise RuntimeError("No se encontró un punto seguro para desactivar el service worker.")
    return source.replace(anchor, APP_CLEANUP + "\n" + anchor, 1)


def main() -> None:
    app_source = APP_JS.read_text(encoding="utf-8")
    revised = patch_app_js(app_source)
    APP_JS.write_text(revised, encoding="utf-8")
    SW_JS.write_text(SELF_DESTRUCT_WORKER, encoding="utf-8")

    final_app = APP_JS.read_text(encoding="utf-8")
    final_sw = SW_JS.read_text(encoding="utf-8")
    if MARKER not in final_app or MARKER not in final_sw:
        raise RuntimeError("No se completó la desactivación de la caché PWA.")
    if 'register("/static/sw.js")' in final_app or "new MutationObserver" in final_app:
        raise RuntimeError("La portada conserva una integración inestable del navegador.")
    if "self.registration.unregister()" not in final_sw:
        raise RuntimeError("El service worker no quedó configurado para retirarse.")

    print("PWA desactivada para estabilidad: cachés eliminadas y service worker retirado.", flush=True)


if __name__ == "__main__":
    main()
