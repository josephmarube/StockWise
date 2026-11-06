# StockWise production image: one container serving the API and the built React app.
#   docker build -t stockwise .
#   docker run -p 8000:8000 --env-file backend/.env stockwise

# ---- 1. Build the frontend ----
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. API + static files ----
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    STATIC_DIR=/app/static \
    MIGRATE_ON_STARTUP=false \
    PORT=8000 \
    WEB_CONCURRENCY=2

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY --from=web /web/dist ./static

RUN useradd --system --uid 1001 app && chown -R app /app
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"

# Migrate once, then start the workers (hosts like Render set PORT).
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
