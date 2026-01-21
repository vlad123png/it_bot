import asyncio
from typing import Any, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, Update


class MediaGroupMiddleware(BaseMiddleware):
  """
  Мидлваре для сборки сообщений из одной медиа группы.
  Позволяет обрабатывать медиа группу как одно целое.
  """

  def __init__(self, latency: Union[int, float] = 1):
    self.latency = latency
    self.media_group_data = {}

  def collect_media_group_messages(self, message: Message):
    """
    Сбор сообщений из одной медиа группы
    """
    if message.media_group_id not in self.media_group_data:
      self.media_group_data[message.media_group_id] = {'messages': []}

    self.media_group_data[message.media_group_id]['messages'].append(message)
    return len(self.media_group_data[message.media_group_id]['messages'])

  async def __call__(self, handler, event: Update, data: Dict[str, Any]) -> Any:
    if not event.message or not event.message.media_group_id:
      return await handler(event, data)

    total_before = self.collect_media_group_messages(event.message)
    await asyncio.sleep(self.latency)
    total_after = len(self.media_group_data[event.message.media_group_id]['messages'])

    # Если пришли новые файлы во время ожидания, то ждём дальше
    if total_before != total_after:
      return

    # Сортировка файлов для правильной последовательности
    median_group_messages = self.media_group_data[event.message.media_group_id]['messages']
    median_group_messages.sort(key=lambda x: x.message_id)
    data['media_group'] = median_group_messages

    del self.media_group_data[event.message.media_group_id]
    return await handler(event, data)
