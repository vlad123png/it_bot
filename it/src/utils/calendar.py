import datetime
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from src.aiogram_calendar.schemas import SimpleCalAct
from src.db.utils import save_parasite_message
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards.admin_inline import create_inline_keyboard_calendar


async def send_simple_calendar(
        bot: Bot,
        chat_id: int,
        db_session: AsyncSession,
        start_date: datetime.datetime = None,
        end_date: datetime.datetime = None
):
    """
    Отправляет простой календарь пользователю.
    :param bot: Aiogram бот
    :param chat_id: Идентификатор чата с пользователем
    :param db_session: Асинхронная сессия с БД
    :param start_date: Дата, с которой можно выбрать
    :param end_date: Дата, до которой можно выбрать
    """
    try:
        calendar_message = await bot.send_message(
            chat_id=chat_id,
            text='📅 Выберите дату: ',
            reply_markup=await create_inline_keyboard_calendar(start_date, end_date)
        )
        await save_parasite_message(db_session, chat_id, calendar_message.message_id)
    except TelegramBadRequest as e:
        logging.info(f'Ошибка отправки календаря пользователю %s: %s',
                     chat_id, e)


async def processing_simple_calendar_date_selection(
        callback_query: CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user_id: int,
) -> bool:
    # Обработка кнопки отмена
    if callback_data.act == SimpleCalAct.cancel:
        await callback_query.answer(text='Операция отменена!')
        await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
        await state.clear()
        logging.info('Пользователь %s отменил выбор даты.', user_id)
        return False

    # Выбор даты
    state_data = await state.get_data()
    calendar = SimpleCalendar()
    min_date = state_data.get('min_date')
    max_date = state_data.get('max_date')
    calendar.set_dates_range(
        datetime.datetime.fromisoformat(min_date) if min_date else None,
        datetime.datetime.fromisoformat(max_date) if max_date else None
    )
    selected, date = await calendar.process_selection(callback_query, callback_data)

    # Обработка выбранной даты
    if selected:
        state_data['date'] = date.isoformat()
        await state.set_data(state_data)
        await callback_query.message.edit_text(date.strftime('%d.%m.%Y'))
        logging.info('Пользователь %s выбрал дату %s.', user_id, date.strftime('%d:%m:%Y'))
        return True
    return False
