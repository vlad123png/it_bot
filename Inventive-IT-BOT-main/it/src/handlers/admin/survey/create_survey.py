import datetime
import logging

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.aiogram_calendar import SimpleCalendarCallback
from src.api_client import APIClient
from src.callbacks import (
    BroadcastCallback,
    BroadcastMessageType,
    ConfirmationCallback,
    ConfirmationAction,
)
from src.config.settings import settings
from src.db.models import User
from src.db.survey_utils import create_survey, create_survey_choices
from src.db.utils import save_parasite_messages
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards.admin_inline import create_number_keyboard
from src.keyboards.survey import confirm_survey_inline_keyboard, get_example_choices_inline_keyboard
from src.smtp_client import SMTPClient
from src.states.create_survey_state import CreateSurveyState
from src.utils import active_user, admin
from src.utils.broadcast import create_task_for_broadcast_survey_by_timezones
from src.utils.calendar import processing_simple_calendar_date_selection, send_simple_calendar

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(BroadcastCallback.filter(F.type == BroadcastMessageType.new_survey))
@active_user
@admin
async def create_questionnaire(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """ Запрашивает пользователя тему(вопрос) для опроса. """
    try:
        await callback_query.answer(text=messages.GET_QUESTION_SURVEY, show_alert=True)
        await state.set_state(CreateSurveyState.WaitingQuestion)
        logger.info('Пользователь %s начал создавать опрос.', user.id)
    except TelegramBadRequest:
        logging.warning(f'Ошибка отправки сообщения для получения темы опроса пользователю %s', user.id)


@router.message(CreateSurveyState.WaitingQuestion)
@active_user
@admin
async def get_question_survey(
        message: types.Message,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """ Получение вопроса (темы) опроса. Запрос вариантов ответов. """
    if not message.text:
        empty_message = await message.answer(messages.EMPTY_MESSAGE)
        await save_parasite_messages(
            db_session,
            empty_message.chat.id,
            [empty_message.message_id, message.message_id]
        )
        return

    # Сохранение вопроса
    data = await state.get_data()
    data['question'] = message.html_text
    await state.update_data(**data)
    # Запрос вариантов ответов
    try:
        answer_message = await message.answer(messages.GET_SURVEY_CHOICES)
        await state.set_state(CreateSurveyState.WaitingChoices)
        await save_parasite_messages(db_session, message.chat.id,
                                     [message.message_id, answer_message.message_id])
        logger.info(f'Пользователь %s ввёл тему опроса.', user.id)
    except TelegramBadRequest:
        logging.warning(f'Не удалось отправить сообщение об запросе темы опроса пользователю %s', user.id)


@router.message(CreateSurveyState.WaitingChoices)
@active_user
@admin
async def get_choice_survey(
        message: types.Message,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """ Получение вариантов ответов. Отправка клавиатуры на подтверждение текста опроса. """
    choices = [choice.strip() for choice in message.text.split('#') if choice.strip()] if message.text else []
    if not choices:
        empty_message = await message.answer(messages.EMPTY_MESSAGE)
        await save_parasite_messages(
            db_session,
            empty_message.chat.id,
            [empty_message.message_id, message.message_id]
        )
        return

    # Сохранение вариантов ответов
    data = await state.get_data()
    data['choices'] = choices
    await state.update_data(data)
    # Отправка сообщения с тем, как будет выглядеть опрос.
    try:
        example_message = await message.answer(
            text=data['question'],
            reply_markup=get_example_choices_inline_keyboard(choices),
            parse_mode=ParseMode.HTML,
        )
        confirm_message = await message.answer(
            text='Проверьте корректность опроса.',
            reply_markup=confirm_survey_inline_keyboard()
        )

        await save_parasite_messages(db_session, message.chat.id,
                                     [message.message_id, example_message.message_id, confirm_message.message_id])
        await state.set_state(CreateSurveyState.WaitingConfirmation)
        logger.info('Пользователь %s ввёл ответы для опросника.', user.id)
    except TelegramBadRequest:
        logging.warning(f'Не удалось отправить сообщение с подтверждение опроса пользователю %s', user.id)


@router.callback_query(
    CreateSurveyState.WaitingConfirmation,
    ConfirmationCallback.filter(F.action == ConfirmationAction.edit)  # noqa
)
async def edit_question_survey(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """ Обработка изменения текста опроса. Возвращает пользователя к шагу ввода темы опросника. """
    try:
        await state.set_state(CreateSurveyState.WaitingQuestion)
        await callback_query.answer(text=messages.GET_QUESTION_SURVEY, show_alert=True)
        await callback_query.message.delete_reply_markup()
        logger.info(f'Пользователь %s решил изменить текст опросника.', user.id)
    except TelegramBadRequest:
        logging.info(f'Не удалось убрать инлайн клавиатуру сообщения для пользователя %s', user.id)


@router.callback_query(
    CreateSurveyState.WaitingConfirmation,
    ConfirmationCallback.filter(F.action == ConfirmationAction.confirm)  # noqa
)
async def request_max_number_of_choices(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """ Подтверждение текста запроса. Запрос максимального количества ответов. """
    try:
        data = await state.get_data()
        max_number_of_choices = len(data['choices'])
        await state.set_state(CreateSurveyState.WaitingMaxNumberChoicesState)
        await callback_query.message.edit_text(
            text=messages.GET_MAX_NUMBER_CHOICES,
            reply_markup=create_number_keyboard(max_number_of_choices)
        )
    except TelegramBadRequest:
        logging.warning(f'Не удалось запросить максимальное количество ответов для опроса у пользователя %s', user.id)
    logger.info(f'Пользователь %s подтвердил опросник.', user.id)


@router.callback_query(CreateSurveyState.WaitingMaxNumberChoicesState)
async def get_max_number_of_choices(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """ Получение максимального количества вариантов ответа. """
    try:
        max_number_of_choices = int(callback_query.data)
        data = await state.get_data()
        data['max_number_choices'] = max_number_of_choices
        data['question'] = data['question'] + f'\nМожно выбрать до {max_number_of_choices} вариантов ответов.'

        min_date = datetime.datetime.now()
        max_date = datetime.datetime.now() + datetime.timedelta(days=13)
        data['min_date'] = min_date.isoformat()
        data['max_date'] = max_date.isoformat()
        await send_simple_calendar(
            callback_query.bot,
            callback_query.message.chat.id,
            db_session,
            min_date,
            max_date,
        )
        await state.set_state(CreateSurveyState.DateStartSelection)
        await state.set_data(data)
        await callback_query.answer(messages.SURVEY_START_DATE_SELECTION, show_alert=True)
        await callback_query.message.delete()
        logger.info(f'Пользователь %s, выбрал максимальное количество ответов: %s', user.id, max_number_of_choices)

    except TelegramBadRequest:
        logging.warning(f'Ошибка отправки сообщения выбора даты начала рассылки опроса пользователю %s', user.id)


@router.callback_query(
    CreateSurveyState.DateStartSelection,
    SimpleCalendarCallback.filter()
)
async def process_start_date_selection(
        callback_query: types.CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """ Обработка выбора даты отправки опроса в календаре. """
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
                # Сохранение времени старта
                data = await state.get_data()
                await state.set_state(CreateSurveyState.DateEndSelection)

                # Отправка сообщения с выбором даты завершения опроса
                data['start_date'] = data['date']
                # Минимум 2 дня перед началом и завершением опроса
                min_date = datetime.datetime.fromisoformat(data['date']) + datetime.timedelta(days=2)
                max_date = min_date + datetime.timedelta(days=13)
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
                await callback_query.answer(messages.SURVEY_END_DATE_SELECTION, show_alert=True)
            except TelegramBadRequest:
                logging.warning(
                    f'Ошибка отправки сообщения для получения даты окончания опроса пользователю %s',
                    user.id)
    except TelegramBadRequest:
        logging.warning(f'Ошибка отправки сообщения при обработки даты отправления опроса пользователю %s', user.id)


@router.callback_query(
    CreateSurveyState.DateEndSelection,
    SimpleCalendarCallback.filter()
)
async def process_end_date_selection(
        callback_query: types.CallbackQuery,
        callback_data: SimpleCalendarCallback,
        state: FSMContext,
        db_session: AsyncSession,
        api_client: APIClient,
        smtp_client: SMTPClient,
        user: User,
        *args, **kwargs
):
    """ Обработка выбора даты окончания опроса в календаре. """
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
                # Сохранение времени окончания опроса
                data = await state.get_data()
                start_datetime = (datetime.datetime.combine(
                    datetime.datetime.fromisoformat(data['start_date']),
                    settings.BROADCAST_TIME
                ).replace(tzinfo=datetime.timezone.utc))

                end_datetime = datetime.datetime.combine(
                    datetime.datetime.fromisoformat(data['date']),
                    settings.BROADCAST_TIME
                ).replace(tzinfo=datetime.timezone.utc)

                # Cоздание опроса в БД
                survey_id = await create_survey(
                    db_session,
                    user.id,
                    data['question'],
                    data['max_number_choices'],
                    start_datetime, end_datetime
                )
                # Создание вариантов ответов в БД
                choices = await create_survey_choices(db_session, survey_id, data['choices'])

                # Создание задачи для рассылки опроса.
                await create_task_for_broadcast_survey_by_timezones(
                    db_session,
                    survey_id,
                    data['question'],
                    start_datetime,
                    end_datetime,
                    user,
                    choices
                )
                await callback_query.message.answer(text=messages.SURVEY_CREATED.format(survey_id), show_alert=True)
                await state.clear()
                await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)

                # Отправка уведомление о создании опроса на почту
                inventive_user = await api_client.get_user(user.inventive_id)
                await smtp_client.send_email(
                    inventive_user.get('Email', settings.FEEDBACK_EMAIL),
                    'Создан новый опрос.',
                    messages.NEW_SURVEY_EMAIL_MESSAGE.format(survey_id),
                    settings.SENDER_EMAIL
                )
                logger.info(f'Пользователь %s создал опрос.', user.id)
            except TelegramBadRequest:
                logging.error(f'Не удалось ответить пользователю %s при создании задачи.', user.id)
            except Exception as e:
                logging.error(f'Ошибка при создании нового опроса пользователем %s: %s', user.id, e)
    except TelegramBadRequest:
        logging.warning(f'Ошибка отправки сообщения пользователю %s для получения даты окончания опроса.', user.id)
