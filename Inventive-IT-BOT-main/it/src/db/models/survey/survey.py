from datetime import UTC, datetime
import sqlalchemy as sa
from typing import TYPE_CHECKING

from sqlalchemy import Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base

if TYPE_CHECKING:
    from .survey_answer import SurveyAnswer
    from .survey_choice import SurveyChoice
    from src.db.models.user import User


class Survey(Base):
    """
    Опросник
    :param id: Идентификатор опросника
    :param question: Вопрос
    :param max_choices: Максимальное количество вариантов ответов, которые может выбрать пользователь
    :param start_date: Время начала опроса (рассылка опросника пользователям)
    :param end_date: Время окончания опроса
    :param created_at: Время создания опросника
    """

    __tablename__ = 'surveys'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    max_choices: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    choices: Mapped[list['SurveyChoice']] = relationship('SurveyChoice', back_populates='survey')
    answers: Mapped[list['SurveyAnswer']] = relationship('SurveyAnswer', back_populates='survey')
    author: Mapped['User'] = relationship('User', back_populates='surveys')

    def __repr__(self):
        return f'<Survey {self.id}, question={self.question[:20]}...'
