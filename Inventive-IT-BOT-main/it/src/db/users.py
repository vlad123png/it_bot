import logging
from typing import Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config.settings import settings
from .models import User, CountUserQuestions, UserRole, SurveyAnswer


async def get_all_users(
        db_session: AsyncSession,
) -> list[User]:
    """Получить всех пользователей"""
    query = (
        select(User)
    )
    result = await db_session.execute(query)
    return result.scalars().all() # noqa

async def update_user_backend_id(db_session: AsyncSession, user_id: int, backend_id: str | UUID) -> None:
    """Обновляет backend id пользователя"""
    query = update(User).where(User.id == user_id).values(backend_id=backend_id)
    await db_session.execute(query)


async def get_user_by_telegram_id(
        db_session: AsyncSession,
        telegram_id: int
) -> User | None:
    """
    Получает пользователя по идентификатору в Telegram.

    :param db_session: База данных
    :type db_session: AsyncSession
    :param telegram_id: Идентификатор пользователя в Telegram
    :type telegram_id: int

    :return: Пользователь или None
    :rtype: Optional[User]
    """
    query = (
        select(User)
        .options(joinedload(User.auth_logs))
        .where(User.telegram_id == telegram_id)
    )
    result = await db_session.execute(query)
    return result.scalars().first()


async def get_user_telegram_ids_by_timezones(
        db_session: AsyncSession,
        timezone: int,
        page_size: int,
        page_number: int
) -> list[int]:
    """
    Получает список пользователей, включая только их telegram_id,
    с использованием пагинации.

    :param db_session: Асинхронная сессия SQLAlchemy для выполнения запросов.
    :param page_size: Количество пользователей, возвращаемых на одной странице.
    :param page_number: Номер страницы для выборки пользователей.
    :param timezone: Часовой пояс пользователя
    :return: Список кортежей (telegram_id, timezone).
    """
    try:
        offset = (page_number - 1) * page_size
        query = (
            select(User.telegram_id)
            .where(User.timezone == timezone)
            .offset(offset)
            .limit(page_size)
        )
        result = await db_session.execute(query)
        users = result.all()
        return [user[0] for user in users]
    except SQLAlchemyError as e:
        logging.error(f'не удалось получить пользователей в часовом поясе %s: %s', timezone, e)
        return []


async def get_non_voted_user_ids_by_timezone(
        db_session: AsyncSession,
        survey_id: int,
        timezone: int,
        page_size: int,
        page_number: int
) -> list[int]:
    """
    Получает список пользователей не прошедших опрос, включая только их telegram_id,
    с использованием пагинации.

    :param db_session: Асинхронная сессия SQLAlchemy для выполнения запросов.
    :param survey_id: Идентификатор опроса.
    :param page_size: Количество пользователей, возвращаемых на одной странице.
    :param page_number: Номер страницы для выборки пользователей.
    :param timezone: Часовой пояс пользователя
    :return: Список кортежей (telegram_id, timezone).
    """
    try:
        offset = (page_number - 1) * page_size
        subquery = (
            select(SurveyAnswer.user_id)
            .where(SurveyAnswer.survey_id == survey_id)
            .scalar_subquery()
        )
        query = (
            select(User.telegram_id)
            .where(User.timezone == timezone)
            .where(User.id.notin_(subquery))
            .offset(offset)
            .limit(page_size)
        )
        result = await db_session.execute(query)
        return [row[0] for row in result.all()]
    except SQLAlchemyError as e:
        logging.error(f'не удалось получить пользователей не прошедших опрос %s: %s', survey_id, e)
        return []


async def get_user_survey_answers_by_survey_id(
        db_session: AsyncSession,
        user_id: int,
        survey_id: int
) -> Sequence[SurveyAnswer]:
    """
    Получение голосов пользователя в конкретном опросе.
    :param db_session: Асинхронная сессия SQLAlchemy для выполнения запросов.
    :param user_id: Идентификатор пользователя.
    :param survey_id: Идентификатор опроса.
    :return:
    """
    try:
        stmt = select(SurveyAnswer).where(SurveyAnswer.user_id == user_id, SurveyAnswer.survey_id == survey_id)
        result = await db_session.execute(stmt)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logging.error(f'Ошибка при проверке голосования пользователя %s в опросе %s: %s', user_id, survey_id, e)
        return []


async def set_user_role_by_inventive_id(
        db_session: AsyncSession,
        inventive_id: int,
        user_role: UserRole
):
    """
    Изменяет права пользователя (роль) по id в inventive
    :param db_session: Сессия базы данных
    :param inventive_id: ID пользователя в inventive
    :param user_role: Роль пользователя
    :return: True - если пользователь получил права администратора, иначе False
    """
    stmt = (
        update(User)
        .where(User.inventive_id == inventive_id)
        .values(role=user_role)
    )
    result = await db_session.execute(stmt)
    if result.rowcount == 0:
        return False
    else:
        await db_session.commit()
        return True


async def check_user_request_to_ai(
        db_session: AsyncSession,
        user_id: int,
):
    """
    Проверяет количество обращений пользователя к ИИ.
    :param db_session: Сессия с БД.
    :param user_id: ID пользователя в БД.
    :return bool: Может ли пользователь совершать запрос (True - может, False - нет)
    """
    # Получаем количество запросов пользователя
    query = select(CountUserQuestions).where(CountUserQuestions.user_id == user_id)
    result = await db_session.execute(query)
    counts = result.scalars().first()

    # Если записи нет, то считаем, создаём новую запись для пользователя
    if counts is None:
        new_record = CountUserQuestions(user_id=user_id, counts=1)
        db_session.add(new_record)
        await db_session.commit()
        return True

    return counts.counts < settings.AI.REQUESTS_COUNT


async def increment_user_request_to_ai(
        db_session: AsyncSession,
        user_id: int,
):
    """
    Увеличивает количество запросов пользователя к ИИ.
    :param db_session: Сессия с БД
    :param user_id: ID пользователя в БД
    """
    try:
        await db_session.execute(
            update(CountUserQuestions)
            .where(CountUserQuestions.user_id == user_id)
            .values({"counts": CountUserQuestions.counts + 1})
        )
        await db_session.commit()
    except SQLAlchemyError as e:
        logging.error(f'Не удалось изменить количество запросов пользователя %s к ИИ: %s', user_id, e)


async def reset_counts_user_questions(db_session: AsyncSession):
    """Сбрасывает количество обращений пользователя к ИИ за сутки."""
    try:
        stmt = update(CountUserQuestions).values(counts=0)
        result = await db_session.execute(stmt)
        await db_session.commit()
        logging.info(f'Сброшено количество обращений к ИИ для {result.rowcount} пользователей.')
    except SQLAlchemyError as e:
        logging.error(f'Не удалось сбросить количество обращений пользователя к ИИ: {e}')
        await db_session.rollback()


async def change_user_timezone(db_session: AsyncSession, user: User, offset: int):
    """
    Изменяет часовой пояс пользователя
    :param db_session: Асинхронная сессия SQLAlchemy для выполнения запросов.
    :param user: Пользователь
    :param offset: Смещение относительно UTC
    """
    try:
        stmt = update(User).values(timezone=offset).where(User.id == user.id)
        await db_session.execute(stmt)
        await db_session.commit()
        logging.info(f'Изменён часовой пояс пользователя %s на %s', user.id, offset)
    except SQLAlchemyError as e:
        await db_session.rollback()
        logging.error(f'Не удалось изменить часовой пояс для пользователя %: %s', user.id, e)
