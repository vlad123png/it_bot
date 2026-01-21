import logging

from aiogram import Router, F, types, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.backend_api import BackendAPI
from src.db.models import User
from src.handlers.assistant.utils import (
    process_question,
    delete_parasite_messages,
    check_user_quantity_to_llm, process_voice_message
)
from src.smtp_client import SMTPClient
from src.utils import antiflood, active_user

router = Router()


@router.message(F.voice, StateFilter(None))
@antiflood
@active_user
async def process_voice_question(
        message: types.Message,
        bot: Bot,
        db_session: AsyncSession,
        user: User,
        backend_service: BackendAPI,
        smtp_client: SMTPClient,
        *args,
        **kwargs
):
    """Обработка голосового вопроса пользоват к базе знаний"""
    try:
        # Удаляем паразитные сообщения в чате пользователя
        await delete_parasite_messages(bot, db_session, message.chat.id)

        # Проверка количества обращений пользователя
        if not await check_user_quantity_to_llm(message, db_session, user):
            return

        # Скачивает файл и сораняем
        recognize_text_message = await message.answer(messages.TEXT_RECOGNIZE_MESSAGE)
        user_question = await process_voice_message(message, message.bot, user.id)
        if not user_question:
            await recognize_text_message.edit_text(text=messages.EMPTY_MESSAGE)
            return

        await recognize_text_message.edit_text(text=f'Ваш вопрос: {user_question}')
        await process_question(message, user_question, user, db_session, backend_service, smtp_client)
        await message.delete()
    except TelegramBadRequest as e:
        logging.error(f'Не удалось ответить на вопрос пользователя %s: %s', user.id, e)
