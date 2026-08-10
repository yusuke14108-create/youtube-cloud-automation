FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Tokyo \
    FFMPEG_BIN=/usr/bin/ffmpeg \
    JP_FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc \
    JP_FONT_REGULAR_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
    SUBTITLE_FONT="Noto Sans CJK JP" VOICEVOX_AUTO_START=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-noto-cjk tzdata ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "generator.scheduler"]
