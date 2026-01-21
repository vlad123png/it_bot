from aiogram import Router

from . import new_task, cancel_task, confirm_task, send_task

router = Router()
router.include_routers(
    new_task.router,
    cancel_task.router,
    confirm_task.router,
    send_task.router
)
