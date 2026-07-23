from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app" / "runtime_entry.py"
MARKER = "# NEXUS_AUTHORING_STUDIO_V2"


def main() -> None:
    if not ENTRY.exists():
        raise RuntimeError(f"No se encontró {ENTRY}")
    source = ENTRY.read_text(encoding="utf-8")
    if MARKER in source:
        print("El estudio de autoría ya está registrado.")
        return
    addition = '''\n\n# NEXUS_AUTHORING_STUDIO_V2\nfrom app.admin_authoring import register_authoring\nregister_authoring(app)\n'''
    ENTRY.write_text(source.rstrip() + addition, encoding="utf-8")
    print("NEXUS Course Studio V2 registrado correctamente.")


if __name__ == "__main__":
    main()
