# Despliegue en Render

## Método recomendado: Blueprint

El archivo `render.yaml` crea un servicio web Docker llamado `nexus-edu-xr-eagarcia77` en la región de Virginia. El servicio usa el plan gratuito, valida `/healthz` y despliega automáticamente después de que las verificaciones de GitHub Actions pasen.

## Pasos

1. Abre `https://render.com/deploy?repo=https://github.com/eagarcia77/lms_project`.
2. Autoriza el acceso de Render a GitHub.
3. Confirma la creación del Blueprint.
4. Las variables `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_WORKSPACE_DOMAIN` son opcionales para el modo demostración.
5. Cuando configures OAuth en Google Cloud, registra:

```text
https://nexus-edu-xr-eagarcia77.onrender.com/auth/google/callback
```

## Verificación

- Aplicación: `https://nexus-edu-xr-eagarcia77.onrender.com`
- Salud: `https://nexus-edu-xr-eagarcia77.onrender.com/healthz`

Si Render informa que el nombre del servicio ya existe, cambia `name` en `render.yaml` y actualiza `APP_BASE_URL` y `GOOGLE_REDIRECT_URI` con el nuevo subdominio.
