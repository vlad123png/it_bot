import datetime as dt
import sqlalchemy as sa
import logging
from typing import Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from .models import User, ParasiteMessage, Statistic
from .models.broadcast_messages import BroadcastMessages


async def save_parasite_message(
        db_session: AsyncSession,
        chat_id: int,
        message_id: int
):
    """
    Добавляет паразитное сообщения в базу данных
    :param db_session: База данных
    :param chat_id: ID чата
    :param message_id: ID паразитного сообщения в telegram
    """
    db_session.add(ParasiteMessage(chat_id=chat_id, message_id=message_id))
    await db_session.commit()
    logging.debug('Добавлено "паразитное сообщение" %s', message_id)


async def save_parasite_messages(db_session: AsyncSession, chat_id: int, messages_id: list[int]):
    """
    Добавляет список паразитных сообщений в базу данных
    :param db_session: Асинхронная сессия БД
    :param chat_id: Индентификатор чата
    :param messages_id: Список id сообщений в telegram
    """
    if not messages_id:
        logging.debug('Список паразитных сообщений пуст')
        return

    db_session.add_all([ParasiteMessage(chat_id=chat_id, message_id=message_id) for message_id in messages_id])
    await db_session.commit()
    logging.debug('Добавлены "паразитные сообщения" %s', messages_id)


async def get_all_parasite_messages_by_chat_id(
        db_session: AsyncSession,
        chat_id: int,
) -> Sequence[ParasiteMessage]:
    """
        Возвращает все паразитные сообщения пользвователя из БД
        :param db_session: База данных
        :param chat_id: ID чата с пользователем
        :return Sequence[ParasiteMessage]: Список паразитных сообщений
    """
    query = select(ParasiteMessage).where(ParasiteMessage.chat_id == chat_id)
    result = await db_session.execute(query)
    parasite_messages = result.scalars().all()
    return parasite_messages


async def delete_all_parasite_messages_by_chat_id(
        db_session: AsyncSession,
        chat_id: int
):
    """
        Удаляет все паразитные сообщения пользвователя из БД
        :param db_session: База данных
        :param chat_id: ID чата с пользователем
    """
    query = delete(ParasiteMessage).where(ParasiteMessage.chat_id == chat_id)
    await db_session.execute(query)
    await db_session.commit()
    logging.debug('Все паразитные сообщения в чате %s удалены.', chat_id)


async def increment_feedback(db_session: AsyncSession, like: bool = True):
    """
    Инкриминирует количество лайков или дизлайков для заданной версии бота.

    :param db_session: Асинхронная сессия SQLAlchemy.
    :param like: Если True, инкриминируются лайки; если False, инкриминируются дизлайки.
    """
    # Установим поле для обновления на основе типа отзыва
    field_to_increment = Statistic.total_likes if like else Statistic.total_dislikes

    # Выполняем запрос на вставку или обновление
    update_stmt = (
        update(Statistic)
        .where(Statistic.bot_version == settings.BOT_VERSION)
        .values({field_to_increment: field_to_increment + 1,
                 Statistic.total_questions: Statistic.total_questions + 1})
    )
    result = await db_session.execute(update_stmt)

    # Создание новой записи, если версия бота изменилась
    if result.rowcount == 0:
        new_values = {
            'bot_version': settings.BOT_VERSION,
            'total_questions': 1,
            'total_likes': 1 if like else 0,
            'total_dislikes': 0 if like else 1
        }
        insert_stmt = insert(Statistic).values(new_values)
        await db_session.execute(insert_stmt)
    await db_session.commit()


async def create_broadcast_message(
        db_session: AsyncSession,
        user_id: int,
        message: str,
        delivery_time: dt.datetime,
) -> int:
    """
    Создаёт запись о рассылке сообщения пользователем.
    :param db_session: Асинхронная сессия SQLAlchemy для выполнения запросов.
    :param user_id: Пользователь создавший рассылку
    :param message: Сообщения для рассылки
    :param delivery_time: Дата и время начала рассылки
    :return: Id записи
    """
    try:
        stmt = insert(BroadcastMessages).values({
            'user_id': user_id,
            'message': message,
            'delivery_time': delivery_time
        })
        result = await db_session.execute(stmt)
        broadcast_message_id = result.inserted_primary_key[0]
        await db_session.commit()
        logging.info(f'Создана запись о рассылки сообщения пользователем %s', user_id)
        return broadcast_message_id
    except SQLAlchemyError as e:
        await db_session.rollback()
        logging.error(f'Не удалось создать запись рассылки сообщения для пользователя %s: %s', user_id, e)
        return -1


async def update_broadcast_message(
        db_session: AsyncSession,
        broadcast_message_id: int,
        successful_sends_increment: int,
        failed_sends_increment: int,
        finished: bool = False
):
    """
    Обновляет информацию о рассылки сообщения
    :param db_session: Асинхронная сессия SQLAlchemy для выполнения запросов.
    :param broadcast_message_id: ID записи о рассылки сообщения
    :param successful_sends_increment: Количество успешно отправленных сообщений, 
        которое нужно добавить к текущему значению.
    :param failed_sends_increment: Количество неудачных отправок сообщений, 
        которое нужно добавить к текущему значению.
    :param finished: Флаг, указывающий, завершена ли рассылка.
    """
    try:
        stmt = (
            update(BroadcastMessages).
            where(BroadcastMessages.id == broadcast_message_id).
            values({
                'successful_sends': BroadcastMessages.successful_sends + successful_sends_increment,
                'failed_sends': BroadcastMessages.failed_sends + failed_sends_increment,
                'finished': finished,
                'finished_at': dt.datetime.now(dt.UTC) if finished else None,
            })
        )
        await db_session.execute(stmt)
        await db_session.commit()
        logging.debug(f'Обновлена запись %s о рассылки сообщения.', broadcast_message_id)
    except SQLAlchemyError as e:
        await db_session.rollback()
        logging.error(f'Не удалось обновить запись рассылки сообщения %s: %s', broadcast_message_id, e)


async def get_unique_timezones(db_session: AsyncSession) -> list[int]:
    """ Возвращает отсартированный список timezone пользователей """
    try:
        result = await db_session.execute(select(User.timezone).distinct().order_by(User.timezone))
        timezones = [timezone[0] for timezone in result.fetchall()]
        logging.debug('Уникальные часовые пояса пользователей успешно получены.')
        return timezones

    except SQLAlchemyError as e:
        await db_session.rollback()
        logging.error(f'Не удалось получить часовые пояса пользователей: %s', e)
        return []
