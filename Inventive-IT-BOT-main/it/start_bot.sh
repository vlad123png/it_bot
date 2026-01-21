#!/bin/sh

# Ждём MySQL
while ! nc -z postgres 5432; do
  echo "⏳ Ожидаем Postgres..." >&2
  sleep 2
done

# Ждём Redis
while ! nc -z redis 6379; do
  echo "⏳ Ожидаем Redis..." >&2
  sleep 2
done

echo "Applying migrations..."
if alembic upgrade head; then
    echo "✅ Миграции успешно применены."
else
    echo "❌ Ошибка при применении миграций Alembic!" >&2
    exit 1
fi

echo "Starting the bot..."
python bot.py