from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine

from src.config.settings import settings


def init_database() -> AsyncEngine:
    """Инициализация подключения к базе данных"""
    database_url: str = (f'postgresql+psycopg_async://'
                         f'{settings.DB.USER_NAME}:'
                         f'{settings.DB.USER_PASSWORD.get_secret_value()}@'
                         f'{settings.DB.HOST_NAME}:'
                         f'{settings.DB.DB_PORT}/'
                         f'{settings.DB.DB_NAME}')
    return create_async_engine(database_url, pool_pre_ping=True, echo=False)


engine = init_database()
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

# Синхронный движок для планировщика!!!
sync_engine = create_engine(
    (f'postgresql+psycopg://'
     f'{settings.DB.USER_NAME}:'
     f'{settings.DB.USER_PASSWORD.get_secret_value()}@'
     f'{settings.DB.HOST_NAME}:'
     f'{settings.DB.DB_PORT}/'
     f'{settings.DB.DB_NAME}'),
    echo=False,
    pool_recycle=3600,
    pool_pre_ping=True
)


@asynccontextmanager
async def get_async_session() -> AsyncSession:
    """ Создаёт и закрывает асинхронную сессию с базой данных."""
    async with async_session_maker() as session:
        yield session # noqa
