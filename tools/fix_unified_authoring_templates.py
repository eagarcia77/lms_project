from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "unified_authoring.py"

# JSON examples inside an f-string must double literal braces. Otherwise Python
# interprets the text after ':' as a format specifier when the page is rendered.
REPLACEMENTS = {
    "placeholder='\u007b\"questions\":[\u007b\"prompt\":\"...\",\"type\":\"multiple_choice\",\"points\":2\u007d]\u007d'":
    "placeholder='\u007b\u007b\"questions\":[\u007b\u007b\"prompt\":\"...\",\"type\":\"multiple_choice\",\"points\":2\u007d\u007d]\u007d\u007d'",
}


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    changed = 0
    for old, new in REPLACEMENTS.items():
        if old in source:
            source = source.replace(old, new)
            changed += 1
        elif new not in source:
            raise RuntimeError(f"No se encontró la plantilla esperada en {TARGET}: {old}")

    TARGET.write_text(source, encoding="utf-8")
    compile(source, str(TARGET), "exec")

    # Guard against reintroducing the known unsafe placeholder.
    unsafe = "placeholder='\u007b\"questions\":[\u007b\"prompt\":\"...\",\"type\":\"multiple_choice\",\"points\":2\u007d]\u007d'"
    if unsafe in source:
        raise RuntimeError("La plantilla JSON continúa sin escapar dentro de la f-string.")

    print(f"Plantillas de Unified Course Studio verificadas; correcciones aplicadas: {changed}.", flush=True)


if __name__ == "__main__":
    main()
