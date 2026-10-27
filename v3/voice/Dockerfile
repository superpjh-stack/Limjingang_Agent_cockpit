FROM public.ecr.aws/docker/library/python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AWS_REGION=ap-northeast-2
WORKDIR /app
COPY v3/voice/requirements.txt ./v3/voice/requirements.txt
RUN pip install --no-cache-dir -r v3/voice/requirements.txt
COPY v3 ./v3
RUN useradd --create-home voicev3 && chown -R voicev3:voicev3 /app
USER voicev3
EXPOSE 8080
CMD ["python", "-m", "v3.voice.runtime"]
