import asyncio
import logging

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from src.backend_api import BackendAPI
from src.backend_api.schemas import CreateRetailFeedbackSchema
from src.callbacks import FeedbackType
from src.config.settings import settings
from src.db.models import User


async def handle_request(
        message: types.Message,
        state: FSMContext,
        backend_service: BackendAPI,
        user: User,
        feedback: str,
        answer_message: str
):
    await state.clear()
    response_message = await message.answer(answer_message)
    data: dict = {"content": feedback}
    if user.backend_id:
        data["user_id"] = user.backend_id
    else:
        data["external_id"] = user.id,

    await backend_service.send_retail_feedback(CreateRetailFeedbackSchema(**data))
    try:
        await message.delete()
        await asyncio.sleep(settings.SLEEP_TIME)
        await response_message.delete()
    except TelegramBadRequest:
        logging.info(f'Ошибка удаления сообщений.')
