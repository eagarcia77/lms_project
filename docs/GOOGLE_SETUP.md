# Configuración de Google Workspace y Course Studio V5

## APIs requeridas

En Google Cloud Console, dentro del proyecto **NEXUS EDU XR**, activa:

1. Google Classroom API.
2. Google Drive API.
3. Google Docs API.
4. Google Slides API.
5. Google Sheets API.
6. Google Forms API.
7. Google Calendar API.

## Cliente OAuth 2.0

1. Configura Google Auth Platform y añade los usuarios de prueba mientras la aplicación esté en modo **Testing**.
2. Crea un cliente OAuth 2.0 de tipo **Web application**.
3. Para Render, registra esta URI autorizada:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
```

4. En Render configura `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.
5. `GOOGLE_WORKSPACE_DOMAIN` es opcional cuando se desea limitar el acceso a un dominio institucional.

## Permisos del Diseñador de Cursos

Course Studio solicita permisos para:

- identificar al usuario mediante nombre, correo y perfil;
- leer los cursos autorizados de Classroom;
- crear archivos y carpetas de la plataforma en Drive;
- crear y editar documentos de Google Docs;
- crear y editar presentaciones de Google Slides;
- crear y editar hojas de Google Sheets;
- crear exámenes y cuestionarios de Google Forms;
- crear eventos de Calendar con videoconferencias de Google Meet.

Los documentos, presentaciones, hojas, formularios y reuniones quedan vinculados al curso y al módulo donde se crearon. Course Studio almacena el identificador y el enlace del recurso, mientras el archivo permanece en el Drive del usuario conectado.

## Autorizar permisos nuevos

Después de instalar Course Studio V5, los usuarios que ya habían conectado Google deben:

1. cerrar sesión en NEXUS EDU XR;
2. volver a entrar con Google;
3. aceptar los permisos nuevos para Drive, Docs, Slides, Sheets, Forms y Calendar.

Mientras la aplicación esté en modo de prueba, la cuenta debe figurar en **Google Auth Platform → Audience → Test users**.

## OpenOffice y LibreOffice

Cada módulo permite descargar plantillas editables en:

- `.odt` para documentos;
- `.odp` para presentaciones;
- `.ods` para hojas de planificación y calificación.

Los archivos siguen el estándar OpenDocument y pueden abrirse con LibreOffice u OpenOffice sin necesidad de una cuenta de Google.

## Inteligencia artificial opcional

Course Studio funciona aun sin proveedor de IA: incluye un diseñador pedagógico local basado en plantillas. Para conectar un servidor gratuito o institucional compatible con Ollama o con la API de OpenAI, configura en Render:

```text
AI_BASE_URL
AI_MODEL
AI_API_STYLE
AI_API_KEY
```

Ejemplos de `AI_API_STYLE`:

```text
ollama
openai
```

No coloque claves privadas en GitHub.

## Herramientas emergentes gratuitas

Course Studio incluye accesos y tipos de contenido para H5P/Lumi, JupyterLite, PhET, GeoGebra, diagrams.net, Excalidraw, Mermaid, Twine, Scratch, Blender y A-Frame. También permite registrar modelos 3D, experiencias de realidad aumentada, espacios de realidad virtual y videos 360 mediante URL HTTPS.

## Producción

Antes de abrir la plataforma públicamente:

- completa la verificación OAuth de Google;
- publica una política de privacidad;
- limita los permisos a los estrictamente necesarios;
- cifra y persiste los tokens de Google;
- revisa accesibilidad, derechos de autor y protección de datos;
- configura copias de seguridad de PostgreSQL.
