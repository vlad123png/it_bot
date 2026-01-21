import logging
from functools import wraps
from typing import Union

from aiogram import types
from aiogram.exceptions import TelegramBadRequest

from src.db.models import User, UserRole
from src.db.utils import save_parasite_message
from src.messages import ONLY_ADMIN_ACCESS
from src.utils.cleanup import cleanup


def admin(handler):
    """
    Декоратор для ограничения доступа только для админов.
    """

    @wraps(handler)
    async def wrapper(
            event: Union[types.Message, types.CallbackQuery],
            *args, **kwargs
    ):
        user: User = kwargs['user']
        if user and user.role == UserRole.ADMIN:
            return await handler(event, *args, **kwargs)
        else:
            if isinstance(event, types.Message):
                try:
                    admin_message = await event.answer(ONLY_ADMIN_ACCESS)
                    await event.delete()
                    await save_parasite_message(kwargs['db_session'], event.chat.id, admin_message.message_id)
                except TelegramBadRequest as e:
                    logging.info('Не удалось удалить сообщение. %s', e)
            elif isinstance(event, types.CallbackQuery):
                admin_message = await event.message.answer(ONLY_ADMIN_ACCESS)
                await save_parasite_message(kwargs['db_session'], event.message.chat.id, admin_message.message_id)
            else:
                raise RuntimeError('active_user: неожиданный тип события.')
            state = kwargs['state']
            if state:
                await cleanup(state)

    return wrapper
