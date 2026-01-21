import asyncio
import datetime
import logging

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.aiogram_calendar import SimpleCalendarCallback
from src.callbacks import (
    BroadcastMessageType,
    BroadcastCallback,
    MyActiveBroadcastCallback,
    EditBroadcastCallback,
    ActionBroadcastType,
    BroadcastType
)
from src.config.settings import settings
from src.db.broadcast_utils import (
    get_user_active_broadcast_messages,
    get_broadcast_message,
    delete_broadcast_message,
    update_broadcast_message_text, update_broadcast_message_delivery_time
)
from src.db.models import User
from src.db.survey_utils import get_user_active_surveys
from src.db.utils import save_parasite_message
from src.handlers.admin.utils import (
    delete_parasite_messages_and_update_change_broadcast_keyboard,
    update_change_broadcast_keyboard
)
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards.admin_inline import (
    create_my_active_broadcast_inline_keyboard,
    create_change_broadcast_message_inline_keyboard
)
from src.scheduler.utils import remove_broadcast_message_jobs
from src.states.change_broadcast_state import ChangeBroadcastMessageState
from src.utils import admin, active_user, split_message
from src.utils.broadcast import create_broadcast_tasks_by_timezone
from src.utils.calendar import processing_simple_calendar_date_selection, send_simple_calendar

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(BroadcastCallback.filter(F.type == BroadcastMessageType.my_active_broadcast))  # type: ignore
@admin
async def my_active_broadcast(
        callback_query: CallbackQuery,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Отправляет клавиатуру с активными рассылками администратора"""
    try:
        # Список рассылаемых сообщений и опросов текущего пользователя, которых рассылка ещё не началась
        broadcast_messages = await get_user_active_broadcast_messages(db_session, user.id)
        surveys = await get_user_active_surveys(db_session, user.id)
        await callback_query.message.edit_reply_markup(
            reply_markup=create_my_active_broadcast_inline_keyboard(broadcast_messages, surveys))
    except TelegramBadRequest:
        logging.warning(f'Не удалось изменить клавиатуру пользователя %s на мои активные рассылки.')


@router.callback_query(MyActiveBroadcastCallback.filter(F.type == BroadcastType.message))  # type: ignore
async def broadcast_message_detail_callback(
        callback_query: CallbackQuery,
        callback_data: MyActiveBroadcastCallback,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Оптравляет детали сообщения для рассылки и инлайн клавиатуру для взаиодействия с сообщением."""
    broadcast_message = await get_broadcast_message(db_session, callback_data.id)
    try:
        list_of_messages_for_broadcast = split_message(str(broadcast_message.message))
        length = len(list_of_messages_for_broadcast) - 1
        for index, part_message in enumerate(list_of_messages_for_broadcast):
            if index == length:
                answer_message = await callback_query.message.answer(
                    part_message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=create_change_broadcast_message_inline_keyboard(callback_data.id)
                )
            else:
                answer_message = await callback_query.message.answer(part_message, parse_mode=ParseMode.HTML)
            await save_parasite_message(db_session, callback_query.message.chat.id, answer_message.message_id)

        await state.set_state(ChangeBroadcastMessageState.ChangeBroadcastMessage)
        await state.set_data({'admin_panel_message_id': callback_query.message.message_id})
        await callback_query.answer()
    except TelegramBadRequest:
        logging.warning(f'Не удалось отправить сообщение для изменения сообщения для рассылки %s пользователю %s',
                        callback_data.id, user.id)


@router.callback_query(
    ChangeBroadcastMessageState.ChangeBroadcastMessage,
    EditBroadcastCallback.filter(F.action == ActionBroadcastType.delete)  # type: ignore
)
@active_user
@admin
async def delete_broadcast_message_callback(
        callback_query: CallbackQuery,
        callback_data: EditBroadcastCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Удаляет сообщение для рассылки"""
    try:
        # Удаление задачи
        await remove_broadcast_message_jobs(callback_data.id)
        await delete_broadcast_message(db_session, callback_data.id)

        # Очистка сообщений и обновление клавиатуры
        state_data = await state.get_data()
        await delete_parasite_messages_and_update_change_broadcast_keyboard(
            callback_query,
            state,
            db_session,
            user.id,
            state_data['admin_panel_message_id']
        )
        logger.info(f'Пользователь %s удалил сообщение для рассылки %s', user.id, callback_data.id)
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка удаления сообщения изменения рассылки %s для пользователя %s: %s',
                        callback_data.id, user.id, e)
    except Exception as e:
        logging.error(f'Ошибка удаления сообщения для рассылки %s пользователем %s: %s', callback_data.id, user.id, e)


@router.callback_query(
    ChangeBroadcastMessageState.ChangeBroadcastMessage,
    EditBroadcastCallback.filter(F.action == ActionBroadcastType.back)  # type: ignore
)
async def back_to_active_broadcast(
        callback_query: CallbackQuery,
        callback_data: EditBroadcastCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
):
    """Удаляет сообщение с изменением сообщения для рассылки и сбрасывает состояние пользователя"""
    await state.clear()
    await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
    logger.info(f'Пользователь %s отменил изменение рассылки %s', user.id, callback_data.id)


@router.callback_query(
    ChangeBroadcastMessageState.ChangeBroadcastMessage,
    EditBroadcastCallback.filter(F.action == ActionBroadcastType.edit_text)  # type: ignore
)
@active_user
@admin
async def get_new_broadcast_message_text(
        callback_query: CallbackQuery,
        callback_data: EditBroadcastCallback,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """Запрашивает сообщение с новым текстом для рассылки сообщения"""
    state_data = await state.get_data()
    state_data['broadcast_message_id'] = callback_data.id
    await state.set_data(state_data)
    await state.set_state(ChangeBroadcastMessageState.WaitingNewText)
    try:
        await callback_query.answer(messages.REQUEST_NEW_BROADCAST_MESSAGE_TEXT)
        logger.info(f'Пользователь %s запросил изменение сообщения для рассылки %s', user.id, callback_data.id)
    except TelegramBadRequest as e:
        logging.info(f'Ошибка отправки сообщения пользователю %s: %s', user.id, e)


@router.message(ChangeBroadcastMessageState.WaitingNewText, F.text)
@active_user
@admin
async def edit_broadcast_message_text(
        message: Message,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """
    Изменяем сообщение для рассылки, обновляет задачи для рассылки этого сообщения.
    Во время выполнения задачи по рассылке сообщения оно берётся из БД. Поэтому сами задачи обновлять не нужно.
    """
    state_data = await state.get_data()
    await state.clear()

    # Изменить текст сообщения для рассылки в БД.
    try:
        broadcast_message = await get_broadcast_message(db_session, state_data.get('broadcast_message_id', 0))
        if broadcast_message:
            broadcast_message_text = broadcast_message.message.split('\n')[0] + '\n' + message.html_text
            await update_broadcast_message_text(db_session, broadcast_message.id, broadcast_message_text)

            answer_message = await message.answer(text=messages.BROADCAST_MESSAGE_UPDATED)
            await update_change_broadcast_keyboard(
                message.bot,
                db_session,
                user.id,
                message.chat.id,
                state_data['admin_panel_message_id']
            )
            await delete_parasite_messages(message.bot, db_session, answer_message.chat.id)
            await message.delete()
            await asyncio.sleep(settings.SLEEP_TIME)
            await answer_message.delete()
            logger.info(f'Пользователь %s изменил текст сообщения для рассылки %s', user.id, broadcast_message.id)
        logger.warning(f'Не удалось изменить текст сообщения для рассылки %s. Сообщение не найдено.',
                       state_data.get('broadcast_message_id', 0))
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка отправки сообщения во время изменения текста рассылаемого сообщения %s: %s',
                        user.id, e)


@router.callback_query(
    ChangeBroadcastMessageState.ChangeBroadcastMessage,
    EditBroadcastCallback.filter(F.action == ActionBroadcastType.edit_date)  # type: ignore
)
@active_user
@admin
async def get_new_broadcast_message_start_date(
        callback_query: CallbackQuery,
        callback_data: EditBroadcastCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    try:
        state_data = await state.get_data()
        await state.set_state(ChangeBroadcastMessageState.NewDateSelection)
        await callback_query.answer()

        state_data['broadcast_message_id'] = callback_data.id
        min_date = datetime.datetime.now()
        max_date = datetime.datetime.now() + datetime.timedelta(days=13)
        state_data['min_date'] = min_date.isoformat()
        state_data['max_date'] = max_date.isoformat()
        await state.set_data(state_data)

        # Отправка календаря
        await send_simple_calendar(
            callback_query.bot,
            callback_query.message.chat.id,
            db_session,
            min_date,
            max_date,
        )
        await callback_query.message.delete_reply_markup()
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка удаления сообщения для пользователя %s при изменении даты рассылки сообщения %s: %s',
                        user.id, callback_data.id, e)


@router.callback_query(
    ChangeBroadcastMessageState.NewDateSelection,
    SimpleCalendarCallback.filter(),
)
async def process_new_date_selection_for_message_broadcast(
        callback_query: CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Обрабатывает запрос на выбор новой даты."""
    try:
        is_selected = await processing_simple_calendar_date_selection(
            callback_query,
            callback_data,
            state,
            db_session,
            user.id,
        )

        if is_selected:
            state_data = await state.get_data()
            await state.clear()
            date = datetime.datetime.fromisoformat(state_data['date'])
            broadcast_message = await get_broadcast_message(db_session, state_data.get('broadcast_message_id', 0))

            if broadcast_message:
                delivery_time = datetime.datetime.combine(date, settings.BROADCAST_TIME).replace(
                    tzinfo=datetime.timezone.utc)

                # Удаление старых задач
                await update_broadcast_message_delivery_time(db_session, broadcast_message.id, delivery_time)
                await remove_broadcast_message_jobs(broadcast_message.id)

                # Создание новых задач для рассылки
                await create_broadcast_tasks_by_timezone(
                    db_session,
                    broadcast_message.id,
                    delivery_time,
                )
                await callback_query.answer(messages.BROADCAST_MESSAGE_UPDATED, show_alert=True)
            else:
                await callback_query.answer(messages.EDIT_BROADCAST_MESSAGE_ERROR, show_alert=True)

            await callback_query.message.delete()
            await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)

            await update_change_broadcast_keyboard(
                callback_query.bot,
                db_session,
                user.id,
                callback_query.message.chat.id,
                state_data.get('admin_panel_message_id', 0)
            )
            logging.info(f'Пользователь %s, изменил дату рассылки сообщения %s', user.id, broadcast_message.id)
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка ответа пользователю %s: %s', user.id, e)
