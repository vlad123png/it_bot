import datetime
from enum import StrEnum
from typing import Sequence

from aiogram import types
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.aiogram_calendar import SimpleCalendar
from src.callbacks import (
    AdminCallback,
    AdminAction,
    TypeSettingsCallback,
    TypeSettingsAction,
    CurrentMenu,
    ChangeSettingsCallback,
    BroadcastMessageType,
    BroadcastCallback,
    MyActiveBroadcastCallback,
    EditBroadcastCallback,
    ActionBroadcastType,
    BroadcastType,
    ChangeSTTModelCallback,
    UpdateKnowledgeBasesCallback,
)
from src.config.ai import STTModel
from src.config.settings import settings
from src.db.models import BroadcastMessages, Survey
from src.utils import extract_text_from_html


def get_admin_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру административной панели.
    """
    buttons = [
        [types.InlineKeyboardButton(
            text='⚙️ Изменить настройки',
            callback_data=AdminCallback(
                action=AdminAction.change_settings,
            ).pack()
        )],
        [types.InlineKeyboardButton(
            text='➕ Добавить администратора',
            callback_data=AdminCallback(action=AdminAction.add_admin).pack()
        )],
        [types.InlineKeyboardButton(
            text='➖ Удалить администратора',
            callback_data=AdminCallback(action=AdminAction.remove_admin).pack()
        )],
        [types.InlineKeyboardButton(
            text='📢 Рассылка сообщения',
            callback_data=AdminCallback(action=AdminAction.broadcast).pack()
        )],
        [types.InlineKeyboardButton(
            text='📊 Собрать статистику',
            callback_data=AdminCallback(action=AdminAction.collect_statistics).pack()
        )],
        [types.InlineKeyboardButton(
            text='Синхронизировать пользователей',
            callback_data=AdminCallback(action=AdminAction.users_sync).pack()
        )]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def get_settings_main_keyboard() -> InlineKeyboardMarkup:
    """ Создаёт inline клавиатуру для выбора типа настроек """
    builder = InlineKeyboardBuilder()
    builder.button(
        text='Основные настройки',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.general,
            current_menu=CurrentMenu.general,
        ).pack()
    )
    builder.button(
        text='LLM настройки',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.ai,
            current_menu=CurrentMenu.ai,
        ).pack()
    )
    builder.button(
        text='Обновление промптов',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.update_prompts,
            current_menu=CurrentMenu.general,
        ).pack()
    )
    builder.button(
        text='Обновление баз знаний',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.update_kwn,
            current_menu=CurrentMenu.general,
        )
    )
    builder.button(
        text='⬅️ Назад',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.back,
            current_menu=CurrentMenu.main_settings,
        ).pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def create_table_from_list_with_back(setting_keys: list | tuple, subclass_tag: str) -> InlineKeyboardMarkup:
    """
    Создаёт inline клавиатуру из списка с кнопкой назад. Кнопки содержат название параметра, его тип и текущее значение.
    :param setting_keys: Список с названиями кнопок. Названия должны совпадать с названием параметра в settings.
    :param subclass_tag: Тег для настроек. Используется для правильного изменения атрибута подкласса в settings.
    """
    builder = InlineKeyboardBuilder()

    # Получения подкласса с настройками
    if subclass_tag == 'general':
        subclass = settings
    else:
        subclass = getattr(settings, subclass_tag, None)
        if not subclass:
            raise ValueError(f"Не найдено подкласса настроек: {subclass_tag}")

    for setting in setting_keys:
        # Проверка существования параметра
        if not hasattr(subclass, setting):
            raise ValueError(f"Параметр {setting} отсутствует в {subclass_tag}")

        # Получение значения и типа параметра
        value = getattr(subclass, setting)
        param_type = type(value).__name__

        # Добавление кнопки
        builder.button(
            text=f"{setting} ({param_type} = {value})",
            callback_data=ChangeSettingsCallback(
                name=setting,
                subclass_tag=subclass_tag,
                type=param_type,
                value=str(value).replace(':', '-'),
            ).pack()
        )

    # Кнопка назад
    builder.button(
        text='⬅️ Назад',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.back,
            current_menu=CurrentMenu.ai,
        ).pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_ai_settings_keyboard() -> InlineKeyboardMarkup:
    """ Создаёт клавиатуру с настройками ИИ """
    setting_keys = [
        'STT_MODEL',
        'REQUESTS_COUNT'
    ]
    keyboard = create_table_from_list_with_back(setting_keys, 'AI')
    return keyboard


def get_general_settings_keyboard() -> InlineKeyboardMarkup:
    """ Создаёт inline клавиатуру с основными настройками бота """
    setting_keys = (
        'SLEEP_TIME',
        'HELP_EMAIL',
        'FEEDBACK_EMAIL',
        'ERROR_EMAIL',
        'CACHE_TIMEOUT',
        'QR_CODE_ENCODED',
        'ASK_OPTIONAL_FIELDS',
        'ANTIFLOOD_TIMEOUT',
        'AUTH_DURATION',
        'AUTH_ATTEMPTS',
        'VERIFICATION_CODE_DURATION',
        'MAX_FILE_SIZE_MB',
        'MAX_TOTAL_UPLOAD_SIZE_MB',
        'BROADCAST_TIME',
    )
    keyboard = create_table_from_list_with_back(setting_keys, 'general')
    return keyboard


def get_apply_parameter_inline_keyboard(use_confirm: bool = True) -> InlineKeyboardMarkup:
    """
    Возвращает inline клавиатуру для подтверждения изменения параметра в настройках бота.
    :param use_confirm: Позволяет создавать клавиатуру без кнопки подтвердить,
    :type use_confirm: bool
    """
    builder = InlineKeyboardBuilder()
    if use_confirm:
        builder.button(text='Подтвердить', callback_data='confirm-param')
    builder.button(text='Отменить', callback_data='reject-param')
    builder.adjust(2)
    return builder.as_markup()


def get_apply_prompt_inline_keyboard() -> InlineKeyboardMarkup:
    """ Возвращает inline клавиатуру для подтверждения изменения промпта в настройках бота """
    builder = InlineKeyboardBuilder()
    builder.button(text='Да', callback_data='confirm-prompt')
    builder.button(text='Нет', callback_data=TypeSettingsCallback(
        action=TypeSettingsAction.back,
        current_menu=CurrentMenu.change_prompts).pack())
    builder.adjust(2)
    return builder.as_markup()


def _get_change_model_keyboard(models: type[StrEnum], callback_data: type[CallbackData]):
    """
    Вспомогательная функция для создания клавиатуры выбора моделей LLM
    :param models: Класс содержащий типы моделей
    :param callback_data: Класс для создания callback
    """
    builder = InlineKeyboardBuilder()
    for model in models:
        builder.button(
            text=model,
            callback_data=callback_data(name=model)
        )
    builder.button(
        text='⬅️ Назад',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.back,
            current_menu=CurrentMenu.change_model
        ).pack()
    )
    builder.adjust(1)
    return builder


def get_sst_models_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с моделями STT (Speak to Text)"""
    return _get_change_model_keyboard(STTModel, ChangeSTTModelCallback).as_markup()


def broadcast_main_keyboard() -> InlineKeyboardMarkup:
    """ Возвращает клавиатуру для рассылки сообщений/опросов"""
    buttons = [
        [types.InlineKeyboardButton(
            text='Обновление 1С Розница',
            callback_data=BroadcastCallback(type=BroadcastMessageType.update_retail_1c).pack(),
        )],
        [types.InlineKeyboardButton(
            text='Обновление Инструкции',
            callback_data=BroadcastCallback(type=BroadcastMessageType.update_instruction).pack(),
        )],
        [types.InlineKeyboardButton(
            text='Изменение Процесса',
            callback_data=BroadcastCallback(type=BroadcastMessageType.change_process).pack(),
        )],
        [types.InlineKeyboardButton(
            text='Важная информация',
            callback_data=BroadcastCallback(type=BroadcastMessageType.important_info).pack(),
        )],
        [types.InlineKeyboardButton(
            text='Отправить ИТ новости',
            callback_data=BroadcastCallback(type=BroadcastMessageType.it_news).pack(),
        )],
        [types.InlineKeyboardButton(
            text='Запустить опрос',
            callback_data=BroadcastCallback(type=BroadcastMessageType.new_survey).pack(),
        )],
        [types.InlineKeyboardButton(
            text='Получить результат опроса',
            callback_data=BroadcastCallback(type=BroadcastMessageType.survey_result).pack(),
        )],
        [types.InlineKeyboardButton(
            text='Мои активные рассылки',
            callback_data=BroadcastCallback(type=BroadcastMessageType.my_active_broadcast).pack(),
        )],
        [types.InlineKeyboardButton(
            text='⬅️ Назад',
            callback_data=TypeSettingsCallback(
                action=TypeSettingsAction.back,
                current_menu=CurrentMenu.broadcast
            ).pack()
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_broadcast_inline_keyboard() -> InlineKeyboardMarkup:
    """ Создаёт клавиатуру с подтверждением рассылки сообщения """
    builder = InlineKeyboardBuilder()
    builder.button(
        text='Отправить',
        callback_data='confirm-broadcast'
    )
    builder.button(
        text='Отредактировать',
        callback_data='edit-broadcast'
    )
    builder.adjust(1)
    return builder.as_markup()


async def create_inline_keyboard_calendar(
        start_date: datetime = None,
        end_date: datetime = None
) -> InlineKeyboardMarkup:
    """ Создаёт календарь и возвращает inline клавиатуру с календарём. """
    calendar = SimpleCalendar()
    if start_date or end_date:
        calendar.set_dates_range(start_date, end_date)
    return await calendar.start_calendar(year=datetime.datetime.now(datetime.UTC).year)


def create_number_keyboard(max_number: int) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для выбора числа.
    :param max_number: Максимальное число
    """
    builder = InlineKeyboardBuilder()
    for i in range(1, max_number + 1):
        builder.button(text=str(i), callback_data=str(i))
    width = min(max_number // 5, 5) or 1
    builder.adjust(width)
    return builder.as_markup()


def create_my_active_broadcast_inline_keyboard(
        broadcast_messages: Sequence[BroadcastMessages],
        surveys: Sequence[Survey]
) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с активными задачами"""
    builder = InlineKeyboardBuilder()
    for broadcast_message in broadcast_messages:
        builder.button(
            text=f'{broadcast_message.delivery_time.strftime('%d:%m:%y')} '
                 f'{extract_text_from_html(broadcast_message.message).split("\n")[1][:40]}',
            callback_data=MyActiveBroadcastCallback(id=broadcast_message.id, type=BroadcastType.message).pack()
        )
    for survey in surveys:
        builder.button(
            text=f'{survey.start_date.strftime('%d:%m:%y')} '
                 f'{extract_text_from_html(survey.question)[:40]}',
            callback_data=MyActiveBroadcastCallback(id=survey.id, type=BroadcastType.survey).pack()
        )
    builder.button(
        text='⬅️ Назад',
        callback_data=TypeSettingsCallback(
            action=TypeSettingsAction.back,
            current_menu=CurrentMenu.my_active_broadcast
        ).pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def create_change_broadcast_message_inline_keyboard(broadcast_message_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для изменения и удаления запланированного сообщения для рассылки.
    :param broadcast_message_id: Идентификатор сообщения для рассылки
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text='Изменить текст',
        callback_data=EditBroadcastCallback(id=broadcast_message_id, action=ActionBroadcastType.edit_text).pack()
    )
    builder.button(
        text='Изменить дату рассылки',
        callback_data=EditBroadcastCallback(id=broadcast_message_id, action=ActionBroadcastType.edit_date).pack()
    )
    builder.button(
        text='Удалить',
        callback_data=EditBroadcastCallback(id=broadcast_message_id, action=ActionBroadcastType.delete).pack()
    )
    builder.button(
        text='Назад',
        callback_data=EditBroadcastCallback(id=broadcast_message_id, action=ActionBroadcastType.back).pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def create_change_survey_broadcast_inline_keyboard(survey_id: int) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для изменения и удаления запланированного опроса для рассылки.
    :param survey_id: Идентификатор опроса для рассылки
    """
    buttons = [
        [types.InlineKeyboardButton(
            text='Изменить вопрос',
            callback_data=EditBroadcastCallback(id=survey_id, action=ActionBroadcastType.edit_text).pack()
        )],
        [types.InlineKeyboardButton(
            text='Изменить ответы',
            callback_data=EditBroadcastCallback(id=survey_id, action=ActionBroadcastType.edit_choices).pack()
        )],
        [types.InlineKeyboardButton(
            text='Изменить макс. количество ответов',
            callback_data=EditBroadcastCallback(id=survey_id, action=ActionBroadcastType.edit_max_number).pack()
        )],
        [types.InlineKeyboardButton(
            text='Изменить дату рассылки',
            callback_data=EditBroadcastCallback(id=survey_id, action=ActionBroadcastType.edit_date).pack()
        )],
        [types.InlineKeyboardButton(
            text='Удалить',
            callback_data=EditBroadcastCallback(id=survey_id, action=ActionBroadcastType.delete).pack()
        )],
        [types.InlineKeyboardButton(
            text='Назад',
            callback_data=EditBroadcastCallback(id=survey_id, action=ActionBroadcastType.back).pack()
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_update_knowledge_bases_inline_keyboard() -> InlineKeyboardMarkup:
    """ Возвращает клавиатуру для обновления БЗ из источника. """
    buttons = [
        [types.InlineKeyboardButton(text='Обновить БЗ 1С',
                                    callback_data=UpdateKnowledgeBasesCallback(action='1c').pack())],
        [types.InlineKeyboardButton(text='Обновить HELP',
                                    callback_data=UpdateKnowledgeBasesCallback(action='help').pack())],
        [types.InlineKeyboardButton(text='Обновить ARED HELP',
                                    callback_data=UpdateKnowledgeBasesCallback(action='ared_help').pack())],
        [types.InlineKeyboardButton(text='Обновить SAP ERP',
                                    callback_data=UpdateKnowledgeBasesCallback(action='sap_erp').pack())],
        [types.InlineKeyboardButton(text='Обновить 1С Документооборот',
                                    callback_data=UpdateKnowledgeBasesCallback(action='document_flow_1c').pack())],
        [types.InlineKeyboardButton(text='Обновить СБИС',
                                    callback_data=UpdateKnowledgeBasesCallback(action='sbis').pack())],
        [types.InlineKeyboardButton(text='Обновить УПП',
                                    callback_data=UpdateKnowledgeBasesCallback(action='upp').pack())],
        [types.InlineKeyboardButton(text='Обновить ВСЕ БЗ',
                                    callback_data=UpdateKnowledgeBasesCallback(action='all').pack())],
        [types.InlineKeyboardButton(text='⬅️ Назад',
                                    callback_data=TypeSettingsCallback(
                                        action=TypeSettingsAction.back,
                                        current_menu=CurrentMenu.update_kwn).pack())]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)
