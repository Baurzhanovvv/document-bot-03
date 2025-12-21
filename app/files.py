# app/files.py (фрагмент)
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message

from app.search import handle_search_query

router = Router()

SKIP_TEXTS = {
    "Поиск по документам",
    "Профиль",
    "Поддержка",
    "Назад",
    "Документы",
    "Администраторы",
    "Рассылки",
    "Пользователи",
    "Добавить администратора",
    "Удалить администратора",
    "Изменить логин и пароль",
    "Нет фото",
}


@router.message(StateFilter(None), F.text & ~F.via_bot)
async def do_search(message: Message):
    q = (message.text or "").strip()
    if not q or q.startswith("/") or q in SKIP_TEXTS:
        return

    await handle_search_query(message, q)
