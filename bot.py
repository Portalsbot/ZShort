import os
import sys
import time
import asyncio
import secrets
from pyrogram import Client, filters, idle
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

import config
from database import (
    init_db, get_setting, set_setting, add_or_update_user, get_user,
    set_premium, is_user_premium, DATABASE_NAME
)
import aiosqlite
from helpers import to_small_caps, btn, paginate_elements, auto_delete_task

app = Client(
    "ZShortBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

def is_owner_filter(_, __, message: Message):
    return message.from_user and message.from_user.id == config.OWNER_ID

is_owner = filters.create(is_owner_filter)

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
            btn(f"👑 ᴏᴡɴᴇʀ ({config.OWNER_LABEL})", url=config.OWNER_LINK),
            btn(f"💻 ᴅᴇᴠ ({config.DEV_LABEL})", url=config.DEV_LINK)
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

    # Check Maintenance
    maintenance = await get_setting("maintenance", "0")
    if maintenance == "1" and user_id != config.OWNER_ID:
        text = to_small_caps("⚠️ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴀᴄᴛɪᴠᴇ. ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ʙᴀᴄᴋ ʟᴀᴛᴇʀ!")
        return await message.reply_text(f"<blockquote>{text}</blockquote>")

    text_parts = message.text.split()
    
    # Deep-link parameter handling (/start file_xxxx)
    if len(text_parts) > 1:
        param = text_parts[1]
        
        # Check Force-Sub
        fsub_channel = int(await get_setting("fsub_channel", "0"))
        is_vip = await is_user_premium(user_id)
        if fsub_channel != 0 and not is_vip and user_id != config.OWNER_ID:
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
            
            if f_row["is_premium"] and not is_vip and user_id != config.OWNER_ID:
                vip_alert = to_small_caps("💎 ᴛʜɪs ғɪʟᴇ ɪs ᴇxᴄʟᴜsɪᴠᴇ ᴛᴏ ᴠɪᴘ ᴍᴇᴍʙᴇʀs.\\nᴜsᴇ /plan ᴏʀ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ᴛᴏ ᴜᴘɢʀᴀᴅᴇ!")
                return await message.reply_text(f"<blockquote>{vip_alert}</blockquote>")
            
            protect = (await get_setting("protect_content", "1")) == "1"
            copied = await client.copy_message(
                chat_id=user_id,
                from_chat_id=config.DB_CHANNEL,
                message_id=f_row["db_msg_id"],
                protect_content=protect
            )
            
            # Auto-Delete Schedule
            auto_del_secs = int(await get_setting("auto_delete", "600"))
            if auto_del_secs > 0:
                timer_msg = await message.reply_text(
                    to_small_caps(f"⏳ ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ {auto_del_secs // 60} ᴍɪɴᴜᴛᴇs!")
                )
                asyncio.create_task(auto_delete_task(client, user_id, [copied.id, timer_msg.id], auto_del_secs))
            return

    # Regular Menu
    banner_url = await get_setting("image_url", config.DEFAULT_IMAGE)
    start_text = await get_setting("start_text")
    footer_text = await get_setting("footer_text")
    caption = f"{start_text}\\n\\n<i>{footer_text}</i>"

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
        caption = f"{start_text}\\n\\n<i>{footer_text}</i>"
        try:
            await query.message.edit_caption(caption=caption, reply_markup=main_start_markup())
        except Exception:
            await query.message.edit_text(text=caption, reply_markup=main_start_markup())

    elif data == "cb_about":
        about_text = await get_setting("about_text")
        info = (
            f"{about_text}\\n\\n"
            f"👑 <b>ᴏᴡɴᴇʀ:</b> <a href='{config.OWNER_LINK}'>{config.OWNER_LABEL}</a>\\n"
            f"💻 <b>ᴅᴇᴠ:</b> <a href='{config.DEV_LINK}'>{config.DEV_LABEL}</a>"
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
            f"<b>💎 ᴠɪᴘ ᴍᴇᴍʙᴇʀsʜɪᴘ ʙᴇɴᴇғɪᴛs:</b>\\n\\n"
            f"<blockquote>"
            f"• ᴢᴇʀᴏ ᴀᴅs & sʜᴏʀᴛᴇɴᴇʀs\\n"
            f"• ɴᴏ ғᴏʀᴄᴇ-sᴜʙsᴄʀɪʙᴇ ʙᴀʀʀɪᴇʀs\\n"
            f"• ᴜɴʟɪᴍɪᴛᴇᴅ ᴠɪᴘ-ᴏɴʟʏ ғɪʟᴇ ᴀᴄᴄᴇss\\n"
            f"• ᴜʟᴛʀᴀ-ʜɪɢʜ sᴘᴇᴇᴅ ᴅᴏᴡɴʟᴏᴀᴅs"
            f"</blockquote>\\n\\n"
            f"ᴄᴏɴᴛᴀᴄᴛ <a href='{config.OWNER_LINK}'>{config.OWNER_LABEL}</a> ᴛᴏ ɢᴇᴛ ᴠɪᴘ!"
        )
        try:
            await query.message.edit_caption(caption=vip_text, reply_markup=back_close_markup("cb_start"))
        except Exception:
            await query.message.edit_text(text=vip_text, reply_markup=back_close_markup("cb_start"))

    # Collections
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
        msg = f"<b>{head}</b>\\n\\n<blockquote>" + to_small_caps("ᴄʟɪᴄᴋ ᴀɴʏ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴏᴘᴇɴ:") + "</blockquote>"
        try:
            await query.message.edit_caption(caption=msg, reply_markup=InlineKeyboardMarkup(kbd))
        except Exception:
            await query.message.edit_text(text=msg, reply_markup=InlineKeyboardMarkup(kbd))

    # VIP Duration Selector
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

    copied = await replied.copy(config.DB_CHANNEL)
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
        f"<b>{to_small_caps(badge)} ɢᴇɴᴇʀᴀᴛᴇᴅ!</b>\\n\\n"
        f"<blockquote>📁 <b>{to_small_caps('ɴᴀᴍᴇ')}:</b> {fname}\\n"
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
        f"<b>ᴜsᴇʀ ɪɴғᴏʀᴍᴀᴛɪᴏɴ:</b>\\n\\n"
        f"<blockquote>"
        f"🆔 <b>ɪᴅ:</b> <code>{u['user_id']}</code>\\n"
        f"👤 <b>ᴜsᴇʀɴᴀᴍᴇ:</b> @{u['username']}\\n"
        f"💎 <b>ᴠɪᴘ ᴀᴄᴛɪᴠᴇ:</b> {is_vip}\\n"
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

# ==================== RUNNER ====================
async def main():
    await init_db()
    print("Database Initialized.")
    await app.start()
    print("ZShort Bot is Online & Running smoothly!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
