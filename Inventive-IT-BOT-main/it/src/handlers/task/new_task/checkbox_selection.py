from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import CheckboxCallback
from src.messages import SELECTED_MESSAGE
from src.states import TaskStates
from .process_form import process_form

router = Router()


@router.callback_query(
    TaskStates.CheckboxSelection,
    CheckboxCallback.filter()
)
async def process_checkbox_selection(
        callback_query: types.CallbackQuery,
        callback_data: CheckboxCallback,
        state: FSMContext,
        db_session: AsyncSession,
):
    """Обрабатывает запрос на выбор из чекбокса."""
    data = await state.get_data()
    field = data['field']
    if (
            data['task_timestamp'] == callback_data.task_timestamp
            and field['key'] == callback_data.field_key
    ):
        await state.set_state()
        field['value'] = callback_data.value
        name = 'Да' if callback_data.value else 'Нет'
        await state.update_data(data)
        await callback_query.message.edit_text(SELECTED_MESSAGE.format(name))
        await process_form(router, callback_query.message, state, db_session)
