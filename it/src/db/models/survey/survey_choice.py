from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship

from src.db.models.base import Base

if TYPE_CHECKING:
    from .survey import Survey
    from .survey_answer import SurveyAnswer


class SurveyChoice(Base):
    """
    Варианты ответов на опросник

    :param id: Идентификатор ответа
    :param text: Текст ответа
    :param survey_id: Идентификатор опросника
    """

    __tablename__ = 'survey_choices'

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), nullable=False)

    survey: Mapped['Survey'] = relationship('Survey', back_populates='choices', cascade='all, delete')
    survey_answers: Mapped[list['SurveyAnswer']] = relationship('SurveyAnswer', back_populates='choice')

    def __repr__(self):
        return f'<SurveyChoice(id={self.id}, survey_id={self.survey_id}, text={self.text})>'
