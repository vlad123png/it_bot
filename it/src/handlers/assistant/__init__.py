from aiogram import Router

from . import processing_text_question, feedback, processing_voice_question

router = Router()
router.include_routers(
    processing_text_question.router,
    processing_voice_question.router,
    feedback.router
)
