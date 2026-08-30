import asyncio
import json
import os
import sqlite3
import re
import logging
import traceback
import aiohttp
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import io
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BusinessConnection, BusinessMessagesDeleted, ChatPermissions,
    LabeledPrice, PreCheckoutQuery, BufferedInputFile
)

TOKEN = "8933814537:AAEuDsif_-E7sXxezKtnMxiaKmZrzwVLle4"
OWNER_ID = 8297446667

DB_PATH = os.getenv("DB_PATH", "loudgram.db")
DEBUG = os.getenv("DEBUG", "1") != "0"
BANNER_PATH = os.getenv("BANNER_PATH", "").strip()

EMOJI = {
    "guide": "🎓",
    "channel": "📢",
    "newbie": "📖",
    "profile": "👤",
    "subscription": "🔐",
    "partner": "💰",
    "stars": "⭐",
    "back": "◀️",
    "home": "🏠",
    "close": "✕",
    "open": "↗️",
    "support": "🆘",
    "settings": "⚙️",
    "info": "ℹ️",
    "refresh": "🔄",
    "check": "✅",
    "cancel": "❌",
    "timezone": "🌍",
    "timezones": "📋",
    "interval": "⏱️",
    "edit": "✏️",
    "add": "➕",
    "enabled": "🟢",
    "disabled": "🔴",
    "clear": "🗑️",
    "edited": "✏️",
    "deleted": "🗑️",
    "video": "🎥",
    "photo": "🖼️",
    "file": "📎",
    "audio": "🎵",
    "voice": "🎙️",
    "saved": "💾",
    "payment": "💎",
    "upload": "📤",
    "stop": "🛑",
    "receipt": "🧾",
    "money": "💵",
    "warning": "⚠️",
    "test": "🧪",
    "mute": "🔴",
}

PREMIUM_EMOJI_IDS = {
    "guide": "5992157823838984339",
    "channel": "5875465628285931233",
    "newbie": "5877332341331857066",
    "profile": "5902335789798265487",
    "subscription": "5994495149336434048",
    "partner": "5954175920506933873",
    "stars": "5958376256788502078",
    "back": "5258236805890710909",
    "home": "5257963315258204021",
    "close": "5258476306152038031",
    "open": "5431721976769027887",
    "support": "5866185084427572234",
    "settings": "5258096772776991776",
    "info": "5879785854284599288",
    "refresh": "5346269127059196142",
    "check": "5776375003280838798",
    "cancel": "5361629691046281578",
    "timezone": "5258419835922030550",
    "timezones": "5296370519136812159",
    "interval": "5260280853841321805",
    "edit": "5334673106202010226",
    "add": "5256143829672672750",
    "enabled": "5213147006561692829",
    "disabled": "5312048833394387701",
    "clear": "5879937509579820068",
    "edited": "6039779802741739617",
    "deleted": "5870875489362513438",
    "video": "5775981206319402773",
    "photo": "5775949822993371030",
    "file": "5877332341331857066",
    "audio": "5890997763331591703",
    "voice": "5897554554894946515",
    "saved": "4947276702599349298",
    "payment": "5472250091332993630",
    "upload": "5877540355187937244",
    "stop": "5882136597259882700",
    "receipt": "5444856076954520455",
    "money": "5913638872411020778",
    "warning": "5913421113274145666",
    "test": "5411512278740640309",
    "mute": "5213208128241278928",
}

BUTTON_STYLES = {
    "main_guide": "primary",
    "main_channel": "None",
    "main_newbie": "None",
    "main_profile": "None",
    "main_subscription": "None",
    "main_partner": "None",
    "main_stars": "None",
    "useful_next": "primary",
    "useful_back": "primary",
    "useful_home": "primary",
    "newbie_copy": "primary",
    "newbie_home": "primary",
    "status_timezone": "primary",
    "status_edit": "primary",
    "status_add": "primary",
    "status_toggle_on": "success",
    "status_toggle_off": "danger",
    "nick_interval": "primary",
    "nick_edit": "primary",
    "nick_add": "primary",
    "nick_toggle_on": "success",
    "nick_toggle_off": "danger",
    "nick_clear": "danger",
    "nick_back": "primary",
    "payment": "primary",
    "support": "primary",
    "close": "danger",
    "back": "primary",
    "home": "primary",
}

def button_style(name: str, fallback: str | None = "primary") -> str | None:
    return BUTTON_STYLES.get(name, fallback)

NEWBIE_GUIDE_BUTTON_STYLE = "primary"
NEWBIE_GUIDE_EMOJI = "🎓"
NEWBIE_GUIDE_PREMIUM_EMOJI_ID = ""

def e(name: str) -> str:
    return EMOJI.get(name, "")

def pe(name: str) -> str:
    fallback = e(name)
    emoji_id = str(PREMIUM_EMOJI_IDS.get(name, "") or "").strip()
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback

BUTTONS = {
    "guide": f"{e('guide')} Чем это полезно?",
    "channel": f"{e('channel')} Канал проекта",
    "newbie": f"{e('newbie')} Гайд новичкам",
    "profile": f"{e('profile')} Мой профиль",
    "subscription": f"{e('subscription')} Подписка",
    "partner": f"{e('partner')} Партнёрка",
    "stars": f"{e('stars')} Звёзды по 1.4₽",
    "timezone": f"{e('timezone')} Узнать часовой пояс",
    "timezones": f"{e('timezones')} Часовые пояса",
    "back": f"{e('back')} Назад",
    "home": f"{e('home')} Главное меню",
    "close": f"{e('close')} Закрыть",
    "support": f"{e('support')} Поддержка",
}

def b(name: str) -> str:
    return BUTTONS.get(name, name)

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "").strip()
CRYPTOBOT_API = "https://pay.crypt.bot/api"
CRYPTO_ASSET = os.getenv("CRYPTO_ASSET", "USDT").strip().upper()
CRYPTO_PLAN_AMOUNTS = {
    "14": os.getenv("CRYPTO_PLUS_14_AMOUNT", "2.90").strip(),
    "30": os.getenv("CRYPTO_PLUS_30_AMOUNT", "5.4").strip(),
    "90": os.getenv("CRYPTO_PLUS_90_AMOUNT", "13.7").strip(),
    "180": os.getenv("CRYPTO_PLUS_180_AMOUNT", "17.77").strip(),
}

PLUS_PLANS = {
    "plus_14": {
        "title": "Plus — 14 дней",
        "description": "Plus-доступ на 14 дней",
        "days": 14,
        "stars": 200,
    },
    "plus_30": {
        "title": "Plus — 30 дней",
        "description": "Plus-доступ на 30 дней",
        "days": 30,
        "stars": 360,
    },
    "plus_90": {
        "title": "Plus — 90 дней",
        "description": "Plus-доступ на 90 дней",
        "days": 90,
        "stars": 920,
    },
    "plus_180": {
        "title": "Plus — 180 дней",
        "description": "Plus-доступ на 180 дней",
        "days": 180,
        "stars": 1200,
    },
    "plus_month_sub": {
        "title": "Plus — подписка на 30 дней",
        "description": "Plus-доступ с автоматическим продлением каждые 30 дней",
        "days": 30,
        "stars": 150,
        "subscription_period": 2592000,
    },
}

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("loudgram")

db = sqlite3.connect(DB_PATH, check_same_thread=False)

db.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    plan TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    telegram_payment_charge_id TEXT,
    updated_at INTEGER NOT NULL
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS crypto_invoices (
    invoice_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    plan_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    asset TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL,
    paid_at INTEGER
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS connections (
    connection_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_chat_id INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    can_reply INTEGER NOT NULL DEFAULT 0
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS messages (
    connection_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    sender_id INTEGER,
    sender_name TEXT,
    sender_username TEXT,
    chat_title TEXT,
    chat_username TEXT,
    chat_type TEXT,
    kind TEXT NOT NULL,
    text TEXT,
    caption TEXT,
    file_id TEXT,
    file_unique_id TEXT,
    created_at INTEGER,
    PRIMARY KEY (connection_id, chat_id, message_id)
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS time_settings (
    user_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    timezone TEXT NOT NULL DEFAULT 'UTC'
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS mutes (
    mute_id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    target_user_id INTEGER NOT NULL,
    muter_user_id INTEGER NOT NULL DEFAULT 0,
    until_ts INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'soft',
    active INTEGER NOT NULL DEFAULT 1
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS nick_settings (
    connection_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    interval_minutes INTEGER NOT NULL DEFAULT 2,
    nicks_json TEXT NOT NULL DEFAULT '[]',
    current_index INTEGER NOT NULL DEFAULT -1,
    next_change_ts INTEGER NOT NULL DEFAULT 0
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS status_settings (
    connection_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    statuses_json TEXT NOT NULL DEFAULT '[]'
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS format_settings (
    connection_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    style TEXT NOT NULL DEFAULT 'bold'
)
""")
db.commit()

try:
    cols = {row[1] for row in db.execute("PRAGMA table_info(mutes)").fetchall()}
    if "muter_user_id" not in cols:
        db.execute("ALTER TABLE mutes ADD COLUMN muter_user_id INTEGER NOT NULL DEFAULT 0")
        db.commit()
except Exception:
    log.exception("[DB] failed to migrate mutes.muter_user_id")

_existing_connections = {row[1] for row in db.execute("PRAGMA table_info(connections)").fetchall()}
if "can_reply" not in _existing_connections:
    db.execute("ALTER TABLE connections ADD COLUMN can_reply INTEGER NOT NULL DEFAULT 0")
if "business_first_name" not in _existing_connections:
    db.execute("ALTER TABLE connections ADD COLUMN business_first_name TEXT")
if "business_last_name" not in _existing_connections:
    db.execute("ALTER TABLE connections ADD COLUMN business_last_name TEXT")
db.commit()

_existing = {row[1] for row in db.execute("PRAGMA table_info(messages)").fetchall()}
for _name, _type in [
    ("sender_name", "TEXT"),
    ("sender_username", "TEXT"),
    ("chat_title", "TEXT"),
    ("chat_username", "TEXT"),
    ("chat_type", "TEXT"),
]:
    if _name not in _existing:
        db.execute(f"ALTER TABLE messages ADD COLUMN {_name} {_type}")
db.commit()

dp = Dispatcher()

def _short(value, limit=120):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"

def business_can_reply(rights) -> bool:
    if rights is None:
        return False
    value = getattr(rights, "can_reply", None)
    if value is None:
        value = getattr(rights, "reply", False)
    return bool(value)

def log_update(update):
    try:
        kind = update.event_type
        log.info("[UPDATE] id=%s type=%s", update.update_id, kind)
        if kind in {"business_message", "edited_business_message"}:
            msg = update.business_message or update.edited_business_message
            log.info(
                "[BUSINESS] connection=%s chat=%s from=%s text=%r",
                getattr(msg, "business_connection_id", None),
                getattr(getattr(msg, "chat", None), "id", None),
                getattr(getattr(msg, "from_user", None), "id", None),
                _short(getattr(msg, "text", None)),
            )
        elif kind == "business_connection":
            bc = update.business_connection
            rights = getattr(bc, "rights", None)
            log.info(
                "[CONNECTION] id=%s user=%s enabled=%s reply=%s",
                getattr(bc, "id", None),
                getattr(getattr(bc, "user", None), "id", None),
                getattr(bc, "is_enabled", None),
                business_can_reply(rights),
            )
    except Exception:
        log.exception("[DEBUG] Failed to log update")

@dp.update.outer_middleware()
async def debug_update_middleware(handler, event, data):
    log_update(event)
    try:
        result = await handler(event, data)
        log.debug("[UPDATE DONE] id=%s", getattr(event, "update_id", "?"))
        return result
    except Exception:
        log.exception("[UPDATE ERROR] id=%s", getattr(event, "update_id", "?"))
        raise

async def answer_message(message: Message, text: str, **kwargs):
    business_connection_id = getattr(message, "business_connection_id", None)
    if not business_connection_id:
        return await message.answer(text, **kwargs)

    connection = await ensure_connection(business_connection_id)
    if not connection:
        log.error("[REPLY BLOCKED] no BusinessConnection for id=%s", business_connection_id)
        return None

    user_id, user_chat_id, enabled = connection[:3]
    row = db.execute("SELECT can_reply FROM connections WHERE connection_id=?", (business_connection_id,)).fetchone()
    can_reply = bool(row[0]) if row else False

    log.info("[REPLY] connection=%s chat=%s enabled=%s can_reply=%s text=%r",
             business_connection_id, message.chat.id, enabled, can_reply, _short(text, 160))

    if not enabled:
        error = ("❌ <b>Business-подключение отключено.</b>\n\n"
                 "Откройте Telegram → Настройки → Telegram для бизнеса → "
                 "Чат-боты и заново подключите бота.")
        log.error("[REPLY BLOCKED] connection disabled: %s", business_connection_id)
        try:
            await bot.send_message(user_chat_id, error, parse_mode="HTML")
        except Exception:
            log.exception("[REPLY DIAGNOSTIC] could not notify owner")
        return None

    if not can_reply:
        log.warning("[REPLY WARNING] cached can_reply=False; attempting Business send anyway. connection=%s", business_connection_id)

    try:
        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            business_connection_id=business_connection_id,
            **kwargs,
        )
        log.info("[REPLY OK] business_connection=%s chat=%s message_id=%s",
                 business_connection_id, message.chat.id, getattr(sent, "message_id", None))
        return sent
    except Exception as exc:
        log.exception("[REPLY ERROR] connection=%s chat=%s error=%s", business_connection_id, message.chat.id, exc)
        try:
            await bot.send_message(
                user_chat_id,
                "❌ <b>Telegram отклонил ответ бота.</b>\n\n"
                f"<code>{str(exc)[:1200]}</code>\n\n"
                "Проверьте права Business-бота и перезапустите бота.",
                parse_mode="HTML",
            )
        except Exception:
            log.exception("[REPLY DIAGNOSTIC] could not notify owner")
        return None

async def answer_callback_message(call: CallbackQuery, text: str, **kwargs):
    if not call.message:
        return None

    old_message = call.message
    try:
        await old_message.delete()
        log.debug("[NAV] old callback message deleted chat=%s message=%s",
                  getattr(old_message.chat, "id", None), getattr(old_message, "message_id", None))
    except Exception as exc:
        log.debug("[NAV] could not delete old callback message: %s", exc)

    reply_markup = kwargs.get("reply_markup")
    is_back_to_menu = str(getattr(call, "data", "") or "") == "back_menu"
    if not is_back_to_menu:
        try:
            home_row = [btn(f"{e('home')} В главное меню", "back_menu", "", button_style("back", "primary"))]
            if isinstance(reply_markup, InlineKeyboardMarkup):
                rows = [list(row) for row in reply_markup.inline_keyboard]
                already_has_home = any(
                    any(getattr(button, "callback_data", None) == "back_menu" for button in row)
                    for row in rows
                )
                if not already_has_home:
                    rows.append(home_row)
                kwargs["reply_markup"] = InlineKeyboardMarkup(inline_keyboard=rows)
            else:
                kwargs["reply_markup"] = InlineKeyboardMarkup(inline_keyboard=[home_row])
        except Exception as exc:
            log.debug("[NAV] could not add home button: %s", exc)

    if getattr(old_message, "business_connection_id", None):
        return await answer_message(old_message, text, **kwargs)
    return await old_message.answer(text, **kwargs)

timezone_waiting = set()

CITY_TIMEZONES = {
    "москва": "Europe/Moscow", "moscow": "Europe/Moscow",
    "санкт-петербург": "Europe/Moscow", "санкт петербург": "Europe/Moscow", "saint petersburg": "Europe/Moscow", "st petersburg": "Europe/Moscow",
    "калининград": "Europe/Kaliningrad", "kaliningrad": "Europe/Kaliningrad",
    "минск": "Europe/Minsk", "minsk": "Europe/Minsk",
    "киев": "Europe/Kyiv", "kyiv": "Europe/Kyiv", "kiev": "Europe/Kyiv",
    "варшава": "Europe/Warsaw", "warsaw": "Europe/Warsaw",
    "берлин": "Europe/Berlin", "berlin": "Europe/Berlin",
    "париж": "Europe/Paris", "paris": "Europe/Paris",
    "лондон": "Europe/London", "london": "Europe/London",
    "лиссабон": "Europe/Lisbon", "lisbon": "Europe/Lisbon",
    "рим": "Europe/Rome", "rome": "Europe/Rome",
    "мадрид": "Europe/Madrid", "madrid": "Europe/Madrid",
    "афины": "Europe/Athens", "athens": "Europe/Athens",
    "стамбул": "Europe/Istanbul", "istanbul": "Europe/Istanbul",
    "хельсинки": "Europe/Helsinki", "helsinki": "Europe/Helsinki",
    "тбилиси": "Asia/Tbilisi", "tbilisi": "Asia/Tbilisi",
    "ереван": "Asia/Yerevan", "yerevan": "Asia/Yerevan",
    "баку": "Asia/Baku", "baku": "Asia/Baku",
    "астана": "Asia/Almaty", "алматы": "Asia/Almaty", "astana": "Asia/Almaty", "almaty": "Asia/Almaty",
    "ташкент": "Asia/Tashkent", "tashkent": "Asia/Tashkent",
    "душанбе": "Asia/Dushanbe", "dushanbe": "Asia/Dushanbe",
    "бишкек": "Asia/Bishkek", "bishkek": "Asia/Bishkek",
    "пекин": "Asia/Shanghai", "beijing": "Asia/Shanghai",
    "шанхай": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "токио": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
    "сеул": "Asia/Seoul", "seoul": "Asia/Seoul",
    "бангкок": "Asia/Bangkok", "bangkok": "Asia/Bangkok",
    "сингапур": "Asia/Singapore", "singapore": "Asia/Singapore",
    "дели": "Asia/Kolkata", "нью-дели": "Asia/Kolkata", "new delhi": "Asia/Kolkata",
    "дубай": "Asia/Dubai", "dubai": "Asia/Dubai",
    "тель-авив": "Asia/Jerusalem", "tel aviv": "Asia/Jerusalem",
    "нью-йорк": "America/New_York", "new york": "America/New_York",
    "вашингтон": "America/New_York", "washington": "America/New_York",
    "чикaго": "America/Chicago", "чикаго": "America/Chicago", "chicago": "America/Chicago",
    "денвер": "America/Denver", "denver": "America/Denver",
    "лос-анджелес": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
    "сан-франциско": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "торонто": "America/Toronto", "toronto": "America/Toronto",
    "мехико": "America/Mexico_City", "mexico city": "America/Mexico_City",
    "сан-паулу": "America/Sao_Paulo", "sao paulo": "America/Sao_Paulo",
    "буэнос-айрес": "America/Argentina/Buenos_Aires", "buenos aires": "America/Argentina/Buenos_Aires",
    "рио-де-жанейро": "America/Sao_Paulo", "rio de janeiro": "America/Sao_Paulo",
    "сидней": "Australia/Sydney", "sydney": "Australia/Sydney",
    "мельбурн": "Australia/Melbourne", "melbourne": "Australia/Melbourne",
    "перт": "Australia/Perth", "perth": "Australia/Perth",
    "окленд": "Pacific/Auckland", "auckland": "Pacific/Auckland",
}

VALID_UTC_OFFSETS = {
    -720, -660, -600, -570, -540, -480, -420, -360, -300, -240, -210,
    -180, -120, -60, 0, 60, 120, 180, 210, 240, 270, 300, 330, 345,
    360, 390, 420, 480, 525, 540, 570, 600, 630, 660, 720, 765, 780, 840,
}

def parse_timezone(value: str):
    raw = value.strip().lower().replace("−", "-").replace("—", "-")
    city_key = re.sub(r"\s+", " ", raw)

    for zone_name in __import__("zoneinfo").available_timezones():
        if zone_name.lower() == city_key:
            try:
                return ZoneInfo(zone_name), zone_name
            except ZoneInfoNotFoundError:
                return None

    if city_key in CITY_TIMEZONES:
        name = CITY_TIMEZONES[city_key]
        try:
            return ZoneInfo(name), name
        except ZoneInfoNotFoundError:
            return None

    match = re.fullmatch(r"(?:utc|gmt)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?", raw)
    if not match:
        return None
    sign = 1 if match.group(1) == "+" else -1
    hours = int(match.group(2))
    minutes = int(match.group(3) or "0")
    total = sign * (hours * 60 + minutes)
    if total not in VALID_UTC_OFFSETS:
        return None
    tz = timezone(timedelta(minutes=total))
    sign_text = "+" if total >= 0 else "-"
    absolute = abs(total)
    hh, mm = divmod(absolute, 60)
    label = f"UTC{sign_text}{hh:02d}:{mm:02d}"
    return tz, label

def get_time_setting(user_id: int):
    row = db.execute(
        "SELECT enabled, timezone FROM time_settings WHERE user_id=?",
        (user_id,)
    ).fetchone()
    return row if row else (0, "UTC")

def set_time_setting(user_id: int, enabled: bool, tz_name: str | None = None):
    if tz_name is None:
        _, tz_name = get_time_setting(user_id)
    db.execute(
        "INSERT INTO time_settings(user_id, enabled, timezone) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled, timezone=excluded.timezone",
        (user_id, 1 if enabled else 0, tz_name),
    )
    db.commit()

def get_interlocutor_last_activity(connection_id: str, chat_id: int, owner_id: int):
    row = db.execute(
        "SELECT MAX(created_at) FROM messages "
        "WHERE connection_id=? AND chat_id=? "
        "AND sender_id IS NOT NULL AND sender_id != ?",
        (connection_id, chat_id, owner_id),
    ).fetchone()
    return row[0] if row and row[0] else None

def format_local_timestamp(timestamp: float, tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        parsed = parse_timezone(tz_name)
        tz = parsed[0] if parsed else timezone.utc
    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone(tz).strftime("%H:%M")

def get_last_activity(connection_id: str, chat_id: int, user_id: int | None = None):
    if user_id is None:
        row = db.execute(
            "SELECT MAX(created_at) FROM messages WHERE connection_id=? AND chat_id=?",
            (connection_id, chat_id),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT MAX(created_at) FROM messages WHERE connection_id=? AND chat_id=? AND sender_id=?",
            (connection_id, chat_id, user_id),
        ).fetchone()
    return row[0] if row and row[0] else None

ENABLE_BUTTON_STYLES = True
VALID_BUTTON_STYLES = {"primary", "success", "danger"}

def btn(
    text: str,
    callback_data: str | None = None,
    url: str | None = None,
    style: str | None = None,
):
    kwargs = {"text": text}
    if style in VALID_BUTTON_STYLES:
        kwargs["style"] = style
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    return InlineKeyboardButton(**kwargs)

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn(b("guide"), "guide_useful", "", button_style("main_guide"))],
            [
                btn(b("channel"), url="https://t.me/loudsaves", style=button_style("main_channel")),
                btn(b("newbie"), "guide_newbie", "", button_style("main_newbie", NEWBIE_GUIDE_BUTTON_STYLE)),
            ],
            [btn(b("profile"), "profile", "", button_style("main_profile"))],
            [
                btn(b("subscription"), "subscription", "", button_style("main_subscription")),
                btn(b("partner"), "partner", "", button_style("main_partner")),
            ],
            [btn(b("stars"), url="https://t.me/loudstarsbot", style=button_style("main_stars"))],
        ]
    )

def time_error_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn(b("timezone"), "time_city", "", button_style("status_timezone"))],
            [btn(b("timezones"), "time_zones", "", button_style("status_timezone"))],
        ]
    )

def timezone_keyboard() -> InlineKeyboardMarkup:
    return time_error_keyboard()

# ---------- НИЖЕ НАЧИНАЮТСЯ ФУНКЦИИ ДЛЯ АВТО-СТАТУСА И АВТО-НИКА ----------
# (они полностью сохранены из оригинального кода, я не буду их дублировать здесь, чтобы не превысить лимит,
# но в вашем исходном файле они уже есть. В полном файле они должны быть на своих местах.
# Я их пропускаю в этой части, но они будут в финальном коде, который вы получите.

# ВНИМАНИЕ: все функции от _load_nick_settings до simple_extra_command и все старые обработчики
# (start, help, info, ghoul, streak, cat, save, a_troll, troll, ping, mute, unmute, status, coin, time_on/off,
# time_command_help, guide_useful, guide_newbie, subscription, partner, stars, pay_*, pre_checkout, successful_payment,
# business_connection, business_message, edited_business_message, deleted_business_messages,
# notification_close_callback, global_error_handler, test_* и т.д.) – они все должны остаться без изменений,
# кроме info_command и streak_command, которые я заменю новыми, и добавлю новые команды в business_message.
# Я продолжу в Части 2, где дам обновлённые функции и main().# ============================================================
# ОБНОВЛЁННЫЕ ФУНКЦИИ (заменяют старые версии)
# ============================================================

async def info_command(message: Message):
    if await reject_non_owner_command(message):
        return

    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif message.business_connection_id:
        conn = get_connection(message.business_connection_id)
        if conn:
            row = db.execute(
                "SELECT sender_id, sender_name, sender_username FROM messages "
                "WHERE connection_id=? AND chat_id=? AND sender_id != ? "
                "ORDER BY created_at DESC LIMIT 1",
                (message.business_connection_id, message.chat.id, conn[0])
            ).fetchone()
            if row:
                class FakeUser:
                    id = row[0]
                    first_name = row[1] or "Неизвестно"
                    username = row[2]
                target = FakeUser()
    if not target:
        target = message.from_user

    last_seen = get_last_activity(message.business_connection_id, message.chat.id, target.id) if message.business_connection_id else None
    enabled, tz_name = get_time_setting(target.id) if message.business_connection_id else (0, "UTC")
    last_seen_text = format_local_timestamp(last_seen, tz_name) if last_seen else "неизвестно"

    online_status = "🟢 Онлайн" if last_seen and (datetime.now(timezone.utc).timestamp() - last_seen) < 300 else "🔴 Офлайн"
    profile_value = abs(hash(str(target.id))) % 1000

    text = (
        f"{pe('info')} <b>Информация о собеседнике</b>\n\n"
        f"ID: <code>{target.id}</code>\n"
        f"Имя: {target.first_name or '—'}\n"
        f"Username: @{target.username}" if target.username else "Username: —"
        f"\n{online_status}\n"
        f"{pe('timezone')} Последняя активность: <code>[{last_seen_text}]</code>\n"
        f"{pe('money')} Стоимость профиля: {profile_value}₽ (оценочно)"
    )
    await answer_message(message, text, parse_mode="HTML")

async def streak_command(message: Message):
    if await reject_non_owner_command(message):
        return
    if message.business_connection_id:
        conn = get_connection(message.business_connection_id)
        if conn:
            now = int(datetime.now(timezone.utc).timestamp())
            day_ago = now - 86400
            count = db.execute(
                "SELECT COUNT(*) FROM messages WHERE connection_id=? AND chat_id=? AND sender_id != ? AND created_at > ?",
                (message.business_connection_id, message.chat.id, conn[0], day_ago)
            ).fetchone()[0]
            await answer_message(message, f"{pe('saved')} <b>Серия общения</b>\n\nЗа последние 24 часа отправлено <b>{count}</b> сообщений.\nПродолжай в том же духе! 🔥", parse_mode="HTML")
            return
    await answer_message(message, f"{pe('warning')} Серия общения пока не настроена для этого чата.", parse_mode="HTML")

# ---------- НОВЫЕ ФУНКЦИИ ----------

async def copy_profile_command(message: Message):
    if await reject_non_owner_command(message):
        return

    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif message.business_connection_id:
        conn = get_connection(message.business_connection_id)
        if conn:
            row = db.execute(
                "SELECT sender_id, sender_name, sender_username FROM messages "
                "WHERE connection_id=? AND chat_id=? AND sender_id != ? "
                "ORDER BY created_at DESC LIMIT 1",
                (message.business_connection_id, message.chat.id, conn[0])
            ).fetchone()
            if row:
                class FakeUser:
                    id = row[0]
                    first_name = row[1] or "Неизвестно"
                    username = row[2]
                target = FakeUser()
    if not target:
        target = message.from_user

    text = (
        f"{pe('profile')} <b>Профиль</b>\n\n"
        f"ID: <code>{target.id}</code>\n"
        f"Имя: {target.first_name or '—'}\n"
        f"Username: @{target.username}" if target.username else "Username: —"
    )
    await answer_message(message, text, parse_mode="HTML")

# Функции для .a_format
def get_format_setting(connection_id: str):
    row = db.execute("SELECT enabled, style FROM format_settings WHERE connection_id=?", (connection_id,)).fetchone()
    if not row:
        db.execute("INSERT INTO format_settings(connection_id, enabled, style) VALUES (?,0,'bold')", (connection_id,))
        db.commit()
        return False, 'bold'
    return bool(row[0]), row[1]

def set_format_setting(connection_id: str, enabled: bool, style: str = None):
    _, cur_style = get_format_setting(connection_id)
    if style is None:
        style = cur_style
    db.execute("INSERT OR REPLACE INTO format_settings(connection_id, enabled, style) VALUES (?,?,?)",
               (connection_id, 1 if enabled else 0, style))
    db.commit()

@dp.message(F.text.regexp(r'^\.a_format\s+(on|off)\s*(.*)$', flags=re.IGNORECASE))
async def a_format_toggle(message: Message):
    if await reject_non_owner_command(message):
        return
    if not message.business_connection_id:
        await answer_message(message, f"{pe('warning')} Команда доступна только в Business-чате.", parse_mode="HTML")
        return
    match = re.match(r'^\.a_format\s+(on|off)\s*(.*)$', message.text.strip(), re.IGNORECASE)
    if not match:
        return
    action = match.group(1).lower()
    style = match.group(2).strip() or 'bold'
    if action == 'on':
        set_format_setting(message.business_connection_id, True, style)
        await answer_message(message, f"{pe('check')} Автоформатирование включено (стиль: {style}).", parse_mode="HTML")
    else:
        set_format_setting(message.business_connection_id, False)
        await answer_message(message, f"{pe('cancel')} Автоформатирование выключено.", parse_mode="HTML")

# .act
@dp.message(F.text.regexp(r'^\.act\s+(\w+)', flags=re.IGNORECASE))
async def act_command(message: Message):
    if await reject_non_owner_command(message):
        return
    action = re.match(r'^\.act\s+(\w+)', message.text.strip(), re.IGNORECASE).group(1).lower()
    actions = {
        'typing': 'typing',
        'upload_photo': 'upload_photo',
        'upload_video': 'upload_video',
        'upload_audio': 'upload_audio',
        'upload_document': 'upload_document',
        'choose_sticker': 'choose_sticker',
        'find_location': 'find_location',
        'record_video_note': 'record_video_note',
        'record_voice': 'record_voice'
    }
    if action not in actions:
        await answer_message(message, f"{pe('warning')} Неизвестное действие. Доступны: typing, upload_photo, upload_video, upload_audio, upload_document, choose_sticker, find_location, record_video_note, record_voice", parse_mode="HTML")
        return
    await bot.send_chat_action(chat_id=message.chat.id, action=actions[action], business_connection_id=message.business_connection_id)
    await answer_message(message, f"{pe('check')} Имитация действия '{action}' выполнена.", parse_mode="HTML")

# .love
@dp.message(F.text == '.love')
async def love_command(message: Message):
    if await reject_non_owner_command(message):
        return
    heart = "❤️"
    animation = (
        f"{heart}\n"
        f"{heart}{heart}{heart}\n"
        f"{heart}{heart}{heart}{heart}{heart}\n"
        f"{heart}{heart}{heart}{heart}{heart}{heart}{heart}"
    )
    await answer_message(message, animation)

# .online
@dp.message(F.text == '.online')
async def online_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await bot.send_chat_action(chat_id=message.chat.id, action='typing', business_connection_id=message.business_connection_id)
    await answer_message(message, f"{pe('enabled')} <b>Вы онлайн</b> (имитация).", parse_mode="HTML")

# .send (обновлённый с генерацией чека)
def generate_receipt_image(amount: float, currency: str = "RUB"):
    img = Image.new('RGB', (400, 300), color='white')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    draw.text((50, 50), f"ЧЕК", fill='black', font=font)
    draw.text((50, 100), f"Сумма: {amount} {currency}", fill='black', font=font)
    draw.text((50, 150), f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}", fill='black', font=font)
    draw.text((50, 200), f"Статус: ТЕСТ", fill='black', font=font)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

@dp.message(F.text.startswith('.send'))
async def send_command(message: Message):
    if await reject_non_owner_command(message):
        return
    parts = message.text.split()
    if len(parts) == 2:
        try:
            amount = float(parts[1].replace(',', '.'))
            if 0 < amount <= 100000:
                img_buf = generate_receipt_image(amount, "RUB")
                photo = BufferedInputFile(img_buf.read(), filename="receipt.png")
                await answer_message(
                    message,
                    caption=f"{pe('payment')} <b>Фейк-чек</b>\n\nЭто демонстрационная карточка, не является платёжным документом.",
                    parse_mode="HTML",
                    photo=photo,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [btn(f"{pe('upload')} Получить", "fake_receipt_get")]
                    ])
                )
                return
        except ValueError:
            pass
    await answer_message(message, f"{pe('warning')} Использование: <code>.send 2.5</code>", parse_mode="HTML")

@dp.callback_query(F.data == "fake_receipt_get")
async def fake_receipt_get(callback: CallbackQuery):
    await callback.answer("Это тестовый чек. Никаких реальных средств не списано.", show_alert=False)

# ============================================================
# ИЗМЕНЕНИЯ В ОБРАБОТЧИКЕ business_message (добавить новые команды)
# ============================================================
# В функции business_message, внутри блока if command_text:, после существующих elif
# добавьте следующие строки (они уже есть в оригинальном коде, но я продублирую для ясности):
#
# elif command_text.lower() == '.copy':
#     await copy_profile_command(message)
# elif command_text.lower() == '.publ':
#     await answer_message(message, f"{pe('channel')} <b>.publ</b>\n\nФункция публикации в Stories будет доступна после обновления Telegram Bot API.", parse_mode="HTML")
# elif command_text.lower() == '.streak':
#     await streak_command(message)
#
# Также после save_message(connection_id, message) добавьте блок автоформатирования:
#
# if message.from_user and message.from_user.id != conn[0] and message.text:
#     enabled, style = get_format_setting(connection_id)
#     if enabled:
#         if style == 'bold':
#             formatted = f"<b>{message.text}</b>"
#         elif style == 'italic':
#             formatted = f"<i>{message.text}</i>"
#         elif style == 'underline':
#             formatted = f"<u>{message.text}</u>"
#         elif style == 'strikethrough':
#             formatted = f"<s>{message.text}</s>"
#         elif style == 'spoiler':
#             formatted = f"<span class='tg-spoiler'>{message.text}</span>"
#         else:
#             formatted = f"<b>{message.text}</b>"
#         await answer_message(message, formatted, parse_mode="HTML")

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ main() (без изменений)
# ============================================================

async def main():
    global bot
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN. Установи переменную окружения BOT_TOKEN.")

    bot = Bot(TOKEN)
    asyncio.create_task(nick_scheduler(), name="nick_scheduler")
    asyncio.create_task(status_scheduler(), name="status_scheduler")
    me = await bot.get_me()
    log.info("=" * 70)
    log.info("loudGram DEBUG STARTED | bot=@%s id=%s | aiogram updates=business", me.username, me.id)
    log.info("DB: %s", os.path.abspath(DB_PATH))

    webhook = await bot.get_webhook_info()
    log.info("Webhook: url=%r pending=%s", webhook.url, webhook.pending_update_count)
    if webhook.url:
        log.error("Webhook is configured! Local polling will not receive updates until webhook is removed.")
        log.error("Run: deleteWebhook in Bot API / or set REMOVE_WEBHOOK=1 before starting.")
        if os.getenv("REMOVE_WEBHOOK") == "1":
            await bot.delete_webhook(drop_pending_updates=False)
            log.warning("Webhook removed because REMOVE_WEBHOOK=1")

    log.info("Allowed updates: message, callback_query, business_connection, business_message, edited_business_message, deleted_business_messages")
    log.info("Commands: .help, .time on/off, .mute, .unmute, .nick, .copy, .info, .streak, .a_format, .act, .love, .online, .send")
    log.info("=" * 70)

    await dp.start_polling(
        bot,
        allowed_updates=[
            "message", "callback_query", "pre_checkout_query",
            "business_connection", "business_message",
            "edited_business_message", "deleted_business_messages"
        ]
    )

if __name__ == "__main__":
    asyncio.run(main())
