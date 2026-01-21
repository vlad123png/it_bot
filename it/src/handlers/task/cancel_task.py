import logging

from aiogram import F, types, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import TaskAction, TaskCallback
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards import get_main_inline_keyboard
from src.messages import TASK_CANCEL_MESSAGE, CREATE_TASK_MESSAGE
from src.states import TaskStates
from src.utils import active_user, cleanup

router = Router()


@router.callback_query(
  TaskStates.TaskConfirmation,
  TaskCallback.filter(F.action == TaskAction.cancel)
)
@active_user
async def process_cancel_task(
    callback_query: types.CallbackQuery,
    callback_data: TaskCallback,
    state: FSMContext,
    db_session: AsyncSession,
    *args, **kwargs
):
  """Обрабатывает запрос на отмену текущей заявки."""
  data = await state.get_data()
  try:
    if data['task_timestamp'] == callback_data.task_timestamp:
      await state.set_state()
      await callback_query.answer(TASK_CANCEL_MESSAGE)
      await callback_query.message.answer(
        text=CREATE_TASK_MESSAGE,
        reply_markup=await get_main_inline_keyboard()
      )
      await cleanup(state)
      await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
  except TelegramBadRequest:
    logging.debug('Не удалось удалить сообщение об подтверждении отправки заявки.')
