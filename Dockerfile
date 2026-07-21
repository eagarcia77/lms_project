FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .
RUN python tools/apply_v3.py \
    && pip install --no-cache-dir -r requirements.txt \
    && chmod +x start.sh \
    && python -m compileall -q app
EXPOSE 8000
CMD ["./start.sh"]
