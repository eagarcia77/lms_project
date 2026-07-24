FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

RUN python -m py_compile tools/*.py app/*.py
RUN python tools/apply_v3.py
RUN python tools/apply_course_studio_package.py
RUN pip install --no-cache-dir -r requirements.txt
RUN test -f tools/apply_course_studio.py
RUN python tools/apply_course_studio.py
RUN test -f app/course_builder.py && test -f app/production_entry.py
RUN python tools/fix_course_builder_response_types.py
RUN python tools/patch_admin_console_v2.py
RUN test -f app/admin_authoring_v6.py && test -f tools/register_authoring_v6_direct.py
RUN python tools/register_authoring_v6_direct.py
RUN chmod +x start_runtime.sh
RUN python -m compileall -q app tools
RUN NEXUS_SESSION_SECRET=build-verification-secret-change-in-production python -c "from app.production_entry import app; print('Production entry validated with', len(app.routes), 'routes', flush=True)"
RUN grep -q "def register_authoring_v6" app/admin_authoring_v6.py && grep -q "def _validate" app/production_entry.py

EXPOSE 8000
CMD ["./start_runtime.sh"]
