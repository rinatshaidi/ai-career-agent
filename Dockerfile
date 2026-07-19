FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN addgroup --system --gid 10001 jobmonitor \
    && adduser --system --uid 10001 --ingroup jobmonitor --home /app jobmonitor

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY config.py main.py analyze.py notify.py profile_bot.py pair_telegram.py worker.py healthcheck.py ./
COPY models ./models
COPY providers ./providers
COPY services ./services
COPY storage ./storage
COPY utils ./utils

RUN mkdir -p /app/data /app/logs \
    && chown -R jobmonitor:jobmonitor /app

USER jobmonitor

CMD ["python", "worker.py"]
