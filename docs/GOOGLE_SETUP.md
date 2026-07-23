# Configuración de Google Workspace y Course Studio V6

## APIs requeridas

En Google Cloud Console, dentro del proyecto **NEXUS EDU XR**, active:

1. Google Classroom API.
2. Google Drive API.
3. Google Docs API.
4. Google Slides API.
5. Google Sheets API.
6. Google Forms API.
7. Google Calendar API.

## Cliente OAuth 2.0

1. Configure Google Auth Platform y añada los usuarios de prueba mientras la aplicación esté en modo **Testing**.
2. Cree un cliente OAuth 2.0 de tipo **Web application**.
3. Registre esta URI autorizada:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
```

4. En Render configure `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.
5. `GOOGLE_WORKSPACE_DOMAIN` es opcional para limitar el acceso a un dominio institucional.

## Permisos utilizados

Course Studio V6 solicita permisos para:

- identificar al usuario mediante nombre, correo y perfil;
- leer los cursos autorizados de Classroom;
- crear archivos propios de la plataforma en Drive;
- crear documentos de Google Docs;
- crear presentaciones de Google Slides;
- crear hojas de Google Sheets;
- crear formularios y cuestionarios en Google Forms;
- crear eventos de Calendar con videoconferencias de Google Meet.

Los archivos permanecen en el Drive del usuario conectado. NEXUS conserva el enlace y los metadatos dentro del curso y módulo donde se crearon.

## Autorizar permisos nuevos

Después del despliegue de V6, los usuarios que ya conectaron Google deben:

1. cerrar sesión en NEXUS;
2. volver a entrar con Google;
3. aceptar los permisos nuevos;
4. confirmar que su cuenta figure en **Google Auth Platform → Audience → Test users** mientras la aplicación esté en pruebas.

## Course Studio V6

La ruta administrativa es:

```text
/admin/authoring
```

Permite:

- crear cursos en blanco o con plantillas 5E, diseño inverso, proyectos, microaprendizaje o aprendizaje inmersivo;
- crear, eliminar y duplicar cursos y módulos;
- crear asignaciones, foros, exámenes, rúbricas, simulaciones y contenido multimedia;
- generar una estructura pedagógica con plantillas locales o un proveedor de IA opcional;
- crear Docs, Slides, Sheets, Forms, cuestionarios y Meet desde un módulo;
- descargar ODT, ODP y ODS para LibreOffice y Apache OpenOffice;
- vincular modelos GLB/glTF, contenido AR, VR, 360° y recursos WebXR;
- utilizar herramientas gratuitas como H5P/Lumi, JupyterLite, PhET, GeoGebra, diagrams.net, Excalidraw, Mermaid, Twine, Scratch, Blender y A-Frame.

## Inteligencia artificial opcional

Sin configuración externa, Course Studio utiliza un generador pedagógico local. Para conectar Ollama o una API compatible con OpenAI, configure en Render:

```text
AI_BASE_URL
AI_MODEL
AI_API_STYLE
AI_API_KEY
```

Valores de `AI_API_STYLE`:

```text
ollama
openai
```

No publique claves privadas en GitHub.

## OpenOffice y LibreOffice

Cada módulo permite descargar:

- `.odt`: documento del módulo;
- `.odp`: presentación editable;
- `.ods`: planificación, actividades y evaluación.

## Producción

Antes de abrir la plataforma públicamente:

- complete la verificación OAuth de Google;
- publique política de privacidad y términos de uso;
- limite los permisos OAuth a los estrictamente necesarios;
- cifre y persista los tokens de Google;
- revise accesibilidad, derechos de autor y protección de datos;
- configure copias de seguridad de PostgreSQL;
- pruebe AR y VR en navegadores y dispositivos compatibles.
