from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_authoring.py"


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    old_signature = '''    async def create_item(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), metadata_json: str = Form(""), points: float | None = Form(None), due_at: str = Form(""), position: int = Form(1), status: str = Form("draft")):'''
    new_signature = '''    async def create_item(module_id: int, request: Request, item_type: str = Form(...), title: str = Form(...), body_html: str = Form(""), external_url: str = Form(""), embed_url: str = Form(""), metadata_json: str = Form(""), points: str = Form(""), due_at: str = Form(""), position: int = Form(1), status: str = Form("draft")):'''
    if old_signature in source:
        source = source.replace(old_signature, new_signature)

    old_block = '''        metadata = {}
        if metadata_json.strip():
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(400, "La configuración adicional debe ser JSON válido") from exc
        with db() as conn:
            module = _module(conn, module_id)
            execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (module_id, item_type, title.strip(), sanitize_rich_html(body_html), external_url.strip(), embed_url.strip(), json.dumps(metadata, ensure_ascii=False), points, due_at or None, max(position,1), status, utcnow(), utcnow()))
            audit(conn, user["email"], "content_created", "module", str(module_id), f"{item_type}: {title}", request.client.host if request.client else "")
        return RedirectResponse(f"/admin/authoring/courses/{module['course_id']}", status_code=303)'''

    new_block = '''        clean_title = title.strip()
        if not clean_title:
            raise HTTPException(400, "El título del contenido es obligatorio")

        metadata = {}
        if metadata_json.strip():
            try:
                metadata = json.loads(metadata_json)
                if not isinstance(metadata, dict):
                    raise ValueError("metadata must be an object")
            except (json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(400, "La configuración adicional debe ser un objeto JSON válido") from exc

        points_value = None
        if points.strip():
            try:
                points_value = float(points.replace(",", "."))
            except ValueError as exc:
                raise HTTPException(400, "La puntuación debe ser un número válido") from exc
            if points_value < 0:
                raise HTTPException(400, "La puntuación no puede ser negativa")

        clean_external_url = external_url.strip() or None
        clean_embed_url = embed_url.strip() or None
        clean_due_at = due_at.strip() or None
        clean_body = sanitize_rich_html(body_html)

        try:
            with db() as conn:
                module = _module(conn, module_id)
                execute(conn, "INSERT INTO nexus_content_items (module_id,item_type,title,body_html,external_url,embed_url,metadata_json,points,due_at,position,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (module_id, item_type, clean_title, clean_body, clean_external_url, clean_embed_url, json.dumps(metadata, ensure_ascii=False), points_value, clean_due_at, max(position,1), status, utcnow(), utcnow()))
                audit(conn, user["email"], "content_created", "module", str(module_id), f"{item_type}: {clean_title}", request.client.host if request.client else "")
        except HTTPException:
            raise
        except Exception as exc:
            print(f"ERROR al guardar contenido en módulo {module_id}: {type(exc).__name__}: {exc}")
            raise HTTPException(500, "No se pudo guardar el contenido. Verifique los campos e inténtelo nuevamente.") from exc

        return RedirectResponse(f"/admin/authoring/courses/{module['course_id']}", status_code=303)'''

    if old_block not in source:
        raise RuntimeError("No se encontró el bloque de creación de contenido para corregir.")
    source = source.replace(old_block, new_block)

    TARGET.write_text(source, encoding="utf-8")
    print("Guardado de contenido del Course Studio corregido.")


if __name__ == "__main__":
    main()
