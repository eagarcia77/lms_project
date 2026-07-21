# NEXUS EDU XR

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eagarcia77/lms_project)

**Repositorio:** https://github.com/eagarcia77/lms_project  
**Aplicación:** https://nexus-edu-xr-eagarcia77.onrender.com

Plataforma de educación en línea inspirada en Blackboard Ultra, integrada con Google Workspace y preparada para realidad virtual, realidad aumentada y contenido 3D.

## Acceso obligatorio

Los cursos, el panel académico, Google Hub y los laboratorios XR requieren una sesión válida. El usuario puede:

- entrar con su cuenta de Google;
- crear una cuenta NEXUS con nombre, correo y contraseña;
- iniciar sesión posteriormente con su cuenta local;
- conectar o desconectar Google Workspace desde la plataforma;
- cerrar completamente su sesión.

Las contraseñas locales se almacenan mediante `scrypt` con sal aleatoria y no se guardan como texto legible. Las rutas académicas de la API responden con `401` cuando no existe una sesión autorizada.

## Funciones

- Cursos, módulos, actividades, anuncios, progreso y analítica.
- Registro local e inicio de sesión con Google OAuth 2.0.
- Google Classroom, Drive, Calendar y Meet.
- Laboratorio AR con `<model-viewer>`.
- Laboratorio VR con A-Frame y WebXR.
- PWA, diseño adaptable y navegación accesible.
- FastAPI, SQLite para desarrollo y PostgreSQL en Render.
- Docker y pruebas automáticas en GitHub Actions.

## Ejecutar localmente

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python tools/apply_source_overlay.py
uvicorn app.main:app --reload
```

Abre `http://localhost:8000`. Sin una sesión, la página principal redirige a `/login`.

## Desplegar en Render

`render.yaml` administra:

1. el servicio Docker `nexus-edu-xr-eagarcia77`;
2. PostgreSQL `nexus-edu-xr-db`;
3. `DATABASE_URL`, `SESSION_SECRET` y cookies HTTPS;
4. las variables de Google OAuth;
5. el endpoint de salud `/healthz`.

En un Blueprint existente, abre **Blueprints → nexus-edu-xr → Syncs** y ejecuta **Manual sync** para aplicar la nueva base de datos.

## Activar Google

En Google Cloud activa Classroom API, Drive API y Calendar API. Crea un cliente OAuth de tipo **Web application** y registra:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
```

En Render añade:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
```

`GOOGLE_WORKSPACE_DOMAIN` es opcional para una institución que desee limitar las cuentas a su propio dominio.

## Validación

```powershell
python tools/apply_source_overlay.py
pip install -r requirements.txt pytest
$env:PYTHONPATH="."
pytest -q
node --check app/static/app.js
node --check app/static/auth.js
```

Esta entrega es un MVP. Antes de usar información académica real deben añadirse verificación de correo, recuperación de contraseña, administración de roles, cifrado persistente de tokens, auditoría, copias de seguridad, migraciones y revisión institucional de privacidad y accesibilidad.
