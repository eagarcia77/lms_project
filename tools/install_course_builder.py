from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"
IMPORT_LINE = "from app.course_builder import router as course_builder_router"
INCLUDE_LINE = "app.include_router(course_builder_router)"


def insert_after_fastapi_creation(text: str) -> str:
    match = re.search(r"(?m)^\s*app\s*=\s*FastAPI\s*\(", text)
    if not match:
        raise RuntimeError("No se encontró la creación de FastAPI en app/main.py")
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


def main() -> None:
    text = MAIN.read_text(encoding="utf-8")
    if IMPORT_LINE not in text:
        future = re.match(r"from __future__ import [^\n]+\n", text)
        position = future.end() if future else 0
        text = text[:position] + "\n" + IMPORT_LINE + "\n" + text[position:]
    if INCLUDE_LINE not in text:
        text = insert_after_fastapi_creation(text)
    MAIN.write_text(text, encoding="utf-8")
    compile(text, str(MAIN), "exec")
    print("Constructor CRUD de cursos instalado correctamente.")


if __name__ == "__main__":
    main()
