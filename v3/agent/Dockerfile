FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 V3_SQLITE_PATH=data/imjingang_v3_demo.db
WORKDIR /app
COPY v3/requirements.txt ./v3/requirements.txt
RUN pip install --no-cache-dir -r v3/requirements.txt
COPY imjingang_agent ./imjingang_agent
COPY v3 ./v3
RUN useradd --create-home agentruntime && mkdir -p /app/data && chown -R agentruntime:agentruntime /app/data
USER agentruntime
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/ping', timeout=4)"
CMD ["uvicorn", "v3.agent.runtime:app", "--host", "0.0.0.0", "--port", "8080"]
