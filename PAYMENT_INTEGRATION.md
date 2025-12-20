# Модуль оплаты через ЮKassa

## Описание

Модуль реализует систему подписок с оплатой через ЮKassa для Telegram-бота поиска по документам.

## Возможности

1. **Бесплатные попытки** - каждый новый пользователь получает 3 бесплатных поиска
2. **Подписка** - месячная подписка с неограниченным доступом
3. **Автоматические уведомления** - за 3 дня до окончания подписки пользователь получает напоминание
4. **Webhook интеграция** - автоматическое подтверждение платежей

## Структура файлов

```
app/
├── yookassa_payment.py      # Интеграция с API ЮKassa
├── subscription.py           # Управление подписками
├── payment_handlers.py       # Обработчики команд бота для платежей
├── payment_webhook.py        # Webhook для приема уведомлений от ЮKassa
└── scheduler.py              # Планировщик уведомлений
```

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install yookassa apscheduler
```

Или используйте обновленный `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 2. Регистрация в ЮKassa

1. Зарегистрируйтесь на [yookassa.ru](https://yookassa.ru)
2. Получите Shop ID и Secret Key в личном кабинете
3. Настройте webhook для уведомлений о платежах:
   - URL: `https://your-domain.com/webhook/yookassa`
   - События: `payment.succeeded`, `payment.canceled`

### 3. Настройка переменных окружения

Добавьте в `.env` файл:

```env
# ЮKassa
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Цена подписки (в рублях)
SUBSCRIPTION_PRICE=299.0

# URL вашего веб-приложения
WEBAPP_URL=https://your-domain.com

# (Необязательно) Прямой URL страницы успешной оплаты, если отличается от WEBAPP_URL
# PAYMENT_SUCCESS_URL=https://your-domain.com/payment/success
```

### 4. Обновление базы данных

Модуль использует существующую таблицу `payments` из вашей базы данных. Убедитесь, что миграции применены:

```bash
python -c "from app.database.models import async_main; import asyncio; asyncio.run(async_main())"
```

## Использование

### Команды бота

- `/subscription` - Информация о подписке
- `/status` - Проверка текущего статуса доступа

### Процесс оплаты

1. Пользователь пытается выполнить поиск после исчерпания бесплатных попыток
2. Бот предлагает оформить подписку
3. Пользователь нажимает "Оформить подписку"
4. Создается платеж в ЮKassa, пользователь переходит на страницу оплаты
5. После успешной оплаты ЮKassa отправляет webhook
6. Бот активирует подписку на 30 дней
7. Пользователь получает уведомление об активации

### Уведомления

Система автоматически отправляет уведомления:

- **За 3 дня до окончания** - первое напоминание
- **За 1 день до окончания** - финальное напоминание
- **При истечении** - подписка автоматически деактивируется

## API

### Проверка доступа пользователя

```python
from app.subscription import check_user_access

access_info = await check_user_access(tg_id)

# Возвращает:
# {
#     "has_access": bool,
#     "access_type": "free" | "subscription" | "expired",
#     "searches_left": int,
#     "subscription_end": datetime | None
# }
```

### Создание платежа

```python
from app.yookassa_payment import create_payment

payment_data = create_payment(
    amount=299.0,
    description="Подписка на месяц",
    user_id=123456789,
    return_url="https://your-domain.com/payment/success"
)

# Возвращает:
# {
#     "payment_id": str,
#     "confirmation_url": str,
#     "status": str,
#     "amount": float
# }
```

### Активация подписки

```python
from app.subscription import create_subscription

success = await create_subscription(
    tg_id=123456789,
    payment_id="payment_id_from_yookassa"
)
```

## Тестирование

### Тестовые карты ЮKassa

Для тестирования используйте тестовые карты:

- **Успешный платеж**: `5555 5555 5555 4477`
- **Отклоненный платеж**: `5555 5555 5555 5599`
- CVC: любые 3 цифры
- Срок действия: любая будущая дата

### Проверка webhook локально

Для тестирования webhook локально используйте ngrok:

```bash
ngrok http 8000
```

Затем укажите ngrok URL в настройках ЮKassa:
```
https://your-ngrok-url.ngrok.io/webhook/yookassa
```

## Безопасность

1. **Никогда не храните** Secret Key в коде - только в переменных окружения
2. **Валидация webhook** - модуль автоматически проверяет подпись от ЮKassa
3. **HTTPS обязателен** - ЮKassa требует HTTPS для webhook в продакшене

## Мониторинг

Логи планировщика:

```bash
# Просмотр логов проверки подписок
tail -f logs/scheduler.log
```

Основные события в логах:
- Проверка истекающих подписок (ежедневно в 10:00)
- Отправка уведомлений пользователям
- Деактивация истекших подписок

## Troubleshooting

### Webhook не приходит

1. Проверьте настройки webhook в ЮKassa
2. Убедитесь что URL доступен извне
3. Проверьте логи сервера на ошибки

### Подписка не активируется

1. Проверьте логи webhook в `/webhook/yookassa`
2. Убедитесь что metadata содержит правильный user_id
3. Проверьте подключение к базе данных

### Уведомления не отправляются

1. Проверьте что планировщик запущен
2. Проверьте логи scheduler.py
3. Убедитесь что бот имеет доступ к отправке сообщений

## Расширение функционала

### Добавление других тарифов

Отредактируйте `app/subscription.py` и добавьте логику для разных тарифов:

```python
SUBSCRIPTION_PLANS = {
    "monthly": {"days": 30, "price": 299},
    "yearly": {"days": 365, "price": 2990}
}
```

### Интеграция с другими платежными системами

Создайте адаптер по аналогии с `yookassa_payment.py` для других систем (Stripe, PayPal и т.д.)

## Дополнительные ресурсы

- [Документация ЮKassa API](https://yookassa.ru/developers/api)
- [Документация Python SDK](https://github.com/yoomoney/yookassa-sdk-python)
- [Тестовая среда ЮKassa](https://yookassa.ru/developers/using-api/testing)

## Поддержка

При возникновении проблем:
1. Проверьте логи приложения
2. Изучите документацию ЮKassa
3. Создайте issue в репозитории проекта
