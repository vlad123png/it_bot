from aiogram import Router

from . import service_selection, show_services

router = Router()
router.include_routers(service_selection.router, show_services.router)
