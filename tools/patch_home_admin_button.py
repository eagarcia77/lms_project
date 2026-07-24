from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
SCRIPT = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"

ADMIN_LINK = (
    '<a id="admin-access" class="admin-access-button" href="/admin" hidden '
    'aria-label="Abrir administración de NEXUS">⚙ Administración</a>'
)

ADMIN_FUNCTION = r'''

// NEXUS_ADMIN_ACCESS_BEGIN
async function updateAdminAccess() {
  const adminLink = document.getElementById("admin-access");
  if (!adminLink) return;

  adminLink.hidden = true;
  adminLink.removeAttribute("data-authorized");

  try {
    const response = await fetch("/api/admin/access", {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;

    const access = await response.json();
    if (!access || access.allowed !== true) return;

    adminLink.href = access.href || "/admin";
    adminLink.hidden = false;
    adminLink.setAttribute("data-authorized", "true");

    const role = access.role ? ` · ${access.role}` : "";
    adminLink.title = access.requiresAdminLogin
      ? `Cuenta administrativa reconocida${role}. Inicie la sesión administrativa para continuar.`
      : `Abrir el panel administrativo${role}.`;
  } catch (_) {
    adminLink.hidden = true;
    adminLink.removeAttribute("data-authorized");
  }
}

function initializeAdminAccess() {
  void updateAdminAccess();
  window.addEventListener("pageshow", () => void updateAdminAccess());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void updateAdminAccess();
  });
  document.addEventListener("click", event => {
    const target = event.target instanceof Element ? event.target.closest("#connect-google, [data-auth-action]") : null;
    if (target) {
      window.setTimeout(() => void updateAdminAccess(), 400);
      window.setTimeout(() => void updateAdminAccess(), 1400);
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeAdminAccess, { once: true });
} else {
  initializeAdminAccess();
}
// NEXUS_ADMIN_ACCESS_END
'''

ADMIN_CSS = r'''

.admin-access-button{display:inline-flex;align-items:center;justify-content:center;gap:7px;background:#0B4E3F;color:#fff;text-decoration:none;border:1px solid #0B4E3F;border-radius:13px;padding:10px 14px;font-weight:800;white-space:nowrap;box-shadow:0 7px 18px rgba(11,78,63,.14);z-index:30}.admin-access-button:hover,.admin-access-button:focus-visible{background:#073B30;color:#fff;transform:translateY(-1px)}.admin-access-button[hidden]{display:none!important}.admin-access-fallback{position:fixed;top:14px;right:76px;z-index:9999;display:flex;align-items:center}@media(max-width:760px){.admin-access-button{padding:10px;width:44px;height:44px;font-size:0}.admin-access-button::first-letter{font-size:18px}.admin-access-fallback{top:10px;right:62px}}
'''


def _require_file(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"No existe el archivo requerido: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def patch_index() -> int:
    source = _require_file(INDEX)
    if 'id="admin-access"' in source:
        return 0

    changed = False

    # Preferred location: inside the existing top action area, regardless of
    # indentation, attributes or the first control rendered there.
    top_actions = re.search(
        r'(<(?:div|nav)\b[^>]*class=["\'][^"\']*\btop-actions\b[^"\']*["\'][^>]*>)',
        source,
        flags=re.IGNORECASE,
    )
    if top_actions:
        position = top_actions.end()
        source = source[:position] + "\n          " + ADMIN_LINK + source[position:]
        changed = True

    # Secondary location: immediately before the closing topbar/header tag.
    if not changed:
        topbar = re.search(
            r'(<header\b[^>]*class=["\'][^"\']*\btopbar\b[^"\']*["\'][^>]*>.*?</header\s*>)',
            source,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if topbar:
            block = topbar.group(1)
            revised = re.sub(
                r'</header\s*>',
                "  " + ADMIN_LINK + "\n</header>",
                block,
                count=1,
                flags=re.IGNORECASE,
            )
            source = source[: topbar.start()] + revised + source[topbar.end() :]
            changed = True

    # Generic header fallback. This keeps the patch compatible with future
    # revisions of the public page that no longer use the current CSS classes.
    if not changed:
        closing_header = re.search(r'</header\s*>', source, flags=re.IGNORECASE)
        if closing_header:
            position = closing_header.start()
            source = source[:position] + "  " + ADMIN_LINK + "\n" + source[position:]
            changed = True

    # Last-resort safe fallback: a fixed-position container. The deployment
    # must not fail merely because the visual structure of the homepage changed.
    if not changed:
        closing_body = re.search(r'</body\s*>', source, flags=re.IGNORECASE)
        if not closing_body:
            raise RuntimeError("index.html no contiene una etiqueta </body> válida.")
        position = closing_body.start()
        fallback = f'<div class="admin-access-fallback">{ADMIN_LINK}</div>\n'
        source = source[:position] + fallback + source[position:]
        changed = True

    if 'id="admin-access"' not in source:
        raise RuntimeError("No se pudo incorporar el acceso administrativo en index.html.")

    INDEX.write_text(source, encoding="utf-8")
    return 1


def patch_script() -> int:
    source = _require_file(SCRIPT)
    if "// NEXUS_ADMIN_ACCESS_BEGIN" in source:
        return 0

    SCRIPT.write_text(source.rstrip() + ADMIN_FUNCTION + "\n", encoding="utf-8")
    return 1


def patch_styles() -> int:
    source = _require_file(STYLES)
    if ".admin-access-button{" in source and ".admin-access-fallback{" in source:
        return 0
    STYLES.write_text(source.rstrip() + ADMIN_CSS + "\n", encoding="utf-8")
    return 1


def validate_result() -> None:
    index = _require_file(INDEX)
    script = _require_file(SCRIPT)
    styles = _require_file(STYLES)
    checks = {
        "index.html": ('id="admin-access"', "hidden", 'href="/admin"'),
        "app.js": ("NEXUS_ADMIN_ACCESS_BEGIN", "/api/admin/access", "initializeAdminAccess"),
        "styles.css": (".admin-access-button{", ".admin-access-button[hidden]", ".admin-access-fallback{"),
    }
    content = {"index.html": index, "app.js": script, "styles.css": styles}
    missing = {
        name: [marker for marker in markers if marker not in content[name]]
        for name, markers in checks.items()
    }
    missing = {name: markers for name, markers in missing.items() if markers}
    if missing:
        raise RuntimeError(f"Integración administrativa incompleta: {missing}")


def main() -> None:
    changes = patch_index() + patch_script() + patch_styles()
    validate_result()
    print(
        "Botón administrativo condicional preparado de forma resiliente; "
        f"cambios: {changes}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
