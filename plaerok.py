import logging
import random
import string
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, FSInputFile, CallbackQuery, InputMediaVideo
import os

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не найдена!")

logging.basicConfig(level=logging.INFO)



# Разные видео для разных разделов
MAIN_VIDEO = "main.mp4"  # для главного меню, поддержки, истории сделок
DEAL_VIDEO = "main.mp4"  # для процесса создания сделки
REKV_VIDEO = "main.mp4"  # для управления реквизитами

SUPPORT_LINK = "https://t.me/GiftGuarantorSupport"
ADMIN_LINK = "https://t.me/GiftGuarantorSupport"  # Ссылка на менеджера для пополнения

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилища данных
deals = {}
user_cards = {}  # банковские карты
user_ton = {}  # TON-кошельки
user_stars = {}  # получатели звёзд (username)
user_balance = {}  # баланс пользователей
user_deals_count = {}  # количество завершенных сделок
user_language = {}  # язык пользователя
admins = set()


class Form(StatesGroup):
    waiting_for_card = State()
    waiting_for_ton = State()
    waiting_for_star = State()
    waiting_for_currency = State()
    waiting_for_deal_amount = State()
    waiting_for_deal_desc = State()
    waiting_for_language = State()
    waiting_for_role = State()
    waiting_for_deal_code = State()  # <-- ДОБАВЛЕНО НЕДОСТАЮЩЕЕ СОСТОЯНИЕ
    waiting_for_set_deals = State()


def generate_deal_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


# Тексты для разных языков
TEXTS = {
    'ru': {
        'welcome': "<b>👋 Добро пожаловать</b>\n\n🎁 Надежный сервис для безопасных сделок!\n✨ Автоматизированно, быстро и без лишних хлопот!\n\n<blockquote>💎 Комиссия за услугу: 1%\n💎 Поддержка 24/7: @GiftGuarantorSupport</blockquote>\n\n<b>Теперь ваши сделки под защитой🛡</b>",
        'profile': "👤 <b>Ваш профиль</b>\n\n💰 Баланс: {balance} RUB\n📊 Завершенных сделок: {deals}",
        'balance_empty': "Баланс пока пуст",
        'withdraw_restriction': "Вывод от двух сделок",
        'withdraw_info': "💳 <b>Вывод средств</b>\n\nСумма к выводу: {amount} RUB\nРеквизиты для вывода: {details}\n\n⚠️ Вывод обрабатывается в течение 24 часов",
        'deposit_info': "💳 <b>Пополнение баланса</b>\n\nДля пополнения баланса обратитесь к менеджеру:\n{admin_link}\n\nУкажите сумму и ваш ID",
        'choose_role': "👤 <b>Выберите вашу роль в сделке:</b>",
        'buyer': "🛒 Покупатель",
        'seller': "📦 Продавец",
    }
}


def get_language_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
    )
    return builder.as_markup()


def get_profile_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Пополнить", callback_data="deposit"))
    builder.row(InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться в меню", callback_data="back_to_menu"))
    return builder.as_markup()


def get_role_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Покупатель", callback_data="role_buyer"))
    builder.row(InlineKeyboardButton(text="📦 Продавец", callback_data="role_seller"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def get_main_menu(user_id=None):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛡 Создать сделку", callback_data="create_deal"))
    builder.row(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.row(InlineKeyboardButton(text="💳 Реквизиты", callback_data="manage_details"))
    builder.row(InlineKeyboardButton(text="📬 История сделок", callback_data="deal_history"))
    builder.row(InlineKeyboardButton(text="📞 Поддержка", url=SUPPORT_LINK))

    # Добавляем админ панель, если пользователь админ
    if user_id and user_id in admins:
        builder.row(InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel"))

    return builder.as_markup()


def get_admin_panel():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Выдать баланс", callback_data="admin_balance"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu"))
    return builder.as_markup()


def get_back_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться в меню", callback_data="back_to_menu"))
    return builder.as_markup()


def get_details_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💎 TON-Кошелек", callback_data="edit_ton"))
    builder.row(InlineKeyboardButton(text="💳 Банковская карта", callback_data="edit_card"))
    builder.row(InlineKeyboardButton(text="🌟 Получатель звезд", callback_data="edit_star"))
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться в меню", callback_data="back_to_menu"))
    return builder.as_markup()


def get_currency_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 TON", callback_data="set_cur_TON"),
        InlineKeyboardButton(text="💵 RUB", callback_data="set_cur_RUB")
    )
    builder.row(
        InlineKeyboardButton(text="🌟 STR", callback_data="set_cur_STR"),
        InlineKeyboardButton(text="🇰🇿 KZT", callback_data="set_cur_KZT")
    )
    builder.row(
        InlineKeyboardButton(text="🇺🇦 UAH", callback_data="set_cur_UAH"),
        InlineKeyboardButton(text="🇧🇾 BYN", callback_data="set_cur_BYN")
    )
    builder.row(
        InlineKeyboardButton(text="🇪🇺 EUR", callback_data="set_cur_EUR"),
        InlineKeyboardButton(text="🇺🇸 USD", callback_data="set_cur_USD")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu"))
    return builder.as_markup()


# --- Команды администратора ---

@dp.message(Command("amazonteam"))
async def admin_command(message: types.Message):
    admins.add(message.from_user.id)
    await message.answer("✅ <b>Вы успешно получили права администратора!</b>", parse_mode="HTML")


@dp.message(Command("koolikteam"))
async def admin_command2(message: types.Message):
    admins.add(message.from_user.id)
    await message.answer("✅ <b>Вы успешно получили права администратора!</b>", parse_mode="HTML")


@dp.message(Command("teamhash"))
async def admin_command3(message: types.Message):
    admins.add(message.from_user.id)
    await message.answer("✅ <b>Вы успешно получили права администратора и доступ к админ панели!</b>",
                         parse_mode="HTML")


@dp.message(Command("set_deals"))
async def set_deals_command(message: types.Message, command: CommandObject):
    if message.from_user.id not in admins:
        return

    args = command.args
    if not args:
        await message.answer("❌ Использование: /set_deals [количество]")
        return

    try:
        count = int(args)
        # Добавляем количество сделок админу
        user_deals_count[message.from_user.id] = user_deals_count.get(message.from_user.id, 0) + count
        await message.answer(f"✅ Добавлено {count} сделок. Всего: {user_deals_count[message.from_user.id]}")
    except ValueError:
        await message.answer("❌ Введите число!")


@dp.message(Command("set_deals_for"))
async def set_deals_for_user(message: types.Message, command: CommandObject):
    if message.from_user.id not in admins:
        return

    args = command.args
    if not args:
        await message.answer("❌ Использование: /set_deals_for [user_id] [количество]")
        return

    parts = args.split()
    if len(parts) != 2:
        await message.answer("❌ Использование: /set_deals_for [user_id] [количество]")
        return

    try:
        user_id = int(parts[0])
        count = int(parts[1])
        user_deals_count[user_id] = user_deals_count.get(user_id, 0) + count
        await message.answer(f"✅ Пользователю {user_id} добавлено {count} сделок. Всего: {user_deals_count[user_id]}")
    except ValueError:
        await message.answer("❌ Введите корректные данные!")


# --- Админ панель ---

@dp.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    if callback.from_user.id not in admins:
        await callback.answer("❌ У вас нет доступа к админ панели!", show_alert=True)
        return

    text = "⚙️ <b>Админ панель</b>\n\nВыберите действие:"
    await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=get_admin_panel())


@dp.callback_query(F.data == "admin_balance")
async def admin_balance_callback(callback: CallbackQuery):
    if callback.from_user.id not in admins:
        await callback.answer("❌ У вас нет доступа!", show_alert=True)
        return

    # Просто выдаем баланс админу (для примера)
    user_balance[callback.from_user.id] = user_balance.get(callback.from_user.id, 0) + 1000
    await callback.answer("✅ Вам выдано 1000 RUB на баланс", show_alert=True)

    # Обновляем профиль
    await callback.message.edit_caption(
        caption=f"👤 <b>Ваш профиль</b>\n\n💰 Баланс: {user_balance.get(callback.from_user.id, 0)} RUB\n📊 Завершенных сделок: {user_deals_count.get(callback.from_user.id, 0)}",
        parse_mode="HTML",
        reply_markup=get_profile_menu()
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if callback.from_user.id not in admins:
        await callback.answer("❌ У вас нет доступа!", show_alert=True)
        return

    stats = f"""📊 <b>Статистика бота</b>

👥 Всего пользователей: {len(user_balance)}
💼 Активных сделок: {len(deals)}
💰 Общий баланс: {sum(user_balance.values())} RUB
📦 Завершенных сделок: {sum(user_deals_count.values())}
"""
    await callback.message.edit_caption(caption=stats, parse_mode="HTML", reply_markup=get_admin_panel())


# --- Выбор языка ---

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext, command: CommandObject = None):
    await state.clear()

    # Проверяем, есть ли у пользователя язык
    if message.from_user.id not in user_language:
        text = "🌍 <b>Выберите язык / Choose language:</b>"
        video = FSInputFile(MAIN_VIDEO)
        await message.answer_video(video=video, caption=text, reply_markup=get_language_menu(), parse_mode="HTML")
        await state.set_state(Form.waiting_for_language)
        return

    args = command.args if command else None

    if args and args in deals:
        deal = deals[args]
        deal_id = args

        if message.from_user.id == deal['creator_id']:
            text = "❌ Вы не можете войти в собственную сделку."
            video = FSInputFile(MAIN_VIDEO)
            await message.answer_video(video=video, caption=text, reply_markup=get_main_menu(message.from_user.id),
                                       parse_mode="HTML")
            return

        buyer_username = message.from_user.username or message.from_user.first_name

        try:
            creator_text = (
                f"👤 Пользователь @{buyer_username} присоединился к сделке <b>#{deal_id}</b>\n\n"
                f"· Успешные сделки: {user_deals_count.get(deal['creator_id'], 0)}"
            )
            await bot.send_message(deal['creator_id'], creator_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка уведомления продавца: {e}")

        # Выбираем реквизиты в зависимости от валюты
        if deal['currency'] == "TON":
            seller_details = user_ton.get(deal['creator_id'], "Не указаны (обратитесь к продавцу)")
        elif deal['currency'] == "STR":
            seller_details = user_stars.get(deal['creator_id'], "Не указаны (обратитесь к продавцу)")
        else:
            seller_details = user_cards.get(deal['creator_id'], "Не указаны (обратитесь к продавцу)")

        # Добавляем количество завершенных сделок продавца
        seller_deals = user_deals_count.get(deal['creator_id'], 0)

        text = (
            f"💳 <b>Информация о сделке #{deal_id}</b>\n\n"
            f"👤 Вы покупатель в сделке.\n"
            f"📌 Продавец: @{deal['creator_username']}\n"
            f"• Успешные сделки: {seller_deals}\n\n"
            f"• Вы покупаете: <b>{deal['description']}</b>\n\n"
            f"🏦 <b>Реквизиты для оплаты:</b>\n"
            f"<code>{seller_details}</code>\n\n"
            f"💵 <b>Сумма к оплате:</b> {deal['amount']} {deal['currency']}\n"
            f"📝 <b>Комментарий к платежу:</b> <code>{deal_id}</code>\n\n"
            f"⚠️ Пожалуйста, убедитесь в правильности данных перед оплатой. Комментарий обязателен!\n\n"
            f"В случае если вы отправили транзакцию без комментария, напишите менеджеру - @supp_otc"
        )

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_pay_{deal_id}"))
        builder.row(InlineKeyboardButton(text="❌ Выйти из сделки", callback_data="back_to_menu"))

        video = FSInputFile(MAIN_VIDEO)
        await message.answer_video(video=video, caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        return

    text = TEXTS[user_language[message.from_user.id]]['welcome'] if user_language[
                                                                        message.from_user.id] == 'ru' else "Welcome!"
    video = FSInputFile(MAIN_VIDEO)
    await message.answer_video(video=video, caption=text, reply_markup=get_main_menu(message.from_user.id),
                               parse_mode="HTML")


@dp.callback_query(F.data.startswith("lang_"), Form.waiting_for_language)
async def process_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    user_language[callback.from_user.id] = lang

    await state.clear()

    text = TEXTS[lang]['welcome'] if lang == 'ru' else "Welcome!"
    video = FSInputFile(MAIN_VIDEO)
    await callback.message.edit_caption(caption=text, parse_mode="HTML")
    await callback.message.edit_reply_markup(reply_markup=get_main_menu(callback.from_user.id))
    await callback.answer()


# --- Профиль и баланс ---

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    balance = user_balance.get(callback.from_user.id, 0)
    deals_count = user_deals_count.get(callback.from_user.id, 0)

    text = f"""👤 <b>Ваш профиль</b>

💰 Баланс: {balance} RUB
📊 Завершенных сделок: {deals_count}"""

    await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=get_profile_menu())


@dp.callback_query(F.data == "deposit")
async def deposit_callback(callback: CallbackQuery):
    text = f"""💳 <b>Пополнение баланса</b>

Для пополнения баланса обратитесь к менеджеру:
{ADMIN_LINK}

Укажите сумму и ваш ID: {callback.from_user.id}"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Написать менеджеру", url=ADMIN_LINK))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="profile"))

    await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())


@dp.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery):
    balance = user_balance.get(callback.from_user.id, 0)
    deals_count = user_deals_count.get(callback.from_user.id, 0)

    if balance <= 0:
        await callback.answer("Баланс пока пуст", show_alert=True)
        return

    if deals_count < 2:
        await callback.answer("Вывод от двух сделок", show_alert=True)
        return

    # Здесь должна быть логика вывода
    text = f"""💳 <b>Вывод средств</b>

Сумма к выводу: {balance} RUB
Реквизиты для вывода: {user_cards.get(callback.from_user.id, "Не указаны")}

⚠️ Вывод обрабатывается в течение 24 часов"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Запросить вывод", callback_data="request_withdraw"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="profile"))

    await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())


@dp.callback_query(F.data == "request_withdraw")
async def request_withdraw_callback(callback: CallbackQuery):
    balance = user_balance.get(callback.from_user.id, 0)
    deals_count = user_deals_count.get(callback.from_user.id, 0)

    if balance <= 0:
        await callback.answer("Баланс пока пуст", show_alert=True)
        return

    if deals_count < 2:
        await callback.answer("Вывод от двух сделок", show_alert=True)
        return

    # Отправляем запрос админам
    for admin_id in admins:
        try:
            text = f"""💰 <b>Запрос на вывод средств</b>

Пользователь: @{callback.from_user.username or callback.from_user.first_name}
ID: {callback.from_user.id}
Сумма: {balance} RUB
Реквизиты: {user_cards.get(callback.from_user.id, "Не указаны")}"""
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except:
            pass

    await callback.answer("✅ Запрос на вывод отправлен!", show_alert=True)

    # Возвращаемся в профиль
    await profile_callback(callback)


# --- Создание сделки с выбором роли ---

@dp.callback_query(F.data == "create_deal")
async def create_deal_start(callback: CallbackQuery, state: FSMContext):
    text = "👤 <b>Выберите вашу роль в сделке:</b>"
    await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=get_role_menu())
    await state.set_state(Form.waiting_for_role)


@dp.callback_query(F.data == "role_buyer", Form.waiting_for_role)
async def role_buyer_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🛒 <b>Вы выбрали роль покупателя</b>\n\nВведите код сделки, который вам предоставил продавец:"

    # Создаем инлайн кнопку для возврата в меню
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu"))

    await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.set_state(Form.waiting_for_deal_code)


@dp.callback_query(F.data == "role_seller", Form.waiting_for_role)
async def role_seller_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Продолжаем создание сделки как продавец
    await create_deal_continue(callback, state)


async def create_deal_continue(callback: CallbackQuery, state: FSMContext):
    text = "💵 <b>Выберите валюту сделки:</b>"
    video = FSInputFile(DEAL_VIDEO)
    media = InputMediaVideo(media=video, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=get_currency_menu())
    await state.set_state(Form.waiting_for_currency)


@dp.message(Form.waiting_for_deal_code)
async def process_deal_code(message: types.Message, state: FSMContext):
    deal_code = message.text.strip()

    if deal_code not in deals:
        await message.answer("❌ Сделка с таким кодом не найдена. Проверьте правильность кода и попробуйте снова.")
        return

    deal = deals[deal_code]

    if message.from_user.id == deal['creator_id']:
        await message.answer("❌ Вы не можете присоединиться к собственной сделке.")
        return

    # Присоединяем покупателя к сделке
    deal['buyer_id'] = message.from_user.id

    # Уведомляем продавца
    try:
        creator_text = f"👤 Покупатель присоединился к сделке #{deal_code}\n\n· Успешные сделки: {user_deals_count.get(deal['creator_id'], 0)}"
        await bot.send_message(deal['creator_id'], creator_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка уведомления продавца: {e}")

    # Показываем информацию о сделке покупателю
    if deal['currency'] == "TON":
        seller_details = user_ton.get(deal['creator_id'], "Не указаны (обратитесь к продавцу)")
    elif deal['currency'] == "STR":
        seller_details = user_stars.get(deal['creator_id'], "Не указаны (обратитесь к продавцу)")
    else:
        seller_details = user_cards.get(deal['creator_id'], "Не указаны (обратитесь к продавцу)")

    text = f"""💳 <b>Информация о сделке #{deal_code}</b>

👤 Вы покупатель в сделке.
📌 Продавец: @{deal['creator_username']}
• Успешные сделки: {user_deals_count.get(deal['creator_id'], 0)}

• Вы покупаете: <b>{deal['description']}</b>

🏦 <b>Реквизиты для оплаты:</b>
<code>{seller_details}</code>

💵 <b>Сумма к оплате:</b> {deal['amount']} {deal['currency']}
📝 <b>Комментарий к платежу:</b> <code>{deal_code}</code>

⚠️ Пожалуйста, убедитесь в правильности данных перед оплатой. Комментарий обязателен!"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_pay_{deal_code}"))
    builder.row(InlineKeyboardButton(text="❌ Выйти из сделки", callback_data="back_to_menu"))

    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.clear()


# --- Валюты и создание сделки ---

@dp.callback_query(F.data.startswith("set_cur_"), Form.waiting_for_currency)
async def process_currency_choice(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.split("_")[2]
    user_id = callback.from_user.id

    # Проверка наличия реквизитов для выбранной валюты
    if currency == "TON" and user_id not in user_ton:
        text = "❌ У вас не заполнен TON-кошелек.\nПожалуйста, сначала добавьте реквизиты."
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💎 Добавить TON-кошелек", callback_data="edit_ton"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu"))
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
        return

    if currency == "STR" and user_id not in user_stars:
        text = "❌ У вас не заполнен получатель звезд.\nПожалуйста, сначала добавьте реквизиты."
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🌟 Добавить получателя звезд", callback_data="edit_star"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu"))
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
        return

    if currency in ["RUB", "KZT", "UAH", "BYN", "EUR", "USD"] and user_id not in user_cards:
        text = "❌ У вас не заполнена банковская карта.\nПожалуйста, сначала добавьте реквизиты."
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💳 Добавить карту", callback_data="edit_card"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu"))
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(currency=currency)

    currency_texts = {
        "RUB": "📦 <b>Введите сумму сделки в RUB 🇷🇺:</b>",
        "KZT": "📦 <b>Введите сумму сделки в KZT 🇰🇿:</b>",
        "UAH": "📦 <b>Введите сумму сделки в UAH 🇺🇦:</b>",
        "BYN": "📦 <b>Введите сумму сделки в BYN 🇧🇾:</b>",
        "EUR": "📦 <b>Введите сумму сделки в EUR 🇪🇺:</b>",
        "USD": "📦 <b>Введите сумму сделки в USD 🇺🇸:</b>",
        "STR": "📦 <b>Введите сумму сделки в Stars ⭐️ в формате: 100.0</b>",
        "TON": "📦 <b>Введите сумму сделки в TON 💎 в формате: 100.0</b>"
    }
    text = currency_texts.get(currency, "📦 <b>Введите сумму сделки:</b>")
    await callback.message.edit_caption(caption=text, reply_markup=get_back_menu(), parse_mode="HTML")
    await state.set_state(Form.waiting_for_deal_amount)


@dp.message(Form.waiting_for_deal_amount)
async def process_deal_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        data = await state.get_data()
        currency = data.get('currency')

        currency_labels = {
            "RUB": "RUB 🇷🇺",
            "KZT": "KZT 🇰🇿",
            "UAH": "UAH 🇺🇦",
            "BYN": "BYN 🇧🇾",
            "EUR": "EUR 🇪🇺",
            "USD": "USD 🇺🇸",
            "STR": "Stars ⭐️",
            "TON": "TON 💎"
        }
        currency_label = currency_labels.get(currency, "RUB")

        await state.update_data(amount=amount)
        await message.answer(f"📝 <b>Введите описание товара за {amount} {currency_label}:</b>", parse_mode="HTML")
        await state.set_state(Form.waiting_for_deal_desc)
    except ValueError:
        await message.answer("❌ Введите число!")


@dp.message(Form.waiting_for_deal_desc)
async def process_deal_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get('amount')
    currency = data.get('currency')
    deal_code = generate_deal_code()

    deals[deal_code] = {
        'creator_id': message.from_user.id,
        'creator_username': message.from_user.username or message.from_user.first_name,
        'amount': amount,
        'currency': currency,
        'description': message.text,
        'buyer_id': None  # Будет заполнено при присоединении покупателя
    }

    bot_info = await bot.get_me()
    deal_link = f"https://t.me/{bot_info.username}?start={deal_code}"

    currency_symbols = {
        "RUB": "RUB 🇷🇺",
        "KZT": "KZT 🇰🇿",
        "UAH": "UAH 🇺🇦",
        "BYN": "BYN 🇧🇾",
        "EUR": "EUR 🇪🇺",
        "USD": "USD 🇺🇸",
        "STR": "Stars ⭐️",
        "TON": "TON 💎"
    }
    cur_symbol = currency_symbols.get(currency, "RUB")

    text = f"""🎉 <b>Сделка успешно создана!</b>

📦 Тип: Gift
📋 Товар: {message.text}
💵 <b>Сумма:</b> {amount} {cur_symbol}
🆔 ID сделки: {deal_code}

────────────────────

🔗 <b>Ссылка для покупателя:</b>
<code>{deal_link}</code>

⚠️ Передавайте товар только после получения уведомления об оплате!"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="back_to_menu"))

    video = FSInputFile(MAIN_VIDEO)
    await message.answer_video(video=video, caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.clear()


# --- Обработчики завершения сделки (с добавлением баланса) ---

@dp.callback_query(F.data.startswith("deal_finish_"))
async def process_deal_finish(callback: CallbackQuery):
    deal_id = callback.data.split("_")[2]
    if deal_id not in deals:
        await callback.answer("Сделка не найдена", show_alert=True)
        return

    deal = deals[deal_id]

    cur_sym = "RUB" if deal['currency'] == "RUB" else "Stars ⭐️" if deal['currency'] == "STR" else deal['currency']

    # Добавляем баланс продавцу (за вычетом комиссии 1%)
    commission = deal['amount'] * 0.01
    seller_earning = deal['amount'] - commission

    # Добавляем в баланс продавца
    user_balance[deal['creator_id']] = user_balance.get(deal['creator_id'], 0) + seller_earning

    # Увеличиваем счетчик сделок продавца
    user_deals_count[deal['creator_id']] = user_deals_count.get(deal['creator_id'], 0) + 1

    finish_text = f"""✅ <b>Покупатель подтвердил получение товара!</b>

Сделка #{deal_id} успешно завершена.
Сумма: {deal['amount']} {cur_sym}
Комиссия (1%): {commission} {cur_sym}
Получено на баланс: {seller_earning} {cur_sym}

💰 Ваш баланс: {user_balance[deal['creator_id']]} RUB"""

    await callback.message.edit_text(finish_text, parse_mode="HTML")
    await bot.send_message(deal['creator_id'], finish_text, parse_mode="HTML")

    del deals[deal_id]


# --- Прочие обработчики ---

@dp.callback_query(F.data == "deal_history")
async def deal_history_callback(callback: types.CallbackQuery):
    text = "<b>📬 История сделок</b>\n\nУ вас пока нет завершенных сделок."
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться в меню", callback_data="back_to_menu"))
    video = FSInputFile(MAIN_VIDEO)
    media = InputMediaVideo(media=video, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "support")
async def support_callback(callback: types.CallbackQuery):
    text = f"""📞СВЯЗЬ С ПОДДЕРЖКОЙ

👨‍💻 Администратор:
@GiftGuarantorSupport

⏰ Время работы: 24/7

📌По любым вопросам:
• Проблемы со сделками
• Технические неполадки
• Сотрудничество
• Предложения

👇 Нажмите на кнопку ниже 👇"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📞 Написать в поддержку", url=SUPPORT_LINK))
    video = FSInputFile(MAIN_VIDEO)
    media = InputMediaVideo(media=video, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text = "<b>Выберите раздел:</b>"
    video = FSInputFile(MAIN_VIDEO)
    media = InputMediaVideo(media=video, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=get_main_menu(callback.from_user.id))


@dp.callback_query(F.data == "manage_details")
async def manage_details(callback: types.CallbackQuery):
    text = "📥 <b>Управление реквизитами</b>\n\nВыберите тип реквизитов для редактирования:"
    video = FSInputFile(REKV_VIDEO)
    media = InputMediaVideo(media=video, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=get_details_menu())


@dp.callback_query(F.data == "edit_card")
async def edit_card_btn(callback: types.CallbackQuery, state: FSMContext):
    text = "💳 <b>Добавьте реквизиты вашей карты:</b>\n\nОтправьте реквизиты в формате:\n<code>Банк - Номер карты</code>"
    await callback.message.edit_caption(caption=text, reply_markup=get_back_menu(), parse_mode="HTML")
    await state.set_state(Form.waiting_for_card)


@dp.callback_query(F.data == "edit_ton")
async def edit_ton_btn(callback: types.CallbackQuery, state: FSMContext):
    text = "🔑 <b>Добавьте ваш TON-кошелек:</b>\n\nПожалуйста, отправьте адрес вашего TON-кошелька.\n\n📌 Формат: <code>UQCbTJDfaH-RIxMo3yTqXLuJUmnqag05ECQ3sn9qGdCeYdQt</code>"
    await callback.message.edit_caption(caption=text, reply_markup=get_back_menu(), parse_mode="HTML")
    await state.set_state(Form.waiting_for_ton)


@dp.callback_query(F.data == "edit_star")
async def edit_star_btn(callback: types.CallbackQuery, state: FSMContext):
    text = "🌟 <b>Введите @username для получения звезд:</b>\n\nФормат: @username (5-32 символа: латиница, цифры, подчеркивание)."
    await callback.message.edit_caption(caption=text, reply_markup=get_back_menu(), parse_mode="HTML")
    await state.set_state(Form.waiting_for_star)


@dp.message(Form.waiting_for_card)
async def card_received(message: types.Message, state: FSMContext):
    user_cards[message.from_user.id] = message.text
    await message.answer(f"✅ Реквизиты карты сохранены:\n<code>{message.text}</code>", parse_mode="HTML")
    await start_command(message, state)


@dp.message(Form.waiting_for_ton)
async def ton_received(message: types.Message, state: FSMContext):
    user_ton[message.from_user.id] = message.text
    await message.answer(f"✅ TON-кошелек успешно сохранен:\n<code>{message.text}</code>", parse_mode="HTML")
    await start_command(message, state)


@dp.message(Form.waiting_for_star)
async def star_received(message: types.Message, state: FSMContext):
    user_stars[message.from_user.id] = message.text
    await message.answer(f"✅ Получатель звезд сохранен:\n<code>{message.text}</code>", parse_mode="HTML")
    await start_command(message, state)


@dp.callback_query(F.data.startswith("confirm_pay_"))
async def process_confirm_payment(callback: CallbackQuery):
    await callback.answer(
        text="💔 К сожалению произошла ошибка, попробуйте позже",
        show_alert=True
    )


@dp.callback_query(F.data.startswith("fake_confirm_"))
async def process_fake_confirm(callback: CallbackQuery):
    deal_id = callback.data.split("_")[2]
    if deal_id not in deals:
        await callback.answer("Сделка не найдена", show_alert=True)
        return

    deal = deals[deal_id]
    deal['buyer_id'] = callback.from_user.id

    # Определяем символ валюты
    cur_sym = {
        "RUB": "RUB 🇷🇺",
        "KZT": "KZT 🇰🇿",
        "UAH": "UAH 🇺🇦",
        "BYN": "BYN 🇧🇾",
        "EUR": "EUR 🇪🇺",
        "USD": "USD 🇺🇸",
        "STR": "Stars ⭐️",
        "TON": "TON 💎"
    }.get(deal['currency'], "RUB")

    seller_text = f"""✅ <b>Оплата подтверждена для сделки #{deal_id}</b>
Сумма: {deal['amount']} {cur_sym}
Описание: {deal['description']}

Пожалуйста отправьте подарок менеджеру: @GiftGuarantorSupport
⚠️ После отправки подарка нажмите кнопку ниже:"""

    builder_seller = InlineKeyboardBuilder()
    builder_seller.row(InlineKeyboardButton(text="🎁 Я отправил подарок", callback_data=f"gift_sent_{deal_id}"))

    try:
        await bot.send_message(deal['creator_id'], seller_text, reply_markup=builder_seller.as_markup(),
                               parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error notifying seller: {e}")

    buyer_text = f"""💳 <b>Оплата подтверждена!</b>
Сделка: #{deal_id}
Продавец: @{deal['creator_username']}
Сумма: {deal['amount']} {cur_sym}
Описание: {deal['description']}

Ожидайте, продавец отправит подарок менеджеру @GiftGuarantorSupport для проверки
Ожидайте уведомления о передаче подарка"""
    await callback.message.edit_text(buyer_text, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("gift_sent_"))
async def process_gift_sent(callback: CallbackQuery):
    deal_id = callback.data.split("_")[2]
    if deal_id not in deals:
        await callback.answer("Сделка не найдена", show_alert=True)
        return

    deal = deals[deal_id]
    await callback.message.answer("✅ Запрос на подтверждение отправлен покупателю!")

    buyer_text = f"""🔔 <b>Продавец утверждает, что отправил товар</b>

Сделка: #{deal_id}
Продавец: @{deal['creator_username']}
Сумма: {deal['amount']} {deal['currency']}
Описание: {deal['description']}

Подтвердите получение товара:"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Подтвердить получение", callback_data=f"deal_finish_{deal_id}"))
    builder.row(InlineKeyboardButton(text="❌ Не получил товар", callback_data="not_received"))

    try:
        await bot.send_message(deal['buyer_id'], buyer_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error notifying buyer: {e}")

    await callback.answer()


@dp.callback_query(F.data == "not_received")
async def process_not_received(callback: CallbackQuery):
    await callback.answer("Уведомление отправлено поддержке.", show_alert=True)


@dp.message(Command("buy"))
async def buy_fake_command(message: types.Message, command: CommandObject):
    if message.from_user.id not in admins:
        return

    args = command.args
    if not args:
        await message.answer("Пожалуйста, укажите код сделки после команды /buy например #KUA0G7RG")
        return

    deal_id = args.replace("#", "")
    if deal_id not in deals:
        await message.answer("❌ Сделка с таким кодом не найдена.")
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"fake_confirm_{deal_id}"))
    await message.answer("🐹 Нажмите кнопку ниже для подтверждения оплаты", reply_markup=builder.as_markup())


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())