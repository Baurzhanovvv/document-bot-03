"""
Web-обработчики для webhook от ЮKassa и страниц успешной оплаты
"""
from aiohttp import web
import json
from app.yookassa_payment import process_webhook
from app.subscription import create_subscription
from aiogram import Bot
from config import settings


async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    """
    Обработчик webhook от ЮKassa
    Вызывается когда меняется статус платежа
    """
    # Если это GET запрос (проверка доступности)
    if request.method == 'GET':
        return web.json_response({
            "status": "ok",
            "message": "Webhook endpoint is active",
            "method": "POST required"
        })

    try:
        print(f"[WEBHOOK] Получен запрос от ЮKassa")
        body = await request.json()
        print(f"[WEBHOOK] Body: {json.dumps(body, indent=2, ensure_ascii=False)}")

        # Обрабатываем webhook
        webhook_data = process_webhook(body)

        if not webhook_data:
            print(f"[WEBHOOK] Ошибка: невалидный webhook")
            return web.json_response({"status": "error", "message": "Invalid webhook"}, status=400)

        print(f"[WEBHOOK] Событие: {webhook_data.get('event')}, Payment ID: {webhook_data.get('payment_id')}")

        # Если платеж успешен - создаем подписку
        if webhook_data["event"] == "payment.succeeded":
            user_id = webhook_data["metadata"].get("user_id")
            payment_id = webhook_data["payment_id"]

            print(f"[WEBHOOK] Успешный платеж для пользователя {user_id}")

            if user_id:
                # Создаем подписку для пользователя
                success = await create_subscription(int(user_id), payment_id)

                if success:
                    print(f"[WEBHOOK] Подписка создана для пользователя {user_id}")
                    # Отправляем уведомление пользователю
                    bot = request.app["bot"]
                    try:
                        await bot.send_message(
                            int(user_id),
                            "✅ <b>Подписка успешно активирована!</b>\n\n"
                            "Теперь вы можете пользоваться неограниченным поиском в течение 30 дней.\n\n"
                            "Используйте 'Поиск по документам' для начала работы.",
                            parse_mode="HTML"
                        )
                        print(f"[WEBHOOK] Уведомление отправлено пользователю {user_id}")
                    except Exception as e:
                        print(f"[WEBHOOK] Ошибка отправки уведомления: {e}")
                else:
                    print(f"[WEBHOOK] Ошибка создания подписки для пользователя {user_id}")

        return web.json_response({"status": "ok"})

    except Exception as e:
        print(f"[WEBHOOK] Ошибка обработки: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def payment_success_handler(request: web.Request) -> web.Response:
    """
    Страница успешной оплаты
    Пользователь попадает сюда после успешной оплаты
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Оплата успешна</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                text-align: center;
                max-width: 500px;
            }
            .success-icon {
                font-size: 64px;
                color: #4CAF50;
                margin-bottom: 20px;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
            }
            p {
                color: #666;
                line-height: 1.6;
                margin-bottom: 20px;
            }
            .button {
                display: inline-block;
                padding: 12px 30px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: background 0.3s;
            }
            .button:hover {
                background: #5568d3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✓</div>
            <h1>Оплата прошла успешно!</h1>
            <p>
                Ваша подписка активирована на 30 дней.<br>
                Вы получите уведомление в Telegram боте.
            </p>
            <p>
                Теперь вы можете пользоваться неограниченным поиском по документам!
            </p>
            <a href="https://t.me/Test_neo_ybr_bot" class="button">Вернуться в бот</a>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def payment_failed_handler(request: web.Request) -> web.Response:
    """
    Страница неудачной оплаты
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Ошибка оплаты</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                text-align: center;
                max-width: 500px;
            }
            .error-icon {
                font-size: 64px;
                color: #f44336;
                margin-bottom: 20px;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
            }
            p {
                color: #666;
                line-height: 1.6;
                margin-bottom: 20px;
            }
            .button {
                display: inline-block;
                padding: 12px 30px;
                background: #f5576c;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: background 0.3s;
                margin: 5px;
            }
            .button:hover {
                background: #e04556;
            }
            .button-secondary {
                background: #999;
            }
            .button-secondary:hover {
                background: #777;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">✗</div>
            <h1>Ошибка оплаты</h1>
            <p>
                К сожалению, платеж не был завершен.<br>
                Попробуйте еще раз или обратитесь в поддержку.
            </p>
            <a href="https://t.me/Test_neo_ybr_bot" class="button">Попробовать снова</a>
            <a href="https://t.me/Test_neo_ybr_bot" class="button button-secondary">Поддержка</a>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def test_activate_subscription(request: web.Request) -> web.Response:
    """Тестовый endpoint для активации подписки вручную"""
    try:
        user_id = request.query.get('user_id')
        if not user_id:
            return web.json_response({"error": "user_id required"}, status=400)

        user_id = int(user_id)
        success = await create_subscription(user_id, "manual-test")

        if success:
            # Отправляем уведомление
            bot = request.app["bot"]
            try:
                await bot.send_message(
                    user_id,
                    "✅ <b>Подписка активирована вручную (тест)</b>\n\n"
                    "Теперь у вас есть неограниченный доступ на 30 дней.",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Ошибка отправки уведомления: {e}")

            return web.json_response({
                "status": "ok",
                "message": f"Subscription activated for user {user_id}"
            })
        else:
            return web.json_response({
                "status": "error",
                "message": "Failed to create subscription"
            }, status=500)

    except Exception as e:
        return web.json_response({
            "status": "error",
            "message": str(e)
        }, status=500)


def setup_payment_routes(app: web.Application):
    """
    Регистрация маршрутов для обработки платежей
    """
    app.router.add_post("/webhook/yookassa", yookassa_webhook_handler)
    app.router.add_get("/webhook/yookassa", yookassa_webhook_handler)  # Для проверки доступности
    app.router.add_get("/payment/success", payment_success_handler)
    app.router.add_get("/payment/failed", payment_failed_handler)
    app.router.add_get("/test/activate", test_activate_subscription)  # Тестовый endpoint