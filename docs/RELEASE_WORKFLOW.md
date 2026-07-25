# Flujo de publicación de NEXUS EDU XR

## Entornos

| Entorno | Rama | Servicio Render | Base de datos | Uso |
|---|---|---|---|---|
| Producción | `main` | `nexus-edu-xr-eagarcia77` | `nexus-edu-xr-db` | Versión publicada para usuarios reales |
| Staging | `staging` | `nexus-edu-xr-staging-eagarcia77` | `nexus-edu-xr-staging-db` | Desarrollo, demostraciones y pruebas |

Las bases de datos, secretos, sesiones, URL base y redirecciones OAuth deben permanecer separados.

## Flujo obligatorio

```text
feature/nombre-del-cambio
          ↓ Pull Request
       staging
          ↓ pruebas automáticas + revisión funcional
Pull Request de publicación
          ↓ aprobación y merge
         main
          ↓ CI aprobado
   Render producción
```

## Desarrollo de cambios

1. Crear una rama desde `staging`:

   ```bash
   git switch staging
   git pull origin staging
   git switch -c feature/nombre-del-cambio
   ```

2. Programar y probar el cambio en la rama `feature/*`.
3. Abrir un Pull Request hacia `staging`.
4. No abrir Pull Requests de funciones directamente hacia `main`.

## Compuerta de calidad de staging

El workflow `Staging Quality Gate` se ejecuta con cada cambio dirigido a `staging` y debe completar:

- construcción de la imagen Docker exacta usada por Render;
- compilación y pruebas incluidas en el Dockerfile;
- inicio de un contenedor aislado;
- validación de `/healthz`;
- validación de `/admin/login`;
- limpieza del contenedor de prueba.

Render staging utiliza `autoDeployTrigger: checksPass`, por lo que solo debe desplegar después de que GitHub informe que todas las verificaciones terminaron correctamente.

## Pruebas funcionales en staging

Después del despliegue de staging se deben verificar, como mínimo:

- inicio y cierre de sesión administrativa;
- creación, edición, suspensión y reactivación de cuentas;
- asignación de roles y matrículas;
- creación y modificación de cursos y módulos;
- permisos de superadministrador, administrador académico, administrador de usuarios, soporte y auditor;
- accesibilidad básica mediante teclado;
- funcionamiento de Google Workspace cuando las credenciales estén configuradas;
- ausencia de ciclos de recarga en el navegador;
- `/healthz` sin errores.

No se deben copiar datos personales reales de producción a staging.

## Promoción a producción

1. Abrir **Actions** en GitHub.
2. Ejecutar `Promote Staging to Production`.
3. El workflow vuelve a construir y probar la rama `staging`.
4. Si todo pasa, crea o reutiliza un Pull Request `staging → main`.
5. Revisar el resumen, archivos modificados y resultados de CI.
6. Fusionar el Pull Request solamente cuando todas las verificaciones estén verdes.
7. Render producción, configurado con `checksPass`, despliega el commit fusionado.
8. Ejecutar una verificación posterior a publicación de `/healthz`, `/admin/login`, usuarios, roles y Course Studio.

## Reversión

Si producción presenta una falla:

1. No continuar haciendo cambios directos en `main`.
2. Identificar el último commit publicado que funcionaba.
3. Crear una rama de corrección o revertir el Pull Request defectuoso.
4. Validar la corrección primero en `staging`.
5. Promover nuevamente mediante el flujo normal.

## Configuración recomendada de ramas

### `main`

- requerir Pull Request;
- impedir `force push`;
- requerir el control `CI / test`;
- requerir que la rama esté actualizada antes del merge;
- limitar el merge a administradores autorizados.

### `staging`

- requerir Pull Request para cambios de funciones;
- impedir `force push`;
- requerir `CI / test`;
- requerir `Staging Quality Gate / Build, tests and runtime smoke test`;
- permitir que únicamente cambios validados lleguen a la rama.

## Archivos de infraestructura

- `render.yaml`: producción.
- `render-staging.yaml`: staging; debe seleccionarse como ruta personalizada al crear el Blueprint de pruebas.
- `.github/workflows/ci.yml`: pruebas generales.
- `.github/workflows/staging-quality-gate.yml`: validación completa de staging.
- `.github/workflows/promote-staging.yml`: creación controlada del Pull Request de publicación.
