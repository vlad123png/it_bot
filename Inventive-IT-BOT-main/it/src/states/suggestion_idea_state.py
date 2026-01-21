from aiogram.fsm.state import State, StatesGroup


class SuggestionIdea(StatesGroup):
    """
    Состояние во время ожидание получения сообщения от пользователя по нажатию на кнопку Предложить идею.

    Состояние:
    - WaitingMessage: Ожидание сообщения от пользователя.
    """
    WaitingMessage = State()
