from aiogram import types, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src import messages
from src.api_client import APIClient
from src.config.settings import settings
from src.db.models import User
from src.db.utils import save_parasite_message
from src.keyboards import get_main_inline_keyboard
from src.keyboards.inline import get_start_inline_keyboard, get_timezone_inline_keyboard
from src.states.bot_feedback_state import FeedbackBot
from src.utils import antiflood, api, check_auth, cleanup, active_user, send_file_with_cache
from .assistant.utils import delete_parasite_messages
from .service.qr_code import process_qr_code
from ..states import AuthStates

router = Router()


@router.message(Command('start'))
@antiflood
async def start(
        message: types.Message,
        command: CommandObject,
        state: FSMContext,
        api_client: APIClient,
        user: User,
        *args, **kwargs
):
    """
    Обрабатывает команду /start.

    Если пользователя не существует, или время действия аутентификации истекло,
    инициируется процесс ввода адреса электронной почты для аутентификации.
    Если пользователь существует и время действия аутентификации не истекло,
    проверяется статус пользователя в Inventive. Если пользователя не
    существует, или он является архивным, инициируетcя процесс ввода адреса
    электронной почты для аутентификации.
    """
    await cleanup(state)

    if command.args:
        await state.update_data(qr_code=command.args)

    if (
            not user
            or not user.auth_logs
            or not check_auth(user.auth_logs[0].auth_time, settings.AUTH_DURATION)
    ):
        await message.answer(text=messages.START_MESSAGE, reply_markup=get_start_inline_keyboard())
    else:
        inventive_user = await api.get_user_by_id(
            api_client,
            user.inventive_id
        )
        if not inventive_user or inventive_user['IsArchive']:
            await message.answer(text=messages.START_MESSAGE, reply_markup=get_start_inline_keyboard())
        else:
            data = await state.get_data()
            if data.get('qr_code'):
                await process_qr_code(message, state, api_client)
            else:
                await message.answer(
                    text=messages.WELCOME_MESSAGE.format(inventive_user['Name']),
                    reply_markup=await get_main_inline_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            await state.clear()
    await message.delete()


@router.message(Command('cancel'))
@antiflood
@active_user
async def cancel(
        message: types.Message,
        state: FSMContext,
        api_client: APIClient,
        user: User,
        db_session: AsyncSession,
        *args, **kwargs
):
    """
    Обрабатывает команду /cancel.

    Отменяет текущую операцию пользователя.
    """
    await cleanup(state)
    await delete_parasite_messages(message.bot, db_session, message.chat.id)

    inventive_user = await api.get_user_by_id(
        api_client,
        user.inventive_id
    )
    await message.answer(
        text=messages.WELCOME_MESSAGE.format(inventive_user['Name']),
        reply_markup=await get_main_inline_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    await message.delete()


@router.message(Command('about'))
@antiflood
async def about(
        message: types.Message,
        db_session: AsyncSession,
):
    """
    Обрабатывает команду /about

    Отправляет сообщение с описанием бота.
    """
    about_message = await message.answer(text=messages.ABOUT)
    await message.delete()
    await save_parasite_message(db_session, message.chat.id, about_message.message_id)


@router.message(Command('help'))
@antiflood
async def help_command(
        message: types.Message,
):
    """
    Обрабатывает команду /help

    Отправляет инструкцию по использованию бота.
    """
    await send_file_with_cache(message, 'Руководство_пользователя.pdf')
    await message.delete()


@router.message(Command('agreement'))
@antiflood
async def consent(
        message: types.Message,
):
    """
    Обрабатывает еоманду /agreement

    Отправляет пользовательское соглашение.
    """
    await send_file_with_cache(message, 'agreement.pdf')
    await message.delete()


@router.message(Command('timezone'))
@antiflood
@active_user
async def timezone(
        message: types.Message,
        user: User,
        *args, **kwargs
):
    """Отправляет пользователю инлайн клавиатуру с выбором часового пояса"""
    await message.delete()
    await message.answer(
        text=messages.TIMEZONE_MESSAGE.format(f'UTC+{user.timezone}'),
        reply_markup=get_timezone_inline_keyboard()
    )


@router.message(Command('feedback'))
@antiflood
async def feedback(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession,
):
    """
    Обрабатывает команду /feedback
    """
    await state.set_state(FeedbackBot.WaitingMessage)
    answer_message = await message.answer(messages.FEEDBACK_BOT_REQUEST, show_alert=True)
    await save_parasite_message(db_session, message.chat.id, answer_message.message_id)
    await message.delete()


@router.message(Command('switch_user'))
@antiflood
async def switch_user(
        message: types.Message,
        state: FSMContext,
):
    """
    Обрабатывает команду /switch_user
    """
    await cleanup(state)
    await state.set_state(AuthStates.EmailInput)
    await message.answer(messages.EMAIL_INPUT_MESSAGE)