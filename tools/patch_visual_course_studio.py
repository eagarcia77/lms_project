from __future__ import annotations

from pathlib import Path

PATH = Path("app/course_editor_access.py")
TAG = "NUVEDRA_VISUAL_STUDIO_PREVIEW_V1"

PREVIEW_ROUTES = r'''

    # NUVEDRA_VISUAL_STUDIO_PREVIEW_V1
    @app.get(f"{STUDIO_PREFIX}/courses/{{course_id}}/preview", response_class=HTMLResponse, response_model=None)
    async def instructor_course_preview(course_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/courses/{course_id}/preview")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            course = _course_access(conn, course_id, user)
            modules = rows(execute(conn, "SELECT * FROM nexus_modules WHERE course_id=? ORDER BY position,id", (course_id,)))
            sections: list[str] = []
            for module in modules:
                items = rows(execute(conn, "SELECT * FROM nexus_content_items WHERE module_id=? ORDER BY position,id", (int(module["id"]),)))
                item_links = "".join(
                    f'<li><a href="{STUDIO_PREFIX}/items/{int(item["id"])}/preview">{_esc(item["title"])}</a> '
                    f'<span class="studio-status studio-status--{_esc(item.get("status") or "draft", attr=True)}">{_esc(item.get("status") or "draft")}</span></li>'
                    for item in items
                ) or '<li data-i18n-en="No content yet" data-i18n-es="Todavía no hay contenido">No content yet</li>'
                sections.append(
                    f'<section class="studio-panel"><p class="studio-eyebrow">{int(module.get("position") or 1)} · {_esc(module.get("status") or "draft")}</p>'
                    f'<h2>{_esc(module["title"])}</h2><p>{_esc(module.get("description"))}</p><ol>{item_links}</ol></section>'
                )
        body = f'''
        <main class="studio-shell" data-testid="instructor-course-preview" data-studio-root>
          <nav class="studio-breadcrumbs"><a href="{STUDIO_PREFIX}/courses/{course_id}" data-i18n-en="Back to editor" data-i18n-es="Volver al editor">Back to editor</a></nav>
          <header class="studio-hero"><div><p class="studio-eyebrow" data-i18n-en="Instructor preview" data-i18n-es="Vista previa del instructor">Instructor preview</p><h2>{_esc(course['course_code'])}: {_esc(course['title'])}</h2><p data-i18n-en="This preview includes drafts and hidden items so the instructor can review the complete structure." data-i18n-es="Esta vista incluye borradores y elementos ocultos para que el instructor revise la estructura completa.">This preview includes drafts and hidden items so the instructor can review the complete structure.</p></div></header>
          <section class="studio-section">{"".join(sections) or '<section class="studio-empty">No modules yet.</section>'}</section>
        </main>
        '''
        return _studio_page("Instructor preview", body, user)

    @app.get(f"{STUDIO_PREFIX}/items/{{item_id}}/preview", response_class=HTMLResponse, response_model=None)
    async def instructor_item_preview(item_id: int, request: Request):
        user = _author(request, f"{STUDIO_PREFIX}/items/{item_id}/preview")
        if isinstance(user, RedirectResponse):
            return user
        with db() as conn:
            course_id, item, module = academic_access.item_bundle(conn, item_id)
            course = _course_access(conn, course_id, user)
        external = (
            f'<p><a class="studio-button studio-button--quiet" href="{_esc(item.get("external_url"), attr=True)}" target="_blank" rel="noopener" data-i18n-en="Open resource" data-i18n-es="Abrir recurso">Open resource</a></p>'
            if item.get("external_url") else ""
        )
        embed = (
            f'<iframe src="{_esc(item.get("embed_url"), attr=True)}" title="{_esc(item.get("title"), attr=True)}" allow="fullscreen; xr-spatial-tracking" style="width:100%;min-height:520px;border:1px solid var(--studio-line);border-radius:16px"></iframe>'
            if item.get("embed_url") else ""
        )
        body = f'''
        <main class="studio-shell" data-testid="instructor-item-preview" data-studio-root>
          <nav class="studio-breadcrumbs"><a href="{STUDIO_PREFIX}/modules/{int(module['id'])}" data-i18n-en="Back to module" data-i18n-es="Volver al módulo">Back to module</a><span>/</span><strong>{_esc(item['title'])}</strong></nav>
          <header class="studio-hero studio-hero--module"><div><p class="studio-eyebrow" data-i18n-en="Instructor preview" data-i18n-es="Vista previa del instructor">Instructor preview</p><h2>{_esc(item['title'])}</h2><p>{_esc(course['course_code'])} · {_esc(module['title'])} · {_esc(item.get('status') or 'draft')}</p></div><div class="studio-actions"><a class="studio-button studio-button--quiet" href="{STUDIO_PREFIX}/items/{item_id}/edit" data-i18n-en="Edit content" data-i18n-es="Editar contenido">Edit content</a></div></header>
          <article class="studio-panel content-body">{sanitize_html(str(item.get('body_html') or ''))}{external}{embed}</article>
        </main>
        '''
        return _studio_page("Content preview", body, user)
'''


def replace_required(text: str, old: str, new: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f"Visual Studio patch marker was not found: {old[:100]!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    text = replace_required(
        text,
        'due_at=due_at.strip() or None, status="draft")',
        'due_at=due_at.strip(), status="draft")',
    )
    text = replace_required(
        text,
        'due_at=item.get("due_at"), status="draft")',
        'due_at=str(item.get("due_at") or ""), status="draft")',
    )
    text = replace_required(
        text,
        'due_at=source.get("due_at"), status="draft")',
        'due_at=str(source.get("due_at") or ""), status="draft")',
    )
    text = text.replace(
        'href="{PREFIX}/items/{item_id}/preview"',
        'href="{STUDIO_PREFIX}/items/{item_id}/preview"',
    )
    text = text.replace(
        'href="/learn/courses/{course_id}"',
        'href="{STUDIO_PREFIX}/courses/{course_id}/preview"',
    )

    if TAG not in text:
        marker = '    @app.get(f"{STUDIO_PREFIX}/items/{{item_id}}/edit", response_class=HTMLResponse, response_model=None)\n'
        if marker not in text:
            raise RuntimeError("Could not insert instructor preview routes.")
        text = text.replace(marker, PREVIEW_ROUTES + "\n" + marker, 1)

    PATH.write_text(text, encoding="utf-8")
    print("NUVEDRA Visual Course Studio hardened: nullable due dates and instructor-safe previews.", flush=True)


if __name__ == "__main__":
    main()
