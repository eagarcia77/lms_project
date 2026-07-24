from __future__ import annotations

import importlib
import sys

REQUIRED_IMPORTS = {
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "httpx": "HTTPX",
    "multipart": "python-multipart",
    "itsdangerous": "itsdangerous",
    "psycopg": "psycopg",
    "cryptography": "cryptography",
    "bleach": "bleach",
    "odf": "odfpy",
}


def main() -> None:
    missing: list[str] = []
    for module_name, package_name in REQUIRED_IMPORTS.items():
        try:
            importlib.import_module(module_name)
            print(f"Dependencia disponible: {package_name}", flush=True)
        except Exception as exc:
            missing.append(f"{package_name} ({exc})")
    if missing:
        print("Dependencias ausentes:", flush=True)
        for item in missing:
            print(f"  - {item}", flush=True)
        raise SystemExit(1)
    print(f"Dependencias de producción verificadas con Python {sys.version.split()[0]}.", flush=True)


if __name__ == "__main__":
    main()
