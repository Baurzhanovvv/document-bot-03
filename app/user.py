from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart, Command

from app.database.requests import set_user, update_user, set_sub
# from middlewares import BaseMiddleware
import app.keyboards as kb
from aiogram.fsm.context import FSMContext
from app.states import Reg, SubState, SearchDocsStates
from app.utils import from_profile_message
from app.search import handle_search_query

user = Router()

# user.message.middleware(BaseMiddleware())

@user.message(CommandStart())
async def cmd_start(message: Message):
    await set_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer('👋 Добро пожаловать в КлинРекиБот!\nБот помогает врачам быстро находить нужные пункты в клинических рекомендациях Минздрава РФ — по ключевым словам, диагнозам и алгоритмам.\n\nИспользуя бота, вы подтверждаете своё согласие на обработку персональных данных в соответствии с ФЗ-152.', reply_markup=kb.first_keyboard)

@user.callback_query(F.data == 'agree')
async def agree(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer('Поделитесь номером телефона', reply_markup=kb.number_kb)
    await state.set_state(Reg.number)

@user.message(F.contact, Reg.number)
async def number(message: Message, state: FSMContext):
    await state.update_data(number=message.contact.phone_number)
    await message.answer('Введите город', reply_markup=kb.location_kb)
    await state.set_state(Reg.location)


@user.message(F.text, Reg.location)
async def location_text(message: Message, state: FSMContext):
    # TODO: Добавить обработку местоположения??
    await state.update_data(location=f'{message.text}')
    await message.answer('Введите специализацию', reply_markup=kb.back_kb)
    await state.set_state(Reg.work)


@user.message(F.location, Reg.location)
async def location(message: Message, state: FSMContext):
    # TODO: Добавить обработку местоположения??
    await state.update_data(location=f'{message.location.latitude}-{message.location.longitude}')
    await message.answer('Введите специализацию', reply_markup=kb.back_kb)
    await state.set_state(Reg.work)

@user.message(F.text, Reg.work)
async def work(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.main_kb)
        await state.clear()
        return
    await state.update_data(work=message.text)
    data = await state.get_data()
    await update_user(message.from_user.id, data.get('number'), data.get('location'), data.get('work'))
    await message.answer('Вы успешно зарегистрированы!', reply_markup=kb.main_kb)
    await state.clear()

@user.message(F.text == 'Поиск по документам')
async def search_docs_start(message: Message, state: FSMContext):
    from app.subscription import check_user_access
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Проверяем доступ пользователя
    access_info = await check_user_access(message.from_user.id)
    
    if not access_info["has_access"]:
        # Доступ закончился - предлагаем купить подписку
        from app.yookassa_payment import get_subscription_price
        price = get_subscription_price()
        
        text = (
            "❌ <b>Бесплатные попытки исчерпаны</b>\n\n"
            f"Оформите подписку за {price:.0f}₽/месяц для безлимитного доступа!\n\n"
            "🎁 Преимущества подписки:\n"
            "• Неограниченный поиск\n"
            "• Доступ ко всем документам\n"
            "• Приоритетная поддержка"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
        ])
        
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return
    
    # Если есть доступ - информируем об оставшихся попытках
    if access_info["access_type"] == "free":
        searches_left = access_info["searches_left"]
        await message.answer(
            f"🔍 У вас осталось {searches_left} бесплатных поисков.\n\n"
            "Введите поисковый запрос:"
        )
    else:
        await message.answer("Введите поисковый запрос по документам:")
    
    await state.set_state(SearchDocsStates.waiting_query)

@user.message(SearchDocsStates.waiting_query, F.text)
async def search_docs_run(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        await message.answer("Пустой запрос. Введите текст запроса:")
        return
    await handle_search_query(message, query)
    await state.clear()


@user.message(F.text == 'Профиль')
async def profile(message: Message):
    text = await from_profile_message(message.from_user.id)
    await message.answer(text, reply_markup=kb.main_kb)
    

@user.message(F.text == 'Поддержка')
async def support(message: Message, state: FSMContext):
    await message.answer('Задайте вопрос, мы вам поможем!', reply_markup=kb.back_kb)
    await state.set_state(SubState.text)

@user.message(F.text, SubState.text)
async def sub_text(message: Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Главное меню', reply_markup=kb.main_kb)
        await state.clear()
        return
    await set_sub(message.from_user.id, message.text)
    await message.answer('Ваш вопрос отправлен! Мы вам поможем!', reply_markup=kb.main_kb)
    await state.clear()


# from app.database.requests import log_search
#
# await log_search(
#     tg_id=message.from_user.id,
#     query_text=user_query,
#     num_results=(len(results) if results is not None else None),
#     source="bot",
#     extra={"took_ms": took_ms}  # что угодно по желанию
# )
