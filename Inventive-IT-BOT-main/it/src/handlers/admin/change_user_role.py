import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.api_client import APIClient
from src.callbacks import AdminCallback, AdminAction
from src.db.models import UserRole
from src.db.users import set_user_role_by_inventive_id
from src.db.utils import save_parasite_message
from src.states.admin import AdminState
from src.utils import active_user, admin, is_email
from src.utils import api

router = Router()


@router.callback_query(AdminCallback.filter(F.action == AdminAction.add_admin)) # noqa
@active_user
@admin
async def add_admin(
        callback_query: types.CallbackQuery,
        callback_data: AdminCallback,
        state: FSMContext,
        *args, **kwargs
):
    """
    Запрашивает email нового администратора.
    """
    await callback_query.answer(text=messages.ADD_ADMIN_EMAIL_INPUT, show_alert=True)
    await state.update_data(user_role=UserRole.ADMIN)
    await state.set_state(AdminState.EmailInput)


@router.callback_query(AdminCallback.filter(F.action == AdminAction.remove_admin)) # noqa
@active_user
@admin
async def remove_admin(
        callback_query: types.CallbackQuery,
        callback_data: AdminCallback,
        state: FSMContext,
        *args, **kwargs
):
    """
    Запрашивает email администратора.
    """
    await callback_query.answer(text=messages.REMOVE_ADMIN_EMAIL_INPUT, show_alert=True)
    await state.update_data(user_role=UserRole.CLIENT)
    await state.set_state(AdminState.EmailInput)


@router.message(AdminState.EmailInput, F.text)
@active_user
@admin
async def set_user_role(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession,
        api_client: APIClient,
        *args, **kwargs
):
    """
    Изменяет роль пользователя в системе.
    """
    email = message.text.strip()

    # Проверка корректности email
    if not is_email(email):
        invalid_email_message = await message.answer(text=messages.INVALID_EMAIL_MESSAGE)
        await save_parasite_message(db_session, message.chat.id, invalid_email_message.message_id)

    data = await state.get_data()
    user_role: UserRole = data.get('user_role')

    # Изменяем роль пользователя, если он зарегестрирован в боте
    await state.clear()
    inventive_user = await api.get_user_by_email(api_client, email)
    try:
        if inventive_user and user_role:
            result = await set_user_role_by_inventive_id(db_session, inventive_user['Id'], user_role)
            if result:
                access_message = await message.answer(messages.SUCCESSFULLY_CHANGE_USER_ROLE.format(email))
                await save_parasite_message(db_session, message.chat.id, access_message.message_id)
            else:
                unsuccessfully_message = await message.answer(messages.UNSUCCESSFULLY_CHANGE_USER_ROLE.format(email))
                await save_parasite_message(db_session, message.chat.id, unsuccessfully_message.message_id)
        await message.delete()

    except Exception as e:
        logging.error('Не удалось изменить роль пользователю %s на %s, %e', email, user_role, e, exc_info=True)
