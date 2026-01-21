from aiogram.fsm.state import StatesGroup, State


class ChangeBroadcastMessageState(StatesGroup):
    """
    Состояние в процессе изменения запланированного сообщения для рассылки.

    Состояния:
    - ChangeBroadcastMessage: Изменение сообщение для рассылки
    - WaitingNewText: Изменение сообщение для рассылки
    - NewDateSelection: Изменение даты рассылки
    - NewTimeSelection: Изменение времени рассылки.
    """
    ChangeBroadcastMessage = State()
    WaitingNewText = State()
    NewDateSelection = State()
    NewTimeSelection = State()


class ChangeBroadcastSurveyState(StatesGroup):
    """
    Состояние в процессе изменения запланированного опроса для рассылки.

    Состояния:
    - ChangeBroadcastSurvey: Изменение опроса для рассылки
    - InputNewQuestion: Изменение вопроса для опроса
    - InputNewChoices: Изменение вариантов ответов
    - InputMaxNumberChoices: Изменение максимального количества ответов
    - NewStartDateSelection: Изменение даты начала опроса
    - NewEndDateSelection: Изменение даты завершения опроса
    """
    ChangeBroadcastSurvey = State()
    InputNewQuestion = State()
    InputNewChoices = State()
    InputMaxNumberChoices = State()
    NewStartDateSelection = State()
    NewStartTimeSelection = State()
    NewEndDateSelection = State()
    NewEndTimeSelection = State()
