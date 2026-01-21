import logging

from aiogram import Router, F, types, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.backend_api import BackendAPI
from src.db.models import User
from src.handlers.assistant.utils import (
    process_voice_message,
    check_text_message_for_empty,
    delete_parasite_messages,
)
from src.states.bot_feedback_state import FeedbackBot
from src.utils import active_user
from .utils import handle_request

router = Router()


@router.callback_query(F.data == 'send-feedback')
async def send_feedback(
        callback: types.CallbackQuery,
        state: FSMContext,

):
    """
    Обработка кнопки по предложению идеи.
    Отправляет сообщение пользователя на почту технической поддержки.
    """
    await state.set_state(FeedbackBot.WaitingMessage)
    await callback.answer(messages.FEEDBACK_BOT_REQUEST, show_alert=True)


@router.message(FeedbackBot.WaitingMessage)
@active_user
async def get_feedback_bot_text(
        message: types.Message,
        bot: Bot,
        state: FSMContext,
        db_session: AsyncSession,
        backend_service: BackendAPI,
        user: User,
        *args, **kwargs
):
    """
    Отправляет сообщение с feedback пользователя на email технической поддержки.
    """
    try:
        feedback = await process_voice_message(message, bot, user.id)
        if await check_text_message_for_empty(feedback, message, db_session):
            await delete_parasite_messages(message.bot, db_session, message.chat.id)
            await handle_request(
                message,
                state,
                backend_service,
                user,
                feedback,
                messages.FEEDBACK_BOT_RESPONSE
            )
    except TelegramBadRequest as e:
        logging.warning(f'Телеграм ошибка при обработке фитбэка от пользователя %s: %s', user.id, e)
