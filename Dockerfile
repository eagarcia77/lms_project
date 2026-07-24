FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Preserve the consolidated authoring layer while applying the authenticated V3 base.
RUN mkdir -p /tmp/nexus-overlay/app \
    && cp app/unified_authoring.py app/production_entry.py app/admin_authoring_v6.py app/admin_console.py /tmp/nexus-overlay/app/ \
    && cp start_runtime.sh requirements.txt /tmp/nexus-overlay/ \
    && python tools/apply_v3.py \
    && cp /tmp/nexus-overlay/app/* app/ \
    && cp /tmp/nexus-overlay/start_runtime.sh /tmp/nexus-overlay/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt
RUN python tools/patch_google_workspace_scopes.py
RUN test -f app/unified_authoring.py \
    && test -f app/production_entry.py \
    && test -f app/admin_authoring_v6.py \
    && test -f app/admin_console.py \
    && test -f tools/validate_unified_routes.py
RUN chmod +x start_runtime.sh
RUN python -m py_compile app/*.py tools/patch_google_workspace_scopes.py tools/validate_unified_routes.py
RUN NEXUS_SESSION_SECRET=build-verification-secret-change-in-production PYTHONPATH=. python tools/validate_unified_routes.py
RUN grep -q "https://www.googleapis.com/auth/drive.file" app/google_api.py \
    && grep -q "https://www.googleapis.com/auth/forms.body" app/google_api.py

EXPOSE 8000
CMD ["./start_runtime.sh"]
