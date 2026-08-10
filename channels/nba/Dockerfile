FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FFMPEG_BIN=/usr/bin/ffmpeg \
    FONT_BOLD=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc \
    FONT_REGULAR=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-noto-cjk ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY crawler crawler
COPY generator generator

CMD ["python", "-m", "generator.scheduler"]
