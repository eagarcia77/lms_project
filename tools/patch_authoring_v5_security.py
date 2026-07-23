from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_authoring_v4.py"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"No se encontró el bloque para {label}")
    return source.replace(old, new, 1)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if "import bleach\n" not in source:
        source = replace_once(source, "import httpx\n", "import bleach\nimport httpx\n", "importar bleach")

    safe_url_block = '''def safe_url(value: str) -> str:\n    value = value.strip()\n    if not value:\n        return ""\n    parsed = urlparse(value)\n    if parsed.scheme not in {"https", "http"}:\n        raise HTTPException(400, "Solo se permiten direcciones http o https")\n    return value\n\n\n'''
    sanitize_block = safe_url_block + '''def sanitize_html(value: str) -> str:\n    return bleach.clean(\n        value,\n        tags={"p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "h1", "h2", "h3", "h4", "blockquote", "a", "img", "code", "pre", "table", "thead", "tbody", "tr", "th", "td"},\n        attributes={"a": ["href", "title", "target", "rel"], "img": ["src", "alt", "title"], "th": ["scope"], "td": ["colspan", "rowspan"]},\n        protocols={"http", "https", "mailto"},\n        strip=True,\n    )\n\n\n'''
    if "def sanitize_html(" not in source:
        source = replace_once(source, safe_url_block, sanitize_block, "sanitizar HTML")

    source = source.replace(
        "_insert_item(conn, module_id, item_type, title, body_html, safe_url(external_url)",
        "_insert_item(conn, module_id, item_type, title, sanitize_html(body_html), safe_url(external_url)",
        1,
    )

    old_forms = '''                created = await _grequest(request, "POST", "https://forms.googleapis.com/v1/forms", {"info":{"title":title,"documentTitle":title}}); form_id = str(created["formId"]); url = f"https://docs.google.com/forms/d/{form_id}/edit"\n                if kind == "quiz":\n                    await _grequest(request, "POST", f"https://forms.googleapis.com/v1/forms/{form_id}:batchUpdate", {"requests":[{"updateSettings":{"settings":{"quizSettings":{"isQuiz":True}},"updateMask":"quizSettings.isQuiz"}},{"createItem":{"item":{"title":"Pregunta 1","questionItem":{"question":{"required":True,"textQuestion":{}}}},"location":{"index":0}}}]})\n                await _grequest(request, "PATCH", f"https://www.googleapis.com/drive/v3/files/{form_id}", {}, {"addParents":folder,"fields":"id,parents"})\n                _insert_item(conn, module_id, "assessment", title, external_url=url, metadata={"provider":"Google Forms","external_id":form_id,"quiz":kind=="quiz"})\n'''
    new_forms = '''                created = await _grequest(request, "POST", "https://forms.googleapis.com/v1/forms", {"info": {"title": title}})\n                form_id = str(created["formId"])\n                edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"\n                if kind == "quiz":\n                    await _grequest(request, "POST", f"https://forms.googleapis.com/v1/forms/{form_id}:batchUpdate", {"requests":[{"updateSettings":{"settings":{"quizSettings":{"isQuiz":True}},"updateMask":"quizSettings.isQuiz"}},{"createItem":{"item":{"title":"Pregunta 1","questionItem":{"question":{"required":True,"textQuestion":{}}}},"location":{"index":0}}}]})\n                await _grequest(request, "POST", f"https://forms.googleapis.com/v1/forms/{form_id}:setPublishSettings", {"publishSettings": {"publishState": {"isPublished": True, "isAcceptingResponses": True}}})\n                await _grequest(request, "PATCH", f"https://www.googleapis.com/drive/v3/files/{form_id}", {}, {"addParents":folder,"fields":"id,parents"})\n                responder_url = str(created.get("responderUri") or edit_url)\n                _insert_item(conn, module_id, "assessment", title, external_url=responder_url, metadata={"provider":"Google Forms","external_id":form_id,"quiz":kind=="quiz","edit_url":edit_url,"published":True})\n'''
    if ":setPublishSettings" not in source:
        source = replace_once(source, old_forms, new_forms, "publicar Google Forms")

    old_preview = '''        title = html.escape(str(item.get("title") or "Contenido")); link = f'<p><a href="{html.escape(str(item.get("external_url")), quote=True)}" target="_blank" rel="noopener">Abrir recurso externo</a></p>' if item.get("external_url") else ""; embed = f'<iframe src="{html.escape(str(item.get("embed_url")), quote=True)}" title="Recurso" style="width:100%;min-height:600px;border:0"></iframe>' if item.get("embed_url") else ""\n'''
    new_preview = '''        title = html.escape(str(item.get("title") or "Contenido"))\n        link = f'<p><a href="{html.escape(str(item.get("external_url")), quote=True)}" target="_blank" rel="noopener">Abrir recurso</a></p>' if item.get("external_url") else ""\n        edit_link = f'<p><a href="{html.escape(str(metadata.get("edit_url")), quote=True)}" target="_blank" rel="noopener">Editar recurso</a></p>' if metadata.get("edit_url") else ""\n        embed = f'<iframe src="{html.escape(str(item.get("embed_url")), quote=True)}" title="Recurso" style="width:100%;min-height:600px;border:0"></iframe>' if item.get("embed_url") else ""\n'''
    if "edit_link =" not in source:
        source = replace_once(source, old_preview, new_preview, "enlace de edición")
        source = replace_once(source, "{link}{embed}{immersive}</body></html>", "{link}{edit_link}{embed}{immersive}</body></html>", "mostrar enlace de edición")

    compile(source, str(TARGET), "exec")
    TARGET.write_text(source, encoding="utf-8")
    print("Course Studio V5 reforzado: HTML sanitizado y Google Forms publicado.")


if __name__ == "__main__":
    main()
