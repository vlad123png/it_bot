from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Statistic(Base):
    """
    Модель статистика работы бота.

    :param id: Идентификатор ответа ИИ
    :param bot_version: Версия бота
    :param total_likes: Общее количество лайков на ответы ИИ
    :param total_dislikes: Общее количество дизлайков на ответы ИИ
    """

    __tablename__ = 'statistics'

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_version: Mapped[str] = mapped_column(String(20))
    total_questions: Mapped[int] = mapped_column(BigInteger, default=0)
    total_likes: Mapped[int] = mapped_column(BigInteger, default=0)
    total_dislikes: Mapped[int] = mapped_column(BigInteger, default=0)
