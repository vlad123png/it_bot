from aiogram import types, Router
from aiogram.filters import Command

from src import messages
from src.db.models import User
from src.keyboards.admin_inline import get_admin_inline_keyboard
from src.utils import antiflood
from src.utils.admin import admin

router = Router()


@router.message(Command('admin'))
@antiflood
@admin
async def admin_panel(
        message: types.Message,
        user: User,
        *args, **kwargs
):
    """
    Обрабатывает команду /admin.
    """
    await message.delete()
    await message.answer(text=messages.ADMIN_PANEL, reply_markup=get_admin_inline_keyboard())




