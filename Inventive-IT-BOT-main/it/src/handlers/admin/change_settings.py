import logging

from aiogram import Router, types, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from dotenv import set_key
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.callbacks import (
    ChangeSettingsCallback,
    AdminCallback,
    AdminAction,
    TypeSettingsCallback,
    TypeSettingsAction,
    CurrentMenu,
    ChangeSTTModelCallback,
)
from src.config.settings import settings
from src.db.models import User
from src.db.utils import save_parasite_message
from src.handlers.admin.utils import update_settings_keyboard_with_parameters
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards.admin_inline import (
    get_settings_main_keyboard,
    get_ai_settings_keyboard,
    get_admin_inline_keyboard,
    get_general_settings_keyboard,
    get_apply_parameter_inline_keyboard,
    broadcast_main_keyboard,
    get_sst_models_keyboard,
)
from src.states.admin import AdminState
from src.utils import active_user, admin
from src.voice_transcription.transcription_orchestrator import get_transcription_orchestrator

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(AdminCallback.filter(F.action == AdminAction.change_settings))  # noqa
@active_user
@admin
async def change_settings(
        callback_query: types.CallbackQuery,
        *args, **kwargs
):
    """ Отправляет инлайн клавиатуру с главными настройками бота """
    await callback_query.message.edit_reply_markup(reply_markup=get_settings_main_keyboard())


@router.callback_query(TypeSettingsCallback.filter(F.action == TypeSettingsAction.back))  # noqa
@active_user
@admin
async def back(
        callback_query: types.CallbackQuery,
        callback_data: TypeSettingsCallback,
        state: FSMContext,
        db_session: AsyncSession,
        *args, **kwargs
):
    """ Обрабатывает кнопку назад. Возвращает предыдущую инлайн клавиатуру. """
    await state.clear()
    if callback_data.current_menu in (CurrentMenu.main_settings, CurrentMenu.broadcast):
        await callback_query.message.edit_reply_markup(reply_markup=get_admin_inline_keyboard())
    elif callback_data.current_menu in (CurrentMenu.my_active_broadcast,):
        await callback_query.message.edit_reply_markup(reply_markup=broadcast_main_keyboard())
    elif callback_data.current_menu == CurrentMenu.change_model:
        await callback_query.message.edit_reply_markup(reply_markup=get_ai_settings_keyboard())
    else:
        await callback_query.message.edit_text(text=messages.ADMIN_PANEL, reply_markup=get_settings_main_keyboard())
    await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)


@router.callback_query(TypeSettingsCallback.filter(F.action == TypeSettingsAction.general))  # noqa
@active_user
@admin
async def general_settings(
        callback_query: types.CallbackQuery,
        *args, **kwargs
):
    """ Отправляет инлайн клавиатуру с основными настройками бота"""
    await callback_query.message.edit_reply_markup(reply_markup=get_general_settings_keyboard())


@router.callback_query(TypeSettingsCallback.filter(F.action == TypeSettingsAction.ai))  # noqa
@active_user
@admin
async def ai_settings(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        *args, **kwargs
):
    """ Отправляет инлайн клавиатуру с настройками AI """
    await callback_query.message.edit_reply_markup(reply_markup=get_ai_settings_keyboard())


@router.callback_query(ChangeSettingsCallback.filter())
@active_user
@admin
async def get_new_parameter(
        callback_query: types.CallbackQuery,
        callback_data: ChangeSettingsCallback,
        state: FSMContext,
        *args, **kwargs
):
    """ Запрашивает пользователя новый параметр настройки бота """
    # Изменение параметра модели LLM
    if callback_data.name == 'STT_MODEL':
        await callback_query.message.edit_reply_markup(reply_markup=get_sst_models_keyboard())
    else:
        # Изменение других параметров
        await callback_query.answer(messages.NEW_PARAMETER.format(
            callback_data.name,
            callback_data.value.replace('-', ':'),
            callback_data.type
        ), show_alert=True)

    await state.set_state(AdminState.NewSettingInput)
    await state.set_data({
        'parameter': callback_data.name,
        'subclass_tag': callback_data.subclass_tag,
        'value': callback_data.value.replace('-', ':'),
        'type': callback_data.type,
        'settings_message_id': callback_query.message.message_id,
    })


@router.message(AdminState.NewSettingInput)
@active_user
@admin
async def set_new_parameter(
        message: types.Message,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """ Изменяет параметры настройки бота исходя из пользовательского ввода с валидацией типа. """
    new_value = message.text
    data = await state.get_data()
    parameter_name = data.get('parameter')
    old_value = data.get('value')
    parameter_type = data.get('type')

    # Определение к каким настройкам относится параметр
    settings_class = settings.__class__
    subclass_tag = data.get('subclass_tag')
    if subclass_tag == 'AI':
        settings_class = settings.AI.__class__

    # Изменение параметра соответствуещего класса настроек с валидацией
    try:
        current_settings_values = settings.dict()
        current_settings_values[parameter_name] = new_value
        settings_class(**current_settings_values)
        data['new_value'] = new_value
        confirm_message = await message.answer(
            text=messages.SUCCESSFULLY_VALIDATED_PARAMETER.format(parameter_name, new_value),
            reply_markup=get_apply_parameter_inline_keyboard(),
        )
        await save_parasite_message(db_session, confirm_message.chat.id, confirm_message.message_id)
        logger.info(f'Пользователь ввёл новый параметр %s для %s', new_value, parameter_name)

    except ValidationError:
        # Отправка сообщение об неверном типе данных, если оно не было отправлено
        if not data.get('cancel_message_id', None):
            cancel_message = await message.answer(
                text=messages.UNSUCCESSFULLY_VALIDATED_PARAMETER.format(parameter_type, parameter_name, old_value),
                reply_markup=get_apply_parameter_inline_keyboard(use_confirm=False),
            )
            data['cancel_message_id'] = cancel_message.message_id
            await save_parasite_message(db_session, cancel_message.chat.id, cancel_message.message_id)
        logger.info(f'Пользователь ввёл неверный тип параметра для %s: %s.', parameter_name, new_value)

    await state.set_data(data)

    try:
        await message.delete()
    except TelegramBadRequest:
        logging.info('Ошибка при удалении сообщения пользователя %s с новым параметром настроек.', user.id)


@router.callback_query(F.data == 'reject-param')
async def reject_param_input(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        bot: Bot,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """ Отменяет ввод параметра настроек бота """
    data = await state.get_data()
    if cancel_message_id := data.get('cancel_message_id'):
        try:
            await bot.delete_message(callback_query.message.chat.id, cancel_message_id)
        except TelegramBadRequest:
            logging.info('Не удалось удалить сообщение о неверном типе параметра.')

    await state.clear()
    await callback_query.answer(text=messages.CANCEL_CHANGE_PARAMETER)
    await delete_parasite_messages(bot, db_session, callback_query.message.chat.id)
    logger.info("Пользователь %s отменил изменение параметра %s", user.id, data.get('parameter'))


@router.callback_query(F.data == 'confirm-param')
@active_user
@admin
async def confirm_parameter(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        user: User,
        bot: Bot,
        *args, **kwargs
):
    """ Изменяет параметр настроек бота """
    data = await state.get_data()
    subclass_tag = data.get('subclass_tag')
    parameter_name = data.get('parameter')
    new_value = data.get('new_value')

    # Определение к каким настройкам относится параметр
    current_setting_obj = settings
    if subclass_tag == 'AI':
        current_setting_obj = settings.AI

    # Изменение параметра соответствуещего класса настроек с валидацией
    try:
        setattr(current_setting_obj, parameter_name, new_value)

        # Обновление .env файла
        set_key('.env', parameter_name, str(new_value))
        logging.info(f'Параметр %s был успешно изменён на %s', parameter_name, new_value)

        await callback_query.answer(
            messages.SUCCESSFULLY_CHANGE_PARAMETER.format(parameter_name, new_value), show_alert=True
        )

        # Обновление параметров в инлайн клавиатуре настроек
        await update_settings_keyboard_with_parameters(
            bot, callback_query.message.chat.id, data.get('settings_message_id'), str(subclass_tag))

    except Exception as e:
        logging.error('Что-то пошло не так при изменении параметра настроек: %s', e, exc_info=True)

    logger.info('Пользователь %s изменил параметр %s на %s', user.id, parameter_name, new_value)
    await state.clear()

    # Удаление сообщения о неверном типе параметра и сообщения подтверждения действия
    messages_ids = [callback_query.message.message_id]
    if cancel_message_id := data.get('cancel_message_id'):
        messages_ids.append(cancel_message_id)
    await bot.delete_messages(callback_query.message.chat.id, messages_ids)


@router.callback_query(ChangeSTTModelCallback.filter())
@active_user
@admin
async def change_stt_model_callback(
        callback_query: types.CallbackQuery,
        callback_data: ChangeSTTModelCallback,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """Изменяет модель SST (Speak to text) с которой работает бот"""
    try:
        settings.AI.STT_MODEL = callback_data.name
        transcription_orchestrator = await get_transcription_orchestrator()
        transcription_orchestrator.initialize_services()

        await state.clear()
        await callback_query.answer(
            text=messages.SUCCESSFULLY_CHANGED_STT_MODEL.format(callback_data.name),
            show_alert=True
        )
        await callback_query.message.edit_reply_markup(reply_markup=get_ai_settings_keyboard())
        set_key('.env', 'STT_MODEL', callback_data.name)
        logger.info('Пользователь %s изменил модель STT на %s', user.id, callback_data.name)
    except (ValidationError, TelegramBadRequest):
        logging.warning('Не удалось изменить модель LLM')
