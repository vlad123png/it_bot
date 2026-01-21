from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.db.models import User, AuthLog, CountUserQuestions


async def get_user_by_telegram_id(
        db_session: AsyncSession,
        telegram_id: int
) -> Optional[User]:
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


async def create_or_update_user(
        db_session: AsyncSession,
        telegram_id: int,
        inventive_id: int,
        backend_id: str | None,
        user_timezone: int,
        telegram_username: str,
        inventive_email: str
) -> User:
    """
    Создает нового или обновляет пользователя по идентификатору в Telegram.

    :param db_session: База данных
    :type db_session: AsyncSession
    :param telegram_id: Идентификатор пользователя в Telegram
    :type telegram_id: int
    :param inventive_id: Идентификатор пользователя в Inventive
    :type inventive_id: int
    :param user_timezone: Часовой пояс пользователя
    :type backend_id: str
    :param backend_id: Идентификатор пользователя в бэкенд сервисе
    :type user_timezone: int
    :param telegram_username: Имя пользователя в telegram
    :type telegram_username: str
    :param inventive_email: Email пользователя в Intraservice
    :type inventive_email: str

    :return: Пользователь
    :rtype: User
    """
    query = (
        select(User)
        .options(joinedload(User.auth_logs))
        .where(User.telegram_id == telegram_id)
    )
    result = await db_session.execute(query)
    user: User = result.scalars().first()

    if user:
        user.inventive_id = inventive_id
        user.inventive_email = inventive_email
        user.backend_id = backend_id
    else:
        user = User(
            telegram_id=telegram_id,
            inventive_id=inventive_id,
            inventive_email=inventive_email,
            timezone=user_timezone,
            telegram_username=telegram_username,
            backend_id=backend_id,
        )
        db_session.add(user)

        user.count_user_questions = CountUserQuestions(user=user)
        db_session.add(user.count_user_questions)

    # Добавляем запись в auth_logs
    auth_log = AuthLog(user=user)
    user.auth_logs.append(auth_log)

    # Сохраняем изменения
    await db_session.commit()
    return user
