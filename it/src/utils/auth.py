from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Union

from aiogram import types

from src.api_client import APIClient
from src.config.settings import settings
from src.db.models import User
from src.messages import SESSION_EXPIRED_MESSAGE
from . import api
from .cleanup import cleanup


def check_auth(
    auth_time,
    duration: timedelta = settings.AUTH_DURATION
) -> bool:
    """
    Проверяет время аутентификации пользователя.

    :param auth_time: Время аутентификации
    :type auth_time: datetime
    :param duration: Время действия аутентификации
    :type duration: timedelta

    :return: True, если время аутентификации не истекло
    :rtype: bool
    """
    return datetime.now(timezone.utc) - auth_time <= duration


def is_authenticated(user: User) -> bool:
    """
    Проверяет, истекла ли аутентификация пользователя.

    :param user: Пользователь
    :type user: User

    :return: True, если аутентификация не истекла
    :rtype: bool
    """
    return (
        user.auth_logs
        and check_auth(user.auth_logs[0].auth_time)
    )


async def is_archive(api_client: APIClient, user_id: int) -> bool:
    """
    Проверяет, является ли пользователь архивным.

    :param api_client: Экземпляр API клиента
    :type api_client: APIClient
    :param user_id: Идентификатор пользователя в Inventive
    :type user_id: int

    :return: True, если пользователь архивный
    :rtype: bool
    """
    user = await api.get_user_by_id(api_client, user_id)
    return not user or user['IsArchive']


def active_user(handler):
    """Декоратор, проверяющий активного пользователя."""
    @wraps(handler)
    async def wrapper(
        event: Union[types.Message, types.CallbackQuery],
        *args, **kwargs
    ):
        user, api_client = kwargs['user'], kwargs['api_client']
        if (
            user
            and is_authenticated(user)
            and not await is_archive(api_client, user.inventive_id)
        ):
            return await handler(event, *args, **kwargs)
        else:
            if isinstance(event, types.Message):
                await event.answer(SESSION_EXPIRED_MESSAGE)
                await event.delete()
            elif isinstance(event, types.CallbackQuery):
                await event.message.answer(SESSION_EXPIRED_MESSAGE)
            else:
                raise RuntimeError('active_user: неожиданный тип события.')
            await cleanup(kwargs['state'])

    return wrapper
