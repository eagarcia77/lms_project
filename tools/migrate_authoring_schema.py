from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_authoring.py"


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    marker = "# NEXUS_AUTHORING_SCHEMA_MIGRATION_V3"
    if marker in source:
        print("Migración de autoría V3 ya incorporada.")
        return

    needle = '''    with db() as conn:\n        for statement in statements:\n            execute(conn, statement)\n'''
    replacement = '''    with db() as conn:\n        for statement in statements:\n            execute(conn, statement)\n\n        # NEXUS_AUTHORING_SCHEMA_MIGRATION_V3\n        # CREATE TABLE IF NOT EXISTS no modifica tablas antiguas. Estas migraciones\n        # añaden, sin borrar datos, las columnas requeridas por Course Studio V2.\n        if database_url().startswith("postgres"):\n            migrations = [\n                "ALTER TABLE nexus_modules ADD COLUMN IF NOT EXISTS description TEXT",\n                "ALTER TABLE nexus_modules ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 1",\n                "ALTER TABLE nexus_modules ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft'",\n                "ALTER TABLE nexus_modules ADD COLUMN IF NOT EXISTS available_from TEXT",\n                "ALTER TABLE nexus_modules ADD COLUMN IF NOT EXISTS available_until TEXT",\n                "ALTER TABLE nexus_modules ADD COLUMN IF NOT EXISTS created_at TEXT",\n                "ALTER TABLE nexus_modules ADD COLUMN IF NOT EXISTS updated_at TEXT",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS item_type TEXT NOT NULL DEFAULT 'page'",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT 'Contenido'",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS body_html TEXT",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS external_url TEXT",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS embed_url TEXT",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS metadata_json TEXT",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS points DOUBLE PRECISION",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS due_at TEXT",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 1",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft'",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS created_at TEXT",\n                "ALTER TABLE nexus_content_items ADD COLUMN IF NOT EXISTS updated_at TEXT",\n            ]\n            for migration in migrations:\n                execute(conn, migration)\n        else:\n            # SQLite no soporta ADD COLUMN IF NOT EXISTS de forma uniforme.\n            existing = {row[1] for row in conn.execute("PRAGMA table_info(nexus_content_items)").fetchall()}\n            sqlite_columns = {\n                "item_type": "TEXT NOT NULL DEFAULT 'page'",\n                "title": "TEXT NOT NULL DEFAULT 'Contenido'",\n                "body_html": "TEXT",\n                "external_url": "TEXT",\n                "embed_url": "TEXT",\n                "metadata_json": "TEXT",\n                "points": "REAL",\n                "due_at": "TEXT",\n                "position": "INTEGER NOT NULL DEFAULT 1",\n                "status": "TEXT NOT NULL DEFAULT 'draft'",\n                "created_at": "TEXT",\n                "updated_at": "TEXT",\n            }\n            for name, definition in sqlite_columns.items():\n                if name not in existing:\n                    conn.execute(f"ALTER TABLE nexus_content_items ADD COLUMN {name} {definition}")\n'''

    if needle not in source:
        raise RuntimeError("No se encontró el bloque de inicialización del esquema de autoría.")

    source = source.replace(needle, replacement, 1)
    TARGET.write_text(source, encoding="utf-8")
    print("Migración no destructiva del esquema de autoría incorporada.")


if __name__ == "__main__":
    main()
