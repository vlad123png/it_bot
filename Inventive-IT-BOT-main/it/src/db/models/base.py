from datetime import datetime, UTC

import sqlalchemy as sa
from sqlalchemy import func, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Базовый класс в SQLAlchemy
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=sa.text("TIMEZONE('utc', CURRENT_TIMESTAMP)"),
        onupdate=func.now(),
    )
