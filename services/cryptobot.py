"""
Сервис для создания чеков через CryptoBot API
Документация: https://help.crypt.bot/crypto-pay-api
"""
import aiohttp
import logging
from config import CRYPTOBOT_TOKEN

logger = logging.getLogger(__name__)

CRYPTOBOT_API = "https://pay.crypt.bot/api"


async def create_invoice(amount: float, currency: str, description: str = "Выплата") -> dict:
    """Создаёт чек (invoice) в CryptoBot"""
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    payload = {
        "asset": currency,
        "amount": str(round(amount, 8)),
        "description": description,
        "paid_btn_name": "callback",
        "paid_btn_url": "https://t.me/",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTOBOT_API}/createInvoice",
                headers=headers,
                json=payload
            ) as resp:
                data = await resp.json()

        if data.get("ok"):
            invoice = data["result"]
            return {
                "success": True,
                "invoice_id": invoice["invoice_id"],
                "pay_url": invoice["pay_url"],
                "bot_invoice_url": invoice.get("bot_invoice_url", invoice["pay_url"]),
            }
        else:
            error = data.get("error", {}).get("name", "Unknown error")
            logger.error(f"CryptoBot error: {data}")
            return {"success": False, "error": error}

    except Exception as e:
        logger.error(f"CryptoBot request failed: {e}")
        return {"success": False, "error": str(e)}


async def get_balance() -> dict:
    """Получает баланс CryptoBot кошелька"""
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CRYPTOBOT_API}/getBalance",
                headers=headers
            ) as resp:
                data = await resp.json()

        if data.get("ok"):
            return {"success": True, "balances": data["result"]}
        else:
            return {"success": False, "error": data.get("error", {}).get("name")}
    except Exception as e:
        return {"success": False, "error": str(e)}
