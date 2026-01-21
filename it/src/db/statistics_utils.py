import datetime as dt
import logging
from typing import Sequence

import sqlalchemy as sa
from sqlalchemy import select, func, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, Statistic

__all__ = [
    'get_user_count',
    'get_users_with_positive_feedback_count',
    'get_users_with_negative_feedback_count',
    'get_bot_statistic',
    'get_user_count_by_period',
    'get_batch_user_emails',
]


async def get_user_count(db_session: AsyncSession) -> int | None:
    """
    Получение количества пользователей.
    """
    try:
        stmt = select(func.count()).select_from(User)
        result = await db_session.execute(stmt)
        return result.scalar_one()
    except SQLAlchemyError:
        logging.exception('Ошибка получения количества пользователей.')
        return None


async def get_users_with_positive_feedback_count(db_session: AsyncSession) -> int | None:
    """
    Получение количества пользователей, которые оценили ответ бота положительно.
    """
    try:
        stmt = select(func.count()).select_from(User).where(User.quantity_like > 0)
        result = await db_session.execute(stmt)
        return result.scalar_one()
    except SQLAlchemyError:
        logging.exception('Ошибка получения количества пользователей с положительными отзывами.')
        return None


async def get_users_with_negative_feedback_count(db_session: AsyncSession) -> int | None:
    """
    Получение количества пользователей, которые оценили ответ бота отрицательно.
    """
    try:
        stmt = select(func.count()).select_from(User).where(User.quantity_dislike > 0)
        result = await db_session.execute(stmt)
        return result.scalar_one()
    except SQLAlchemyError:
        logging.exception('Ошибка получения количества пользователей с положительными отзывами.')
        return None


async def get_batch_user_emails(db_session: AsyncSession, offset: int, limit: int) -> Sequence[str] | None:
    """
    Получение inventive user email с пагинацией.
    """
    try:
        stmt = select(User.inventive_email).limit(limit).offset(offset)
        result = await db_session.execute(stmt)
        return result.scalars().all()
    except SQLAlchemyError:
        logging.exception('Ошибка получения общего количества вопросов к боту.')
        return None


async def get_bot_statistic(db_session: AsyncSession) -> Statistic | None:
    """
    Получение общей статистики по боту.
    """
    try:
        stmt = select(Statistic).order_by(desc(Statistic.id)).limit(1)
        result = await db_session.execute(stmt)
        last_row = result.scalar_one_or_none()
        return last_row
    except SQLAlchemyError:
        logging.exception('Ошибка получения общего количества вопросов к боту.')
        return None


async def get_user_count_by_period(db_session: AsyncSession, start_date: dt, end_date: dt) -> int | None:
    """
    Получение количества пользователей за период.
    """
    try:
        stmt = select(sa.func.count()).select_from(User).where(
            User.created_at >= start_date,
            User.created_at < end_date + dt.timedelta(seconds=1)
        )
        result = await db_session.execute(stmt)
        return result.scalar_one()
    except SQLAlchemyError:
        logging.exception('Ошибка получения количества пользователей за период.')
        return None
