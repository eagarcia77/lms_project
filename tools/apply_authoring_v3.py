from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app" / "runtime_entry.py"
MARKER = "# NEXUS_AUTHORING_STUDIO_V4"


def main() -> None:
    source = ENTRY.read_text(encoding="utf-8")
    old_blocks = [
        "\n\n# NEXUS_AUTHORING_STUDIO_V2\nfrom app.admin_authoring import register_authoring\nregister_authoring(app)\n",
        "\n\n# NEXUS_AUTHORING_STUDIO_V3\nfrom app.admin_authoring_v3 import register_authoring_v3\nregister_authoring_v3(app)\n",
    ]
    for block in old_blocks:
        source = source.replace(block, "\n")
    if MARKER not in source:
        source = source.rstrip() + (
            "\n\n# NEXUS_AUTHORING_STUDIO_V4\n"
            "from app.admin_authoring_v4 import register_authoring_v4\n"
            "register_authoring_v4(app)\n"
        )
    ENTRY.write_text(source, encoding="utf-8")
    print("NEXUS Course Studio V4 registrado directamente.")


if __name__ == "__main__":
    main()
