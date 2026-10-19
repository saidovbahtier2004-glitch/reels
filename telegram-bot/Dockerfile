FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 bot
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot ./bot
USER bot

CMD ["python", "-m", "bot"]
