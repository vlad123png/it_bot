import logging

from aiogram import Router, types, F

from src.backend_api import BackendAPI
from src.backend_api.enums import Index
from src.callbacks import UpdateKnowledgeBasesCallback, TypeSettingsCallback, TypeSettingsAction
from src.db.models import User
from src.keyboards.admin_inline import create_update_knowledge_bases_inline_keyboard
from src.utils import active_user, admin

router = Router()
logger = logging.getLogger('user_activity')


@router.callback_query(TypeSettingsCallback.filter(F.action == TypeSettingsAction.update_kwn))  # noqa
@active_user
@admin
async def update_knowledge_bases(
        callback_query: types.CallbackQuery,
        user: User,
        *args, **kwargs
):
    """ Выводит клавиатуру для выбора БЗ которую нужно обновить из источников. """
    await callback_query.message.edit_reply_markup(reply_markup=create_update_knowledge_bases_inline_keyboard())


@router.callback_query(UpdateKnowledgeBasesCallback.filter())
@active_user
@admin
async def update_knowledge_base(
        callback_query: types.CallbackQuery,
        callback_data: UpdateKnowledgeBasesCallback,
        backend_service: BackendAPI,
        user: User,
        *args, **kwargs
):
    """ Обновляет выбранную БЗ из источника. """
    await callback_query.answer(text=f'Обновляю БЗ {callback_data.action}. Пожалуйста, ожидай завершения!',
                                show_alert=True)

    if callback_data.action == 'all':
        for index_name in Index:
            await backend_service.recreate_index(index_name)
        await callback_query.message.answer(text='Все БЗ обновлены!')
        logger.info('Ручное обновление ВСЕХ БЗ пользователем %s', user.id)

    else:
        await backend_service.recreate_index(Index(callback_data.action))
        await callback_query.message.answer(text=f'Обновление БЗ ({callback_data.action}) завершено!', show_alert=True)
        logger.info('Ручное обновление БЗ %s пользователем %s', callback_data.action, user.id)
