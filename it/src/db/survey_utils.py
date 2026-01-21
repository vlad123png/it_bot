import datetime as dt
import sqlalchemy as sa
import logging
from typing import Sequence

from cachetools import TTLCache
from sqlalchemy import select, func, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, load_only

from .models import SurveyChoice, SurveyAnswer
from .models.survey.survey import Survey

survey_cache = TTLCache(maxsize=1000, ttl=3600)  # Кэширование запросов на 1 час


async def create_survey(
        db_session: AsyncSession,
        user_id: int,
        question: str,
        max_choices: int,
        start_datetime: dt.datetime,
        end_datetime: dt.datetime,
):
    """
    Создание опроса в БД
    :param db_session: Асинхронная сессия с БД
    :param user_id: ID пользователя (автор)
    :param question: Текст вопроса опроса
    :param max_choices: Максимальное количество ответов
    :param start_datetime: Время рассылки опроса
    :param end_datetime: Время завершения опроса
    :return: Идентификатор опроса
    """
    survey = Survey(
        user_id=user_id,
        question=question,
        max_choices=max_choices,
        start_date=start_datetime,
        end_date=end_datetime
    )
    db_session.add(survey)
    await db_session.commit()
    logging.debug(f'Создан опрос: {repr(survey)}')
    return survey.id


async def get_survey_by_id(db_session: AsyncSession, survey_id: int, include_choices: bool = False) -> Survey | None:
    """
    Получение опроса из БД по идентификатору.
    :param db_session: Асинхронная сессия с БД.
    :param survey_id: Идентификатор опроса.
    :param include_choices: Включить ли связанные варианты ответов.
    :return: Объект опроса или None, если не найден.
    """
    try:
        stmt = select(Survey).where(Survey.id == survey_id)
        if include_choices:
            stmt = stmt.options(selectinload(Survey.choices))

        result = await db_session.execute(stmt)
        survey = result.scalars().first()
        return survey
    except SQLAlchemyError as e:
        logging.error(f'Ошибка получения опроса {survey_id}: {e}')
        return None


async def get_user_active_surveys(db_session: AsyncSession, user_id: int) -> Sequence[Survey]:
    """
    Получает список запланированных рассылок опросов.
    :param db_session: Асинхронная сессия с БД
    :param user_id: Идентификатор пользователя
    :return: Список запланированных опросов пользователя.
    """
    try:
        # + 12 часов, для того, чтобы учесть местное время самого раннего временного региона
        now = dt.datetime.now(dt.UTC) + dt.timedelta(hours=12)
        stmt = (
            select(Survey)
            .options(load_only(Survey.id, Survey.question, Survey.start_date))
            .where(Survey.user_id == user_id, Survey.start_date > now)
        )
        result = await db_session.execute(stmt)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logging.error(f'Ошибка получения запланированных опросов пользователя %s: %s', user_id, e)
        return []


async def update_survey(
        db_session: AsyncSession,
        survey: Survey
):
    """
    Обновление опроса по переданным параметрам.
    :param db_session: Сессия базы данных.
    :param survey: Опрос
    """
    try:
        db_session.add(survey)
        await db_session.commit()
    except SQLAlchemyError as e:
        await db_session.rollback()
        logging.error(f'Ошибка обновления опроса %s: %s', survey.id, e)


async def delete_survey(db_session: AsyncSession, survey_id: int):
    """
    Удаляет из БД опрос
    :param db_session: Асинхронная сессия с БД
    :param survey_id: Идентификатор опроса
    """
    try:
        await db_session.execute(delete(Survey).where(Survey.id == survey_id))
    except SQLAlchemyError as e:
        logging.error(f'Ошибка удаления опроса %s из БД: %s', survey_id, e)


async def create_survey_choices(db_session: AsyncSession, survey_id: int, choices: list[str]) -> list[list[str | int]]:
    """
    Создание вариантов ответов для опроса.
    :param db_session: Асинхронная сессия с БД
    :param survey_id: Идентификатор опроса
    :param choices: Список текстов вариантов ответов
    :return: Список из текста и id вариантов ответов
    """
    try:
        list_choices = [SurveyChoice(survey_id=survey_id, text=choice) for choice in choices]
        db_session.add_all(list_choices)
        await db_session.commit()
        logging.debug(f'Успешно созданы варианты ответов для опроса %s', survey_id)
        return [[choice.text, choice.id] for choice in list_choices]
    except SQLAlchemyError:
        await db_session.rollback()
        logging.info(f'Не удалось создать варианты ответов для опроса %s', survey_id)
        return []


async def change_survey_choices(db_session: AsyncSession, survey_id: int, new_choices: Sequence[SurveyChoice]):
    """
    Удаляет старые ответы и добавляет новые.
    :param db_session: Асинхронная сессия с БД
    :param survey_id: Идентификатор опроса
    :param new_choices: Список новых вариантов ответа
    """
    try:
        await db_session.execute(
            delete(SurveyChoice).where(SurveyChoice.survey_id == survey_id)
        )
        db_session.add_all(new_choices)
        await db_session.commit()
    except SQLAlchemyError as e:
        await db_session.rollback()
        logging.error(f'Не удалось изменить ответы на опрос %s: %s', survey_id, e)


async def get_survey_with_choices_by_choice_id(db_session: AsyncSession, choice_id: int) -> Survey | None:
    """
    Возвращает опрос с ответами по id ответа. Используется кэширование результата запроса.
    :param db_session: Асинхронная сессия с БД
    :param choice_id: Идентификатор ответа на опрос
    """

    # Проверка кэша
    if choice_id in survey_cache:
        return survey_cache[choice_id]

    try:
        query = (
            select(Survey)
            .join(SurveyChoice, Survey.id == SurveyChoice.survey_id)
            .filter(SurveyChoice.id == choice_id)
            .options(selectinload(Survey.choices))
        )
        result = await db_session.execute(query)
        survey = result.scalars().one_or_none()

        # Кэширование ответа
        if survey:
            for choice in survey.choices:
                survey_cache[choice.id] = survey

        return survey
    except SQLAlchemyError:
        logging.error(f'Не удалось получить опрос с вариантами выбора ответов.')
        return None


async def save_user_choices(
        db_session: AsyncSession,
        user_id: int,
        survey_id: int,
        choices_id: list[int],
):
    """
    Сохраняет результаты опроса пользователя.
    :param db_session: Асинхронная сессия с БД
    :param user_id: Идентификатор пользователя
    :param survey_id: Идентификатор опроса
    :param choices_id: Список идентификаторов ответов на опрос.
    """
    try:
        survey_answers = [
            SurveyAnswer(user_id=user_id, survey_id=survey_id, survey_choice_id=choice_id) for choice_id in choices_id
        ]
        db_session.add_all(survey_answers)
        await db_session.commit()
    except SQLAlchemyError:
        logging.error(f'Не удалось сохранить ответы %s пользователя %s на опрос %s', choices_id, user_id, survey_id)


async def get_survey_results(db_session: AsyncSession, survey_id: int, user_id: int) -> Survey | None:
    """
    Возвращает результат опроса по идентификатору из базы данных.
    :param db_session: Асинхронная сессия с БД
    :param survey_id: Идентификатор опроса
    :param user_id: Идентификатор пользователя
    :return: Опрос с результатами
    """
    try:
        # Создаём подзапрос для подсчёта количества ответов на каждый выбор
        subquery = (
            select(
                SurveyChoice.id,
                sa.func.coalesce(sa.func.count(SurveyAnswer.id), 0).label('choice_count')
            )
            .join(SurveyAnswer, SurveyAnswer.survey_choice_id == SurveyChoice.id, isouter=True)
            .filter(SurveyChoice.survey_id == survey_id)
            .group_by(SurveyChoice.id)
            .subquery()
        )

        # Основной запрос для загрузки опроса с вариантами
        stmt = (
            select(Survey)
            .options(
                selectinload(Survey.choices)
            )
            .filter(Survey.id == survey_id, Survey.user_id == user_id)
        )

        # Выполнение запроса
        result = await db_session.execute(stmt)
        survey = result.scalars().first()

        # Присваиваем количество ответов каждому варианту
        if survey:
            count_result = await db_session.execute(select(subquery))
            counts = {row.id: row.choice_count for row in count_result}

            for choice in survey.choices:
                choice.choice_count = counts.get(choice.id, 0)

        return survey
    except SQLAlchemyError as e:
        logging.error(f'Не удалось получить результат опроса %s из БД: %s', survey_id, e)
        return None
