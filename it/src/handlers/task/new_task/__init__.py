from aiogram import Router

from . import (
    checkbox_selection,
    choice_selection,
    date_selection,
    file_attach,
    file_upload,
    inputs,
    list_selection,
    new_task,
    optional_field_selection
)

router = Router()
router.include_routers(
    checkbox_selection.router,
    choice_selection.router,
    date_selection.router,
    file_attach.router,
    file_upload.router,
    inputs.router,
    list_selection.router,
    new_task.router,
    optional_field_selection.router
)
