from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
SCRIPT = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"
VERSION = "20260725-admin-restored-v1"
MARKER = "NEXUS_ADMIN_HOME_ACCESS_V1"

TOP_LINK = (
    '<a id="admin-access-top" class="admin-access-button" data-admin-access '
    'href="/admin" hidden aria-label="Abrir la administración de NEXUS">'
    '⚙ Administrador</a>'
)

NAV_LINK = (
    '<a id="admin-access-nav" class="nav-item admin-nav-link" data-admin-access '
    'href="/admin" hidden><span aria-hidden="true">⚙</span> Administración</a>'
)

ADMIN_JS = r'''

// NEXUS_ADMIN_HOME_ACCESS_V1
(function nexusAdministratorAccess() {
  const links = () => [...document.querySelectorAll("[data-admin-access]")];

  function hideAdministratorAccess() {
    links().forEach(link => {
      link.hidden = true;
      link.removeAttribute("data-authorized");
    });
  }

  async function refreshAdministratorAccess() {
    hideAdministratorAccess();
    try {
      const response = await fetch("/api/admin/access", {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      const access = await response.json();
      if (!access || access.allowed !== true) return;

      links().forEach(link => {
        link.href = access.href || "/admin";
        link.hidden = false;
        link.setAttribute("data-authorized", "true");
        link.title = access.requiresAdminLogin
          ? "Cuenta administrativa reconocida. Inicie la sesión administrativa para continuar."
          : "Abrir el portal Administrador de NEXUS.";
      });
    } catch (_) {
      hideAdministratorAccess();
    }
  }

  function initializeAdministratorAccess() {
    void refreshAdministratorAccess();
    window.addEventListener("pageshow", () => void refreshAdministratorAccess());
    window.addEventListener("focus", () => void refreshAdministratorAccess());
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") void refreshAdministratorAccess();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeAdministratorAccess, { once: true });
  } else {
    initializeAdministratorAccess();
  }

  window.nexusRefreshAdministratorAccess = refreshAdministratorAccess;
})();
'''

ADMIN_CSS = r'''

/* NEXUS_ADMIN_HOME_ACCESS_V1 */
.admin-access-button{display:inline-flex;align-items:center;justify-content:center;gap:.45rem;padding:.68rem .9rem;border:1px solid #00664f;border-radius:12px;background:#007b5f;color:#fff;text-decoration:none;font-weight:800;white-space:nowrap;box-shadow:0 6px 16px rgba(0,75,59,.18)}
.admin-access-button:hover,.admin-access-button:focus-visible{background:#005f49;color:#fff;transform:translateY(-1px)}
.admin-access-button[hidden],.admin-nav-link[hidden]{display:none!important}
.admin-nav-link{width:100%;text-decoration:none}
@media(max-width:760px){.admin-access-button{width:44px;height:44px;padding:0;font-size:0}.admin-access-button::first-letter{font-size:1.1rem}}
'''


def require(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"No existe {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def cache_bust(source: str) -> str:
    for asset in ("app.js", "styles.css"):
        pattern = re.compile(
            rf'(?P<prefix>(?:src|href)=["\']/static/{re.escape(asset)})(?:\?[^"\']*)?(?P<quote>["\'])',
            flags=re.IGNORECASE,
        )
        source, count = pattern.subn(
            rf'\g<prefix>?v={VERSION}\g<quote>', source, count=1
        )
        if count != 1:
            raise RuntimeError(f"No se encontró la referencia a {asset} en index.html.")
    return source


def patch_index(source: str) -> str:
    if 'id="admin-access-top"' not in source:
        match = re.search(
            r'(<div\b[^>]*class=["\'][^"\']*\btop-actions\b[^"\']*["\'][^>]*>)',
            source,
            flags=re.IGNORECASE,
        )
        if not match:
            raise RuntimeError("No se encontró top-actions para incorporar Administrador.")
        source = source[: match.end()] + "\n          " + TOP_LINK + source[match.end() :]

    if 'id="admin-access-nav"' not in source:
        match = re.search(
            r'(<nav\b[^>]*id=["\']primary-nav["\'][^>]*>.*?)(</nav\s*>)',
            source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise RuntimeError("No se encontró primary-nav para incorporar Administración.")
        replacement = match.group(1) + "\n        " + NAV_LINK + "\n      " + match.group(2)
        source = source[: match.start()] + replacement + source[match.end() :]

    return cache_bust(source)


def main() -> None:
    index = patch_index(require(INDEX))
    script = require(SCRIPT)
    styles = require(STYLES)

    if MARKER not in script:
        script = script.rstrip() + ADMIN_JS + "\n"
    if MARKER not in styles:
        styles = styles.rstrip() + ADMIN_CSS + "\n"

    INDEX.write_text(index, encoding="utf-8")
    SCRIPT.write_text(script, encoding="utf-8")
    STYLES.write_text(styles, encoding="utf-8")

    final_index = require(INDEX)
    final_script = require(SCRIPT)
    final_styles = require(STYLES)
    checks = {
        "index.html": ('id="admin-access-top"', 'id="admin-access-nav"', VERSION),
        "app.js": (MARKER, "/api/admin/access", "nexusRefreshAdministratorAccess"),
        "styles.css": (MARKER, ".admin-access-button", ".admin-nav-link"),
    }
    content = {
        "index.html": final_index,
        "app.js": final_script,
        "styles.css": final_styles,
    }
    missing = {
        name: [item for item in required if item not in content[name]]
        for name, required in checks.items()
    }
    missing = {name: items for name, items in missing.items() if items}
    if missing:
        raise RuntimeError(f"Integración Administrador incompleta: {missing}")
    if "new MutationObserver" in final_script or "location.reload(" in final_script:
        raise RuntimeError("La integración Administrador introdujo comportamiento inestable.")

    print("Parte Administrador restaurada en la portada sin modificar la PWA.", flush=True)


if __name__ == "__main__":
    main()
