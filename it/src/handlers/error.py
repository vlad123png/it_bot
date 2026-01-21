import asyncio
import datetime as dt
import logging
import traceback
from dataclasses import dataclass
from pprint import pformat
from typing import Any

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, User

from src import messages
from src.config.settings import settings
from src.container import app_container
from src.exceptions import NewTaskError, KnowledgeBaseNotFoundError, LoadPromptError
from src.messages import GENERAL_ERROR_MESSAGE
from src.utils import cleanup, create_support_task

router = Router()


@dataclass(slots=True)
class ErrorContext:
    """Сводная структура с полезной информацией о падении."""
    # --- время и идентификаторы ---
    happened_at: str
    bot_id: int
    update_id: int | None

    # --- пользователь ---
    telegram_id: int
    first_name: str | None
    last_name: str | None
    username: str | None
    language_code: str | None
    is_premium: bool | None

    # --- место ошибки ---
    exception_type: str
    exception_text: str
    traceback: str

    # --- контекст FSM ---
    state: str | None
    data: dict[str, Any]

    # --- update raw ---
    update_raw: dict[str, Any]

    # --- доп. поля, которые можно «по желанию» включать ---
    chat_type: str | None
    chat_id: int | None
    message_text: str | None
    message_id: int | None
    callback_data: str | None


def _extract_user(event: ErrorEvent) -> User | None:
    upd = event.update
    for attr in ("message", "callback_query", "inline_query", "chosen_inline_result"):
        obj = getattr(upd, attr, None)
        if obj and obj.from_user:
            return obj.from_user
    return None


async def _build_error_context(event: ErrorEvent, state: FSMContext, bot: Bot) -> ErrorContext:
    user = _extract_user(event)
    if not user:
        raise RuntimeError("Не удалось извлечь пользователя из update.")

    upd = event.update  # <- единая переменная

    # FSM
    current_state = None
    state_data = {}
    try:
        current_state = await state.get_state()
        state_data = await state.get_data()
    except Exception:
        pass

    # Chat / message / callback
    chat_type = chat_id = message_text = message_id = callback_data = None
    if upd.message:
        chat_type = upd.message.chat.type
        chat_id = upd.message.chat.id
        message_id = upd.message.message_id
        message_text = upd.message.text or upd.message.caption
    elif upd.callback_query and upd.callback_query.message:
        chat_type = upd.callback_query.message.chat.type
        chat_id = upd.callback_query.message.chat.id
        message_id = upd.callback_query.message.message_id
        callback_data = upd.callback_query.data

    return ErrorContext(
        happened_at=dt.datetime.now(dt.UTC).isoformat(timespec='seconds'),
        bot_id=bot.id,
        update_id=upd.update_id,
        telegram_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        language_code=user.language_code,
        is_premium=getattr(user, 'is_premium', None),
        exception_type=type(event.exception).__name__,
        exception_text=str(event.exception),
        traceback=''.join(traceback.format_exception(
            type(event.exception), event.exception, event.exception.__traceback__
        )),
        state=current_state,
        data=state_data,
        update_raw=upd.model_dump(mode='json'),
        chat_type=chat_type,
        chat_id=chat_id,
        message_text=message_text,
        message_id=message_id,
        callback_data=callback_data,
    )


def format_for_log(ctx: ErrorContext) -> str:
    """Красивый читаемый текст для лога / email."""
    return (
        f"<b>🚨 Необработанное исключение</b>\n"
        f"<b>Время</b>: {ctx.happened_at} UTC\n"
        f"<b>Бот</b>: {ctx.bot_id}\n"
        f"<b>Пользователь</b>: "
        f"<a href='tg://user?id={ctx.telegram_id}'>"
        f"{ctx.first_name or ''} {ctx.last_name or ''} (@{ctx.username or '—'})</a>\n"
        f"<b>ID пользователя</b>: <code>{ctx.telegram_id}</code>\n"
        f"<b>Язык</b>: {ctx.language_code or '—'}, Premium: {ctx.is_premium}\n"
        f"<b>Чат</b>: {ctx.chat_type}:{ctx.chat_id}\n"
        f"<b>Сообщение</b>: <code>{ctx.message_text or '—'}</code>\n"
        f"<b>State</b>: <code>{ctx.state}</code>\n"
        f"<b>Data</b>: <pre>{pformat(ctx.data, width=100)}</pre>\n"
        f"<b>Тип исключения</b>: {ctx.exception_type}\n"
        f"<b>Текст исключения</b>: <code>{ctx.exception_text}</code>\n\n"
        f"<b>Полный traceback</b>:\n<pre>{ctx.traceback}</pre>"
    )


def format_short_for_user(ctx: ErrorContext) -> str:
    """Короткое сообщение, которое показываем пользователю."""
    return getattr(ctx, 'error_message', GENERAL_ERROR_MESSAGE)


@router.error()
async def process_error(event: ErrorEvent, state: FSMContext, bot: Bot):
    """
    Централизованный обработчик ошибок.
    1. Собирает контекст.
    2. Пишет в лог.
    3. Отправляет пользователю короткое сообщение.
    4. Отправляет детали в указанные каналы (email / трекер / Telegram-лог).
    """
    try:
        ctx = await _build_error_context(event, state, bot)
    except RuntimeError as outer:
        logging.critical('Не удалось извлечь пользователя из update: %s', outer)
        return

    # 1. Логируем
    logging.critical('%s', format_for_log(ctx), extra={'markup': True})

    # 2. Чистим FSM
    await cleanup(state)

    # 3. Пользователю — короткое сообщение
    try:
        user_msg = await bot.send_message(
            chat_id=ctx.telegram_id,
            text=format_short_for_user(ctx)
        )
        await asyncio.sleep(settings.SLEEP_TIME)
        await user_msg.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass  # бот заблокирован или сообщение удалено

    # 4. Отправляем в «технические» каналы, если ошибка не ожидаемая
    if isinstance(event.exception, (NewTaskError, KnowledgeBaseNotFoundError, LoadPromptError)):
        return

    # 4a. Email
    try:
        await app_container.smtp_client.send_html_email(
            settings.ERROR_EMAIL,
            messages.ERROR_SUBJECT,
            format_for_log(ctx),
            settings.SENDER_EMAIL,
        )
    except Exception as mail_exc:
        logging.error('Не удалось отправить email: %s', mail_exc)

    # 4b. Telegram-канал (если задан CHAT_LOG)
    # if settings.LOG_CHAT_ID:
    #     try:
    #         await bot.send_message(
    #             chat_id=settings.LOG_CHAT_ID,
    #             text=format_for_log(ctx),
    #             parse_mode='HTML',
    #             disable_web_page_preview=True,
    #         )
    #     except Exception as tg_exc:
    #         logging.error('Не удалось отправить лог в Telegram: %s', tg_exc)

    # 4c. Внешний трекер
    if not settings.DEBUG:
        try:
            await create_support_task(
                app_container.api_client,
                title=f'Крит. ошибка: {ctx.exception_type}',
                content=format_for_log(ctx),
            )
        except Exception as api_exc:
            logging.error('Не удалось создать задачу в трекере: %s', api_exc)
