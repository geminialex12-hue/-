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
        return await old_message.answer(text, **kwargs)

timezone_waiting = set()

CITY_TIMEZONES = {
    "москва": "Europe/Moscow", "moscow": "Europe/Moscow",
    "санкт-петербург": "Europe/Moscow", "санкт петербург": "Europe/Moscow",
    "saint petersburg": "Europe/Moscow", "st petersburg": "Europe/Moscow",
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
    "астана": "Asia/Almaty", "алматы": "Asia/Almaty", "astana": "Asia/Almaty",
    "almaty": "Asia/Almaty",
    "ташкент": "Asia/Tashkent", "tashkent": "Asia/Tashkent",
    "душанбе": "Asia/Dushanbe", "dushanbe": "Asia/Dushanbe",
    "бишкек": "Asia/Bishkek", "bishkek": "Asia/Bishkek",
    "пекин": "Asia/Shanghai", "beijing": "Asia/Shanghai",
    "шанхай": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "токио": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
    "сеул": "Asia/Seoul", "seoul": "Asia/Seoul",
    "бангкок": "Asia/Bangkok", "bangkok": "Asia/Bangkok",
    "сингапур": "Asia/Singapore", "singapore": "Asia/Singapore",
    "дели": "Asia/Kolkata", "нью-дели": "Asia/Kolkata",
    "new delhi": "Asia/Kolkata",
    "дубай": "Asia/Dubai", "dubai": "Asia/Dubai",
    "тель-авив": "Asia/Jerusalem", "tel aviv": "Asia/Jerusalem",
    "нью-йорк": "America/New_York", "new york": "America/New_York",
    "вашингтон": "America/New_York", "washington": "America/New_York",
    "чикаго": "America/Chicago", "chicago": "America/Chicago",
    "денвер": "America/Denver", "denver": "America/Denver",
    "лос-анджелес": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
    "сан-франциско": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "торонто": "America/Toronto", "toronto": "America/Toronto",
    "мехико": "America/Mexico_City", "mexico city": "America/Mexico_City",
    "сан-паулу": "America/Sao_Paulo", "sao paulo": "America/Sao_Paulo",
    "буэнос-айрес": "America/Argentina/Buenos_Aires",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "рио-де-жанейро": "America/Sao_Paulo",
    "rio de janeiro": "America/Sao_Paulo",
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

# ==================== АВТО-СТАТУС ====================

status_timezone_waiting = set()
status_edit_waiting = {}
STATUS_DEFAULTS = [
    {"name": "Сплю", "start": "06:00", "end": "15:00"},
    {"name": "Занят", "start": "16:00", "end": "23:00"},
    {"name": "Кушаю", "start": "23:00", "end": "06:00"},
]

def get_status_settings(connection_id: str):
    row = db.execute("SELECT enabled, statuses_json FROM status_settings WHERE connection_id=?", (connection_id,)).fetchone()
    if not row:
        statuses = [dict(x) for x in STATUS_DEFAULTS]
        db.execute("INSERT INTO status_settings(connection_id, enabled, statuses_json) VALUES (?, 0, ?)",
                   (connection_id, json.dumps(statuses, ensure_ascii=False)))
        db.commit()
        return False, statuses
    try:
        statuses = json.loads(row[1] or "[]")
        if not isinstance(statuses, list):
            statuses = []
    except Exception:
        statuses = []
    return bool(row[0]), statuses

def save_status_settings(connection_id: str, *, enabled=None, statuses=None):
    cur_enabled, cur_statuses = get_status_settings(connection_id)
    db.execute(
        "INSERT INTO status_settings(connection_id, enabled, statuses_json) VALUES (?, ?, ?) "
        "ON CONFLICT(connection_id) DO UPDATE SET enabled=excluded.enabled, statuses_json=excluded.statuses_json",
        (connection_id,
         int(cur_enabled if enabled is None else bool(enabled)),
         json.dumps(cur_statuses if statuses is None else statuses, ensure_ascii=False))
    )
    db.commit()

def _status_minutes(value: str):
    try:
        h, m = map(int, value.split(":", 1))
        return h * 60 + m if 0 <= h <= 23 and 0 <= m <= 59 else None
    except Exception:
        return None

def active_status_for_local_time(statuses, minutes):
    for item in statuses:
        a = _status_minutes(item.get("start", ""))
        b = _status_minutes(item.get("end", ""))
        if a is None or b is None or a == b or not item.get("name"):
            continue
        if (a < b and a <= minutes < b) or (a > b and (minutes >= a or minutes < b)):
            return item
    return None

def status_menu(connection_id: str) -> InlineKeyboardMarkup:
    enabled, statuses = get_status_settings(connection_id)
    rows = [[btn(f"{e('timezone')} Изменить часовой пояс", f"status_timezone:{connection_id}", "", button_style("status_timezone"))]]
    for i, x in enumerate(statuses[:3]):
        rows.append([btn(f"{e('edit')} {x.get('name','Статус')} ({x.get('start')}-{x.get('end')})",
                         f"status_edit:{connection_id}:{i}", "", button_style("status_edit"))])
    rows.append([btn(f"{e('add')} Добавить статус", f"status_add:{connection_id}", "", button_style("status_add"))])
    rows.append([btn(f"{e('disabled')} Выключить" if enabled else f"{e('enabled')} Включить",
                     f"status_toggle:{connection_id}", "",
                     button_style("status_toggle_off" if enabled else "status_toggle_on"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def status_menu_text(connection_id: str) -> str:
    enabled, statuses = get_status_settings(connection_id)
    conn = get_connection(connection_id)
    tz = get_time_setting(conn[0])[1] if conn else "UTC"
    lines = [
        f"{pe('settings')} <b>Настройка авто-статуса</b>",
        "",
        f"{pe('info')} Статус: <b>{'включён ' + pe('enabled') if enabled else 'выключен ' + pe('disabled')}</b>",
        f"{pe('timezone')} Часовой пояс: <code>{escape_html(tz)}</code>",
        "",
        f"{pe('timezones')} <b>Расписание:</b>"
    ]
    for i, x in enumerate(statuses[:3], 1):
        lines.append(f"{i}. <b>{escape_html(str(x.get('name','')))}</b>  {x.get('start')} – {x.get('end')}")
    if not statuses:
        lines.append("— пока нет статусов —")
    lines += ["", "Выберите действие:"]
    return "\n".join(lines)

async def show_status_menu(message: Message, connection_id: str):
    conn = get_connection(connection_id)
    if not conn or not message.from_user or int(message.from_user.id) != int(conn[0]):
        await answer_message(message, "⛔ <b>Эта настройка доступна только владельцу Business-аккаунта.</b>", parse_mode="HTML")
        return
    await answer_message(message, status_menu_text(connection_id), reply_markup=status_menu(connection_id), parse_mode="HTML")

async def apply_auto_status(connection_id: str):
    enabled, statuses = get_status_settings(connection_id)
    if not enabled or not statuses:
        return False
    conn = get_connection(connection_id)
    if not conn:
        return False
    tz_name = get_time_setting(conn[0])[1]
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        parsed = parse_timezone(tz_name)
        tz = parsed[0] if parsed else timezone.utc
    dt = datetime.now(timezone.utc).astimezone(tz)
    item = active_status_for_local_time(statuses, dt.hour * 60 + dt.minute)
    if not item:
        return False
    await set_business_last_name(connection_id, f"[{item['name']}]")
    return True

async def status_scheduler():
    while True:
        try:
            for (cid,) in db.execute("SELECT connection_id FROM status_settings WHERE enabled=1").fetchall():
                try:
                    await apply_auto_status(cid)
                except Exception:
                    log.exception("[STATUS SCHEDULER] connection=%s failed", cid)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[STATUS SCHEDULER] loop error")
        await asyncio.sleep(30)

# ==================== АВТО-НИК ====================

nick_waiting = set()
NICK_INTERVALS = [1, 2, 5, 10, 15, 30, 60]

def _load_nick_settings(connection_id: str):
    row = db.execute(
        "SELECT enabled, interval_minutes, nicks_json, current_index, next_change_ts "
        "FROM nick_settings WHERE connection_id=?",
        (connection_id,),
    ).fetchone()
    if not row:
        db.execute(
            "INSERT INTO nick_settings(connection_id, enabled, interval_minutes, nicks_json, current_index, next_change_ts) "
            "VALUES (?, 0, 2, '[]', -1, 0)",
            (connection_id,),
        )
        db.commit()
        return False, 2, [], -1, 0
    try:
        nicks = json.loads(row[2] or "[]")
        if not isinstance(nicks, list):
            nicks = []
    except Exception:
        nicks = []
    return bool(row[0]), int(row[1]), [str(x) for x in nicks if str(x).strip()], int(row[3]), int(row[4])

def get_nick_settings(connection_id: str):
    return _load_nick_settings(connection_id)

def save_nick_settings(connection_id: str, *, enabled=None, interval_minutes=None,
                       nicks=None, current_index=None, next_change_ts=None):
    cur = _load_nick_settings(connection_id)
    values = {
        "enabled": int(cur[0] if enabled is None else bool(enabled)),
        "interval_minutes": int(cur[1] if interval_minutes is None else interval_minutes),
        "nicks": cur[2] if nicks is None else list(nicks),
        "current_index": int(cur[3] if current_index is None else current_index),
        "next_change_ts": int(cur[4] if next_change_ts is None else next_change_ts),
    }
    db.execute("""
        INSERT INTO nick_settings(
            connection_id, enabled, interval_minutes, nicks_json, current_index, next_change_ts
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(connection_id) DO UPDATE SET
            enabled=excluded.enabled,
            interval_minutes=excluded.interval_minutes,
            nicks_json=excluded.nicks_json,
            current_index=excluded.current_index,
            next_change_ts=excluded.next_change_ts
    """, (
        connection_id, values["enabled"], values["interval_minutes"],
        json.dumps(values["nicks"], ensure_ascii=False),
        values["current_index"], values["next_change_ts"]
    ))
    db.commit()

def escape_html(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def nick_menu(connection_id: str) -> InlineKeyboardMarkup:
    enabled, interval_minutes, nicks, _, _ = get_nick_settings(connection_id)
    rows = [[btn(
        f"{e('interval')} Изменить интервал ({interval_minutes} мин.)",
        f"nick_interval:{connection_id}", "", button_style("nick_interval")
    )]]

    for i, nick in enumerate(nicks):
        label = nick if len(nick) <= 28 else nick[:25] + "..."
        rows.append([btn(
            f"{e('edit')} {label}",
            f"nick_use:{connection_id}:{i}", "", button_style("nick_edit")
        )])

    rows.append([btn(
        f"{e('add')} Добавить ник",
        f"nick_add:{connection_id}", "", button_style("nick_add")
    )])

    rows.append([btn(
        f"{e('disabled')} Выключить" if enabled else f"{e('enabled')} Включить",
        f"nick_toggle:{connection_id}", "",
        button_style("nick_toggle_off" if enabled else "nick_toggle_on")
    )])

    if nicks:
        rows.append([btn(
            f"{e('clear')} Очистить ники",
            f"nick_clear:{connection_id}", "", button_style("nick_clear")
        )])

    return InlineKeyboardMarkup(inline_keyboard=rows)

async def show_nick_menu(message: Message, connection_id: str):
    conn = get_connection(connection_id)
    if not conn or not message.from_user or message.from_user.id != conn[0]:
        await answer_message(message, "⛔ <b>Эта настройка доступна только владельцу Business-аккаунта.</b>", parse_mode="HTML")
        return
    enabled, interval_minutes, nicks, _, _ = get_nick_settings(connection_id)
    status = f"включен {pe('enabled')}" if enabled else f"выключен {pe('disabled')}"
    nick_list = "\n".join(
        f"{i+1}. <b>{escape_html(n)}</b>" for i, n in enumerate(nicks)
    ) if nicks else "— пока нет ников —"
    await answer_message(
        message,
        f"{pe('refresh')} <b>Настройка авто-ника</b>\n\n"
        f"{pe('info')} Статус: <b>{status}</b>\n"
        f"{pe('interval')} Интервал: <b>{interval_minutes} мин.</b>\n\n"
        f"{pe('profile')} <b>Ники:</b>\n{nick_list}\n\n"
        "Выберите действие:",
        reply_markup=nick_menu(connection_id),
        parse_mode="HTML",
    )

async def set_business_nickname(connection_id: str, nickname: str):
    conn = get_connection(connection_id)
    if not conn:
        raise RuntimeError("Business connection not found")
    nickname = nickname.strip()
    if not nickname:
        raise ValueError("Пустой ник")
    if len(nickname) > 64:
        raise ValueError("Ник длиннее 64 символов")
    first_name = conn[3]
    if not first_name:
        try:
            bc = await bot.get_business_connection(business_connection_id=connection_id)
            first_name = getattr(getattr(bc, "user", None), "first_name", None)
            if first_name:
                db.execute(
                    "UPDATE connections SET business_first_name=?, business_last_name=? WHERE connection_id=?",
                    (first_name, getattr(getattr(bc, "user", None), "last_name", None), connection_id),
                )
                db.commit()
        except Exception:
            log.exception("[NICK] failed to recover Business first_name")
    if not first_name:
        raise RuntimeError("Не удалось определить текущее имя Business-аккаунта. Переподключите Business-бота.")
    method = getattr(bot, "set_business_account_name", None)
    if method is not None:
        await method(business_connection_id=connection_id, first_name=first_name, last_name=nickname)
    else:
        url = f"https://api.telegram.org/bot{bot.token}/setBusinessAccountName"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"business_connection_id": connection_id, "first_name": first_name, "last_name": nickname},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                payload = await response.json(content_type=None)
                if not response.ok or not payload.get("ok"):
                    raise RuntimeError(payload.get("description", f"HTTP {response.status}"))
    db.execute("UPDATE connections SET business_last_name=? WHERE connection_id=?", (nickname, connection_id))
    db.commit()
    log.info("[NICK] connection=%s Last name=%r", connection_id, nickname)

async def set_business_last_name(connection_id: str, last_name: str):
    conn = get_connection(connection_id)
    if not conn:
        raise RuntimeError("Business connection not found")
    last_name = str(last_name).strip()
    if len(last_name) > 64:
        raise ValueError("Last name длиннее 64 символов")
    first_name = conn[3]
    if not first_name:
        bc = await bot.get_business_connection(business_connection_id=connection_id)
        first_name = getattr(getattr(bc, "user", None), "first_name", None)
        if first_name:
            db.execute("UPDATE connections SET business_first_name=? WHERE connection_id=?", (first_name, connection_id))
            db.commit()
    if not first_name:
        raise RuntimeError("Не удалось определить First name Business-аккаунта.")
    method = getattr(bot, "set_business_account_name", None)
    if method is not None:
        await method(business_connection_id=connection_id, first_name=first_name, last_name=last_name)
    else:
        url = f"https://api.telegram.org/bot{bot.token}/setBusinessAccountName"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"business_connection_id": connection_id, "first_name": first_name, "last_name": last_name},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                payload = await response.json(content_type=None)
                if not response.ok or not payload.get("ok"):
                    raise RuntimeError(payload.get("description", f"HTTP {response.status}"))
    db.execute("UPDATE connections SET business_last_name=? WHERE connection_id=?", (last_name or None, connection_id))
    db.commit()
    log.info("[TIME LAST NAME] connection=%s Last name=%r", connection_id, last_name)

async def nick_rotate_once(connection_id: str):
    enabled, interval_minutes, nicks, current_index, _ = get_nick_settings(connection_id)
    if not enabled or not nicks:
        return
    next_index = (current_index + 1) % len(nicks)
    await set_business_nickname(connection_id, nicks[next_index])
    save_nick_settings(
        connection_id,
        current_index=next_index,
        next_change_ts=int(datetime.now(timezone.utc).timestamp()) + interval_minutes * 60,
    )

async def nick_scheduler():
    while True:
        try:
            now = int(datetime.now(timezone.utc).timestamp())
            rows = db.execute("SELECT connection_id FROM nick_settings WHERE enabled=1").fetchall()
            for (connection_id,) in rows:
                try:
                    enabled, interval_minutes, nicks, current_index, next_ts = get_nick_settings(connection_id)
                    if not nicks:
                        save_nick_settings(connection_id, enabled=False)
                        continue
                    if next_ts <= now:
                        await nick_rotate_once(connection_id)
                except Exception:
                    log.exception("[NICK SCHEDULER] connection=%s failed", connection_id)
                    save_nick_settings(connection_id, next_change_ts=now + 60)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[NICK SCHEDULER] loop error")
        await asyncio.sleep(5)

async def nick_add_input(message: Message):
    connection_id = message.business_connection_id
    if not connection_id or not message.from_user:
        return
    conn = get_connection(connection_id)
    if not conn or message.from_user.id != conn[0]:
        return
    nick_waiting.discard(message.from_user.id)
    nick = (message.text or "").strip()
    if not nick or nick.startswith("."):
        await answer_message(message, "❌ Введите обычный ник, например <code>sally</code>.", parse_mode="HTML")
        return
    if len(nick) > 64:
        await answer_message(message, "❌ Ник должен быть не длиннее 64 символов.")
        return
    enabled, interval_minutes, nicks, current_index, next_ts = get_nick_settings(connection_id)
    if nick not in nicks:
        nicks.append(nick)
    save_nick_settings(connection_id, nicks=nicks)
    await show_nick_menu(message, connection_id)

def menu() -> InlineKeyboardMarkup:
    return main_menu_keyboard()

def create_mute(connection_id: str, chat_id: int, target_user_id: int, muter_user_id: int, until_ts: int, mode: str) -> str:
    import secrets
    mute_id = secrets.token_urlsafe(8)

    db.execute(
        "UPDATE mutes SET active=0 WHERE connection_id=? AND chat_id=? "
        "AND target_user_id=? AND active=1",
        (connection_id, int(chat_id), int(target_user_id)),
    )
    db.execute(
        "INSERT INTO mutes(mute_id, connection_id, chat_id, target_user_id, muter_user_id, until_ts, mode, active) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (mute_id, connection_id, int(chat_id), int(target_user_id), int(muter_user_id), int(until_ts), mode),
    )
    db.commit()
    return mute_id

def get_active_mute(connection_id: str, chat_id: int, target_user_id: int):
    now = int(datetime.now(timezone.utc).timestamp())
    row = db.execute(
        "SELECT mute_id, until_ts, mode FROM mutes WHERE connection_id=? AND chat_id=? AND target_user_id=? AND active=1 ORDER BY until_ts DESC LIMIT 1",
        (connection_id, chat_id, target_user_id),
    ).fetchone()
    if row and row[1] <= now:
        db.execute("UPDATE mutes SET active=0 WHERE mute_id=?", (row[0],))
        db.commit()
        return None
    return row

def get_mute(mute_id: str):
    return db.execute(
        "SELECT mute_id, connection_id, chat_id, target_user_id, muter_user_id, until_ts, mode, active FROM mutes WHERE mute_id=?",
        (mute_id,),
    ).fetchone()

def set_mute_inactive(mute_id: str):
    db.execute("UPDATE mutes SET active=0 WHERE mute_id=?", (mute_id,))
    db.commit()

def mute_keyboard(mute_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            btn(
                f"{e('disabled')} Размутить",
                f"unmute:{mute_id}",
            )
        ]]
    )

async def delete_business_message(message: Message):
    if not message.business_connection_id:
        return False
    try:
        await bot.delete_business_messages(
            business_connection_id=message.business_connection_id,
            message_ids=[message.message_id],
        )
        return True
    except Exception:
        log.exception("[MUTE] deleteBusinessMessages failed")
        return False

def target_from_message(message: Message):
    reply = message.reply_to_message
    if reply and reply.from_user:
        return reply.from_user

    if message.business_connection_id:
        conn = get_connection(message.business_connection_id)
        if conn:
            row = db.execute(
                """
                SELECT sender_id, sender_name, sender_username
                FROM messages
                WHERE connection_id=? AND chat_id=? AND sender_id IS NOT NULL
                  AND sender_id != ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (message.business_connection_id, message.chat.id, conn[0]),
            ).fetchone()
            if row:
                class SavedUser:
                    id = row[0]
                    first_name = row[1] or "Собеседник"
                    last_name = None
                    username = (row[2] or "").lstrip("@") or None

                    @property
                    def full_name(self):
                        return self.first_name

                return SavedUser()
    return None

def get_connection(connection_id: str):
    return db.execute(
        "SELECT user_id, user_chat_id, enabled, business_first_name, business_last_name "
        "FROM connections WHERE connection_id=?",
        (connection_id,)
    ).fetchone()

def is_command_owner(message: Message, connection_id: str | None = None) -> bool:
    user = getattr(message, "from_user", None)
    if not user:
        return False

    connection_id = connection_id or getattr(message, "business_connection_id", None)
    if connection_id:
        conn = get_connection(connection_id)
        if conn:
            return int(user.id) == int(conn[0])

    if OWNER_ID:
        return int(user.id) == OWNER_ID

    row = db.execute(
        "SELECT 1 FROM connections WHERE user_id=? LIMIT 1",
        (int(user.id),),
    ).fetchone()
    return bool(row)

async def reject_non_owner_command(message: Message) -> bool:
    if is_command_owner(message):
        return False

    log.info(
        "[COMMAND BLOCKED] user=%s connection=%s text=%r",
        getattr(getattr(message, "from_user", None), "id", None),
        getattr(message, "business_connection_id", None),
        _short(getattr(message, "text", None)),
    )
    return True

def save_connection_from_api(bc: BusinessConnection):
    rights = getattr(bc, "rights", None)
    enabled = bool(getattr(bc, "is_enabled", True))
    can_reply = business_can_reply(rights)
    db.execute("""
        INSERT INTO connections(
            connection_id, user_id, user_chat_id, enabled, can_reply,
            business_first_name, business_last_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(connection_id) DO UPDATE SET
            user_id=excluded.user_id,
            user_chat_id=excluded.user_chat_id,
            enabled=excluded.enabled,
            can_reply=excluded.can_reply,
            business_first_name=COALESCE(excluded.business_first_name, connections.business_first_name),
            business_last_name=COALESCE(excluded.business_last_name, connections.business_last_name)
    """, (
        bc.id, bc.user.id, bc.user_chat_id, 1 if enabled else 0, 1 if can_reply else 0,
        getattr(bc.user, "first_name", None),
        getattr(bc.user, "last_name", None),
    ))
    db.commit()
    return get_connection(bc.id)

async def ensure_connection(connection_id: str):
    cached = get_connection(connection_id)
    if cached:
        log.info(
            "[BUSINESS CONNECTION CACHE] id=%s enabled=%s can_reply=%s",
            connection_id, cached[2],
            bool(db.execute(
                "SELECT can_reply FROM connections WHERE connection_id=?",
                (connection_id,)
            ).fetchone()[0])
        )
        return cached

    try:
        bc = await bot.get_business_connection(
            business_connection_id=connection_id
        )
        rights = getattr(bc, "rights", None)
        if rights is None:
            log.warning(
                "[BUSINESS CONNECTION RECOVERY] Telegram returned no rights for %s; "
                "keeping connection disabled until a business_connection update arrives.",
                connection_id,
            )
            return None

        conn = save_connection_from_api(bc)
        log.info(
            "[BUSINESS CONNECTION RECOVERY] id=%s enabled=%s reply=%s",
            connection_id,
            getattr(bc, "is_enabled", None),
            business_can_reply(rights),
        )
        return conn
    except Exception as exc:
        log.exception(
            "[BUSINESS CONNECTION RECOVERY ERROR] id=%s: %s",
            connection_id, exc
        )
        return None

def save_message(connection_id: str, message: Message):
    sender_id = message.from_user.id if message.from_user else None
    sender_name = message.from_user.full_name if message.from_user else None
    sender_username = (
        f"@{message.from_user.username}"
        if message.from_user and message.from_user.username
        else None
    )

    kind = "text"
    text = message.text
    caption = message.caption
    file_id = None
    file_unique_id = None

    if message.video:
        kind = "video"
        file_id = message.video.file_id
        file_unique_id = message.video.file_unique_id
    elif message.photo:
        kind = "photo"
        item = message.photo[-1]
        file_id = item.file_id
        file_unique_id = item.file_unique_id
    elif message.document:
        kind = "document"
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
    elif message.audio:
        kind = "audio"
        file_id = message.audio.file_id
        file_unique_id = message.audio.file_unique_id
    elif message.voice:
        kind = "voice"
        file_id = message.voice.file_id
        file_unique_id = message.voice.file_unique_id

    db.execute("""
        INSERT OR REPLACE INTO messages
        (connection_id, chat_id, message_id, sender_id, sender_name, sender_username,
         chat_title, chat_username, chat_type, kind, text, caption, file_id,
         file_unique_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        connection_id,
        message.chat.id,
        message.message_id,
        sender_id,
        sender_name,
        sender_username,
        message.chat.title or (
            message.chat.full_name if message.chat.type == "private" else None
        ),
        message.chat.username,
        message.chat.type,
        kind,
        text,
        caption,
        file_id,
        file_unique_id,
        message.date.timestamp(),
    ))
    db.commit()

def notification_keyboard(link: str | None = None, close_callback: str = "notice_close") -> InlineKeyboardMarkup:
    row = []
    if link:
        row.append(btn(f"{e('open')} Открыть", url=link))
    row.append(btn(f"{e('close')} Закрыть", close_callback))
    return InlineKeyboardMarkup(inline_keyboard=[row])

async def send_owner_notification(
    chat_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    if BANNER_PATH and Path(BANNER_PATH).is_file():
        from aiogram.types import FSInputFile
        return await bot.send_photo(
            chat_id,
            FSInputFile(BANNER_PATH),
            caption=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )

    return await bot.send_message(
        chat_id,
        f"{pe('info')}\n{text}",
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

def chat_link(chat, message_id: int | None = None) -> str | None:
    if chat.username:
        return f"https://t.me/{chat.username}" + (
            f"/{message_id}" if message_id else ""
        )

    if chat.type in {"group", "supergroup", "channel"} and message_id:
        raw_id = str(chat.id)
        if raw_id.startswith("-100"):
            return f"https://t.me/c/{raw_id[4:]}/{message_id}"

    return None

def get_saved(connection_id: str, chat_id: int, message_id: int):
    return db.execute("""
        SELECT sender_id, sender_name, sender_username, chat_title,
               chat_username, chat_type, kind, text, caption, file_id
        FROM messages
        WHERE connection_id=? AND chat_id=? AND message_id=?
    """, (connection_id, chat_id, message_id)).fetchone()

def delete_saved(connection_id: str, chat_id: int, message_id: int):
    db.execute(
        "DELETE FROM messages WHERE connection_id=? AND chat_id=? AND message_id=?",
        (connection_id, chat_id, message_id)
    )
    db.commit()

@dp.message(F.text.regexp(r"^/start(?:\s+.*)?$", flags=re.IGNORECASE))
async def start(message: Message):
    log.info("[START] /start received chat=%s user=%s", message.chat.id, getattr(message.from_user, "id", None))
    name = message.from_user.first_name if message.from_user else "пользователь"

    caption = (
        f"👋 <b>Добро пожаловать, {name}!</b>\n\n"
        f"<b>LoudGram</b> — многофункциональный помощник в личных сообщениях.\n\n"
        f"{pe('guide')} Используй кнопки ниже, чтобы открыть нужный раздел."
    )

    if BANNER_PATH and Path(BANNER_PATH).is_file():
        from aiogram.types import FSInputFile
        await message.answer_photo(
            FSInputFile(BANNER_PATH),
            caption=caption,
            reply_markup=menu(),
            parse_mode="HTML",
        )
    else:
        await answer_message(
            message,
            caption,
            reply_markup=menu(),
            parse_mode="HTML",
        )

@dp.message(F.text == ".help")
async def help_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "🛠 <b>Справка по командам</b>\n"
        "<b>Твоя подписка:</b> обычная\n"
        "<b>Формат:</b> .команда — описание\n\n"
        "<b>📝 Профиль</b>\n\n"
        "> <code>.copy</code> — показать данные профиля (без клонирования чужой личности)\n"
        "> <code>.nick</code> — Авто смена ника: <code>.nick</code> / <code>.nick off</code>\n"
        "> <code>.publ</code> — Публикация доступного медиа в поддерживаемом режиме\n"
        "> <code>.status</code> — Настройка статуса профиля\n"
        "> <code>.stories</code> — Подготовка фото для истории\n"
        "> <code>.time</code> — Авто-время: <code>.time on UTC+3</code> / <code>.time off</code>\n\n"
        "<b>🔥 Серии</b>\n\n"
        "> <code>.streak</code> — Серия сообщений\n"
        "> <code>.streak_freeze</code> — Заморозить серию\n"
        "> <code>.streak_recover</code> — Восстановить проваленную серию\n"
        "> <code>.streak_restart</code> — Перезапустить серию с сохранением рекорда\n"
        "> <code>.streak_top</code> — Топ серий\n"
        "> <code>.streak_unfreeze</code> — Разморозить серию\n\n"
        "<b>🎲 Развлечения</b>\n\n"
        "> <code>.a_format</code> — Авто-форматирование своих сообщений\n"
        "> <code>.a_mute</code> — Авто-удаление сообщений собеседника: вкл/выкл\n"
        "> <code>.a_troll</code> — Автоответ после каждого сообщения собеседника; <code>.a_troll off</code> — выкл\n"
        "> <code>.act</code> — Имитация действия в чате\n"
        "> <code>.cat</code> — Случайное фото кота\n"
        "> <code>.coin</code> — Орёл или Решка\n"
        "> <code>.fco</code> — Предсказание на сегодня\n"
        "> <code>.ghoul</code> — Я гуль...\n"
        "> <code>.love</code> — Анимация сердца\n"
        "> <code>.online</code> — Информационная имитация режима онлайна\n"
        "> <code>.rps</code> — Камень-Ножницы-Бумага\n"
        "> <code>.save</code> — Сохранить доступное медиа\n"
        "> <code>.send</code> — Тестовая карточка суммы; не является платежом\n"
        "> <code>.spam</code> — Отключено\n"
        "> <code>.troll</code> — Отправить 3 случайные фразы из <code>troll_message</code>\n"
        "> <code>.ttt</code> — Крестики-нолики\n"
        "> <code>.typing</code> — Анимация печати\n\n"
        "<b>💎 Plus функции</b>\n\n"
        "> <code>.a_gpt</code> — Автоответ нейросетью (требуется настройка API)\n"
        "> <code>.a_gpt_off</code> — Выключить автоответ\n"
        "> <code>.doxing</code> — Команда отключена; используйте <code>.info</code> для данных собеседника\n"
        "> <code>.gpt</code> — Вопрос нейросети (требуется настройка API)\n"
        "> <code>.image</code> — Генерация изображения (требуется настройка API)\n\n"
        "<b>📌 Информация</b>\n\n"
        "> <code>.help</code> — Вызвать это сообщение\n"
        "> <code>.info</code> — Информация о собеседнике\n"
        "> <code>.ping</code> — Задержка ответа бота\n\n"
        "<b>💬 Поддержка:</b> @LoudSupport",
        parse_mode="HTML"
    )

# ============================================================
# TROLL MESSAGES
# ============================================================
a_troll_message = [
        "Перекрыл твои трубы своей членпиром, теперь ты не сможешь дышать",
     "Глобус пропихнул в твою задницу, чтобы хоть какие то знания географии в тебе остались, а то ты даже позабыл где первый раз я тебе залупой своей память отшиб",
     "сосу хуй в теле твоей мамаши, в хуй спиздани ниже",
     "ниже отпиши если твоя мать шлюха",
     "че замолк идиот ебаный мать те ебём",
     "Я КОГДА ВЫЕБАЛ ТВОЮ МАТЬ Я СВОЙ ХУЙ ПОСТАВИЛ К ЕЁ УХУ, ЧТОБ ОНА СЛЫШАЛА ПРИБОЯ СПЕРМЫ, А ПОТОМ ОНА ШИРОКО РАСКРЫЛА РОТ  МЫ В ЕЁ ЕБЛЯТНИКЕ УСТРОИЛИ ОКЕАН",
     "воздух = мой член, дыши глубже",
     "рыло те ебём",
     "Твою ускую пезду разорвал своим между ножным боевым орудием,которое в старые времена выручало меня против сопливого рыла твоего деда",
     "ЕСЛИ ТЫ СЕЙЧАС ТАК И БУДЕШЬ ПРОДОЛЖАТЬ ПРОТИВОРЕЧИТЬ МОЕМУ ХУЮ, КАК ИМ КАК БЛЯДЬ НА НЛО ЗАХВОЧУ ТВОЁ ОЧКО И НАЧНУ ОПЫТЫ ПРОВОДИТЬ",
     "с этими словами я твою мать в подвале ебал, а ты сосал член моему псу и что отцу своему орал?)",
     "Устроил армагеддон в анальном чистилище твоей слабоумной мамаши, мозги которой я выбил ещё давно",
     "пошел нахуй",
     "с этой провокацией твоя мать ебала тебя страпаном в анал ,а ты что ей орал когда хуй отца досасывал?",
     "член выжуй огромный",
     "Подобью твои копытца трупными иглами дабы на тебе порча некая висела тупой блять обмудок",
     "Сосеш ты мне блядина ебаная",
     "Кровоточивость дёсен твоего отца усилилась после прихода моей хуины в его ротовой полости",
     "Задушил тебя ленточкой выпускника, когда ты лизал пездак своей жирной химички за тройку в году",
     "ТЫ ПОНИМАЕШЬ ЧТО КОГДА Я ТВОЮ МАТЬ ОНА КАК ШЛЮХА ЛОЖИТСЯ НА СПИНКУ И НАЧИНАЕТ ПОСАСЫВАТЬ МОИ ЯЙЦА",
     "я тя парой слов ебу, пока ты потеешь мне в залупу",
     "БЛЯТЬ МОЕ ГОВНО ЖУЙ КОМУ Я СКАЗАЛ БЛЯТЬ!!!!",
     "твоя мать шлюха соберись давай с силами идиот ебаный и придумай хоть какие то слова сын шлюхи зашуганный",
     "Зубной щёткой промыл твой кишечник, для того, чтобы твоя мать видела, какой у неё сын еблан, вырос под опекой моего хуя не отцепляясь всю жизнь",
     "всем селом тебя негры ебали",
     "ебальник закрой и соси тут сын шлюхи",
]

troll_message = [
        "Перекрыл твои трубы своей членпиром, теперь ты не сможешь дышать",
     "Глобус пропихнул в твою задницу, чтобы хоть какие то знания географии в тебе остались, а то ты даже позабыл где первый раз я тебе залупой своей память отшиб",
     "сосу хуй в теле твоей мамаши, в хуй спиздани ниже",
     "ниже отпиши если твоя мать шлюха",
     "че замолк идиот ебаный мать те ебём",
     "Я КОГДА ВЫЕБАЛ ТВОЮ МАТЬ Я СВОЙ ХУЙ ПОСТАВИЛ К ЕЁ УХУ, ЧТОБ ОНА СЛЫШАЛА ПРИБОЯ СПЕРМЫ, А ПОТОМ ОНА ШИРОКО РАСКРЫЛА РОТ  МЫ В ЕЁ ЕБЛЯТНИКЕ УСТРОИЛИ ОКЕАН",
     "воздух = мой член, дыши глубже",
     "рыло те ебём",
     "Твою ускую пезду разорвал своим между ножным боевым орудием,которое в старые времена выручало меня против сопливого рыла твоего деда",
     "ЕСЛИ ТЫ СЕЙЧАС ТАК И БУДЕШЬ ПРОДОЛЖАТЬ ПРОТИВОРЕЧИТЬ МОЕМУ ХУЮ, КАК ИМ КАК БЛЯДЬ НА НЛО ЗАХВОЧУ ТВОЁ ОЧКО И НАЧНУ ОПЫТЫ ПРОВОДИТЬ",
     "с этими словами я твою мать в подвале ебал, а ты сосал член моему псу и что отцу своему орал?)",
     "Устроил армагеддон в анальном чистилище твоей слабоумной мамаши, мозги которой я выбил ещё давно",
     "пошел нахуй",
     "с этой провокацией твоя мать ебала тебя страпаном в анал ,а ты что ей орал когда хуй отца досасывал?",
     "член выжуй огромный",
     "Подобью твои копытца трупными иглами дабы на тебе порча некая висела тупой блять обмудок",
     "Сосеш ты мне блядина ебаная",
     "Кровоточивость дёсен твоего отца усилилась после прихода моей хуины в его ротовой полости",
     "Задушил тебя ленточкой выпускника, когда ты лизал пездак своей жирной химички за тройку в году",
     "ТЫ ПОНИМАЕШЬ ЧТО КОГДА Я ТВОЮ МАТЬ ОНА КАК ШЛЮХА ЛОЖИТСЯ НА СПИНКУ И НАЧИНАЕТ ПОСАСЫВАТЬ МОИ ЯЙЦА",
     "я тя парой слов ебу, пока ты потеешь мне в залупу",
     "БЛЯТЬ МОЕ ГОВНО ЖУЙ КОМУ Я СКАЗАЛ БЛЯТЬ!!!!",
     "твоя мать шлюха соберись давай с силами идиот ебаный и придумай хоть какие то слова сын шлюхи зашуганный",
     "Зубной щёткой промыл твой кишечник, для того, чтобы твоя мать видела, какой у неё сын еблан, вырос под опекой моего хуя не отцепляясь всю жизнь",
     "всем селом тебя негры ебали",
     "ебальник закрой и соси тут сын шлюхи",
]

A_TROLL_ENABLED = set()

async def send_troll_messages(message: Message, messages: list[str], count: int = 1):
    import random

    available = [str(x).strip() for x in messages if str(x).strip()]
    if not available:
        await answer_message(
            message,
            "⚠️ Список сообщений пуст. Добавь фразы в "
            "<code>a_troll_message</code> или <code>troll_message</code>.",
            parse_mode="HTML",
        )
        return

    count = min(count, len(available))
    for item in random.sample(available, count):
        await answer_message(message, item)

async def simple_extra_command(message: Message, command: str):
    texts = {
        ".copy": "👤 <b>.copy</b>\n\nПоказываю данные твоего профиля через <code>.info</code>. Клонирование чужого профиля/аватара не выполняется.",
        ".publ": "📌 <b>.publ</b>\n\nКоманда распознана. Публикация в Stories требует соответствующих прав Telegram Business/API.",
        ".status": "⚙️ <b>.status</b>\n\nОткройте команду в подключённом Business-чате, чтобы настроить авто-статусы.",
        ".stories": "🖼 <b>.stories</b>\n\nКоманда распознана. Для публикации Stories нужны поддерживаемые Telegram API-права.",
        ".streak_freeze": "🧊 <b>.streak_freeze</b>\n\nФункция серии распознана; сохранение состояния серии требует отдельного хранилища.",
        ".streak_recover": "🔄 <b>.streak_recover</b>\n\nВосстановление серии распознано; отдельное хранилище серии ещё не подключено.",
        ".streak_restart": "♻️ <b>.streak_restart</b>\n\nПерезапуск серии распознан; отдельное хранилище серии ещё не подключено.",
        ".streak_top": "🏆 <b>.streak_top</b>\n\nТоп серий будет доступен после подключения постоянного хранилища статистики.",
        ".streak_unfreeze": "🔥 <b>.streak_unfreeze</b>\n\nРазморозка серии распознана; отдельное хранилище серии ещё не подключено.",
        ".a_format": "✍️ <b>.a_format</b>\n\nАвтоформатирование распознано. Для автоматического изменения каждого сообщения нужна отдельная настройка режима.",
        ".a_mute": "🔇 <b>.a_mute</b>\n\nИспользуй <code>.a_mute on</code> или <code>.a_mute off</code>. Автоудаление можно включить только для подключённого Business-чата.",
        ".a_troll": "😈 <b>.a_troll</b>\n\nИгровой режим распознан. Автоматический спам/оскорбления не выполняются.",
        ".act": "🎭 <b>.act</b>\n\nПример: <code>.act typing</code>. Имитация действия выполняется только через Telegram chat action.",
        ".coin": "🪙 <b>.coin</b>\n\nОрёл или Решка: <code>.coin</code> — случайный результат.",
        ".fco": "🔮 <b>.fco</b>\n\nСегодня: всё получится, если начать с маленького шага.",
        ".love": "❤️ <b>.love</b>\n\n❤️\n💗❤️💗\n❤️💗❤️💗❤️\n💗❤️💗❤️💗❤️💗",
        ".online": "🟢 <b>.online</b>\n\nКоманда распознана. Реальное изменение Telegram presence ботом не гарантируется API.",
        ".rps": "✊ <b>.rps</b>\n\nВыбери: <code>.rps камень</code>, <code>.rps ножницы</code> или <code>.rps бумага</code>.",
        ".troll": "😈 <b>.troll</b>\n\nБезопасный игровой режим: без массовой рассылки и оскорблений.",
        ".ttt": "❌⭕ <b>.ttt</b>\n\nИгровая команда распознана. Поле можно добавить отдельным модулем состояния партий.",
        ".typing": "⌨️ <b>.typing</b>\n\nИмитация печати доступна через Telegram chat action в Business-чате.",
        ".a_gpt": "🤖 <b>.a_gpt</b>\n\nКоманда распознана. Для реального GPT-ответа требуется настроить API/модель.",
        ".a_gpt_off": "⏹ <b>.a_gpt_off</b>\n\nАвтоответ GPT отключён на уровне режима команды.",
        ".doxing": "🔒 <b>.doxing</b>\n\nПоиск/сбор чувствительных персональных данных отключён. Используй <code>.info</code> для обычной информации о собеседнике.",
        ".gpt": "🤖 <b>.gpt</b>\n\nДля реального ответа нейросети требуется настроить API/модель.",
        ".image": "🖼 <b>.image</b>\n\nДля генерации изображений требуется подключить image API.",
        ".ping": "🏓 <b>Pong</b> — ответ получен.",
    }
    await answer_message(message, texts.get(command, f"Команда <code>{command}</code> распознана."), parse_mode="HTML")

async def coin_command(message: Message):
    import random
    await answer_message(message, "🪙 " + random.choice(["Орёл", "Решка"]))

async def ping_command(message: Message):
    started = datetime.now(timezone.utc)
    sent = await answer_message(message, "🏓 Проверяю задержку…")
    elapsed = (datetime.now(timezone.utc) - started).total_seconds() * 1000
    try:
        await sent.edit_text(f"🏓 <b>Pong</b> — ~{elapsed:.0f} ms", parse_mode="HTML")
    except Exception:
        pass

@dp.message(F.text.regexp(r"^\.status$", flags=re.IGNORECASE))
async def status_command(message: Message):
    if await reject_non_owner_command(message): return
    if not message.business_connection_id:
        await answer_message(message,"❌ <b>.status</b> доступна в подключённом Business-чате.",parse_mode="HTML"); return
    await show_status_menu(message,message.business_connection_id)

# Старая версия info_command (будет заменена в части 4)
@dp.message(F.text == ".info")
async def info_command_old(message: Message):
    if await reject_non_owner_command(message):
        return
    user = message.from_user
    last_seen = None
    if message.business_connection_id:
        row = db.execute(
            "SELECT MAX(created_at) FROM messages WHERE connection_id=? AND chat_id=? AND sender_id=?",
            (message.business_connection_id, message.chat.id, user.id),
        ).fetchone()
        last_seen = row[0] if row and row[0] else None
    enabled, tz_name = get_time_setting(get_connection(message.business_connection_id)[0]) if message.business_connection_id and get_connection(message.business_connection_id) else (0, "UTC")
    last_seen_text = format_local_timestamp(last_seen, tz_name) if last_seen else "неизвестно"
    username_line = f"Username: @{user.username}" if user.username else "Username: —"
    last_name = getattr(user, "last_name", None) or "—"
    await answer_message(message,
        f"ℹ️ <b>Информация</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Имя: {user.first_name or '—'}\n"
        f"Last name: {last_name}\n"
        f"{username_line}\n"
        f"🕒 Last seen: <code>[{last_seen_text}]</code>",
        parse_mode="HTML"
    )

@dp.message(F.text == ".ghoul")
async def ghoul_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message, "👻 1000 - 7 = 993\n\nDead Inside.")

@dp.message(F.text == ".streak")
async def streak_command_old(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "🔥 <b>Streak</b>\n\n"
        "Счётчик серии общения готов к подключению к архиву чата.",
        parse_mode="HTML"
    )

@dp.message(F.text == ".cat")
async def cat_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "🐱 .cat — команда подключена. "
        "Источник случайных изображений можно настроить отдельно."
    )

@dp.message(F.text == ".save")
async def save_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "💾 .save — команда сохранения медиа. "
        "Для Business-чата сохранение выполняется автоматически при получении сообщения."
    )

@dp.message(F.text.startswith(".a_troll"))
async def a_troll_command(message: Message):
    if await reject_non_owner_command(message):
        return
    connection_id = getattr(message, "business_connection_id", None)
    if not connection_id:
        await answer_message(
            message,
            "❌ <b>.a_troll</b> работает в подключённом Business-чате.",
            parse_mode="HTML",
        )
        return
    parts = (message.text or "").strip().lower().split()
    key = (connection_id, message.chat.id)

    if len(parts) > 1 and parts[1] == "off":
        A_TROLL_ENABLED.discard(key)
        await answer_message(message, "⏹ <b>.a_troll выключен.</b>", parse_mode="HTML")
        return

    if not any(str(x).strip() for x in a_troll_message):
        await answer_message(
            message,
            "⚠️ Список <code>a_troll_message</code> пуст. Добавь фразы в начале файла.",
            parse_mode="HTML",
        )
        return

    A_TROLL_ENABLED.add(key)
    await answer_message(
        message,
        "😈 <b>.a_troll включён.</b>\n\n"
        "После каждого сообщения собеседника будет отправляться "
        "случайная фраза из <code>a_troll_message</code>.\n\n"
        "Выключить: <code>.a_troll off</code>",
        parse_mode="HTML",
    )

@dp.message(F.text == ".troll")
async def troll_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await send_troll_messages(message, troll_message, count=3)

# .send будет переопределён в части 4 новым, поэтому здесь мы его не трогаем

# .time on/off, .mute, .unmute, .diag, .nick, .status и др. — они ниже.

# ========== ОБРАБОТЧИКИ .time, .mute, .unmute, .nick, .diag ==========
# Они уже есть в вашем исходном коде, я их включаю для полноты,
# но чтобы не дублировать, я добавлю их в этом блоке.

@dp.message(F.text.regexp(r"^\.time\s+on(?:\s+(.+))?$"))
async def time_on_command(message: Message):
    if await reject_non_owner_command(message):
        return

    match = re.match(r"^\.time\s+on(?:\s+(.+))?$", message.text.strip(), re.IGNORECASE)
    value = match.group(1).strip() if match and match.group(1) else None

    if not value:
        timezone_waiting.add(message.from_user.id)
        await answer_message(
            message,
            "🕒 <b>.time on</b>\n\n"
            "Укажите часовой пояс, например <code>UTC+3</code>.\n"
            "Если не знаете свой часовой пояс — нажмите кнопку ниже и введите город "
            "(например, <b>Москва</b>).",
            reply_markup=timezone_keyboard(),
            parse_mode="HTML",
        )
        return

    parsed = parse_timezone(value)
    if not parsed:
        timezone_waiting.add(message.from_user.id)
        await answer_message(
            message,
            "❌ Не удалось распознать часовой пояс.\n\n"
            "Пример: <code>UTC+3</code>, <code>UTC+05:30</code> или название города.",
            reply_markup=timezone_keyboard(),
            parse_mode="HTML",
        )
        return

    tz, tz_name = parsed
    timezone_waiting.discard(message.from_user.id)
    set_time_setting(message.from_user.id, True, tz_name)

    conn = get_connection(message.business_connection_id) if message.business_connection_id else None
    last_activity = None
    if conn and message.business_connection_id:
        last_activity = get_interlocutor_last_activity(
            message.business_connection_id, message.chat.id, conn[0]
        )

    activity_ts = last_activity or message.date.timestamp()
    activity_time = datetime.fromtimestamp(
        activity_ts, timezone.utc
    ).astimezone(tz).strftime("%H:%M")

    if conn and message.business_connection_id:
        try:
            await set_business_last_name(
                message.business_connection_id,
                f"[{activity_time}]",
            )
        except Exception as exc:
            log.exception("[TIME] failed to set Business Last name")
            await answer_message(
                message,
                "⚠️ Часовой пояс сохранён, но Last name изменить не удалось.\n\n"
                f"<code>{escape_html(str(exc)[:900])}</code>",
                parse_mode="HTML",
            )
            return

    await answer_message(
        message,
        "✅ <b>Время включено.</b>\n\n"
        f"🌍 Часовой пояс: <code>{tz_name}</code>\n"
        f"🕒 Last name: <code>[{activity_time}]</code>\n\n"
        "При каждом новом сообщении собеседника Last name будет обновляться "
        "на время его последней активности.",
        parse_mode="HTML",
    )

@dp.message(F.text.regexp(r"^\.time\s+off$"))
async def time_off_command(message: Message):
    if await reject_non_owner_command(message):
        return

    timezone_waiting.discard(message.from_user.id)
    set_time_setting(message.from_user.id, False)
    await answer_message(message, "⏹ <b>Отображение времени отключено.</b>", parse_mode="HTML")

@dp.message(F.text.regexp(r"^\.time(?:\s+.*)?$"))
async def time_command_help(message: Message):
    if await reject_non_owner_command(message):
        return

    text = (message.text or "").strip()
    if re.match(r"^\.time\s+(on|off)(?:\s+.*)?$", text, re.IGNORECASE):
        return
    await answer_message(
        message,
        "❌ <b>Команда .time указана неправильно.</b>\n\n"
        "Чтобы включить время: <code>.time on UTC+3</code>\n"
        "или просто <code>.time on</code>, затем выберите/укажите город.\n\n"
        "Чтобы выключить: <code>.time off</code>.",
        reply_markup=time_error_keyboard(),
        parse_mode="HTML",
    )

@dp.message(F.text.regexp(r"^\.mute(?:\s+\d+)?$"))
async def mute_command(message: Message):
    if await reject_non_owner_command(message):
        return

    connection_id = message.business_connection_id
    if not connection_id:
        await answer_message(message, "❌ <b>.mute</b> доступна в подключённом Business-чате.", parse_mode="HTML")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit() or not (1 <= int(parts[1]) <= 10080):
        await answer_message(message, "❌ Использование: <code>.mute 300</code> — мут на 300 минут.\n\nМожно отправить ответом на сообщение собеседника или просто написать <code>.mute 300</code> в личном Business-чате.", parse_mode="HTML")
        return
    target = target_from_message(message)
    if not target:
        await answer_message(message, "❌ Не найден собеседник. Сначала дождитесь сообщения от собеседника, затем напишите <code>.mute 300</code> или ответьте этой командой на его сообщение.", parse_mode="HTML")
        return
    if message.from_user and int(target.id) == int(message.from_user.id):
        await answer_message(message, "❌ Нельзя замутить самого себя.", parse_mode="HTML")
        return
    minutes = int(parts[1])
    until = int(datetime.now(timezone.utc).timestamp()) + minutes * 60
    mode = "restrict" if message.chat.type in {"group", "supergroup"} else "soft"
    if mode == "restrict":
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
                use_independent_chat_permissions=True,
            )
        except Exception as exc:
            await answer_message(message, f"❌ <b>Не удалось замутить пользователя.</b>\n\n<code>{str(exc)[:700]}</code>\n\nПроверь, что бот — администратор и имеет право <b>Ограничивать участников</b>.", parse_mode="HTML")
            return
    mute_id = create_mute(connection_id, message.chat.id, target.id, message.from_user.id, until, mode)
    await delete_business_message(message)
    await answer_message(
        message,
        f"🔇 <b>Собеседник замучен на {minutes} минут.</b>\n\n"
        f"👤 {target.full_name}\n"
        f"⏳ До: <code>{datetime.fromtimestamp(until, timezone.utc).strftime('%H:%M')}</code>",
        reply_markup=mute_keyboard(mute_id),
        parse_mode="HTML",
    )

@dp.callback_query(F.data.startswith("unmute:"))
async def unmute_callback(callback: CallbackQuery):
    data = str(callback.data or "")
    log.info("[UNMUTE BUTTON] callback_data=%r from=%s", data, callback.from_user.id)

    try:
        mute_id = data.split(":", 1)[1].strip()
        if not mute_id:
            raise ValueError
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректные данные кнопки.", show_alert=True)
        return

    mute = get_mute(mute_id)
    if not mute or not int(mute[7]):
        await callback.answer("Мут уже снят или истёк.", show_alert=True)
        return

    _, connection_id, chat_id, target_user_id, muter_user_id, until_ts, mode, active = mute
    if int(callback.from_user.id) != int(muter_user_id):
        await callback.answer("⛔ Только тот, кто установил мут, может его снять.", show_alert=True)
        log.warning(
            "[UNMUTE] unauthorized button actor=%s owner=%s target=%s mute=%s",
            callback.from_user.id, muter_user_id, target_user_id, mute_id,
        )
        return

    try:
        if mode == "restrict":
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
                use_independent_chat_permissions=True,
            )

        set_mute_inactive(mute_id)

        if callback.message:
            try:
                await answer_callback_message(
                    callback,
                    "🟢 <b>Собеседник размучен.</b>",
                    parse_mode="HTML",
                )
            except Exception:
                log.exception("[UNMUTE] failed to replace button message")

        await callback.answer("✅ Мут снят.")
    except Exception as exc:
        log.exception("[UNMUTE] failed mute=%s target=%s: %s", mute_id, target_user_id, exc)
        await callback.answer("❌ Не удалось снять мут.", show_alert=True)

@dp.message(F.text.regexp(r"^\.unmute(?:\s*)$", flags=re.IGNORECASE))
async def unmute_command(message: Message):
    connection_id = message.business_connection_id
    if not connection_id:
        await answer_message(message, "❌ <b>.unmute</b> доступна в подключённом Business-чате.", parse_mode="HTML")
        return

    if not message.from_user:
        return

    mute = get_active_mute_for_chat(connection_id, message.chat.id)
    if not mute:
        await answer_message(message, "ℹ️ В этом чате активного мута нет.", parse_mode="HTML")
        return

    mute_id, target_user_id, muter_user_id, until_ts, mode = mute
    if int(message.from_user.id) != int(muter_user_id):
        await answer_message(message, "⛔ Только тот, кто установил мут, может его снять.", parse_mode="HTML")
        return

    try:
        if mode == "restrict":
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target_user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
                use_independent_chat_permissions=True,
            )
        set_mute_inactive(mute_id)
        await delete_business_message(message)
        await answer_message(message, "🟢 <b>Собеседник размучен.</b>", parse_mode="HTML")
    except Exception as exc:
        log.exception("[UNMUTE] command failed mute=%s: %s", mute_id, exc)
        await answer_message(message, f"❌ <b>Не удалось снять мут.</b>\n\n<code>{str(exc)[:700]}</code>", parse_mode="HTML")

@dp.message(F.text == ".nick")
async def nick_command(message: Message):
    if await reject_non_owner_command(message):
        return
    if not message.business_connection_id:
        await answer_message(message, "❌ <b>.nick</b> доступна в подключённом Business-чате.", parse_mode="HTML")
        return
    await show_nick_menu(message, message.business_connection_id)

@dp.message(F.text.regexp(r"^\.diag$"))
async def diag_command(message: Message):
    if await reject_non_owner_command(message):
        return

    connection_id = getattr(message, "business_connection_id", None)
    if not connection_id:
        await answer_message(
            message,
            "ℹ️ <b>Диагностика</b>\n\nЭто обычный чат бота, не Business-чата.",
            parse_mode="HTML",
        )
        return

    conn = await ensure_connection(connection_id)
    if not conn:
        await answer_message(
            message,
            "❌ Не удалось получить BusinessConnection из Telegram.",
            parse_mode="HTML",
        )
        return

    row = db.execute(
        "SELECT can_reply FROM connections WHERE connection_id=?",
        (connection_id,)
    ).fetchone()
    can_reply = bool(row[0]) if row else False

    await answer_message(
        message,
        "🔧 <b>Business диагностика</b>\n\n"
        f"Connection: <code>{connection_id}</code>\n"
        f"Enabled: <b>{'да' if conn[2] else 'нет'}</b>\n"
        f"Reply: <b>{'да' if can_reply else 'нет'}</b>\n\n"
        "Проверка использует право Business Bot API: <code>can_reply</code>.\n"
        "Если Reply = нет — включите право «Отвечать на сообщения» "
        "в настройках Telegram Business-бота.",
        parse_mode="HTML",
    )@dp.message(F.text.regexp(r"^/start(?:\s+.*)?$", flags=re.IGNORECASE))
async def start(message: Message):
    log.info("[START] /start received chat=%s user=%s", message.chat.id, getattr(message.from_user, "id", None))
    name = message.from_user.first_name if message.from_user else "пользователь"

    caption = (
        f"👋 <b>Добро пожаловать, {name}!</b>\n\n"
        f"<b>LoudGram</b> — многофункциональный помощник в личных сообщениях.\n\n"
        f"{pe('guide')} Используй кнопки ниже, чтобы открыть нужный раздел."
    )

    if BANNER_PATH and Path(BANNER_PATH).is_file():
        from aiogram.types import FSInputFile
        await message.answer_photo(
            FSInputFile(BANNER_PATH),
            caption=caption,
            reply_markup=menu(),
            parse_mode="HTML",
        )
    else:
        await answer_message(
            message,
            caption,
            reply_markup=menu(),
            parse_mode="HTML",
        )

@dp.message(F.text == ".help")
async def help_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "🛠 <b>Справка по командам</b>\n"
        "<b>Твоя подписка:</b> обычная\n"
        "<b>Формат:</b> .команда — описание\n\n"
        "<b>📝 Профиль</b>\n\n"
        "> <code>.copy</code> — показать данные профиля (без клонирования чужой личности)\n"
        "> <code>.nick</code> — Авто смена ника: <code>.nick</code> / <code>.nick off</code>\n"
        "> <code>.publ</code> — Публикация доступного медиа в поддерживаемом режиме\n"
        "> <code>.status</code> — Настройка статуса профиля\n"
        "> <code>.stories</code> — Подготовка фото для истории\n"
        "> <code>.time</code> — Авто-время: <code>.time on UTC+3</code> / <code>.time off</code>\n\n"
        "<b>🔥 Серии</b>\n\n"
        "> <code>.streak</code> — Серия сообщений\n"
        "> <code>.streak_freeze</code> — Заморозить серию\n"
        "> <code>.streak_recover</code> — Восстановить проваленную серию\n"
        "> <code>.streak_restart</code> — Перезапустить серию с сохранением рекорда\n"
        "> <code>.streak_top</code> — Топ серий\n"
        "> <code>.streak_unfreeze</code> — Разморозить серию\n\n"
        "<b>🎲 Развлечения</b>\n\n"
        "> <code>.a_format</code> — Авто-форматирование своих сообщений\n"
        "> <code>.a_mute</code> — Авто-удаление сообщений собеседника: вкл/выкл\n"
        "> <code>.a_troll</code> — Автоответ после каждого сообщения собеседника; <code>.a_troll off</code> — выкл\n"
        "> <code>.act</code> — Имитация действия в чате\n"
        "> <code>.cat</code> — Случайное фото кота\n"
        "> <code>.coin</code> — Орёл или Решка\n"
        "> <code>.fco</code> — Предсказание на сегодня\n"
        "> <code>.ghoul</code> — Я гуль...\n"
        "> <code>.love</code> — Анимация сердца\n"
        "> <code>.online</code> — Информационная имитация режима онлайна\n"
        "> <code>.rps</code> — Камень-Ножницы-Бумага\n"
        "> <code>.save</code> — Сохранить доступное медиа\n"
        "> <code>.send</code> — Тестовая карточка суммы; не является платежом\n"
        "> <code>.spam</code> — Отключено\n"
        "> <code>.troll</code> — Отправить 3 случайные фразы из <code>troll_message</code>\n"
        "> <code>.ttt</code> — Крестики-нолики\n"
        "> <code>.typing</code> — Анимация печати\n\n"
        "<b>💎 Plus функции</b>\n\n"
        "> <code>.a_gpt</code> — Автоответ нейросетью (требуется настройка API)\n"
        "> <code>.a_gpt_off</code> — Выключить автоответ\n"
        "> <code>.doxing</code> — Команда отключена; используйте <code>.info</code> для данных собеседника\n"
        "> <code>.gpt</code> — Вопрос нейросети (требуется настройка API)\n"
        "> <code>.image</code> — Генерация изображения (требуется настройка API)\n\n"
        "<b>📌 Информация</b>\n\n"
        "> <code>.help</code> — Вызвать это сообщение\n"
        "> <code>.info</code> — Информация о собеседнике\n"
        "> <code>.ping</code> — Задержка ответа бота\n\n"
        "<b>💬 Поддержка:</b> @LoudSupport",
        parse_mode="HTML"
    )

# ============================================================
# TROLL MESSAGES
# ============================================================
a_troll_message = [
        "Перекрыл твои трубы своей членпиром, теперь ты не сможешь дышать",
     "Глобус пропихнул в твою задницу, чтобы хоть какие то знания географии в тебе остались, а то ты даже позабыл где первый раз я тебе залупой своей память отшиб",
     "сосу хуй в теле твоей мамаши, в хуй спиздани ниже",
     "ниже отпиши если твоя мать шлюха",
     "че замолк идиот ебаный мать те ебём",
     "Я КОГДА ВЫЕБАЛ ТВОЮ МАТЬ Я СВОЙ ХУЙ ПОСТАВИЛ К ЕЁ УХУ, ЧТОБ ОНА СЛЫШАЛА ПРИБОЯ СПЕРМЫ, А ПОТОМ ОНА ШИРОКО РАСКРЫЛА РОТ  МЫ В ЕЁ ЕБЛЯТНИКЕ УСТРОИЛИ ОКЕАН",
     "воздух = мой член, дыши глубже",
     "рыло те ебём",
     "Твою ускую пезду разорвал своим между ножным боевым орудием,которое в старые времена выручало меня против сопливого рыла твоего деда",
     "ЕСЛИ ТЫ СЕЙЧАС ТАК И БУДЕШЬ ПРОДОЛЖАТЬ ПРОТИВОРЕЧИТЬ МОЕМУ ХУЮ, КАК ИМ КАК БЛЯДЬ НА НЛО ЗАХВОЧУ ТВОЁ ОЧКО И НАЧНУ ОПЫТЫ ПРОВОДИТЬ",
     "с этими словами я твою мать в подвале ебал, а ты сосал член моему псу и что отцу своему орал?)",
     "Устроил армагеддон в анальном чистилище твоей слабоумной мамаши, мозги которой я выбил ещё давно",
     "пошел нахуй",
     "с этой провокацией твоя мать ебала тебя страпаном в анал ,а ты что ей орал когда хуй отца досасывал?",
     "член выжуй огромный",
     "Подобью твои копытца трупными иглами дабы на тебе порча некая висела тупой блять обмудок",
     "Сосеш ты мне блядина ебаная",
     "Кровоточивость дёсен твоего отца усилилась после прихода моей хуины в его ротовой полости",
     "Задушил тебя ленточкой выпускника, когда ты лизал пездак своей жирной химички за тройку в году",
     "ТЫ ПОНИМАЕШЬ ЧТО КОГДА Я ТВОЮ МАТЬ ОНА КАК ШЛЮХА ЛОЖИТСЯ НА СПИНКУ И НАЧИНАЕТ ПОСАСЫВАТЬ МОИ ЯЙЦА",
     "я тя парой слов ебу, пока ты потеешь мне в залупу",
     "БЛЯТЬ МОЕ ГОВНО ЖУЙ КОМУ Я СКАЗАЛ БЛЯТЬ!!!!",
     "твоя мать шлюха соберись давай с силами идиот ебаный и придумай хоть какие то слова сын шлюхи зашуганный",
     "Зубной щёткой промыл твой кишечник, для того, чтобы твоя мать видела, какой у неё сын еблан, вырос под опекой моего хуя не отцепляясь всю жизнь",
     "всем селом тебя негры ебали",
     "ебальник закрой и соси тут сын шлюхи",
]

troll_message = [
        "Перекрыл твои трубы своей членпиром, теперь ты не сможешь дышать",
     "Глобус пропихнул в твою задницу, чтобы хоть какие то знания географии в тебе остались, а то ты даже позабыл где первый раз я тебе залупой своей память отшиб",
     "сосу хуй в теле твоей мамаши, в хуй спиздани ниже",
     "ниже отпиши если твоя мать шлюха",
     "че замолк идиот ебаный мать те ебём",
     "Я КОГДА ВЫЕБАЛ ТВОЮ МАТЬ Я СВОЙ ХУЙ ПОСТАВИЛ К ЕЁ УХУ, ЧТОБ ОНА СЛЫШАЛА ПРИБОЯ СПЕРМЫ, А ПОТОМ ОНА ШИРОКО РАСКРЫЛА РОТ  МЫ В ЕЁ ЕБЛЯТНИКЕ УСТРОИЛИ ОКЕАН",
     "воздух = мой член, дыши глубже",
     "рыло те ебём",
     "Твою ускую пезду разорвал своим между ножным боевым орудием,которое в старые времена выручало меня против сопливого рыла твоего деда",
     "ЕСЛИ ТЫ СЕЙЧАС ТАК И БУДЕШЬ ПРОДОЛЖАТЬ ПРОТИВОРЕЧИТЬ МОЕМУ ХУЮ, КАК ИМ КАК БЛЯДЬ НА НЛО ЗАХВОЧУ ТВОЁ ОЧКО И НАЧНУ ОПЫТЫ ПРОВОДИТЬ",
     "с этими словами я твою мать в подвале ебал, а ты сосал член моему псу и что отцу своему орал?)",
     "Устроил армагеддон в анальном чистилище твоей слабоумной мамаши, мозги которой я выбил ещё давно",
     "пошел нахуй",
     "с этой провокацией твоя мать ебала тебя страпаном в анал ,а ты что ей орал когда хуй отца досасывал?",
     "член выжуй огромный",
     "Подобью твои копытца трупными иглами дабы на тебе порча некая висела тупой блять обмудок",
     "Сосеш ты мне блядина ебаная",
     "Кровоточивость дёсен твоего отца усилилась после прихода моей хуины в его ротовой полости",
     "Задушил тебя ленточкой выпускника, когда ты лизал пездак своей жирной химички за тройку в году",
     "ТЫ ПОНИМАЕШЬ ЧТО КОГДА Я ТВОЮ МАТЬ ОНА КАК ШЛЮХА ЛОЖИТСЯ НА СПИНКУ И НАЧИНАЕТ ПОСАСЫВАТЬ МОИ ЯЙЦА",
     "я тя парой слов ебу, пока ты потеешь мне в залупу",
     "БЛЯТЬ МОЕ ГОВНО ЖУЙ КОМУ Я СКАЗАЛ БЛЯТЬ!!!!",
     "твоя мать шлюха соберись давай с силами идиот ебаный и придумай хоть какие то слова сын шлюхи зашуганный",
     "Зубной щёткой промыл твой кишечник, для того, чтобы твоя мать видела, какой у неё сын еблан, вырос под опекой моего хуя не отцепляясь всю жизнь",
     "всем селом тебя негры ебали",
     "ебальник закрой и соси тут сын шлюхи",
]

A_TROLL_ENABLED = set()

async def send_troll_messages(message: Message, messages: list[str], count: int = 1):
    import random

    available = [str(x).strip() for x in messages if str(x).strip()]
    if not available:
        await answer_message(
            message,
            "⚠️ Список сообщений пуст. Добавь фразы в "
            "<code>a_troll_message</code> или <code>troll_message</code>.",
            parse_mode="HTML",
        )
        return

    count = min(count, len(available))
    for item in random.sample(available, count):
        await answer_message(message, item)

async def simple_extra_command(message: Message, command: str):
    texts = {
        ".copy": "👤 <b>.copy</b>\n\nПоказываю данные твоего профиля через <code>.info</code>. Клонирование чужого профиля/аватара не выполняется.",
        ".publ": "📌 <b>.publ</b>\n\nКоманда распознана. Публикация в Stories требует соответствующих прав Telegram Business/API.",
        ".status": "⚙️ <b>.status</b>\n\nОткройте команду в подключённом Business-чате, чтобы настроить авто-статусы.",
        ".stories": "🖼 <b>.stories</b>\n\nКоманда распознана. Для публикации Stories нужны поддерживаемые Telegram API-права.",
        ".streak_freeze": "🧊 <b>.streak_freeze</b>\n\nФункция серии распознана; сохранение состояния серии требует отдельного хранилища.",
        ".streak_recover": "🔄 <b>.streak_recover</b>\n\nВосстановление серии распознано; отдельное хранилище серии ещё не подключено.",
        ".streak_restart": "♻️ <b>.streak_restart</b>\n\nПерезапуск серии распознан; отдельное хранилище серии ещё не подключено.",
        ".streak_top": "🏆 <b>.streak_top</b>\n\nТоп серий будет доступен после подключения постоянного хранилища статистики.",
        ".streak_unfreeze": "🔥 <b>.streak_unfreeze</b>\n\nРазморозка серии распознана; отдельное хранилище серии ещё не подключено.",
        ".a_format": "✍️ <b>.a_format</b>\n\nАвтоформатирование распознано. Для автоматического изменения каждого сообщения нужна отдельная настройка режима.",
        ".a_mute": "🔇 <b>.a_mute</b>\n\nИспользуй <code>.a_mute on</code> или <code>.a_mute off</code>. Автоудаление можно включить только для подключённого Business-чата.",
        ".a_troll": "😈 <b>.a_troll</b>\n\nИгровой режим распознан. Автоматический спам/оскорбления не выполняются.",
        ".act": "🎭 <b>.act</b>\n\nПример: <code>.act typing</code>. Имитация действия выполняется только через Telegram chat action.",
        ".coin": "🪙 <b>.coin</b>\n\nОрёл или Решка: <code>.coin</code> — случайный результат.",
        ".fco": "🔮 <b>.fco</b>\n\nСегодня: всё получится, если начать с маленького шага.",
        ".love": "❤️ <b>.love</b>\n\n❤️\n💗❤️💗\n❤️💗❤️💗❤️\n💗❤️💗❤️💗❤️💗",
        ".online": "🟢 <b>.online</b>\n\nКоманда распознана. Реальное изменение Telegram presence ботом не гарантируется API.",
        ".rps": "✊ <b>.rps</b>\n\nВыбери: <code>.rps камень</code>, <code>.rps ножницы</code> или <code>.rps бумага</code>.",
        ".troll": "😈 <b>.troll</b>\n\nБезопасный игровой режим: без массовой рассылки и оскорблений.",
        ".ttt": "❌⭕ <b>.ttt</b>\n\nИгровая команда распознана. Поле можно добавить отдельным модулем состояния партий.",
        ".typing": "⌨️ <b>.typing</b>\n\nИмитация печати доступна через Telegram chat action в Business-чате.",
        ".a_gpt": "🤖 <b>.a_gpt</b>\n\nКоманда распознана. Для реального GPT-ответа требуется настроить API/модель.",
        ".a_gpt_off": "⏹ <b>.a_gpt_off</b>\n\nАвтоответ GPT отключён на уровне режима команды.",
        ".doxing": "🔒 <b>.doxing</b>\n\nПоиск/сбор чувствительных персональных данных отключён. Используй <code>.info</code> для обычной информации о собеседнике.",
        ".gpt": "🤖 <b>.gpt</b>\n\nДля реального ответа нейросети требуется настроить API/модель.",
        ".image": "🖼 <b>.image</b>\n\nДля генерации изображений требуется подключить image API.",
        ".ping": "🏓 <b>Pong</b> — ответ получен.",
    }
    await answer_message(message, texts.get(command, f"Команда <code>{command}</code> распознана."), parse_mode="HTML")

async def coin_command(message: Message):
    import random
    await answer_message(message, "🪙 " + random.choice(["Орёл", "Решка"]))

async def ping_command(message: Message):
    started = datetime.now(timezone.utc)
    sent = await answer_message(message, "🏓 Проверяю задержку…")
    elapsed = (datetime.now(timezone.utc) - started).total_seconds() * 1000
    try:
        await sent.edit_text(f"🏓 <b>Pong</b> — ~{elapsed:.0f} ms", parse_mode="HTML")
    except Exception:
        pass

@dp.message(F.text.regexp(r"^\.status$", flags=re.IGNORECASE))
async def status_command(message: Message):
    if await reject_non_owner_command(message): return
    if not message.business_connection_id:
        await answer_message(message,"❌ <b>.status</b> доступна в подключённом Business-чате.",parse_mode="HTML"); return
    await show_status_menu(message,message.business_connection_id)

# Старая версия info_command (будет заменена в части 4)
@dp.message(F.text == ".info")
async def info_command_old(message: Message):
    if await reject_non_owner_command(message):
        return
    user = message.from_user
    last_seen = None
    if message.business_connection_id:
        row = db.execute(
            "SELECT MAX(created_at) FROM messages WHERE connection_id=? AND chat_id=? AND sender_id=?",
            (message.business_connection_id, message.chat.id, user.id),
        ).fetchone()
        last_seen = row[0] if row and row[0] else None
    enabled, tz_name = get_time_setting(get_connection(message.business_connection_id)[0]) if message.business_connection_id and get_connection(message.business_connection_id) else (0, "UTC")
    last_seen_text = format_local_timestamp(last_seen, tz_name) if last_seen else "неизвестно"
    username_line = f"Username: @{user.username}" if user.username else "Username: —"
    last_name = getattr(user, "last_name", None) or "—"
    await answer_message(message,
        f"ℹ️ <b>Информация</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Имя: {user.first_name or '—'}\n"
        f"Last name: {last_name}\n"
        f"{username_line}\n"
        f"🕒 Last seen: <code>[{last_seen_text}]</code>",
        parse_mode="HTML"
    )

@dp.message(F.text == ".ghoul")
async def ghoul_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message, "👻 1000 - 7 = 993\n\nDead Inside.")

@dp.message(F.text == ".streak")
async def streak_command_old(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "🔥 <b>Streak</b>\n\n"
        "Счётчик серии общения готов к подключению к архиву чата.",
        parse_mode="HTML"
    )

@dp.message(F.text == ".cat")
async def cat_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "🐱 .cat — команда подключена. "
        "Источник случайных изображений можно настроить отдельно."
    )

@dp.message(F.text == ".save")
async def save_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await answer_message(message,
        "💾 .save — команда сохранения медиа. "
        "Для Business-чата сохранение выполняется автоматически при получении сообщения."
    )

@dp.message(F.text.startswith(".a_troll"))
async def a_troll_command(message: Message):
    if await reject_non_owner_command(message):
        return
    connection_id = getattr(message, "business_connection_id", None)
    if not connection_id:
        await answer_message(
            message,
            "❌ <b>.a_troll</b> работает в подключённом Business-чате.",
            parse_mode="HTML",
        )
        return
    parts = (message.text or "").strip().lower().split()
    key = (connection_id, message.chat.id)

    if len(parts) > 1 and parts[1] == "off":
        A_TROLL_ENABLED.discard(key)
        await answer_message(message, "⏹ <b>.a_troll выключен.</b>", parse_mode="HTML")
        return

    if not any(str(x).strip() for x in a_troll_message):
        await answer_message(
            message,
            "⚠️ Список <code>a_troll_message</code> пуст. Добавь фразы в начале файла.",
            parse_mode="HTML",
        )
        return

    A_TROLL_ENABLED.add(key)
    await answer_message(
        message,
        "😈 <b>.a_troll включён.</b>\n\n"
        "После каждого сообщения собеседника будет отправляться "
        "случайная фраза из <code>a_troll_message</code>.\n\n"
        "Выключить: <code>.a_troll off</code>",
        parse_mode="HTML",
    )

@dp.message(F.text == ".troll")
async def troll_command(message: Message):
    if await reject_non_owner_command(message):
        return
    await send_troll_messages(message, troll_message, count=3)

# .send будет переопределён в части 4 новым, поэтому здесь мы его не трогаем

# .time on/off, .mute, .unmute, .diag, .nick, .status и др. — они ниже.

# ========== ОБРАБОТЧИКИ .time, .mute, .unmute, .nick, .diag ==========
# Они уже есть в вашем исходном коде, я их включаю для полноты,
# но чтобы не дублировать, я добавлю их в этом блоке.

@dp.message(F.text.regexp(r"^\.time\s+on(?:\s+(.+))?$"))
async def time_on_command(message: Message):
    if await reject_non_owner_command(message):
        return

    match = re.match(r"^\.time\s+on(?:\s+(.+))?$", message.text.strip(), re.IGNORECASE)
    value = match.group(1).strip() if match and match.group(1) else None

    if not value:
        timezone_waiting.add(message.from_user.id)
        await answer_message(
            message,
            "🕒 <b>.time on</b>\n\n"
            "Укажите часовой пояс, например <code>UTC+3</code>.\n"
            "Если не знаете свой часовой пояс — нажмите кнопку ниже и введите город "
            "(например, <b>Москва</b>).",
            reply_markup=timezone_keyboard(),
            parse_mode="HTML",
        )
        return

    parsed = parse_timezone(value)
    if not parsed:
        timezone_waiting.add(message.from_user.id)
        await answer_message(
            message,
            "❌ Не удалось распознать часовой пояс.\n\n"
            "Пример: <code>UTC+3</code>, <code>UTC+05:30</code> или название города.",
            reply_markup=timezone_keyboard(),
            parse_mode="HTML",
        )
        return

    tz, tz_name = parsed
    timezone_waiting.discard(message.from_user.id)
    set_time_setting(message.from_user.id, True, tz_name)

    conn = get_connection(message.business_connection_id) if message.business_connection_id else None
    last_activity = None
    if conn and message.business_connection_id:
        last_activity = get_interlocutor_last_activity(
            message.business_connection_id, message.chat.id, conn[0]
        )

    activity_ts = last_activity or message.date.timestamp()
    activity_time = datetime.fromtimestamp(
        activity_ts, timezone.utc
    ).astimezone(tz).strftime("%H:%M")

    if conn and message.business_connection_id:
        try:
            await set_business_last_name(
                message.business_connection_id,
                f"[{activity_time}]",
            )
        except Exception as exc:
            log.exception("[TIME] failed to set Business Last name")
            await answer_message(
                message,
                "⚠️ Часовой пояс сохранён, но Last name изменить не удалось.\n\n"
                f"<code>{escape_html(str(exc)[:900])}</code>",
                parse_mode="HTML",
            )
            return

    await answer_message(
        message,
        "✅ <b>Время включено.</b>\n\n"
        f"🌍 Часовой пояс: <code>{tz_name}</code>\n"
        f"🕒 Last name: <code>[{activity_time}]</code>\n\n"
        "При каждом новом сообщении собеседника Last name будет обновляться "
        "на время его последней активности.",
        parse_mode="HTML",
    )

@dp.message(F.text.regexp(r"^\.time\s+off$"))
async def time_off_command(message: Message):
    if await reject_non_owner_command(message):
        return

    timezone_waiting.discard(message.from_user.id)
    set_time_setting(message.from_user.id, False)
    await answer_message(message, "⏹ <b>Отображение времени отключено.</b>", parse_mode="HTML")

@dp.message(F.text.regexp(r"^\.time(?:\s+.*)?$"))
async def time_command_help(message: Message):
    if await reject_non_owner_command(message):
        return

    text = (message.text or "").strip()
    if re.match(r"^\.time\s+(on|off)(?:\s+.*)?$", text, re.IGNORECASE):
        return
    await answer_message(
        message,
        "❌ <b>Команда .time указана неправильно.</b>\n\n"
        "Чтобы включить время: <code>.time on UTC+3</code>\n"
        "или просто <code>.time on</code>, затем выберите/укажите город.\n\n"
        "Чтобы выключить: <code>.time off</code>.",
        reply_markup=time_error_keyboard(),
        parse_mode="HTML",
    )

@dp.message(F.text.regexp(r"^\.mute(?:\s+\d+)?$"))
async def mute_command(message: Message):
    if await reject_non_owner_command(message):
        return

    connection_id = message.business_connection_id
    if not connection_id:
        await answer_message(message, "❌ <b>.mute</b> доступна в подключённом Business-чате.", parse_mode="HTML")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit() or not (1 <= int(parts[1]) <= 10080):
        await answer_message(message, "❌ Использование: <code>.mute 300</code> — мут на 300 минут.\n\nМожно отправить ответом на сообщение собеседника или просто написать <code>.mute 300</code> в личном Business-чате.", parse_mode="HTML")
        return
    target = target_from_message(message)
    if not target:
        await answer_message(message, "❌ Не найден собеседник. Сначала дождитесь сообщения от собеседника, затем напишите <code>.mute 300</code> или ответьте этой командой на его сообщение.", parse_mode="HTML")
        return
    if message.from_user and int(target.id) == int(message.from_user.id):
        await answer_message(message, "❌ Нельзя замутить самого себя.", parse_mode="HTML")
        return
    minutes = int(parts[1])
    until = int(datetime.now(timezone.utc).timestamp()) + minutes * 60
    mode = "restrict" if message.chat.type in {"group", "supergroup"} else "soft"
    if mode == "restrict":
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
                use_independent_chat_permissions=True,
            )
        except Exception as exc:
            await answer_message(message, f"❌ <b>Не удалось замутить пользователя.</b>\n\n<code>{str(exc)[:700]}</code>\n\nПроверь, что бот — администратор и имеет право <b>Ограничивать участников</b>.", parse_mode="HTML")
            return
    mute_id = create_mute(connection_id, message.chat.id, target.id, message.from_user.id, until, mode)
    await delete_business_message(message)
    await answer_message(
        message,
        f"🔇 <b>Собеседник замучен на {minutes} минут.</b>\n\n"
        f"👤 {target.full_name}\n"
        f"⏳ До: <code>{datetime.fromtimestamp(until, timezone.utc).strftime('%H:%M')}</code>",
        reply_markup=mute_keyboard(mute_id),
        parse_mode="HTML",
    )

@dp.callback_query(F.data.startswith("unmute:"))
async def unmute_callback(callback: CallbackQuery):
    data = str(callback.data or "")
    log.info("[UNMUTE BUTTON] callback_data=%r from=%s", data, callback.from_user.id)

    try:
        mute_id = data.split(":", 1)[1].strip()
        if not mute_id:
            raise ValueError
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректные данные кнопки.", show_alert=True)
        return

    mute = get_mute(mute_id)
    if not mute or not int(mute[7]):
        await callback.answer("Мут уже снят или истёк.", show_alert=True)
        return

    _, connection_id, chat_id, target_user_id, muter_user_id, until_ts, mode, active = mute
    if int(callback.from_user.id) != int(muter_user_id):
        await callback.answer("⛔ Только тот, кто установил мут, может его снять.", show_alert=True)
        log.warning(
            "[UNMUTE] unauthorized button actor=%s owner=%s target=%s mute=%s",
            callback.from_user.id, muter_user_id, target_user_id, mute_id,
        )
        return

    try:
        if mode == "restrict":
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
                use_independent_chat_permissions=True,
            )

        set_mute_inactive(mute_id)

        if callback.message:
            try:
                await answer_callback_message(
                    callback,
                    "🟢 <b>Собеседник размучен.</b>",
                    parse_mode="HTML",
                )
            except Exception:
                log.exception("[UNMUTE] failed to replace button message")

        await callback.answer("✅ Мут снят.")
    except Exception as exc:
        log.exception("[UNMUTE] failed mute=%s target=%s: %s", mute_id, target_user_id, exc)
        await callback.answer("❌ Не удалось снять мут.", show_alert=True)

@dp.message(F.text.regexp(r"^\.unmute(?:\s*)$", flags=re.IGNORECASE))
async def unmute_command(message: Message):
    connection_id = message.business_connection_id
    if not connection_id:
        await answer_message(message, "❌ <b>.unmute</b> доступна в подключённом Business-чате.", parse_mode="HTML")
        return

    if not message.from_user:
        return

    mute = get_active_mute_for_chat(connection_id, message.chat.id)
    if not mute:
        await answer_message(message, "ℹ️ В этом чате активного мута нет.", parse_mode="HTML")
        return

    mute_id, target_user_id, muter_user_id, until_ts, mode = mute
    if int(message.from_user.id) != int(muter_user_id):
        await answer_message(message, "⛔ Только тот, кто установил мут, может его снять.", parse_mode="HTML")
        return

    try:
        if mode == "restrict":
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target_user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
                use_independent_chat_permissions=True,
            )
        set_mute_inactive(mute_id)
        await delete_business_message(message)
        await answer_message(message, "🟢 <b>Собеседник размучен.</b>", parse_mode="HTML")
    except Exception as exc:
        log.exception("[UNMUTE] command failed mute=%s: %s", mute_id, exc)
        await answer_message(message, f"❌ <b>Не удалось снять мут.</b>\n\n<code>{str(exc)[:700]}</code>", parse_mode="HTML")

@dp.message(F.text == ".nick")
async def nick_command(message: Message):
    if await reject_non_owner_command(message):
        return
    if not message.business_connection_id:
        await answer_message(message, "❌ <b>.nick</b> доступна в подключённом Business-чате.", parse_mode="HTML")
        return
    await show_nick_menu(message, message.business_connection_id)

@dp.message(F.text.regexp(r"^\.diag$"))
async def diag_command(message: Message):
    if await reject_non_owner_command(message):
        return

    connection_id = getattr(message, "business_connection_id", None)
    if not connection_id:
        await answer_message(
            message,
            "ℹ️ <b>Диагностика</b>\n\nЭто обычный чат бота, не Business-чата.",
            parse_mode="HTML",
        )
        return

    conn = await ensure_connection(connection_id)
    if not conn:
        await answer_message(
            message,
            "❌ Не удалось получить BusinessConnection из Telegram.",
            parse_mode="HTML",
        )
        return

    row = db.execute(
        "SELECT can_reply FROM connections WHERE connection_id=?",
        (connection_id,)
    ).fetchone()
    can_reply = bool(row[0]) if row else False

    await answer_message(
        message,
        "🔧 <b>Business диагностика</b>\n\n"
        f"Connection: <code>{connection_id}</code>\n"
        f"Enabled: <b>{'да' if conn[2] else 'нет'}</b>\n"
        f"Reply: <b>{'да' if can_reply else 'нет'}</b>\n\n"
        "Проверка использует право Business Bot API: <code>can_reply</code>.\n"
        "Если Reply = нет — включите право «Отвечать на сообщения» "
        "в настройках Telegram Business-бота.",
        parse_mode="HTML",
    )
# ============================================================
# КОЛБЭКИ МЕНЮ
# ============================================================

@dp.callback_query(F.data == "guide_useful")
async def guide_useful(call: CallbackQuery):
    text = (
        f"{pe('guide')} <b>Чем полезна бесплатная подписка?</b>\n\n"
        "• Сохранение одноразовых и временных медиафайлов.\n"
        "• Отслеживание изменений и удалений сообщений.\n\n"
        f"{pe('settings')} <b>Команды (Free)</b>\n\n"
        "<blockquote>"
        "• <code>.cat</code> — случайное изображение с котом.\n"
        "• <code>.ghoul</code> — 1000-7, Dead Inside.\n"
        "• <code>.info</code> — информация о пользователе.\n"
        "• <code>.streak</code> — серия общения с другом.\n"
        "• <code>.a_troll</code> — авто-троллинг в чате.\n"
        "• <code>.send (сумма)</code> — демонстрация платёжной команды.\n"
        "• <code>.save</code> — сохранение видео/медиа.\n"
        "• <code>.spam «текст»</code> — отправить текст несколько раз."
        "</blockquote>\n\n"
        "<i>Нажмите на команду для просмотра её функционала. Полный список — <code>.help</code></i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn("Далее »", "guide_useful_next", "", button_style("useful_next"))],
        [btn(f"{e('home')} В главное меню", "back_menu", "", button_style("useful_home"))],
    ])
    try:
        await answer_callback_message(call, text, reply_markup=kb, parse_mode="HTML")
        await call.answer()
    except Exception as exc:
        log.exception("[GUIDE USEFUL] callback failed: %s", exc)
        await call.answer("❌ Не удалось открыть раздел.", show_alert=True)

@dp.callback_query(F.data == "guide_useful_next")
async def guide_useful_next(call: CallbackQuery):
    text = (
        f"{pe('payment')} <b>Чем полезна подписка Plus?</b>\n\n"
        "• Доступен весь функционал бесплатной подписки без лимитов.\n\n"
        f"{pe('settings')} <b>Доп. команды:</b>\n\n"
        "<blockquote>"
        "• <code>.chat</code> — список чатов пользователя.\n"
        "• <code>.gpt «prompt»</code> — генерация текста с нейросетью.\n"
        "• <code>.image «prompt»</code> — генерация изображений.\n"
        "• <code>.a_gpt</code> — автоответчик с нейросетью."
        "</blockquote>\n\n"
        "<i>Нажмите на команду для просмотра её функционала. Полный список — <code>.help</code></i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn(f"{e('back')} Назад", "guide_useful", "", button_style("useful_back"))],
        [btn(f"{e('home')} В главное меню", "back_menu", "", button_style("useful_home"))],
    ])
    try:
        await answer_callback_message(call, text, reply_markup=kb, parse_mode="HTML")
        await call.answer()
    except Exception as exc:
        log.exception("[GUIDE USEFUL NEXT] callback failed: %s", exc)
        await call.answer("❌ Не удалось открыть продолжение.", show_alert=True)

@dp.callback_query(F.data == "guide_newbie")
async def guide_newbie(call: CallbackQuery):
    emoji = NEWBIE_GUIDE_EMOJI
    premium_id = NEWBIE_GUIDE_PREMIUM_EMOJI_ID.strip()
    if premium_id:
        emoji = f'<tg-emoji emoji-id="{escape_html(premium_id)}">{escape_html(NEWBIE_GUIDE_EMOJI)}</tg-emoji>'

    connection = False
    if call.from_user:
        row = db.execute(
            "SELECT 1 FROM connections WHERE user_id=? AND enabled=1 LIMIT 1",
            (int(call.from_user.id),),
        ).fetchone()
        connection = bool(row)

    status_text = "подключен" if connection else "не подключен"
    bot_username = getattr(bot, "username", None)
    if not bot_username:
        try:
            me = await bot.get_me()
            bot_username = me.username
        except Exception:
            bot_username = None
    bot_username = bot_username or "username_бота"

    text = (
        f"{emoji} <b>Гайд на подключение</b>\n\n"
        "Посмотрите видео-инструкцию или следуйте\n"
        "текстовой:\n\n"
        "<blockquote>"
        "1. Скопируйте username этого бота\n"
        "2. Перейдите в <b>свой профиль → Изменить</b>\n"
        "3. Найдите вкладку «автоматизация чатов»\n"
        "4. Вставьте юзер нашего бота"
        "</blockquote>\n\n"
        f"{pe('support')} <b>Статус бота:</b> {status_text}\n\n"
        "Если статус бота «подключен» — значит всё\n"
        "сделано правильно и вы можете\n"
        "использовать команды."
    )

    try:
        from aiogram.types import CopyTextButton
        copy_button = InlineKeyboardButton(
            text=f"{e('upload')} Скопировать username бота",
            copy_text=CopyTextButton(text=f"@{bot_username}"),
            style=button_style("newbie_copy", NEWBIE_GUIDE_BUTTON_STYLE),
        )
    except Exception:
        copy_button = btn(
            f"{e('upload')} @{bot_username}",
            "guide_copy_username",
            "",
            button_style("newbie_copy", NEWBIE_GUIDE_BUTTON_STYLE),
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [copy_button],
        [btn(f"{e('home')} В главное меню", "back_menu", "", button_style("newbie_home", NEWBIE_GUIDE_BUTTON_STYLE))],
    ])

    try:
        await answer_callback_message(call, text, reply_markup=kb, parse_mode="HTML")
        await call.answer()
    except Exception as exc:
        log.exception("[GUIDE NEWBIE] callback failed: %s", exc)
        await call.answer("❌ Не удалось открыть гайд.", show_alert=True)

@dp.callback_query(F.data == "guide_copy_username")
async def guide_copy_username(call: CallbackQuery):
    username = getattr(bot, "username", None) or "username_бота"
    await answer_callback_message(
        call,
        f"📋 <b>Username бота:</b> <code>@{escape_html(username)}</code>\n\nСкопируйте его и вставьте в настройках автоматизации чатов.",
        parse_mode="HTML",
    )
    await call.answer()

@dp.callback_query(F.data.startswith("cmd_"))
async def command_info(call: CallbackQuery):
    descriptions = {
        "cmd_cat": f"{pe('photo')} <b>.cat</b>\n\nОтправляет случайное изображение с котом.",
        "cmd_ghoul": f"{pe('warning')} <b>.ghoul</b>\n\nЗапускает прикол с обратным отсчётом 1000 − 7.",
        "cmd_info": f"{pe('info')} <b>.info</b>\n\nПоказывает ID, имя и username пользователя.",
        "cmd_streak": f"{pe('saved')} <b>.streak</b>\n\nПоказывает серию общения с другом. Подсчёт серии можно подключить к архиву сообщений.",
        "cmd_a_troll": f"{pe('test')} <b>.a_troll</b>\n\nКоманда для автоматического игрового троллинга в чате.",
        "cmd_send": f"{pe('payment')} <b>.send (сумма)</b>\n\nКоманда зарезервирована под тестовую демонстрацию платежного интерфейса. Фальшивые чеки и имитация реальных платежей отключены.",
        "cmd_save": f"{pe('saved')} <b>.save</b>\n\nСохраняет доступное медиа в архив Business-чата.",
        "cmd_spam": f"{pe('upload')} <b>.spam [текст]</b>\n\nОтправляет указанный текст 10 раз с интервалом 1 секунда. <code>.spam stop</code> — остановить.",
        "cmd_time_on": f"{pe('timezone')} <b>.time on</b>\n\nВключает отображение времени последней активности по выбранному часовому поясу. Пример: <code>.time on UTC+3</code>. Если пояс неизвестен, бот предложит определить его по городу.",
        "cmd_time_off": f"{pe('stop')} <b>.time off</b>\n\nОтключает отображение времени активности.",
        "cmd_nick": f"{pe('refresh')} <b>.nick</b>\n\nНастройка автоматической смены Last name по кругу через выбранный интервал.",
        "cmd_mute": f"{pe('mute')} <b>.mute 300</b>\n\nМутит пользователя на указанное число минут. Используйте команду ответом на его сообщение.",
    }
    await answer_callback_message(call, descriptions.get(call.data, "Функция пока не подключена."), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "back_menu")
async def back_menu(call: CallbackQuery):
    await answer_callback_message(call,
        "🏠 <b>Главное меню</b>",
        reply_markup=menu(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    rows = db.execute(
        "SELECT connection_id, enabled FROM connections WHERE user_id=?",
        (call.from_user.id,)
    ).fetchall()
    status = "подключён" if rows else "не подключён"
    await answer_callback_message(call,
        f"👤 <b>Мой профиль</b>\n\n"
        f"ID: <code>{call.from_user.id}</code>\n"
        f"Secretary Mode: <b>{status}</b>\n"
        f"Подключений: {len(rows)}",
        parse_mode="HTML"
    )
    await call.answer()

# ============================================================
# ПОДПИСКА И ПЛАТЕЖИ
# ============================================================

@dp.callback_query(F.data == "subscription")
async def subscription(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            btn("📅 14 Дней - 250₽", "plus_plan:14"),
            btn("📅 30 Дней - 450₽", "plus_plan:30"),
        ],
        [
            btn("📅 90 Дней - 1150₽", "plus_plan:90"),
            btn("📅 180 Дней - 1500₽", "plus_plan:180"),
        ],
        [
            btn("🏠 Назад в меню", "back_menu"),
        ],
    ])

    await answer_callback_message(
        call,
        f"{e('subscription')} <b>Подписка Plus</b>\n\n"
        "Подписка открывает доступ к дополнительным возможностям:\n\n"
        "• Увеличение лимитов ограниченных команд  ❞\n"
        "• Безлимитные сохранения одноразок\n"
        "• Доступ к генерации фото\n"
        "• Ускоренная работа бота\n\n"
        "Производя оплату вы соглашаетесь с "
        "<a href=\"https://telegram.org/tos\">пользовательским соглашением</a> и "
        "<a href=\"https://telegram.org/privacy\">политикой конфиденциальности</a>.\n\n"
        "Выберите подходящий тариф:",
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await call.answer()

@dp.callback_query(F.data.startswith("plus_plan:"))
async def plus_plan_selected(call: CallbackQuery):
    days = call.data.split(":", 1)[1]
    stars = {
        "14": PLUS_PLANS["plus_14"]["stars"],
        "30": PLUS_PLANS["plus_30"]["stars"],
        "90": PLUS_PLANS["plus_90"]["stars"],
        "180": PLUS_PLANS["plus_180"]["stars"],
    }
    rub = {"14": "250", "30": "450", "90": "1150", "180": "1500"}
    prices = {
        days: f"{rub[days]} руб. или {stars[days]} звёзд"
        for days in rub
    }
    price = prices.get(days)
    if not price:
        await call.answer("Тариф не найден.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn("📲 СБП / Картой", f"pay_sbp:{days}", style=button_style("payment"))],
        [btn("₿ Crypto Бот", f"pay_crypto:{days}", style=button_style("payment"))],
        [btn("⭐ Звёзды Telegram", f"pay_stars:{days}", style=button_style("payment"))],
        [btn("« Назад", "subscription", style=button_style("back"))],
    ])

    await answer_callback_message(
        call,
        f"<b>Выбрано: Подписка Plus на {days} дней за {price}.</b>\n\n"
        "Выберите способ оплаты подписки:",
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await call.answer()

@dp.callback_query(F.data.startswith("pay_sbp:"))
async def pay_sbp(call: CallbackQuery):
    days = call.data.split(":", 1)[1]
    await call.answer(
        f"Оплата СБП / картой для тарифа на {days} дней пока не настроена.",
        show_alert=True,
    )

@dp.callback_query(F.data.startswith("pay_crypto:"))
async def pay_crypto_selected(call: CallbackQuery):
    days = call.data.split(":", 1)[1]
    plan_id = {
        "14": "plus_14",
        "30": "plus_30",
        "90": "plus_90",
        "180": "plus_180",
    }.get(days)

    if not plan_id or plan_id not in PLUS_PLANS:
        await call.answer("Тариф не найден.", show_alert=True)
        return

    if not CRYPTOBOT_TOKEN:
        await call.answer(
            "Crypto Pay не настроен: задайте CRYPTOBOT_TOKEN.",
            show_alert=True,
        )
        return

    try:
        invoice = await create_crypto_invoice(call.from_user.id, plan_id)
    except Exception as exc:
        log.exception("Не удалось создать Crypto Pay invoice")
        await call.answer(
            f"Не удалось создать счёт: {str(exc)[:180]}",
            show_alert=True,
        )
        return

    pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url")
    if not pay_url:
        await call.answer(
            "Crypto Pay не вернул ссылку на оплату.",
            show_alert=True,
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn(
            f"{e('payment')} Оплатить в Crypto Bot",
            url=pay_url,
            style=button_style("payment"),
        )],
        [btn(
            f"{e('back')} Назад",
            f"plus_plan:{days}",
            style=button_style("back"),
        )],
    ])

    await answer_callback_message(
        call,
        "💎 <b>Счёт Crypto Pay создан</b>\n\n"
        f"Тариф: <b>{PLUS_PLANS[plan_id]['title']}</b>\n"
        f"Сумма: <b>{invoice['amount']} {invoice['asset']}</b>\n\n"
        "После оплаты Plus активируется автоматически.",
        reply_markup=kb,
        parse_mode="HTML",
    )
    asyncio.create_task(
        watch_crypto_invoice(
            int(invoice["invoice_id"]),
            call.from_user.id,
            plan_id,
        )
    )
    await call.answer()

@dp.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars_selected(call: CallbackQuery):
    days = call.data.split(":", 1)[1]
    plan_id = {
        "14": "plus_14",
        "30": "plus_30",
        "90": "plus_90",
        "180": "plus_180",
    }.get(days)
    plan = PLUS_PLANS.get(plan_id or "")

    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return

    payload = f"plus:{plan_id}:{call.from_user.id}"
    kwargs = dict(
        chat_id=call.from_user.id,
        title=plan["title"],
        description=plan["description"],
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=plan["title"], amount=plan["stars"])],
    )

    try:
        await bot.send_invoice(**kwargs)
    except Exception:
        log.exception("Не удалось создать Telegram Stars invoice")
        await call.answer(
            "Не удалось открыть оплату Stars. Проверьте логи бота.",
            show_alert=True,
        )
        return

    await call.answer()

@dp.callback_query(F.data == "partner")
async def partner(call: CallbackQuery):
    await answer_callback_message(call, "💰 Партнёрская программа пока не подключена.")
    await call.answer()

@dp.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await subscription(call)

@dp.callback_query(F.data.startswith("buy_crypto:"))
async def buy_plus_crypto(call: CallbackQuery):
    plan_id = call.data.split(":", 1)[1]
    if plan_id != "plus_month":
        await call.answer("Тариф не найден.", show_alert=True)
        return
    if not CRYPTOBOT_TOKEN:
        await call.answer("Crypto Pay пока не настроен.", show_alert=True)
        return

    try:
        invoice = await create_crypto_invoice(call.from_user.id, plan_id)
    except Exception as e:
        log.exception("Не удалось создать Crypto Pay invoice")
        await call.answer("Не удалось создать счёт. Проверьте настройки Crypto Pay.", show_alert=True)
        return

    pay_url = invoice.get("pay_url")
    if not pay_url:
        await call.answer("Crypto Pay не вернул ссылку на оплату.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn(f"{e('payment')} Оплатить в Crypto Bot", url=pay_url)],
    ])
    await answer_callback_message(
        call,
        "💎 <b>Счёт Crypto Pay создан</b>\n\n"
        f"Сумма: <b>{invoice['amount']} {invoice['asset']}</b>\n"
        "После оплаты Plus активируется автоматически.",
        reply_markup=kb,
        parse_mode="HTML",
    )
    asyncio.create_task(
        watch_crypto_invoice(int(invoice["invoice_id"]), call.from_user.id, plan_id)
    )
    await call.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def buy_plus(call: CallbackQuery):
    plan_id = call.data.split(":", 1)[1]
    plan = PLUS_PLANS.get(plan_id)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return

    prices = [LabeledPrice(label=plan["title"], amount=plan["stars"])]
    kwargs = dict(
        chat_id=call.from_user.id,
        title=plan["title"],
        description=plan["description"],
        payload=f"plus:{plan_id}:{call.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=prices,
    )
    if plan.get("subscription_period"):
        kwargs["subscription_period"] = plan["subscription_period"]

    await bot.send_invoice(**kwargs)
    await call.answer()

@dp.pre_checkout_query()
async def process_pre_checkout_query(query: PreCheckoutQuery):
    payload = query.invoice_payload or ""
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "plus":
        await query.answer(
            ok=False,
            error_message="Неизвестный товар.",
        )
        return

    if parts[2] != str(query.from_user.id):
        await query.answer(
            ok=False,
            error_message="Заказ не принадлежит этому пользователю.",
        )
        return

    plan_id = parts[1]
    plan = PLUS_PLANS.get(plan_id)
    if (
        not plan
        or query.currency != "XTR"
        or query.total_amount != int(plan["stars"])
    ):
        await query.answer(
            ok=False,
            error_message="Параметры оплаты не совпадают.",
        )
        return

    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload or ""
    parts = payload.split(":")

    if len(parts) != 3 or parts[0] != "plus":
        return

    plan_id = parts[1]
    plan = PLUS_PLANS.get(plan_id)
    if not plan:
        return

    expiration = getattr(payment, "subscription_expiration_date", None)
    activated = await activate_plus(
        message.from_user.id,
        plan_id,
        payment.telegram_payment_charge_id,
        expires_at_override=expiration,
    )
    if not activated:
        return

    until = db.execute(
        "SELECT expires_at FROM subscriptions WHERE user_id=?",
        (message.from_user.id,),
    ).fetchone()[0]
    until_text = datetime.fromtimestamp(
        until, timezone.utc
    ).strftime("%d.%m.%Y %H:%M UTC")

    await message.answer(
        "✅ <b>Оплата получена!</b>\n\n"
        f"⭐ Тариф: <b>{plan['title']}</b>\n"
        f"📅 Действует до: <b>{until_text}</b>",
        parse_mode="HTML",
    )

@dp.message(F.text == "/paysupport")
async def paysupport(message: Message):
    await message.answer(
        "💳 <b>Поддержка по оплате</b>\n\n"
        "Если оплата прошла, но Plus не активировался, сохраните чек Telegram и обратитесь к владельцу бота.",
        parse_mode="HTML",
    )

# ============================================================
# БИЗНЕС-ОБРАБОТЧИКИ
# ============================================================

@dp.business_connection()
async def business_connection(update: BusinessConnection):
    log.info(
        "[CONNECTION] received id=%s user=%s chat=%s enabled=%s rights=%s",
        update.id, update.user.id, update.user_chat_id,
        getattr(update, "is_enabled", None), getattr(update, "rights", None)
    )
    conn = save_connection_from_api(update)
    cached_reply = bool(db.execute(
        "SELECT can_reply FROM connections WHERE connection_id=?",
        (update.id,)
    ).fetchone()[0])
    log.info(
        "[CONNECTION SAVED] id=%s enabled=%s can_reply=%s",
        update.id, bool(update.is_enabled), cached_reply
    )
    if getattr(update, "is_enabled", False):
        try:
            await bot.send_message(
                update.user_chat_id,
                "✅ <b>Secretary Mode подключён.</b>\n\n"
                "Сообщения Business-чата будут приходить боту.\n"
                "Права Business-подключения сохранены. Бот готов обрабатывать команды.",
                parse_mode="HTML",
                reply_markup=menu()
            )
        except Exception:
            log.exception("[CONNECTION] Failed to notify owner")

@dp.business_message()
async def business_message(message: Message):
    connection_id = message.business_connection_id
    log.info(
        "[BUSINESS MESSAGE] connection=%s chat=%s from=%s text=%r",
        connection_id, message.chat.id,
        getattr(message.from_user, "id", None), _short(message.text or message.caption)
    )
    if not connection_id:
        log.error("[BUSINESS MESSAGE] message has no business_connection_id")
        return

    conn = await ensure_connection(connection_id)
    if not conn:
        log.error("[BUSINESS MESSAGE] no connection data; message ignored")
        return
    if not conn[2]:
        log.warning(
            "[BUSINESS MESSAGE] connection reports disabled after refresh: %s",
            connection_id
        )

    if message.from_user and message.from_user.id != conn[0]:
        active_mute = get_active_mute(connection_id, message.chat.id, message.from_user.id)
        if active_mute:
            log.info("[MUTE] deleting message %s from user %s", message.message_id, message.from_user.id)
            await delete_business_message(message)
            return

    save_message(connection_id, message)

    # Авто-троллинг
    if (
        message.from_user
        and int(message.from_user.id) != int(conn[0])
        and (connection_id, message.chat.id) in A_TROLL_ENABLED
        and (message.text or "").strip()
    ):
        await send_troll_messages(message, a_troll_message, count=1)

    command_text = (message.text or "").strip()
    if command_text:
        log.info("[COMMAND CHECK] %r", command_text)
        user_id = message.from_user.id if message.from_user else None
        try:
            if command_text.startswith(".") and not is_command_owner(message, connection_id):
                log.info(
                    "[COMMAND BLOCKED] interlocutor=%s connection=%s command=%r",
                    user_id, connection_id, command_text,
                )
                return

            if user_id and user_id in nick_waiting and not command_text.startswith('.'):
                log.info("[COMMAND] nick input")
                await nick_add_input(message)
            elif user_id and user_id in timezone_waiting and not command_text.startswith('.'):
                log.info("[COMMAND] timezone city input")
                await timezone_city_input(message)
            elif re.match(r'^/start(?:\s+.*)?$', command_text, re.IGNORECASE):
                log.info("[COMMAND] /start")
                await start(message)
            elif command_text.lower() == '.help':
                log.info("[COMMAND] .help")
                await help_command(message)
            elif command_text.lower() == '.info':
                log.info("[COMMAND] .info")
                await info_command_old(message)
            elif command_text.lower() == '.ghoul':
                log.info("[COMMAND] .ghoul")
                await ghoul_command(message)
            elif command_text.lower() == '.streak':
                log.info("[COMMAND] .streak")
                await streak_command_old(message)
            elif command_text.lower() == '.cat':
                log.info("[COMMAND] .cat")
                await cat_command(message)
            elif command_text.lower() == '.save':
                log.info("[COMMAND] .save")
                await save_command(message)
            elif command_text.lower().startswith('.a_troll'):
                log.info("[COMMAND] .a_troll")
                await a_troll_command(message)
            elif command_text.lower() == '.troll':
                log.info("[COMMAND] .troll")
                await troll_command(message)
            elif command_text.lower() == '.ping':
                log.info("[COMMAND] .ping")
                await ping_command(message)
            elif re.match(r'^\.mute(?:\s+\d+)?$', command_text, re.IGNORECASE):
                log.info("[COMMAND] .mute")
                await mute_command(message)
            elif re.match(r'^\.unmute\s*$', command_text, re.IGNORECASE):
                log.info("[COMMAND] .unmute")
                await unmute_command(message)
            elif command_text.lower() == '.status':
                log.info("[COMMAND] .status")
                await status_command(message)
            elif command_text.lower() == '.coin':
                log.info("[COMMAND] .coin")
                await coin_command(message)
            elif command_text.lower() in {'.copy', '.publ', '.stories', '.streak_freeze', '.streak_recover', '.streak_restart', '.streak_top', '.streak_unfreeze', '.a_format', '.a_mute', '.act', '.fco', '.love', '.online', '.rps', '.ttt', '.typing', '.a_gpt', '.a_gpt_off', '.doxing', '.gpt', '.image'}:
                base = command_text.lower().split()[0]
                log.info("[COMMAND] %s", base)
                await simple_extra_command(message, base)
            elif command_text.lower().startswith('.send'):
                log.info("[COMMAND] .send")
                await send_command(message)
            elif command_text.lower() == '.nick':
                log.info("[COMMAND] .nick")
                await show_nick_menu(message, connection_id)
            elif command_text.lower() == '.diag':
                log.info("[COMMAND] .diag")
                await diag_command(message)
            elif re.match(r'^\.time\s+on(?:\s+(.+))?$', command_text, re.IGNORECASE):
                log.info("[COMMAND] .time on")
                await time_on_command(message)
            elif re.match(r'^\.time\s+off$', command_text, re.IGNORECASE):
                log.info("[COMMAND] .time off")
                await time_off_command(message)
            else:
                log.debug("[COMMAND] not recognized")
        except Exception:
            log.exception("[COMMAND ERROR] command=%r", command_text)
            try:
                await answer_message(
                    message,
                    "❌ <b>Ошибка команды.</b>\n\n"
                    "Смотрите консоль бота — там будет полный traceback.",
                    parse_mode="HTML"
                )
            except Exception:
                log.exception("[COMMAND ERROR] could not send error reply")

    enabled, tz_name = get_time_setting(conn[0])
    if enabled and message.from_user and message.from_user.id != conn[0]:
        activity_time = format_local_timestamp(message.date.timestamp(), tz_name)
        person = message.from_user.full_name or "Пользователь"
        log.info(
            "[TIME] %s last activity [%s] tz=%s; updating Business Last name",
            person, activity_time, tz_name
        )
        try:
            await set_business_last_name(connection_id, f"[{activity_time}]")
        except Exception:
            log.exception("[TIME] failed to update Business Last name")
        try:
            await bot.send_message(
                conn[1],
                f"🟢 <b>{person}</b> — последняя активность <code>[{activity_time}]</code>",
                parse_mode="HTML",
            )
        except Exception:
            log.exception("[TIME] failed to notify owner")

@dp.edited_business_message()
async def edited_business_message(message: Message):
    connection_id = message.business_connection_id
    if not connection_id:
        return

    conn = get_connection(connection_id)
    if not conn or not conn[2]:
        return

    old = get_saved(connection_id, message.chat.id, message.message_id)
    save_message(connection_id, message)

    if old and old[2] != message.text:
        link = chat_link(message.chat, message.message_id)
        notice = (
            f"{pe('edited')} <b>Изменено</b>\n"
            f"<s>{escape_html(_short(old[2] or old[3] or '[медиа]', 180))}</s> → "
            f"<b>{escape_html(_short(message.text or message.caption or '[медиа]', 180))}</b>"
        )
        await send_owner_notification(
            conn[1],
            notice,
            reply_markup=notification_keyboard(link, f"notice_close:edit:{message.message_id}"),
        )

@dp.deleted_business_messages()
async def deleted_business_messages(update: BusinessMessagesDeleted):
    conn = get_connection(update.business_connection_id)
    if not conn or not conn[2]:
        return

    for message_id in update.message_ids:
        saved = get_saved(
            update.business_connection_id,
            update.chat.id,
            message_id
        )

        if not saved:
            notice = (
                f"{pe('deleted')} <b>Удалено</b>\n"
                f"<code>#{message_id}</code> · автор не определён"
            )
            await send_owner_notification(
                conn[1],
                notice,
                reply_markup=notification_keyboard(
                    chat_link(update.chat, message_id),
                    f"notice_close:delete:{message_id}",
                ),
            )
            continue

        (
            sender_id,
            sender_name,
            sender_username,
            chat_title,
            chat_username,
            chat_type,
            kind,
            text,
            caption,
            file_id,
        ) = saved

        author = sender_name or sender_username or (
            f"ID {sender_id}" if sender_id else "неизвестен"
        )
        author_label = (
            f"{author} ({sender_username})"
            if sender_username and sender_username not in author
            else author
        )
        link = chat_link(update.chat, message_id)
        content = text or caption

        notice = (
            f"{pe('deleted')} <b>Удалено</b>\n"
            f"{escape_html(_short(author_label, 80))} · <code>#{message_id}</code>"
        )

        await send_owner_notification(
            conn[1],
            notice,
            reply_markup=notification_keyboard(
                link,
                f"notice_close:delete:{message_id}",
            ),
        )

        if kind == "video" and file_id:
            await bot.send_video(
                conn[1],
                file_id,
                caption=f"{pe('video')} <b>Сохранённое видео</b>",
                parse_mode="HTML"
            )
        elif kind == "photo" and file_id:
            await bot.send_photo(
                conn[1],
                file_id,
                caption=f"{pe('photo')} <b>Сохранённое фото</b>",
                parse_mode="HTML"
            )
        elif kind == "document" and file_id:
            await bot.send_document(
                conn[1],
                file_id,
                caption=f"{pe('file')} <b>Сохранённый файл</b>",
                parse_mode="HTML"
            )
        elif kind == "audio" and file_id:
            await bot.send_audio(
                conn[1],
                file_id,
                caption=f"{pe('audio')} <b>Сохранённое аудио</b>",
                parse_mode="HTML"
            )
        elif kind == "voice" and file_id:
            await bot.send_voice(
                conn[1],
                file_id,
                caption=f"{pe('voice')} <b>Сохранённое голосовое</b>",
                parse_mode="HTML"
            )
        elif content:
            await bot.send_message(
                conn[1],
                f"{pe('saved')} <b>Сохранённый текст</b>\n{escape_html(_short(content, 3500))}",
                parse_mode="HTML",
            )

        delete_saved(
            update.business_connection_id,
            update.chat.id,
            message_id
        )

@dp.callback_query(F.data.startswith("notice_close"))
async def notification_close_callback(callback: CallbackQuery):
    try:
        if callback.message:
            await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Закрыто")

# ============================================================
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК
# ============================================================

@dp.errors()
async def global_error_handler(event):
    log.error("[GLOBAL ERROR] %s", _short(getattr(event, "exception", event), 500))
    exc = getattr(event, "exception", None)
    if exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    return True

# ============================================================
# ТЕСТОВЫЙ СПАМ И ФЕЙК-ЧЕКИ (старые)
# ============================================================

TEST_SEND_AMOUNTS = (1, 5, 10, 50, 100)

def test_send_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("$1 TEST", "testsend:1"), btn("$5 TEST", "testsend:5")],
        [btn("$10 TEST", "testsend:10"), btn("$50 TEST", "testsend:50")],
        [btn("$100 TEST", "testsend:100")],
    ])

def test_receipt_keyboard(amount: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn(f"{e('upload')} Сформировать TEST-карточку", f"testsend_share:{amount}")]
    ])

def test_receipt_text(amount: int) -> str:
    return (
        "🧾 <b>TEST RECEIPT</b>\n\n"
        f"💵 Сумма: <b>${amount}.00</b>\n"
        "🧪 Статус: <b>ТЕСТ — НЕ ПЛАТЁЖ</b>\n\n"
        "Эта карточка не подтверждает перевод денег и не является платёжным документом."
    )

@dp.callback_query(F.data.startswith("testsend:"))
async def test_send_amount_callback(call: CallbackQuery):
    try:
        amount = int(call.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await call.answer("Некорректная сумма.", show_alert=True)
        return
    if amount not in TEST_SEND_AMOUNTS:
        await call.answer("Эта сумма недоступна.", show_alert=True)
        return
    await answer_callback_message(call, test_receipt_text(amount), reply_markup=test_receipt_keyboard(amount), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("testsend_share:"))
async def test_send_share_callback(call: CallbackQuery):
    try:
        amount = int(call.data.split(":", 1)[1])
    except (ValueError, AttributeError):
        await call.answer("Некорректная сумма.", show_alert=True)
        return
    if amount not in TEST_SEND_AMOUNTS:
        await call.answer("Эта сумма недоступна.", show_alert=True)
        return
    await answer_callback_message(call, test_receipt_text(amount), parse_mode="HTML")
    await call.answer("TEST-карточка сформирована.")

TEST_SPAM_TASKS = {}

def _test_spam_stop_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn(
            f"{e('stop')} Остановить рассылку",
            "testspam_stop"
        )]
    ])

async def _run_test_spam(message: Message, payload: str):
    import asyncio

    key = (
        getattr(message, "business_connection_id", None),
        message.chat.id,
        message.from_user.id,
    )

    old = TEST_SPAM_TASKS.get(key)
    if old and not old.done():
        await answer_message(message, "⏳ Рассылка уже запущена.", parse_mode="HTML")
        return

    payload = payload.strip()
    if not payload:
        await answer_message(
            message,
            "Использование: <code>.spam [текст]</code>\n"
            "Пример: <code>.spam привет</code>\n"
            "Остановить: <code>.spam stop</code>",
            parse_mode="HTML",
        )
        return

    async def worker():
        try:
            for i in range(10):
                await answer_message(message, payload)

                if i == 1:
                    await asyncio.sleep(1)
                    await answer_message(message, "test")

                if i < 9:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        finally:
            TEST_SPAM_TASKS.pop(key, None)

    task = asyncio.create_task(worker())
    TEST_SPAM_TASKS[key] = task

    await answer_message(
        message,
        "✅ <b>Рассылка успешно запущена</b>\n"
        "10 сообщений с интервалом 1 секунда.",
        reply_markup=_test_spam_stop_keyboard(),
        parse_mode="HTML",
    )

async def _stop_test_spam(message: Message):
    key = (
        getattr(message, "business_connection_id", None),
        message.chat.id,
        message.from_user.id,
    )
    task = TEST_SPAM_TASKS.get(key)

    if not task or task.done():
        await answer_message(message, "ℹ️ Рассылка уже завершена.")
        return

    task.cancel()
    TEST_SPAM_TASKS.pop(key, None)
    await answer_message(message, "🛑 <b>Рассылка остановлена</b>", parse_mode="HTML")

@dp.callback_query(F.data == "testspam_stop")
async def _testspam_stop_callback(call: CallbackQuery):
    if not call.message:
        await call.answer("Сообщение недоступно.", show_alert=True)
        return

    key = (
        getattr(call.message, "business_connection_id", None),
        call.message.chat.id,
        call.from_user.id,
    )
    task = TEST_SPAM_TASKS.get(key)

    if not task or task.done():
        await call.answer("Рассылка уже завершена.", show_alert=True)
        return

    task.cancel()
    TEST_SPAM_TASKS.pop(key, None)

    try:
        await answer_callback_message(call, "🛑 <b>Рассылка остановлена</b>", parse_mode="HTML")
    except Exception:
        await answer_message(call.message, "🛑 <b>Рассылка остановлена</b>", parse_mode="HTML")

    await call.answer("Рассылка остановлена.")# ============================================================
# НОВЫЕ / ОБНОВЛЁННЫЕ ФУНКЦИИ (вставить в конец файла)
# ============================================================

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

# Обновлённая info_command (заменяет старую)
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

# Обновлённый streak_command
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
# ВАЖНО: В вашем существующем бизнес-обработчике нужно добавить следующие проверки:
# - В блоке if command_text: добавить elif для .copy, .publ, .streak (заменить старый .streak)
# - После save_message добавить блок автоформатирования.
# Эти изменения уже описаны в инструкции выше. Если их нет, добавьте вручную.

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ main()
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
