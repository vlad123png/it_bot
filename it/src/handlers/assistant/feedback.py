import logging
from random import choice

from aiogram import Router, types, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.backend_api import BackendAPI
from src.backend_api.schemas import CreateRetailMessageFeedbackSchema
from src.callbacks import ReactionCallback, ReactionType, FeedbackCallback, FeedbackAction, AnswerFeedbackCallback
from src.db.models import User
from src.db.utils import save_parasite_message, increment_feedback
from src.handlers.assistant.utils import (
    delete_parasite_messages,
    process_voice_message,
    check_text_message_for_empty
)
from src.keyboards.inline import get_feedback_keyboard
from src.messages import BAD_REACTION_MESSAGE
from src.states.feedback_states import FeedbackStates

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(ReactionCallback.filter())
async def reaction_handler(
        callback_query: types.CallbackQuery,
        callback_data: ReactionCallback,
        db_session: AsyncSession,
        backend_service: BackendAPI,
        state: FSMContext,
        user: User,
):
    """Обработка кнопок реакций на сообщение с ответом ИИ"""
    reaction: ReactionType = callback_data.type
    try:
        if reaction == ReactionType.like:
            notification_message_text = choice(messages.LIST_EMOJI_GOOD)
        elif reaction == ReactionType.dislike:
            notification_message_text = choice(messages.LIST_EMOJI_BAD)
        else:
            notification_message_text = 'Спасибо за отзыв!'

        await callback_query.answer(text=notification_message_text)

        current_markup = callback_query.message.reply_markup
        builder = InlineKeyboardBuilder()
        for button in current_markup.inline_keyboard:
            for btn in button:
                if btn.callback_data.startswith('reaction'):
                    continue
                builder.button(text=btn.text, callback_data=btn.callback_data)
        builder.adjust(1)

        await callback_query.message.edit_reply_markup(reply_markup=builder.as_markup())

    except TelegramBadRequest as e:
        logging.exception(
            f'Reaction_hendler: Ошибка при изменении клавиатуры сообщения %s для пользователя %s: %s',
            callback_query.message.message_id, callback_query.from_user.id, e, exc_info=False)
        return

    # Сохраняем выбор
    data = CreateRetailMessageFeedbackSchema(
        retail_message_id=callback_data.id,
        reaction=reaction,
    )
    await backend_service.send_retail_message_feedback(data)
    await increment_feedback(db_session, bool(reaction == ReactionType.like))

    logger.info(
        'Пользователь %s оставил реакцию %s на сообщение %s',
        user.telegram_id, reaction, callback_query.message.message_id
    )


@router.callback_query(AnswerFeedbackCallback.filter())
async def report_answer(
        callback_query: types.CallbackQuery,
        callback_data: AnswerFeedbackCallback,
        state: FSMContext,
        user: User,
):
    try:
        await state.set_state(FeedbackStates.WaitingFeedback)

        await state.set_data({'ai_message_id': callback_query.message.message_id, 'processing_voice': 0})
        await callback_query.message.answer(
            text=BAD_REACTION_MESSAGE,
            reply_markup=get_feedback_keyboard(callback_data.id)
        )
        await callback_query.answer()
        logging.info('Пользователь %s начал формировать отзыв об ответе бота %s', user.id,
                     callback_query.message.message_id)
    except TelegramBadRequest as e:
        logging.warning('Телеграм API ошибка. Пользователь: %s. Ошибка: %s', user.id, e)


@router.callback_query(FeedbackCallback.filter())
async def feedback_handler(
        callback_query: types.CallbackQuery,
        callback_data: FeedbackCallback,
        state: FSMContext,
        bot: Bot,
        db_session: AsyncSession,
        backend_service: BackendAPI,
        user: User,
):
    """Обработка кнопок фидбэка"""
    action = callback_data.action
    message_id = callback_query.message.message_id

    try:
        # Пользователь отказался оставлять сообщение. Удаляем сообщение
        if action == FeedbackAction.skip:
            logger.info(f'Пользователь %s отказался оставлять фидбэк для сообщения %s',
                        user.telegram_id, message_id)

        # Сообщаем пользователю, что ожидаем сообщения с фитбэком
        elif action == FeedbackAction.leave:
            data = await state.get_data()
            user_feedbacks = data.get('user_feedbacks')

            # Если обработка голосовго сообщения ещё не закончена
            if data.get('processing_voice', 0) > 0:
                await callback_query.answer(
                    text=messages.TEXT_RECOGNIZE_NOT_DONE_MESSAGE,
                    show_alert=True
                )
                return

            # Если пользователь ничего не написал
            if not user_feedbacks:
                await callback_query.answer(text=messages.EMPTY_MESSAGE, show_alert=True)
                await state.set_state(FeedbackStates.WaitingFeedback)
                return

            # Сохраняем фидбэк в базу данных
            feedback_data = CreateRetailMessageFeedbackSchema(retail_message_id=callback_data.id,
                                                              content=user_feedbacks)
            await backend_service.send_retail_message_feedback(feedback_data)
            await callback_query.answer(text=messages.ANSWER_FEEDBACK_MESSAGE, show_alert=True)

        # Уведомляем пользователя, что его фитбэк сохранён.
        await state.clear()
        await callback_query.message.delete()
        await delete_parasite_messages(bot, db_session, callback_query.message.chat.id)
    except TelegramBadRequest as e:
        logging.warning(f'Telegram API ошибка. пользователь %s при обработке клавиатуры фитбэка: %s', user.id, e)


@router.message(FeedbackStates.WaitingFeedback)
async def get_feedback_handler(
        message: types.Message,
        state: FSMContext,
        bot: Bot,
        db_session: AsyncSession,
        user: User
):
    """Получение фидбэка и запись его в БД."""
    try:
        data = await state.get_data()

        # Транскрибация голосового сообщения.
        if message.voice:
            data['processing_voice'] += 1
            await state.set_data(data)
            recognize_text_message = await message.answer(messages.TEXT_RECOGNIZE_MESSAGE)
            feedback = await process_voice_message(message, bot, user.id)
            data = await state.get_data()
            data['processing_voice'] -= 1
            await recognize_text_message.edit_text(text=f'Вы сказали: {feedback}')
            await save_parasite_message(db_session, message.chat.id, recognize_text_message.message_id)
        else:
            feedback = message.text

        if not await check_text_message_for_empty(feedback, message, db_session):
            await state.set_data(data)
            return

        # сохраняем паразитное сообщение
        await save_parasite_message(db_session, message.chat.id, message.message_id)

        # Сохраняем сообщения в состояние пользователя
        previous_feedbacks = data.get('user_feedbacks', '')
        data['user_feedbacks'] = f'{previous_feedbacks}\n{feedback}'.strip()
        await state.set_data(data)
    except TelegramBadRequest as e:
        logging.warning(f'Ошибка отправки сообщения пользователю %s при обработке отзыва на ответ LLM: %s', user.id, e)
