import csv
import logging
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from src.backend_api import BackendAPI
from src.db.statistics_utils import *


async def get_user_count_by_domain(db_session: AsyncSession) -> dict:
    """Получения количества пользователей по их доменту в Email. """
    offset = 0
    limit = 500
    user_count_by_domain = defaultdict(int)

    while True:
        users_email = await get_batch_user_emails(db_session, offset, limit)
        if not users_email:
            break

        for email in users_email:
            domain = email.split('@')[-1]
            user_count_by_domain[domain] += 1

        offset += limit

    logging.debug('Количество пользователей по доменам успешно получено.')
    return user_count_by_domain


async def generate_statistic_info_csv_file(backend_service: BackendAPI, db_session, start_date, end_date,
                                           file_path: str):
    """
    Формирует CSV-файл со статистикой за период.
    :param backend_service: Сервис для обращения к backend.
    :param db_session: Асинхронная сессия базы данных.
    :param start_date: Дата начала сбора статистики.
    :param end_date: Дата окончания сбора статистики.
    :param file_path: Путь к файлу, в который будет сохранена статистика.
    """

    # Общая статистика
    user_count = await get_user_count(db_session)
    user_count_with_positive_feedback = await get_users_with_positive_feedback_count(db_session)
    user_count_with_negative_feedback = await get_users_with_negative_feedback_count(db_session)
    user_count_by_domain = await get_user_count_by_domain(db_session)
    bot_statistic = await get_bot_statistic(db_session)

    # Статистика за период
    new_user_count_by_period = await get_user_count_by_period(db_session, start_date, end_date)
    backend_statistic = await backend_service.get_retail_statistics(start_date, end_date)

    # Формирование таблицы на основе полученных данных
    total_statistics = {
        'Количество пользователей': user_count,
        'Количество положительных реакцией': user_count_with_positive_feedback,
        'Количество отрицательных реакцией': user_count_with_negative_feedback,
    }

    bot_statistics = {
        'Версия': bot_statistic.bot_version,
        'Лайки': bot_statistic.total_likes,
        'Дизлайки': bot_statistic.total_dislikes,
        'Количество вопросов': bot_statistic.total_questions,
    }

    period_statistics = {
        'Количество новых пользователей': new_user_count_by_period,
        'Количество сообщений за период': backend_statistic.user_messages_count,
        'Количество уточнений за период': backend_statistic.clarify_count,
        'Количество ответов сгенерировано за период': backend_statistic.answers_count,
        'Количество положительных реакций': backend_statistic.like_count,
        'Количество отрицательных реакций': backend_statistic.dislike_count,
        'Количество входных токенов': backend_statistic.input_token_count,
        'Количество выходных токенов': backend_statistic.output_token_count,
    }

    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Общая статистика по боту помощнику за всё время'])
            for key, value in total_statistics.items():
                writer.writerow([key, value])

            writer.writerows([[], ['Статистика бота']])
            for key, value in bot_statistics.items():
                writer.writerow([key, value])

            writer.writerows([[], ['Количество пользователей по доменам:']], )
            for key, value in user_count_by_domain.items():
                writer.writerow([key, value])

            writer.writerows([[], ['За период', f'c {start_date}', f'по {end_date}']], )
            for key, value in period_statistics.items():
                writer.writerow([key, value])

            writer.writerows([[], ['Использование токенов']])
    except Exception as e:
        logging.exception(f'Ошибка при сохранении в CSV: %s', e)
