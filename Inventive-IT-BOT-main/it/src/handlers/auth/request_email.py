from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.messages import EMAIL_INPUT_MESSAGE
from src.states import AuthStates

router = Router()


@router.callback_query(F.data == 'login')
async def start_login(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        db_session: AsyncSession,
):
    """Запрашивает mail пользователя"""
    await state.set_state(AuthStates.EmailInput)
    await callback_query.answer(text=EMAIL_INPUT_MESSAGE, show_alert=True)
