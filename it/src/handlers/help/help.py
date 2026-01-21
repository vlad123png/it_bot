from aiogram import Router, F, types

from src.utils import send_file_with_cache

router = Router()


@router.callback_query(F.data == 'help')
async def help_request(
        callback: types.CallbackQuery,
):
    """
    Обрабатывает нажатие инлайн кнопки 'помощь' в главном меню.
    """
    await callback.answer()
    await send_file_with_cache(callback.message, 'Руководство_пользователя.pdf')
