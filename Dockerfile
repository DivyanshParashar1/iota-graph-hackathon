# Ripple: single container (API + UI). Not run in the build session (no Docker there): see docs/KNOWN_ISSUES.md.
# Build: docker build -t ripple .
# Run (embedded FalkorDB, data in a volume):  docker run -p 8000:8000 -v ripple-data:/app/var ripple
# Run against a FalkorDB server:              docker run -p 8000:8000 -e RIPPLE_DB_MODE=remote -e FALKORDB_HOST=... ripple

FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RIPPLE_DB_MODE=embedded RIPPLE_DB_PATH=/app/var/ripple.db
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY ripple/ ripple/
COPY graph/ graph/
COPY data/ data/
COPY eval/ eval/
COPY scripts/ scripts/
COPY pyproject.toml ./
COPY --from=ui /ui/dist ui/dist
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "ripple.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
