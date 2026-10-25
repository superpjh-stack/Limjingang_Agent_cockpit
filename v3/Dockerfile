FROM node:22-slim AS web
WORKDIR /build
COPY v3/web/package.json v3/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY v3/web ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 V3_SQLITE_PATH=data/imjingang_v3_demo.db
WORKDIR /app
COPY v3/requirements.txt ./v3/requirements.txt
RUN pip install --no-cache-dir -r v3/requirements.txt
COPY imjingang_agent ./imjingang_agent
COPY v3 ./v3
COPY --from=web /build/dist ./v3/web/dist
RUN useradd --create-home agentv3 && mkdir -p /app/data && chown -R agentv3:agentv3 /app/data
USER agentv3
EXPOSE 8510
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8510/api/health', timeout=4)"
CMD ["uvicorn", "v3.api:app", "--host", "0.0.0.0", "--port", "8510"]
