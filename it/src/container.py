from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.api_client import APIClient
from src.config.settings import settings
from src.db.db_connection import sync_engine
from src.smtp_client import SMTPClient


@dataclass
class AppContainer:
    """Контейнер с глобальными переменными. Используется в единственном экземпляре."""
    bot: Bot = field(init=False)
    scheduler: AsyncIOScheduler = field(init=False)
    smtp_client: SMTPClient = field(init=False)
    api_client: APIClient = field(init=False)

    def __post_init__(self):
        self.bot = Bot(
            token=settings.TG_TOKEN.get_secret_value(),
            default=DefaultBotProperties(parse_mode='HTML')
        )
        self.scheduler = AsyncIOScheduler(
            jobstores={
                'default': SQLAlchemyJobStore(engine=sync_engine)
            }
        )

        self.smtp_client = SMTPClient(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            settings.HOST_USERNAME,
            settings.HOST_PASSWORD.get_secret_value(),
            settings.USE_SSL
        )

        self.api_client = APIClient(
            settings.API_LOGIN,
            settings.API_PASSWORD.get_secret_value(),
            settings.API_URL,
            settings.CACHE_TIMEOUT
        )


app_container = AppContainer()
