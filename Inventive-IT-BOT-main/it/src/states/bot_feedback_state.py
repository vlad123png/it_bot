from aiogram.fsm.state import State, StatesGroup


class FeedbackBot(StatesGroup):
    """
    Состояние во время ожидание получения сообщения от пользователя по нажатию на кнопку Написать фидбэк.

    Состояние:
    - WaitingMessage: Ожидание сообщения от пользователя.
    """
    WaitingMessage = State()
