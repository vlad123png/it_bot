from aiogram import Router

from . import email_input, send_verification_code, verification_code_input, request_email, access_request

router = Router()
router.include_routers(
    email_input.router,
    send_verification_code.router,
    verification_code_input.router,
    request_email.router,
    access_request.router
)
