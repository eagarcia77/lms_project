FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Preserve the consolidated platform while applying the authenticated V3 base.
RUN mkdir -p /tmp/nexus-overlay/app \
    && cp app/unified_authoring.py app/innovation_hub.py app/admin_portal.py app/role_management.py app/home_admin_access.py app/platform_access.py app/course_management.py app/unified_course_catalog.py app/quality_center.py app/production_entry.py app/admin_authoring_v6.py app/admin_console.py app/admin_system.py /tmp/nexus-overlay/app/ \
    && cp start_runtime.sh requirements.txt /tmp/nexus-overlay/ \
    && python tools/apply_v3.py \
    && cp /tmp/nexus-overlay/app/* app/ \
    && cp /tmp/nexus-overlay/start_runtime.sh /tmp/nexus-overlay/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt
RUN python tools/patch_google_workspace_scopes.py
RUN python tools/patch_admin_navigation.py
RUN python tools/patch_admin_portal_roles.py
RUN python tools/patch_academic_roles.py
RUN python tools/patch_quality_navigation.py
RUN python tools/patch_home_admin_button.py
RUN python tools/patch_course_catalog_frontend.py
RUN python tools/bump_course_editor_cache.py
RUN python tools/stabilize_browser_runtime.py
RUN python tools/fix_unified_authoring_templates.py
RUN test -f app/unified_authoring.py \
    && test -f app/innovation_hub.py \
    && test -f app/admin_portal.py \
    && test -f app/role_management.py \
    && test -f app/home_admin_access.py \
    && test -f app/platform_access.py \
    && test -f app/course_management.py \
    && test -f app/unified_course_catalog.py \
    && test -f app/quality_center.py \
    && test -f app/production_entry.py \
    && test -f app/admin_authoring_v6.py \
    && test -f app/admin_console.py \
    && test -f app/admin_system.py \
    && test -f tools/patch_admin_portal_roles.py \
    && test -f tools/patch_academic_roles.py \
    && test -f tools/patch_quality_navigation.py \
    && test -f tools/patch_home_admin_button.py \
    && test -f tools/patch_course_catalog_frontend.py \
    && test -f tools/bump_course_editor_cache.py \
    && test -f tools/stabilize_browser_runtime.py \
    && test -f tools/fix_unified_authoring_templates.py \
    && test -f tools/validate_runtime_dependencies.py \
    && test -f tools/validate_unified_routes.py \
    && test -f tools/smoke_test_admin_flow.py \
    && test -f tools/smoke_test_integrated_portal.py \
    && test -f tools/smoke_test_role_management.py \
    && test -f tools/smoke_test_academic_roles.py \
    && test -f tools/smoke_test_home_admin_button.py \
    && test -f tools/smoke_test_course_editing.py \
    && test -f tools/smoke_test_quality_center.py \
    && test -f tools/smoke_test_browser_stability.py
RUN chmod +x start_runtime.sh
RUN python -m py_compile app/*.py \
    tools/patch_google_workspace_scopes.py \
    tools/patch_admin_navigation.py \
    tools/patch_admin_portal_roles.py \
    tools/patch_academic_roles.py \
    tools/patch_quality_navigation.py \
    tools/patch_home_admin_button.py \
    tools/patch_course_catalog_frontend.py \
    tools/bump_course_editor_cache.py \
    tools/stabilize_browser_runtime.py \
    tools/fix_unified_authoring_templates.py \
    tools/validate_runtime_dependencies.py \
    tools/validate_unified_routes.py \
    tools/smoke_test_admin_flow.py \
    tools/smoke_test_integrated_portal.py \
    tools/smoke_test_role_management.py \
    tools/smoke_test_academic_roles.py \
    tools/smoke_test_home_admin_button.py \
    tools/smoke_test_course_editing.py \
    tools/smoke_test_quality_center.py \
    tools/smoke_test_browser_stability.py
RUN python tools/validate_runtime_dependencies.py
RUN SESSION_SECRET=build-verification-session-secret-change-in-production \
    NEXUS_SESSION_SECRET=build-verification-admin-secret-change-in-production \
    PYTHONPATH=. python tools/validate_unified_routes.py
RUN PYTHONPATH=. python tools/smoke_test_admin_flow.py
RUN PYTHONPATH=. python tools/smoke_test_integrated_portal.py
RUN PYTHONPATH=. python tools/smoke_test_role_management.py
RUN PYTHONPATH=. python tools/smoke_test_academic_roles.py
RUN PYTHONPATH=. python tools/smoke_test_home_admin_button.py
RUN PYTHONPATH=. python tools/smoke_test_course_editing.py
RUN PYTHONPATH=. python tools/smoke_test_quality_center.py
RUN PYTHONPATH=. python tools/smoke_test_browser_stability.py
RUN grep -q "https://www.googleapis.com/auth/drive.file" app/google_api.py \
    && grep -q "https://www.googleapis.com/auth/forms.body" app/google_api.py \
    && grep -q "Administración integral" app/admin_portal.py \
    && grep -q '"/admin/roles"' app/admin_portal.py \
    && grep -q '"/admin/quality"' app/admin_portal.py \
    && grep -q '"label": "Instructor"' app/role_management.py \
    && grep -q '"label": "Estudiante"' app/role_management.py \
    && grep -q 'Esta cuenta no tiene un rol administrativo' app/admin_console.py \
    && grep -q '/api/platform/access' app/platform_access.py \
    && grep -q '/admin/authoring/courses/{course_id}/update' app/production_entry.py \
    && grep -q '/admin/quality/report.json' app/production_entry.py \
    && grep -q 'Creación y edición unificada' app/course_management.py \
    && grep -q 'Portada y Course Studio conectados' app/unified_course_catalog.py \
    && grep -q 'Centro de Calidad Académica' app/quality_center.py \
    && grep -q 'NEXUS_UNIFIED_COURSE_CATALOG_FRONTEND_V3' app/static/app.js \
    && grep -q 'id="admin-access"' app/static/index.html \
    && grep -q '20260725-browser-stability-v7' app/static/index.html \
    && grep -q '20260725-browser-stability-v7' app/static/sw.js \
    && grep -q 'NEXUS_BROWSER_STABILITY_NETWORK_ONLY' app/static/sw.js \
    && grep -q 'updateAdminAccess' app/static/app.js \
    && grep -q '/api/admin/access' app/home_admin_access.py

EXPOSE 8000
CMD ["./start_runtime.sh"]
