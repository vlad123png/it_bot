import logging
import os
from datetime import datetime
from functools import wraps
from pathlib import Path

from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from cachetools import TTLCache

from src.config.settings import settings
from src.messages import (
    FILE_SIZE_LIMIT_EXCEEDED_MESSAGE,
    TOTAL_UPLOAD_SIZE_LIMIT_EXCEEDED_MESSAGE
)

cache = TTLCache(maxsize=2, ttl=settings.USER_AGREEMENT_CACHE_TIME)


async def save_file(bot: Bot, user_id: int, file_id: str, file_name: str):
  """
  Сохраняет файл в указанную директорию
  """

  dir = f'{settings.TEMP_FILES_DIR}/{user_id}'
  os.makedirs(dir, exist_ok=True)

  file = await bot.get_file(file_id)
  destination = Path(f'{dir}/{file_name}')
  await bot.download_file(file.file_path, destination)
  return destination


async def download_and_save_file(message: types.Message, bot: Bot) -> Path:
  """
  Загружает файл из сообщения и сохраняет в указанную директорию.

  :param message: Экземпляр сообщения
  :type message: Message
  :param bot: Экземпляр бота
  :type bot: Bot

  :return: Файл
  :rtype: Path
  """
  if message.document:
    file_id = message.document.file_id
    file_name = message.document.file_name
  elif message.photo:
    file_id = message.photo[-1].file_id
    file_name = f'{int(datetime.utcnow().timestamp())}.jpg'
  elif message.video:
    file_id = message.video.file_id
    file_name = f'{int(datetime.utcnow().timestamp())}.mp4'
  else:
    raise RuntimeError('download_and_save_file: неожиданный тип файла.')

  return await save_file(bot, message.from_user.id, file_id, file_name)


def check_file_size(handler):
  """Декоратор, проверяющий размер загружаемого файла."""

  @wraps(handler)
  async def wrapper(message: types.Message, *args, **kwargs):
    file_sizes = []
    messages = kwargs.get('media_group', [message])

    for message in messages:
      if message.document:
        file_sizes.append(message.document.file_size)
      elif message.photo:
        file_sizes.append(message.photo[-1].file_size)
      elif message.video:
        file_sizes.append(message.video.file_size)
      else:
        raise RuntimeError('check_file_size: неверный тип файла.')

    for file_size in file_sizes:
      if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(
          FILE_SIZE_LIMIT_EXCEEDED_MESSAGE.format(settings.MAX_FILE_SIZE_MB)
        )
        return

    return await handler(message, *args, **kwargs)

  return wrapper


def check_uploaded_size(handler):
  """Декоратор, проверяющий суммарный размер загруженных файлов."""

  @wraps(handler)
  async def wrapper(
      callback_query: types.CallbackQuery,
      state: FSMContext,
      *args, **kwargs
  ):
    data = await state.get_data()
    files = data.get('files', {})
    total_size = sum(os.path.getsize(file) for file in files.values())
    if total_size > settings.MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024:
      await callback_query.message.answer(
        TOTAL_UPLOAD_SIZE_LIMIT_EXCEEDED_MESSAGE
      )
    else:
      return await handler(callback_query, state, *args, **kwargs)

  return wrapper


async def send_file_with_cache(message: types.Message, filename: str) -> None:
  """
  Отправляет файл с использованием кэширования.
  :param message: Aiogram объект сообщения
  :param filename: Имя файла
  """
  try:
    if document_id := cache.get(filename):
      await message.bot.send_document(chat_id=message.chat.id, document=document_id)
      logging.debug('Файл %s отправлен телеграм пользователю %s. Файл получен из кэша %s.',
                    filename, message.from_user.id, document_id)
    else:
      file = types.FSInputFile(f'./static/{filename}')
      send_message = await message.bot.send_document(chat_id=message.chat.id, document=file)
      cache[filename] = send_message.document.file_id
      logging.debug('Файл %s отправлен телеграм пользователю %s. ID файла кэшировано: %s',
                    filename, message.chat.id, send_message.document.file_id)
  except TelegramBadRequest as e:
    logging.warning('Не удалось отправить файл %s пользователю (chat id: %s): %s', filename, message.chat.id, e)
