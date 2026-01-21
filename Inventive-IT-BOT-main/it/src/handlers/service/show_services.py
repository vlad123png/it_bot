from aiogram import F, types, Router
from aiogram.enums import ParseMode

from src import messages
from src.api_client import APIClient
from src.callbacks import ShowServiceCallback
from src.db.models import User
from src.keyboards import (
    ButtonsWithPagination,
    get_service_buttons, get_main_inline_keyboard
)
from src.messages import SELECT_SERVICE_MESSAGE
from src.utils import api, active_user

router = Router()


@router.callback_query(ShowServiceCallback.filter())
@active_user
async def show_services(
        callback_query: types.CallbackQuery,
        callback_data: ShowServiceCallback,
        api_client: APIClient,
        user: User,
        *args, **kwargs
):
    """
    Обрабатывает запрос на отображение меню сервисов.

    Получает список сервисов, генерирует кнопки для сервисов
    и отображает их в виде пагинированной инлайн-клавиатуры.
    """
    services = await api.get_services(api_client, user.inventive_email)
    menus, controls = await get_service_buttons(services)
    inline_keyboard = ButtonsWithPagination(
        router,
        menus,
        controls,
        SELECT_SERVICE_MESSAGE
    )

    await callback_query.answer()
    force_new_message = callback_data.force_new_message
    await inline_keyboard.start(callback_query.message, force_new_message)


@router.callback_query(F.data == 'back_to_main_menu')
async def back_to_main_menu(callback_query: types.CallbackQuery):
    """ Обрабатывает запрос на возвращение в главное меню. """
    await callback_query.message.edit_text(
        text=messages.WELCOME_MESSAGE.format(callback_query.from_user.full_name),
        reply_markup=await get_main_inline_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data == 'send_main_menu')
async def back_to_main_menu(callback_query: types.CallbackQuery):
    """ Обрабатывает запрос на отправку сообщения с главным меню. """
    await callback_query.message.answer(
        text=messages.WELCOME_MESSAGE.format(callback_query.from_user.full_name),
        reply_markup=await get_main_inline_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback_query.answer()
