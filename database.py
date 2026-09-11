import aiosqlite
import logging
from datetime import datetime

DB_PATH = "bot_database.db"
logger = logging.getLogger(__name__)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance REAL DEFAULT 0.0,
                total_submitted INTEGER DEFAULT 0,
                total_earned REAL DEFAULT 0.0,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                session_data TEXT,
                submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                price REAL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                crypto_check TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # Дефолтная цена если не задана
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('price_per_account', '50')"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                phone TEXT,
                user_id INTEGER,
                phone_code_hash TEXT,
                session_string TEXT,
                requires_2fa INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        await db.commit()
    logger.info("База данных инициализирована")


# ========== USERS ==========

async def get_or_create_user(user_id: int, username: str = None, full_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                (user_id, username, full_name)
            )
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
        return user


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users ORDER BY total_submitted DESC") as cursor:
            return await cursor.fetchall()


async def update_user_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?",
            (amount, amount if amount > 0 else 0, user_id)
        )
        await db.commit()


async def deduct_user_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


# ========== ACCOUNTS ==========

async def create_account(user_id: int, phone: str, price: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO accounts (user_id, phone, price) VALUES (?, ?, ?)",
            (user_id, phone, price)
        )
        await db.commit()
        return cursor.lastrowid


async def get_account(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)) as cursor:
            return await cursor.fetchone()


async def get_all_accounts():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.*, u.username, u.full_name
            FROM accounts a
            LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY a.submitted_at DESC
        """) as cursor:
            return await cursor.fetchall()


async def get_user_accounts(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY submitted_at DESC",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def update_account_status(account_id: int, status: str, session_data: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if session_data:
            await db.execute(
                "UPDATE accounts SET status = ?, session_data = ? WHERE id = ?",
                (status, session_data, account_id)
            )
        else:
            await db.execute(
                "UPDATE accounts SET status = ? WHERE id = ?",
                (status, account_id)
            )
        if status == 'approved':
            row = await db.execute("SELECT user_id, price FROM accounts WHERE id = ?", (account_id,))
            acc = await row.fetchone()
            if acc:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, total_submitted = total_submitted + 1 WHERE user_id = ?",
                    (acc[1], acc[1], acc[0])
                )
        await db.commit()


# ========== PENDING CODES ==========

async def save_pending_code(account_id: int, phone: str, user_id: int,
                             phone_code_hash: str, session_string: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_codes WHERE user_id = ?", (user_id,))
        await db.execute(
            "INSERT INTO pending_codes (account_id, phone, user_id, phone_code_hash, session_string) VALUES (?, ?, ?, ?, ?)",
            (account_id, phone, user_id, phone_code_hash, session_string)
        )
        await db.commit()


async def get_pending_code(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM pending_codes WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def set_pending_2fa(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pending_codes SET requires_2fa = 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def delete_pending_code(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_codes WHERE user_id = ?", (user_id,))
        await db.commit()


# ========== WITHDRAWALS ==========

async def create_withdrawal(user_id: int, amount: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO withdrawals (user_id, amount) VALUES (?, ?)",
            (user_id, amount)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_withdrawals():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT w.*, u.username, u.full_name
            FROM withdrawals w
            LEFT JOIN users u ON w.user_id = u.user_id
            WHERE w.status = 'pending'
            ORDER BY w.created_at ASC
        """) as cursor:
            return await cursor.fetchall()


async def update_withdrawal(withdrawal_id: int, status: str, crypto_check: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if crypto_check:
            await db.execute(
                "UPDATE withdrawals SET status = ?, crypto_check = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, crypto_check, withdrawal_id)
            )
        else:
            await db.execute(
                "UPDATE withdrawals SET status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, withdrawal_id)
            )
        await db.commit()


async def get_price() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'price_per_account'") as c:
            row = await c.fetchone()
            return float(row[0]) if row else 50.0


async def set_price(price: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('price_per_account', ?)",
            (str(price),)
        )
        await db.commit()


async def get_bot_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM accounts") as c:
            total_accounts = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM accounts WHERE status = 'approved'") as c:
            approved_accounts = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM accounts WHERE status = 'pending'") as c:
            pending_accounts = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(balance) FROM users") as c:
            total_balance = (await c.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'") as c:
            pending_withdrawals = (await c.fetchone())[0]
    return {
        "total_users": total_users,
        "total_accounts": total_accounts,
        "approved_accounts": approved_accounts,
        "pending_accounts": pending_accounts,
        "total_balance": total_balance,
        "pending_withdrawals": pending_withdrawals,
    }
