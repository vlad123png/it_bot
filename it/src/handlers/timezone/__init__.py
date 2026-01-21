from aiogram import Router

from . import timezone

router = Router()
router.include_routers(
    timezone.router
)
