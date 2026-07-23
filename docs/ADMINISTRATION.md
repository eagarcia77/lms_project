# Administración de NEXUS EDU XR

La consola administrativa se integra después de construir la aplicación principal. Por esta razón, la portada y la imagen animada que acompaña el mensaje **“Tu ecosistema académico, conectado, seguro e inmersivo”** permanecen intactas.

## Acceso

Después de configurar Render, visite:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/admin/login
```

## Variables protegidas en Render

Configure estos valores en **Environment**. No los publique en GitHub.

```text
NEXUS_BOOTSTRAP_ADMIN_EMAIL=correo-del-administrador
NEXUS_BOOTSTRAP_ADMIN_PASSWORD=contraseña-temporal-de-12-o-más-caracteres
NEXUS_BOOTSTRAP_ADMIN_NAME=Nombre del administrador
```

`NEXUS_SESSION_SECRET` se genera automáticamente desde `render.yaml`.

La primera cuenta se crea únicamente cuando no existe. Al iniciar sesión por primera vez, el sistema exige cambiar la contraseña temporal.

## Funciones disponibles en la fase inicial

- panel general con métricas;
- creación y administración del estado de cursos;
- periodos académicos y profesor asignado;
- administradores delegados;
- roles `superadmin`, `course_admin`, `user_admin`, `support` y `auditor`;
- matrículas con roles de estudiante, profesor, asistente, diseñador y facilitador;
- registro de auditoría con usuario, acción, entidad, fecha e IP;
- exportación JSON de cursos, matrículas y auditoría;
- almacenamiento en PostgreSQL de Render o SQLite para desarrollo.

## Modelo inspirado en administración LMS empresarial

La estructura separa los permisos institucionales de los roles de curso. Esto permite delegar administración de cursos, usuarios o auditoría sin entregar acceso total al sistema.

## Seguridad

- contraseñas protegidas con `scrypt` y sal aleatoria;
- cookie de sesión firmada, `HttpOnly`, `SameSite=Lax` y segura en producción;
- contraseña inicial de al menos 12 caracteres;
- cambio obligatorio de contraseña en el primer acceso;
- registro de inicios de sesión y acciones administrativas;
- secretos almacenados en Render, no en el repositorio.

## Próximas integraciones

La base administrativa ya permite continuar con:

1. sincronización directa con Course Studio;
2. copia de cursos y plantillas maestras;
3. importación y exportación de paquetes;
4. administración masiva mediante CSV;
5. centro de calificaciones y periodos;
6. reportes institucionales;
7. autenticación multifactor;
8. respaldos programados y restauración granular.
