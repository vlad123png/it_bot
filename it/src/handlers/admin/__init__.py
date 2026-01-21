from aiogram import Router

from . import (
    admin_panel,
    change_user_role,
    change_settings,
    broadcast_message,
    change_prompts,
    change_broadcast_message,
    statistics,
    update_knowledge_bases,
    users_sync
)
from .survey import create_survey, survey_result, choice, change_broadcast_survey

router = Router()

router.include_routers(
    admin_panel.router,
    change_user_role.router,
    change_settings.router,
    create_survey.router,  # Важно, чтобы данный роутер был перед broadcast_message.router
    survey_result.router,  # Важно, чтобы данный роутер был перед broadcast_message.router
    change_broadcast_message.router,  # Важно, чтобы данный роутер был перед broadcast_message.router
    change_broadcast_survey.router,
    broadcast_message.router,
    change_prompts.router,
    choice.router,
    statistics.router,
    update_knowledge_bases.router,
    users_sync.router,
)
