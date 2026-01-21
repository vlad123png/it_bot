from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware для передачи сессии базы данных в обработчики.
    """

    def __init__(self, async_session: async_sessionmaker):
        self.async_session = async_session
        super().__init__()

    async def __call__(
            self,
            handler: Callable[
                [TelegramObject, Dict[str, Any]], Awaitable[Any]
            ],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        async with self.async_session() as session:
            data['db_session'] = session
            result = await handler(event, data)
        return result
