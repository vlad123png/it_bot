from aiogram.fsm.state import StatesGroup, State


class AuthStates(StatesGroup):
    """
    Состояния в процессе аутентификации.

    Состояния:
    - EmailInput: Ввод адреса электронной почты
    - VerificationCodeInput: Ввод кода подтверждения
    """
    EmailInput = State()
    VerificationCodeInput = State()
