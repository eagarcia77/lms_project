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
RUN python tools/install_course_builder.py
RUN python tools/fix_course_builder_response_types.py
RUN chmod +x start.sh
RUN python -m compileall -q app
RUN python -c "from app.main import app; paths=[getattr(r, 'path', '') for r in app.routes]; assert '/course-studio' in paths; assert '/course-studio/courses' in paths"

EXPOSE 8000
CMD ["./start.sh"]
