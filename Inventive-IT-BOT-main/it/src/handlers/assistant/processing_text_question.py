import logging

from aiogram import F, types, Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend_api import BackendAPI
from src.db.models import User
from src.handlers.assistant.utils import delete_parasite_messages, process_question, check_user_quantity_to_llm
from src.smtp_client import SMTPClient
from src.utils import active_user
from src.utils.antiflood import antiflood

router = Router()


@router.message(F.text, StateFilter(None))
@antiflood
@active_user
async def process_text_question(
        message: types.Message,
        bot: Bot,
        user: User,
        db_session: AsyncSession,
        backend_service: BackendAPI,
        smtp_client: SMTPClient,
        *args,
        **kwargs
):
    """ Обрабатывает запрос пользователя к базе знаний. """
    try:
        # Удаляем паразитные сообщения в чате пользователя
        await delete_parasite_messages(bot, db_session, message.chat.id)

        # Проверка количества обращений пользователя к ИИ за сутки
        if not await check_user_quantity_to_llm(message, db_session, user):
            return

        user_question = message.text.strip()
        await process_question(message, user_question, user, db_session, backend_service, smtp_client)
    except TelegramBadRequest as e:
        logging.error(f'Не удалось ответить на вопрос пользователя %s: %s', user.id, e)
