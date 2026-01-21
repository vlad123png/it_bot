from aiogram import F, types, Router

from src.api_client import APIClient
from src.callbacks import ServiceAction, ServiceCallback
from src.db.models import User
from src.keyboards import (
    ButtonsWithPagination,
    get_service_buttons,
    get_task_type_buttons, get_main_inline_keyboard
)
from src.messages import SELECT_SERVICE_MESSAGE, SELECT_TASK_TYPE_MESSAGE, NOT_EXISTING_SERVICE
from src.utils import api

router = Router()


@router.callback_query(
    ServiceCallback.filter(F.action == ServiceAction.select)
)
async def process_service_select(
    callback_query: types.CallbackQuery,
    callback_data: ServiceCallback,
    api_client: APIClient,
    user: User
):
    """
    Обрабатывает запрос выбора сервиса.

    Получает выбранный сервис и проверяет, можно ли создавать заявки
    для данного сервиса. Если создание заявок возможно, получает типы задач
    и отображает их в виде пагинированной инлайн-клавиатуры. Если создание
    задач невозможно, получает родительский сервис и отображает его дочерние
    сервисы в виде пагинированной инлайн-клавиатуры.
    """
    service_id = callback_data.service_id
    services = await api.get_services(api_client, user.inventive_email)
    service = next((s for s in services if s['Id'] == service_id), None)

    if service is None:
        await callback_query.answer(NOT_EXISTING_SERVICE, show_alert=True)
        return

    if service['CanCreateTask']:
        task_types = await api.get_task_types(api_client, service_id)
        menus, controls = await get_task_type_buttons(task_types, service_id)
        inline_keyboard = ButtonsWithPagination(
            router,
            menus,
            controls,
            SELECT_TASK_TYPE_MESSAGE
        )
        await inline_keyboard.start(callback_query.message, callback_data.new_msg)
    else:
        menus, controls = await get_service_buttons(services, service_id)
        inline_keyboard = ButtonsWithPagination(
            router,
            menus,
            controls,
            SELECT_SERVICE_MESSAGE
        )
        await inline_keyboard.start(callback_query.message, callback_data.new_msg)


@router.callback_query(
    ServiceCallback.filter(F.action == ServiceAction.back)
)
async def process_service_back(
    callback_query: types.CallbackQuery,
    callback_data: ServiceCallback,
    api_client: APIClient,
    user: User
):
    """
    Обрабатывает запрос для навигации назад в меню сервисов.

    Получает родительский сервис для текущего сервиса и отображает его
    дочерние элементы в виде пагинированной инлайн-клавиатуры.
    """
    service_id = callback_data.service_id
    services = await api.get_services(api_client, user.inventive_email)
    service = next((s for s in services if s['Id'] == service_id), None)
    if service is None:
        await callback_query.answer(NOT_EXISTING_SERVICE, show_alert=True)
        await callback_query.message.edit_reply_markup(reply_markup=await get_main_inline_keyboard())
        return

    menus, controls = await get_service_buttons(services, service['ParentId'])
    inline_keyboard = ButtonsWithPagination(
        router,
        menus,
        controls,
        SELECT_SERVICE_MESSAGE
    )
    await inline_keyboard.start(callback_query.message)
