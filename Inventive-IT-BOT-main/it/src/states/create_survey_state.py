from aiogram.fsm.state import State, StatesGroup


class CreateSurveyState(StatesGroup):
    """
    Состояние во время создания опросника.

    Состояние:
    - WaitingQuestion: Ожидание вопроса для опросника
    - WaitingChoices: Ожидание Списка ответов для вопросника
    - WaitingConfirmation: Ожидание подтверждение или изменение текста опроса
    - WaitingMaxNumberChoicesState: Ожидание максимального количества вариантов ответов в опроснике
    - DateStartSelection: Выбор даты начала опроса пользователей
    - DateEndSelection: Выбор даты окончания опроса пользователей
    """
    WaitingQuestion = State()
    WaitingChoices = State()
    WaitingConfirmation = State()
    WaitingMaxNumberChoicesState = State()
    DateStartSelection = State()
    DateEndSelection = State()
