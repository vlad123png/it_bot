import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.db.broadcast_utils import get_user_active_broadcast_messages
from src.db.survey_utils import get_user_active_surveys
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards.admin_inline import (
    get_ai_settings_keyboard,
    get_general_settings_keyboard,
    create_my_active_broadcast_inline_keyboard
)


async def update_settings_keyboard_with_parameters(
        bot: Bot,
        chat_id: int,
        message_id: int,
        subclass_tag: str,
) -> None:
    """
    Обновляет инлайн клавиатуру админ панели с параметрами.
    Используется для того, чтобы после обновление параметра был заметно изменение в админ панеле.
    :param bot: Aiogram бот
    :param chat_id: идентификатор чата пользователя
    :param message_id: id сообщения в чате с настройками
    :param subclass_tag: Тип настроек. Используется для выбора инлайн клавиатуры (AI, general, knowledge bases)
    """
    try:
        if subclass_tag == 'AI':
            inline_keyboard_function = get_ai_settings_keyboard
        else:
            inline_keyboard_function = get_general_settings_keyboard

        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=inline_keyboard_function()
        )
    except TelegramBadRequest:
        logging.info("Не удалось обновить клавиатуру с настройками")


async def update_change_broadcast_keyboard(
        bot: Bot,
        db_session: AsyncSession,
        user_id: int,
        chat_id: int,
        message_id: int
):
    """
    Обновляет клавиатуру для изменения сообщений/опросов для рассылки
    :param bot: Aiogram бот
    :param db_session: Асинхронная сессия с БД
    :param user_id: Идентификатор пользователя
    :param chat_id: int: Идентификатор чата в telegram
    :param message_id: Идентификатор сообщения админ панели
    """
    try:
        broadcast_messages = await get_user_active_broadcast_messages(db_session, user_id)
        surveys = await get_user_active_surveys(db_session, user_id)
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=create_my_active_broadcast_inline_keyboard(broadcast_messages, surveys)
        )
    except TelegramBadRequest as e:
        logging.info(f'Не удалось обновить my_active_broadcast клавиатуру для пользователя %s: %s', chat_id, e)


async def delete_parasite_messages_and_update_change_broadcast_keyboard(
        callback_query: CallbackQuery,
        state: FSMContext,
        db_session: AsyncSession,
        user_id: int,
        message_id: int
):
    """
    Удаляет паразитные сообщения и обновляет инлайн клавиатуру изменения
    :param callback_query: Объект aiogram
    :param state: Состояние пользователя
    :param db_session: Асинхронная сессия с БД
    :param user_id: Идентификатор пользователя
    :param message_id: Идентификатор сообщения в чате telegram
    """
    await state.clear()
    await callback_query.answer(text=messages.DELETE_BROADCAST_SUCCESS, show_alert=True)
    await update_change_broadcast_keyboard(
        callback_query.bot,
        db_session,
        user_id,
        callback_query.message.chat.id,
        message_id
    )
    await callback_query.message.delete()
    await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
