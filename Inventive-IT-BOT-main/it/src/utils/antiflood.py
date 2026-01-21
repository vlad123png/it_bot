from functools import wraps

from aiogram import types
from cachetools import TTLCache

from src.config.settings import settings
from src.db.utils import save_parasite_message
from src.messages import ANTIFLOOD_MESSAGE

cache = TTLCache(maxsize=1000, ttl=settings.ANTIFLOOD_TIMEOUT)


def antiflood(handler):
    """
    Aнти-флуд декоратор.
    """
    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = message.from_user.id
        if cache.get(user_id):
            antiflood_message = await message.answer(ANTIFLOOD_MESSAGE)
            await save_parasite_message(kwargs['db_session'], message.chat.id, antiflood_message.message_id)
            await message.delete()
        else:
            cache[user_id] = True
            return await handler(message, *args, **kwargs)
    return wrapper
