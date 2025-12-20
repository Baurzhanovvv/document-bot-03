# Быстрый старт: Интеграция платежей ЮKassa

## Что добавлено в проект

### Новые файлы:
1. `app/yookassa_payment.py` - Интеграция с API ЮKassa
2. `app/subscription.py` - Управление подписками
3. `app/payment_handlers.py` - Команды бота для платежей
4. `app/payment_webhook.py` - Webhook от ЮKassa
5. `app/scheduler.py` - Автоматические уведомления
6. `.env.example` - Пример конфигурации
7. `PAYMENT_INTEGRATION.md` - Подробная документация

### Измененные файлы:
1. `app/user.py` - Добавлена проверка доступа при поиске
2. `run.py` - Подключен роутер платежей и планировщик
3. `config.py` - Добавлены настройки ЮKassa

## Пошаговое внедрение

### Шаг 1: Установите зависимости

```bash
pip install yookassa==3.0.0 apscheduler==3.10.4
```

Или установите все из обновленного requirements.txt:
```bash
pip install -r requirements_updated.txt
```

### Шаг 2: Настройте ЮKassa

1. Зарегистрируйтесь на https://yookassa.ru
2. Получите:
   - Shop ID
   - Secret Key
3. Добавьте в `.env`:

```env
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_secret_key
SUBSCRIPTION_PRICE=299.0
```

### Шаг 3: Настройте webhook

В личном кабинете ЮKassa:
- URL: `https://ваш-домен.com/webhook/yookassa`
- HTTP метод: POST
- События: `payment.succeeded`, `payment.canceled`

**Для локальной разработки:** используйте ngrok
```bash
ngrok http 8000
# Укажите ngrok URL в настройках webhook
```

### Шаг 4: Обновите базу данных

База данных уже содержит нужные таблицы (User, Payment), но убедитесь что миграции применены:

```bash
python run.py
# Таблицы создадутся автоматически при запуске
```

### Шаг 5: Замените файлы проекта

Скопируйте новые и измененные файлы в ваш проект, заменив существующие:

```bash
# Новые файлы
cp app/yookassa_payment.py YOUR_PROJECT/app/
cp app/subscription.py YOUR_PROJECT/app/
cp app/payment_handlers.py YOUR_PROJECT/app/
cp app/payment_webhook.py YOUR_PROJECT/app/
cp app/scheduler.py YOUR_PROJECT/app/

# Измененные файлы (сделайте backup перед заменой!)
cp app/user.py YOUR_PROJECT/app/
cp run.py YOUR_PROJECT/
cp config.py YOUR_PROJECT/
```

### Шаг 6: Запустите проект

```bash
python run.py
```

## Проверка работоспособности

### 1. Тест бесплатных попыток

```
Пользователь -> /start
Пользователь -> Поиск по документам
Введите запрос -> test
# Поиск должен выполниться, останется 2 попытки
```

### 2. Тест оформления подписки

```
Пользователь -> /subscription
Нажать кнопку "Оформить подписку"
# Должна открыться страница оплаты ЮKassa
```

### 3. Тест тестовым платежом

Используйте тестовую карту ЮKassa:
- Номер: `5555 5555 5555 4477`
- CVC: `123`
- Срок: `12/25`

### 4. Проверка активации

После успешной оплаты:
- Пользователь должен получить сообщение "Подписка активирована"
- `/status` должен показать активную подписку
- Поиск должен работать без ограничений

## Команды для тестирования

```bash
# Проверка уведомлений вручную (в Python shell)
from app.subscription import get_expiring_subscriptions
import asyncio

expiring = asyncio.run(get_expiring_subscriptions(days_before=3))
print(expiring)
```

## Что происходит автоматически

1. **При регистрации** - пользователю дается 3 бесплатных поиска
2. **При поиске** - счетчик уменьшается, если нет подписки
3. **После исчерпания попыток** - предлагается оформить подписку
4. **После оплаты** - webhook активирует подписку на 30 дней
5. **Каждый день в 10:00** - проверяются истекающие подписки
6. **За 3 дня до окончания** - отправляется уведомление
7. **При истечении** - подписка деактивируется

## Основные URL endpoints

- `/webhook/yookassa` - Webhook от ЮKassa (POST)
- `/payment/success` - Страница успешной оплаты (GET)
- `/payment/failed` - Страница ошибки оплаты (GET)

## Troubleshooting

**Проблема:** Webhook не приходит
- Проверьте URL в настройках ЮKassa
- Убедитесь что сервер доступен извне
- Проверьте логи: `tail -f logs/app.log`

**Проблема:** Подписка не активируется
- Проверьте metadata в платеже содержит user_id
- Посмотрите логи webhook endpoint
- Убедитесь что пользователь существует в БД

**Проблема:** Уведомления не приходят
- Проверьте что scheduler запущен (в логах должно быть "Subscription scheduler started")
- Проверьте что бот может отправлять сообщения пользователю

## Дополнительная настройка

### Изменить цену подписки

В `.env`:
```env
SUBSCRIPTION_PRICE=499.0
```

### Изменить время уведомлений

В `app/scheduler.py`, функция `send_daily_notifications_task`, измените:
```python
target_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
# На нужное вам время
```

### Добавить уведомление за 1 день

Уже реализовано в планировщике! Проверяются подписки за 3 и за 1 день до истечения.

## Готово!

Теперь ваш бот поддерживает:
✅ Бесплатные попытки
✅ Оплату подписки через ЮKassa
✅ Автоматические уведомления
✅ Управление доступом

Подробная документация: `PAYMENT_INTEGRATION.md`
