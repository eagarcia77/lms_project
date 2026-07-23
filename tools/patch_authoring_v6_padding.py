from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "apply_authoring_v6.py"


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    old = "    raw = gzip.decompress(base64.b64decode(PAYLOAD))"
    new = (
        "    encoded_payload = PAYLOAD + ('=' * (-len(PAYLOAD) % 4))\n"
        "    raw = gzip.decompress(base64.b64decode(encoded_payload))"
    )
    if old in source:
        source = source.replace(old, new, 1)
    elif "encoded_payload = PAYLOAD" not in source:
        raise RuntimeError("No se encontró la instrucción Base64 esperada en apply_authoring_v6.py")
    TARGET.write_text(source, encoding="utf-8")
    compile(source, str(TARGET), "exec")
    print("Relleno Base64 de Course Studio V6 corregido.")


if __name__ == "__main__":
    main()
