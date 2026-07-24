from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
SCRIPT = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"

ADMIN_LINK = '''          <a id="admin-access" class="admin-access-button" href="/admin" hidden aria-label="Abrir administración de NEXUS">⚙ Administración</a>\n'''

ADMIN_FUNCTION = '''\nasync function updateAdminAccess() {\n  const adminLink = $("#admin-access");\n  if (!adminLink) return;\n  adminLink.hidden = true;\n  try {\n    const access = await api("/api/admin/access");\n    if (!access.allowed) return;\n    adminLink.href = access.href || "/admin";\n    adminLink.hidden = false;\n    const role = access.role ? ` · ${access.role}` : "";\n    adminLink.title = access.requiresAdminLogin\n      ? `Cuenta administrativa reconocida${role}. Inicie la sesión administrativa para continuar.`\n      : `Abrir el panel administrativo${role}.`;\n  } catch (_) {\n    adminLink.hidden = true;\n  }\n}\n'''

ADMIN_CSS = '''\n.admin-access-button{display:inline-flex;align-items:center;justify-content:center;gap:7px;background:#0B4E3F;color:#fff;text-decoration:none;border:1px solid #0B4E3F;border-radius:13px;padding:10px 14px;font-weight:800;white-space:nowrap;box-shadow:0 7px 18px rgba(11,78,63,.14)}.admin-access-button:hover,.admin-access-button:focus-visible{background:#073B30;transform:translateY(-1px)}.admin-access-button[hidden]{display:none!important}@media(max-width:760px){.admin-access-button{padding:10px;width:44px;height:44px;font-size:0}.admin-access-button::first-letter{font-size:18px}}\n'''


def patch_index() -> int:
    source = INDEX.read_text(encoding="utf-8")
    if 'id="admin-access"' in source:
        return 0
    marker = '        <div class="top-actions">\n          <button class="icon-button" aria-label="Notificaciones">'
    if marker not in source:
        raise RuntimeError("No se encontró el bloque de acciones superiores en index.html.")
    source = source.replace(
        marker,
        '        <div class="top-actions">\n' + ADMIN_LINK + '          <button class="icon-button" aria-label="Notificaciones">',
        1,
    )
    INDEX.write_text(source, encoding="utf-8")
    return 1


def patch_script() -> int:
    source = SCRIPT.read_text(encoding="utf-8")
    changed = 0
    if "async function updateAdminAccess()" not in source:
        marker = "async function updateGoogleIdentity() {"
        if marker not in source:
            raise RuntimeError("No se encontró updateGoogleIdentity() en app.js.")
        source = source.replace(marker, ADMIN_FUNCTION + "\n" + marker, 1)
        changed += 1

    init_old = "renderDashboard(); renderCourses(); renderXR(); bindEvents(); await updateGoogleIdentity();"
    init_new = "renderDashboard(); renderCourses(); renderXR(); bindEvents(); await updateGoogleIdentity(); await updateAdminAccess();"
    if init_new not in source:
        if init_old not in source:
            raise RuntimeError("No se encontró la secuencia de inicialización de app.js.")
        source = source.replace(init_old, init_new, 1)
        changed += 1

    logout_old = '      await updateGoogleIdentity();\n      toast("Cuenta de Google desconectada.");'
    logout_new = '      await updateGoogleIdentity();\n      await updateAdminAccess();\n      toast("Cuenta de Google desconectada.");'
    if logout_new not in source:
        if logout_old not in source:
            raise RuntimeError("No se encontró el flujo de desconexión de Google en app.js.")
        source = source.replace(logout_old, logout_new, 1)
        changed += 1

    SCRIPT.write_text(source, encoding="utf-8")
    compile("", str(SCRIPT), "exec")
    return changed


def patch_styles() -> int:
    source = STYLES.read_text(encoding="utf-8")
    if ".admin-access-button{" in source:
        return 0
    STYLES.write_text(source.rstrip() + ADMIN_CSS, encoding="utf-8")
    return 1


def main() -> None:
    changes = patch_index() + patch_script() + patch_styles()
    print(f"Botón administrativo condicional preparado en la página principal; cambios: {changes}.", flush=True)


if __name__ == "__main__":
    main()
