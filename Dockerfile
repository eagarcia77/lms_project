FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python tools/apply_source_overlay.py && chmod +x start.sh
EXPOSE 8000
CMD ["./start.sh"]
