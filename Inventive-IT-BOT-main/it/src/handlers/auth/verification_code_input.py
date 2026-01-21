import asyncio
import datetime

from aiogram import types, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.api_client import APIClient
from src.backend_api import BackendAPI
from src.config.settings import settings
from src.handlers.assistant.utils import delete_parasite_messages
from src.handlers.service.qr_code import process_qr_code
from src.keyboards import get_main_inline_keyboard
from src.messages import (
    INVALID_VERIFICATION_CODE_MESSAGE,
    VERIFICATION_CODE_EXPIRED_MESSAGE,
    VERIFICATION_LIMIT_EXCEEDED_MESSAGE,
    WELCOME_MESSAGE,
    VERIFICATION_ERROR_MESSAGE
)
from src.states import AuthStates
from src.utils import db, text_only
from src.utils.users import match_user

router = Router()


@router.message(AuthStates.VerificationCodeInput)
@text_only
async def process_verification_code_input(
        message: types.Message,
        state: FSMContext,
        api_client: APIClient,
        db_session: AsyncSession,
        backend_service: BackendAPI,
):
    """
    Обрабатывает ввод кода подтверждения.

    Вызывается при получении от пользователя кода подтверждения в процессе
    аутентификации. Проверяет корректность введенного кода, срок действия,
    и количество попыток ввода. Если пользователь успешно ввёл код
    подтверждения, создаётся новый или обновляется пользователь в базе данных.
    """
    data = await state.get_data()
    verification = data.get('verification')

    if not verification:
        answer_message = await message.answer(VERIFICATION_ERROR_MESSAGE)
        await state.clear()
        await asyncio.sleep(settings.SLEEP_TIME)
        await answer_message.delete()
        return

    await delete_parasite_messages(message.bot, db_session, message.chat.id)

    if datetime.datetime.now(datetime.UTC) > datetime.datetime.fromisoformat(verification['expiry']):
        builder = InlineKeyboardBuilder()
        builder.button(
            text='🔄 Отправить ещё раз',
            callback_data='resend-verification-code'
        )
        await message.answer(
            text=VERIFICATION_CODE_EXPIRED_MESSAGE,
            reply_markup=builder.as_markup()
        )
    else:
        verification_code = message.text.strip()
        if verification['code'] != verification_code:
            if verification['attempts'] < settings.AUTH_ATTEMPTS - 1:
                verification['attempts'] += 1
                await message.answer(INVALID_VERIFICATION_CODE_MESSAGE)
                await state.set_data(data)
            else:
                await message.answer(VERIFICATION_LIMIT_EXCEEDED_MESSAGE)
                await state.clear()
        else:
            await state.set_state()
            inventive_user = data['inventive_user']
            email = inventive_user.get('Email')
            backend_users = await backend_service.get_users_by_email(email)
            fio = inventive_user.get('Name').lower()
            candidates = [bu for bu in backend_users if match_user(fio, bu)]
            backend_id = candidates[0].id if len(candidates) == 1 else None

            # Определение часового пояса пользователя по данным из inventive.
            try:
                user_timezone = int(inventive_user.get("UtcOffset").split(":")[0])
            except (ValueError, AttributeError):
                # По умолчанию используем часовой пояс MSK
                user_timezone = 3

            await db.create_or_update_user(
                db_session,
                message.from_user.id,
                inventive_user['Id'],
                backend_id,
                user_timezone,
                message.chat.username,
                email
            )

            if data.get('qr_code'):
                await process_qr_code(message, state, api_client)
            else:
                await message.answer(
                    text=WELCOME_MESSAGE.format(inventive_user['Name']),
                    reply_markup=await get_main_inline_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            await state.clear()
    await message.delete()
