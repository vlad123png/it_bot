import logging

from apscheduler.triggers.cron import CronTrigger

from src.container import app_container
from src.db.db_connection import get_async_session
from src.db.users import reset_counts_user_questions


async def reset_user_counts_to_ai():
    """Сбрасывает количество обращений пользователя к ИИ за сутки."""
    try:
        async with get_async_session() as db_session:
            await reset_counts_user_questions(db_session)
    except Exception as e:
        logging.error(f'Не удалось сбросить количество обращений к ИИ пользователя: %s', e)


async def add_periodic_tasks():
    """ Добавляет периодичесие задачи. """
    # Добавление задачи для сброса количества запросов пользователей к ИИ
    app_container.scheduler.add_job(
        reset_user_counts_to_ai,
        CronTrigger(hour=0, minute=1),
        id='reset_user_counts_to_ai',
        replace_existing=True,
    )
