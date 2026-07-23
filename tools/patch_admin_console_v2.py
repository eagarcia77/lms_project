from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_console.py"


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    source = source.replace(
        '    if len(password) < 12:\n        raise RuntimeError("NEXUS_BOOTSTRAP_ADMIN_PASSWORD debe tener al menos 12 caracteres.")',
        '    if len(password) < 12:\n        print("ADVERTENCIA: NEXUS_BOOTSTRAP_ADMIN_PASSWORD no cumple el mínimo de 12 caracteres; la cuenta inicial no fue creada.")\n        return',
    )
    source = source.replace(
        '<a href="/admin/courses">Cursos</a><a href="/admin/users">Usuarios</a>',
        '<a href="/admin/courses">Cursos</a><a href="/admin/authoring">Diseñador</a><a href="/admin/users">Usuarios</a>',
    )
    source = source.replace(
        'La próxima fase conectará copia de cursos, plantillas maestras y contenido del Course Studio.',
        'Use el Diseñador académico para crear módulos, materiales, asignaciones, discusiones y evaluaciones dentro de cada curso.',
    )
    source = source.replace(
        '<th>Profesor</th><th>Administrar</th>',
        '<th>Profesor</th><th>Contenido</th><th>Administrar</th>',
    )
    source = source.replace(
        "<td>{html.escape(x.get('instructor_email') or '')}</td><td><form method='post'",
        "<td>{html.escape(x.get('instructor_email') or '')}</td><td><a class='button' href='/admin/authoring/courses/{x['id']}'>Diseñar</a></td><td><form method='post'",
    )
    TARGET.write_text(source, encoding="utf-8")
    print("Consola administrativa NEXUS actualizada a V2.")


if __name__ == "__main__":
    main()
