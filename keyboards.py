from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORT_USERNAME


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📱 Сдать аккаунт", callback_data="submit_account")],
    ])


def profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Вывести баланс", callback_data="withdraw")],
        [InlineKeyboardButton(text="📱 Мои аккаунты", callback_data="my_accounts")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_main")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])


def support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


# ===== ADMIN KEYBOARDS =====

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="📱 Все аккаунты", callback_data="admin_accounts")],
        [InlineKeyboardButton(text="💸 Заявки на выплату", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="💵 Изменить прайс", callback_data="admin_set_price")],
    ])


def cancel_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")],
    ])


def admin_account_actions(account_id: int, phone: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Слушать коды (2 мин)", callback_data=f"admin_listen_{account_id}")],
        [InlineKeyboardButton(text="🔒 Сменить пароль", callback_data=f"admin_chpass_{account_id}")],
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_{account_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{account_id}")],
        [InlineKeyboardButton(text="🔙 К аккаунтам", callback_data="admin_accounts")],
    ])


def admin_withdrawal_actions(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выплатить", callback_data=f"admin_pay_{withdrawal_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_w_{withdrawal_id}")],
        [InlineKeyboardButton(text="🔙 К заявкам", callback_data="admin_withdrawals")],
    ])


def admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_menu")],
    ])
    
