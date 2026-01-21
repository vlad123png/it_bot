import logging

from aiogram import types, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import ChoiceSelectCallback, ChoiceCompleteCallback
from src.db.models import User
from src.db.utils import save_parasite_message
from src.messages import (
    ALREADY_SELECTED_MESSAGE,
    NOT_SELECTED_MESSAGE,
    SELECTED_MESSAGE
)
from src.states import TaskStates
from .process_form import process_form

router = Router()


@router.callback_query(
    TaskStates.ChoiceSelection,
    ChoiceSelectCallback.filter()
)
async def process_multiple_choice_selection(
        callback_query: types.CallbackQuery,
        callback_data: ChoiceSelectCallback,
        state: FSMContext,
        db_session,
        user: User
):
    """Обрабатывает запрос на выбор нескольких элементов из списка."""
    data = await state.get_data()
    field = data['field']
    if (
            data['task_timestamp'] == callback_data.task_timestamp
            and field['key'] == callback_data.field_key
    ):
        try:
            if not field.get('value'):
                field['value'] = []
            option = next(
                option
                for option in field['options']
                if option['Id'] == callback_data.option_id
            )
            if callback_data.option_id not in field['value']:
                field['value'].append(callback_data.option_id)
                selected_message = await callback_query.message.answer(
                    SELECTED_MESSAGE.format(option['Name'])
                )
                await save_parasite_message(db_session, selected_message.chat.id, selected_message.message_id)
            else:
                already_selected_message = await callback_query.message.answer(
                    ALREADY_SELECTED_MESSAGE.format(repr(option['Name']))
                )
                await save_parasite_message(
                    db_session,
                    already_selected_message.chat.id,
                    already_selected_message.message_id
                )
            await state.update_data(data)
        except TelegramBadRequest as e:
            logging.warning(f'Ошибка Telegram API. Пользователь: %s. Ошибка: %s', user.id, e)


@router.callback_query(
    TaskStates.ChoiceSelection,
    ChoiceCompleteCallback.filter()
)
async def process_multiple_choice_complete(
        callback_query: types.CallbackQuery,
        callback_data: ChoiceCompleteCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
):
    """
    Обрабатывает запрос на завершение выбора из списка.
    """
    data = await state.get_data()
    field = data['field']
    if (
            data['task_timestamp'] == callback_data.task_timestamp
            and field['key'] == callback_data.field_key
    ):
        try:
            if not field.get('value'):
                await callback_query.answer(NOT_SELECTED_MESSAGE, show_alert=True)
            else:
                await state.set_state()
                await callback_query.message.delete()
                await process_form(router, callback_query.message, state, db_session)
        except TelegramBadRequest as e:
            logging.warning(f'Ошибка Telegram API. Пользователь: %s. Ошибка: %s', user.id, e)
