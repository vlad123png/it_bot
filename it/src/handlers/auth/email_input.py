import asyncio

from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.api_client import APIClient
from src.config.settings import settings
from src.messages import (
    INVALID_EMAIL_MESSAGE,
    USER_IS_ARCHIVE_MESSAGE,
    USER_NOT_FOUND_MESSAGE
)
from src.smtp_client import SMTPClient
from src.states import AuthStates
from src.utils import api, is_email, text_only, antiflood
from .send_verification_code import send_verification_code

router = Router()


@router.message(AuthStates.EmailInput)
@antiflood
@text_only
async def process_email_input(
        message: types.Message,
        state: FSMContext,
        api_client: APIClient,
        db_session: AsyncSession,
        smtp_client: SMTPClient
):
    """
    Обрабатывает ввод адреса электронной почты.

    Вызывается при получении от пользователя адреса электронной почты
    в процессе аутентификации. Проверяет корректность введенного адреса,
    наличие пользователя с таким адресом в Inventive, и его статус.
    Если пользователь существует и не является архивным, инициируется
    отправка кода подтверждения для завершения процесса аутентификации.
    """
    email = message.text.strip()
    if not is_email(email):
        answer_message = await message.answer(INVALID_EMAIL_MESSAGE)
        await asyncio.sleep(settings.SLEEP_TIME)
        await answer_message.delete()

    else:
        inventive_user = await api.get_user_by_email(api_client, email)
        if not inventive_user:
            answer_message = await message.answer(USER_NOT_FOUND_MESSAGE)
            await asyncio.sleep(settings.SLEEP_TIME)
            await answer_message.delete()
        elif inventive_user['IsArchive']:
            await state.clear()
            answer_message = await message.answer(USER_IS_ARCHIVE_MESSAGE)
            await asyncio.sleep(settings.SLEEP_TIME)
            await answer_message.delete()
        else:
            await state.set_state()
            await state.update_data(inventive_user=inventive_user)
            await send_verification_code(message, state, smtp_client, db_session)

    await message.delete()
