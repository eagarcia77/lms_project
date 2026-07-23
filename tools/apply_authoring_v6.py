from __future__ import annotations

import base64
import gzip
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "admin_authoring_v6.py"
ENTRY = ROOT / "app" / "runtime_entry.py"
GOOGLE_API = ROOT / "app" / "google_api.py"
ADMIN_CONSOLE = ROOT / "app" / "admin_console.py"
EXPECTED_SHA256 = "584ad35e121c993b33f363c352f6e14393ff131cb7e63ed6a59af32fb2f7f2f3"
PAYLOAD = (
    "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"
)


def _patch_runtime() -> None:
    source = ENTRY.read_text(encoding="utf-8")
    source = re.sub(
        r"\n# NEXUS_AUTHORING_STUDIO_V[2-6]\nfrom app\.[^\n]+\nregister_[^\n]+\n?",
        "\n",
        source,
    )
    source = source.rstrip() + (
        "\n\n# NEXUS_AUTHORING_STUDIO_V6\n"
        "from app.admin_authoring_v6 import register_authoring_v6\n"
        "register_authoring_v6(app)\n"
    )
    ENTRY.write_text(source, encoding="utf-8")


def _patch_google_scopes() -> None:
    source = GOOGLE_API.read_text(encoding="utf-8")
    scopes = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/presentations",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    anchor = '    "https://www.googleapis.com/auth/calendar.events",'
    additions = "\n".join(f'    "{scope}",' for scope in scopes if scope not in source)
    if additions:
        source = source.replace(anchor, anchor + "\n" + additions)
    GOOGLE_API.write_text(source, encoding="utf-8")


def _patch_navigation() -> None:
    source = ADMIN_CONSOLE.read_text(encoding="utf-8")
    needle = '<a href="/admin/courses">Cursos</a>'
    addition = needle + '<a href="/admin/authoring">Course Studio</a>'
    if addition not in source:
        source = source.replace(needle, addition)
    ADMIN_CONSOLE.write_text(source, encoding="utf-8")


def main() -> None:
    raw = gzip.decompress(base64.b64decode(PAYLOAD))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Course Studio V6 incompleto: {digest}")
    TARGET.write_bytes(raw)
    _patch_runtime()
    _patch_google_scopes()
    _patch_navigation()
    compile(TARGET.read_text(encoding="utf-8"), str(TARGET), "exec")
    print("NEXUS Course Studio V6 aplicado correctamente.")


if __name__ == "__main__":
    main()
