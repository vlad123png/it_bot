from aiogram import F, Bot, types, Router
from aiogram.fsm.context import FSMContext
from dateutil import parser
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.utils import save_parasite_message
from src.messages import INVALID_FLOAT_NUMBER_MESSAGE, INVALID_DATE_MESSAGE
from src.states import TaskStates
from src.utils import text_only, download_and_save_file, check_file_size
from .process_form import process_form

router = Router()


@router.message(TaskStates.TextInput)
@text_only
async def process_text_input(message: types.Message, state: FSMContext, db_session: AsyncSession):
    """Обрабатывает ввод текста."""
    await state.set_state()
    data = await state.get_data()
    field = data['field']
    field['value'] = message.text.strip()
    await state.update_data(data)
    await process_form(router, message, state, db_session)
    await save_parasite_message(db_session, message.chat.id, message.message_id)


@router.message(TaskStates.NumberInput)
@text_only
async def process_number_input(message: types.Message, state: FSMContext, db_session: AsyncSession):
    """Обрабатывает ввод числа."""
    try:
        value = float(message.text.replace(' ', '').replace(',', '.'))
    except ValueError:
        await message.answer(INVALID_FLOAT_NUMBER_MESSAGE)
    else:
        await state.set_state()
        data = await state.get_data()
        field = data['field']
        field['value'] = value
        await state.update_data(data)
        await process_form(router, message, state, db_session)
        await save_parasite_message(db_session, message.chat.id, message.message_id)


@router.message(TaskStates.DateInput)
@text_only
async def process_date_input(message: types.Message, state: FSMContext, db_session: AsyncSession):
    """Обрабатывает ввод даты."""
    try:
        date = parser.parse(message.text.strip())
    except ValueError:
        await message.answer(INVALID_DATE_MESSAGE)
    else:
        await state.set_state()
        data = await state.get_data()
        field = data['field']
        field['value'] = date
        await state.update_data(data)
        await process_form(router, message, state, db_session)
    await save_parasite_message(db_session, message.chat.id, message.message_id)


@router.message(TaskStates.FileInput, F.document | F.photo | F.video)
@check_file_size
async def process_file_input(
        message: types.Message,
        state: FSMContext,
        bot: Bot,
        db_session: AsyncSession
):
    """Обрабатывает файл."""
    await state.set_state()
    file_path = await download_and_save_file(message, bot)
    data = await state.get_data()
    field = data['field']
    field['value'] = str(file_path)
    await state.update_data(data)
    await process_form(router, message, state, db_session)
    await save_parasite_message(db_session, message.chat.id, message.message_id)
