from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app" / "runtime_entry.py"
MARKER = "# NEXUS_ADMIN_CONSOLE_V1"


def main() -> None:
    if not ENTRY.exists():
        raise RuntimeError(f"No se encontró {ENTRY}")
    source = ENTRY.read_text(encoding="utf-8")
    if MARKER in source:
        print("La consola administrativa ya está registrada.")
        return
    addition = '''\n\n# NEXUS_ADMIN_CONSOLE_V1\nfrom app.admin_console import register_admin_console\nregister_admin_console(app)\n'''
    ENTRY.write_text(source.rstrip() + addition, encoding="utf-8")
    print("Consola administrativa NEXUS registrada correctamente.")


if __name__ == "__main__":
    main()
