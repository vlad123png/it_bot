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
    MyActiveBroadcastCallback,
    BroadcastType,
    ActionBroadcastType,
    EditBroadcastCallback,
)
from src.config.settings import settings
from src.db.models import User, SurveyChoice
from src.db.survey_utils import delete_survey, update_survey, get_survey_by_id, change_survey_choices
from src.db.utils import save_parasite_messages, save_parasite_message
from src.handlers.admin.survey.utils import answer_user_after_edit_survey
from src.handlers.admin.utils import (
    update_change_broadcast_keyboard,
    delete_parasite_messages_and_update_change_broadcast_keyboard
)
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards.admin_inline import create_change_survey_broadcast_inline_keyboard, create_number_keyboard
from src.keyboards.survey import get_example_choices_inline_keyboard
from src.scheduler.utils import remove_broadcast_survey_jobs
from src.states.change_broadcast_state import ChangeBroadcastSurveyState
from src.utils import active_user, admin
from src.utils.broadcast import create_task_for_broadcast_survey_by_timezones
from src.utils.calendar import send_simple_calendar, processing_simple_calendar_date_selection

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(MyActiveBroadcastCallback.filter(F.type == BroadcastType.survey))
async def broadcast_message_detail_callback(
        callback_query: CallbackQuery,
        callback_data: MyActiveBroadcastCallback,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Оптравляет детали сообщения для рассылки и инлайн клавиатуру для взаиодействия с сообщением."""
    survey = await get_survey_by_id(db_session, callback_data.id, include_choices=True)
    if survey is None:
        not_found_message = await callback_query.answer(f'Опрос не найден!')
        await save_parasite_message(db_session, callback_query.message.chat.id, not_found_message)
        return

    try:
        example_message = await callback_query.message.answer(
            text=survey.question,
            reply_markup=get_example_choices_inline_keyboard([choice.text for choice in survey.choices]),
            parse_mode=ParseMode.HTML,
        )
        handle_message = await callback_query.message.answer(
            text='Проверьте корректность опроса.',
            reply_markup=create_change_survey_broadcast_inline_keyboard(survey.id)
        )
        await save_parasite_messages(
            db_session,
            callback_query.message.chat.id,
            [example_message.message_id, handle_message.message_id]
        )

        await state.set_state(ChangeBroadcastSurveyState.ChangeBroadcastSurvey)
        await state.set_data({
            'admin_panel_message_id': callback_query.message.message_id,
            'survey_id': survey.id
        })
        await callback_query.answer()
    except TelegramBadRequest as e:
        logging.warning(f'Не удалось отправить сообщение для изменения сообщения для рассылки %s пользователю %s:%s',
                        callback_data.id, user.id, e)


@router.callback_query(
    ChangeBroadcastSurveyState.ChangeBroadcastSurvey,
    EditBroadcastCallback.filter(F.action == ActionBroadcastType.back)
)
async def cancel_change_survey_broadcast_callback(
        callback_query: CallbackQuery,
        callback_data: MyActiveBroadcastCallback,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Удаляет сообщение с изменением опроса для рассылки и сбрасывает состояние пользователя"""
    await state.clear()
    await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
    logger.info(f'Пользователь %s отменил изменение опроса %s', user.id, callback_data.id)


@router.callback_query(
    ChangeBroadcastSurveyState.ChangeBroadcastSurvey,
    EditBroadcastCallback.filter(F.action == ActionBroadcastType.delete)
)
@active_user
@admin
async def delete_survey_broadcast_callback(
        callback_query: CallbackQuery,
        callback_data: MyActiveBroadcastCallback,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Удаляет опрос для рассылки"""
    try:
        # Удаление
        await remove_broadcast_survey_jobs(callback_data.id)
        await delete_survey(db_session, callback_data.id)

        # Очистка сообщений и обновление клавиатуры
        state_data = await state.get_data()
        await delete_parasite_messages_and_update_change_broadcast_keyboard(
            callback_query,
            state,
            db_session,
            user.id,
            state_data.get('admin_panel_message_id', 0)
        )
        logger.info(f'Пользователь %s удалил опрос для рассылки %s', user.id, callback_data.id)
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка удаления рассылки опроса %s пользователем %s: %s',
                        callback_data.id, user.id, e)
    except Exception as e:
        logging.error(f'Ошибка удаления рассылки опроса %s пользователем %s: %s', callback_data.id, user.id, e)


@router.callback_query(
    ChangeBroadcastSurveyState.ChangeBroadcastSurvey,
    EditBroadcastCallback.filter()
)
@active_user
@admin
async def get_new_survey_question_callback(
        callback_query: CallbackQuery,
        callback_data: EditBroadcastCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """ Обрабатывает выбранный параметр для изменения опроса. """
    try:
        # Запрос сообщения для изменения текста, ответов или максимального количество для выбора.
        if callback_data.action in (
                ActionBroadcastType.edit_choices,
                ActionBroadcastType.edit_text
        ):
            state_mapper = {
                ActionBroadcastType.edit_choices: (
                    ChangeBroadcastSurveyState.InputNewChoices, messages.GET_SURVEY_CHOICES),
                ActionBroadcastType.edit_max_number: (
                    ChangeBroadcastSurveyState.InputMaxNumberChoices, messages.REQUEST_MAX_CHOICES_NUMBER),
                ActionBroadcastType.edit_text: (
                    ChangeBroadcastSurveyState.InputNewQuestion, messages.REQUEST_NEW_SURVEY_QUESTION),
            }
            new_state, message = state_mapper[callback_data.action]
            await state.set_state(new_state)
            await callback_query.answer(text=message, show_alert=True)
            await callback_query.message.delete_reply_markup()

        elif callback_data.action == ActionBroadcastType.edit_max_number:
            await state.set_state(ChangeBroadcastSurveyState.InputMaxNumberChoices)
            survey = await get_survey_by_id(db_session, callback_data.id, True)
            if survey:
                max_number_of_choices = len(survey.choices)
                await callback_query.message.edit_text(
                    text=messages.GET_MAX_NUMBER_CHOICES,
                    reply_markup=create_number_keyboard(max_number_of_choices)
                )

        # Выбор новой даты рассылки опроса
        elif callback_data.action == ActionBroadcastType.edit_date:
            state_data = await state.get_data()
            min_date = datetime.datetime.now()
            max_date = datetime.datetime.now() + datetime.timedelta(days=13)
            state_data['min_date'] = min_date.isoformat()
            state_data['max_date'] = max_date.isoformat()
            await state.set_data(state_data)
            await state.set_state(ChangeBroadcastSurveyState.NewStartDateSelection)
            await callback_query.answer(text=messages.SURVEY_START_DATE_SELECTION, show_alert=True)
            await send_simple_calendar(
                callback_query.bot,
                callback_query.message.chat.id,
                db_session,
                min_date,
                max_date,
            )
            await callback_query.message.delete_reply_markup()
        logger.info(f'Пользователь {user.id} изменяет опрос {callback_data.id}')
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка отправки сообщения пользователю %s при изменении опроса %s: %s',
                        user.id, callback_data.id, e)


@router.message(ChangeBroadcastSurveyState.InputNewChoices, F.text)
@active_user
@admin
async def change_broadcast_survey_choices(
        message: Message,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Изменяет ответы на опрос."""
    try:
        state_data = await state.get_data()
        survey = await get_survey_by_id(db_session, state_data.get('survey_id'), True)

        # Изменение опроса
        new_choices = [SurveyChoice(text=text, survey_id=survey.id) for text in message.text.split('#') if text]
        if not new_choices:
            empty_message = await message.answer(messages.EMPTY_MESSAGE)
            await save_parasite_messages(
                db_session,
                empty_message.chat.id,
                [empty_message.message_id, message.message_id]
            )
            return
        await change_survey_choices(db_session, survey.id, new_choices)

        # Запрос нового максимального количества ответов
        max_number_of_choices = len(new_choices)
        await message.answer(
            text=messages.GET_MAX_NUMBER_CHOICES,
            reply_markup=create_number_keyboard(max_number_of_choices)
        )
        await state.set_state(ChangeBroadcastSurveyState.InputMaxNumberChoices)
        await message.delete()
    except TelegramBadRequest as e:
        logger.warning(f'Ошибка отправки сообщения пользователю %s: %s', user.id, e)


@router.message(ChangeBroadcastSurveyState.InputNewQuestion, F.text)
@active_user
@admin
async def change_broadcast_survey_text(
        message: Message,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Изменяет текст опроса. """
    state_data = await state.get_data()
    survey = await get_survey_by_id(db_session, state_data.get('survey_id'))
    survey.question = message.html_text + f'\nМожно выбрать до {survey.max_choices} вариантов ответов.'
    await update_survey(db_session, survey)

    # Очистка чата, обновление админ панели
    await answer_user_after_edit_survey(
        message.bot,
        db_session,
        message.chat.id,
        user.id,
        state_data.get('admin_panel_message_id', 0)
    )
    await message.delete()


@router.callback_query(ChangeBroadcastSurveyState.InputMaxNumberChoices)
@active_user
@admin
async def change_broadcast_survey_max_number_choices(
        callback_query: CallbackQuery,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """Изменяет максимальное количество ответов в опросе. """
    state_data = await state.get_data()
    survey = await get_survey_by_id(db_session, state_data.get('survey_id'), True)
    max_number_choices = int(callback_query.data)

    try:
        # Проверка на совпадение с предыдущим значением
        if survey.max_choices == max_number_choices:
            await callback_query.answer(messages.SAME_MAX_CHOICES_NUMBER)
            return

        # Сохранение нового значения
        parts = survey.question.rsplit('\n', 1)
        survey.question = f'{parts[0]}\nМожно выбрать до {max_number_choices} вариантов ответов.'
        survey.max_choices = max_number_choices
        await update_survey(db_session, survey)

        # Очистка чата, обновление админ панели
        await answer_user_after_edit_survey(
            callback_query.bot,
            db_session,
            callback_query.message.chat.id,
            user.id,
            state_data.get('admin_panel_message_id', 0)
        )
        await state.clear()
        await callback_query.message.delete()
    except TelegramBadRequest as e:
        logging.info(f'Ошибка отправки сообщения пользователю %s: %s', user.id, e)


@router.callback_query(ChangeBroadcastSurveyState.NewStartDateSelection, SimpleCalendarCallback.filter())
async def process_change_broadcast_survey_start_date(
        callback_query: CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Выбор новой даты для рассылки опроса."""
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
            date = datetime.datetime.fromisoformat(state_data.get('date'))
            state_data['start_datetime'] = datetime.datetime.combine(
                date,
                settings.BROADCAST_TIME
            ).replace(tzinfo=datetime.timezone.utc).isoformat()
            min_date = date + datetime.timedelta(days=2)
            max_date = min_date + datetime.timedelta(days=13)
            state_data['min_date'] = min_date.isoformat()
            state_data['max_date'] = max_date.isoformat()
            await state.set_data(data=state_data)
            await state.set_state(ChangeBroadcastSurveyState.NewEndDateSelection)
            await callback_query.answer(text=messages.SURVEY_END_DATE_SELECTION, show_alert=True)

            await send_simple_calendar(
                callback_query.bot,
                callback_query.message.chat.id,
                db_session,
                min_date,
                max_date,
            )
            await callback_query.message.delete()
    except TelegramBadRequest as e:
        logger.warning(f'Ошибка отправки сообщения пользователю %s: %s', user.id, e)


@router.callback_query(ChangeBroadcastSurveyState.NewEndDateSelection, SimpleCalendarCallback.filter())
async def process_change_broadcast_survey_end_date(
        callback_query: CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Выбор новой даты завершения опроса."""
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
            date = datetime.datetime.fromisoformat(state_data.get('date'))
            end_datetime = datetime.datetime.combine(
                date,
                settings.BROADCAST_TIME
            ).replace(tzinfo=datetime.timezone.utc)

            # Обновление опроса
            survey = await get_survey_by_id(db_session, state_data.get('survey_id'), True)
            survey.start_date = datetime.datetime.fromisoformat(state_data.get('start_datetime'))
            survey.end_date = end_datetime
            await update_survey(db_session, survey)

            # Обновление задач
            await remove_broadcast_survey_jobs(survey.id)
            await create_task_for_broadcast_survey_by_timezones(
                db_session,
                survey.id,
                survey.question,
                survey.start_date,
                end_datetime,
                user,
                [[choice.text, choice.id] for choice in survey.choices]
            )

            # Очистка чата, обновление админ панели
            await callback_query.answer(text=messages.SURVEY_UPDATED, show_alert=True)
            await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
            await update_change_broadcast_keyboard(
                callback_query.bot,
                db_session,
                user.id,
                callback_query.message.chat.id,
                state_data.get('admin_panel_message_id', 0)
            )
            await state.clear()
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка отправки сообщения пользователю %s: %s', user.id, e)
