from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import (
    FilesAction,
    FilesCallback,
    TaskAction,
    TaskCallback
)
from src.db.utils import save_parasite_message
from src.messages import TASK_CONFIRMATION_MESSAGE
from src.states import TaskStates

router = Router()


@router.callback_query(
  TaskStates.Files,
  FilesCallback.filter(F.action == FilesAction.proceed)
)
async def process_confirm_task(
    callback_query: types.CallbackQuery,
    callback_data: FilesCallback,
    state: FSMContext,
    db_session: AsyncSession
):
  """
  Обрабатывает запрос на подтверждение отправки текущей заявки.

  Вызывается для подтверждения пользователем создания новой заявки.
  Предоставляет пользователю выбор подтвердить или отменить создание
  новой заявки.
  """
  data = await state.get_data()

  if data['task_timestamp'] == callback_data.task_timestamp:
    text = TASK_CONFIRMATION_MESSAGE
    files = data.get('files', {})
    if files:
      text += '\n\n'
      text += '\n'.join(f'📎 {filename}' for filename in files.keys())

    builder = InlineKeyboardBuilder()
    builder.button(
      text='✅ Подтвердить',
      callback_data=TaskCallback(
        action=TaskAction.send,
        task_timestamp=data['task_timestamp']
      )
    )
    builder.button(
      text='❌ Отменить',
      callback_data=TaskCallback(
        action=TaskAction.cancel,
        task_timestamp=data['task_timestamp']
      )
    )
    builder.adjust(1)
    await state.set_state(TaskStates.TaskConfirmation)
    await callback_query.message.edit_text(
      text=text,
      reply_markup=builder.as_markup()
    )
    await save_parasite_message(db_session, callback_query.message.chat.id, callback_query.message.message_id)
