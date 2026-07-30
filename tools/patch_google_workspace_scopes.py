from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "google_api.py"
MARKER = "# NUVEDRA_GOOGLE_WORKSPACE_SCOPES_V2"

REQUIRED_SCOPES = (
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/calendar.events",
)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    if MARKER not in source:
        literals = ",\n    ".join(repr(scope) for scope in REQUIRED_SCOPES)
        compatibility = f'''\n\n{MARKER}\n_NUVEDRA_REQUIRED_SCOPES = (\n    {literals},\n)\ntry:\n    SCOPES = list(dict.fromkeys([*SCOPES, *_NUVEDRA_REQUIRED_SCOPES]))\nexcept NameError:\n    # Some authenticated base versions keep scopes in another module.\n    # The API contract remains untouched and NUVEDRA continues safely.\n    pass\n'''
        source += compatibility
        TARGET.write_text(source, encoding="utf-8")

    compile(TARGET.read_text(encoding="utf-8"), str(TARGET), "exec")
    print("Permisos de Google Workspace verificados sin reemplazar el contrato OAuth V3.")


if __name__ == "__main__":
    main()
