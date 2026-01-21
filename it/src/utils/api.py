import logging
from pathlib import Path
from typing import List, Optional, Tuple

from src.api_client import APIClient, ClientError
from src.api_client import APIPermissionError
from src.exceptions import NewTaskError, UploadFileError, CreateTaskError
from src.utils.users import is_ared


async def get_user_by_id(api_client: APIClient, service_id: int) -> Optional[dict]:
  """
  Получает пользователя по его идентификатору.

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient
  :param service_id: Идентификатор пользователя в Inventive
  :type service_id: int

  :return: Пользователь или None
  :rtype: Optional[dict]
  """
  try:
    async with api_client:
      return await api_client.get_user(service_id)
  except ClientError as e:
    logging.warning(str(e))


async def get_user_by_email(
    api_client: APIClient,
    email: str
) -> Optional[dict]:
  """
  Получает пользователя по адресу электронной почты.

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient
  :param email: E-mail пользователя в Inventive

  :return: Пользователь или None
  :rtype: Optional[dict]
  """
  async with api_client:
    users = await api_client.get_users(email=email)
    return users[0] if users else None


async def get_services(api_client: APIClient, user_email: str | None = None) -> List[dict]:
  """
  Получает список сервисов.

  :param api_client: Экземпляр API клиента
  :type user_email: Email пользователя из invtraservice
  :type api_client: APIClient

  :return: Список сервисов
  :rtype: List[dict]
  """
  async with api_client:
    if user_email is None:
      return await api_client.get_services('all')
    elif is_ared(user_email):
      ared =  await api_client.get_services('ared')
      return ared
    else:
      return await api_client.get_services('main')




async def get_assets(api_client: APIClient, service_id: int) -> List[dict]:
  """
  Получает список активов для указанного сервиса.

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient
  :param service_id: Идентификатор сервиса в Inventive
  :type service_id: int

  :return: Список активов
  :rtype: List[dict]
  """
  async with api_client:
    return await api_client.get_assets(service_id)


async def get_categories(api_client: APIClient, service_id: int) -> List[dict]:
  """
  Получает список категорий для указанного сервиса.

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient
  :param service_id: Идентификатор сервиса в Inventive
  :type service_id: int

  :return: Список категорий
  :rtype: List[dict]
  """
  async with api_client:
    return await api_client.get_categories(service_id)


async def get_task_types(api_client: APIClient, service_id: int) -> List[dict]:
  """
  Получает список типов заявок для указанного сервиса.

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient
  :param service_id: Идентификатор сервиса в Inventive
  :type service_id: int

  :return: Список типов заявок
  :rtype: List[dict]
  """
  async with api_client:
    return await api_client.get_task_types(service_id)


async def get_new_task(
    api_client: APIClient,
    service_id: int,
    task_type_id: int
) -> Tuple[dict, dict, List[dict]]:
  """
  Получает шаблон новой заявки, полномочия пользователя и список
  дополнительных полей заявки для указанного сервиса и типа заявки.

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient
  :param service_id: Идентификатор сервиса в Inventive
  :type service_id: int
  :param task_type_id: Идентификатор типа заявки в Inventive
  :type task_type_id: int

  :return: Шаблон новой заявки, полномочия пользователя и список
          дополнительных полей заявки.
  :rtype: Tuple[dict, dict, List[dict]]

  :raises NewTaskError: Ошибка при получении шаблона новой заявки
  """
  try:
    async with api_client:
      return await api_client.get_new_task(service_id, task_type_id)
  except ClientError as e:
    raise NewTaskError(f'NewTaskError: {str(e)}')


async def upload_file(api_client: APIClient, file: Path) -> str:
  """
  Загружает файл.

  :param file: Файл
  :type file: Path

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient

  :return: Токен загруженного файла
  :rtype: str

  :raises UploadFilesError: Ошибка при загрузке файлов
  """
  try:
    async with api_client:
      return await api_client.upload_file(file)
  except ClientError as e:
    raise UploadFileError(f'UploadFilesError: {str(e)}')


async def create_task(api_client: APIClient, **kwargs) -> dict:
  """
  Создает новую заявку.

  :param kwargs: Параметры заявки
  :type kwargs: dict

  :param api_client: Экземпляр API клиента
  :type api_client: APIClient

  :return: Новая заявка
  :rtype: dict

  :raises CreateTaskError: Ошибка при создании новой заявки
  """
  try:
    async with api_client:
      return await api_client.create_task(**kwargs)
  except ClientError as e:
    raise CreateTaskError(f'CreateTaskError: {str(e)}')


async def check_user_can_create_task(
    api_client: APIClient,
    service_id: int,
    intraservice_user_id: int,
) -> bool:
  """
  Проверяет права пользователя на создание заявки
  :param api_client: Экземпляр API клиента
  :param service_id: Идентификатор сервиса, в котором требуется проверить права.
  :param intraservice_user_id: Inventive id пользователя, для которого выполняется проверка.
  """
  try:
    async with api_client:
      user = await get_user_by_id(api_client=api_client, service_id=intraservice_user_id)
      return await api_client.check_user_can_create_task(service_id=service_id, user_name=user.get('Name'))
  except ClientError as e:
    raise CreateTaskError(f'CheckTaskCreatePermissionError: {str(e)}')


async def create_support_task(
    api_client: APIClient,
    title: str,
    content: str,
    **kwargs
) -> dict:
  """
  Создает новую заявку в сервисе поддержки бота Intraservice.

  :param api_client: Модуль работы с Intraservice
  :param title: Название заявки
  :param content: Содержимое заявки
  :param kwargs: Параметры заявки
  :return: Новая заявка

  Приоритеты (Priority):
  11 - Низкий
  9 - средний
  13 - менее высокий
  10 - высокий
  12 - критичный

  Идентификатор сервиса заявки (ServiceId): 1211 - Инцидент бизнес-приложений
  Тип заявки (StatusId): 1029 - Заявки для решения обращений по вопросам поддержки в бизнес-приложениях 1С или SAP

  Статусы (StatusId):
  31 - Открыта
  95 - В процессе
  100 - В ожидании документов
  """
  try:
    async with api_client:
      task_form, *_ = await get_new_task(api_client, 1211, 1029)
      task_form.update(Name=title, Description=content, **kwargs)
      return await api_client.create_task(**task_form)
  except (ClientError, APIPermissionError) as e:
    logging.error('CreateSupportTaskError: title: %s, content: %s, error: %s', title, content, str(e))
    return {}