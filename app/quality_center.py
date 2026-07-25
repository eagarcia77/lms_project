from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

import app.admin_console as admin_console
from app.admin_authoring_v6 import ensure_schema
from app.admin_console import db, execute, require_admin, rows

ADMIN_ROLES = {"course_admin", "auditor", "support"}
ASSESSMENT_TYPES = {
    "assignment",
    "discussion",
    "quiz",
    "exam",
    "project",
    "presentation",
    "rubric",
    "h5p",
    "simulation",
    "portfolio",
    "ar",
    "vr",
    "360",
}
EMERGING_TYPES = {"h5p", "simulation", "ar", "vr", "360"}


@dataclass
class QualityResult:
    course_id: int
    course_code: str
    title: str
    status: str
    score: int
    level: str
    modules: int
    modules_with_outcomes: int
    modules_with_content: int
    assessments: int
    emerging_activities: int
    total_points: float
    missing_alt_images: int
    issues: list[str]
    recommendations: list[str]


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


def _replace_get_route(app: FastAPI, path: str) -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            str(getattr(route, "path", "")) == path
            and "GET" in set(getattr(route, "methods", set()) or set())
        )
    ]


def _level(score: int) -> str:
    if score >= 90:
        return "Excelente"
    if score >= 75:
        return "Sólido"
    if score >= 60:
        return "En desarrollo"
    return "Requiere atención"


def _drafts(conn: Any, module_ids: list[int]) -> dict[int, str]:
    if not module_ids:
        return {}
    placeholders = ",".join("?" for _ in module_ids)
    try:
        records = rows(
            execute(
                conn,
                f"SELECT module_id,COALESCE(body_html,'') AS body_html FROM nexus_module_drafts WHERE module_id IN ({placeholders})",
                tuple(module_ids),
            )
        )
    except Exception:
        return {}
    return {int(record["module_id"]): str(record.get("body_html") or "") for record in records}


def _items(conn: Any, module_ids: list[int]) -> list[dict[str, Any]]:
    if not module_ids:
        return []
    placeholders = ",".join("?" for _ in module_ids)
    return rows(
        execute(
            conn,
            f"""SELECT id,module_id,item_type,title,COALESCE(body_html,'') AS body_html,
                COALESCE(points,0) AS points,status
                FROM nexus_content_items WHERE module_id IN ({placeholders}) ORDER BY module_id,position,id""",
            tuple(module_ids),
        )
    )


def _quality_for_course(conn: Any, course: dict[str, Any]) -> QualityResult:
    course_id = int(course["id"])
    modules = rows(
        execute(
            conn,
            "SELECT id,title,description,learning_outcomes,status FROM nexus_modules WHERE course_id=? ORDER BY position,id",
            (course_id,),
        )
    )
    module_ids = [int(module["id"]) for module in modules]
    drafts = _drafts(conn, module_ids)
    items = _items(conn, module_ids)

    items_by_module: dict[int, list[dict[str, Any]]] = {module_id: [] for module_id in module_ids}
    for item in items:
        items_by_module.setdefault(int(item["module_id"]), []).append(item)

    outcomes_count = 0
    content_count = 0
    assessments = 0
    emerging = 0
    total_points = 0.0
    missing_alt = 0
    heading_modules = 0

    for module in modules:
        module_id = int(module["id"])
        outcomes = str(module.get("learning_outcomes") or "").strip()
        if outcomes:
            outcomes_count += 1

        draft = drafts.get(module_id, "")
        resource_html = " ".join(str(item.get("body_html") or "") for item in items_by_module.get(module_id, []))
        combined = f"{draft} {resource_html}".strip()
        text_only = re.sub(r"<[^>]+>", " ", combined)
        if len(re.sub(r"\s+", " ", text_only).strip()) >= 80:
            content_count += 1
        if re.search(r"<h[1-4]\b", combined, flags=re.IGNORECASE):
            heading_modules += 1

        for image in re.findall(r"<img\b[^>]*>", combined, flags=re.IGNORECASE):
            if not re.search(r"\balt\s*=", image, flags=re.IGNORECASE):
                missing_alt += 1

        for item in items_by_module.get(module_id, []):
            item_type = str(item.get("item_type") or "").lower()
            if item_type in ASSESSMENT_TYPES:
                assessments += 1
                try:
                    total_points += float(item.get("points") or 0)
                except (TypeError, ValueError):
                    pass
            if item_type in EMERGING_TYPES:
                emerging += 1

    total_modules = len(modules)
    score = 0.0
    issues: list[str] = []
    recommendations: list[str] = []

    if total_modules:
        score += 20
        score += 20 * (outcomes_count / total_modules)
        score += 20 * (content_count / total_modules)
        score += 20 * min(assessments / total_modules, 1)
    else:
        issues.append("El curso no tiene módulos.")
        recommendations.append("Cree al menos un módulo con introducción, objetivos, contenido y evaluación.")

    accessibility_score = 10.0
    if missing_alt:
        accessibility_score -= 5
        issues.append(f"Se detectaron {missing_alt} imágenes sin atributo alternativo.")
        recommendations.append("Añada texto alternativo significativo o alt vacío para imágenes decorativas.")
    if total_modules and heading_modules < content_count:
        accessibility_score -= 5
        issues.append("Parte del contenido no utiliza encabezados estructurados.")
        recommendations.append("Organice el contenido con H2 y H3 en una jerarquía lógica.")
    score += max(0, accessibility_score)

    status = str(course.get("status") or "draft")
    score += 5 if status == "active" else 2 if status == "draft" else 3
    score += 5 if emerging else 0

    if total_modules and outcomes_count < total_modules:
        missing = total_modules - outcomes_count
        issues.append(f"{missing} módulos no tienen resultados de aprendizaje.")
        recommendations.append("Redacte resultados medibles alineados con actividades y criterios de evaluación.")
    if total_modules and content_count < total_modules:
        missing = total_modules - content_count
        issues.append(f"{missing} módulos tienen contenido insuficiente o vacío.")
        recommendations.append("Complete cada módulo con introducción, desarrollo, ejemplos y cierre.")
    if total_modules and assessments < total_modules:
        issues.append("No todos los módulos tienen una actividad evaluativa identificable.")
        recommendations.append("Añada al menos una evaluación formativa o sumativa por módulo.")
    if assessments and total_points <= 0:
        issues.append("Las actividades evaluativas no tienen puntuación configurada.")
        recommendations.append("Defina puntuaciones y criterios mediante rúbricas transparentes.")
    if not emerging:
        recommendations.append("Considere incorporar H5P, simulaciones, RA, VR o contenido 360 cuando aporte valor pedagógico.")
    if not issues:
        recommendations.append("Mantenga la revisión periódica de accesibilidad, alineación y vigencia de los recursos.")

    final_score = max(0, min(100, round(score)))
    return QualityResult(
        course_id=course_id,
        course_code=str(course.get("course_code") or ""),
        title=str(course.get("title") or ""),
        status=status,
        score=final_score,
        level=_level(final_score),
        modules=total_modules,
        modules_with_outcomes=outcomes_count,
        modules_with_content=content_count,
        assessments=assessments,
        emerging_activities=emerging,
        total_points=round(total_points, 2),
        missing_alt_images=missing_alt,
        issues=issues,
        recommendations=recommendations,
    )


def _all_results(conn: Any) -> list[QualityResult]:
    courses = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE status<>'archived' ORDER BY updated_at DESC,id DESC"))
    return [_quality_for_course(conn, course) for course in courses]


def register_quality_center(app: FastAPI) -> None:
    ensure_schema()
    for path in ("/admin/quality", "/admin/quality/report.json", "/admin/quality/courses/{course_id}"):
        _replace_get_route(app, path)

    @app.get("/admin/quality", response_class=HTMLResponse, response_model=None)
    async def quality_dashboard(request: Request):
        user = require_admin(request, ADMIN_ROLES)
        with db() as conn:
            results = _all_results(conn)

        average = round(sum(result.score for result in results) / len(results)) if results else 0
        attention = sum(result.score < 60 for result in results)
        solid = sum(result.score >= 75 for result in results)
        rows_html = "".join(
            f'''<tr><td><strong>{_escape(result.course_code)}</strong><br>{_escape(result.title)}</td>
            <td><span class="badge">{result.score}/100 · {_escape(result.level)}</span></td>
            <td>{result.modules}</td><td>{result.assessments}</td><td>{result.emerging_activities}</td>
            <td>{_escape(result.issues[0] if result.issues else "Sin hallazgos críticos")}</td>
            <td><a class="button" href="/admin/quality/courses/{result.course_id}">Revisar</a>
            <a class="button secondary" href="/admin/authoring/courses/{result.course_id}">Corregir</a></td></tr>'''
            for result in results
        ) or '<tr><td colspan="7">No hay cursos para evaluar.</td></tr>'

        body = f'''
        <h2>Centro de Calidad Académica</h2>
        <p>Evalúa automáticamente estructura, contenido, alineación, accesibilidad y uso pertinente de tecnologías emergentes. La puntuación es diagnóstica y no sustituye la revisión académica institucional.</p>
        <div class="grid">
          <div class="card metric"><strong>{len(results)}</strong>Cursos revisados</div>
          <div class="card metric"><strong>{average}</strong>Promedio de calidad</div>
          <div class="card metric"><strong>{solid}</strong>Cursos sólidos o excelentes</div>
          <div class="card metric"><strong>{attention}</strong>Cursos que requieren atención</div>
        </div>
        <p><a class="button" href="/admin/quality/report.json">Descargar informe JSON</a><a class="button secondary" href="/admin/authoring">Abrir Course Studio</a></p>
        <section class="card"><table><thead><tr><th>Curso</th><th>Calidad</th><th>Módulos</th><th>Evaluaciones</th><th>Emergentes</th><th>Hallazgo principal</th><th>Acciones</th></tr></thead><tbody>{rows_html}</tbody></table></section>
        '''
        return admin_console.page("Calidad académica", body, user)

    @app.get("/admin/quality/courses/{course_id}", response_class=HTMLResponse, response_model=None)
    async def quality_course(course_id: int, request: Request):
        user = require_admin(request, ADMIN_ROLES)
        with db() as conn:
            found = rows(execute(conn, "SELECT * FROM nexus_admin_courses WHERE id=?", (course_id,)))
            if not found:
                raise HTTPException(404, "Curso no encontrado.")
            result = _quality_for_course(conn, found[0])
            modules = rows(execute(conn, "SELECT id,title,learning_outcomes,status FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            drafts = _drafts(conn, [int(module["id"]) for module in modules])
            all_items = _items(conn, [int(module["id"]) for module in modules])

        item_counts: dict[int, int] = {}
        for item in all_items:
            module_id = int(item["module_id"])
            item_counts[module_id] = item_counts.get(module_id, 0) + 1
        module_rows = "".join(
            f'''<tr><td><strong>{_escape(module["title"])}</strong></td>
            <td>{"Sí" if str(module.get("learning_outcomes") or "").strip() else "No"}</td>
            <td>{len(re.sub(r"<[^>]+>", " ", drafts.get(int(module["id"]), "")).strip())} caracteres</td>
            <td>{item_counts.get(int(module["id"]), 0)}</td>
            <td><a href="/admin/authoring/modules/{module["id"]}">Abrir módulo</a></td></tr>'''
            for module in modules
        ) or '<tr><td colspan="5">El curso no tiene módulos.</td></tr>'
        issue_list = "".join(f"<li>{_escape(issue)}</li>" for issue in result.issues) or "<li>No se detectaron hallazgos críticos.</li>"
        recommendation_list = "".join(f"<li>{_escape(item)}</li>" for item in result.recommendations)
        body = f'''
        <p><a href="/admin/quality">&larr; Volver al Centro de Calidad</a></p>
        <h2>{_escape(result.course_code)} · {_escape(result.title)}</h2>
        <div class="grid">
          <div class="card metric"><strong>{result.score}/100</strong>{_escape(result.level)}</div>
          <div class="card metric"><strong>{result.modules_with_outcomes}/{result.modules}</strong>Módulos con resultados</div>
          <div class="card metric"><strong>{result.modules_with_content}/{result.modules}</strong>Módulos con contenido</div>
          <div class="card metric"><strong>{result.assessments}</strong>Actividades evaluativas</div>
          <div class="card metric"><strong>{result.total_points:g}</strong>Puntos configurados</div>
          <div class="card metric"><strong>{result.emerging_activities}</strong>Actividades emergentes</div>
        </div>
        <div class="grid"><section class="card"><h3>Hallazgos</h3><ul>{issue_list}</ul></section><section class="card"><h3>Recomendaciones</h3><ul>{recommendation_list}</ul></section></div>
        <p><a class="button secondary" href="/admin/authoring/courses/{course_id}">Editar curso</a><a class="button" href="/admin/authoring/innovation/courses/{course_id}">IA/XR</a></p>
        <section class="card"><h3>Revisión por módulo</h3><table><thead><tr><th>Módulo</th><th>Resultados</th><th>Contenido</th><th>Recursos y evaluaciones</th><th>Acción</th></tr></thead><tbody>{module_rows}</tbody></table></section>
        '''
        return admin_console.page("Informe de calidad", body, user)

    @app.get("/admin/quality/report.json", response_model=None)
    async def quality_report(request: Request):
        require_admin(request, ADMIN_ROLES)
        with db() as conn:
            results = _all_results(conn)
        payload = {
            "format": "NEXUS-QUALITY-1.0",
            "summary": {
                "courses": len(results),
                "average_score": round(sum(result.score for result in results) / len(results), 2) if results else 0,
                "requires_attention": sum(result.score < 60 for result in results),
            },
            "courses": [asdict(result) for result in results],
        }
        return JSONResponse(payload, headers={"Content-Disposition": "attachment; filename=nexus-quality-report.json"})

    print("Centro de Calidad Académica registrado.", flush=True)
