from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "course_builder.py"


def main() -> None:
    if not TARGET.exists():
        raise RuntimeError("No existe app/course_builder.py")

    text = TARGET.read_text(encoding="utf-8")

    if "from fastapi import APIRouter, Request, Response" not in text:
        text = text.replace(
            "from fastapi import APIRouter, Request",
            "from fastapi import APIRouter, Request, Response",
            1,
        )

    incompatible = "HTMLResponse | RedirectResponse"
    occurrences = text.count(incompatible)
    text = text.replace(incompatible, "Response")

    if occurrences == 0 and "-> Response:" not in text:
        raise RuntimeError("No se encontraron las anotaciones de respuesta que debían corregirse.")

    compile(text, str(TARGET), "exec")
    TARGET.write_text(text, encoding="utf-8")
    print(f"Tipos de respuesta de Course Builder corregidos: {occurrences}")


if __name__ == "__main__":
    main()
