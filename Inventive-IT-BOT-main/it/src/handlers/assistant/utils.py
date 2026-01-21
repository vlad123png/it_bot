import asyncio
import datetime
import logging
import os
import random
import traceback
from typing import Any

from aiogram import Bot, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputMediaPhoto, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.backend_api import BackendAPI
from src.backend_api.error import BaseBackendAPIError
from src.backend_api.schemas import CreateRetailMessagesSchema, DownloadedFile
from src.config.settings import settings
from src.db.models import User
from src.db.users import check_user_request_to_ai, increment_user_request_to_ai
from src.db.utils import (
    get_all_parasite_messages_by_chat_id,
    delete_all_parasite_messages_by_chat_id,
    save_parasite_message,
)
from src.keyboards.inline import get_reaction_keyboard
from src.smtp_client import SMTPClient
from src.utils.cleanup import remove_user_voice_messages
from src.utils.users import is_ared
from src.voice_transcription.transcription_orchestrator import get_transcription_orchestrator


async def delete_parasite_messages(
        bot: Bot,
        db_session: AsyncSession,
        chat_id: int,
):
    """
    Удаляет паразитные сообщения из чата и из БД.
    :param bot: Объект telegram бот
    :param db_session: БД
    :param chat_id: ID чата с пользователем
    """
    parasite_messages = [msg.message_id for msg in await get_all_parasite_messages_by_chat_id(db_session, chat_id)]
    if parasite_messages:
        try:
            await bot.delete_messages(chat_id, parasite_messages)
        except TelegramBadRequest:
            logging.warning('Не удалось удалить паразитные сообщения для чата %s', chat_id)
    await delete_all_parasite_messages_by_chat_id(db_session, chat_id)


async def process_voice_message(message: types.Message, bot: Bot, user_id: int) -> str:
    """
     Обработка голосового сообщения. Транслирует голосовое сообщение в текст.
    :param message: Объект сообщения из aiogram
    :param bot: Обхект бота aiogram
    :param user_id: Идентификатор пользователя
    :return: Возврщает текст полученный из голосового сообщения.
    """
    text = ''
    if message.voice:
        try:
            now = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H-%M-%S')
            path = f'user_voice_messages/{user_id}/inbox_{now}_voice.ogg'
            os.makedirs(os.path.dirname(path), exist_ok=True)
            await bot.download(message.voice.file_id, path)
            transcription_orchestrator = await get_transcription_orchestrator()
            text = await transcription_orchestrator.recognize(path)
            remove_user_voice_messages(user_id)
        except TelegramBadRequest as e:
            logging.warning(f'Ошибка ответа пользователю %s при обработке голосового сообщения: %s', user_id, e)
    else:
        text = message.text
    return text


async def check_text_message_for_empty(text: str, message: types.Message, db_session: AsyncSession) -> bool:
    """
    Проверяет содержимое сообщения на пустоту и отправляет сообщение пользователю о повторном вводе.
    :param text: Текст для проверки
    :param message: Объект сообщения из aiogram
    :param db_session: Асинхронная сессия с БД
    :return: False - если текст пустой.
    """
    if not text:
        try:
            await message.delete()
            answer_message: types.Message = await message.answer(text=messages.EMPTY_MESSAGE)
            await save_parasite_message(db_session, message.chat.id, answer_message.message_id)
        except TelegramBadRequest:
            logging.exception(f'Не удалось удалить пустое сообщение пользователя.')
        return False
    return True


async def process_question(
        message: types.Message,
        user_question: str,
        user: User,
        db_session: AsyncSession,
        backend_service: BackendAPI,
        smtp_client: SMTPClient
):
    """
    Обрабатывает запрос пользователя к базе знаний.
    """
    # Отправка сообщения об ожидании
    text_pause = random.choice(messages.LIST_PAUSE)
    pause_message: types.Message = await message.answer(text=str(text_pause), parse_mode=ParseMode.MARKDOWN)

    try:
        params: dict[str, Any] = dict(content=user_question, is_ared=is_ared(user.inventive_email))

        if user.backend_id:
            params["user_id"] = user.backend_id
        else:
            params["external_id"] = user.id

        data = CreateRetailMessagesSchema(**params)
        response = await backend_service.generate_retail_answer(data)
    except BaseBackendAPIError as e:
        error_message = await message.answer(text=messages.APOLOGIZE_MESSAGE)
        await save_parasite_message(db_session, message.chat.id, error_message.message_id)
        await pause_message.delete()

        # Отправка сообщения об ошибке на почту
        await smtp_client.send_email(
            settings.HELP_EMAIL,
            messages.ERROR_SUBJECT,
            messages.ERROR_EMAIL_MESSAGE.format(user.id, user_question, traceback.format_exc()),
            settings.ERROR_EMAIL
        )
        return

    text = response.content[:4096]
    inline_keyboard = get_reaction_keyboard(response.id, response.task_id) if response.is_answer else None

    if response.images:
        try:
            tasks = [backend_service.download_teamly_file(url) for url in response.images[:10]]
            images: list[DownloadedFile] = await asyncio.gather(*tasks)
            media = []
            for idx, img in enumerate(images):
                if not img:
                    continue
                file = BufferedInputFile(img.content, filename=f"image_{idx}.jpg")
                media.append(InputMediaPhoto(media=file))
            if media:
                await message.answer_media_group(media=media)
        except BaseBackendAPIError as e:
            logging.warning('Не удалось загрузить изображения! Error: %s', e)

    try:
        await message.answer(
            text=text,
            reply_markup=inline_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except TelegramBadRequest:
        # Возможна ошибка возникновения markdown разметки.
        await message.answer(
            text=text,
            reply_markup=inline_keyboard,
            parse_mode=ParseMode.HTML
        )

    await increment_user_request_to_ai(db_session, user.id)
    await pause_message.delete()


async def check_user_quantity_to_llm(message: types.Message, db_session: AsyncSession, user: User) -> bool:
    """ Проверка количества вопросов пользователя к ИИ за сутки """
    if not await check_user_request_to_ai(db_session, user.id):
        warning_message: types.Message = await message.answer(messages.TEXT_STOP_COUNT)
        await save_parasite_message(db_session, message.chat.id, warning_message.message_id)
        await message.delete()
        return False
    return True
