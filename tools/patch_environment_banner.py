from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
SCRIPT = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"
MARKER = "NEXUS_ENVIRONMENT_BANNER_V1"
VERSION = "20260725-staging-banner-v1"

BANNER = (
    '<aside id="environment-banner" class="environment-banner" hidden '
    'role="status" aria-live="polite">'
    '<strong>ENTORNO DE PRUEBA · STAGING</strong>'
    '<span id="environment-release-detail">Los cambios aquí no afectan producción.</span>'
    '</aside>'
)

JAVASCRIPT = r'''

// NEXUS_ENVIRONMENT_BANNER_V1
(function nexusEnvironmentBanner() {
  async function loadEnvironmentStatus() {
    const banner = document.getElementById("environment-banner");
    if (!banner) return;
    banner.hidden = true;

    try {
      const response = await fetch("/api/release", {
        method: "GET",
        cache: "no-store",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      const release = await response.json();
      if (!release || release.isStaging !== true) return;

      const detail = document.getElementById("environment-release-detail");
      const commit = typeof release.commit === "string" && release.commit
        ? ` · ${release.commit.slice(0, 7)}`
        : "";
      if (detail) {
        detail.textContent = `Los cambios aquí no afectan producción${commit}.`;
      }
      banner.hidden = false;
      document.documentElement.setAttribute("data-nexus-environment", "staging");
    } catch (_) {
      banner.hidden = true;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => void loadEnvironmentStatus(), { once: true });
  } else {
    void loadEnvironmentStatus();
  }
})();
'''

CSS = r'''

/* NEXUS_ENVIRONMENT_BANNER_V1 */
.environment-banner{position:sticky;top:0;z-index:10000;display:flex;align-items:center;justify-content:center;gap:.75rem;flex-wrap:wrap;padding:.55rem 1rem;background:#fff3cd;color:#5c4300;border-bottom:2px solid #d99b00;text-align:center;font-size:.9rem;box-shadow:0 3px 12px rgba(61,44,0,.12)}
.environment-banner strong{letter-spacing:.05em}.environment-banner[hidden]{display:none!important}
html[data-nexus-environment="staging"] .app-shell{min-height:calc(100vh - 42px)}
@media(max-width:640px){.environment-banner{font-size:.78rem;padding:.45rem .65rem;gap:.35rem}}
'''


def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"No existe {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def cache_bust(index: str) -> str:
    for asset in ("app.js", "styles.css"):
        pattern = re.compile(
            rf'(?P<prefix>(?:src|href)=["\']/static/{re.escape(asset)})(?:\?[^"\']*)?(?P<quote>["\'])',
            flags=re.IGNORECASE,
        )
        index, count = pattern.subn(
            rf'\g<prefix>?v={VERSION}\g<quote>', index, count=1
        )
        if count != 1:
            raise RuntimeError(f"No se encontró la referencia a {asset}.")
    return index


def main() -> None:
    index = read(INDEX)
    script = read(SCRIPT)
    styles = read(STYLES)

    if 'id="environment-banner"' not in index:
        body = re.search(r'<body\b[^>]*>', index, flags=re.IGNORECASE)
        if not body:
            raise RuntimeError("index.html no contiene una etiqueta body válida.")
        index = index[: body.end()] + "\n  " + BANNER + index[body.end() :]
    index = cache_bust(index)

    if MARKER not in script:
        script = script.rstrip() + JAVASCRIPT + "\n"
    if MARKER not in styles:
        styles = styles.rstrip() + CSS + "\n"

    INDEX.write_text(index, encoding="utf-8")
    SCRIPT.write_text(script, encoding="utf-8")
    STYLES.write_text(styles, encoding="utf-8")

    final_index = read(INDEX)
    final_script = read(SCRIPT)
    final_styles = read(STYLES)
    required = {
        "index": ('id="environment-banner"', VERSION),
        "script": (MARKER, "/api/release", "isStaging"),
        "styles": (MARKER, ".environment-banner", '[hidden]'),
    }
    values = {"index": final_index, "script": final_script, "styles": final_styles}
    missing = {
        name: [item for item in markers if item not in values[name]]
        for name, markers in required.items()
    }
    missing = {name: items for name, items in missing.items() if items}
    if missing:
        raise RuntimeError(f"Identificación de entorno incompleta: {missing}")
    if "location.reload(" in final_script or "new MutationObserver" in final_script:
        raise RuntimeError("La identificación de entorno introdujo comportamiento inestable.")

    print("Banda STAGING integrada sin modificar producción ni recargar la página.", flush=True)


if __name__ == "__main__":
    main()
