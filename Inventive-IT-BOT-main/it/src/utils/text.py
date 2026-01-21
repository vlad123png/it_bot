import asyncio
import html
import logging
import re
from functools import wraps

from aiogram import types
from aiogram.exceptions import TelegramBadRequest

from src.config.settings import settings
from src.messages import INVALID_TEXT_MESSAGE, INVALID_NUMBER_MESSAGE

CALLBACK_DATA_MAX_BYTES_LENGTH: int = 64

EMAIL_REGEX = re.compile(r'[^@]+@[^@]+\.[^@]+')


def is_email(text: str) -> bool:
    """Проверяет, является ли строка e-mail."""
    return EMAIL_REGEX.fullmatch(text)

def get_email_from_string(text: str) -> str:
    for word in text.split():
        if is_email(word):
            return word.strip()

def remove_special_chars(text: str, all: bool = False) -> str:
    """Удаляет специальные символы."""
    text = re.sub(r'\\"', '', text)
    if all:
        return re.sub(r'[^a-zA-Z0-9а-яА-Я\s]', '', text)
    return text


def remove_html(text: str) -> str:
    """Удаляет HTML-теги и лишние символы."""
    text = text.strip().replace('<br>', '')
    return re.sub(r'<.*?>.*?</.*?>', '', text)


def clean_text(text: str) -> str:
    """Удаляет специальные символы и HTML-теги."""
    return remove_special_chars(remove_html(text))


def truncate_callback_data(callback_data: str, encoding='utf-8') -> str:
    """
    Обрезает строку до максимальной длины байтов.
    """
    encoded_data = callback_data.encode(encoding)
    if len(encoded_data) > CALLBACK_DATA_MAX_BYTES_LENGTH:
        callback_data = encoded_data[:CALLBACK_DATA_MAX_BYTES_LENGTH - 3].decode(
            encoding,
            errors='ignore'
        ) + '...'
    return callback_data


def has_emojis(text: str) -> bool:
    """Проверяет, содержит ли текст эмодзи."""
    emojis = re.compile(
        '['
        u'\U0001F600-\U0001F64F'
        u'\U0001F300-\U0001F5FF'
        u'\U0001F680-\U0001F6FF'
        u'\U0001F700-\U0001F77F'
        u'\U0001F780-\U0001F7FF'
        u'\U0001F800-\U0001F8FF'
        u'\U0001F900-\U0001F9FF'
        u'\U0001FA00-\U0001FA6F'
        u'\U0001FA70-\U0001FAFF'
        u'\U00002702-\U000027B0'
        u'\U000024C2-\U0001F251'
        ']+',
        flags=re.UNICODE
    )
    return bool(emojis.search(text))


def text_only(handler):
    """Декоратор, проверяющий текстовые сообщения."""

    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.content_type != 'text' or has_emojis(message.text):
            await message.answer(INVALID_TEXT_MESSAGE)
        else:
            return await handler(message, *args, **kwargs)

    return wrapper


def digit_only(handler):
    """ Декаратор, проверяющий что текстовое сообщение является числом. """

    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.content_type == 'text' and message.text.isdigit():
            return await handler(message, *args, **kwargs)
        error_message = await message.answer(INVALID_NUMBER_MESSAGE)
        try:
            await message.delete()
            await asyncio.sleep(settings.SLEEP_TIME)
            await error_message.delete()
        except TelegramBadRequest:
            logging.warning(f'Не удалось удалить сообщение о неверном формате.')

    return wrapper


def split_message(text: str, max_length: int = settings.MAX_MESSAGE_LENGTH) -> list[str]:
    """Разбивает HTML-сообщение на части, если оно превышает лимит длины."""
    if len(text) <= max_length:
        text = fix_html(text)
        return [text]

    parts = []
    while len(text) > max_length:
        # Нахождение последнего пробела или тега для корректного разделения
        split_index = text[:max_length].rfind(' ')
        if split_index == -1:
            split_index = max_length

        part = text[:split_index].strip()
        part = fix_html(part)
        parts.append(part)

        text = text[split_index:].strip()

    text = fix_html(text)
    parts.append(text)
    return parts


def fix_html(text: str) -> str:
    """
    Исправляет незакрытые HTML-теги в тексте и экранирует спецсимволы.

    :param text: Исходная строка
    :return: Исправленная строка
    """
    open_tags = []
    tag_pattern = re.compile(r'<(/?)([a-zA-Z]+)[^>]*?>')

    # Найти все теги в тексте
    for match in tag_pattern.finditer(text):
        tag_type, tag_name = match.groups()
        if tag_type == '':
            open_tags.append(tag_name)
        elif tag_name in open_tags:
            open_tags.remove(tag_name)

    # Закрыть незакрытые теги
    for tag in reversed(open_tags):
        text += f'</{tag}>'

    return text


def strip_html_tags(text: str) -> str:
    """
    Удаляет все HTML-теги из текста, оставляя только человекочитаемый контент.

    :param text: Исходная строка с HTML-разметкой
    :return: Строка без HTML-тегов
    """
    tag_pattern = re.compile(r'<[^>]+>')
    return re.sub(tag_pattern, '', text).strip()


def extract_text_from_html(text: str) -> str:
    """
    Удаляет HTML-теги и экранирование для инлайн-клавиатур.

    :param text: Исходная строка
    :return: Очищенная строка
    """
    return html.unescape(strip_html_tags(text))
