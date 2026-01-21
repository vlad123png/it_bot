from datetime import UTC, datetime
import sqlalchemy as sa
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base

if TYPE_CHECKING:
    from src.db.models.user import User
    from .survey import Survey
    from .survey_choice import SurveyChoice


class SurveyAnswer(Base):
    """
    Модель ответа пользователя на оприсник.
    
    :param id: Идентификатор ответа
    :param user_id: Идентификатор пользователя
    :param survey_id: Идентификатор опросника
    :param survey_choice_id: Идентификатор варианта ответа
    """

    __tablename__ = 'surveys_answers'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), nullable=False)
    survey_choice_id: Mapped[int] = mapped_column(ForeignKey('survey_choices.id', ondelete='CASCADE'), nullable=False)

    user: Mapped['User'] = relationship('User', back_populates='survey_answers')
    survey: Mapped['Survey'] = relationship('Survey', back_populates='answers')
    choice: Mapped['SurveyChoice'] = relationship('SurveyChoice', back_populates='survey_answers')

    def __repr__(self):
        return (f'<SurveyAnswer(user_id={self.user_id!r}, '
                f'survey_id={self.survey_id!r}, survey_choice_id={self.survey_choice_id!r})>')
