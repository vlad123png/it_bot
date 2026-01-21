from aiogram.fsm.state import StatesGroup, State


class FeedbackStates(StatesGroup):
    """
    Состояние во время ожидания фитбэка от пользователя.

    Состояния:
    - WaitingFeedback: Ввод текстового сообщения
    """
    WaitingFeedback = State()
