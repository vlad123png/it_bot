from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import (
    FilesAction,
    FilesCallback,
    OptionalFieldAction,
    OptionalFieldCallback
)
from src.messages import OPTIONAL_FIELD_MESSAGE, ATTCH_FILES_MESSAGE
from src.states import TaskStates
from .process_field import process_field


async def process_form(
        router: Router,
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession
):
    """
    Обрабатывает анкету.

    Извлекает следующее поле анкеты и инициирует процесс заполнения этого поля.
    Если все поля анкеты обработаны, инициирует процесс прикрепления файлов к
    заявке или завершения создания заявки.
    """
    data = await state.get_data()
    try:
        # Если было заполнено поле, то сохраняем его в форму
        if field := data.get('field'):
            data['form'][data['current_field_index'] - 1] = field

        # Получаем новое поле формы для заполнение
        form = data['form']
        field = form[data['current_field_index']]
        data['current_field_index'] += 1
        data['field'] = field
        await state.set_data(data)
    except IndexError:
        await state.set_data(data)
        builder = InlineKeyboardBuilder()
        builder.button(
            text='✅ Да',
            callback_data=FilesCallback(
                action=FilesAction.attach,
                task_timestamp=data['task_timestamp']
            )
        )
        builder.button(
            text='❌ Нет',
            callback_data=FilesCallback(
                action=FilesAction.proceed,
                task_timestamp=data['task_timestamp']
            )
        )
        await state.set_state(TaskStates.Files)
        await message.answer(
            text=ATTCH_FILES_MESSAGE,
            reply_markup=builder.as_markup()
        )
    else:
        if field['required']:
            await process_field(router, message, state, db_session)
        else:
            builder = InlineKeyboardBuilder()
            builder.button(
                text='✅ Да',
                callback_data=OptionalFieldCallback(
                    action=OptionalFieldAction.fill,
                    task_timestamp=data['task_timestamp'],
                    field_key=field['key']
                )
            )
            builder.button(
                text='⏭ Пропустить',
                callback_data=OptionalFieldCallback(
                    action=OptionalFieldAction.skip,
                    task_timestamp=data['task_timestamp'],
                    field_key=field['key']
                )
            )
            await state.set_state(TaskStates.OptionalField)
            await message.answer(
                text=OPTIONAL_FIELD_MESSAGE.format(field['name']),
                reply_markup=builder.as_markup()
            )
