import logging

from aiogram import Router, F, types

from src.utils import send_file_with_cache

router = Router()


@router.callback_query(F.data == 'user_agreement')
async def help_request(
        callback: types.CallbackQuery,
):
    """
    Обрабатывает нажатие инлайн кнопки 'Соглашение' в меню регистрации.
    """
    await send_file_with_cache(callback.message, 'agreement.pdf')
    await callback.answer()
    logging.info('Отправлено пользовательское соглашение телеграм пользователю %s', callback.from_user.id)
