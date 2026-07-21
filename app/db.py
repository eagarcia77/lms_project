from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nexus.db"


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database() -> None:
    schema = """
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        instructor TEXT NOT NULL,
        progress INTEGER NOT NULL DEFAULT 0,
        accent TEXT NOT NULL DEFAULT '#007B5F',
        xr_enabled INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        position INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'available',
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        due_date TEXT,
        points INTEGER NOT NULL DEFAULT 0,
        google_url TEXT,
        FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        author TEXT NOT NULL,
        published_at TEXT NOT NULL,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS xr_experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        mode TEXT NOT NULL,
        description TEXT NOT NULL,
        model_url TEXT,
        course_code TEXT
    );
    """
    with connection() as conn:
        conn.executescript(schema)
        count = conn.execute("SELECT COUNT(*) AS total FROM courses").fetchone()["total"]
        if count == 0:
            seed_database(conn)


def seed_database(conn: sqlite3.Connection) -> None:
    courses = [
        ("NTEL 3770", "Redes Inalámbricas", "Diseño, seguridad y cobertura de redes inalámbricas.", "Dr. Eduardo A. García", 72, "#007B5F", 1),
        ("BADM 5030", "Metodología de Investigación", "Desarrollo progresivo de una investigación aplicada.", "Dr. Eduardo A. García", 58, "#3956A3", 0),
        ("PSYC 7050", "Diseño y Evaluación de Programas", "Planificación y evaluación científica de programas psicológicos.", "Facultad Graduada", 41, "#7A3E9D", 1),
    ]
    conn.executemany(
        "INSERT INTO courses(code,title,description,instructor,progress,accent,xr_enabled) VALUES (?,?,?,?,?,?,?)",
        courses,
    )
    course_ids = {row["code"]: row["id"] for row in conn.execute("SELECT id, code FROM courses")}

    modules = [
        (course_ids["NTEL 3770"], "Módulo 1 · Fundamentos inalámbricos", 1, "completed"),
        (course_ids["NTEL 3770"], "Módulo 2 · Seguridad y amenazas", 2, "available"),
        (course_ids["NTEL 3770"], "Módulo 3 · Diseño de cobertura", 3, "available"),
        (course_ids["BADM 5030"], "Parte 1 · Idea y bibliografía", 1, "completed"),
        (course_ids["BADM 5030"], "Parte 2 · Capítulo I", 2, "available"),
        (course_ids["PSYC 7050"], "Unidad 1 · Planificación de programas", 1, "available"),
    ]
    conn.executemany(
        "INSERT INTO modules(course_id,title,position,status) VALUES (?,?,?,?)", modules
    )
    module_ids = {row["title"]: row["id"] for row in conn.execute("SELECT id,title FROM modules")}

    activities = [
        (module_ids["Módulo 2 · Seguridad y amenazas"], "Foro: análisis de ataques", "discussion", "2026-07-28", 20, "https://docs.google.com/"),
        (module_ids["Módulo 3 · Diseño de cobertura"], "Laboratorio XR: ubicación de puntos de acceso", "xr_lab", "2026-08-03", 50, None),
        (module_ids["Parte 2 · Capítulo I"], "Entrega del Capítulo I", "assignment", "2026-07-31", 100, "https://drive.google.com/"),
        (module_ids["Unidad 1 · Planificación de programas"], "Mapa conceptual colaborativo", "collaboration", "2026-08-05", 30, "https://docs.google.com/presentation/"),
    ]
    conn.executemany(
        "INSERT INTO activities(module_id,title,activity_type,due_date,points,google_url) VALUES (?,?,?,?,?,?)",
        activities,
    )

    announcements = [
        (None, "Bienvenidos a NEXUS EDU XR", "Esta versión inicial demuestra el centro académico, Google Hub y los laboratorios inmersivos.", "Administración", "2026-07-21T09:00:00-04:00"),
        (course_ids["NTEL 3770"], "Nuevo laboratorio inmersivo", "Ya está disponible la simulación para planificar la cobertura de una red inalámbrica.", "Dr. Eduardo A. García", "2026-07-21T10:15:00-04:00"),
    ]
    conn.executemany(
        "INSERT INTO announcements(course_id,title,body,author,published_at) VALUES (?,?,?,?,?)",
        announcements,
    )

    experiences = [
        ("Laboratorio de cobertura Wi-Fi", "VR", "Explora un salón virtual y determina la ubicación óptima de los puntos de acceso.", None, "NTEL 3770"),
        ("Anatomía de un modelo 3D", "AR", "Coloca un objeto 3D en tu espacio y examínalo desde cualquier ángulo.", "https://modelviewer.dev/shared-assets/models/Astronaut.glb", "DEMO XR"),
        ("Campus virtual colaborativo", "VR", "Espacio persistente para orientación, tutorías, presentaciones y trabajo en equipo.", None, "INSTITUCIONAL"),
    ]
    conn.executemany(
        "INSERT INTO xr_experiences(title,mode,description,model_url,course_code) VALUES (?,?,?,?,?)",
        experiences,
    )
