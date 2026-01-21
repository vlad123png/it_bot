import datetime
import logging
import random

from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.db.utils import save_parasite_message
from src.messages import (
    VERIFICATION_CODE_SENT_MESSAGE,
    VERIFICATION_EMAIL_BODY,
    VERIFICATION_EMAIL_SUBJECT
)
from src.smtp_client import SMTPClient
from src.states import AuthStates

router = Router()


@router.callback_query(
    AuthStates.VerificationCodeInput,
    F.data == 'resend-verification-code'
)
async def resend_verification_code(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        smtp_client: SMTPClient,
        db_session: AsyncSession
):
    """Обрабатывает запрос на повторную отправку кода подтверждения."""
    await state.set_state()
    await callback_query.message.delete()
    await send_verification_code(callback_query.message, state, smtp_client, db_session)


async def send_verification_code(
        message: types.Message,
        state: FSMContext,
        smtp_client: SMTPClient,
        db_session: AsyncSession,
):
    """Отправляет код подтверждения."""
    data = await state.get_data()
    email = data['inventive_user']['Email']

    code = str(random.randint(1000, 9999))
    expiry = datetime.datetime.now(datetime.UTC) + settings.VERIFICATION_CODE_DURATION
    await state.update_data(
        {
            'verification': {
                'code': code,
                'expiry': expiry.isoformat(),
                'attempts': 0
            }
        }
    )
    await smtp_client.send_email(
        email,
        VERIFICATION_EMAIL_SUBJECT,
        VERIFICATION_EMAIL_BODY.format(code),
        settings.SENDER_EMAIL
    )
    logging.debug(VERIFICATION_EMAIL_BODY.format(code))
    await state.set_state(AuthStates.VerificationCodeInput)
    verification_cod_message = await message.answer(VERIFICATION_CODE_SENT_MESSAGE)
    await save_parasite_message(db_session, verification_cod_message.chat.id, verification_cod_message.message_id)
