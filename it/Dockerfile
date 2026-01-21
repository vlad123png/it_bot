FROM python:3.12-slim
LABEL authors="crusazer"

WORKDIR /app
COPY requirements.txt .

# Устанавливаем системные зависимости + netcat для wait-скриптов
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ netcat-openbsd ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

# Создаём директорию для логов
RUN mkdir -p /usr/app/src/log

COPY .. /app
RUN chmod +x /app/start_bot.sh

CMD /app/start_bot.sh
