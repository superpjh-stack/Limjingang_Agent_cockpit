FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app.py README.md .env.example ./
COPY assets ./assets
COPY .streamlit ./.streamlit
COPY imjingang_agent ./imjingang_agent
COPY sample_docs ./sample_docs
COPY scripts ./scripts
COPY data/imjingang_demo.db ./data/imjingang_demo.db

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]
