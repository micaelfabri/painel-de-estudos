# Etapa 1: compila o frontend (React + Vite)
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Etapa 2: API (FastAPI) servindo o frontend compilado
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PAINEL_DB_PATH=/app/data/painel.db

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# Usuário sem privilégio para a API (auditoria de segurança); o entrypoint troca para ele
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data /app/secrets && chown app:app /app/data /app/secrets \
    && chmod +x /app/backend/entrypoint.sh

EXPOSE 8000
CMD ["/app/backend/entrypoint.sh"]
