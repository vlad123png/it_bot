from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.aiogram_calendar import DialogCalendar, DialogCalendarCallback
from src.db.utils import save_parasite_message
from src.states import TaskStates
from .process_form import process_form

router = Router()


@router.callback_query(
    TaskStates.DateSelection,
    DialogCalendarCallback.filter()
)
async def process_date_selection(
        callback_query: types.CallbackQuery,
        callback_data: DialogCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
):
    """Обрабатывает запрос на выбор даты."""
    selected, date = await DialogCalendar(
        locale='ru_RU'
    ).process_selection(callback_query, callback_data)
    if selected:
        await state.set_state()
        data = await state.get_data()
        field = data['field']
        field['value'] = date.isoformat()
        await state.update_data(data)
        await callback_query.message.edit_text(date.strftime('%d.%m.%Y'))
        await save_parasite_message(db_session, callback_query.message.chat.id, callback_query.message.message_id)
        await process_form(router, callback_query.message, state, db_session)
