import datetime
import logging
from pathlib import Path

from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.api_client import APIClient, APIPermissionError
from src.callbacks import TaskAction, TaskCallback
from src.db.models import User
from src.handlers.assistant.utils import delete_parasite_messages
from src.keyboards import get_main_inline_keyboard
from src.messages import (
    CREATE_ANOTHER_TASK_MESSAGE,
    TASK_SUCCESS_MESSAGE,
)
from src.states import TaskStates
from src.utils import api, active_user, cleanup

router = Router()


@router.callback_query(
  TaskStates.TaskConfirmation,
  TaskCallback.filter(F.action == TaskAction.send)
)
@active_user
async def process_send_task(
    callback_query: types.CallbackQuery,
    callback_data: TaskCallback,
    state: FSMContext,
    api_client: APIClient,
    user: User,
    db_session: AsyncSession,
    *args, **kwargs
):
  """
  Обрабатывает запрос на отправку текущей заявки.

  Обрабатывает данные заявки и отправляет их на сервер для создания новой
  заявки. В случае успешного создания заявки, уведомляет пользователя о
  созданной заявке.
  """
  data = await state.get_data()
  if data['task_timestamp'] == callback_data.task_timestamp:
    await state.set_state()

    task = data['task']
    for field in data['form']:
      if not field.get('value'):
        continue
      key, field_type = field['key'], field['type']
      if field_type in {'text', 'number'}:
        task[key] = field['value']
      elif field_type == 'file':
        task[key] = await api.upload_file(api_client, Path(field['value']))
      elif field_type == 'date':
        task[key] = datetime.datetime.fromisoformat(field['value']).strftime('%d.%m.%Y')
      elif field_type in {'checkbox', 'list'}:
        task[key] = str(field['value'])
      elif field_type == 'choice':
        task[key] = ','.join(map(str, field['value']))
      else:
        raise RuntimeError(
          'process_send_task: неожиданный тип поля: '
          f'{field["type"]}.'
        )
    await state.update_data(data)

    inventive_user = await api.get_user_by_id(
      api_client,
      user.inventive_id
    )

    file_tokens = [
      await api.upload_file(api_client, Path(file_path))
      for file_path in data.get('files', {}).values()
    ]
    file_tokens = ','.join(file_tokens)

    try:
      task = await api.create_task(
        api_client,
        **task,
        UserEmail=inventive_user['Email'],
        FileTokens=file_tokens or None
      )
      answer_text = TASK_SUCCESS_MESSAGE.format(task['Id'])
      await callback_query.message.answer(answer_text)
      logging.info('Пользователь %s создал заявку %s', user.id, task['Id'])

    except APIPermissionError as e:
      logging.info("Пользователь %s попытался создать заявку на которую у него нет прав!", user.id)
      await  callback_query.answer(messages.PERMISSION_ERROR_TASK_CREATE_MESSAGE)

    await callback_query.message.answer(text=CREATE_ANOTHER_TASK_MESSAGE, reply_markup=await get_main_inline_keyboard())

    await cleanup(state)
    await delete_parasite_messages(callback_query.bot, db_session, callback_query.message.chat.id)
