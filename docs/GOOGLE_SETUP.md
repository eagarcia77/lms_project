# Configuración de Google Workspace

## APIs requeridas

En Google Cloud Console, dentro del proyecto **NEXUS EDU XR**, activa:

1. Google Classroom API.
2. Google Drive API.
3. Google Docs API.
4. Google Slides API.
5. Google Forms API.
6. Google Calendar API.

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

La plataforma solicita permisos para:

- identificar al usuario mediante nombre, correo y perfil;
- leer los cursos autorizados de Classroom;
- crear y conservar archivos propios de la aplicación en Drive;
- crear y editar documentos de Google Docs;
- crear y editar presentaciones de Google Slides;
- crear exámenes y cuestionarios de Google Forms;
- leer respuestas de Forms cuando se habilite el centro de calificaciones;
- leer y crear eventos de Calendar con videoconferencias de Google Meet.

Los documentos, presentaciones y formularios se guardan en el Drive del usuario conectado. NEXUS EDU XR conserva en su base de datos el identificador y el enlace de edición dentro del curso y módulo donde se crearon.

## Autorizar permisos nuevos

Después de instalar Course Studio, los usuarios que ya habían conectado Google deben:

1. cerrar sesión en NEXUS EDU XR;
2. volver a entrar con Google;
3. aceptar los permisos nuevos para Docs, Slides y Forms.

Mientras la aplicación esté en modo de prueba, la cuenta debe figurar en **Google Auth Platform → Audience → Test users**.

## Producción

Antes de abrir la plataforma públicamente, completa la verificación OAuth de Google, publica una política de privacidad, limita los permisos a los estrictamente necesarios y conserva los tokens cifrados en almacenamiento persistente.
