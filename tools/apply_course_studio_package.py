from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / ".course-studio-v4"
EXPECTED_SHA256 = "fde996ee97927d5a558ac571ffd19742a7a8b73fc6248610e647d4cfcd815d08"


def main() -> None:
    files = sorted(PARTS.glob("part-*"))
    if not files:
        raise RuntimeError("No se encontraron los archivos de Course Studio.")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in files)
    archive = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Paquete Course Studio incompleto: {digest}")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        for member in package.getmembers():
            destination = (ROOT / member.name).resolve()
            if ROOT not in destination.parents and destination != ROOT:
                raise RuntimeError(f"Ruta no permitida: {member.name}")
        package.extractall(ROOT, filter="data")
    print("Course Studio v0.4.0 aplicado correctamente.")


if __name__ == "__main__":
    main()
