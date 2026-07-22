from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "course_builder.py"
ROUTE_DECORATOR = re.compile(
    r"(?m)^(?P<prefix>\s*@router\.(?:get|post|put|patch|delete)\()(?P<args>[^\n]*)(?P<close>\)\s*)$"
)


def _disable_response_model_inference(text: str) -> tuple[str, int]:
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        args = match.group("args")
        if "response_model=" in args:
            return match.group(0)
        changed += 1
        separator = "" if not args.strip() else ", "
        return f'{match.group("prefix")}{args}{separator}response_model=None{match.group("close")}'

    return ROUTE_DECORATOR.sub(replace, text), changed


def main() -> None:
    if not TARGET.exists():
        raise RuntimeError("No existe app/course_builder.py")

    text = TARGET.read_text(encoding="utf-8")

    # Las uniones de clases Response no deben convertirse en modelos Pydantic.
    if "from fastapi import APIRouter, Request, Response" not in text:
        text = text.replace(
            "from fastapi import APIRouter, Request",
            "from fastapi import APIRouter, Request, Response",
            1,
        )
    text = text.replace("HTMLResponse | RedirectResponse", "Response")

    # response_model=None evita que FastAPI infiera modelos desde cualquier
    # anotación de retorno presente o futura en las rutas del constructor.
    text, changed = _disable_response_model_inference(text)

    remaining = [
        line
        for line in text.splitlines()
        if line.lstrip().startswith(("@router.get(", "@router.post(", "@router.put(", "@router.patch(", "@router.delete("))
        and "response_model=None" not in line
    ]
    if remaining:
        raise RuntimeError("Quedaron rutas sin response_model=None: " + " | ".join(remaining))

    compile(text, str(TARGET), "exec")
    TARGET.write_text(text, encoding="utf-8")
    print(f"Inferencia de response_model desactivada en {changed} rutas de Course Builder.")


if __name__ == "__main__":
    main()
