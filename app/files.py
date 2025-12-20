# app/files.py (фрагмент)
from aiogram import Router, F
from aiogram.types import Message
from opensearch_dir.opensearch_service import OpenSearchService

router = Router()

@router.message(F.text & ~F.via_bot)
async def do_search(message: Message):
    q = (message.text or "").strip()
    if not q:
        return

    try:
        svc = OpenSearchService()
        results = svc.search(q, limit=5)
    except Exception as e:
        await message.answer(f"Поиск временно недоступен: {e}")
        return

    if not results:
        await message.answer("Ничего не нашёл.")
        return

    lines = []
    for r in results:
        fn = r.get("filename") or "без имени"
        p = r.get("path") or ""
        snip = r.get("snippet") or ""
        lines.append(f"📄 <b>{fn}</b>\n{p}\n{snip}\n")
    await message.answer("\n".join(lines), parse_mode="HTML")
