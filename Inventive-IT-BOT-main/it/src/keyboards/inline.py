from typing import List, Tuple
from uuid import UUID

from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.callbacks import (
    ServiceAction,
    ServiceCallback,
    NewTaskCallback,
    ReactionCallback,
    ReactionType,
    FeedbackCallback,
    FeedbackAction,
    ShowServiceCallback,
    TimezoneCallback,
    AnswerFeedbackCallback
)


def get_start_inline_keyboard() -> InlineKeyboardMarkup:
    """Получает стартовую инлайн-клавиатуру"""
    buttons = [
        [
            types.InlineKeyboardButton(
                text='✍️ Соглашение',
                callback_data='user_agreement')
        ],
        [
            types.InlineKeyboardButton(
                text='🔘 Войти',
                callback_data='login')
        ],
        [
            types.InlineKeyboardButton(
                text='⁉️ Помощь',
                callback_data='help')
        ],
        [
            types.InlineKeyboardButton(
                text='📧 Запрос доступа',
                callback_data='request_access')
        ],
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


async def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Получает главную инлайн-клавиатуру.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text='🛎️ Сервисы создания заявок',
        callback_data=ShowServiceCallback(force_new_message=False).pack()
    )
    builder.button(
        text='💬 Оставить отзыв',
        callback_data='send-feedback'
    )
    builder.adjust(1)
    return builder.as_markup()


async def get_service_buttons(
        services: List[dict],
        parent_id: int = None
) -> Tuple[list, list]:
    """
    Получает список кнопок для сервисов.

    :param services: Список сервисов
    :type services: List[dict]
    :param parent_id: Идентификатор родительского сервиса
    :type parent_id: int

    :return: Кортеж из кнопок меню и кнопок управления меню
    :rtype: Tuple[list, list]
    """
    services = filter(
        lambda data: data['ParentId'] == parent_id,
        services
    )
    menus = [
        [
            types.InlineKeyboardButton(
                text=service['Name'],
                callback_data=ServiceCallback(
                    action=ServiceAction.select,
                    service_id=service['Id']
                ).pack()
            )
        ] for service in services if service.get('HasTaskTypes', True)
    ]
    controls = [
        [
            types.InlineKeyboardButton(
                text='⬅️ Назад',
                callback_data=ServiceCallback(
                    action=ServiceAction.back,
                    service_id=parent_id
                ).pack()
            )
        ] if parent_id else [
            types.InlineKeyboardButton(
                text='⬅️ Назад',
                callback_data='back_to_main_menu'
            )
        ]
    ]
    return menus, controls


async def get_task_type_buttons(
        task_types: List[dict],
        service_id: int = None
) -> Tuple[list, list]:
    """
    Полученает список кнопок для типов заявок.

    :param task_types: Список типов заявок
    :type task_types: List[dict]
    :param service_id: Идентификатор сервиса
    :type service_id: int

    :return: Кортеж из кнопок меню и кнопок управления меню
    :rtype: Tuple[list, list]
    """
    menus = [
        [
            types.InlineKeyboardButton(
                text=task_type['Name'],
                callback_data=NewTaskCallback(
                    service_id=service_id,
                    task_type_id=task_type['Id']
                ).pack()
            )
        ] for task_type in task_types
    ]
    controls = [
        [
            types.InlineKeyboardButton(
                text='⬅️ Назад',
                callback_data=ServiceCallback(
                    action=ServiceAction.back,
                    service_id=service_id
                ).pack()
            )
        ] if service_id else []
    ]
    return menus, controls


def get_reaction_keyboard(
        ai_message_id: UUID,
        service_id: int | None = None,
) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для сообщения с ответом ИИ

    :param ai_message_id: ID сообщения с ответом ИИ
    :param service_id: ID сервиса для создания заявки.
    """
    ai_message_id = str(ai_message_id)
    builder = InlineKeyboardBuilder()
    builder.button(
        text='👍',
        callback_data=ReactionCallback(type=ReactionType.like, id=ai_message_id).pack()
    )
    builder.button(
        text='👎',
        callback_data=ReactionCallback(type=ReactionType.dislike, id=ai_message_id).pack()
    )
    builder.button(
        text='📝 Оставить отзыв об ответе',
        callback_data=AnswerFeedbackCallback(id=ai_message_id).pack()
    )
    if service_id:
        builder.button(
            text='📬 Создать заявку',
            callback_data=ServiceCallback(
                action=ServiceAction.select,
                service_id=service_id,
                new_msg=True
            ).pack()
        )
    builder.button(
        text='🏠 Вернуться в главное меню',
        callback_data='send_main_menu'
    )
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def get_create_task_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text='🛎️ Сервисы создания заявок',
        callback_data=ShowServiceCallback(force_new_message=True).pack()
    )
    builder.button(
        text='💬 Оставить отзыв',
        callback_data='send-feedback'
    )
    builder.adjust(1)
    return builder.as_markup()


def get_feedback_keyboard(ai_message_id: UUID | str) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с предложением оставить отзыв

    :param ai_message_id: ID сообщения с ответом ИИ
    """
    ai_message_id = str(ai_message_id)
    buttons = [
        types.InlineKeyboardButton(
            text='📎 Оставить отзыв',
            callback_data=FeedbackCallback(action=FeedbackAction.leave, id=ai_message_id).pack()
        ),
        types.InlineKeyboardButton(
            text='➡️ Пропустить',
            callback_data=FeedbackCallback(action=FeedbackAction.skip, id=ai_message_id).pack()
        ),
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[buttons])
    return keyboard


def get_timezone_inline_keyboard():
    """
    Создаёт инлайн клавиатуру с кнопками часовых поясов
    """
    timezone_mapper = {
        'Калининградское время (UTC+2)': 2,
        'Московское время (UTC+3)': 3,
        'Самарское время (UTC+4)': 4,
        'Екатеринбургское время (UTC+5)': 5,
        'Омское время (UTC+6)': 6,
        'Красноярское время (UTC+7)': 7,
        'Иркутское время (UTC+8)': 8,
        'Якутское время (UTC+9)': 9,
        'Владивостокское время (UTC+10)': 10,
        'Магаданское время (UTC+11)': 11,
        'Камчатское время (UTC+12)': 12,
    }
    buttons = [
        [types.InlineKeyboardButton(
            text=text,
            callback_data=TimezoneCallback(offset=offset, timezone=text).pack()
        )] for text, offset in timezone_mapper.items()
    ]

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)
