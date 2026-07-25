from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
WORKER = ROOT / "app" / "static" / "sw.js"
OLD = "20260724-admin-access-v4"
NEW = "20260724-course-edit-v5"


def update(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    if NEW in source:
        return 0
    if OLD not in source:
        raise RuntimeError(f"No se encontró la versión de caché anterior en {path.name}.")
    path.write_text(source.replace(OLD, NEW), encoding="utf-8")
    return 1


def main() -> None:
    changes = update(INDEX) + update(WORKER)
    for path in (INDEX, WORKER):
        source = path.read_text(encoding="utf-8")
        if NEW not in source or OLD in source:
            raise RuntimeError(f"La caché del editor no se actualizó correctamente en {path.name}.")
    print(f"Caché de la portada actualizada para edición de cursos; cambios: {changes}.", flush=True)


if __name__ == "__main__":
    main()
