from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.db.users import get_user_by_telegram_id


class UserMiddleware(BaseMiddleware):
    """
    Middleware для передачи пользователя в обработчики.
    """
    async def __call__(
            self,
            handler: Callable[
                [TelegramObject, Dict[str, Any]], Awaitable[Any]
            ],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        if event.message:
            telegram_id = event.message.from_user.id
        elif event.callback_query:
            telegram_id = event.callback_query.from_user.id
        else:
            raise RuntimeError('UserMiddleware: неожиданный тип события.')

        if 'db_session' not in data:
            raise RuntimeError('UserMiddleware: база данных не найдена.')

        user = await get_user_by_telegram_id(
            data['db_session'],
            telegram_id
        )
        data['user'] = user

        return await handler(event, data)
