from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import OptionalFieldAction, OptionalFieldCallback
from src.states import TaskStates
from .process_field import process_field
from .process_form import process_form

router = Router()


@router.callback_query(
    TaskStates.OptionalField,
    OptionalFieldCallback.filter(F.action == OptionalFieldAction.fill)
)
async def process_optional_field_fill(
        callback_query: types.CallbackQuery,
        callback_data: OptionalFieldCallback,
        state: FSMContext,
        db_session: AsyncSession
):
    """Обрабатывает запрос на заполнение необязательного поля."""
    data = await state.get_data()
    field = data['field']
    if (
            data['task_timestamp'] == callback_data.task_timestamp
            and field['key'] == callback_data.field_key
    ):
        await state.set_state()
        await callback_query.message.delete()
        await process_field(router, callback_query.message, state, db_session)


@router.callback_query(
    TaskStates.OptionalField,
    OptionalFieldCallback.filter(F.action == OptionalFieldAction.skip)
)
async def process_optional_field_skip(
        callback_query: types.CallbackQuery,
        callback_data: OptionalFieldCallback,
        state: FSMContext,
        db_session: AsyncSession,
):
    """Обрабатывает запрос на пропуск необязательного поля."""
    data = await state.get_data()
    field = data['field']
    if (
            data['task_timestamp'] == callback_data.task_timestamp
            and field['key'] == callback_data.field_key
    ):
        await state.set_state()
        await callback_query.message.delete()
        await process_form(router, callback_query.message, state, db_session)
