from __future__ import annotations

from pathlib import Path

APP_JS = Path(__file__).resolve().parent / "static" / "app.js"
MARKER = "NUVEDRA_PUBLIC_LOGIN_SAFE_V1"

OPTIONAL_API = f'''/* {MARKER} */
async function optionalApi(path, fallback) {{
  try {{
    return await api(path);
  }} catch {{
    return fallback;
  }}
}}

'''

OLD_IDENTITY = '  state.me = await api("/api/me");'
NEW_IDENTITY = '''  try {
    state.me = await api("/api/me");
  } catch {
    state.me = { authenticated: false, user: null };
  }'''

OLD_INIT = '''    const [config, dashboard, courses, xr] = await Promise.all([
      api("/api/config"),
      api("/api/dashboard"),
      api("/api/courses"),
      api("/api/xr"),
    ]);'''

NEW_INIT = '''    const [config, dashboard, courses, xr] = await Promise.all([
      optionalApi("/api/config", { appName: "NUVEDRA", googleConfigured: false }),
      optionalApi("/api/dashboard", {
        stats: { courses: 0, activities: 0, xrExperiences: 0, engagement: 0 },
        upcoming: [],
        announcements: [],
      }),
      optionalApi("/api/courses", []),
      optionalApi("/api/xr", []),
    ]);'''


def main() -> None:
    if not APP_JS.is_file():
        raise RuntimeError(f"No se encontró {APP_JS}.")

    text = APP_JS.read_text(encoding="utf-8")
    changed = 0

    if MARKER not in text:
        anchor = "function escapeHTML(value) {"
        if anchor not in text:
            raise RuntimeError("No se encontró el punto para insertar optionalApi.")
        text = text.replace(anchor, OPTIONAL_API + anchor, 1)
        changed += 1

    if OLD_IDENTITY in text:
        text = text.replace(OLD_IDENTITY, NEW_IDENTITY, 1)
        changed += 1
    elif NEW_IDENTITY not in text:
        raise RuntimeError("No se pudo proteger la consulta de identidad de Google.")

    if OLD_INIT in text:
        text = text.replace(OLD_INIT, NEW_INIT, 1)
        changed += 1
    elif NEW_INIT not in text:
        raise RuntimeError("No se pudo convertir la carga inicial en tolerante a sesiones anónimas.")

    APP_JS.write_text(text, encoding="utf-8")

    updated = APP_JS.read_text(encoding="utf-8")
    required = (MARKER, "optionalApi(\"/api/config\"", "authenticated: false")
    missing = [item for item in required if item not in updated]
    if missing:
        raise RuntimeError(f"La portada pública quedó incompleta: {missing}")

    print(f"Portada pública de NUVEDRA protegida para acceso anónimo; cambios: {changed}.", flush=True)


if __name__ == "__main__":
    main()
