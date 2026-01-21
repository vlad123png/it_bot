from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import ListCallback
from src.db.utils import save_parasite_message
from src.messages import SELECTED_MESSAGE
from src.states import TaskStates
from .process_form import process_form

router = Router()


@router.callback_query(TaskStates.ListSelection, ListCallback.filter())
async def process_list_selection(
        callback_query: types.CallbackQuery,
        callback_data: ListCallback,
        state: FSMContext,
        db_session: AsyncSession,
):
    """Обрабатывает запрос на выбор элемента из списка."""
    data = await state.get_data()
    field = data['field']
    if (
            data['task_timestamp'] == callback_data.task_timestamp
            and field['key'] == callback_data.field_key
    ):
        await state.set_state()
        field['value'] = callback_data.option_id
        option = next(
            option
            for option in field['options']
            if option['Id'] == callback_data.option_id
        )
        selected_message = await callback_query.message.edit_text(
            SELECTED_MESSAGE.format(option['Name'])
        )
        await state.update_data(data)
        await save_parasite_message(db_session, selected_message.chat.id, selected_message.message_id)
        await process_form(router, callback_query.message, state, db_session)
