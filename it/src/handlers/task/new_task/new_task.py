import logging
from datetime import datetime

from aiogram import types, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.api_client import APIClient
from src.callbacks import NewTaskCallback
from src.config.settings import settings
from src.db.models import User
from src.db.utils import save_parasite_message
from src.exceptions import TaskError
from src.messages import NEW_TASK_MESSAGE
from src.utils import (
    active_user,
    cleanup,
    clean_text,
    get_assets,
    get_categories,
    get_new_task,
    check_user_can_create_task
)
from .process_form import process_form

router = Router()


def get_field_type_by_id(id: int):
  """
  Получает тип поля по идентификатору.

  :param id: Идентификатор типа поля
  :return: Тип поля
  """
  field_type_mapping = {
    1: 'text',
    2: 'number',
    3: 'date',
    4: 'checkbox',
    5: 'list',
    6: 'file',
    7: 'text',
  }
  return field_type_mapping.get(id)


@router.callback_query(NewTaskCallback.filter())
@active_user
async def process_new_task(
    callback_query: types.CallbackQuery,
    callback_data: NewTaskCallback,
    state: FSMContext,
    user: User,
    db_session: AsyncSession,
    api_client: APIClient,
    *args, **kwargs
):
  """
  Обрабатывает запрос на создание новой заявки.

  Вызывается при запросе на создание новой заявки. Осуществляет подготовку
  данных для новой заявки, включая поля и их значения. Создает анкету и
  инициирует процесс её заполнения.
  """
  await cleanup(state)
  user_can_create_task = await check_user_can_create_task(api_client, callback_data.service_id, user.inventive_id)
  if not user_can_create_task:
    await callback_query.answer(text=messages.PERMISSION_ERROR_TASK_CREATE_MESSAGE, show_alert=True)
    return

  task, field_rights, extra_fields = await get_new_task(
    api_client,
    callback_data.service_id,
    callback_data.task_type_id
  )

  if settings.ASK_OPTIONAL_FIELDS:
    permissions = {1, 5}
  else:
    permissions = {5}

  form = []
  if field_rights['Name'] in permissions:
    form.append(
      {
        'key': 'Name',
        'name': 'Название',
        'type': 'text',
        'required': field_rights['Name'] == 5
      }
    )

  form.append(
    {
      'key': 'Description',
      'name': 'Описание',
      'type': 'text',
      'required': field_rights['Description'] == 5
    }
  )

  if field_rights['Assets'] in permissions:
    assets = await get_assets(api_client, callback_data.service_id)
    if not assets:
      raise TaskError(
        f'TaskError: для сервиса с id={callback_data.service_id} '
        'нет активов.'
      )
    form.append(
      {
        'key': 'AssetIds',
        'name': 'Активы',
        'type': 'choice',
        'required': field_rights['Assets'] == 5,
        'options': assets
      }
    )

  if field_rights['Categories'] in permissions:
    categories = await get_categories(api_client, callback_data.service_id)
    if not categories:
      raise TaskError(
        f'TaskError: для сервиса с id={callback_data.service_id} '
        'нет категорий.'
      )
    form.append(
      {
        'key': 'CategoryIds',
        'name': 'Категории заявки',
        'type': 'choice',
        'required': field_rights['Categories'] == 5,
        'options': categories
      }
    )

  for field in extra_fields:
    if field_rights['TaskTypeFields'][str(field['Id'])] not in permissions:
      continue

    field_type = get_field_type_by_id(field['FieldTypeId'])
    if not field_type:
      if not field.get('IsRequired', False):
        continue

      raise TaskError(
        f'TaskError: неожиданный тип поля: {field["FieldTypeId"]}.'
      )

    form.append(
      {
        'key': f'Field{field["Id"]}',
        'name': clean_text(field['Name']),
        'hint': clean_text(field['Hint']),
        'type': field_type,
        'required': field_rights['TaskTypeFields'][
                      str(field['Id'])] == 5,
        'options': field.get('TaskTypeComboBoxes', [])
      }
    )

  await state.update_data(
    {
      'task_timestamp': int(datetime.utcnow().timestamp()),
      'task': task,
      'form': form,
      'current_field_index': 0
    }
  )
  try:
    await callback_query.message.delete()
  except TelegramBadRequest:
    logging.warning(f'Не удалось удалить сообщение!')

  new_task_message = await callback_query.message.answer(
    NEW_TASK_MESSAGE.format(repr(task['ServiceName']))
  )
  await save_parasite_message(db_session, callback_query.message.chat.id, new_task_message.message_id)
  await process_form(router, callback_query.message, state, db_session)
