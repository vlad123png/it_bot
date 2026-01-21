# Подключаем .env — чтобы переменные были доступны в make
include .env
export

.PHONY: build run lint revision migrate rollback down logs up stop

# Определяем COMPOSE_FILE на основе CONTOUR (по умолчанию prod)
ifeq ($(CONTOUR), DEV)
COMPOSE_FILE ?= docker-compose.dev.yaml
else
COMPOSE_FILE ?= docker-compose.yaml
endif

# Определяем PROJECT_NAME на основе .env и приводим к безопасному формату
UNSAFE_PROJECT_NAME := $(strip $(if $(APP_NAME),$(APP_NAME),$(if $(CONTOUR),myapp-$(CONTOUR),myapp)))
SAFE_PROJECT_NAME := $(shell echo '$(UNSAFE_PROJECT_NAME)' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g')
PROJECT_NAME := $(if $(SAFE_PROJECT_NAME),$(SAFE_PROJECT_NAME),myapp)

# Docker Compose команда с project name и выбранным файлом
DC := docker compose -p $(PROJECT_NAME) -f $(COMPOSE_FILE) --env-file .env

# Собираем образ
build:
	$(DC) build

# Запускаем бота (и БД, если нужно)
up:
	$(DC) up -d --build

# Останавливаем бота
stop:
	$(DC) stop

down:
	$(DC) down

# Логи
logs:
	$(DC) logs -f retail_bot

# Миграции — выполняем внутри контейнера бота
migrate:
	$(DC) exec retail_bot alembic upgrade head

revision:
ifndef NAME
	$(error NAME is undefined, try: make revision NAME="описание изменений")
endif
	$(DC) exec retail_bot alembic revision --autogenerate -m "$(NAME)"

rollback:
ifndef NUM
	$(error NUM is undefined, try: make rollback NUM="-1" or NUM="base")
endif
	$(DC) exec retail_bot alembic downgrade $(NUM)

# Помощь
help:
	@echo "🛠️  Available commands:"
	@echo "   make up           # Запустить сервисы"
	@echo "   make down         # Остановить и удалить"
	@echo "   make logs         # Показать логи"
	@echo "   make build        # Пересобрать образ"
	@echo "   make migrate      # Применить миграции"
	@echo "   make revision NAME='...' # Создать миграцию"
	@echo "   make rollback NUM=-1     # Откатить миграции"
	@echo ""
	@echo "💡 Используй: ENV=dev make ... для dev-окружения"
	@echo "   (например: ENV=dev make up)"