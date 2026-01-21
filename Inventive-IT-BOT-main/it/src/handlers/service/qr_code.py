
import base64
import logging

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.api_client import APIClient
from src.config.settings import settings
from src.messages import SERVICE_NOT_FOUND_MESSAGE, SERVICE_FOUND_MESSAGE
from src.utils import api


async def process_qr_code(
    message: types.Message,
    state: FSMContext,
    api_client: APIClient
):
    """
    Обрабатывает выбор сервиса по QR-коду.

    Использует код сервиса из QR-кода для поиска сервиса. Если сервис найден,
    отображает инлайн-клавиатуру с кнопкой для подтверждения выбора сервиса.
    """
    data = await state.get_data()

    if settings.QR_CODE_ENCODED:
        try:
            service_code = base64.urlsafe_b64decode(
                data['qr_code'].encode('utf-8')).decode('utf-8')
        except Exception as e:
            logging.error(
                f'Ошибка декодирования QR кода {data["qr_code"]}: %s',
                str(e)
            )
            service_code = None
    else:
        service_code = data['qr_code']

    services = await api.get_services(api_client)
    service = next((s for s in services if s['Code'] == service_code), None)
    builder = InlineKeyboardBuilder()
    if service:
        text = SERVICE_FOUND_MESSAGE.format(repr(service['Name']))
        builder.button(
            text='✅ Подтвердить',
            callback_data=f'service:select:{service["Id"]}'
        )
    else:
        text = SERVICE_NOT_FOUND_MESSAGE
    builder.button(
        text='🛎️ Сервисы создания заявок',
        callback_data='show-services'
    )
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())
