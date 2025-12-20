"""
Модуль интеграции с ЮKassa для приема платежей за подписку
"""
import uuid
from typing import Optional
from yookassa import Configuration, Payment as YooPayment
from yookassa.domain.notification import WebhookNotificationEventType, WebhookNotification
from config import settings


# Инициализация ЮKassa
def init_yookassa():
    """Инициализация конфигурации ЮKassa"""
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    
    # Для тестового режима (если указан TEST в переменных)
    if hasattr(settings, 'YOOKASSA_TEST_MODE') and settings.YOOKASSA_TEST_MODE:
        Configuration.configure(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)
        print("ЮKassa: Работа в ТЕСТОВОМ режиме")


def create_payment(amount: float, description: str, user_id: int, return_url: str) -> dict:
    """
    Создание платежа в ЮKassa
    
    Args:
        amount: Сумма платежа в рублях
        description: Описание платежа
        user_id: ID пользователя Telegram
        return_url: URL для возврата после оплаты
        
    Returns:
        dict с данными платежа (id, confirmation_url, status)
    """
    try:
        init_yookassa()
        
        idempotence_key = str(uuid.uuid4())
        
        print(f"Создание платежа: amount={amount}, user_id={user_id}")
        
        payment = YooPayment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": user_id,
                "subscription": "monthly"
            }
        }, idempotence_key)
        
        print(f"Платеж создан: {payment.id}, статус: {payment.status}")
        
        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
            "status": payment.status,
            "amount": float(payment.amount.value)
        }
    except Exception as e:
        print(f"Ошибка создания платежа: {e}")
        import traceback
        traceback.print_exc()
        raise


def check_payment_status(payment_id: str) -> dict:
    """
    Проверка статуса платежа
    
    Args:
        payment_id: ID платежа в ЮKassa
        
    Returns:
        dict со статусом платежа
    """
    init_yookassa()
    
    payment = YooPayment.find_one(payment_id)
    
    return {
        "payment_id": payment.id,
        "status": payment.status,
        "paid": payment.paid,
        "amount": float(payment.amount.value),
        "created_at": payment.created_at,
        "metadata": payment.metadata
    }


def process_webhook(request_body: dict) -> Optional[dict]:
    """
    Обработка webhook от ЮKassa
    
    Args:
        request_body: Тело запроса от ЮKassa
        
    Returns:
        dict с данными о платеже или None
    """
    try:
        notification = WebhookNotification(request_body)
        payment = notification.object
        
        if notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            return {
                "event": "payment.succeeded",
                "payment_id": payment.id,
                "status": payment.status,
                "paid": payment.paid,
                "amount": float(payment.amount.value),
                "metadata": payment.metadata
            }
        elif notification.event == WebhookNotificationEventType.PAYMENT_CANCELED:
            return {
                "event": "payment.canceled",
                "payment_id": payment.id,
                "status": payment.status,
                "metadata": payment.metadata
            }
        
        return None
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return None


def get_subscription_price() -> float:
    """Получить цену месячной подписки"""
    return float(settings.SUBSCRIPTION_PRICE)
