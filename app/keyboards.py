from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from app.database.requests import get_specializations
from config import settings

first_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Политика конфиденциальности', url='https://disk.yandex.ru/i/9ZD70jOhHm70MQ')],
        [InlineKeyboardButton(text='Согласен', callback_data='agree')]
    ]
)

number_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Поделиться номером телефона', request_contact=True)],
    ],
    resize_keyboard=True,
)

location_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Поделиться местоположением', request_location=True)]],
    resize_keyboard=True,
)

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Поиск по документам')],
        [KeyboardButton(text='Профиль'), KeyboardButton(text='Поддержка')],
    ],
    resize_keyboard=True,
)

back_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Назад')]],
    resize_keyboard=True,
)

# Обновлённая админская клавиатура БЕЗ "Настройки поиска"
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Документы', web_app=WebAppInfo(url=settings.WEBAPP_URL)),
         KeyboardButton(text='Администраторы')],
        [KeyboardButton(text='Рассылки'), KeyboardButton(text='Пользователи')],
    ],
    resize_keyboard=True
)

admin_admin_manager_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Добавить администратора'),
         KeyboardButton(text='Удалить администратора')],
        [KeyboardButton(text='Изменить логин и пароль')],
        [KeyboardButton(text='Назад')]
    ],
    resize_keyboard=True
)

admin_back_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Назад')]
    ],
    resize_keyboard=True
)

admin_sender_no_photo_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Нет фото')]
    ],
    resize_keyboard=True
)



async def admin_specialization_kb():
    specializations = await get_specializations()
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Все')],
            [KeyboardButton(text=specialization) for specialization in specializations],
            [KeyboardButton(text='Назад')]
        ],
        resize_keyboard=True
    )
    return keyboard

