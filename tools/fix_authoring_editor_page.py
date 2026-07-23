from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_authoring.py"


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    pattern = re.compile(
        r'''    @app\.get\("/admin/authoring/modules/\{module_id\}/items/new", response_class=HTMLResponse\)\n'''
        r'''    async def new_item\(module_id: int, request: Request\):\n.*?'''
        r'''(?=    @app\.post\("/admin/authoring/modules/\{module_id\}/items"\))''',
        re.DOTALL,
    )

    replacement = """    @app.get(\"/admin/authoring/modules/{module_id}/items/new\", response_class=HTMLResponse)
    async def new_item(module_id: int, request: Request):
        user = require_admin(request, {\"course_admin\"})
        try:
            with db() as conn:
                module = _module(conn, module_id)
                course = _course(conn, int(module[\"course_id\"]))
                count_rows = rows(execute(conn, \"SELECT COUNT(*) AS total FROM nexus_content_items WHERE module_id=?\", (module_id,)))
                item_count = int(count_rows[0].get(\"total\", 0) or 0) if count_rows else 0

            options = \"\".join(
                f'<option value=\"{html.escape(kind)}\">{html.escape(kind.replace(\"_\", \" \u200b\").replace(\"\u200b\", \"\").title())}</option>'
                for kind in sorted(CONTENT_TYPES)
            )
            course_id = int(course[\"id\"])
            module_title = html.escape(str(module.get(\"title\") or \"Módulo\"))
            next_position = item_count + 1

            body = f'''<p><a href=\"/admin/authoring/courses/{course_id}\">&larr; Volver al curso</a></p>
            <h2>Añadir contenido a {module_title}</h2>
            <section class=\"card\">
              <form method=\"post\" action=\"/admin/authoring/modules/{module_id}/items\" data-editor onsubmit=\"syncEditor()\">
                <label>Tipo de contenido<select name=\"item_type\" required>{options}</select></label>
                <label>Título<input name=\"title\" maxlength=\"250\" required></label>
                <label>Contenido</label>
                <div class=\"toolbar\">
                  <button type=\"button\" onclick=\"cmd('bold')\">Negrita</button>
                  <button type=\"button\" onclick=\"cmd('italic')\">Cursiva</button>
                  <button type=\"button\" onclick=\"cmd('insertUnorderedList')\">Lista</button>
                  <button type=\"button\" onclick=\"cmd('formatBlock','h2')\">Encabezado</button>
                  <button type=\"button\" onclick=\"insertLink()\">Enlace</button>
                  <button type=\"button\" onclick=\"insertImage()\">Imagen</button>
                </div>
                <div id=\"editor\" contenteditable=\"true\" role=\"textbox\" aria-multiline=\"true\" class=\"rich-editor\"><p>Escriba aquí el contenido instruccional.</p></div>
                <textarea id=\"body_html\" name=\"body_html\" hidden></textarea>
                <label>Enlace externo<input type=\"url\" name=\"external_url\" placeholder=\"https://...\"></label>
                <label>URL para incrustar<input type=\"url\" id=\"embed_url\" name=\"embed_url\" placeholder=\"https://...\"></label>
                <div class=\"grid\">
                  <label>Puntos<input type=\"number\" min=\"0\" step=\"0.01\" name=\"points\"></label>
                  <label>Fecha límite<input type=\"datetime-local\" name=\"due_at\"></label>
                  <label>Posición<input type=\"number\" name=\"position\" min=\"1\" value=\"{next_position}\"></label>
                  <label>Estado<select name=\"status\"><option value=\"draft\">Borrador</option><option value=\"published\">Publicado</option><option value=\"hidden\">Oculto</option></select></label>
                </div>
                <label>Configuración adicional JSON (opcional)<textarea name=\"metadata_json\" placeholder='{{\"attempts\": 2}}'></textarea></label>
                <button type=\"submit\">Guardar contenido</button>
              </form>
            </section>
            <section class=\"card\"><h3>Herramientas gratuitas</h3><div class=\"grid\">{_tool_cards()}</div></section>
            <style>.toolbar{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}}.toolbar button{{margin:0;padding:8px}}.rich-editor{{min-height:280px;background:#fff;border:1px solid #8093a7;border-radius:8px;padding:16px}}</style>
            {_editor_script()}'''
            return page(\"Añadir contenido\", body, user)
        except HTTPException:
            raise
        except Exception as exc:
            print(f\"ERROR al abrir editor de contenido para módulo {module_id}: {type(exc).__name__}: {exc}\")
            error_body = f'''<section class=\"card\"><h2>No se pudo abrir el editor</h2>
            <p class=\"error\">Ocurrió un error al preparar el formulario de contenido.</p>
            <p>Identificador del módulo: {module_id}</p>
            <p><a class=\"button\" href=\"/admin/authoring\">Volver al diseñador</a></p></section>'''
            return page(\"Error del editor\", error_body, user)

"""

    updated, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise RuntimeError("No se encontró exactamente una ruta new_item para reemplazar.")

    TARGET.write_text(updated, encoding="utf-8")
    print("Pantalla Añadir contenido reemplazada por una versión robusta.")


if __name__ == "__main__":
    main()
