import logging.config
import os

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

from src.config.settings import settings


def setup_dirs() -> None:
    """
    Создает директории, указанные в настройках.
    """
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    os.makedirs(settings.TEMP_FILES_DIR, exist_ok=True)


def setup_logging() -> None:
    """
    Настраивает логи на основе конфигурации в настройках.
    """
    logging.config.dictConfig(settings.LOGGING_CONFIG)


def cleanup_temp_dir(directory: str) -> None:
    """
    Удаляет временные файлы.
    """
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            cleanup_temp_dir(item_path)
            os.rmdir(item_path)


async def configure_bot_commands(bot: Bot) -> None:
    """настраивает комманды бота"""
    await bot.set_my_commands(
        [
            BotCommand(command='start', description='Начать заново'),
            BotCommand(
                command='about',
                description='🤖 Возможности'
            ),
            BotCommand(
                command='help',
                description='📘 Инструкция'
            ),
            BotCommand(
                command='feedback',
                description='💬 Обратная связь'
            ),
            BotCommand(
                command='agreement',
                description='🎓 Согласие'
            ),
            BotCommand(
                command='timezone',
                description='⏰ Часовой пояс'
            ),
            BotCommand(
                command='admin',
                description='🛠️ Панель администратора'
            ),
            BotCommand(
                command='cancel',
                description='Отменить текущую операцию'
            ),
            BotCommand(
                command='switch_user',
                description='🔄 Сменить пользователя'
            ),
        ],
        BotCommandScopeDefault()
    )
