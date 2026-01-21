import asyncio
import os
import platform

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from src.api_client import APIClient
from src.config.settings import settings
from src.container import app_container
from src.db.db_connection import async_session_maker
from src.handlers import auth, service, assistant, error, commands, task, help, admin, timezone
from src.middlewares import (
    DbSessionMiddleware,
    UserMiddleware,
    APIClientMiddleware,
    SMTPClientMiddleware,
    MiddlewareLogger,
)
from src.middlewares.backend_service import BackendServiceSessionMiddleware
from src.middlewares.mediagroup_middleware import MediaGroupMiddleware
from src.scheduler.scheduler import start_scheduler
from src.utils.start_bot import cleanup_temp_dir, configure_bot_commands, setup_dirs, setup_logging
from src.voice_transcription.transcription_orchestrator import initialize_transcription_orchestrator

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


async def main():
    """
    Запускает бота.
    """
    cleanup_temp_dir(settings.TEMP_FILES_DIR)
    api_client = APIClient(
        settings.API_LOGIN,
        settings.API_PASSWORD.get_secret_value(),
        settings.API_URL,
        settings.CACHE_TIMEOUT
    )
    storage = RedisStorage.from_url(settings.REDIS.redis_url)

    await initialize_transcription_orchestrator()  # инициализация моделей трансгрибации
    await start_scheduler()

    # Добавление роуторов и middleware
    dp = Dispatcher(storage=storage)
    dp.update.middleware(MediaGroupMiddleware(latency=2))
    dp.update.middleware(APIClientMiddleware(api_client))
    dp.update.middleware(DbSessionMiddleware(async_session_maker))
    dp.update.middleware(SMTPClientMiddleware(app_container.smtp_client))
    dp.update.middleware(BackendServiceSessionMiddleware())
    dp.update.middleware(MiddlewareLogger())
    dp.update.middleware(UserMiddleware())

    dp.include_routers(
        commands.router,
        auth.router,
        service.router,
        admin.router,
        task.router,
        error.router,
        help.router,
        assistant.router,
        timezone.router,
    )

    bot = app_container.bot
    await configure_bot_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        if api_client.session:
            await api_client.session.close()


if __name__ == '__main__':
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )

    setup_dirs()
    setup_logging()

    asyncio.run(main())
