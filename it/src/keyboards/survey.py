from typing import Sequence

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.callbacks import ConfirmationCallback, ConfirmationAction, SurveyChoiceCallback, ConfirmSurveyChoiceCallback


def get_example_choices_inline_keyboard(choices: list[str]) -> InlineKeyboardMarkup:
    """ Возвращает клавиатуру для примера сообщения с опросом. """
    builder = InlineKeyboardBuilder()
    for choice in choices:
        builder.add(InlineKeyboardButton(text=choice, callback_data='none'))
    builder.adjust(1)

    builder.row(InlineKeyboardButton(text='Отправить', callback_data='none'))
    return builder.as_markup()


def get_choices_inline_keyboard(
        choices: list[[str, int]],
        selected_id: Sequence[int],
        survey_id: int
) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для сообщения с опросом.
    :param choices: Список вариантов из названий и их идентификаторов
    :param selected_id: Список идентификаторов выбранных вариантов
    :param survey_id: Идентификатор опроса
    :return: Инлайн клавиатура
    """
    builder = InlineKeyboardBuilder()
    for choice in choices:
        text = choice[0]
        if choice[1] in selected_id:
            text = '★ ' + text

        builder.add(
            InlineKeyboardButton(
                text=text,
                callback_data=SurveyChoiceCallback(choice_id=choice[1], confirm=False).pack())
        )
    builder.adjust(1)

    builder.row(InlineKeyboardButton(
        text='Отправить',
        callback_data=ConfirmSurveyChoiceCallback(survey_id=survey_id).pack())
    )
    return builder.as_markup()


def confirm_survey_inline_keyboard() -> InlineKeyboardMarkup:
    """ Создаёт клавиатуру с подтверждением опроса """
    builder = InlineKeyboardBuilder()
    builder.button(
        text='Отправить',
        callback_data=ConfirmationCallback(action=ConfirmationAction.confirm).pack()
    )
    builder.button(
        text='Отредактировать',
        callback_data=ConfirmationCallback(action=ConfirmationAction.edit).pack()
    )
    builder.adjust(1)
    return builder.as_markup()
