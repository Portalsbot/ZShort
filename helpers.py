import re
import asyncio
from typing import List, Tuple
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CHARMAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ',
    'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
    'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ'
}

def to_small_caps(text: str) -> str:
    """Converts alphabets to Small Caps while strictly keeping slash commands & URLs clickable."""
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
    keyboard.append([
        InlineKeyboardButton(text=to_small_caps("❌ ᴄʟᴏsᴇ"), callback_data="close_msg")
    ])
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
