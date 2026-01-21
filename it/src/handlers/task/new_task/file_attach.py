from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.callbacks import FilesAction, FilesCallback
from src.db.utils import save_parasite_message
from src.messages import UPLOAD_FILE_MESSAGE
from src.states import TaskStates
from src.utils import check_uploaded_size

router = Router()


@router.callback_query(
    TaskStates.Files,
    FilesCallback.filter(F.action == FilesAction.attach)
)
@check_uploaded_size
async def process_file_attach(
    callback_query: types.CallbackQuery,
    state: FSMContext,
    callback_data: FilesCallback,
    db_session: AsyncSession,
    *args, **kwargs
):
    """Обрабатывает запрос на прикрепление файлов."""
    data = await state.get_data()

    if data['task_timestamp'] == callback_data.task_timestamp:
        await state.set_state(TaskStates.FileUpload)
        await callback_query.message.edit_text(UPLOAD_FILE_MESSAGE)
        await save_parasite_message(db_session, callback_query.message.chat.id, callback_query.message.message_id)
