from datetime import datetime
from enum import Enum
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, ForeignKey, DateTime, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .broadcast_messages import BroadcastMessages
from .count_user_questions import CountUserQuestions
from .survey.survey import Survey
from .survey.survey_answer import SurveyAnswer


class UserRole(str, Enum):
    """
    Класс описывающий возможные роли пользователя.
    """
    CLIENT = 'client'
    ADMIN = 'admin'


class User(Base):
    """
    Модель пользователя.

    :param id: Идентификатор пользователя
    :param telegram_id: Идентификатор пользователя в Telegram
    :param inventive_id: Идентификатор пользователя в Inventive
    :param auth_logs: Связь с записями в журнале аутентификаций пользователей
    :param role: Роль пользователя
    :param quantity_all: Общее количество отзывов о работе бота
    :param quantity_like: Количество положительных отзывов о работе бота
    :param quantity_dislike: Количество отрицательных отзывов о работе бота
    :param broadcast_messages: Сообщения которые рассылал пользователь
    """

    __tablename__ = 'users'  # noqa

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    backend_id: Mapped[UUID | None] = mapped_column(nullable=True, default=None)
    telegram_username: Mapped[str] = mapped_column(String(64), nullable=True)
    inventive_id: Mapped[int] = mapped_column(nullable=False)
    inventive_email: Mapped[str] = mapped_column(String(64), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, native_enum=False, length=32), nullable=False,default=UserRole.CLIENT
    )
    timezone: Mapped[int] = mapped_column(nullable=False)

    quantity_all: Mapped[int] = mapped_column(nullable=False, default=0)
    quantity_like: Mapped[int] = mapped_column(nullable=False, default=0)
    quantity_dislike: Mapped[int] = mapped_column(nullable=False, default=0)

    auth_logs: Mapped[list['AuthLog']] = relationship(
        'AuthLog',
        back_populates='user',
        order_by='desc(AuthLog.auth_time)',
    )
    count_user_questions: Mapped['CountUserQuestions'] = relationship(back_populates='user')
    broadcast_messages: Mapped['BroadcastMessages'] = relationship(back_populates='author')
    surveys: Mapped[list['Survey']] = relationship(back_populates='author')
    survey_answers: Mapped['SurveyAnswer'] = relationship(back_populates='user')

    def __repr__(self):
        return f'<{self.__class__.__name__}(id={self.id}, telegram_id={self.telegram_id})>'


class AuthLog(Base):
    """
    Модель журнала аутентификаций пользователей.

    :param id: Идентификатор записи
    :param user_id: Идентификатор пользователя
    :param auth_time: Время аутентификации
    :param user: Связь с пользователем данной записи
    """

    __tablename__ = 'auth_logs'  # noqa

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    auth_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)")
    )

    user: Mapped['User'] = relationship(back_populates='auth_logs')

    def __repr__(self):
        return f'<{self.__class__.__name__}(id={self.id}, user_id={self.user_id})>'
