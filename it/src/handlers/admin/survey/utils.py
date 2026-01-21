import asyncio
import datetime
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.config.settings import settings
from src.db.models import Survey, User
from src.handlers.admin.utils import update_change_broadcast_keyboard
from src.handlers.assistant.utils import delete_parasite_messages

logger = logging.getLogger('user_activity')


async def check_survey_finished(callback_query: CallbackQuery, user: User, survey: Survey) -> bool:
    """
    Проверяет завершён ли опрос с учётом часового пояса пользователя и уведомляет его, если опрос завершён.
    :param callback_query: Объект aiogram
    :param user: Пользователь
    :param survey: Опрос
    :return: True - если опрос ещё не завершён, иначе False
    """
    # Создаем timezone пользователя
    user_tz = datetime.timezone(datetime.timedelta(hours=user.timezone))

    # Получаем текущее время в timezone пользователя
    now_user_tz = datetime.datetime.now(user_tz)

    # Конвертируем время окончания опроса в timezone пользователя
    survey_end_user_tz = survey.end_date.astimezone(user_tz)

    if survey_end_user_tz < now_user_tz:
        try:
            await callback_query.answer(text=messages.SURVEY_IS_FINISHED)
            await callback_query.message.delete()
        except TelegramBadRequest:
            logging.warning(f'Не удалось ответить пользователю %s об окончании опроса.', user.id)
        logger.info(f'Пользователь попытался пройти завершённый опрос %s.', survey.id)
        return False
    return True


async def answer_user_after_edit_survey(
        bot: Bot,
        db_session: AsyncSession,
        chat_id: int,
        user_id: int,
        admin_panel_message_id: int
):
    """
    Уведомление пользователя об именении опроса. Очищает чат от ненужных сообщений.
    :param bot: Aiogram бот
    :param db_session: Асинхронная сессия с БД
    :param chat_id: Идентификатор чата в telgram
    :param user_id: Идентификатор пользователя
    :param admin_panel_message_id: Идентификатор сообщения с административной панелью в чате
    """
    try:
        # Ответ пользователю, обновление клавиатуры админ панели, очистка ненужных сообщений
        answer_message = await bot.send_message(text=messages.SURVEY_UPDATED, chat_id=chat_id)
        await delete_parasite_messages(bot, db_session, chat_id)
        await update_change_broadcast_keyboard(
            bot,
            db_session,
            user_id,
            chat_id,
            admin_panel_message_id
        )
        await asyncio.sleep(settings.SLEEP_TIME)
        await answer_message.delete()
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка отправки сообщения пользователю %s при изменении текста опроса: %s', user_id, e)
