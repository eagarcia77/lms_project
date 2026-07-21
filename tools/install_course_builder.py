from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = (
    ROOT / "app" / "main.py",
    ROOT / "app" / "course_studio_entry.py",
)
IMPORT_LINE = "from app.course_builder import router as course_builder_router"
INCLUDE_LINE = "app.include_router(course_builder_router)"


def _add_import(text: str) -> str:
    if IMPORT_LINE in text:
        return text
    future = re.match(r"from __future__ import [^\n]+\n", text)
    position = future.end() if future else 0
    return text[:position] + "\n" + IMPORT_LINE + "\n" + text[position:]


def _insert_after_fastapi_creation(text: str) -> str | None:
    match = re.search(r"(?m)^\s*app\s*=\s*FastAPI\s*\(", text)
    if not match:
        return None
    opening = text.find("(", match.start())
    depth = 0
    in_string: str | None = None
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in ("'", '"'):
            in_string = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[: index + 1] + "\n" + INCLUDE_LINE + text[index + 1 :]
    raise RuntimeError("No se pudo determinar el final de FastAPI(...)")


def _patch(path: Path) -> bool:
    if not path.exists():
        return False
    text = _add_import(path.read_text(encoding="utf-8"))
    if INCLUDE_LINE not in text:
        inserted = _insert_after_fastapi_creation(text)
        if inserted is not None:
            text = inserted
        elif re.search(r"(?m)^\s*app\s*=", text):
            text = text.rstrip() + "\n\n" + INCLUDE_LINE + "\n"
        else:
            raise RuntimeError(f"No se encontró la aplicación FastAPI en {path}")
    path.write_text(text, encoding="utf-8")
    compile(text, str(path), "exec")
    return True


def main() -> None:
    patched = [str(path.relative_to(ROOT)) for path in CANDIDATES if _patch(path)]
    if not patched:
        raise RuntimeError("No se encontró ninguna entrada de NEXUS EDU XR para instalar Course Builder.")
    print("Constructor CRUD instalado en: " + ", ".join(patched))


if __name__ == "__main__":
    main()
