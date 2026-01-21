from aiogram.fsm.state import State, StatesGroup


class RequestAccess(StatesGroup):
    """
    Состояние во время ожидание получения сообщения о запросе доступа к боту.

    Состояние:
    - WaitingRequest: Ввод текстового сообщения с запросом и email.
    """
    WaitingRequest = State()
