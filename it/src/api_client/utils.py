import mimetypes
from pathlib import Path


def clean_none_values(d: dict) -> dict:
    """
    Удаляет None значения.

    :param d: Исходнные данные
    :type d: dict

    :return: Форматированные данные
    :rtype: dict
    """
    return {key: value for key, value in d.items() if value is not None}


def get_content_type(file: Path) -> str:
    """
    Получает тип файла.

    :param file: Файл
    :type file: Path

    :return: Тип файла или 'application/octet-stream'
    :rtype: str
    """
    mime, _ = mimetypes.guess_type(file)
    return mime or 'application/octet-stream'
