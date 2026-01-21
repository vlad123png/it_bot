import logging

from aiogram import Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.callbacks import TimezoneCallback
from src.db.models import User
from src.db.users import change_user_timezone
from src.utils import active_user

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(TimezoneCallback.filter())
@active_user
async def get_broadcast_message(
        callback_query: types.CallbackQuery,
        callback_data: TimezoneCallback,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """ Изменяет часовой пояс пользователя """
    offset: int = callback_data.offset
    await change_user_timezone(db_session, user, offset)
    await callback_query.answer(text=messages.TIMEZONE_CHANGED.format(callback_data.timezone), show_alert=True)
    await callback_query.message.delete()
    logger.info('Пользователь %s сменил часовой пояс на %s', user.id, callback_data.timezone)
