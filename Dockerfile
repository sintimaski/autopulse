FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTOPULSE_FRONTEND_STATIC_DIR=/app/frontend/out \
    AUTOPULSE_DATA_DIR=/data

WORKDIR /app

COPY backend/ /app/backend/
RUN pip install --no-cache-dir -e "/app/backend[parquet-s3]"

COPY --from=frontend-builder /app/frontend/out /app/frontend/out

EXPOSE 8000

CMD ["uvicorn", "autopulse_backend.main:app", "--app-dir", "/app/backend/src", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
