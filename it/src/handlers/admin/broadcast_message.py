import datetime
import logging

from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.aiogram_calendar import SimpleCalendarCallback
from src.callbacks import (
    AdminCallback,
    AdminAction,
    BroadcastMessageType,
    BroadcastCallback,
)
from src.config.settings import settings
from src.db.models import User
from src.db.utils import save_parasite_message, create_broadcast_message
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards.admin_inline import (
    broadcast_main_keyboard,
    confirm_broadcast_inline_keyboard,
)
from src.states.broadcast_state import BroadcastState
from src.utils import active_user, admin, split_message
from src.utils.broadcast import create_broadcast_tasks_by_timezone
from src.utils.calendar import processing_simple_calendar_date_selection, send_simple_calendar

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(AdminCallback.filter(F.action == AdminAction.broadcast)) # type: ignore
async def get_broadcast_message_settings(
        callback_query: types.CallbackQuery,
        user: User,
        *args, **kwargs
):
    """
    Отправляет клавиатуру с выбором типа рассылки
    """
    try:
        await callback_query.message.edit_reply_markup(reply_markup=broadcast_main_keyboard())
    except TelegramBadRequest:
        logging.warning('Не удалось изменить клавиатуру на выбор рассылки типа сообщения для пользователя %s',
                        user.id)


@router.callback_query(BroadcastCallback.filter())
@active_user
@admin
async def processing_broadcast_message_type(
        callback_query: types.CallbackQuery,
        callback_data: BroadcastCallback,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """ Обработка выбора типа рассылки. Запрос текста рассылки. """
    message_mapping = {
        BroadcastMessageType.update_retail_1c: '⚠️ <b>Обновление продукта 1С Розница</b>\n',
        BroadcastMessageType.update_instruction: '📝 <b>Обновилась инструкция</b>\n',
        BroadcastMessageType.change_process: '⚡ <b>Обновился бизнес-процесс</b>\n',
        BroadcastMessageType.important_info: '❗️ <b>Обратите внимание на информацию ниже</b>\n',
        BroadcastMessageType.it_news: '📣 <b>Дайджест новостей ИТ</b>\n',
    }

    await callback_query.answer(text=messages.BROADCAST_MESSAGE_INPUT, show_alert=True)
    await state.set_state(BroadcastState.MessageInput)
    await state.set_data({'broadcast_message': message_mapping.get(callback_data.type, None)})
    logger.info('Пользователь %s выбрал тип рассылки %s', user.id, callback_data.type)


@router.message(BroadcastState.MessageInput, F.text)
@active_user
@admin
async def get_broadcast_message(
        message: types.Message,
        db_session: AsyncSession,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """Получает сообщение от пользователя и отправляет сообщение с подтверждением """
    data = await state.get_data()
    message_for_broadcast = data.get('broadcast_message') + message.html_text
    list_of_messages_for_broadcast = split_message(message_for_broadcast)
    length = len(list_of_messages_for_broadcast) - 1
    try:
        for index, part_message in enumerate(list_of_messages_for_broadcast):
            if index == length:
                answer_message = await message.answer(
                    part_message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=confirm_broadcast_inline_keyboard()
                )
            else:
                answer_message = await message.answer(part_message, parse_mode=ParseMode.HTML)
            await save_parasite_message(db_session, message.chat.id, answer_message.message_id)
        logging.info('Отправлено подтверждающее сообщение о рассылке пользователю %s', user.id)
    except TelegramBadRequest as e:
        logging.warning('Ошибка при отправке подтверждающего сообщения о рассылке пользователю %s: %e', user.id, e)

    data['list_of_messages_for_broadcast'] = list_of_messages_for_broadcast
    await state.set_data(data)
    await state.set_state(BroadcastState.WaitingConfirm)
    await save_parasite_message(db_session, message.chat.id, message.message_id)


@router.callback_query(BroadcastState.WaitingConfirm, F.data == 'edit-broadcast')
@active_user
@admin
async def edit_broadcast_message(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """ Изменение текста сообщения. Возврат к вводу сообщения для рассылки. """
    try:
        await callback_query.answer(text=messages.BROADCAST_MESSAGE_INPUT, show_alert=True)
        await callback_query.message.delete_reply_markup()
    except TelegramBadRequest:
        logging.warning(f'Не удалось ответить пользователю %s при обработки inline кнопки "Отредактировать".',
                        user.id)
    await state.set_state(BroadcastState.MessageInput)
    logger.info('Пользователь %s изменяет сообщение для рассылки.', user.id)


@router.callback_query(BroadcastState.WaitingConfirm, F.data == 'confirm-broadcast')
@active_user
@admin
async def confirm_broadcast_message(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Подтверждение отправки и переход к выбору даты отправки"""
    data = await state.get_data()
    min_date = datetime.datetime.now()
    max_date = datetime.datetime.now() + datetime.timedelta(days=13)
    data['min_date'] = min_date.isoformat()
    data['max_date'] = max_date.isoformat()
    await state.set_data(data)
    await send_simple_calendar(
        callback_query.bot,
        callback_query.message.chat.id,
        db_session,
        min_date,
        max_date,
    )
    await state.set_state(BroadcastState.DateSelection)
    await callback_query.message.delete_reply_markup()
    logger.info('Пользователь %s перешёл к выбору даты рассылки сообщения.', user.id)


@router.callback_query(
    BroadcastState.DateSelection,
    SimpleCalendarCallback.filter()
)
async def process_date_selection(
        callback_query: types.CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Обрабатывает запрос на выбор даты."""
    try:
        # Выбор даты
        is_selected = await processing_simple_calendar_date_selection(
            callback_query,
            callback_data,
            state,
            db_session,
            user.id,
        )

        # Создаёт задачи для рассылки сообщения согласно часовым поясам пользователей и рабочему дню.
        if is_selected:
            data = await state.get_data()
            date = datetime.datetime.fromisoformat(data['date'])
            list_of_messages_for_broadcast = data['list_of_messages_for_broadcast']

            # Сохранение сообщения в БД
            delivery_time = datetime.datetime.combine(date, settings.BROADCAST_TIME).replace(
                tzinfo=datetime.timezone.utc)
            broadcast_message_id = await create_broadcast_message(
                db_session, user.id, ' '.join(list_of_messages_for_broadcast), delivery_time)

            # Создание задач для рассылки сообщения
            await create_broadcast_tasks_by_timezone(
                db_session,
                broadcast_message_id,
                delivery_time
            )

            await state.clear()
            await callback_query.answer(text=messages.BROADCAST_CREATED.format(settings.BROADCAST_TIME),
                                        show_alert=True)
            await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
            logger.info(f'Пользователь %s, создал рассылку сообщения %s', user.id, broadcast_message_id)
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка ответа пользователю %s: %s', user.id, e)
