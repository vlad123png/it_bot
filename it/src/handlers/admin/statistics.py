import datetime as dt
import logging
import os

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.aiogram_calendar import SimpleCalendarCallback
from src.backend_api import BackendAPI
from src.callbacks import AdminCallback, AdminAction
from src.db.models import User
from src.handlers.admin.statistics_utils import generate_statistic_info_csv_file
from src.handlers.assistant.utils import delete_parasite_messages
from src.states.statistics_state import StatisticState
from src.utils import active_user, admin
from src.utils.calendar import send_simple_calendar, processing_simple_calendar_date_selection

router = Router()


@router.callback_query(AdminCallback.filter(F.action == AdminAction.collect_statistics))  # noqa
@active_user
@admin
async def collect_statistics_callback(
        callback_query: CallbackQuery,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Обработка нажатия кнопки сбора статистики. """
    try:
        await state.set_state(StatisticState.select_start_date)
        await callback_query.answer(text=messages.SELECT_START_DATE_COLLECT_STATISTICS, show_alert=True)
        await send_simple_calendar(
            callback_query.bot,
            callback_query.message.chat.id,
            db_session,
            end_date=dt.datetime.now(dt.UTC)
        )
        await state.set_data({'max_date': dt.datetime.now(dt.UTC).isoformat()})

    except TelegramBadRequest:
        logging.warning(f'Ошибка отправки сообщения при выборе даты начала сбора статистики %s', user.id)


@router.callback_query(StatisticState.select_start_date, SimpleCalendarCallback.filter())
@active_user
@admin
async def select_start_date(
        callback_query: CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs

):
    """Обработка выбора начальной даты сбора статитстики"""
    try:
        is_selected = await processing_simple_calendar_date_selection(
            callback_query,
            callback_data,
            state,
            db_session,
            user.id,
        )

        if is_selected:
            try:
                state_data = await state.get_data()
                await state.set_state(StatisticState.select_end_date)
                state_data['start_date'] = state_data['date']

                min_date = state_data['date']
                max_date = dt.datetime.now(dt.UTC)
                state_data['min_date'] = min_date
                state_data['max_date'] = max_date.isoformat()
                await state.set_data(state_data)

                await send_simple_calendar(
                    callback_query.bot,
                    callback_query.message.chat.id,
                    db_session,
                    dt.datetime.fromisoformat(min_date),
                    max_date
                )
                await callback_query.answer(messages.SELECT_END_DATE_COLLECT_STATISTICS, show_alert=True)
            except TelegramBadRequest:
                logging.warning(
                    f'Ошибка отправки сообщения для выбора даты окончания сбора статистики %s',
                    user.id)
    except TelegramBadRequest:
        logging.warning(f'Ошибка отправки сообщения при обработки даты начала сбора статистики %s', user.id)


@router.callback_query(StatisticState.select_end_date, SimpleCalendarCallback.filter())
@active_user
@admin
async def select_end_date(
        callback_query: CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        backend_service: BackendAPI,
        *args, **kwargs
):
    """Обработка финальной даты сбора статистики. Сбор статистики и отправка файла."""
    try:
        is_selected = await processing_simple_calendar_date_selection(
            callback_query,
            callback_data,
            state,
            db_session,
            user.id
        )

        if is_selected:
            state_data = await state.get_data()
            start_date_str = state_data['start_date']
            end_date_str = state_data['date']

            # Преобразуем строки в datetime объекты
            start_date = dt.datetime.fromisoformat(start_date_str)
            end_date = dt.datetime.fromisoformat(end_date_str)

            file_path = f'temp/statistics_{dt.datetime.now(dt.UTC).strftime("%Y-%m-%d_%H-%M-%S")}.csv'
            await generate_statistic_info_csv_file(backend_service, db_session, start_date, end_date, file_path)

            try:
                file = FSInputFile(file_path)
                await callback_query.bot.send_document(chat_id=callback_query.message.chat.id, document=file)
                await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
    except TelegramBadRequest:
        logging.warning(f'Ошибка отправки файла статистики %s', user.id)
