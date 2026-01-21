from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.api_client import APIClient
from src.config.settings import settings
from src.db.utils import save_parasite_message
from src.smtp_client import SMTPClient
from src.states.request_access_state import RequestAccess
from src.utils import create_support_task

router = Router()


@router.callback_query(F.data == 'request_access')
async def access_request(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    Обрабатывает нажатие инлайн кнопки 'Запрос доступа' в главном меню.
    Запрашивает сообщение от пользователя и отправляет на имеил поддержки.
    """
    await state.set_state(RequestAccess.WaitingRequest)
    await callback.answer(text=messages.REQUEST_ACCESS, show_alert=True)


@router.message(RequestAccess.WaitingRequest, F.text)
async def get_access_text(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession,
        smtp_client: SMTPClient,
        api_client: APIClient,
):
    """
    Обработка сообщения о запросе доступа.
    Отправляет текст сообщения на почту администратора.
    """
    response_message = await message.answer(text=messages.RESPONSE_ACCESS)
    username = message.from_user.username
    content = f'Telegram username: {username}\n{message.text}'

    await state.set_state()
    await save_parasite_message(db_session, message.chat.id, response_message.message_id)
    await smtp_client.send_email(
        settings.HELP_EMAIL,
        messages.ACCESS_SUBJECT,
        content,
        settings.SENDER_EMAIL
    )

    await create_support_task(
        api_client=api_client,
        title='Запрос доступа',
        content=content,
    )
    await message.delete()
