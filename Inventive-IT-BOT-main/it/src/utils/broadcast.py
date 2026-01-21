import asyncio
import datetime
import logging

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.config.settings import settings
from src.container import app_container
from src.db.broadcast_utils import get_broadcast_message
from src.db.db_connection import get_async_session
from src.db.models import User
from src.db.survey_utils import get_survey_results
from src.db.users import get_user_telegram_ids_by_timezones, get_non_voted_user_ids_by_timezone
from src.db.utils import (
    update_broadcast_message,
    get_unique_timezones
)
from src.keyboards.survey import get_choices_inline_keyboard
from src.utils import split_message

logger = logging.getLogger('user_activity')


async def send_messages_to_users_by_timezones(
        timezones: list[int],
        broadcast_message_id: int,
        page_size: int = 500,
        is_last_task: bool = False
):
    """
    Отправка сообщений пользователям из списка timezone,
    учитывая рабочее время.

    :param timezones: Временные зоны пользователей которым будут разосланы сообщения
    :param broadcast_message_id: Идентификатор записи рассылаемого сообщения
    :param page_size: Количество пользователей получаемых из БД за 1 запрос
    :param is_last_task: Флаг завершения рассылки сообщений всем пользователям
    """
    total_successful_sends = 0
    total_failed_sends = 0
    logging.info('Начало рассылки %s для timezone: %s', broadcast_message_id, timezones)
    async with get_async_session() as db_session:
        # Получение сообщения для рассылки
        broadcast_message = await get_broadcast_message(db_session, broadcast_message_id)
        if broadcast_message is None:
            logging.warning(f'Сообщения для рассылки %s не найдено.', broadcast_message_id)
            return
        broadcast_messages = split_message(broadcast_message.message)

        # Рассылка сообщения
        for timezone in timezones:
            successful_sends = 0
            failed_sends = 0
            page_number = 1
            logging.info('Начало обработки timezone: %s', timezone)

            while users := await get_user_telegram_ids_by_timezones(db_session, timezone, page_size, page_number):
                for user_telegram_id in users:
                    try:
                        for message in broadcast_messages:
                            await app_container.bot.send_message(
                                user_telegram_id, message, parse_mode=ParseMode.HTML)
                            await asyncio.sleep(0.1)  # Задержка из-за Telegram API
                        successful_sends += 1
                    except TelegramAPIError as e:
                        logging.error('Ошибка отправки сообщения пользователю %s: %s', user_telegram_id, e)
                        failed_sends += 1

                page_number += 1
            total_successful_sends += successful_sends
            total_failed_sends += failed_sends

        # Обновление статуса прогресса рассылки
        await update_broadcast_message(
            db_session,
            broadcast_message_id,
            total_successful_sends,
            total_failed_sends,
            finished=is_last_task
        )
    logging.info(
        'Рассылка для timezones %s завершена. Успешных отправок: %d, неудачных: %d',
        timezones, total_successful_sends, total_failed_sends
    )


async def broadcast_survey(
        timezones: list[int],
        broadcast_messages: list[str],
        survey_id: int,
        inline_keyboard: InlineKeyboardMarkup = None,
        page_size: int = 500,
        filter_voted_users: bool = False
):
    """
    Рассылка опроса пользователям.
    :param timezones: Таймозоны для пользователей которых будет осуществляться рассылка
    :param broadcast_messages: Сообщения для рассылки
    :param survey_id: Идентификатор опроса
    :param inline_keyboard: Inline клавиатура прикрепляемая к опросу.
    :param page_size: Количество пользователей получаемых из базы данных за раз.
    :param filter_voted_users: Учитывать ли проголосовавших пользователей (True — исключить проголосовавших).
    """
    total_successful_sends = 0
    total_failed_sends = 0
    logging.info('Начало рассылки %s для timezone: %s', survey_id, timezones)
    async with get_async_session() as db_session:
        for timezone in timezones:
            successful_sends = 0
            failed_sends = 0
            page_number = 1
            logging.info('Начало обработки timezone: %s', timezone)
            while True:
                if filter_voted_users:
                    users = await get_non_voted_user_ids_by_timezone(
                        db_session, survey_id, timezone, page_size, page_number)
                else:
                    users = await get_user_telegram_ids_by_timezones(db_session, timezone, page_size, page_number)

                if not users:
                    break

                for user_telegram_id in users:
                    try:
                        for message in broadcast_messages:
                            await app_container.bot.send_message(
                                user_telegram_id,
                                message,
                                reply_markup=inline_keyboard,
                                parse_mode=ParseMode.HTML)
                            await asyncio.sleep(0.1)  # Задержка из-за Telegram API
                        successful_sends += 1
                    except TelegramAPIError as e:
                        logging.error('Ошибка отправки сообщения пользователю %s: %s', user_telegram_id, e)
                        failed_sends += 1

                page_number += 1
            total_successful_sends += successful_sends
            total_failed_sends += failed_sends


async def calculate_local_run_time(timezone: int, delivery_time: datetime.datetime) -> datetime.datetime:
    """
    Рассчитывает время отправки в UTC для пользователей в указанной timezone.
    Если локальное время вне рабочего диапазона, переносит отправку на 8:00 следующего дня.

    :param timezone: Временная зона группы пользователей
    :param delivery_time: Время в которое сообщение должно быть доставлено (aware datetime)
    """
    local_run_time = delivery_time - datetime.timedelta(hours=timezone)

    # Случай, если рассылка производится немедленно.
    # Проверка, если локальное время за пределами рабочего времени
    if datetime.datetime.now(datetime.UTC).date() == delivery_time.date():
        local_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=timezone)
        if local_time.hour >= settings.WORK_HOURS_END or local_time.hour < settings.WORK_HOURS_START:
            # Перенос на следующее утро
            if local_time.hour < settings.WORK_HOURS_START:
                # День уже следующий
                next_day = local_time.date()
            else:
                next_day = local_time.date() + datetime.timedelta(days=1)

            local_run_time = (datetime.datetime.combine(next_day, datetime.time(hour=settings.WORK_HOURS_START))
                              .replace(tzinfo=datetime.timezone.utc))
            local_run_time = local_run_time - datetime.timedelta(hours=timezone)

    return local_run_time


async def get_runtimes(
        timezones: list[int],
        delivery_time: datetime.datetime,
) -> dict[datetime.datetime, list[int]]:
    """
    Определение времени отправки сообщений для часовых поясов.
    Формирует словарь ключом которого является время отправки,
    а значением timezone для которых нужно отправлять сообщение.
    :param timezones: Список временных зон
    :param delivery_time: Время доставки сообщения
    :return: Словарь с ключём врумя отправки и значением списка с таймзонами
    """
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)

    timezone_run_items = {}
    for timezone in timezones:
        local_runtime_in_utc = await calculate_local_run_time(timezone, delivery_time)
        # Задачи, которые запланированы на прошедшее время - группируются и добавляются на выполнение через 10 секунд.
        if local_runtime_in_utc < current_time_utc:
            local_runtime_in_utc = current_time_utc + datetime.timedelta(seconds=10)

        if local_runtime_in_utc not in timezone_run_items:
            timezone_run_items[local_runtime_in_utc] = []
        timezone_run_items[local_runtime_in_utc].append(timezone)
    return timezone_run_items


async def create_broadcast_tasks_by_timezone(
        db_session: AsyncSession,
        broadcast_message_id: int,
        delivery_time: datetime.datetime,
):
    """
    Планирует задачи для рассылки сообщения пользователям согласно их часовым поясам и рабочему времени.
    :param db_session: Асинхронная сессия sqlAlchemy с БД
    :param broadcast_message_id: Индентификатор сообщения для рассылки
    :param delivery_time: Время и дата доставки сообщения опльзователям
    """
    try:
        timezones = await get_unique_timezones(db_session)
        timezone_run_items = await get_runtimes(timezones, delivery_time)

        for run_time, timezone_list in timezone_run_items.items():
            is_last_task = (run_time == max(timezone_run_items.keys()))
            app_container.scheduler.add_job(
                send_messages_to_users_by_timezones,
                'date',
                run_date=run_time,
                args=[timezone_list, broadcast_message_id, 100, is_last_task],
                id=f'broadcast_message_{broadcast_message_id}_at_{run_time}',
                replace_existing=True
            )

        logging.info('Задачи для рассылки созданы. Broadcast ID: %s', broadcast_message_id)

    except Exception as e:
        logging.error('Ошибка создания задач для рассылки: %s', e)


async def send_survey_result_to_user(user_telegram_id: int, survey_id: int, user_id: int):
    """
    Оправляет отчёт опроса.
    :param user_telegram_id: Идентификатор пользователя в telegram
    :param survey_id: Идентификатор опроса
    :param user_id: Идентификатор пользоватея (автора
    """
    async with get_async_session() as db_session:
        survey = await get_survey_results(db_session, survey_id, user_id)
        if not survey:
            logging.info(f'Результат опроса %s не был отправлен, так ка кне был найден.', survey_id)
            return

        general_count_number = sum(choice.choice_count for choice in survey.choices)
        try:
            if general_count_number < 1:
                await app_container.bot.send_message(
                    chat_id=user_telegram_id, text=messages.SURVEY_REPORT_NOT_READY.format(survey.id, survey.question))
            else:
                await app_container.bot.send_message(
                    chat_id=user_telegram_id,
                    text=messages.RESULT_SURVEY_MESSAGE.format(
                        survey.id,
                        survey.question,
                        '\n'.join(
                            f'<b>{(choice.choice_count / general_count_number * 100):.2f}%  '
                            f'({choice.choice_count} голосов)</b>: {choice.text}'
                            for choice in survey.choices)
                    ))
        except TelegramBadRequest:
            logging.error(f'Не удалось отправить сообщение с результатом опроса %s пользователю %s',
                          survey_id, survey.user_id)
        logger.info(f'Отправлено сообщение с рузьтатом опроса %s пользователю %s', survey.id, survey.user_id)


async def create_task_for_broadcast_survey_by_timezones(
        db_session: AsyncSession,
        survey_id: int,
        message: str,
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime,
        author: User,
        choices: list[[str, int]],
):
    """
    Создание задач для рассылки опроса по временным зонам.
    :param db_session: Асинхронная сессия с БД
    :param survey_id: Идентификатор опроса
    :param message: Сообщение (тема, вопрос).
    :param start_datetime: Время и дата начала рассылки
    :param end_datetime: Вемя завершения опроса
    :param author: Автор (нужна для отправки уведомления об окончании)
    :param choices: Варианты выбора
    """
    try:
        # Создание задач для рассылки опроса
        delivery_time = start_datetime.replace(tzinfo=datetime.timezone.utc)
        timezones = await get_unique_timezones(db_session)
        timezone_run_items = await get_runtimes(timezones, delivery_time)
        inline_keyboard = get_choices_inline_keyboard(choices, [], survey_id)
        for run_time, timezone_list in timezone_run_items.items():
            app_container.scheduler.add_job(
                broadcast_survey,
                'date',
                run_date=run_time,
                args=[timezone_list, [message], survey_id, inline_keyboard],
                id=f'survey_{survey_id}_broadcast__at_{run_time}',
                replace_existing=True
            )
        logging.info(f'Задачи для рассылки опроса %s созданы пользователем %s.', survey_id, author.id)

        # Создание задач по напоминанию о прохождении опроса.
        # Напоминание за сутки, если опрос расчитан на 3 и более дня
        reminder_delivery_time = (end_datetime - datetime.timedelta(days=1))
        if reminder_delivery_time.date() - datetime.timedelta(days=1) > start_datetime.date():
            reminder_time_run_items = await get_runtimes(timezones, reminder_delivery_time)
            reminder_message = messages.REMAINDER_SURVEY_MESSAGE.format('1 день') + message
            for run_time, timezone_list in reminder_time_run_items.items():
                app_container.scheduler.add_job(
                    broadcast_survey,
                    'date',
                    run_date=run_time,
                    args=[timezone_list, [reminder_message], survey_id, inline_keyboard, 500, True],
                    id=f'survey_{survey_id}_broadcast_remainder__at_{run_time}',
                    replace_existing=True
                )
            logging.info(f'Задачи для рассылки напоминаний об опросе %s за день созданы пользователем %s.',
                         survey_id, author.id)

        # Напоминания за неделю, если опрос расчитан на 9 и более дней
        reminder_delivery_time = (end_datetime - datetime.timedelta(days=7))
        if reminder_delivery_time.date() - datetime.timedelta(days=1) > start_datetime.date():
            reminder_time_run_items = await get_runtimes(timezones, reminder_delivery_time)
            reminder_message = messages.REMAINDER_SURVEY_MESSAGE.format('7 дней') + message
            for run_time, timezone_list in reminder_time_run_items.items():
                app_container.scheduler.add_job(
                    broadcast_survey,
                    'date',
                    run_date=run_time,
                    args=[timezone_list, [reminder_message], survey_id, inline_keyboard, 500, True],
                    id=f'survey_{survey_id}_broadcast_remainder__at_{run_time}',
                    replace_existing=True
                )
            logging.info(f'Задачи для рассылки напоминаний об опросе %s за 7 деней созданы пользователем %s.',
                         survey_id, author.id)

        # Создание задачи для отправки результата опроса по окончанию
        send_result_datetime = await get_runtimes([author.timezone], end_datetime)
        send_result_datetime = next(iter(send_result_datetime))
        app_container.scheduler.add_job(
            send_survey_result_to_user,
            'date',
            run_date=send_result_datetime,
            args=[author.telegram_id, survey_id, author.id],
            id=f'survey_{survey_id}_send_result_{author.id}',
            replace_existing=True
        )
        logging.info(f'Задача для отправки результата опроса %s пользователю %s создана.', survey_id, author.id)
        logging.info(f'Завершено создание всех задач для рассылки опроса %s.', survey_id)
    except Exception as e:
        logging.error('Ошибка создания задач для рассылки опроса: %s', e)
