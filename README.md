# NEXUS EDU XR

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eagarcia77/lms_project)

**Repositorio:** https://github.com/eagarcia77/lms_project  
**URL objetivo en Render:** https://nexus-edu-xr-eagarcia77.onrender.com

MVP de una plataforma de educación en línea inspirada en la claridad de Blackboard Ultra, integrada con Google Workspace y preparada para realidad virtual, realidad aumentada y contenido 3D.

## Funciones incluidas

- Panel académico, cursos, módulos, actividades, anuncios y progreso.
- Integración OAuth 2.0 con Google.
- Lectura de cursos activos de Google Classroom.
- Archivos recientes de Google Drive.
- Eventos de Google Calendar.
- Creación de videoclases con Google Meet mediante Calendar.
- Laboratorio AR con `<model-viewer>` y laboratorio VR con A-Frame/WebXR.
- PWA básica, diseño adaptable, navegación por teclado y reducción de movimiento.
- FastAPI, SQLite, Docker y pruebas automatizadas.

## Ejecutar en Windows PowerShell

```powershell
cd nexus-edu-xr
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abre `http://localhost:8000`.

## Ejecutar con Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## Activar Google Workspace

Sigue `docs/GOOGLE_SETUP.md`. Sin credenciales, el LMS funciona en modo demostración; las llamadas reales a Classroom, Drive, Calendar y Meet permanecen desactivadas.

## Pruebas

```powershell
pip install pytest
pytest -q
```

## Producción

Este repositorio es un MVP técnico, no un reemplazo institucional listo para datos reales. Antes de usarlo con estudiantes se deben implementar PostgreSQL, cifrado de tokens, control de roles, auditoría, copias de seguridad, evaluación de privacidad, cumplimiento institucional, pruebas de accesibilidad y monitoreo.

## Instalación rápida en Windows

Desde PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
.\run_windows.bat
```

## Desplegar en Render

El repositorio incluye `render.yaml`, Docker y el endpoint de salud `/healthz`.

1. Pulsa **Deploy to Render** al inicio de este README.
2. Inicia sesión en Render y autoriza el acceso al repositorio.
3. Confirma el Blueprint `nexus-edu-xr-eagarcia77`.
4. El primer despliegue funciona en modo demostración sin credenciales de Google.
5. Para activar Google Workspace, añade en Render `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` y, si aplica, `GOOGLE_WORKSPACE_DOMAIN`.
6. Configura `GOOGLE_REDIRECT_URI` con este valor y regístralo también en Google Cloud:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
```

Render desplegará automáticamente cada cambio publicado en la rama `main`.
