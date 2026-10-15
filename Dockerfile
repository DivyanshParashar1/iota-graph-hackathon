# Ripple: single container (API + UI). Not built or run in the build session: see docs/KNOWN_ISSUES.md.
# Build: docker build -t ripple .
# Run (embedded FalkorDB, data in a volume):  docker run -p 8000:8000 -v ripple-data:/app/var ripple
# Run against a FalkorDB server:              docker run -p 8000:8000 -e RIPPLE_DB_MODE=remote -e FALKORDB_HOST=... ripple
#
# The container has no `claude` CLI, so with RIPPLE_LLM_PROVIDER=claude_code it needs the host-side bridge:
#   host$ .venv/bin/python -m ripple.claude_code_bridge
#   docker run ... -e CLAUDE_CODE_BRIDGE_URL=http://host.docker.internal:8765 ripple
# Or give it a key instead: -e RIPPLE_LLM_PROVIDER=openrouter -e OPENROUTER_API_KEY=...

FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    RIPPLE_DB_MODE=embedded RIPPLE_DB_PATH=/app/var/ripple.db RIPPLE_TENANTS_DIR=/app/var/tenants
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY ripple/ ripple/
COPY graph/ graph/
COPY scripts/ scripts/
COPY eval/ eval/
COPY pyproject.toml ./
COPY --from=ui /ui/dist ui/dist
ENV PYTHONPATH=/app
EXPOSE 8000
# /app/var holds the graph and each tenant's uploads and exported expert prompts: mount it to keep them.
VOLUME ["/app/var"]
CMD ["uvicorn", "ripple.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
