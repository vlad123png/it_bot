import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.callbacks import NewTaskCallback, TaskAction, TaskCallback
from src.states import AuthStates, TaskStates
from src.states.admin import AdminState
from src.states.bot_feedback_state import FeedbackBot
from src.states.feedback_states import FeedbackStates
from src.states.request_access_state import RequestAccess

logger = logging.getLogger('user_activity')


class MiddlewareLogger(BaseMiddleware):
    """
    Middleware для логирования действий пользователей.
    """

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        if event.message:
            id = event.message.from_user.id
        elif event.callback_query:
            id = event.callback_query.from_user.id
        else:
            raise RuntimeError(
                'MiddlewareLogger: неожиданный тип события.'
            )

        state = await data['state'].get_state()

        if event.message:
            if (
                    event.message.content_type == 'text'
                    and event.message.text.startswith('/')
            ):
                logger.info(f'Пользователь id={id} отправил команду: {event.message.text}')
            elif event.message.content_type == 'voice':
                logger.info(f'Пользователь id={id} отправил голосовое сообщение id={event.message.voice.file_id}.')
            else:
                if event.message.content_type == 'text':
                    text = event.message.text
                else:
                    text = f'<{event.message.content_type}>'
                logger.info(
                    f'Пользователь id={id} отправил сообщение: {text}'
                )


        elif event.callback_query:
            callback_data = event.callback_query.data
            if (
                    state == AuthStates.VerificationCodeInput
                    and callback_data == 'resend-verification-code'
            ):
                logger.info(
                    f'Пользователь id={id} повторно запросил код подтверждения'
                )
            elif callback_data == 'show-services':
                logger.info(f'Пользователь id={id} запросил меню сервисов')
            elif callback_data.startswith('new-task'):
                cb = NewTaskCallback.unpack(callback_data)
                logger.info(
                    f'Пользователь id={id} запросил шаблон новой заявки для '
                    f'сервиса id={cb.service_id} и '
                    f'типа заявки id={cb.task_type_id}'
                )
            elif (
                    state == TaskStates.TaskConfirmation
                    and callback_data.startswith('task')
            ):
                cb = TaskCallback.unpack(callback_data)
                if cb.action == TaskAction.send:
                    logger.info(
                        f'Пользователь id={id} отправил текущую заявку'
                    )
                elif cb.action == TaskAction.cancel:
                    logger.info(f'Пользователь id={id} отменил текущую заявку')
                else:
                    raise RuntimeError(
                        f'MiddlewareLogger: неожиданное событие: {cb.action}'
                    )
            elif callback_data.startswith('parametr'):
                logger.info(f'Администратор id={id} пытается изменить параметр бота: {callback_data}')

        result = await handler(event, data)

        state = await data['state'].get_state()

        match state:
            case AuthStates.EmailInput:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние "Ввод E-mail"'
                )

            case AuthStates.VerificationCodeInput:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние '
                    '"Ввод кода подтверждения"'
                )
            case TaskStates.Files:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние '
                    '"Прикрепление файлов"'
                )
            case TaskStates.FileUpload:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние '
                    '"Загрузка файла"'
                )
            case TaskStates.TaskConfirmation:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние '
                    '"Подтверждение заявки"'
                )
            case AdminState.MessageFromBroadcastInput:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние'
                    '"Рассылка сообщения пользователям бота"'
                )
            case AdminState.EmailInput:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние'
                    '"Предоставление прав администратора"'
                )
            case AdminState.MessageFromBroadcastInput:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние'
                    '"Удаление прав администратора"'
                )
            case FeedbackStates.WaitingFeedback:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние'
                    '"Отправка отзыва об ответе ИИ"'
                )
            case FeedbackBot.WaitingMessage:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние'
                    '"Отправка отзыва о боте"'
                )
            case RequestAccess.WaitingRequest:
                logger.info(
                    f'Пользователь id={id} перешёл в состояние'
                    '"Запрос доступа к боту"'
                )

        return result
