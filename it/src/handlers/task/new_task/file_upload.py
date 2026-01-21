from aiogram import F, Bot, types, Router
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import FilesAction, FilesCallback
from src.db.utils import save_parasite_messages
from src.handlers.assistant.utils import delete_parasite_messages
from src.messages import ATTACH_MORE_FILES_MESSAGE
from src.states import TaskStates
from src.utils import download_and_save_file, check_file_size

router = Router()


@router.message(TaskStates.FileUpload, F.document | F.photo | F.video)
@check_file_size
async def process_file_upload(
    message: types.Message,
    state: FSMContext,
    bot: Bot,
    db_session: AsyncSession,
    media_group: list[types.Message] = None,
):
  """Обрабатывает загрузку файла."""
  messages = media_group or [message]
  data = await state.get_data()

  for message in messages:
    file_path = await download_and_save_file(message, bot)
    files = data.setdefault('files', {})
    files[file_path.name] = str(file_path)

  builder = InlineKeyboardBuilder()
  builder.button(
    text='✅ Да',
    callback_data=FilesCallback(
      action=FilesAction.attach,
      task_timestamp=data['task_timestamp']
    )
  )
  builder.button(
    text='❌ Нет',
    callback_data=FilesCallback(
      action=FilesAction.proceed,
      task_timestamp=data['task_timestamp']
    )
  )

  await state.set_data(data)
  await state.set_state(TaskStates.Files)

  choice_message = await message.answer(
    text=ATTACH_MORE_FILES_MESSAGE,
    reply_markup=builder.as_markup()
  )

  parasite_messages = [msg.message_id for msg in messages]
  parasite_messages.append(choice_message.message_id)
  await delete_parasite_messages(bot, db_session, message.chat.id)
  await save_parasite_messages(db_session, message.chat.id, parasite_messages)
