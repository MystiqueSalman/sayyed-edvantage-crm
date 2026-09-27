FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Persistent data (Railway volume) can be mounted here; env vars point at it.
ENV SQLITE_PATH=/app/data/lms.db \
    UPLOAD_DIR=/app/data/uploads
RUN mkdir -p /app/data/uploads /app/app/static/img/banners

EXPOSE 5000

# Seed demo data on every start (seed.py is idempotent: skips existing rows),
# then serve. Railway injects $PORT at runtime.
CMD ["sh", "-c", "python seed.py && gunicorn run:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120"]
