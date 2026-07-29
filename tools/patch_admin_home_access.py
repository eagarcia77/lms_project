from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
SCRIPT = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"
VERSION = "20260729-admin-restored-v2"
MARKER = "NEXUS_ADMIN_HOME_ACCESS_V1"

TOP_LINK = (
    '<a id="admin-access-top" class="admin-access-button" data-admin-access '
    'href="/admin" hidden aria-label="Abrir la administración de la plataforma">'
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
          : "Abrir el portal Administrador.";
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
.admin-access-fallback{position:fixed;right:1rem;bottom:1rem;z-index:1000;display:flex;flex-direction:column;align-items:flex-end;gap:.5rem}
.admin-access-fallback .admin-nav-link{display:inline-flex;width:auto;padding:.62rem .85rem;border-radius:12px;background:#09283d;color:#fff;font-weight:800;box-shadow:0 6px 16px rgba(9,40,61,.2)}
@media(max-width:760px){.admin-access-button{width:44px;height:44px;padding:0;font-size:0}.admin-access-button::first-letter{font-size:1.1rem}.admin-access-fallback{right:.75rem;bottom:.75rem}}
'''


def require(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"No existe {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def cache_bust(source: str) -> str:
    """Update asset versions when references exist; never fail on layout changes."""
    for asset in ("app.js", "styles.css"):
        pattern = re.compile(
            rf'(?P<prefix>(?:src|href)=["\']/static/{re.escape(asset)})(?:\?[^"\']*)?(?P<quote>["\'])',
            flags=re.IGNORECASE,
        )
        source, _ = pattern.subn(
            rf'\g<prefix>?v={VERSION}\g<quote>', source, count=1
        )
    return source


def _after_opening_tag(source: str, tag: str, fragment: str) -> tuple[str, bool]:
    match = re.search(rf'<{tag}\b[^>]*>', source, flags=re.IGNORECASE)
    if not match:
        return source, False
    return source[: match.end()] + "\n" + fragment + source[match.end() :], True


def _insert_top_link(source: str) -> tuple[str, bool]:
    selectors = (
        r'(<div\b[^>]*class=["\'][^"\']*\btop-actions\b[^"\']*["\'][^>]*>)',
        r'(<div\b[^>]*class=["\'][^"\']*\bheader-actions\b[^"\']*["\'][^>]*>)',
        r'(<header\b[^>]*>)',
    )
    for pattern in selectors:
        match = re.search(pattern, source, flags=re.IGNORECASE)
        if match:
            return source[: match.end()] + "\n" + TOP_LINK + source[match.end() :], True
    return source, False


def _insert_nav_link(source: str) -> tuple[str, bool]:
    nav_patterns = (
        r'(<nav\b[^>]*id=["\']primary-nav["\'][^>]*>.*?)(</nav\s*>)',
        r'(<nav\b[^>]*>.*?)(</nav\s*>)',
        r'(<aside\b[^>]*>.*?)(</aside\s*>)',
    )
    for pattern in nav_patterns:
        match = re.search(pattern, source, flags=re.IGNORECASE | re.DOTALL)
        if match:
            replacement = match.group(1) + "\n" + NAV_LINK + "\n" + match.group(2)
            return source[: match.start()] + replacement + source[match.end() :], True
    return source, False


def _insert_fallback(source: str, include_top: bool, include_nav: bool) -> str:
    fragments: list[str] = []
    if include_top:
        fragments.append(TOP_LINK)
    if include_nav:
        fragments.append(NAV_LINK)
    if not fragments:
        return source

    container = (
        '<div class="admin-access-fallback" aria-label="Accesos administrativos">\n'
        + "\n".join(fragments)
        + "\n</div>"
    )
    revised, inserted = _after_opening_tag(source, "body", container)
    if inserted:
        return revised

    # Last-resort valid HTML shell for malformed or fragment-only base files.
    return container + "\n" + source


def patch_index(source: str) -> str:
    need_top = 'id="admin-access-top"' not in source
    need_nav = 'id="admin-access-nav"' not in source

    if need_top:
        source, inserted = _insert_top_link(source)
        need_top = not inserted

    if need_nav:
        source, inserted = _insert_nav_link(source)
        need_nav = not inserted

    source = _insert_fallback(source, include_top=need_top, include_nav=need_nav)
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
        "index.html": ('id="admin-access-top"', 'id="admin-access-nav"'),
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

    print(
        "Parte Administrador restaurada con integración adaptable al diseño V3.",
        flush=True,
    )


if __name__ == "__main__":
    main()
