from datetime import datetime

from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.aiogram_calendar import DialogCalendar
from src.callbacks import (
    CheckboxCallback,
    ListCallback,
    ChoiceSelectCallback,
    ChoiceCompleteCallback
)
from src.db.utils import save_parasite_message
from src.keyboards import ButtonsWithPagination
from src.messages import (
    SELECT_CHECKBOX_MESSAGE,
    SELECT_CHOICE_MESSAGE,
    SELECT_LIST_MESSAGE
)
from src.states import TaskStates
from src.utils import clean_text


async def process_field(
        router: Router,
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession
):
    """
    Обрабатывает текущее поле анкеты.

    Отображает пользователю информацию о текущем поле и инициирует процесс
    заполнения поля в зависимости от типа поля (ввод значения или выбор опции).
    """
    data = await state.get_data()
    field = data['field']

    text = f'📝 {field["name"]}{" (файл):" if field["type"] == "file" else ":"}'
    if field.get('hint'):
        text += f'\n\n💡 {field["hint"]}'

    answer_message = await message.answer(text)
    await save_parasite_message(db_session, answer_message.chat.id, answer_message.message_id)

    if field['type'] == 'text':
        await state.set_state(TaskStates.TextInput)
    elif field['type'] == 'number':
        await state.set_state(TaskStates.NumberInput)
    elif field['type'] == 'file':
        await state.set_state(TaskStates.FileInput)
    elif field['type'] == 'date':
        await state.set_state(TaskStates.DateSelection)
        calendar_message = await message.answer(
            text='📅 Выберите дату: ',
            reply_markup=await DialogCalendar(
                locale='ru_RU'
            ).start_calendar(year=datetime.utcnow().year)
        )
        await save_parasite_message(db_session, calendar_message.chat.id, calendar_message.message_id)
    elif field['type'] == 'checkbox':
        builder = InlineKeyboardBuilder()
        builder.button(
            text='Да',
            callback_data=CheckboxCallback(
                task_timestamp=data['task_timestamp'],
                field_key=field['key'],
                value=True
            )
        )
        builder.button(
            text='Нет',
            callback_data=CheckboxCallback(
                task_timestamp=data['task_timestamp'],
                field_key=field['key'],
                value=False
            )
        )
        await state.set_state(TaskStates.CheckboxSelection)
        checkbox_message = await message.answer(
            SELECT_CHECKBOX_MESSAGE,
            reply_markup=builder.as_markup()
        )
        await save_parasite_message(db_session, checkbox_message.chat.id, checkbox_message.message_id)
    elif field['type'] == 'list':
        menus = []
        for option in field['options']:
            menus.append(
                [
                    types.InlineKeyboardButton(
                        text=clean_text(option['Name']),
                        callback_data=ListCallback(
                            task_timestamp=data['task_timestamp'],
                            field_key=field['key'],
                            option_id=option['Id']
                        ).pack()
                    )
                ]
            )
        inline_keyboard = ButtonsWithPagination(
            router,
            menus,
            text=SELECT_LIST_MESSAGE
        )
        await state.set_state(TaskStates.ListSelection)
        await inline_keyboard.start(message, force_new_message=True)
    elif field['type'] == 'choice':
        menus = []
        for option in field['options']:
            menus.append(
                [
                    types.InlineKeyboardButton(
                        text=clean_text(option['Name']),
                        callback_data=ChoiceSelectCallback(
                            task_timestamp=data['task_timestamp'],
                            field_key=field['key'],
                            option_id=option["Id"]
                        ).pack()
                    )
                ]
            )
        controls = [
            [
                types.InlineKeyboardButton(
                    text='✅ Завершить выбор',
                    callback_data=ChoiceCompleteCallback(
                        task_timestamp=data['task_timestamp'],
                        field_key=field['key']
                    ).pack()
                )
            ]
        ]
        inline_keyboard = ButtonsWithPagination(
            router,
            menus,
            controls,
            SELECT_CHOICE_MESSAGE
        )
        await state.set_state(TaskStates.ChoiceSelection)
        await inline_keyboard.start(message, force_new_message=True)
    else:
        raise RuntimeError(
            f'process_field: неожиданный тип поля: {field["type"]}.'
        )
