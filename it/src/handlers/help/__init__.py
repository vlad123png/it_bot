from aiogram import Router

from . import help, feedback, user_agreement

router = Router()

router.include_routers(
    help.router,
    feedback.router,
    user_agreement.router
)
