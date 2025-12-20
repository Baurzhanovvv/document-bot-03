"""
Планировщик задач для проверки истекающих подписок и отправки уведомлений
"""
import asyncio
from datetime import datetime
from aiogram import Bot
from app.subscription import get_expiring_subscriptions, deactivate_expired_subscriptions
from app.payment_handlers import send_subscription_expiring_notification
from config import settings


async def check_expiring_subscriptions_task(bot: Bot):
    """
    Периодическая задача для проверки истекающих подписок
    Проверяет каждые 24 часа и отправляет уведомления за 3 дня до истечения
    """
    while True:
        try:
            print(f"[{datetime.now()}] Checking expiring subscriptions...")
            
            # Получаем подписки, которые истекают через 3 дня
            expiring = await get_expiring_subscriptions(days_before=3)
            
            # Отправляем уведомления
            for sub_info in expiring:
                tg_id = sub_info["tg_id"]
                days_left = sub_info["days_left"]
                
                print(f"Sending notification to user {tg_id} (days left: {days_left})")
                await send_subscription_expiring_notification(bot, tg_id, days_left)
                
                # Небольшая задержка между отправками
                await asyncio.sleep(0.5)
            
            if expiring:
                print(f"Sent {len(expiring)} expiration notifications")
            
            # Деактивируем истекшие подписки
            deactivated = await deactivate_expired_subscriptions()
            if deactivated:
                print(f"Deactivated {deactivated} expired subscriptions")
            
        except Exception as e:
            print(f"Error in check_expiring_subscriptions_task: {e}")
        
        # Ждем 24 часа до следующей проверки
        await asyncio.sleep(86400)  # 24 часа = 86400 секунд


async def send_daily_notifications_task(bot: Bot):
    """
    Ежедневная задача для отправки уведомлений
    Запускается в определенное время (например, в 10:00 по местному времени)
    """
    while True:
        try:
            now = datetime.now()
            
            # Вычисляем время до следующих 10:00
            target_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
            if now >= target_time:
                # Если уже прошло 10:00, берем завтрашние 10:00
                from datetime import timedelta
                target_time += timedelta(days=1)
            
            # Вычисляем задержку в секундах
            delay = (target_time - now).total_seconds()
            
            print(f"Next notification check scheduled at {target_time}")
            await asyncio.sleep(delay)
            
            # Проверяем подписки
            print(f"[{datetime.now()}] Running daily subscription check...")
            
            # За 3 дня до истечения
            expiring_3days = await get_expiring_subscriptions(days_before=3)
            for sub_info in expiring_3days:
                await send_subscription_expiring_notification(
                    bot, sub_info["tg_id"], sub_info["days_left"]
                )
                await asyncio.sleep(0.5)
            
            # За 1 день до истечения (дополнительное напоминание)
            expiring_1day = await get_expiring_subscriptions(days_before=1)
            for sub_info in expiring_1day:
                await send_subscription_expiring_notification(
                    bot, sub_info["tg_id"], sub_info["days_left"]
                )
                await asyncio.sleep(0.5)
            
            # Деактивируем истекшие
            deactivated = await deactivate_expired_subscriptions()
            if deactivated:
                print(f"Deactivated {deactivated} expired subscriptions")
            
            print(f"Daily check completed. Sent {len(expiring_3days) + len(expiring_1day)} notifications")
            
        except Exception as e:
            print(f"Error in send_daily_notifications_task: {e}")
            # При ошибке ждем час и повторяем
            await asyncio.sleep(3600)


def start_scheduler(bot: Bot):
    """
    Запуск планировщика задач
    Вызывать при старте приложения
    """
    # Создаем задачи
    asyncio.create_task(send_daily_notifications_task(bot))
    print("Subscription scheduler started")
