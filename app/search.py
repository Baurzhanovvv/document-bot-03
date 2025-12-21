import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.database.requests import create_search_preview, log_search
from app.subscription import check_user_access, decrease_search_count
from config import settings
from opensearch_dir.opensearch_service import OpenSearchService


async def handle_search_query(message: Message, query: str) -> None:
    access_info = await check_user_access(message.from_user.id)
    if not access_info["has_access"]:
        from app.yookassa_payment import get_subscription_price

        price = get_subscription_price()
        text = "❌ Доступ закончился. Оформите подписку для продолжения работы."
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
            ]
        )
        await message.answer(text, reply_markup=kb)
        return

    svc = OpenSearchService()
    results = svc.search(query=query, size=settings.PAGE_SIZE)

    log_id = await log_search(
        tg_id=message.from_user.id,
        query_text=query,
        num_results=len(results),
        source="bot",
    )

    if access_info["access_type"] == "free":
        remaining = await decrease_search_count(message.from_user.id)
        if remaining == 0:
            from app.yookassa_payment import get_subscription_price

            price = get_subscription_price()
            await message.answer(
                f"⚠️ Это была ваша последняя бесплатная попытка!\n\n"
                f"Оформите подписку за {price:.0f}₽/мес для безлимитного доступа.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
                    ]
                ),
            )

    total = len(results)
    preview_token = await create_search_preview(
        search_log_id=log_id,
        query_text=query,
        results=results,
    )

    preview_url = settings.WEBAPP_URL.rstrip("/") + f"/search/{preview_token}"
    preview_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📑 Открыть результаты", web_app=WebAppInfo(url=preview_url))]
        ]
    )

    display_query = html.escape(query)
    summary_line = f"Найдено документов: {total}" if total else "Совпадений не найдено"
    response_text = (
        "<b>🔎 Результаты готовы</b>\n"
        f"Запрос: <b>{display_query}</b>\n"
        f"{summary_line}\n"
        "Откройте веб-приложение, чтобы посмотреть подробности и скачать файлы."
    )

    await message.answer(
        response_text,
        parse_mode="HTML",
        reply_markup=preview_kb,
        disable_web_page_preview=True,
    )
