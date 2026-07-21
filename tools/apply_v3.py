from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / ".source-v3"
EXPECTED_SHA256 = "7a7839dee4841c4e2a3e83a34c5f54a229c8de75c5baefc93efc2ec72883de33"


def main() -> None:
    files = sorted(PARTS.glob("part-*"))
    if not files:
        raise RuntimeError("No se encontraron los archivos de NEXUS EDU XR v0.3.0.")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in files)
    archive = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Paquete NEXUS EDU XR incompleto: {digest}")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        for member in package.getmembers():
            destination = (ROOT / member.name).resolve()
            if ROOT not in destination.parents and destination != ROOT:
                raise RuntimeError(f"Ruta no permitida: {member.name}")
        package.extractall(ROOT, filter="data")
    print("NEXUS EDU XR v0.3.0 aplicado correctamente.")


if __name__ == "__main__":
    main()
