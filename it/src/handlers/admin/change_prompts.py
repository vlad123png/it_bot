import logging

from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from src import messages
from src.backend_api import BackendAPI
from src.callbacks import TypeSettingsAction, TypeSettingsCallback
from src.db.models import User
from src.keyboards.admin_inline import (
    get_apply_prompt_inline_keyboard, get_settings_main_keyboard
)
from src.utils import active_user, admin

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(TypeSettingsCallback.filter(F.action == TypeSettingsAction.update_prompts))  # noqa
@active_user
@admin
async def update_prompts(
        callback_query: types.CallbackQuery,
        user: User,
        *args, **kwargs
):
    """ Обновляет промпты бота загружая их из файлов. """
    await callback_query.message.edit_text(
        text=messages.UPDATE_PROMPTS,
        reply_markup=get_apply_prompt_inline_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


@router.callback_query(F.data == 'confirm-prompt')
@active_user
@admin
async def apply_prompt(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        user: User,
        backend_service: BackendAPI,
        *args, **kwargs
):
    """Применение нового промпта"""
    await backend_service.update_prompts()
    await callback_query.answer(text=messages.PROMPTS_UPDATED, show_alert=True)
    await callback_query.message.edit_text(text=messages.ADMIN_PANEL, reply_markup=get_settings_main_keyboard())
    await state.clear()
    logger.info('Пользователь %s обновил промпты.', user.id)
