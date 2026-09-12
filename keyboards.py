from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORT_USERNAME


def e(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# Кастомные эмодзи
E_SUPPORT   = e("5443038326535759644", "💬")
E_PROFILE   = e("5416041192905265756", "👤")
E_SUBMIT    = e("5397916757333654639", "📱")
E_BALANCE   = e("5445353829304387411", "💰")
E_CHECK     = e("5206607081334906820", "✅")
E_PENDING   = e("5386367538735104399", "⏳")
E_STATS     = e("5197503331215361533", "📊")
E_REJECT    = e("5210952531676504517", "❌")
E_PROCESS   = e("5386367538735104399", "🔄")
E_USERS     = e("5244837092042750681", "👥")
E_WITHDRAW  = e("5210956306952758910", "💸")
E_CODES     = e("5463424023734014980", "🔑")
E_LOCK      = e("5213179235996294999", "🔒")
E_PRICE     = e("5307843983102204243", "💵")
E_BACK      = "🔙"
E_CANCEL    = e("5210952531676504517", "❌")


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_SUPPORT} Поддержка", callback_data="support")],
        [InlineKeyboardButton(text=f"{E_PROFILE} Профиль", callback_data="profile")],
        [InlineKeyboardButton(text=f"{E_SUBMIT} Сдать аккаунт", callback_data="submit_account")],
    ])


def profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_BALANCE} Вывести баланс", callback_data="withdraw")],
        [InlineKeyboardButton(text=f"{E_SUBMIT} Мои аккаунты", callback_data="my_accounts")],
        [InlineKeyboardButton(text=f"{E_BACK} Назад", callback_data="back_main")],
    ])


def back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_BACK} Главное меню", callback_data="back_main")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_CANCEL} Отмена", callback_data="cancel")],
    ])


def support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_SUPPORT} Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(text=f"{E_BACK} Назад", callback_data="back_main")],
    ])


# ===== ADMIN KEYBOARDS =====

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_STATS} Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton(text=f"{E_USERS} Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text=f"{E_SUBMIT} Все аккаунты", callback_data="admin_accounts")],
        [InlineKeyboardButton(text=f"{E_WITHDRAW} Заявки на выплату", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text=f"{E_PRICE} Изменить прайс", callback_data="admin_set_price")],
    ])


def cancel_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_CANCEL} Отмена", callback_data="admin_menu")],
    ])


def admin_account_actions(account_id: int, phone: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_CODES} Слушать коды (2 мин)", callback_data=f"admin_listen_{account_id}")],
        [InlineKeyboardButton(text=f"{E_LOCK} Сменить пароль", callback_data=f"admin_chpass_{account_id}")],
        [InlineKeyboardButton(text=f"{E_CHECK} Одобрить", callback_data=f"admin_approve_{account_id}")],
        [InlineKeyboardButton(text=f"{E_REJECT} Отклонить", callback_data=f"admin_reject_{account_id}")],
        [InlineKeyboardButton(text=f"{E_BACK} К аккаунтам", callback_data="admin_accounts")],
    ])


def admin_withdrawal_actions(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_CHECK} Выплатить", callback_data=f"admin_pay_{withdrawal_id}")],
        [InlineKeyboardButton(text=f"{E_REJECT} Отклонить", callback_data=f"admin_reject_w_{withdrawal_id}")],
        [InlineKeyboardButton(text=f"{E_BACK} К заявкам", callback_data="admin_withdrawals")],
    ])


def admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{E_BACK} Админ меню", callback_data="admin_menu")],
    ])
    
