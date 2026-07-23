from __future__ import annotations

import html
import json
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.admin_console import audit, db, execute, page, require_admin, rows, utcnow

CONTENT_TYPES = {"document", "link", "video", "file", "image", "embed", "xr"}


def _h(value: Any) -> str:
    return html.escape(str(value or ""))


def init_authoring_schema() -> None:
    statements = [
        """CREATE TABLE IF NOT EXISTS nexus_course_modules (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            course_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT,
            position INTEGER NOT NULL DEFAULT 0, published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_course_materials (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            module_id INTEGER NOT NULL, title TEXT NOT NULL, material_type TEXT NOT NULL,
            content TEXT, url TEXT, position INTEGER NOT NULL DEFAULT 0,
            published INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_course_assignments (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            module_id INTEGER NOT NULL, title TEXT NOT NULL, instructions TEXT,
            points REAL NOT NULL DEFAULT 100, due_at TEXT, submission_type TEXT NOT NULL DEFAULT 'online_text',
            published INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_course_discussions (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            module_id INTEGER NOT NULL, title TEXT NOT NULL, prompt TEXT,
            points REAL NOT NULL DEFAULT 0, due_at TEXT, published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS nexus_course_assessments (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            module_id INTEGER NOT NULL, title TEXT NOT NULL, instructions TEXT,
            points REAL NOT NULL DEFAULT 100, due_at TEXT, time_limit_minutes INTEGER,
            attempts INTEGER NOT NULL DEFAULT 1, question_bank_json TEXT NOT NULL DEFAULT '[]',
            published INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
    ]
    sqlite_statements = [s.replace("INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY", "INTEGER PRIMARY KEY AUTOINCREMENT") for s in statements]
    from app.admin_console import database_url
    with db() as conn:
        for statement in (statements if database_url().startswith("postgres") else sqlite_statements):
            execute(conn, statement)


def register_admin_course_authoring(app: FastAPI) -> None:
    init_authoring_schema()

    @app.get("/admin/authoring", response_class=HTMLResponse)
    async def authoring_home(request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            courses = rows(execute(conn, "SELECT id,course_code,title,term,status FROM nexus_admin_courses ORDER BY id DESC"))
        cards = "".join(
            f'''<article class="card"><p class="status">{_h(c['course_code'])}</p><h3>{_h(c['title'])}</h3><p>{_h(c.get('term'))} · {_h(c['status'])}</p><a class="button" href="/admin/authoring/courses/{c['id']}">Abrir diseñador</a></article>'''
            for c in courses
        ) or '<section class="card"><h3>No hay cursos administrativos</h3><p>Cree primero un curso desde <a href="/admin/courses">Administración de cursos</a>.</p></section>'
        return page("Diseñador académico", f'''<h2>Diseñador académico</h2><p>Organice cada curso en módulos e incorpore materiales, asignaciones, discusiones y evaluaciones.</p><div class="grid">{cards}</div>''', user)

    @app.get("/admin/authoring/courses/{course_id}", response_class=HTMLResponse)
    async def course_editor(course_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            course_rows = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,)))
            if not course_rows:
                raise HTTPException(404, "Curso no encontrado")
            course = course_rows[0]
            modules = rows(execute(conn, "SELECT * FROM nexus_course_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            for module in modules:
                mid = module["id"]
                module["materials"] = rows(execute(conn, "SELECT * FROM nexus_course_materials WHERE module_id=? ORDER BY position,id", (mid,)))
                module["assignments"] = rows(execute(conn, "SELECT * FROM nexus_course_assignments WHERE module_id=? ORDER BY id", (mid,)))
                module["discussions"] = rows(execute(conn, "SELECT * FROM nexus_course_discussions WHERE module_id=? ORDER BY id", (mid,)))
                module["assessments"] = rows(execute(conn, "SELECT * FROM nexus_course_assessments WHERE module_id=? ORDER BY id", (mid,)))

        module_html = []
        for m in modules:
            materials = "".join(f"<li><strong>{_h(x['title'])}</strong> · {_h(x['material_type'])} · {'Publicado' if x['published'] else 'Borrador'}</li>" for x in m["materials"]) or "<li>Sin materiales</li>"
            assignments = "".join(f"<li><strong>{_h(x['title'])}</strong> · {_h(x['points'])} puntos · {'Publicado' if x['published'] else 'Borrador'}</li>" for x in m["assignments"]) or "<li>Sin asignaciones</li>"
            discussions = "".join(f"<li><strong>{_h(x['title'])}</strong> · {'Publicado' if x['published'] else 'Borrador'}</li>" for x in m["discussions"]) or "<li>Sin discusiones</li>"
            assessments = "".join(f"<li><strong>{_h(x['title'])}</strong> · {_h(x['points'])} puntos · {'Publicado' if x['published'] else 'Borrador'}</li>" for x in m["assessments"]) or "<li>Sin evaluaciones</li>"
            module_html.append(f'''<section class="card"><p class="status">Módulo {m['position']}</p><h3>{_h(m['title'])}</h3><p>{_h(m.get('description'))}</p><p>{'Publicado' if m['published'] else 'Borrador'}</p><div class="grid"><div><h4>Materiales</h4><ul>{materials}</ul></div><div><h4>Asignaciones</h4><ul>{assignments}</ul></div><div><h4>Discusiones</h4><ul>{discussions}</ul></div><div><h4>Evaluaciones</h4><ul>{assessments}</ul></div></div><p><a class="button" href="/admin/authoring/modules/{m['id']}">Añadir contenido</a></p></section>''')

        body = f'''<p><a href="/admin/authoring">← Todos los cursos</a></p><h2>{_h(course['course_code'])} · {_h(course['title'])}</h2><p>{_h(course.get('description'))}</p><div class="grid"><section class="card"><h3>Crear módulo</h3><form method="post" action="/admin/authoring/courses/{course_id}/modules"><label>Título<input name="title" required></label><label>Descripción<textarea name="description"></textarea></label><label>Posición<input type="number" name="position" min="0" value="{len(modules)+1}"></label><label><input style="width:auto" type="checkbox" name="published" value="1"> Publicar inmediatamente</label><button>Crear módulo</button></form></section><section class="card"><h3>Flujo recomendado</h3><ol><li>Cree los módulos.</li><li>Añada materiales y enlaces.</li><li>Configure asignaciones y discusiones.</li><li>Prepare evaluaciones.</li><li>Revise y publique.</li></ol></section></div>{''.join(module_html) or '<section class="card"><p>Este curso todavía no tiene módulos.</p></section>'}'''
        return page("Diseño del curso", body, user)

    @app.post("/admin/authoring/courses/{course_id}/modules")
    async def create_module(course_id: int, request: Request, title: str = Form(...), description: str = Form(""), position: int = Form(0), published: str = Form("0")):
        user = require_admin(request, {"course_admin"})
        now = utcnow()
        with db() as conn:
            execute(conn, "INSERT INTO nexus_course_modules (course_id,title,description,position,published,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", (course_id, title.strip(), description.strip(), position, 1 if published == "1" else 0, now, now))
            audit(conn, user["email"], "module_created", "course", str(course_id), title, request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{course_id}", status_code=303)

    @app.get("/admin/authoring/modules/{module_id}", response_class=HTMLResponse)
    async def module_editor(module_id: int, request: Request):
        user = require_admin(request, {"course_admin"})
        with db() as conn:
            found = rows(execute(conn, "SELECT m.*,c.title AS course_title,c.id AS course_id FROM nexus_course_modules m JOIN nexus_admin_courses c ON c.id=m.course_id WHERE m.id=?", (module_id,)))
        if not found:
            raise HTTPException(404, "Módulo no encontrado")
        m = found[0]
        body = f'''<p><a href="/admin/authoring/courses/{m['course_id']}">← {_h(m['course_title'])}</a></p><h2>{_h(m['title'])}</h2><div class="grid">
<section class="card"><h3>Añadir material</h3><form method="post" action="/admin/authoring/modules/{module_id}/materials"><label>Título<input name="title" required></label><label>Tipo<select name="material_type"><option value="document">Documento o lectura</option><option value="link">Enlace web</option><option value="video">Video</option><option value="file">Archivo</option><option value="image">Imagen</option><option value="embed">Contenido incrustado</option><option value="xr">Recurso AR/VR/3D</option></select></label><label>Texto o instrucciones<textarea name="content"></textarea></label><label>URL<input type="url" name="url"></label><label><input style="width:auto" type="checkbox" name="published" value="1"> Publicar</label><button>Añadir material</button></form></section>
<section class="card"><h3>Crear asignación</h3><form method="post" action="/admin/authoring/modules/{module_id}/assignments"><label>Título<input name="title" required></label><label>Instrucciones<textarea name="instructions"></textarea></label><label>Puntuación<input type="number" step="0.01" min="0" name="points" value="100"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label><label>Entrega<select name="submission_type"><option value="online_text">Texto en línea</option><option value="file_upload">Carga de archivo</option><option value="external_url">Enlace externo</option><option value="no_submission">Sin entrega</option></select></label><label><input style="width:auto" type="checkbox" name="published" value="1"> Publicar</label><button>Crear asignación</button></form></section>
<section class="card"><h3>Crear discusión</h3><form method="post" action="/admin/authoring/modules/{module_id}/discussions"><label>Título<input name="title" required></label><label>Pregunta o consigna<textarea name="prompt"></textarea></label><label>Puntuación<input type="number" step="0.01" min="0" name="points" value="0"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label><label><input style="width:auto" type="checkbox" name="published" value="1"> Publicar</label><button>Crear discusión</button></form></section>
<section class="card"><h3>Crear evaluación</h3><form method="post" action="/admin/authoring/modules/{module_id}/assessments"><label>Título<input name="title" required></label><label>Instrucciones<textarea name="instructions"></textarea></label><label>Puntuación<input type="number" step="0.01" min="0" name="points" value="100"></label><label>Fecha límite<input type="datetime-local" name="due_at"></label><label>Tiempo en minutos<input type="number" min="1" name="time_limit_minutes"></label><label>Intentos<input type="number" min="1" name="attempts" value="1"></label><label>Preguntas en JSON<textarea name="questions_json" placeholder='[{"type":"multiple_choice","prompt":"...","options":["A","B"],"answer":"A"}]'></textarea></label><label><input style="width:auto" type="checkbox" name="published" value="1"> Publicar</label><button>Crear evaluación</button></form></section></div>'''
        return page("Contenido del módulo", body, user)

    @app.post("/admin/authoring/modules/{module_id}/materials")
    async def add_material(module_id: int, request: Request, title: str = Form(...), material_type: str = Form(...), content: str = Form(""), url: str = Form(""), published: str = Form("0")):
        user = require_admin(request, {"course_admin"})
        if material_type not in CONTENT_TYPES:
            raise HTTPException(400, "Tipo de material inválido")
        now = utcnow()
        with db() as conn:
            execute(conn, "INSERT INTO nexus_course_materials (module_id,title,material_type,content,url,published,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", (module_id,title.strip(),material_type,content.strip(),url.strip(),1 if published=="1" else 0,now,now))
            audit(conn,user["email"],"material_created","module",str(module_id),title,request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/modules/{module_id}",303)

    @app.post("/admin/authoring/modules/{module_id}/assignments")
    async def add_assignment(module_id: int, request: Request, title: str = Form(...), instructions: str = Form(""), points: float = Form(100), due_at: str = Form(""), submission_type: str = Form("online_text"), published: str = Form("0")):
        user = require_admin(request,{"course_admin"}); now=utcnow()
        with db() as conn:
            execute(conn,"INSERT INTO nexus_course_assignments (module_id,title,instructions,points,due_at,submission_type,published,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",(module_id,title.strip(),instructions.strip(),points,due_at or None,submission_type,1 if published=="1" else 0,now,now))
            audit(conn,user["email"],"assignment_created","module",str(module_id),title,request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/modules/{module_id}",303)

    @app.post("/admin/authoring/modules/{module_id}/discussions")
    async def add_discussion(module_id: int, request: Request, title: str = Form(...), prompt: str = Form(""), points: float = Form(0), due_at: str = Form(""), published: str = Form("0")):
        user=require_admin(request,{"course_admin"}); now=utcnow()
        with db() as conn:
            execute(conn,"INSERT INTO nexus_course_discussions (module_id,title,prompt,points,due_at,published,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",(module_id,title.strip(),prompt.strip(),points,due_at or None,1 if published=="1" else 0,now,now))
            audit(conn,user["email"],"discussion_created","module",str(module_id),title,request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/modules/{module_id}",303)

    @app.post("/admin/authoring/modules/{module_id}/assessments")
    async def add_assessment(module_id: int, request: Request, title: str = Form(...), instructions: str = Form(""), points: float = Form(100), due_at: str = Form(""), time_limit_minutes: int | None = Form(None), attempts: int = Form(1), questions_json: str = Form("[]"), published: str = Form("0")):
        user=require_admin(request,{"course_admin"}); now=utcnow()
        try:
            questions=json.loads(questions_json or "[]")
            if not isinstance(questions,list): raise ValueError
        except ValueError:
            raise HTTPException(400,"Las preguntas deben ser una lista JSON válida")
        with db() as conn:
            execute(conn,"INSERT INTO nexus_course_assessments (module_id,title,instructions,points,due_at,time_limit_minutes,attempts,question_bank_json,published,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(module_id,title.strip(),instructions.strip(),points,due_at or None,time_limit_minutes,attempts,json.dumps(questions,ensure_ascii=False),1 if published=="1" else 0,now,now))
            audit(conn,user["email"],"assessment_created","module",str(module_id),title,request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/modules/{module_id}",303)
