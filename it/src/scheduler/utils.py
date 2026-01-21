import logging

from src.container import app_container


async def remove_jobs_by_id_pattern(id_pattern: str):
    jobs = app_container.scheduler.get_jobs()
    for job in jobs:
        if job.id.startswith(id_pattern):
            app_container.scheduler.remove_job(job.id)

    logging.info(f'Удалены задачи с id: %s', id_pattern)


async def remove_broadcast_message_jobs(broadcast_message_id: int):
    await remove_jobs_by_id_pattern(f'broadcast_message_{broadcast_message_id}')


async def remove_broadcast_survey_jobs(survey_id: int):
    await remove_jobs_by_id_pattern(f'survey_{survey_id}')
