# Arquitectura de NEXUS EDU XR

## Capas

1. **Experiencia web/PWA:** HTML semántico, diseño adaptable, navegación por teclado, contraste institucional y modo instalable.
2. **API académica:** FastAPI para cursos, módulos, actividades, anuncios, analítica y servicios de integración.
3. **Datos:** SQLite en el MVP; PostgreSQL y almacenamiento de objetos para producción.
4. **Google Workspace:** OAuth 2.0 y APIs de Classroom, Drive y Calendar. Google Meet se crea mediante `conferenceData` en Calendar.
5. **Capa inmersiva:** WebXR, A-Frame y `<model-viewer>` para VR, AR y visualización 3D.
6. **Seguridad:** sesión firmada, OAuth con `state`, permisos mínimos y tokens guardados solo en el servidor durante la sesión.

## Evolución recomendada

- PostgreSQL + Redis.
- Control de acceso basado en roles: administrador, diseñador instruccional, docente, estudiante, mentor y auditor.
- LTI 1.3, OneRoster 1.2 y Caliper Analytics.
- Integración SIS, biblioteca, pagos, videoteca y sistema de identidad institucional.
- Almacenamiento cifrado de tokens con Google Secret Manager o un servicio equivalente.
- Microservicio de analítica y alertas tempranas.
- Motor de evaluación con banco de preguntas, rúbricas, SafeAssign-equivalent y proctoring compatible con políticas institucionales.
