FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk cron && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 VOICEVOX_URL=http://voicevox:50021 VOICEVOX_AUTO_START=0 FFMPEG_BIN=ffmpeg FFPROBE_BIN=ffprobe
CMD ["python", "-m", "generator.run_daily"]
