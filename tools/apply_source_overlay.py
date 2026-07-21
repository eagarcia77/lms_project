from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / ".source-overlay"
EXPECTED_SHA256 = "b816c2aff5cf392015d763d3b7c76905c0a681ce3c1edabe5bf86b1a7edb0e6b"


def main() -> None:
    files = sorted(PARTS.glob("part-*"))
    if not files:
        raise RuntimeError("No se encontraron las partes del código de autenticación.")

    encoded = "".join(path.read_text(encoding="ascii").strip() for path in files)
    archive = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"El código de autenticación está incompleto: {digest}")

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        for member in package.getmembers():
            destination = (ROOT / member.name).resolve()
            if ROOT not in destination.parents and destination != ROOT:
                raise RuntimeError(f"Ruta no permitida en el paquete: {member.name}")
        package.extractall(ROOT, filter="data")

    old_public_page = ROOT / "app" / "static" / "index.html"
    old_public_page.unlink(missing_ok=True)
    print("Código de autenticación NEXUS EDU XR aplicado correctamente.")


if __name__ == "__main__":
    main()
