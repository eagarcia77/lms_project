from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "google_api.py"

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
    marker = "SCOPES = ["
    start = source.find(marker)
    if start < 0:
        raise RuntimeError("No se encontró SCOPES en app/google_api.py")
    end = source.find("\n]", start)
    if end < 0:
        raise RuntimeError("No se pudo localizar el final de SCOPES")
    block = source[start : end + 2]
    additions = [
        f'    "{scope}",'
        for scope in REQUIRED_SCOPES
        if f'"{scope}"' not in block
    ]
    if additions:
        updated_block = block[:-2].rstrip() + "\n" + "\n".join(additions) + "\n]"
        source = source[:start] + updated_block + source[end + 2 :]
        TARGET.write_text(source, encoding="utf-8")
    compile(TARGET.read_text(encoding="utf-8"), str(TARGET), "exec")
    print("Permisos de Google Workspace verificados.")


if __name__ == "__main__":
    main()
