FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

RUN python tools/apply_v3.py
RUN python tools/apply_course_studio_package.py
RUN pip install --no-cache-dir -r requirements.txt
RUN test -f tools/apply_course_studio.py
RUN python tools/apply_course_studio.py
RUN test -f app/course_builder.py && test -f app/runtime_entry.py
RUN python tools/fix_course_builder_response_types.py
RUN python tools/apply_admin_console.py
RUN chmod +x start_runtime.sh
RUN python -m compileall -q app
RUN NEXUS_SESSION_SECRET=build-verification-secret-change-in-production python -c "from app.runtime_entry import app; routes=[(getattr(r,'path',''),set(getattr(r,'methods',[]) or [])) for r in app.routes]; assert any(p == '/course-studio' and 'GET' in m for p,m in routes); assert any(p == '/course-studio/courses' and 'POST' in m for p,m in routes); assert any(p == '/course-studio/courses/{course_id}/modules' and 'POST' in m for p,m in routes); assert any(p == '/admin/login' and 'GET' in m for p,m in routes); assert any(p == '/admin/courses' and 'GET' in m for p,m in routes); assert any(p == '/admin/users' and 'GET' in m for p,m in routes)"

EXPOSE 8000
CMD ["./start_runtime.sh"]
