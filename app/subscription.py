"""
Модуль управления подписками пользователей
"""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, and_
from app.database.models import async_session, User, Payment


async def check_user_access(tg_id: int) -> dict:
    """
    Проверка доступа пользователя к поиску
    
    Returns:
        dict с информацией о доступе:
        - has_access: bool - есть ли доступ
        - access_type: str - тип доступа (free, subscription, expired)
        - searches_left: int - осталось бесплатных поисков
        - subscription_end: datetime - дата окончания подписки (если есть)
    """
    print(f"[ACCESS] Проверка доступа для пользователя {tg_id}")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            print(f"[ACCESS] Пользователь {tg_id} не найден в БД")
            return {
                "has_access": False,
                "access_type": "no_user",
                "searches_left": 0,
                "subscription_end": None
            }

        print(f"[ACCESS] Пользователь найден: search_count={user.search_count}")

        # Проверяем активную подписку
        active_payment = await get_active_subscription(tg_id)

        if active_payment:
            print(f"[ACCESS] Найдена активная подписка до {active_payment['end_date']}")
            return {
                "has_access": True,
                "access_type": "subscription",
                "searches_left": -1,  # безлимит
                "subscription_end": active_payment["end_date"]
            }
        else:
            print(f"[ACCESS] Активная подписка не найдена")

        # Проверяем бесплатные попытки
        search_count = user.search_count or 0
        if search_count > 0:
            print(f"[ACCESS] Доступ по бесплатным попыткам: {search_count} осталось")
            return {
                "has_access": True,
                "access_type": "free",
                "searches_left": search_count,
                "subscription_end": None
            }

        print(f"[ACCESS] Доступ закрыт: нет подписки и попыток")
        return {
            "has_access": False,
            "access_type": "expired",
            "searches_left": 0,
            "subscription_end": None
        }


async def decrease_search_count(tg_id: int) -> int:
    """
    Уменьшить количество бесплатных поисков

    Returns:
        Оставшееся количество поисков
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user and user.search_count > 0:
            user.search_count -= 1
            await session.commit()
            return user.search_count
        return 0


async def create_subscription(tg_id: int, payment_id: str) -> bool:
    """
    Создать подписку для пользователя после успешной оплаты

    Args:
        tg_id: ID пользователя в Telegram
        payment_id: ID платежа в ЮKassa

    Returns:
        True если подписка создана успешно
    """
    from datetime import timezone as tz

    async with async_session() as session:
        try:
            # Проверяем существует ли пользователь
            user = await session.scalar(select(User).where(User.tg_id == tg_id))
            if not user:
                print(f"[SUBSCRIPTION] Пользователь {tg_id} не найден в БД")
                return False

            print(f"[SUBSCRIPTION] Создание подписки для пользователя {tg_id}")

            # Создаем новую запись о платеже
            payment = Payment(
                user_id=tg_id,
                created_at=datetime.now(tz.utc),
                active=True
            )
            session.add(payment)
            await session.commit()

            print(f"[SUBSCRIPTION] Подписка создана: Payment ID={payment.id}, active={payment.active}")
            return True

        except Exception as e:
            print(f"[SUBSCRIPTION] Ошибка создания подписки для {tg_id}: {e}")
            import traceback
            traceback.print_exc()
            return False


async def get_active_subscription(tg_id: int) -> Optional[dict]:
    """
    Получить активную подписку пользователя

    Returns:
        dict с данными подписки или None
    """
    from datetime import timezone as tz

    print(f"[GET_SUB] Поиск активной подписки для {tg_id}")

    async with async_session() as session:
        # Получаем последний активный платеж
        payment = await session.scalar(
            select(Payment)
            .where(
                and_(
                    Payment.user_id == tg_id,
                    Payment.active == True
                )
            )
            .order_by(Payment.created_at.desc())
            .limit(1)
        )

        if not payment:
            print(f"[GET_SUB] Платежи не найдены для {tg_id}")
            return None

        print(f"[GET_SUB] Найден платеж: ID={payment.id}, created_at={payment.created_at}, active={payment.active}")

        # Убедимся что created_at timezone-aware
        created_at = payment.created_at
        if created_at.tzinfo is None:
            print(f"[GET_SUB] ВНИМАНИЕ: created_at без timezone, добавляю UTC")
            created_at = created_at.replace(tzinfo=tz.utc)

        end_date = created_at + timedelta(days=30)
        now = datetime.now(tz.utc)

        print(f"[GET_SUB] created_at: {created_at}")
        print(f"[GET_SUB] end_date: {end_date}")
        print(f"[GET_SUB] now: {now}")
        print(f"[GET_SUB] is_valid: {end_date > now}")

        # Проверяем не истекла ли подписка
        if end_date > now:
            result = {
                "payment_id": payment.id,
                "start_date": created_at,
                "end_date": end_date,
                "days_left": (end_date - now).days
            }
            print(f"[GET_SUB] Подписка активна, осталось дней: {result['days_left']}")
            return result
        else:
            print(f"[GET_SUB] Подписка истекла, деактивирую")
            # Деактивируем истекшую подписку
            payment.active = False
            await session.commit()
            return None


async def get_expiring_subscriptions(days_before: int = 3) -> List[dict]:
    """
    Получить список подписок, которые скоро истекут

    Args:
        days_before: За сколько дней до истечения уведомлять

    Returns:
        Список dict с информацией о пользователях и их подписках
    """
    async with async_session() as session:
        # Дата для проверки (через days_before дней)
        check_date = datetime.now() + timedelta(days=days_before)
        end_check_date = datetime.now() + timedelta(days=days_before + 1)

        # Получаем все активные платежи
        result = await session.execute(
            select(Payment, User)
            .join(User, Payment.user_id == User.tg_id)
            .where(Payment.active == True)
        )

        expiring = []
        for payment, user in result:
            end_date = payment.created_at + timedelta(days=30)

            # Проверяем попадает ли дата окончания в нужный диапазон
            if check_date <= end_date < end_check_date:
                expiring.append({
                    "tg_id": user.tg_id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "end_date": end_date,
                    "days_left": (end_date - datetime.now()).days
                })

        return expiring


async def deactivate_expired_subscriptions() -> int:
    """
    Деактивировать все истекшие подписки

    Returns:
        Количество деактивированных подписок
    """
    async with async_session() as session:
        result = await session.execute(
            select(Payment).where(Payment.active == True)
        )
        payments = result.scalars().all()

        count = 0
        for payment in payments:
            end_date = payment.created_at + timedelta(days=30)
            if end_date <= datetime.now():
                payment.active = False
                count += 1

        await session.commit()
        return count