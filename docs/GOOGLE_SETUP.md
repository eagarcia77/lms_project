# Configuración de Google Workspace

1. Crea un proyecto en Google Cloud Console.
2. Configura la pantalla de consentimiento OAuth y añade los usuarios de prueba mientras la aplicación esté en modo de prueba.
3. Activa estas APIs: Google Classroom API, Google Drive API y Google Calendar API.
4. Crea un cliente OAuth 2.0 de tipo **Web application**.
5. Registra `http://localhost:8000/auth/google/callback` como URI de redirección autorizada.
6. Copia `.env.example` a `.env` y completa `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `SESSION_SECRET`.
7. Para una institución, define `GOOGLE_WORKSPACE_DOMAIN` y completa la verificación/publicación de la aplicación según los scopes solicitados.

## Permisos solicitados por el MVP

- Perfil, nombre y correo.
- Lectura de cursos y tareas propias en Classroom.
- Lectura de archivos en Drive.
- Lectura y creación de eventos en Calendar para videoclases de Meet.

Antes de producción, reduce los scopes a los estrictamente necesarios, completa la evaluación de privacidad y almacena refresh tokens cifrados en el servidor.
