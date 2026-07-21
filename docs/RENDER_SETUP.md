# Despliegue en Render

## Método recomendado: Blueprint

El archivo `render.yaml` crea un servicio web Docker llamado `nexus-edu-xr-eagarcia77` en la región de Virginia. El servicio usa el plan gratuito, valida `/healthz` y despliega automáticamente cada cambio de la rama `main`.

## Pasos

1. Abre `https://render.com/deploy?repo=https://github.com/eagarcia77/lms_project`.
2. Inicia sesión en Render y autoriza el acceso al repositorio.
3. Confirma la creación del Blueprint.
4. El primer despliegue funciona en modo demostración sin credenciales de Google.
5. Para activar Google Workspace, añade estas variables en el panel de Render:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI=https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
GOOGLE_WORKSPACE_DOMAIN
```

6. Registra también la URI de redirección en Google Cloud.

## Verificación

- Aplicación: `https://nexus-edu-xr-eagarcia77.onrender.com`
- Salud: `https://nexus-edu-xr-eagarcia77.onrender.com/healthz`

Si Render informa que el nombre del servicio ya existe, cambia `name` en `render.yaml` y actualiza `APP_BASE_URL` y `GOOGLE_REDIRECT_URI` con el nuevo subdominio.
