from app.database.requests import get_user, get_last_payment, get_admins_info, get_all_users_ids
from aiogram import Bot
import time



async def from_profile_message(tg_id):
    user = await get_user(tg_id)
    text = ''
    payment = await get_last_payment(tg_id)
    if user:
        text += f"ID: {user[0]}\n"
        text += f"Username: {user[1]}\n"
        text += f"Full name: {user[2]}\n"
        text += f"Number: {user[3]}\n"
        text += f"Location: {user[4]}\n"
        text += f"Специальность: {user[5]}\n"
        if payment is not None:
            text += f"Статус подписки: {payment[0]}\n"
            text += f"Подписка закончится: {payment[1]}\n"
        else:
            text += "Подписка не активна\n"
    return text

async def from_admins_message():
    admins = await get_admins_info()
    text = ''
    if len(admins) == 0:
        return 'Empty'
    for admin in admins:
        text += f"ID: {admin[0]}\n"
        text += f"Login: {admin[1]}\n"
        text += f"Назначен: {admin[2]}\n"
        text += f"Добавил: {admin[3]}\n"
        text += "\n"

    return text
    



import asyncio
from typing import Iterable, Union

from aiogram import Bot
from aiogram.types import FSInputFile, BufferedInputFile, InputFile
from aiogram.exceptions import (
    TelegramRetryAfter, TelegramForbiddenError, TelegramNotFound,
    TelegramBadRequest, TelegramEntityTooLarge, TelegramAPIError
)

PhotoType = Union[str, FSInputFile, BufferedInputFile, InputFile]


async def send_message_to_all_users(
    bot: Bot,
    users_ids: list[int],
    text: str,
    photo: PhotoType | None = None,
    disable_notification: bool = False,
    throttle_per_msg: float = 0.1,    # пауза между отправками
) -> dict:
    """
    Рассылка всем пользователям.
    - text: текст сообщения (для фото это будет caption)
    - photo: опционально фото (file_id/URL/FSInputFile/BufferedInputFile)
    - get_all_users_ids: асинхр. функция, возвращающая Iterable[int]
    Возвращает статистику: {'ok': n, 'blocked': n, 'bad_request': n, 'errors': n}
    """

    users = users_ids
    stats = {"ok": 0, "blocked": 0, "bad_request": 0, "errors": 0}

    # лимиты Telegram: caption для фото ≤ 1024, текст сообщения ≤ 4096
    def clip_text_for_caption(s: str) -> str:
        return s if len(s) <= 1024 else s[:1021] + "…"

    for uid in users:
        # до 3 попыток при 429/временных ошибках
        attempts = 0
        while attempts < 3:
            try:
                if photo is not None:
                    await bot.send_photo(
                        uid,
                        photo=photo,
                        caption=clip_text_for_caption(text),
                        disable_notification=disable_notification,
                    )
                else:
                    await bot.send_message(
                        uid,
                        text=text if len(text) <= 4096 else text[:4093] + "…",
                        disable_notification=disable_notification,
                    )

                stats["ok"] += 1
                await asyncio.sleep(throttle_per_msg)
                break  # успех — выходим из цикла попыток

            except TelegramRetryAfter as e:
                # FloodWait / Too Many Requests — ждём указанное время и пробуем ещё
                await asyncio.sleep(e.retry_after + 1)
                attempts += 1
                continue

            except (TelegramForbiddenError, TelegramNotFound):
                # пользователь заблокировал бота / аккаунт удалён
                stats["blocked"] += 1
                # тут можно пометить пользователя как неактивного в БД
                break

            except TelegramBadRequest as e:
                # например, слишком длинный caption, некорректные сущности и т.п.
                stats["bad_request"] += 1
                # попробуем один раз отправить «облегчённо»
                if photo is not None and attempts == 0:
                    # убираем caption совсем
                    try:
                        await bot.send_photo(uid, photo=photo, disable_notification=disable_notification)
                        stats["ok"] += 1
                    except Exception:
                        pass
                break

            except TelegramEntityTooLarge:
                # картинка/файл слишком большие
                stats["bad_request"] += 1
                break

            except TelegramAPIError:
                # какая-то временная ошибка API
                attempts += 1
                await asyncio.sleep(1.5)
                continue

            except Exception:
                # неожиданные ошибки — не падаем всей рассылкой
                stats["errors"] += 1
                break

    return stats

