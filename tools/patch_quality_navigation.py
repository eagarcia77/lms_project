from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_portal.py"
NAV_MARKER = '("/admin/quality", "Calidad académica"'
CARD_MARKER = "NEXUS_QUALITY_CENTER_CARD"


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    changes = 0

    if NAV_MARKER not in source:
        role_aware = re.compile(
            r'(?m)^(?P<indent>\s*)\("/admin/authoring/innovation",\s*"Innovación IA/XR",\s*"[^"]+",\s*\{"superadmin",\s*"course_admin"\}\),\s*$'
        )
        match = role_aware.search(source)
        if match:
            indent = match.group("indent")
            addition = (
                match.group(0)
                + "\n"
                + indent
                + '("/admin/quality", "Calidad académica", "Accesibilidad, alineación y mejora continua", {"superadmin", "course_admin", "support", "auditor"}),' 
            )
            source = source[: match.start()] + addition + source[match.end() :]
            changes += 1
        else:
            basic = re.compile(
                r'(?m)^(?P<indent>\s*)\("/admin/authoring/innovation",\s*"Innovación IA/XR",\s*"[^"]+"\),\s*$'
            )
            match = basic.search(source)
            if not match:
                raise RuntimeError("No se encontró un punto seguro para integrar Calidad académica en la navegación.")
            indent = match.group("indent")
            addition = match.group(0) + "\n" + indent + '("/admin/quality", "Calidad académica", "Accesibilidad, alineación y mejora continua"),'
            source = source[: match.start()] + addition + source[match.end() :]
            changes += 1

    if CARD_MARKER not in source:
        innovation_card = re.compile(
            r'(?P<card><section class="card"><h3>IA y experiencias inmersivas</h3>.*?</section>)',
            re.DOTALL,
        )
        match = innovation_card.search(source)
        if match:
            quality_card = '''
          <!-- NEXUS_QUALITY_CENTER_CARD -->
          <section class="card"><h3>Calidad académica</h3><p>Revise accesibilidad, objetivos, contenido, evaluación y tecnologías emergentes con recomendaciones automáticas.</p><a class="button secondary" href="/admin/quality">Abrir Centro de Calidad</a></section>'''
            source = source[: match.end()] + quality_card + source[match.end() :]
            changes += 1

    TARGET.write_text(source, encoding="utf-8")
    compile(source, str(TARGET), "exec")

    verified = TARGET.read_text(encoding="utf-8")
    required = ("/admin/quality", "Calidad académica", "Accesibilidad, alineación y mejora continua")
    missing = [marker for marker in required if marker not in verified]
    if missing:
        raise RuntimeError(f"Integración del Centro de Calidad incompleta: {missing}")
    print(f"Centro de Calidad integrado en el portal; cambios: {changes}.", flush=True)


if __name__ == "__main__":
    main()
