
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import List, Optional

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

# !!! Проверь названия модулей здесь под свой проект
from app.database.models import User  # твоя ORM-модель пользователя


from datetime import timedelta

from app.database.models import async_session, Payment, Admin
from app.database.models import User
from app.database.models import Sub, SubStatus
from sqlalchemy import select, update, delete, desc
from sqlalchemy.dialects.postgresql import insert  # <- добавь к импортам


async def set_user(tg_id: int, username: Optional[str], full_name: Optional[str]):
    async with async_session() as session:
        stmt = (
            insert(User)
            .values(
                tg_id=tg_id,
                username=username,
                full_name=full_name,
                number=None,
                location=None,
                work=None,
            )
            .on_conflict_do_update(
                index_elements=[User.tg_id],
                set_={
                    "username": username,
                    "full_name": full_name,
                },
            )
        )
        await session.execute(stmt)
        await session.commit()


async def update_user(tg_id, number, location, work):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            user.number = number
            user.location = location
            user.work = work
            await session.commit()


async def set_sub(tg_id, text):
    async with async_session() as session:
        sub = await session.scalar(select(Sub).where(Sub.user_id == tg_id, Sub.status != SubStatus.ended))
        if not sub:
            session.add(Sub(user_id=tg_id, status=SubStatus.waiting, text=text))
            await session.commit()


import io
from typing import Optional, Iterable
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.database.models import async_session, User, SearchLog, SearchResultPreview
import secrets

# лог поиска
async def log_search(
    tg_id: int,
    query_text: str,
    *,
    num_results: Optional[int] = None,
    source: Optional[str] = "bot",
    extra: Optional[dict] = None,
) -> int:
    async with async_session() as session:
        async with session.begin():
            # попробуем найти user.id
            user_id = None
            res = await session.execute(select(User.id).where(User.tg_id == tg_id))
            row = res.first()
            if row:
                user_id = row[0]
            log = SearchLog(
                user_id=user_id,
                tg_id=tg_id,
                query_text=query_text,
                num_results=num_results,
                source=source,
                extra=extra or {},
                created_at=datetime.utcnow(),
            )
            session.add(log)
            await session.flush()
            return log.id


async def create_search_preview(
    *,
    search_log_id: int,
    query_text: str,
    results: list[dict],
) -> str:
    token = secrets.token_urlsafe(16)
    payload = {
        "results": results,
        "created_at": datetime.utcnow().isoformat(),
    }

    async with async_session() as session:
        async with session.begin():
            preview = SearchResultPreview(
                search_log_id=search_log_id,
                token=token,
                query_text=query_text,
                results=payload,
            )
            session.add(preview)
    return token


async def get_search_preview(token: str) -> Optional[SearchResultPreview]:
    async with async_session() as session:
        res = await session.execute(
            select(SearchResultPreview).where(SearchResultPreview.token == token)
        )
        preview = res.scalar_one_or_none()
        return preview


# выгрузка пользователей в Excel
async def export_users_xlsx() -> io.BytesIO:
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("Установи пакет 'openpyxl' в requirements.txt")

    async with async_session() as session:
        res = await session.execute(
            select(User).options(
                joinedload(User.subs),
                joinedload(User.payments),
            )
        )
        users: list[User] = list(res.unique().scalars())  # ключевое изменение

        stats_res = await session.execute(
            select(
                SearchLog.user_id,
                func.count(SearchLog.id),
                func.max(SearchLog.created_at),
            )
            .where(SearchLog.user_id.is_not(None))
            .group_by(SearchLog.user_id)
        )
        stats_map = {row[0]: (row[1], row[2]) for row in stats_res}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Users"

    headers = [
        "id", "tg_id", "username", "full_name",
        "created_at", "number", "location", "work",
        "search_count", "subs_count", "payments_count",
        "searches_total", "last_search_at",
    ]
    ws.append(headers)

    for u in users:
        total, last_at = stats_map.get(u.id, (0, None))
        ws.append([
            u.id,
            u.tg_id,
            u.username or "",
            u.full_name or "",
            (u.created_at.isoformat() if getattr(u, "created_at", None) else ""),
            u.number or "",
            u.location or "",
            u.work or "",
            (u.search_count or 0),
            len(getattr(u, "subs", []) or []),
            len(getattr(u, "payments", []) or []),
            total,
            last_at.isoformat() if last_at else "",
        ])

    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val = str(cell.value) if cell.value is not None else ""
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 60)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


async def get_user(tg_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            return [user.tg_id, user.username, user.full_name, user.number, user.location, user.work]
        return None

async def get_last_payment(tg_id):
    async with async_session() as session:
        payment = await session.scalar(select(Payment).where(Payment.user_id == int(tg_id)).order_by(desc(Payment.created_at)).limit(1))
        if payment:
            return [payment.active, payment.created_at + timedelta(days=30)]
        return None



async def get_admin(tg_id):
    async with async_session() as session:
        admin = await session.scalar(select(Admin).where(Admin.tg_id == int(tg_id)))
        if admin:
            return [admin.tg_id, admin.login, admin.password]
        return None
    
async def set_admin(tg_id, login, password, added_by):
    async with async_session() as session:
        tg_id = int(tg_id)
        admin = await session.scalar(select(Admin).where(Admin.tg_id == int(tg_id)))
        if not admin:
            session.add(Admin(tg_id=tg_id, login=login, password=password, added_by=added_by))
            await session.commit()

async def update_admin(tg_id, login, password):
    async with async_session() as session:
        tg_id = int(tg_id)
        admin = await session.scalar(select(Admin).where(Admin.tg_id == int(tg_id)))
        if admin:
            admin.login = login
            admin.password = password
            await session.commit()


async def get_admins_tg_id():
    async with async_session() as session:
        admins = await session.scalars(select(Admin))
        return [admin.tg_id for admin in admins]


async def check_admin(tg_id, login, password):
    async with async_session() as session:
        tg_id = int(tg_id)
        admin = await session.scalar(select(Admin).where(Admin.tg_id == int(tg_id), Admin.login == login, Admin.password == password))
        if admin:
            return True
        return False
    
async def get_admins_info():
    async with async_session() as session:
        admins = await session.scalars(select(Admin))
        return [[admin.tg_id, admin.login, admin.created_at, admin.added_by] for admin in admins]



async def get_all_users_ids():
    async with async_session() as session:
        users = await session.scalars(select(User))
    return [user.tg_id for user in users]

async def remove_admin(tg_id):
    async with async_session() as session:
        tg_id = int(tg_id)
        admin = await session.scalar(select(Admin).where(Admin.tg_id == int(tg_id)))
        if admin:
            await session.delete(admin)
            await session.commit()
            return True
        return False


async def get_specializations():
    async with async_session() as session:
        # ✅ ПРАВИЛЬНО - используем distinct() в SQL запросе
        result = await session.execute(
            select(User.work)
            .where(User.work.isnot(None))
            .distinct()
            .order_by(User.work)
        )
        specializations = result.scalars().all()
        return specializations

async def find_users_by_specialization(specialization):
    async with async_session() as session:
        users = await session.scalars(select(User).where(User.work == specialization))
        return [user.tg_id for user in users]
        