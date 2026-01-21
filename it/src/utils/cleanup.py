import logging
import os
from pathlib import Path
from typing import Set

from aiogram.fsm.context import FSMContext


def remove_files(files: Set[Path]) -> None:
    """
    Удаляет указанные файлы.
    """
    for file in files:
        try:
            os.remove(file)
        except Exception as e:
            logging.error(str(e))


async def cleanup(state: FSMContext) -> None:
    """Очищает состояние пользователя и временные файлы."""
    data = await state.get_data()
    files = set()
    for field in data.get('form', []):
        if field['type'] == 'file' and field.get('value'):
            files.add(field['value'])
    files |= set(data.get('files', {}).values())
    remove_files(files)
    await state.clear()


def remove_user_voice_messages(user_id: int) -> None:
    """
    Удаляет все голосовые сообщения пользователя по его user_id
    :param user_id: Идентификатор пользователя
    """
    base_path = f'user_voice_messages/{user_id}'

    if os.path.exists(base_path):
        try:
            for filename in os.listdir(base_path):
                file_path = os.path.join(base_path, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            logging.debug(f'Голосовые сообщения пользователя %s удалены.', user_id)
        except Exception as e:
            logging.error(f'Ошибка при удалении голосовых сообщений пользователя %s: %s', user_id, e)
    else:
        logging.debug(f'Голосовые сообщения пользователя %s не найдены!', user_id)
