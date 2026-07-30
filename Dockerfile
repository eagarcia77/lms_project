FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Preserve the consolidated authoring, innovation, role management,
# homepage content management and administration layers while applying
# the authenticated V3 base package.
RUN mkdir -p /tmp/nexus-overlay/app /tmp/nexus-overlay/static \
    && cp app/unified_authoring.py app/innovation_hub.py app/admin_portal.py app/role_management.py app/production_entry.py app/home_content.py app/patch_public_homepage_runtime.py app/admin_authoring_v6.py app/admin_console.py app/admin_system.py /tmp/nexus-overlay/app/ \
    && cp -a app/static/. /tmp/nexus-overlay/static/ \
    && cp start_runtime.sh requirements.txt /tmp/nexus-overlay/ \
    && python tools/apply_v3.py \
    && cp /tmp/nexus-overlay/app/* app/ \
    && mkdir -p app/static \
    && cp -a /tmp/nexus-overlay/static/. app/static/ \
    && cp /tmp/nexus-overlay/start_runtime.sh /tmp/nexus-overlay/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt
RUN python tools/patch_google_workspace_scopes.py
RUN python tools/patch_admin_navigation.py
RUN python tools/patch_admin_portal_roles.py
RUN python tools/disable_pwa_cache.py
RUN python tools/fix_unified_authoring_templates.py
RUN python tools/patch_nuvedra_branding.py
RUN python app/patch_public_homepage_runtime.py
RUN test -f app/unified_authoring.py \
    && test -f app/innovation_hub.py \
    && test -f app/admin_portal.py \
    && test -f app/role_management.py \
    && test -f app/production_entry.py \
    && test -f app/home_content.py \
    && test -f app/patch_public_homepage_runtime.py \
    && test -f app/admin_authoring_v6.py \
    && test -f app/admin_console.py \
    && test -f app/admin_system.py \
    && test -f app/static/auth.js \
    && test -f app/static/assets/nuvedra-logo.svg \
    && test -f app/static/assets/nuvedra-hero.svg \
    && test -f tools/patch_admin_portal_roles.py \
    && test -f tools/disable_pwa_cache.py \
    && test -f tools/fix_unified_authoring_templates.py \
    && test -f tools/patch_nuvedra_branding.py \
    && test -f tools/validate_runtime_dependencies.py \
    && test -f tools/validate_unified_routes.py \
    && test -f tools/smoke_test_admin_flow.py \
    && test -f tools/smoke_test_integrated_portal.py \
    && test -f tools/smoke_test_role_management.py \
    && test -f tools/smoke_test_nuvedra_branding.py
RUN chmod +x start_runtime.sh
RUN python -m py_compile app/*.py \
    tools/patch_google_workspace_scopes.py \
    tools/patch_admin_navigation.py \
    tools/patch_admin_portal_roles.py \
    tools/disable_pwa_cache.py \
    tools/fix_unified_authoring_templates.py \
    tools/patch_nuvedra_branding.py \
    tools/validate_runtime_dependencies.py \
    tools/validate_unified_routes.py \
    tools/smoke_test_admin_flow.py \
    tools/smoke_test_integrated_portal.py \
    tools/smoke_test_role_management.py \
    tools/smoke_test_nuvedra_branding.py
RUN node --check app/static/app.js && node --check app/static/auth.js
RUN python tools/validate_runtime_dependencies.py
RUN APP_NAME=NUVEDRA \
    SESSION_SECRET=build-verification-session-secret-change-in-production \
    NEXUS_SESSION_SECRET=build-verification-admin-secret-change-in-production \
    PYTHONPATH=. python tools/validate_unified_routes.py
RUN PYTHONPATH=. python tools/smoke_test_admin_flow.py
RUN PYTHONPATH=. python tools/smoke_test_integrated_portal.py
RUN PYTHONPATH=. python tools/smoke_test_role_management.py
RUN PYTHONPATH=. python tools/smoke_test_nuvedra_branding.py
RUN grep -q "https://www.googleapis.com/auth/drive.file" app/google_api.py \
    && grep -q "https://www.googleapis.com/auth/forms.body" app/google_api.py \
    && grep -q "Administración integral" app/admin_portal.py \
    && grep -q '"/admin/roles"' app/admin_portal.py \
    && grep -q '"/admin/home-content"' app/admin_portal.py \
    && grep -q "Debe permanecer por lo menos un superadministrador activo" app/role_management.py \
    && grep -q "NUVEDRA" app/static/index.html \
    && grep -q "/api/home-content" app/static/app.js \
    && grep -q "NUVEDRA_PUBLIC_LOGIN_SAFE_V1" app/static/app.js \
    && grep -q "NUVEDRA_ACCESSIBLE_THEME_V1" app/static/styles.css \
    && grep -q '"name": "NUVEDRA"' app/static/manifest.json \
    && grep -q "prefers-reduced-motion" app/static/styles.css \
    && grep -q "forced-colors" app/static/styles.css \
    && ! grep -q "NEXUS EDU XR" app/static/index.html \
    && ! grep -qi "#007B5F\|#FED141\|#85714D" app/static/styles.css \
    && grep -q "NEXUS_PWA_DISABLED_FOR_STABILITY" app/static/app.js \
    && grep -q "self.registration.unregister()" app/static/sw.js \
    && ! grep -q 'register("/static/sw.js")' app/static/app.js

EXPOSE 8000
CMD ["./start_runtime.sh"]
