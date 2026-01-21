import datetime as dt
import logging
from typing import Sequence

from sqlalchemy import select, delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import BroadcastMessages


async def get_user_active_broadcast_messages(db_session: AsyncSession, user_id: int) -> Sequence[BroadcastMessages]:
    """
    Получает из базы данных активные рассылки пользователя.
    :param db_session: Асинхронная сессия с БД
    :param user_id: Идентификатор пользователя
    :return: Последовательность из сообщений из для рассылки
    """
    # + 12 часов, для того, чтобы учесть местное время самого раннего временного региона
    now = dt.datetime.now(dt.UTC) + dt.timedelta(hours=12)
    try:
        stmt = select(BroadcastMessages).where(
            BroadcastMessages.user_id == user_id,
            BroadcastMessages.delivery_time > now
        )
        result = await db_session.execute(stmt)
        return result.scalars().all()

    except SQLAlchemyError as e:
        logging.error(f'Ошибка получения активных рассылок для пользователя %s: %s', user_id, e)
        return []


async def get_broadcast_message(db_session: AsyncSession, broadcast_message_id: int) -> BroadcastMessages | None:
    """
    Получает из БД сообщение для рассылки
    :param db_session: Асинхронная сессия с БД
    :param broadcast_message_id: Идентификатор сообщения для рассылки
    :return: Сообщение для рассылки
    """
    try:
        stmt = select(BroadcastMessages).where(BroadcastMessages.id == broadcast_message_id)
        result = await db_session.execute(stmt)
        return result.scalars().one_or_none()
    except SQLAlchemyError as e:
        logging.error(f'Ошибка получения сообщения для рассылки %s: %s', broadcast_message_id, e)
        return None


async def delete_broadcast_message(db_session: AsyncSession, broadcast_message_id: int):
    """
    Удаляет из БД сообщение для рассылки
    :param db_session: Асинхронная сессия с БД
    :param broadcast_message_id: Идентификатор сообщения для рассылки
    """
    try:
        stmt = delete(BroadcastMessages).where(BroadcastMessages.id == broadcast_message_id)
        await db_session.execute(stmt)
        await db_session.commit()
    except SQLAlchemyError as e:
        logging.error(f'Ошибка при удалении сообщения для рассылки %s: %s', broadcast_message_id, e)


async def update_broadcast_message_text(db_session: AsyncSession, broadcast_message_id: int, text: str):
    """
    Изменяет текст сообщения для рассылки в БД
    :param db_session: Асинхронная сессия с БД
    :param broadcast_message_id: Идентификатор сообщения для рассылки
    :param text: Новый текст сообщения
    """
    try:
        stmt = update(BroadcastMessages).where(BroadcastMessages.id == broadcast_message_id).values(message=text)
        await db_session.execute(stmt)
        await db_session.commit()
    except SQLAlchemyError as e:
        logging.error(f'Ошибка обновления текста сообщения для рассылки %s: %s', broadcast_message_id, e)


async def update_broadcast_message_delivery_time(
        db_session: AsyncSession,
        broadcast_message_id: int,
        delivery_time: dt.datetime
):
    """
    Изменяет время доставки сообщения для рассылки в БД
    :param db_session: Асинхронная сессия с БД
    :param broadcast_message_id: Идентификатор сообщения для рассылки
    :param delivery_time: Новое время доставки сообщения
    """
    try:
        stmt = (update(BroadcastMessages)
                .where(BroadcastMessages.id == broadcast_message_id)
                .values(delivery_time=delivery_time)
                )
        await db_session.execute(stmt)
        await db_session.commit()
    except SQLAlchemyError as e:
        logging.error(f'Ошибка обновления времени доставки сообщения для рассылки %s: %s', broadcast_message_id, e)
