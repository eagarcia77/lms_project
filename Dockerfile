FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

RUN python tools/apply_v3.py \
    && python tools/apply_course_studio_package.py \
    && pip install --no-cache-dir -r requirements.txt \
    && test -f tools/apply_course_studio.py \
    && python tools/apply_course_studio.py \
    && python tools/install_course_builder.py \
    && python tools/fix_course_builder_response_types.py \
    && chmod +x start.sh \
    && python -m compileall -q app \
    && python -c "from app.main import app; assert any(getattr(r, 'path', '') == '/course-studio' for r in app.routes)"

EXPOSE 8000
CMD ["./start.sh"]
