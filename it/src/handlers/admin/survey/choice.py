import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.api_client import APIClient
from src.callbacks import SurveyChoiceCallback, ConfirmSurveyChoiceCallback
from src.db.models import User
from src.db.survey_utils import get_survey_with_choices_by_choice_id, save_user_choices
from src.db.users import get_user_survey_answers_by_survey_id
from src.handlers.admin.survey.utils import check_survey_finished
from src.keyboards.survey import get_choices_inline_keyboard
from src.utils import active_user, get_user_by_id

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(SurveyChoiceCallback.filter())
@active_user
async def processing_choices(
        callback_query: CallbackQuery,
        callback_data: SurveyChoiceCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """Обрабатка выбора ответа в опросе"""
    selected_choice_id = int(callback_data.choice_id)
    data = await state.get_data()
    selected_choices_id = data.get('selected_choices_id', [])
    survey = await get_survey_with_choices_by_choice_id(db_session, selected_choice_id)

    # Проверка найденного опросника
    if not survey:
        await callback_query.answer()
        logging.error(f'Ошибка извелечения опроса по id ответа. Опрос не найден. Survey choice id: %s',
                      selected_choice_id)
        return

    # Проверка окончания опроса
    if not await check_survey_finished(callback_query, user, survey):
        return

    # Отмена выбора
    if selected_choice_id in selected_choices_id:
        selected_choices_id.remove(selected_choice_id)
        logger.info(f'Пользователь %s, отменил выбор ответа %s на опрос %s', user.id, survey.id, selected_choice_id)
    else:
        if len(selected_choices_id) >= survey.max_choices:
            await callback_query.answer(text=messages.REACHED_MAX_SELECT_CHOICES, show_alert=True)
            logger.info(f'Пользователь %s попытался добавить ответ сверхлимита %s', user.id, survey.max_choices)
            return
        else:
            selected_choices_id.append(selected_choice_id)
            logger.info(f'Пользователь %s, выбрал ответ %s на опрос %s', user.id, survey.id, selected_choice_id)

    # Обновление клавиатуры
    data['selected_choices_id'] = selected_choices_id
    await state.set_data(data)
    await callback_query.message.edit_reply_markup(reply_markup=get_choices_inline_keyboard(
        [[choice.text, choice.id] for choice in survey.choices], selected_choices_id, survey.id)
    )


@router.callback_query(ConfirmSurveyChoiceCallback.filter())
@active_user
async def confirm_survey_choice(
        callback_query: CallbackQuery,
        callback_data: ConfirmSurveyChoiceCallback,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        api_client: APIClient,
        *args, **kwargs
):
    """Обрабатывает нажатие кнопки 'Отправить' при опросе. Сохраняет результат опроса пользователя в БД. """
    data = await state.get_data()
    selected_choices_id = data.get('selected_choices_id', [])

    # Проверка выбора хотя бы 1 варианта ответа
    if not selected_choices_id:
        await callback_query.answer(text=messages.NOT_SELECTED_CHOICES, show_alert=True)
        logger.info(f'Попытка завершить опрос без вариантов ответов пользователем %s.', user.id)
        return

    survey = await get_survey_with_choices_by_choice_id(db_session, selected_choices_id[0])
    if not survey:
        return

    # Проверка окончания опроса
    if not await check_survey_finished(callback_query, user, survey):
        return

    # Проверка прохождения опроса
    if await get_user_survey_answers_by_survey_id(db_session, user.id, survey.id):
        await callback_query.answer(text=messages.SURVEY_ALREADY_PASSED)
        await callback_query.message.delete()
        return

    await save_user_choices(db_session, user.id, survey.id, selected_choices_id)
    await state.clear()
    try:
        inventive_user = await get_user_by_id(api_client, user.inventive_id)
        name = inventive_user.get('Name', callback_query.from_user.full_name)
        await callback_query.answer(
            text=messages.SURVEY_COMPLETED.format(name),
            show_alert=True
        )
        await callback_query.message.delete()
    except TelegramBadRequest:
        logging.warning(f'Не удалось ответить пользователю %s на звершение опроса %s.', user.id, survey.id)

    logger.info(f'Пользователь %s завершил опрос %s с выбором %s', user.id, survey.id, selected_choices_id)
