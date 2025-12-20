"""
Обработчики платежей и подписок для Telegram бота
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.subscription import (
    check_user_access,
    get_active_subscription,
    create_subscription
)
from app.yookassa_payment import create_payment, get_subscription_price
from app.database.requests import get_user
from urllib.parse import urljoin

from config import settings

payment_router = Router()


@payment_router.message(Command("subscription"))
async def cmd_subscription(message: Message):
    """Команда для просмотра информации о подписке"""
    tg_id = message.from_user.id
    
    access_info = await check_user_access(tg_id)
    
    if access_info["access_type"] == "subscription":
        end_date = access_info["subscription_end"]
        days_left = (end_date - end_date.now()).days
        
        text = (
            "✅ <b>У вас активная подписка</b>\n\n"
            f"📅 Действует до: {end_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Осталось дней: {days_left}\n\n"
            "Вы можете пользоваться неограниченным поиском по документам!"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="buy_subscription")]
        ])
        
    elif access_info["access_type"] == "free":
        searches_left = access_info["searches_left"]
        price = get_subscription_price()
        
        text = (
            "🆓 <b>Бесплатный доступ</b>\n\n"
            f"🔍 Осталось бесплатных поисков: {searches_left}\n\n"
            f"Оформите подписку за {price:.0f}₽/месяц для безлимитного доступа!"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
        ])
        
    else:
        price = get_subscription_price()
        
        text = (
            "❌ <b>Бесплатные попытки закончились</b>\n\n"
            f"Для продолжения работы оформите подписку за {price:.0f}₽/месяц\n\n"
            "🎁 Преимущества подписки:\n"
            "• Неограниченный поиск по документам\n"
            "• Доступ ко всем материалам\n"
            "• Приоритетная поддержка"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
        ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@payment_router.callback_query(F.data == "buy_subscription")
async def buy_subscription_callback(callback: CallbackQuery):
    """Обработчик покупки подписки"""
    await callback.answer()
    
    tg_id = callback.from_user.id
    price = get_subscription_price()
    
    # Формируем URL для возврата после оплаты
    base_url = settings.PAYMENT_SUCCESS_URL or settings.WEBAPP_URL
    if not base_url:
        raise RuntimeError("PAYMENT_SUCCESS_URL или WEBAPP_URL не настроены")
    if base_url.startswith("http://"):
        raise RuntimeError(
            "YooKassa требует HTTPS return_url. Укажите PAYMENT_SUCCESS_URL с https-ссылкой."
        )
    return_url = urljoin(base_url.rstrip("/") + "/", "payment/success")
    
    # Создаем платеж в ЮKassa
    try:
        payment_data = create_payment(
            amount=price,
            description=f"Подписка на месяц для пользователя {tg_id}",
            user_id=tg_id,
            return_url=return_url
        )
        
        text = (
            "💳 <b>Оплата подписки</b>\n\n"
            f"Сумма: {price:.0f}₽\n"
            f"Период: 30 дней\n\n"
            "Нажмите кнопку ниже для перехода к оплате:"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Оплатить", url=payment_data["confirmation_url"])],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        
    except Exception as e:
        error_message = str(e)
        print(f"Ошибка при создании платежа для пользователя {tg_id}: {error_message}")
        
        text = (
            "❌ Произошла ошибка при создании платежа.\n\n"
            "Возможные причины:\n"
            "• Неверные ключи ЮKassa\n"
            "• Проблемы с подключением к API\n"
            "• Магазин не активирован\n\n"
            "Попробуйте позже или обратитесь в поддержку."
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")


@payment_router.callback_query(F.data == "cancel_payment")
async def cancel_payment_callback(callback: CallbackQuery):
    """Отмена платежа"""
    await callback.answer()
    await callback.message.edit_text(
        "Оплата отменена. Используйте /subscription для оформления подписки.",
        parse_mode="HTML"
    )


@payment_router.message(Command("status"))
async def cmd_payment_status(message: Message):
    """Проверка статуса доступа"""
    tg_id = message.from_user.id
    access_info = await check_user_access(tg_id)
    
    if access_info["has_access"]:
        if access_info["access_type"] == "subscription":
            text = (
                "✅ <b>Статус доступа: Активная подписка</b>\n\n"
                f"Действует до: {access_info['subscription_end'].strftime('%d.%m.%Y')}"
            )
        else:
            text = (
                "✅ <b>Статус доступа: Бесплатный</b>\n\n"
                f"Осталось поисков: {access_info['searches_left']}"
            )
    else:
        text = "❌ <b>Доступ заблокирован</b>\n\nОформите подписку: /subscription"
    
    await message.answer(text, parse_mode="HTML")


async def send_subscription_expiring_notification(bot, tg_id: int, days_left: int):
    """
    Отправить уведомление о скором истечении подписки
    
    Args:
        bot: Экземпляр бота
        tg_id: ID пользователя
        days_left: Дней до истечения
    """
    price = get_subscription_price()
    
    text = (
        f"⚠️ <b>Ваша подписка истекает через {days_left} дн.</b>\n\n"
        f"Продлите подписку, чтобы продолжить пользоваться сервисом!\n\n"
        f"Стоимость продления: {price:.0f}₽/месяц"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="buy_subscription")]
    ])
    
    try:
        await bot.send_message(tg_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        print(f"Failed to send notification to {tg_id}: {e}")
