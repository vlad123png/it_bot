from datetime import UTC, datetime
import sqlalchemy as sa
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class BroadcastMessages(Base):
    """
    Модель рассылки сообщений.

    :param id: Идентификатор ответа ИИ
    :param user_id: Идентификатор пользователя
    :param message: Разосланное сообщение
    :param successful_sends: Количество успешных отправок сообщения
    :param failed_sends: Количество неудачных отправок сообщения
    :param finished: Флаг завершения рассылки
    :param delivery_time: Время в которое пользователь получит сообщение.
    :param finished_at: Время завершения рассылки в UTC.
    """
    __tablename__ = 'broadcast_messages' # noqa

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    successful_sends: Mapped[int] = mapped_column(default=0)
    failed_sends: Mapped[int] = mapped_column(default=0)
    finished: Mapped[bool] = mapped_column(default=False)
    delivery_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)")
    )
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped['User'] = relationship(back_populates='broadcast_messages')

    def __repr__(self):
        return f'<Broadcast: {self.id}>'
