FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Preserve the consolidated authoring, innovation, role management and
# administration layers while applying the authenticated V3 base package.
RUN mkdir -p /tmp/nexus-overlay/app \
    && cp app/unified_authoring.py app/innovation_hub.py app/admin_portal.py app/role_management.py app/production_entry.py app/admin_authoring_v6.py app/admin_console.py app/admin_system.py /tmp/nexus-overlay/app/ \
    && cp start_runtime.sh requirements.txt /tmp/nexus-overlay/ \
    && python tools/apply_v3.py \
    && cp /tmp/nexus-overlay/app/* app/ \
    && cp /tmp/nexus-overlay/start_runtime.sh /tmp/nexus-overlay/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt
RUN python tools/patch_google_workspace_scopes.py
RUN python tools/patch_admin_navigation.py
RUN python tools/patch_admin_portal_roles.py
RUN python tools/fix_unified_authoring_templates.py
RUN test -f app/unified_authoring.py \
    && test -f app/innovation_hub.py \
    && test -f app/admin_portal.py \
    && test -f app/role_management.py \
    && test -f app/production_entry.py \
    && test -f app/admin_authoring_v6.py \
    && test -f app/admin_console.py \
    && test -f app/admin_system.py \
    && test -f tools/patch_admin_portal_roles.py \
    && test -f tools/fix_unified_authoring_templates.py \
    && test -f tools/validate_runtime_dependencies.py \
    && test -f tools/validate_unified_routes.py \
    && test -f tools/smoke_test_admin_flow.py \
    && test -f tools/smoke_test_integrated_portal.py \
    && test -f tools/smoke_test_role_management.py
RUN chmod +x start_runtime.sh
RUN python -m py_compile app/*.py \
    tools/patch_google_workspace_scopes.py \
    tools/patch_admin_navigation.py \
    tools/patch_admin_portal_roles.py \
    tools/fix_unified_authoring_templates.py \
    tools/validate_runtime_dependencies.py \
    tools/validate_unified_routes.py \
    tools/smoke_test_admin_flow.py \
    tools/smoke_test_integrated_portal.py \
    tools/smoke_test_role_management.py
RUN python tools/validate_runtime_dependencies.py
RUN SESSION_SECRET=build-verification-session-secret-change-in-production \
    NEXUS_SESSION_SECRET=build-verification-admin-secret-change-in-production \
    PYTHONPATH=. python tools/validate_unified_routes.py
RUN PYTHONPATH=. python tools/smoke_test_admin_flow.py
RUN PYTHONPATH=. python tools/smoke_test_integrated_portal.py
RUN PYTHONPATH=. python tools/smoke_test_role_management.py
RUN grep -q "https://www.googleapis.com/auth/drive.file" app/google_api.py \
    && grep -q "https://www.googleapis.com/auth/forms.body" app/google_api.py \
    && grep -q "Administración integral" app/admin_portal.py \
    && grep -q '"/admin/roles"' app/admin_portal.py \
    && grep -q "Debe permanecer por lo menos un superadministrador activo" app/role_management.py

EXPOSE 8000
CMD ["./start_runtime.sh"]
