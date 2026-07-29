FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Preserve the consolidated authoring, innovation, role management,
# administration and release metadata layers while applying the V3 base.
RUN mkdir -p /tmp/nexus-overlay/app \
    && cp app/unified_authoring.py app/innovation_hub.py app/admin_portal.py app/role_management.py app/home_admin_access.py app/environment_status.py app/production_entry.py app/admin_authoring_v6.py app/admin_console.py app/admin_system.py /tmp/nexus-overlay/app/ \
    && cp start_runtime.sh requirements.txt /tmp/nexus-overlay/ \
    && python tools/apply_v3.py \
    && cp /tmp/nexus-overlay/app/* app/ \
    && cp /tmp/nexus-overlay/start_runtime.sh /tmp/nexus-overlay/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt
RUN python tools/patch_google_workspace_scopes.py
RUN python tools/patch_admin_navigation.py
RUN python tools/patch_admin_portal_roles.py
RUN python tools/disable_pwa_cache.py
RUN python tools/patch_admin_home_access.py
RUN python tools/patch_environment_banner.py
RUN python tools/fix_unified_authoring_templates.py
RUN python tools/patch_eagr_branding.py
RUN test -f app/unified_authoring.py \
    && test -f app/innovation_hub.py \
    && test -f app/admin_portal.py \
    && test -f app/role_management.py \
    && test -f app/home_admin_access.py \
    && test -f app/environment_status.py \
    && test -f app/production_entry.py \
    && test -f app/admin_authoring_v6.py \
    && test -f app/admin_console.py \
    && test -f app/admin_system.py \
    && test -f tools/patch_admin_portal_roles.py \
    && test -f tools/disable_pwa_cache.py \
    && test -f tools/patch_admin_home_access.py \
    && test -f tools/patch_environment_banner.py \
    && test -f tools/fix_unified_authoring_templates.py \
    && test -f tools/patch_eagr_branding.py \
    && test -f tools/validate_runtime_dependencies.py \
    && test -f tools/validate_unified_routes.py \
    && test -f tools/smoke_test_admin_flow.py \
    && test -f tools/smoke_test_integrated_portal.py \
    && test -f tools/smoke_test_role_management.py \
    && test -f tools/smoke_test_admin_home_access.py \
    && test -f tools/smoke_test_environment_status.py \
    && test -f tools/smoke_test_eagr_branding.py
RUN chmod +x start_runtime.sh
RUN python -m py_compile app/*.py \
    tools/patch_google_workspace_scopes.py \
    tools/patch_admin_navigation.py \
    tools/patch_admin_portal_roles.py \
    tools/disable_pwa_cache.py \
    tools/patch_admin_home_access.py \
    tools/patch_environment_banner.py \
    tools/fix_unified_authoring_templates.py \
    tools/patch_eagr_branding.py \
    tools/validate_runtime_dependencies.py \
    tools/validate_unified_routes.py \
    tools/smoke_test_admin_flow.py \
    tools/smoke_test_integrated_portal.py \
    tools/smoke_test_role_management.py \
    tools/smoke_test_admin_home_access.py \
    tools/smoke_test_environment_status.py \
    tools/smoke_test_eagr_branding.py
RUN python tools/validate_runtime_dependencies.py
RUN APP_ENV=staging \
    RELEASE_CHANNEL=staging \
    APP_NAME='EAGR Learning XR · STAGING' \
    SESSION_SECRET=build-verification-session-secret-change-in-production \
    NEXUS_SESSION_SECRET=build-verification-admin-secret-change-in-production \
    PYTHONPATH=. python tools/validate_unified_routes.py
RUN PYTHONPATH=. python tools/smoke_test_admin_flow.py
RUN PYTHONPATH=. python tools/smoke_test_integrated_portal.py
RUN PYTHONPATH=. python tools/smoke_test_role_management.py
RUN PYTHONPATH=. python tools/smoke_test_admin_home_access.py
RUN PYTHONPATH=. python tools/smoke_test_environment_status.py
RUN PYTHONPATH=. python tools/smoke_test_eagr_branding.py
RUN grep -q "https://www.googleapis.com/auth/drive.file" app/google_api.py \
    && grep -q "https://www.googleapis.com/auth/forms.body" app/google_api.py \
    && grep -q "Administración integral" app/admin_portal.py \
    && grep -q '"/admin/roles"' app/admin_portal.py \
    && grep -q "Debe permanecer por lo menos un superadministrador activo" app/role_management.py \
    && grep -q '"/api/admin/access"' app/production_entry.py \
    && grep -q '"/api/release"' app/production_entry.py \
    && grep -q 'id="admin-access-top"' app/static/index.html \
    && grep -q 'id="admin-access-nav"' app/static/index.html \
    && grep -q 'id="environment-banner"' app/static/index.html \
    && grep -q "NEXUS_ADMIN_HOME_ACCESS_V1" app/static/app.js \
    && grep -q "NEXUS_ENVIRONMENT_BANNER_V1" app/static/app.js \
    && grep -q "EAGR Learning XR" app/static/index.html \
    && grep -q '"name": "EAGR Learning XR"' app/static/manifest.json \
    && grep -q "EAGR_LEARNING_XR_BRANDING_V1" tools/patch_eagr_branding.py \
    && ! grep -q "NEXUS EDU XR" app/static/index.html \
    && ! grep -q "NEXUS EDU XR" app/static/manifest.json \
    && ! grep -q "NEXUS EDU XR" app/admin_portal.py \
    && grep -q "NEXUS_PWA_DISABLED_FOR_STABILITY" app/static/app.js \
    && grep -q "self.registration.unregister()" app/static/sw.js \
    && ! grep -q 'register("/static/sw.js")' app/static/app.js \
    && ! grep -q "new MutationObserver" app/static/app.js \
    && ! grep -q "location.reload(" app/static/app.js

EXPOSE 8000
CMD ["./start_runtime.sh"]
