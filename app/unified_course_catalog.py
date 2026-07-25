from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from app.admin_authoring_v6 import ensure_schema
from app.admin_console import db, database_url, execute, rows, utcnow
from app.platform_access import _payload

ACCENTS = ("#007B5F", "#3956A3", "#7A3E9D", "#B45309", "#0F766E")
EDITOR_COURSE_ROLES = {"instructor", "teaching_assistant", "course_builder", "facilitator"}

LEGACY_COURSES = (
    {
        "code": "NTEL 3770",
        "title": "Redes Inalámbricas",
        "description": "Diseño, seguridad y cobertura de redes inalámbricas.",
        "modules": (
            ("Módulo 1 · Fundamentos inalámbricos", 1, ()),
            ("Módulo 2 · Seguridad y amenazas", 2, (("discussion", "Foro: análisis de ataques", "2026-07-28", 20),)),
            ("Módulo 3 · Diseño de cobertura", 3, (("vr", "Laboratorio XR: ubicación de puntos de acceso", "2026-08-03", 50),)),
        ),
    },
    {
        "code": "BADM 5030",
        "title": "Metodología de Investigación",
        "description": "Desarrollo progresivo de una investigación aplicada.",
        "modules": (
            ("Parte 1 · Idea y bibliografía", 1, ()),
            ("Parte 2 · Capítulo I", 2, (("assignment", "Entrega del Capítulo I", "2026-07-31", 100),)),
        ),
    },
    {
        "code": "PSYC 7050",
        "title": "Diseño y Evaluación de Programas",
        "description": "Planificación y evaluación científica de programas psicológicos.",
        "modules": (
            ("Unidad 1 · Planificación de programas", 1, (("presentation", "Mapa conceptual colaborativo", "2026-08-05", 30),)),
        ),
    },
)


def _replace_route(app: FastAPI, path: str, method: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and method in set(getattr(route, "methods", set()) or set())
        )
    ]


def _insert_course(conn: Any, code: str, title: str, description: str) -> int:
    now = utcnow()
    params = (code, title, description, "", "active", "", "legacy-migration", now, now)
    if database_url().startswith("postgres"):
        row = execute(
            conn,
            """INSERT INTO nexus_admin_courses
            (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""",
            params,
        ).fetchone()
        return int(row[0])
    cursor = execute(
        conn,
        """INSERT INTO nexus_admin_courses
        (course_code,title,description,term,status,instructor_email,created_by,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        params,
    )
    return int(cursor.lastrowid)


def migrate_legacy_courses() -> None:
    ensure_schema()
    with db() as conn:
        for course in LEGACY_COURSES:
            existing = rows(execute(conn, "SELECT id FROM nexus_admin_courses WHERE UPPER(course_code)=?", (course["code"].upper(),)))
            if existing:
                continue
            course_id = _insert_course(conn, course["code"], course["title"], course["description"])
            for module_title, position, activities in course["modules"]:
                now = utcnow()
                if database_url().startswith("postgres"):
                    row = execute(
                        conn,
                        """INSERT INTO nexus_modules
                        (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""",
                        (course_id, module_title, "", "", 60, position, "published", now, now),
                    ).fetchone()
                    module_id = int(row[0])
                else:
                    cursor = execute(
                        conn,
                        """INSERT INTO nexus_modules
                        (course_id,title,description,learning_outcomes,estimated_minutes,position,status,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (course_id, module_title, "", "", 60, position, "published", now, now),
                    )
                    module_id = int(cursor.lastrowid)
                for item_position, (item_type, title, due_at, points) in enumerate(activities, 1):
                    execute(
                        conn,
                        """INSERT INTO nexus_content_items
                        (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (module_id, item_type, title, "", None, None, json.dumps({"migrated": True}), points, due_at, item_position, "published", now, now),
                    )
    print("Catálogo histórico migrado al Course Studio sin duplicados.", flush=True)


def _visible_course_ids(identity: dict[str, Any]) -> set[int] | None:
    if identity.get("isAdmin"):
        return None
    memberships = identity.get("courseRoles") or []
    return {int(item["course_id"]) for item in memberships if item.get("status") == "active"}


def _can_edit(identity: dict[str, Any], course_id: int) -> bool:
    if identity.get("isAdmin"):
        return True
    for membership in identity.get("courseRoles") or []:
        if int(membership.get("course_id") or 0) == course_id and str(membership.get("course_role") or "") in EDITOR_COURSE_ROLES:
            return True
    return identity.get("platformRole") == "instructor" and any(
        int(item.get("course_id") or 0) == course_id for item in identity.get("courseRoles") or []
    )


def _course_summary(conn: Any, course: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    course_id = int(course["id"])
    modules = rows(execute(conn, "SELECT COUNT(*) AS total FROM nexus_modules WHERE course_id=?", (course_id,)))
    activities = rows(
        execute(
            conn,
            "SELECT COUNT(*) AS total FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id WHERE m.course_id=?",
            (course_id,),
        )
    )
    xr = rows(
        execute(
            conn,
            "SELECT COUNT(*) AS total FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id WHERE m.course_id=? AND i.item_type IN ('ar','vr','360')",
            (course_id,),
        )
    )
    status = str(course.get("status") or "draft")
    progress = 100 if status == "completed" else 60 if status == "active" else 20 if status == "draft" else 0
    return {
        "id": course_id,
        "code": course.get("course_code"),
        "title": course.get("title"),
        "description": course.get("description") or "",
        "instructor": course.get("instructor_email") or "Facultad por asignar",
        "progress": progress,
        "accent": ACCENTS[(course_id - 1) % len(ACCENTS)],
        "xr_enabled": int(xr[0].get("total") or 0) > 0 if xr else False,
        "module_count": int(modules[0].get("total") or 0) if modules else 0,
        "activity_count": int(activities[0].get("total") or 0) if activities else 0,
        "status": status,
        "can_edit": _can_edit(identity, course_id),
        "edit_url": f"/admin/authoring/courses/{course_id}",
    }


def register_unified_course_catalog(app: FastAPI) -> None:
    migrate_legacy_courses()
    for path, method in (
        ("/api/dashboard", "GET"),
        ("/api/courses", "GET"),
        ("/api/courses/{course_id}", "GET"),
        ("/api/xr", "GET"),
    ):
        _replace_route(app, path, method)

    @app.get("/api/courses", response_model=None)
    async def unified_courses(request: Request) -> list[dict[str, Any]]:
        identity = _payload(request)
        visible = _visible_course_ids(identity)
        with db() as conn:
            if visible is None:
                courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE status<>'archived' ORDER BY updated_at DESC,id DESC"))
            elif visible:
                placeholders = ",".join("?" for _ in visible)
                courses = rows(execute(conn, f"SELECT * FROM nexus_admin_courses WHERE id IN ({placeholders}) AND status<>'archived' ORDER BY updated_at DESC,id DESC", tuple(sorted(visible))))
            else:
                courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE status='active' ORDER BY updated_at DESC,id DESC")) if not identity.get("authenticated") else []
            return [_course_summary(conn, course, identity) for course in courses]

    @app.get("/api/courses/{course_id}", response_model=None)
    async def unified_course_detail(course_id: int, request: Request) -> dict[str, Any]:
        identity = _payload(request)
        visible = _visible_course_ids(identity)
        if visible is not None and identity.get("authenticated") and course_id not in visible:
            raise HTTPException(403, "No tiene acceso a este curso.")
        with db() as conn:
            found = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE id=? AND status<>'archived'", (course_id,)))
            if not found:
                raise HTTPException(404, "Curso no encontrado.")
            course = _course_summary(conn, found[0], identity)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                module["activities"] = rows(
                    execute(
                        conn,
                        """SELECT id,title,item_type AS activity_type,due_at AS due_date,COALESCE(points,0) AS points,status
                        FROM nexus_content_items WHERE module_id=? ORDER BY position,id""",
                        (module["id"],),
                    )
                )
        return {"course": course, "modules": modules}

    @app.get("/api/dashboard", response_model=None)
    async def unified_dashboard(request: Request) -> dict[str, Any]:
        identity = _payload(request)
        visible = _visible_course_ids(identity)
        with db() as conn:
            if visible is None:
                where = "c.status<>'archived'"
                params: tuple[Any, ...] = ()
            elif visible:
                placeholders = ",".join("?" for _ in visible)
                where = f"c.id IN ({placeholders}) AND c.status<>'archived'"
                params = tuple(sorted(visible))
            else:
                where = "c.status='active'" if not identity.get("authenticated") else "1=0"
                params = ()
            courses_count = rows(execute(conn, f"SELECT COUNT(*) AS total FROM nexus_admin_courses c WHERE {where}", params))
            activity_count = rows(execute(conn, f"SELECT COUNT(*) AS total FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id JOIN nexus_admin_courses c ON c.id=m.course_id WHERE {where}", params))
            xr_count = rows(execute(conn, f"SELECT COUNT(*) AS total FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id JOIN nexus_admin_courses c ON c.id=m.course_id WHERE {where} AND i.item_type IN ('ar','vr','360')", params))
            upcoming = rows(execute(conn, f"""SELECT i.id,i.title,i.item_type AS activity_type,i.due_at AS due_date,COALESCE(i.points,0) AS points,c.course_code,c.title AS course_title
                FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id JOIN nexus_admin_courses c ON c.id=m.course_id
                WHERE {where} AND i.due_at IS NOT NULL AND i.due_at<>'' ORDER BY i.due_at LIMIT 5""", params))
        return {
            "stats": {
                "courses": int(courses_count[0].get("total") or 0) if courses_count else 0,
                "activities": int(activity_count[0].get("total") or 0) if activity_count else 0,
                "xrExperiences": int(xr_count[0].get("total") or 0) if xr_count else 0,
                "engagement": 0,
            },
            "upcoming": upcoming,
            "announcements": [],
        }

    @app.get("/api/xr", response_model=None)
    async def unified_xr(request: Request) -> list[dict[str, Any]]:
        identity = _payload(request)
        visible = _visible_course_ids(identity)
        with db() as conn:
            if visible is None:
                where = "c.status<>'archived'"
                params: tuple[Any, ...] = ()
            elif visible:
                placeholders = ",".join("?" for _ in visible)
                where = f"c.id IN ({placeholders})"
                params = tuple(sorted(visible))
            else:
                where = "c.status='active'" if not identity.get("authenticated") else "1=0"
                params = ()
            items = rows(execute(conn, f"""SELECT i.id,i.title,i.item_type AS mode,COALESCE(i.body_html,'') AS description,
                COALESCE(i.external_url,i.embed_url) AS model_url,c.course_code
                FROM nexus_content_items i JOIN nexus_modules m ON m.id=i.module_id JOIN nexus_admin_courses c ON c.id=m.course_id
                WHERE {where} AND i.item_type IN ('ar','vr','360') ORDER BY i.updated_at DESC""", params))
        return items

    print("Portada y Course Studio conectados al mismo catálogo de cursos.", flush=True)
