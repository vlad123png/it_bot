from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.backend_api.factory import get_backend_api


class BackendServiceSessionMiddleware(BaseMiddleware):
    """
    Middleware для передачи backend service в обработчики.
    """

    def __init__(self):
        super().__init__()

    async def __call__(
            self,
            handler: Callable[
                [TelegramObject, Dict[str, Any]], Awaitable[Any]
            ],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        data['backend_service'] = get_backend_api()
        result = await handler(event, data)
        return result
