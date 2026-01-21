import logging

from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.callbacks import BroadcastCallback, BroadcastMessageType
from src.db.models import User
from src.db.survey_utils import get_survey_results
from src.db.utils import save_parasite_message
from src.states.admin import AdminState
from src.utils import active_user, admin, digit_only

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(BroadcastCallback.filter(F.type == BroadcastMessageType.survey_result))
@active_user
@admin
async def get_survey_id(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        user: User,
        *args, **kwargs
):
    """ Запрашивает ID опроса для формирования результата. """
    await callback_query.answer(text=messages.REQUEST_SURVEY_ID, show_alert=True)
    await state.set_state(AdminState.WaitingSurveyId)
    logger.info(f'Пользователь %s вводит ID для получения результата опроса.', user.id)


@router.message(AdminState.WaitingSurveyId, F.text)
@active_user
@admin
@digit_only
async def send_survey_result(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession,
        user: User,
        *args, **kwargs
):
    """ Отправляет результат опроса администратору по id. """
    survey = await get_survey_results(db_session, int(message.text), user.id)

    try:
        if not survey:
            not_found_message = await message.answer(text=f'Опрос с ID={message.text} не найден!')
            await save_parasite_message(db_session, message.chat.id, not_found_message.message_id)
        else:
            general_count_number = sum(choice.choice_count for choice in survey.choices)
            if general_count_number < 1:
                await message.answer(text=messages.SURVEY_REPORT_NOT_READY.format(survey.id, survey.question))
            else:
                await message.answer(text=messages.RESULT_SURVEY_MESSAGE.format(
                    survey.id,
                    survey.question,
                    '\n'.join(
                        f'<b>{(choice.choice_count / general_count_number * 100):.2f}%  '
                        f'({choice.choice_count} голосов)</b>: {choice.text}'
                        for choice in survey.choices)
                ))
        await state.clear()
        await message.delete()
    except TelegramBadRequest:
        logging.info(f'Не удалось отправить отчёт об опросе %s пользователю %s', message.text, user.id)

    logger.info(f'Пользователь %s запросил результаты опроса %s', user.id, survey.id)
