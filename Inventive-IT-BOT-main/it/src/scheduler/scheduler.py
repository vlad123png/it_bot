import logging

from src.container import app_container
from src.scheduler.period_tasks import add_periodic_tasks


async def start_scheduler():
    """ Запускает планировщик задач """
    await add_periodic_tasks()
    app_container.scheduler.start()
    logging.info('Планировщик задач запущен.')
