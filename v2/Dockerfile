FROM node:22-slim AS web
WORKDIR /build
COPY v2/web/package.json v2/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY v2/web ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY v2/requirements.lock ./v2/requirements.lock
RUN pip install --no-cache-dir -r v2/requirements.lock
COPY imjingang_agent ./imjingang_agent
COPY sample_docs ./sample_docs
COPY v2/__init__.py v2/api.py v2/work.py v2/metrics.py v2/manage_users.py ./v2/
COPY --from=web /build/dist ./v2/web/dist
RUN useradd --create-home cockpit && mkdir /app/data && chown cockpit:cockpit /app/data
USER cockpit
EXPOSE 8510
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8510/api/health', timeout=4)"
CMD ["uvicorn", "v2.api:app", "--host", "0.0.0.0", "--port", "8510"]
