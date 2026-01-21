import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.api_client import APIClient
from src.backend_api.factory import get_backend_api
from src.callbacks import AdminCallback, AdminAction
from src.db.models import User
from src.db.users import get_all_users, update_user_backend_id
from src.utils import active_user, admin
from src.utils import api
from src.utils.users import match_user

router = Router()

BATCH_SIZE = 50

@router.callback_query(AdminCallback.filter(F.action == AdminAction.users_sync))
@active_user
@admin
async def get_google_sheet_url_for_testing(
        callback_query: CallbackQuery,
        state: FSMContext,
        user: User,
        db_session: AsyncSession,
        api_client: APIClient,
        *args, **kwargs
):
    await callback_query.answer("Начинаю синхронизацию…")

    backend_service = get_backend_api()

    db_users: list[User] = await get_all_users(db_session)

    processed = 0
    updated_in_batch = 0
    errors = 0

    for db_user in db_users:
        try:
            inventive_user = await api.get_user_by_id(api_client, db_user.inventive_id)
            if not inventive_user:
                continue

            backend_users = await backend_service.get_users_by_email(
                db_user.inventive_email
            )
            if not backend_users:
                continue

            #  ФИО в одной строке «Иванов Иван Иванович»
            fio = inventive_user.get("Name")
            if not fio:
                continue

            candidates = [
                bu
                for bu in backend_users
                if match_user(fio, bu)
            ]

            if len(candidates) == 1:
                await update_user_backend_id(
                    db_session, db_user.id, candidates[0].id
                )
                updated_in_batch += 1

        except Exception as exc:
            errors += 1
            logging.exception(
                "Failed to sync user_id=%s inventive_id=%s: %s",
                db_user.id,
                db_user.inventive_id,
                exc,
            )

        processed += 1

        if processed % BATCH_SIZE == 0:
            await db_session.commit()

    # Коммит «хвоста»
    await db_session.commit()

    await callback_query.message.answer(
        f"Синхронизация завершена. Обработано: {processed}, обновлено: {updated_in_batch}, ошибок: {errors}"
    )