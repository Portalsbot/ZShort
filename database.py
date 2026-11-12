import aiosqlite
import time
from config import DATABASE_NAME

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Users Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_at INTEGER,
                is_premium INTEGER DEFAULT 0,
                premium_until INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                downloads INTEGER DEFAULT 0
            )
        """)
        # Files Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                db_msg_id INTEGER,
                file_name TEXT,
                file_type TEXT,
                is_premium INTEGER DEFAULT 0,
                created_at INTEGER
            )
        """)
        # Collections Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                collection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at INTEGER
            )
        """)
        # Collection Items Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS collection_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER,
                item_title TEXT,
                item_link TEXT,
                FOREIGN KEY (collection_id) REFERENCES collections(collection_id) ON DELETE CASCADE
            )
        """)
        # Settings Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Default Settings
        defaults = [
            ("image_url", "https://envs.sh/default.jpg"),
            ("start_text", "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴢsʜᴏʀᴛ!\\n\\n<blockquote>ᴘᴏᴡᴇʀғᴜʟ ғɪʟᴇ sʜᴀʀɪɴɢ & ᴄᴏʟʟᴇᴄᴛɪᴏɴs ᴇɴɢɪɴᴇ. ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ.</blockquote>"),
            ("about_text", "<b>ᴢsʜᴏʀᴛ sᴛᴏʀᴇ ᴠ3.0</b>\\n\\n<blockquote>ʙᴜɪʟᴛ ғᴏʀ ᴜʟᴛʀᴀ-ғᴀsᴛ, sᴇᴄᴜʀᴇ ᴀɴᴅ ᴇʟᴇɢᴀɴᴛ ғɪʟᴇ sʜᴀʀɪɴɢ.</blockquote>"),
            ("help_text", "<b>ʜᴏᴡ ᴛᴏ ᴜsᴇ:</b>\\n\\n1. ᴄʟɪᴄᴋ ᴀɴʏ sʜᴀʀᴇᴅ ʟɪɴᴋ ᴛᴏ ɢᴇᴛ ғɪʟᴇs.\\n2. ᴜsᴇ /collection ᴛᴏ ʙʀᴏᴡsᴇ ᴘᴀᴄᴋs.\\n3. ᴄᴏɴᴛᴀᴄᴛ sᴜᴘᴘᴏʀᴛ ғᴏʀ ᴠɪᴘ ᴀᴄᴄᴇss."),
            ("footer_text", "⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴢsʜᴏʀᴛ"),
            ("auto_delete", "600"),  # 10 minutes in seconds
            ("maintenance", "0"),
            ("protect_content", "1"),
            ("fsub_channel", "0")
        ]
        for k, v in defaults:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        await db.commit()

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def add_or_update_user(user_id: int, username: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, joined_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = ?
        """, (user_id, username, int(time.time()), username))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as c:
            return await c.fetchone()

async def set_premium(user_id: int, duration_seconds: int):
    expiry = int(time.time()) + duration_seconds
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (expiry, user_id))
        await db.commit()

async def is_user_premium(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    if user['is_premium']:
        if user['premium_until'] > int(time.time()):
            return True
        else:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute("UPDATE users SET is_premium = 0 WHERE user_id = ?", (user_id,))
                await db.commit()
    return False
