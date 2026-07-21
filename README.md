# NEXUS EDU XR

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eagarcia77/lms_project)

**Repositorio:** https://github.com/eagarcia77/lms_project  
**Aplicación:** https://nexus-edu-xr-eagarcia77.onrender.com

Plataforma de educación en línea inspirada en Blackboard Ultra, integrada con Google Workspace y preparada para realidad virtual, realidad aumentada y contenido 3D.

## Acceso y seguridad

- Inicio de sesión con Google OAuth 2.0.
- Registro e inicio de sesión con una cuenta NEXUS local.
- Cierre de sesión visible y cierre de todas las sesiones.
- Recuperación y restablecimiento de contraseña mediante enlace seguro.
- Contraseñas locales protegidas mediante `scrypt` con sal aleatoria.
- Protección de rutas académicas, controles de sesión y registro de eventos de seguridad.

## Course Studio

El área **Diseñador de cursos** permite:

- crear cursos propios;
- crear y ordenar módulos;
- crear Google Docs y Google Slides desde un módulo;
- guardar en la base de datos el identificador y enlace del archivo dentro del módulo donde se creó;
- crear asignaciones con instrucciones, puntuación y fecha límite;
- crear foros de discusión y publicar respuestas;
- crear exámenes de Google Forms con preguntas de selección múltiple y respuesta corta;
- crear eventos de Google Calendar con videoconferencia de Google Meet;
- mantener todos los recursos organizados dentro del curso.

Los archivos de Docs, Slides y Forms permanecen en el Google Drive del usuario conectado. El editor de Google se abre en una pestaña segura y NEXUS conserva el enlace en el módulo.

## Otras funciones

- Panel académico, anuncios, progreso y analítica.
- Google Classroom, Drive y Calendar.
- Laboratorios AR con `<model-viewer>`.
- Laboratorios VR con A-Frame y WebXR.
- PWA, diseño adaptable y navegación accesible.
- FastAPI, SQLite para desarrollo y PostgreSQL en Render.
- Docker y pruebas automáticas con GitHub Actions.

## Google Cloud requerido

Activa estas APIs:

1. Google Classroom API.
2. Google Drive API.
3. Google Docs API.
4. Google Slides API.
5. Google Forms API.
6. Google Calendar API.

URI OAuth autorizada para Render:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
```

Variables en Render:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
```

Los usuarios que ya habían conectado Google deben cerrar sesión y autorizar nuevamente la aplicación para aceptar los permisos de Docs, Slides y Forms. Consulta `docs/GOOGLE_SETUP.md`.

## Construcción y despliegue

El Dockerfile aplica, en orden:

```text
tools/apply_v3.py
tools/apply_course_studio_package.py
tools/apply_course_studio.py
```

Render despliega automáticamente los cambios de `main`. El endpoint de salud es `/healthz`.

## Desarrollo local

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python tools/apply_v3.py
python tools/apply_course_studio_package.py
python tools/apply_course_studio.py
pip install -r requirements.txt
uvicorn app.course_studio_entry:app --reload
```

## Estado del proyecto

NEXUS EDU XR continúa siendo un MVP. Antes de manejar información académica institucional deben completarse administración avanzada de roles, migraciones formales, copias de seguridad, cifrado persistente de tokens, centro de calificaciones, auditoría institucional, revisión de privacidad, verificación OAuth y pruebas de accesibilidad.
