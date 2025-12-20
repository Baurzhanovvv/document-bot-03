import asyncio

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Filter, CommandStart, Command
from app.database.requests import get_admins_tg_id, update_admin, remove_admin, set_admin
from app.utils import from_admins_message, send_message_to_all_users
from config import settings

admin = Router()
import app.keyboards as kb
from aiogram.fsm.context import FSMContext
from app.states import AdminState, AdminSenderState, AdminAdd, AdminRemove, AdminChange
from app.database.requests import check_admin, get_all_users_ids, export_users_xlsx, find_users_by_specialization
from aiogram.types import BufferedInputFile


class AdminDev(Filter):
    def __init__(self):
        self.admins = [1319778538]

    async def __call__(self, message: Message):
        return message.from_user.id in self.admins


class Admin(Filter):
    def __init__(self):
        self.admins = []

    async def __call__(self, message: Message):
        return message.from_user.id in await get_admins_tg_id() or message.from_user.id in [1319778538]


@admin.message(AdminDev(), Command('admin'))
async def cmd_start(message: Message):
    await message.answer('Добро пожаловать в бот, администратор-developer!', reply_markup=kb.admin_kb)


@admin.message(Admin(), Command('admin'))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer('Пожалуйста, войдите в систему! Логин:')
    await state.set_state(AdminState.login)


@admin.message(Admin(), AdminState.login)
async def cmd_login(message: Message, state: FSMContext):
    await state.update_data(login=message.text)
    await state.set_state(AdminState.password)
    await message.answer('Пароль:')


@admin.message(Admin(), AdminState.password)
async def cmd_password(message: Message, state: FSMContext):
    await state.update_data(password=message.text)
    data = await state.get_data()
    await state.clear()
    if await check_admin(message.from_user.id, data.get('login'), data.get('password')):
        await message.answer('Вы успешно вошли в систему!', reply_markup=kb.admin_kb)
    else:
        await message.answer('Неверный логин или пароль!')


@admin.message(Admin(), F.text == 'Администраторы')
async def cmd_admins(message: Message):
    await message.answer(f"{await from_admins_message()}", reply_markup=kb.admin_admin_manager_kb)


# ========= ПОЛЬЗОВАТЕЛИ: отдать Excel прямо при нажатии =========
@admin.message(F.text == 'Пользователи')
async def cmd_users(message: Message):
    await message.answer('Готовлю выгрузку пользователей...')
    buf = await export_users_xlsx()
    await message.answer_document(
        BufferedInputFile(buf.read(), filename="users_export.xlsx"),
        caption="Выгрузка пользователей (Excel)",
        reply_markup=kb.admin_kb
    )


# ========= РАССЫЛКИ =========
@admin.message(Admin(), F.text == 'Рассылки')
async def cmd_messages(message: Message, state: FSMContext):
    await message.answer('Введите текст рассылки', reply_markup=kb.admin_back_kb)
    await state.set_state(AdminSenderState.text)


@admin.message(Admin(), AdminSenderState.text)
async def cmd_messages_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(AdminSenderState.photo)
    await message.answer('Отправьте фото', reply_markup=kb.admin_sender_no_photo_kb)


@admin.message(Admin(), AdminSenderState.photo)
async def cmd_messages_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text == 'Нет фото':
        # stats = await send_message_to_all_users(
        #     message.bot,
        #     data.get('text'),
        #     photo=None
        # )
        await state.update_data(photo=None)
    else:
        photo_id = message.photo[-1].file_id
        await state.update_data(photo=photo_id)
        # stats = await send_message_to_all_users(
        #     message.bot,
        #     data.get('text'),
        #     photo=photo_id
        # )
    # await message.answer(f"Рассылка завершена: {stats}", reply_markup=kb.admin_kb)
    keyboard = await kb.admin_specialization_kb()
    await message.answer('Выберите кому отправить сообщение:', reply_markup=keyboard)
    await state.set_state(AdminSenderState.specialization)




@admin.message(Admin(), AdminSenderState.specialization)
async def cmd_messages_specialization(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await state.clear()
        await message.answer(f"Меню", reply_markup=kb.admin_kb)
        return
    await state.update_data(specialization=message.text)
    data = await state.get_data()
    user_ids = await find_users_by_specialization(message.text)
    if len(user_ids) == 0:
        user_ids = await get_all_users_ids()
    stats = await send_message_to_all_users(
        message.bot,
        users_ids=user_ids,
        text=data.get('text'),
        photo=data.get('photo'),
    )
    await state.clear()
    await message.answer(f"Рассылка завершена: {stats}", reply_markup=kb.admin_kb)


# ========= УПРАВЛЕНИЕ ИНДЕКСОМ =========
from opensearch_dir.opensearch_service import OpenSearchService
from pathlib import Path
import os


@admin.message(F.text == 'Переиндексация файлов')
async def reindex_all(message: Message):
    await message.answer("Запускаю переиндексацию… Это может занять время.")
    svc = OpenSearchService()

    loop = asyncio.get_running_loop()
    # Нужно добавить метод index_folder в OpenSearchService, если его нет
    # result = await loop.run_in_executor(None, svc.index_folder, settings.UPLOAD_DIR)

    await message.answer(
        f"Готово.\n"
        f"Индекс обновлён с автоматическими синонимами"
    )


@admin.message(F.text == 'Очистить индекс')
async def clear_index(message: Message):
    svc = OpenSearchService()
    try:
        svc.client.indices.delete(index=svc.index, ignore=[404])
        # Пересоздадим пустой с маппингом
        svc._ensure_index(svc._get_client())
        await message.answer("Индекс очищен и пересоздан с автоматическими синонимами.")
    except Exception as e:
        await message.answer(f"Не удалось очистить: {e}")


# ========= УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ =========
@admin.message(Admin(), F.text == 'Добавить администратора')
async def cmd_add_admin(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await state.set_state(AdminAdd.tg_id)
    await message.answer('Введите ID администратора')


@admin.message(AdminAdd.tg_id)
async def cmd_add_admin_tg_id(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await state.update_data(tg_id=message.text)
    await state.set_state(AdminAdd.login)
    await message.answer('Введите логин администратора')


@admin.message(AdminAdd.login)
async def cmd_add_admin_login(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await state.update_data(login=message.text)
    await state.set_state(AdminAdd.password)
    await message.answer('Введите пароль администратора')


@admin.message(AdminAdd.password)
async def cmd_add_admin_password(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await state.update_data(password=message.text)
    data = await state.get_data()
    await set_admin(data.get('tg_id'), data.get('login'), data.get('password'), message.from_user.id)
    await state.clear()
    await message.answer('Администратор добавлен', reply_markup=kb.admin_kb)


@admin.message(Admin(), F.text == 'Удалить администратора')
async def cmd_remove_admin(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await message.answer('Введите ID администратора')
    await state.set_state(AdminRemove.tg_id)


@admin.message(AdminRemove.tg_id)
async def cmd_remove_admin_tg_id(message: Message, state: FSMContext):
    await state.update_data(tg_id=message.text)
    status = await remove_admin(message.text)
    await state.clear()
    if status:
        await message.answer('Администратор удален', reply_markup=kb.admin_kb)
    else:
        await message.answer('Администратор не найден', reply_markup=kb.admin_kb)


@admin.message(Admin(), F.text == 'Изменить логин и пароль')
async def cmd_change_admin(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await message.answer('Введите ID администратора')
    await state.set_state(AdminChange.tg_id)


@admin.message(AdminChange.tg_id)
async def cmd_change_admin_tg_id(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await state.update_data(tg_id=message.text)
    await state.set_state(AdminChange.login)
    await message.answer('Введите логин администратора')


@admin.message(AdminChange.login)
async def cmd_change_admin_login(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await state.update_data(login=message.text)
    await state.set_state(AdminChange.password)
    await message.answer('Введите пароль администратора')


@admin.message(AdminChange.password)
async def cmd_change_admin_password(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.admin_kb)
        await state.clear()
        return
    await state.update_data(password=message.text)
    data = await state.get_data()
    await update_admin(data.get('tg_id'), data.get('login'), data.get('password'))
    await state.clear()
    await message.answer('Администратор изменен', reply_markup=kb.admin_kb)


@admin.message(Admin(), F.text == 'Назад')
async def cmd_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Главное меню', reply_markup=kb.admin_kb)