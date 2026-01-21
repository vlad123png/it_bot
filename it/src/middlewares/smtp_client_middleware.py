from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.smtp_client import SMTPClient


class SMTPClientMiddleware(BaseMiddleware):
    """
    Middleware для передачи SMTP клиента в обработчики.
    """
    def __init__(self, smtp_client: SMTPClient):
        self.smtp_client = smtp_client
        super().__init__()

    async def __call__(
            self,
            handler: Callable[
                [TelegramObject, Dict[str, Any]], Awaitable[Any]
            ],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        data['smtp_client'] = self.smtp_client
        return await handler(event, data)
