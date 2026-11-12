import os
import sys
import re
import time
import asyncio
import secrets
from typing import List, Tuple
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.errors import UserNotParticipant
from dotenv import load_dotenv
import aiosqlite

load_dotenv()

# ==================== CONFIGURATION ====================
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "0"))
PORT = int(os.environ.get("PORT", "8080"))

OWNER_LINK = "https://t.me/reactivehcl"
OWNER_LABEL = "ʜᴄʟ"
DEV_LINK = "https://t.me/just_astha"
DEV_LABEL = "ᴀsᴛʜᴀ"

DEFAULT_IMAGE = os.environ.get("DEFAULT_IMAGE", "https://envs.sh/default.jpg")
DATABASE_NAME = "zshort_bot.db"

app = Client(
    "ZShortBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def is_owner_filter(_, __, message: Message):
    return message.from_user and message.from_user.id == OWNER_ID

is_owner = filters.create(is_owner_filter)

# ==================== HELPERS & FORMATTING ====================
CHARMAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ',
    'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
    'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ'
}

def to_small_caps(text: str) -> str:
    """Converts text to Small Caps while keeping slash commands and URLs raw & clickable."""
    if not text:
        return ""
    tokens = re.split(r'(\s+)', text)
    transformed = []
    for t in tokens:
        if (t.startswith('/') or t.startswith('http://') or t.startswith('https://') 
            or 't.me/' in t or t.startswith('@') or t.startswith('#') or t.startswith('<')):
            transformed.append(t)
        else:
            transformed.append("".join(CHARMAP.get(c.lower(), c) if c.isalpha() else c for c in t))
    return "".join(transformed)

def btn(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=to_small_caps(text), callback_data=callback_data, url=url)

def paginate_elements(items: List[Tuple[int, str]], page: int = 1, page_size: int = 5):
    total_items = len(items)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * page_size
    page_items = items[start_idx:start_idx + page_size]
    
    keyboard = []
    for item_id, item_name in page_items:
        keyboard.append([InlineKeyboardButton(text=to_small_caps(f"📂 {item_name}"), callback_data=f"col_open_{item_id}")])
    
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text=to_small_caps("« ᴘʀᴇᴠ"), callback_data=f"col_page_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=to_small_caps(f"• {page}/{total_pages} •"), callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text=to_small_caps("ɴᴇxᴛ »"), callback_data=f"col_page_{page+1}"))
        
    keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(text=to_small_caps("❌ ᴄʟᴏsᴇ"), callback_data="close_msg")])
    return InlineKeyboardMarkup(keyboard)

async def auto_delete_task(bot, chat_id: int, message_ids: list, delay_seconds: int):
    try:
        await asyncio.sleep(delay_seconds)
        for msg_id in message_ids:
            try:
                await bot.delete_messages(chat_id=chat_id, message_ids=msg_id)
            except Exception:
                pass
    except Exception:
        pass

# ==================== DATABASE ====================
async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                collection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS collection_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER,
                item_title TEXT,
                item_link TEXT,
                FOREIGN KEY (collection_id) REFERENCES collections(collection_id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        defaults = [
            ("image_url", DEFAULT_IMAGE),
            ("start_text", "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴢsʜᴏʀᴛ!\n\n<blockquote>ᴘᴏᴡᴇʀғᴜʟ ғɪʟᴇ sʜᴀʀɪɴɢ & ᴄᴏʟʟᴇᴄᴛɪᴏɴs ᴇɴɢɪɴᴇ. ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ.</blockquote>"),
            ("about_text", "<b>ᴢsʜᴏʀᴛ sᴛᴏʀᴇ ᴠ3.0</b>\n\n<blockquote>ʙᴜɪʟᴛ ғᴏʀ ᴜʟᴛʀᴀ-ғᴀsᴛ, sᴇᴄᴜʀᴇ ᴀɴᴅ ᴇʟᴇɢᴀɴᴛ ғɪʟᴇ sʜᴀʀɪɴɢ.</blockquote>"),
            ("help_text", "<b>ʜᴏᴡ ᴛᴏ ᴜsᴇ:</b>\n\n1. ᴄʟɪᴄᴋ ᴀɴʏ sʜᴀʀᴇᴅ ʟɪɴᴋ ᴛᴏ ɢᴇᴛ ғɪʟᴇs.\n2. ᴜsᴇ /collections ᴛᴏ ʙʀᴏᴡsᴇ ᴘᴀᴄᴋs.\n3. ᴄᴏɴᴛᴀᴄᴛ sᴜᴘᴘᴏʀᴛ ғᴏʀ ᴠɪᴘ ᴀᴄᴄᴇss."),
            ("footer_text", "⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴢsʜᴏʀᴛ"),
            ("auto_delete", "600"),
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

# ==================== DYNAMIC KEYBOARDS ====================
def main_start_markup():
    return InlineKeyboardMarkup([
        [
            btn("ℹ️ ᴀʙᴏᴜᴛ", callback_data="cb_about"),
            btn("❓ ʜᴇʟᴘ", callback_data="cb_help")
        ],
        [
            btn("📂 ᴄᴏʟʟᴇᴄᴛɪᴏɴs", callback_data="col_page_1"),
            btn("💎 ᴠɪᴘ ᴘʟᴀɴ", callback_data="cb_vip")
        ],
        [
            btn(f"👑 ᴏᴡɴᴇʀ ({OWNER_LABEL})", url=OWNER_LINK),
            btn(f"💻 ᴅᴇᴠ ({DEV_LABEL})", url=DEV_LINK)
        ],
        [
            btn("❌ ᴄʟᴏsᴇ", callback_data="close_msg")
        ]
    ])

def back_close_markup(back_to: str = "cb_start"):
    return InlineKeyboardMarkup([
        [
            btn("« ʙᴀᴄᴋ", callback_data=back_to),
            btn("❌ ᴄʟᴏsᴇ", callback_data="close_msg")
        ]
    ])

# ==================== CORE /START & RETRIEVAL ====================
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    await add_or_update_user(user_id, username)

    maintenance = await get_setting("maintenance", "0")
    if maintenance == "1" and user_id != OWNER_ID:
        text = to_small_caps("⚠️ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴀᴄᴛɪᴠᴇ. ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ʙᴀᴄᴋ ʟᴀᴛᴇʀ!")
        return await message.reply_text(f"<blockquote>{text}</blockquote>")

    text_parts = message.text.split()
    if len(text_parts) > 1:
        param = text_parts[1]
        
        # Check Force Sub
        fsub_channel = int(await get_setting("fsub_channel", "0"))
        is_vip = await is_user_premium(user_id)
        if fsub_channel != 0 and not is_vip and user_id != OWNER_ID:
            try:
                await client.get_chat_member(chat_id=fsub_channel, user_id=user_id)
            except UserNotParticipant:
                invite = await client.create_chat_invite_link(fsub_channel)
                fsub_markup = InlineKeyboardMarkup([
                    [btn("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=invite.invite_link)],
                    [btn("🔄 ᴛʀʏ ᴀɢᴀɪɴ", url=f"https://t.me/{client.me.username}?start={param}")]
                ])
                quote = to_small_caps("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴀᴄᴄᴇss ᴛʜɪs ғɪʟᴇ!")
                return await message.reply_text(f"<blockquote>{quote}</blockquote>", reply_markup=fsub_markup)
            except Exception:
                pass

        if param.startswith("file_"):
            file_key = param.replace("file_", "")
            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM files WHERE file_id = ?", (file_key,)) as c:
                    f_row = await c.fetchone()
            
            if not f_row:
                return await message.reply_text(to_small_caps("❌ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ᴏʀ ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ."))
            
            if f_row["is_premium"] and not is_vip and user_id != OWNER_ID:
                vip_alert = to_small_caps("💎 ᴛʜɪs ғɪʟᴇ ɪs ᴇxᴄʟᴜsɪᴠᴇ ᴛᴏ ᴠɪᴘ ᴍᴇᴍʙᴇʀs.\nᴜsᴇ /vip ᴏʀ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ᴛᴏ ᴜᴘɢʀᴀᴅᴇ!")
                return await message.reply_text(f"<blockquote>{vip_alert}</blockquote>")
            
            protect = (await get_setting("protect_content", "1")) == "1"
            copied = await client.copy_message(
                chat_id=user_id,
                from_chat_id=DB_CHANNEL,
                message_id=f_row["db_msg_id"],
                protect_content=protect
            )
            
            auto_del_secs = int(await get_setting("auto_delete", "600"))
            if auto_del_secs > 0:
                timer_msg = await message.reply_text(
                    to_small_caps(f"⏳ ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {auto_del_secs // 60} ᴍɪɴᴜᴛᴇs!")
                )
                asyncio.create_task(auto_delete_task(client, user_id, [copied.id, timer_msg.id], auto_del_secs))
            return

    banner_url = await get_setting("image_url", DEFAULT_IMAGE)
    start_text = await get_setting("start_text")
    footer_text = await get_setting("footer_text")
    caption = f"{start_text}\n\n<i>{footer_text}</i>"

    try:
        await message.reply_photo(photo=banner_url, caption=caption, reply_markup=main_start_markup())
    except Exception:
        await message.reply_text(caption, reply_markup=main_start_markup())

# ==================== CALLBACK NAVIGATION ====================
@app.on_callback_query()
async def callback_router(client: Client, query: CallbackQuery):
    data = query.data

    if data == "close_msg":
        return await query.message.delete()

    elif data == "cb_start":
        start_text = await get_setting("start_text")
        footer_text = await get_setting("footer_text")
        caption = f"{start_text}\n\n<i>{footer_text}</i>"
        try:
            await query.message.edit_caption(caption=caption, reply_markup=main_start_markup())
        except Exception:
            await query.message.edit_text(text=caption, reply_markup=main_start_markup())

    elif data == "cb_about":
        about_text = await get_setting("about_text")
        info = (
            f"{about_text}\n\n"
            f"👑 <b>ᴏᴡɴᴇʀ:</b> <a href='{OWNER_LINK}'>{OWNER_LABEL}</a>\n"
            f"💻 <b>ᴅᴇᴠ:</b> <a href='{DEV_LINK}'>{DEV_LABEL}</a>"
        )
        try:
            await query.message.edit_caption(caption=info, reply_markup=back_close_markup("cb_start"))
        except Exception:
            await query.message.edit_text(text=info, reply_markup=back_close_markup("cb_start"))

    elif data == "cb_help":
        help_text = await get_setting("help_text")
        try:
            await query.message.edit_caption(caption=help_text, reply_markup=back_close_markup("cb_start"))
        except Exception:
            await query.message.edit_text(text=help_text, reply_markup=back_close_markup("cb_start"))

    elif data == "cb_vip":
        vip_text = (
            f"<b>💎 ᴠɪᴘ ᴍᴇᴍʙᴇʀsʜɪᴘ ʙᴇɴᴇғɪᴛs:</b>\n\n"
            f"<blockquote>"
            f"• ᴢᴇʀᴏ ᴀᴅs & sʜᴏʀᴛᴇɴᴇʀs\n"
            f"• ɴᴏ ғᴏʀᴄᴇ-sᴜʙsᴄʀɪʙᴇ ʙᴀʀʀɪᴇʀs\n"
            f"• ᴜɴʟɪᴍɪᴛᴇᴅ ᴠɪᴘ-ᴏɴʟʏ ғɪʟᴇ ᴀᴄᴄᴇss\n"
            f"• ᴜʟᴛʀᴀ-ʜɪɢʜ sᴘᴇᴇᴅ ᴅᴏᴡɴʟᴏᴀᴅs"
            f"</blockquote>\n\n"
            f"ᴄᴏɴᴛᴀᴄᴛ <a href='{OWNER_LINK}'>{OWNER_LABEL}</a> ᴛᴏ ɢᴇᴛ ᴠɪᴘ!"
        )
        try:
            await query.message.edit_caption(caption=vip_text, reply_markup=back_close_markup("cb_start"))
        except Exception:
            await query.message.edit_text(text=vip_text, reply_markup=back_close_markup("cb_start"))

    elif data.startswith("col_page_"):
        page = int(data.split("_")[2])
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT collection_id, name FROM collections ORDER BY collection_id DESC") as c:
                cols = await c.fetchall()
        markup = paginate_elements(cols, page=page, page_size=5)
        text = to_small_caps("📁 sᴇʟᴇᴄᴛ ᴀ ᴄᴏʟʟᴇᴄᴛɪᴏɴ ᴛᴏ ʙʀᴏᴡsᴇ ɪᴛs ғɪʟᴇs:")
        try:
            await query.message.edit_caption(caption=f"<blockquote>{text}</blockquote>", reply_markup=markup)
        except Exception:
            await query.message.edit_text(text=f"<blockquote>{text}</blockquote>", reply_markup=markup)

    elif data.startswith("col_open_"):
        cid = int(data.split("_")[2])
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT name FROM collections WHERE collection_id = ?", (cid,)) as c:
                crow = await c.fetchone()
            async with db.execute("SELECT item_title, item_link FROM collection_items WHERE collection_id = ?", (cid,)) as c:
                items = await c.fetchall()
        
        cname = crow["name"] if crow else "ᴄᴏʟʟᴇᴄᴛɪᴏɴ"
        kbd = []
        for itm in items:
            kbd.append([InlineKeyboardButton(text=to_small_caps(f"🎬 {itm['item_title']}"), url=itm["item_link"])])
        kbd.append([btn("« ʙᴀᴄᴋ", callback_data="col_page_1"), btn("❌ ᴄʟᴏsᴇ", callback_data="close_msg")])

        head = to_small_caps(f"📂 ᴄᴏʟʟᴇᴄᴛɪᴏɴ: {cname}")
        msg = f"<b>{head}</b>\n\n<blockquote>" + to_small_caps("ᴄʟɪᴄᴋ ᴀɴʏ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴏᴘᴇɴ:") + "</blockquote>"
        try:
            await query.message.edit_caption(caption=msg, reply_markup=InlineKeyboardMarkup(kbd))
        except Exception:
            await query.message.edit_text(text=msg, reply_markup=InlineKeyboardMarkup(kbd))

    elif data.startswith("vipdur_"):
        _, uid, secs = data.split("_")
        await set_premium(int(uid), int(secs))
        await query.answer("✅ ᴠɪᴘ ɢʀᴀɴᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!", show_alert=True)
        await query.message.edit_text(to_small_caps(f"✅ ᴠɪᴘ ᴀᴄᴄᴇss ɢʀᴀɴᴛᴇᴅ ᴛᴏ ᴜsᴇʀ {uid}!"))

# ==================== FILE STORAGE COMMANDS ====================
@app.on_message(filters.command(["upload", "link", "premium_link"]) & filters.private & is_owner)
async def upload_file_handler(client: Client, message: Message):
    is_prem = 1 if "premium" in message.command[0] else 0
    replied = message.reply_to_message
    if not replied or not (replied.document or replied.video or replied.audio or replied.photo):
        return await message.reply_text(to_small_caps("⚠️ ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴠɪᴅᴇᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ, ᴏʀ ᴀᴜᴅɪᴏ!"))

    copied = await replied.copy(DB_CHANNEL)
    file_key = secrets.token_urlsafe(8)
    
    fname = "ᴍᴇᴅɪᴀ"
    if replied.document and replied.document.file_name:
        fname = replied.document.file_name
    elif replied.video and replied.video.file_name:
        fname = replied.video.file_name

    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO files (file_id, db_msg_id, file_name, file_type, is_premium, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (file_key, copied.id, fname, "media", is_prem, int(time.time())))
        await db.commit()

    bot_user = (await client.get_me()).username
    share_url = f"https://t.me/{bot_user}?start=file_{file_key}"
    badge = "💎 ᴠɪᴘ ʟɪɴᴋ" if is_prem else "⚡ ғɪʟᴇ ʟɪɴᴋ"
    
    res_text = (
        f"<b>{to_small_caps(badge)} ɢᴇɴᴇʀᴀᴛᴇᴅ!</b>\n\n"
        f"<blockquote>📁 <b>{to_small_caps('ɴᴀᴍᴇ')}:</b> {fname}\n"
        f"🔗 <b>ʟɪɴᴋ:</b> <code>{share_url}</code></blockquote>"
    )
    markup = InlineKeyboardMarkup([
        [btn("📋 sʜᴀʀᴇ ʟɪɴᴋ", url=f"https://t.me/share/url?url={share_url}")],
        [btn("❌ ᴄʟᴏsᴇ", callback_data="close_msg")]
    ])
    await message.reply_text(res_text, reply_markup=markup)

# ==================== COLLECTIONS COMMANDS ====================
@app.on_message(filters.command("collections") & filters.private)
async def collections_cmd(client: Client, message: Message):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT collection_id, name FROM collections ORDER BY collection_id DESC") as c:
            cols = await c.fetchall()
    markup = paginate_elements(cols, page=1, page_size=5)
    text = to_small_caps("📁 sᴇʟᴇᴄᴛ ᴀ ᴄᴏʟʟᴇᴄᴛɪᴏɴ ᴛᴏ ʙʀᴏᴡsᴇ ɪᴛs ғɪʟᴇs:")
    await message.reply_text(f"<blockquote>{text}</blockquote>", reply_markup=markup)

@app.on_message(filters.command("new_collection") & filters.private & is_owner)
async def new_collection_cmd(client: Client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text(to_small_caps("ᴜsᴀɢᴇ: /new_collection [name]"))
    name = args[1].strip()
    try:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("INSERT INTO collections (name, created_at) VALUES (?, ?)", (name, int(time.time())))
            await db.commit()
        await message.reply_text(to_small_caps(f"✅ ᴄᴏʟʟᴇᴄᴛɪᴏɴ '{name}' ᴄʀᴇᴀᴛᴇᴅ!"))
    except Exception as e:
        await message.reply_text(to_small_caps(f"❌ ᴇʀʀᴏʀ: {e}"))

# ==================== VIP MANAGEMENT ====================
@app.on_message(filters.command("premium") & filters.private & is_owner)
async def premium_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text(to_small_caps("ᴜsᴀɢᴇ: /premium [user_id]"))
    
    uid = args[1]
    markup = InlineKeyboardMarkup([
        [btn("1 ᴡᴇᴇᴋ", callback_data=f"vipdur_{uid}_{7*86400}"), btn("1 ᴍᴏɴᴛʜ", callback_data=f"vipdur_{uid}_{30*86400}")],
        [btn("3 ᴍᴏɴᴛʜs", callback_data=f"vipdur_{uid}_{90*86400}"), btn("6 ᴍᴏɴᴛʜs", callback_data=f"vipdur_{uid}_{180*86400}")],
        [btn("1 ʏᴇᴀʀ", callback_data=f"vipdur_{uid}_{365*86400}")],
        [btn("❌ ᴄᴀɴᴄᴇʟ", callback_data="close_msg")]
    ])
    await message.reply_text(to_small_caps(f"💎 sᴇʟᴇᴄᴛ ᴠɪᴘ ᴅᴜʀᴀᴛɪᴏɴ ғᴏʀ ᴜsᴇʀ {uid}:"), reply_markup=markup)

@app.on_message(filters.command("user_info") & filters.private & is_owner)
async def user_info_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text(to_small_caps("ᴜsᴀɢᴇ: /user_info [user_id]"))
    u = await get_user(int(args[1]))
    if not u:
        return await message.reply_text(to_small_caps("❌ ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ."))
    
    is_vip = "ʏᴇs" if u["is_premium"] and u["premium_until"] > time.time() else "ɴᴏ"
    info = (
        f"<b>ᴜsᴇʀ ɪɴғᴏʀᴍᴀᴛɪᴏɴ:</b>\n\n"
        f"<blockquote>"
        f"🆔 <b>ɪᴅ:</b> <code>{u['user_id']}</code>\n"
        f"👤 <b>ᴜsᴇʀɴᴀᴍᴇ:</b> @{u['username']}\n"
        f"💎 <b>ᴠɪᴘ ᴀᴄᴛɪᴠᴇ:</b> {is_vip}\n"
        f"🚫 <b>ʙᴀɴɴᴇᴅ:</b> {'ʏᴇs' if u['is_banned'] else 'ɴᴏ'}"
        f"</blockquote>"
    )
    await message.reply_text(info)

# ==================== LIVE CUSTOMIZATION ====================
@app.on_message(filters.command("set_image") & filters.private & is_owner)
async def set_image_cmd(client: Client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text(to_small_caps("ᴜsᴀɢᴇ: /set_image [image_url]"))
    await set_setting("image_url", args[1].strip())
    await message.reply_text(to_small_caps("✅ ɢʟᴏʙᴀʟ ʙᴀɴɴᴇʀ ᴜᴘᴅᴀᴛᴇᴅ!"))

@app.on_message(filters.command("autodelete") & filters.private & is_owner)
async def autodelete_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text(to_small_caps("ᴜsᴀɢᴇ: /autodelete [seconds] (e.g. 600 for 10 mins)"))
    await set_setting("auto_delete", args[1])
    await message.reply_text(to_small_caps(f"✅ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇʀ sᴇᴛ ᴛᴏ {int(args[1])//60} ᴍɪɴᴜᴛᴇs!"))

@app.on_message(filters.command("ping") & filters.private)
async def ping_cmd(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 ᴘᴏɴɢ...")
    delta = round((time.time() - start) * 1000, 2)
    await msg.edit_text(to_small_caps(f"🏓 ᴘᴏɴɢ: {delta}ᴍs"), reply_markup=back_close_markup("cb_start"))

# ==================== WEB SERVER (RENDER PORT BINDING) ====================
async def web_server():
    async def handle_ping(request):
        return web.Response(text="ZShort Bot is Alive & Running Smoothly!")
    
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Render HTTP Web Server bound on port {PORT}")

# ==================== ASYNC MAIN & RESILIENT RUNNER ====================
async def main():
    await init_db()
    print("Database Initialized.")
    await web_server()
    await app.start()
    print("ZShort Bot Started Successfully on Render!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
