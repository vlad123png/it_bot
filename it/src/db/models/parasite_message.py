from typing import TYPE_CHECKING

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

if TYPE_CHECKING:
    pass


class ParasiteMessage(Base):
    """
    Модель паразитных сообщений.

    :param id: Идентификатор ответа ИИ
    :param chat_id: Идентификатор чата в Telegram
    :param message_id: Идентификатор сообщения в Telegram
    """

    __tablename__ = 'parasite_messages' # noqa

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    def __repr__(self):
        return f'<{self.__class__.__name__}(id={self.id}, chat_id={self.chat_id}, message_id={self.message_id})>'
