# app/database/models.py
from __future__ import annotations

from enum import Enum as PyEnum
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import JSON
from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    func,
    text,
    Enum as SAEnum,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property

# Берём URL из config (где уже есть алиасы), иначе из окружения
try:
    from config import DB_URL  # alias, который мы добавили ранее в config.py
except Exception:
    import os
    DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./dev.db")


# ---------- SQLAlchemy Base / Engine / Session ----------

class Base(DeclarativeBase):
    pass


engine: AsyncEngine = create_async_engine(DB_URL, echo=False, future=True)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


# ---------- Enums ----------

class SubStatus(PyEnum):
    waiting = "waiting"
    active = "active"
    ended = "ended"


# ---------- Models ----------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    work: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    search_count: Mapped[Optional[int]] = mapped_column(Integer, default=3)

    subs: Mapped[List["Sub"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Sub(Base):
    __tablename__ = "subs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id"))
    text: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ВАЖНО: enum через SAEnum (а не сам Python Enum в mapped_column)
    status: Mapped[SubStatus] = mapped_column(
        SAEnum(SubStatus, name="sub_status", native_enum=True),
        default=SubStatus.waiting,
        nullable=False,
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subs")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_id"))

    # Когда создан платёж: даём server_default=now() чтобы и на стороне БД корректно проставлялось
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # НЕ вычисляемая колонка. Просто флаг в базе (по умолчанию True).
    # «Активен 30 дней» считаем через hybrid_property ниже.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="payments")

    @hybrid_property
    def is_active(self) -> bool:
        """Активность платежа: 30 дней от момента создания (Python-уровень)."""
        created = self.created_at or datetime.now(timezone.utc)
        return created + timedelta(days=30) > datetime.now(timezone.utc)

    @is_active.expression
    def is_active(cls):
        """SQL-эквивалент для фильтрации в запросах: (created_at + interval '30 days') > now()."""
        return (cls.created_at + text("interval '30 days'")) > func.now()


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    login: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=func.now())
    added_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


class SearchLog(Base):
    __tablename__ = "search_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # на случай, если user ещё не создан
    query_text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    num_results: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)  # bot / web / api
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship("User", backref="search_logs")


class SearchResultPreview(Base):
    __tablename__ = "search_result_previews"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_log_id: Mapped[int] = mapped_column(ForeignKey("search_logs.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(String, nullable=False)
    results: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    search_log: Mapped["SearchLog"] = relationship("SearchLog", backref="preview", uselist=False)

# ---------- DB init helpers ----------

async def init_models(drop_existing: bool = False) -> None:
    """
    Инициализация схемы:
    - при drop_existing=True дропает все таблицы (DEV-режим), затем создаёт заново;
    - если False — просто создаёт недостающие (create_all).
    """
    async with engine.begin() as conn:
        if drop_existing:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


# Для совместимости с тем, как ты вызывал ранее (run.py: await async_main())
async def async_main(drop_existing: bool = False) -> None:
    await init_models(drop_existing=drop_existing)
