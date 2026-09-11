import os

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Твой Telegram ID (узнать можно у @userinfobot)
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# CryptoBot API токен (получить у @CryptoBot -> My Apps)
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "YOUR_CRYPTOBOT_TOKEN_HERE")

# Username поддержки (без @)
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "support_username")

# Цена за 1 аккаунт (в рублях/USDT — как договоришься)
PRICE_PER_ACCOUNT = float(os.getenv("PRICE_PER_ACCOUNT", "50"))

# Минимальная сумма вывода
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "100"))

# Валюта для выплат (USDT, TON, BTC...)
CRYPTO_CURRENCY = os.getenv("CRYPTO_CURRENCY", "USDT")
