from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class CountUserQuestions(Base):
    """
    Модель подсчёта запросов пользователя.

    :param id: Идентификатор ответа ИИ
    :param user_id: Идентификатор пользователя в Telegram
    :param counts: Количество запросов пользователя
    """

    __tablename__ = 'counts_users_questions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    counts: Mapped[int] = mapped_column(nullable=False, default=0)

    user: Mapped['User'] = relationship(back_populates='count_user_questions', uselist=False)

    def __repr__(self):
        return f'<{self.__class__.__name__}(id={self.id}, user_id={self.user_id}, counts={self.counts})>'
