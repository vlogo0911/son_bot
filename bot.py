"""
🎮 O'yinlar boti  —  Son topish · Tosh-Qaychi-Qog'oz · XO

Talab: python-telegram-bot >= 22   (pip install -r requirements.txt)
Ishga tushirish:  BOT_TOKEN muhit o'zgaruvchisini o'rnating va `python bot.py`
"""

import html
import json
import math
import asyncio
import logging
from datetime import date, datetime, timedelta
import os
import random
import sqlite3
import re
import hashlib
import hmac
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape

from telegram import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputFile,
    InputTextMessageContent,
    MenuButtonWebApp,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TelegramError, TimedOut
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    InlineQueryHandler,
    MessageHandler,
    PrefixHandler,
    filters,
)

# ───────────────────────────── Sozlamalar ─────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOLUME_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
DB_FILE = os.path.join(VOLUME_PATH, "game.db") if VOLUME_PATH else os.path.join(BASE_DIR, "game.db")

DEFAULT_LANG = "uz"
MONEY_LOG_CHAT_ID = -1004430776232

# Kasb almashtirish so'rovlarini qabul qiladigan ownerlar
CAREER_OWNER_IDS = {6913838682, 1150777456, 8358319733}
REREG_SEED_IDS = (8337510055,)   # birinchi ishga tushishda ruxsat ro'yxatiga qo'shiladi


def init_rereg():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS rereg_config (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS rereg_users (user_id INTEGER PRIMARY KEY)")
        if not c.execute("SELECT 1 FROM rereg_config WHERE key='seeded'").fetchone():
            c.executemany("INSERT OR IGNORE INTO rereg_users(user_id) VALUES (?)", [(u,) for u in REREG_SEED_IDS])
            c.execute("INSERT INTO rereg_config(key, value) VALUES ('seeded', 1)")


def init_bot_users():
    """users.started — botni shaxsiy chatda ishlatgan (start bosgan) odamlar belgisi."""
    with db() as c:
        if "started" not in {r[1] for r in c.execute("PRAGMA table_info(users)")}:
            c.execute("ALTER TABLE users ADD COLUMN started INTEGER NOT NULL DEFAULT 0")


def mark_started(user_id):
    with db() as c:
        c.execute("UPDATE users SET started=1 WHERE user_id=? AND started=0", (user_id,))


def bot_users_count(c):
    """Botdan haqiqatan foydalanganlar: start bosgan, o'yin o'ynagan, hamyon/jins/ro'yxatdan o'tgan.
    `users` jadvalida guruhlarda shunchaki ko'rilgan a'zolar ham bor (member_seen) — ular sanalmaydi."""
    return c.execute("""
        SELECT COUNT(*) FROM users u WHERE u.started=1 OR u.birth_confirmed=1
           OR EXISTS (SELECT 1 FROM chat_stats s WHERE s.user_id=u.user_id AND s.games>0)
           OR EXISTS (SELECT 1 FROM user_wallet w WHERE w.user_id=u.user_id)
           OR EXISTS (SELECT 1 FROM user_gender g WHERE g.user_id=u.user_id)
    """).fetchone()[0]


def seen_users_count(c):
    return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def rereg_all_on():
    row = db().execute("SELECT value FROM rereg_config WHERE key='all'").fetchone()
    return bool(row and row[0])


def rereg_allowed(uid):
    """Qayta ro'yxatdan o'tish: ommaviy yoqilgan bo'lsa hamma, aks holda faqat ro'yxatdagilar."""
    if rereg_all_on():
        return True
    return db().execute("SELECT 1 FROM rereg_users WHERE user_id=?", (int(uid),)).fetchone() is not None

MIN_NUMBER = 1
MAX_NUMBER = 100
FAST_ATTEMPTS = 7  # shuncha urinishgacha topsa — bonus

# Ballar
NUMBER_WIN_PTS = 10
NUMBER_BONUS_PTS = 5
RSP_WIN_PTS = 10
XO_WIN_PTS = 15
XO_DRAW_PTS = 5

# Faolsizlik vaqtlari (soniya)
NUMBER_TTL = 300
RSP_SETUP_TTL = 60
RSP_LOBBY_TTL = 120
RSP_CHOOSE_TTL = 60
XO_LOBBY_TTL = 120
XO_MOVE_TTL = 90

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("son_bot")

# ───────────────────────────── Tarjimalar ─────────────────────────────
# Barcha matnlar HTML formatida (<b>, <i>). Ismlar har doim escape() qilinadi.

LANGS = {
    # ───────────────────────── 🇺🇿 O'zbekcha ─────────────────────────
    "uz": {
        "flag_name": "🇺🇿 O‘zbekcha",
        "lang_title": "🌐 <b>Tilni tanlang</b>\n<i>Til shu chat uchun o‘rnatiladi.</i>",
        "lang_set": "✅ Til o‘rnatildi: 🇺🇿 <b>O‘zbekcha</b>",
        "lang_admin_only": "⛔ Tilni faqat guruh adminlari o‘zgartira oladi.",
        "use_group": "👥 Bu buyruqni guruh ichida ishlating.",
        "start_text": (
            "🎮 <b>O‘YINLAR BOTI</b> 🎮\n\n"
            "Salom! Men guruhingizni qiziqarli o‘yinlar bilan to‘ldiraman:\n\n"
            "🎯 Son topish\n"
            "✊ Tosh-Qaychi-Qog‘oz\n"
            "❌⭕ XO\n\n"
            "🏆 G‘alaba qozoning, ball to‘plang va reytingda birinchi bo‘ling!\n\n"
            "▶️ Boshlash: /emps"
        ),
        "menu_title": "🎮 <b>O‘YINLAR MARKAZI</b>\n\nQaysi o‘yinni o‘ynaymiz? 👇",
        "btn_number": "🎯 Son topish",
        "btn_rsp": "✊ Tosh-Qaychi-Qog‘oz",
        "btn_xo": "❌⭕ XO",
        "btn_join": "🙋 Qo‘shilish",
        "btn_again": "🎮 Yana o‘ynash",
        "btn_games": "🎮 O‘yinlar",
        "btn_add_group": "➕ Guruhga qo‘shish",
        "busy": "⚠️ Guruhda hozir o‘yin ketmoqda: <b>{game}</b>\n🛑 To‘xtatish: /stop",
        "busy_alert": "⚠️ Hozir o‘yin ketmoqda: {game}",
        "no_game": "🤷 Hozir faol o‘yin yo‘q.\n▶️ Boshlash: /emps",
        "stop_denied": "⛔ O‘yinni faqat uni boshlagan o‘yinchi yoki admin to‘xtata oladi.",
        "stopped": "🛑 O‘yin to‘xtatildi.",
        "timeout": "⌛ Vaqt tugadi — o‘yin bekor qilindi.",
        "gone": "🤷 Bu o‘yin allaqachon tugagan.",
        "only_owner": "☝️ Buni faqat o‘yinni boshlagan o‘yinchi tanlay oladi.",
        "not_player": "🚫 Siz bu o‘yinda ishtirok etmayapsiz.",
        # 🎯 Son topish
        "number_started": (
            "🎯 <b>SON TOPISH</b>\n\n"
            "🧠 Men <b>{min}</b> dan <b>{max}</b> gacha son o‘yladim.\n"
            "💬 Chatga son yozing — men yo‘l ko‘rsataman!\n\n"
            "🏆 G‘olib: +{points} ball\n"
            "⚡ {fast} urinishgacha topsangiz: +{bonus} bonus\n"
            "⏱ Faolsizlik vaqti: {minutes} daqiqa\n"
            "🛑 To‘xtatish: /stop"
        ),
        "higher": "📈 <b>Kattaroq!</b>",
        "lower": "📉 <b>Kichikroq!</b>",
        "heat_hot": "🔥 Juda yaqin!",
        "heat_warm": "♨️ Issiq",
        "heat_cool": "🌤 Iliq",
        "heat_cold": "🧊 Sovuq",
        "hint_tail": "📍 Oraliq: <b>{lo}–{hi}</b> · 🎲 Urinish: {n}",
        "number_dup": "♻️ <b>{number}</b> allaqachon aytilgan!",
        "number_win": (
            "🎉 <b>{name}</b> sonni topdi: <b>{number}</b>! 🎯\n"
            "🎲 Urinishlar soni: {attempts}\n"
            "🏆 +{points} ball{bonus}"
        ),
        "bonus": " ⚡ (tezkor bonus!)",
        "number_timeout": "⌛ Vaqt tugadi! Yashirin son: <b>{number}</b> edi.\n▶️ Yana o‘ynash: /emps",
        # ✊ RSP
        "rsp_setup": "✊✂️📄 <b>TOSH · QAYCHI · QOG‘OZ</b>\n\n👥 Nechta o‘yinchi o‘ynaydi?",
        "rsp_lobby": (
            "✊✂️📄 <b>TOSH · QAYCHI · QOG‘OZ</b>\n\n"
            "👥 O‘yinchilar: <b>{current}/{count}</b>\n\n"
            "{players}\n\n"
            "👇 Qo‘shilish uchun tugmani bosing!"
        ),
        "rsp_choose": (
            "✊✂️📄 <b>TOSH · QAYCHI · QOG‘OZ</b>\n\n"
            "{players}\n\n"
            "🤫 Tanlovingiz yashirin — hamma tanlagach ochiladi!\n"
            "⏳ Tanladi: <b>{current}/{count}</b>"
        ),
        "rsp_result": "🏁 <b>NATIJA</b>\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 <b>G‘olib: {names}</b>\n💰 Har biriga +{points} ball",
        "rsp_draw_same": "🤝 <b>Durang!</b> Hamma bir xil tanladi.",
        "rsp_draw_three": "🤝 <b>Durang!</b> Uchala variant ham chiqdi.",
        "rsp_already": "✋ Siz allaqachon qo‘shilgansiz.",
        "rsp_already_choice": "✋ Siz tanlovingizni allaqachon berdingiz.",
        "rsp_picked": "✅ Tanlov qabul qilindi: {choice}",
        "rsp_rock": "✊ Tosh",
        "rsp_scissors": "✂️ Qaychi",
        "rsp_paper": "📄 Qog‘oz",
        # ❌⭕ XO
        "xo_lobby": "❌⭕ <b>XO</b>\n\n🙋 <b>{owner}</b> raqib kutmoqda!\n👇 O‘yinga qo‘shiling.",
        "xo_board": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "👉 Navbat: {mark} <b>{turn}</b>\n"
            "⏱ Har bir yurish uchun {seconds} soniya"
        ),
        "xo_win": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🏆 <b>G‘olib: {mark} {winner}!</b>\n💰 +{points} ball"
        ),
        "xo_draw": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🤝 <b>Durang!</b>\n💰 Har biriga +{points} ball"
        ),
        "xo_own": "☝️ Siz o‘yin egasisiz — raqib kerak!",
        "xo_not_turn": "⏳ Hozir sizning navbatingiz emas!",
        "xo_taken": "🚫 Bu katak band!",
        # 🏆 Reyting va profil
        "rating_title": "🏆 <b>TOP 10 REYTING</b>\n━━━━━━━━━━━━━━",
        "rating_title_global": "🌍 <b>UMUMIY TOP 10</b>\n━━━━━━━━━━━━━━",
        "rating_empty": "📭 Hali reyting mavjud emas.\n▶️ O‘yin boshlang: /emps",
        "profile": (
            "👤 <b>{name}</b>\n━━━━━━━━━━━━━━\n"
            "🎂 Tug‘ilgan sana: <b>{birth_date}</b>\n"
            "🎈 Yosh: <b>{age}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "🎖 Daraja: {level}\n"
            "💰 Ball: <b>{points}</b>\n"
            "💵 Pul: <b>{money}</b>\n"
            "💼 Kasb: <b>{profession}</b>\n"
            "⭐ Kasb XP: <b>{career_xp}</b>\n"
            "🎮 O‘yinlar: {games}\n"
            "🏆 G‘alabalar: {wins}\n"
            "💔 Mag‘lubiyatlar: {losses}\n"
            "🤝 Duranglar: {draws}\n"
            "📊 G‘alaba foizi: <b>{winrate}%</b>\n"
            "{partner_info}\n{bar}{rank}"
        ),
        "profile_rank": "\n🏅 Guruhdagi o‘rin: <b>#{rank}</b>",
        "levels": ["🌱 Yangi", "🥉 Tajribali", "🥈 Usta", "🥇 Ekspert", "👑 Afsona"],
        "rules": (
            "📚 <b>QOIDALAR</b>\n\n"
            "🎯 <b>Son topish</b>\n"
            "Bot 1–100 oralig‘ida son o‘ylaydi. Chatga son yozing — bot «kattaroq» yoki «kichikroq» deb yo‘l ko‘rsatadi. "
            "Topgan o‘yinchi +10 ball oladi (7 urinishgacha +5 bonus).\n\n"
            "✊ <b>Tosh-Qaychi-Qog‘oz</b>\n"
            "2, 3 yoki 5 kishi o‘ynaydi. Tanlovlar yashirin, hamma tanlagach natija ochiladi. G‘oliblar +10 ball oladi.\n\n"
            "❌⭕ <b>XO</b>\n"
            "Ikki kishi navbatma-navbat yuradi. 3 ta belgini bir qatorga terish — g‘alaba (+15 ball), durang — +5 ball.\n\n"
            "⌛ Faol bo‘lmasa o‘yin avtomatik bekor bo‘ladi.\n"
            "📊 Ball va reyting har bir guruh uchun alohida hisoblanadi."
        ),
        "help": (
            "🤖 <b>BUYRUQLAR</b>\n\n"
            "🎮 /emps — o‘yin tanlash\n"
            "🛑 /stop — o‘yinni to‘xtatish\n"
            "🏆 /reyting — reyting\n"
            "👤 /profil — profilingiz\n"
            "📚 /qoidalar — qoidalar\n"
            "🌐 /lang — til tanlash"
        ),
    },
    # ───────────────────────── 🇬🇧 English ─────────────────────────
    "eng": {
        "flag_name": "🇬🇧 English",
        "lang_title": "🌐 <b>Choose a language</b>\n<i>It will be set for this chat.</i>",
        "lang_set": "✅ Language set: 🇬🇧 <b>English</b>",
        "lang_admin_only": "⛔ Only group admins can change the language.",
        "use_group": "👥 Use this command inside a group.",
        "start_text": (
            "🎮 <b>GAMES BOT</b> 🎮\n\n"
            "Hi! I'll fill your group with fun games:\n\n"
            "🎯 Guess the Number\n"
            "✊ Rock-Paper-Scissors\n"
            "❌⭕ Tic-Tac-Toe\n\n"
            "🏆 Win games, earn points and climb the leaderboard!\n\n"
            "▶️ Start: /emps"
        ),
        "menu_title": "🎮 <b>GAMES CENTER</b>\n\nWhat shall we play? 👇",
        "btn_number": "🎯 Guess the Number",
        "btn_rsp": "✊ Rock-Paper-Scissors",
        "btn_xo": "❌⭕ XO",
        "btn_join": "🙋 Join",
        "btn_again": "🎮 Play again",
        "btn_games": "🎮 Games",
        "btn_add_group": "➕ Add to a group",
        "busy": "⚠️ A game is already running in this group: <b>{game}</b>\n🛑 Stop it: /stop",
        "busy_alert": "⚠️ A game is already running: {game}",
        "no_game": "🤷 There is no active game.\n▶️ Start: /emps",
        "stop_denied": "⛔ Only the game starter or an admin can stop the game.",
        "stopped": "🛑 The game was stopped.",
        "timeout": "⌛ Time is up — the game was cancelled.",
        "gone": "🤷 This game has already ended.",
        "only_owner": "☝️ Only the player who started the game can choose this.",
        "not_player": "🚫 You are not part of this game.",
        "number_started": (
            "🎯 <b>GUESS THE NUMBER</b>\n\n"
            "🧠 I'm thinking of a number from <b>{min}</b> to <b>{max}</b>.\n"
            "💬 Type a number in the chat — I'll guide you!\n\n"
            "🏆 Winner: +{points} points\n"
            "⚡ Guess within {fast} tries: +{bonus} bonus\n"
            "⏱ Inactivity limit: {minutes} min\n"
            "🛑 Stop: /stop"
        ),
        "higher": "📈 <b>Higher!</b>",
        "lower": "📉 <b>Lower!</b>",
        "heat_hot": "🔥 Burning hot!",
        "heat_warm": "♨️ Warm",
        "heat_cool": "🌤 Mild",
        "heat_cold": "🧊 Cold",
        "hint_tail": "📍 Range: <b>{lo}–{hi}</b> · 🎲 Tries: {n}",
        "number_dup": "♻️ <b>{number}</b> has already been guessed!",
        "number_win": (
            "🎉 <b>{name}</b> guessed the number: <b>{number}</b>! 🎯\n"
            "🎲 Tries: {attempts}\n"
            "🏆 +{points} points{bonus}"
        ),
        "bonus": " ⚡ (speed bonus!)",
        "number_timeout": "⌛ Time is up! The number was <b>{number}</b>.\n▶️ Play again: /emps",
        "rsp_setup": "✊✂️📄 <b>ROCK · PAPER · SCISSORS</b>\n\n👥 How many players?",
        "rsp_lobby": (
            "✊✂️📄 <b>ROCK · PAPER · SCISSORS</b>\n\n"
            "👥 Players: <b>{current}/{count}</b>\n\n"
            "{players}\n\n"
            "👇 Press the button to join!"
        ),
        "rsp_choose": (
            "✊✂️📄 <b>ROCK · PAPER · SCISSORS</b>\n\n"
            "{players}\n\n"
            "🤫 Your pick is secret — revealed when everyone has chosen!\n"
            "⏳ Chosen: <b>{current}/{count}</b>"
        ),
        "rsp_result": "🏁 <b>RESULT</b>\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 <b>Winner: {names}</b>\n💰 +{points} points each",
        "rsp_draw_same": "🤝 <b>Draw!</b> Everyone chose the same.",
        "rsp_draw_three": "🤝 <b>Draw!</b> All three options appeared.",
        "rsp_already": "✋ You have already joined.",
        "rsp_already_choice": "✋ You have already made your choice.",
        "rsp_picked": "✅ Choice saved: {choice}",
        "rsp_rock": "✊ Rock",
        "rsp_scissors": "✂️ Scissors",
        "rsp_paper": "📄 Paper",
        "xo_lobby": "❌⭕ <b>XO</b>\n\n🙋 <b>{owner}</b> is waiting for an opponent!\n👇 Join the game.",
        "xo_board": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "👉 Turn: {mark} <b>{turn}</b>\n"
            "⏱ {seconds} seconds per move"
        ),
        "xo_win": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🏆 <b>Winner: {mark} {winner}!</b>\n💰 +{points} points"
        ),
        "xo_draw": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🤝 <b>Draw!</b>\n💰 +{points} points each"
        ),
        "xo_own": "☝️ You started this game — you need an opponent!",
        "xo_not_turn": "⏳ It's not your turn!",
        "xo_taken": "🚫 This cell is taken!",
        "rating_title": "🏆 <b>TOP 10 LEADERBOARD</b>\n━━━━━━━━━━━━━━",
        "rating_title_global": "🌍 <b>GLOBAL TOP 10</b>\n━━━━━━━━━━━━━━",
        "rating_empty": "📭 No leaderboard yet.\n▶️ Start a game: /emps",
        "profile": (
            "👤 <b>{name}</b>\n━━━━━━━━━━━━━━\n"
            "🎂 Date of birth: <b>{birth_date}</b>\n"
            "🎈 Age: <b>{age}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "🎖 Level: {level}\n"
            "💰 Points: <b>{points}</b>\n"
            "💵 Money: <b>{money}</b>\n"
            "💼 Profession: <b>{profession}</b>\n"
            "⭐ Career XP: <b>{career_xp}</b>\n"
            "🎮 Games: {games}\n"
            "🏆 Wins: {wins}\n"
            "💔 Losses: {losses}\n"
            "🤝 Draws: {draws}\n"
            "📊 Win rate: <b>{winrate}%</b>\n"
            "{partner_info}\n{bar}{rank}"
        ),
        "profile_rank": "\n🏅 Group rank: <b>#{rank}</b>",
        "levels": ["🌱 Newbie", "🥉 Skilled", "🥈 Pro", "🥇 Expert", "👑 Legend"],
        "rules": (
            "📚 <b>RULES</b>\n\n"
            "🎯 <b>Guess the Number</b>\n"
            "The bot picks a number from 1–100. Type numbers in the chat — the bot says «higher» or «lower». "
            "The winner gets +10 points (+5 bonus within 7 tries).\n\n"
            "✊ <b>Rock-Paper-Scissors</b>\n"
            "2, 3 or 5 players. Picks are secret and revealed once everyone has chosen. Winners get +10 points.\n\n"
            "❌⭕ <b>XO</b>\n"
            "Two players take turns. Three in a row wins (+15 points), a draw gives +5 points.\n\n"
            "⌛ Inactive games are cancelled automatically.\n"
            "📊 Points and leaderboards are tracked separately for each group."
        ),
        "help": (
            "🤖 <b>COMMANDS</b>\n\n"
            "🎮 /emps — choose a game\n"
            "🛑 /stop — stop the game\n"
            "🏆 /reyting — leaderboard\n"
            "👤 /profil — your profile\n"
            "📚 /qoidalar — rules\n"
            "🌐 /lang — choose language"
        ),
    },
    # ───────────────────────── 🇷🇺 Русский ─────────────────────────
    "ru": {
        "flag_name": "🇷🇺 Русский",
        "lang_title": "🌐 <b>Выберите язык</b>\n<i>Язык будет установлен для этого чата.</i>",
        "lang_set": "✅ Язык установлен: 🇷🇺 <b>Русский</b>",
        "lang_admin_only": "⛔ Менять язык могут только админы группы.",
        "use_group": "👥 Используйте эту команду в группе.",
        "start_text": (
            "🎮 <b>БОТ-ИГРЫ</b> 🎮\n\n"
            "Привет! Я наполню вашу группу интересными играми:\n\n"
            "🎯 Угадай число\n"
            "✊ Камень-Ножницы-Бумага\n"
            "❌⭕ Крестики-нолики\n\n"
            "🏆 Побеждайте, копите очки и поднимайтесь в рейтинге!\n\n"
            "▶️ Начать: /emps"
        ),
        "menu_title": "🎮 <b>ИГРОВОЙ ЦЕНТР</b>\n\nВо что сыграем? 👇",
        "btn_number": "🎯 Угадай число",
        "btn_rsp": "✊ Камень-Ножницы-Бумага",
        "btn_xo": "❌⭕ XO",
        "btn_join": "🙋 Присоединиться",
        "btn_again": "🎮 Сыграть ещё",
        "btn_games": "🎮 Игры",
        "btn_add_group": "➕ Добавить в группу",
        "busy": "⚠️ В группе уже идёт игра: <b>{game}</b>\n🛑 Остановить: /stop",
        "busy_alert": "⚠️ Сейчас уже идёт игра: {game}",
        "no_game": "🤷 Сейчас нет активной игры.\n▶️ Начать: /emps",
        "stop_denied": "⛔ Остановить игру может только её создатель или админ.",
        "stopped": "🛑 Игра остановлена.",
        "timeout": "⌛ Время вышло — игра отменена.",
        "gone": "🤷 Эта игра уже закончилась.",
        "only_owner": "☝️ Это может выбрать только тот, кто начал игру.",
        "not_player": "🚫 Вы не участвуете в этой игре.",
        "number_started": (
            "🎯 <b>УГАДАЙ ЧИСЛО</b>\n\n"
            "🧠 Я загадал число от <b>{min}</b> до <b>{max}</b>.\n"
            "💬 Пишите числа в чат — я буду подсказывать!\n\n"
            "🏆 Победитель: +{points} очков\n"
            "⚡ Угадаете за {fast} попыток: +{bonus} бонус\n"
            "⏱ Время бездействия: {minutes} мин\n"
            "🛑 Остановить: /stop"
        ),
        "higher": "📈 <b>Больше!</b>",
        "lower": "📉 <b>Меньше!</b>",
        "heat_hot": "🔥 Очень горячо!",
        "heat_warm": "♨️ Тепло",
        "heat_cool": "🌤 Прохладно",
        "heat_cold": "🧊 Холодно",
        "hint_tail": "📍 Диапазон: <b>{lo}–{hi}</b> · 🎲 Попыток: {n}",
        "number_dup": "♻️ <b>{number}</b> уже называли!",
        "number_win": (
            "🎉 <b>{name}</b> угадал число: <b>{number}</b>! 🎯\n"
            "🎲 Попыток: {attempts}\n"
            "🏆 +{points} очков{bonus}"
        ),
        "bonus": " ⚡ (бонус за скорость!)",
        "number_timeout": "⌛ Время вышло! Загаданное число: <b>{number}</b>.\n▶️ Сыграть ещё: /emps",
        "rsp_setup": "✊✂️📄 <b>КАМЕНЬ · НОЖНИЦЫ · БУМАГА</b>\n\n👥 Сколько игроков?",
        "rsp_lobby": (
            "✊✂️📄 <b>КАМЕНЬ · НОЖНИЦЫ · БУМАГА</b>\n\n"
            "👥 Игроки: <b>{current}/{count}</b>\n\n"
            "{players}\n\n"
            "👇 Нажмите кнопку, чтобы присоединиться!"
        ),
        "rsp_choose": (
            "✊✂️📄 <b>КАМЕНЬ · НОЖНИЦЫ · БУМАГА</b>\n\n"
            "{players}\n\n"
            "🤫 Выбор тайный — откроется, когда выберут все!\n"
            "⏳ Выбрали: <b>{current}/{count}</b>"
        ),
        "rsp_result": "🏁 <b>РЕЗУЛЬТАТ</b>\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 <b>Победитель: {names}</b>\n💰 Каждому +{points} очков",
        "rsp_draw_same": "🤝 <b>Ничья!</b> Все выбрали одинаково.",
        "rsp_draw_three": "🤝 <b>Ничья!</b> Выпали все три варианта.",
        "rsp_already": "✋ Вы уже присоединились.",
        "rsp_already_choice": "✋ Вы уже сделали выбор.",
        "rsp_picked": "✅ Выбор принят: {choice}",
        "rsp_rock": "✊ Камень",
        "rsp_scissors": "✂️ Ножницы",
        "rsp_paper": "📄 Бумага",
        "xo_lobby": "❌⭕ <b>XO</b>\n\n🙋 <b>{owner}</b> ждёт соперника!\n👇 Присоединяйтесь к игре.",
        "xo_board": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "👉 Ход: {mark} <b>{turn}</b>\n"
            "⏱ {seconds} секунд на ход"
        ),
        "xo_win": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🏆 <b>Победитель: {mark} {winner}!</b>\n💰 +{points} очков"
        ),
        "xo_draw": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🤝 <b>Ничья!</b>\n💰 Каждому +{points} очков"
        ),
        "xo_own": "☝️ Вы создали игру — нужен соперник!",
        "xo_not_turn": "⏳ Сейчас не ваш ход!",
        "xo_taken": "🚫 Эта клетка занята!",
        "rating_title": "🏆 <b>ТОП 10 РЕЙТИНГА</b>\n━━━━━━━━━━━━━━",
        "rating_title_global": "🌍 <b>ОБЩИЙ ТОП 10</b>\n━━━━━━━━━━━━━━",
        "rating_empty": "📭 Рейтинг пока пуст.\n▶️ Начните игру: /emps",
        "profile": (
            "👤 <b>{name}</b>\n━━━━━━━━━━━━━━\n"
            "🎂 Дата рождения: <b>{birth_date}</b>\n"
            "🎈 Возраст: <b>{age}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "🎖 Уровень: {level}\n"
            "💰 Очки: <b>{points}</b>\n"
            "💵 Деньги: <b>{money}</b>\n"
            "💼 Профессия: <b>{profession}</b>\n"
            "⭐ Карьерный XP: <b>{career_xp}</b>\n"
            "🎮 Игр: {games}\n"
            "🏆 Побед: {wins}\n"
            "💔 Поражений: {losses}\n"
            "🤝 Ничьих: {draws}\n"
            "📊 Процент побед: <b>{winrate}%</b>\n"
            "{partner_info}\n{bar}{rank}"
        ),
        "profile_rank": "\n🏅 Место в группе: <b>#{rank}</b>",
        "levels": ["🌱 Новичок", "🥉 Опытный", "🥈 Мастер", "🥇 Эксперт", "👑 Легенда"],
        "rules": (
            "📚 <b>ПРАВИЛА</b>\n\n"
            "🎯 <b>Угадай число</b>\n"
            "Бот загадывает число от 1 до 100. Пишите числа в чат — бот подсказывает «больше» или «меньше». "
            "Угадавший получает +10 очков (+5 бонус за 7 попыток).\n\n"
            "✊ <b>Камень-Ножницы-Бумага</b>\n"
            "Играют 2, 3 или 5 человек. Выбор тайный, результат — после выбора всех. Победители получают +10 очков.\n\n"
            "❌⭕ <b>XO</b>\n"
            "Двое ходят по очереди. Три в ряд — победа (+15 очков), ничья — +5 очков.\n\n"
            "⌛ Неактивные игры отменяются автоматически.\n"
            "📊 Очки и рейтинг ведутся отдельно для каждой группы."
        ),
        "help": (
            "🤖 <b>КОМАНДЫ</b>\n\n"
            "🎮 /emps — выбрать игру\n"
            "🛑 /stop — остановить игру\n"
            "🏆 /reyting — рейтинг\n"
            "👤 /profil — ваш профиль\n"
            "📚 /qoidalar — правила\n"
            "🌐 /lang — выбрать язык"
        ),
    },
    # ───────────────────────── 🇰🇿 Қазақша ─────────────────────────
    "kz": {
        "flag_name": "🇰🇿 Қазақша",
        "lang_title": "🌐 <b>Тілді таңдаңыз</b>\n<i>Тіл осы чат үшін орнатылады.</i>",
        "lang_set": "✅ Тіл орнатылды: 🇰🇿 <b>Қазақша</b>",
        "lang_admin_only": "⛔ Тілді тек топ админдері өзгерте алады.",
        "use_group": "👥 Бұл команданы топ ішінде қолданыңыз.",
        "start_text": (
            "🎮 <b>ОЙЫНДАР БОТЫ</b> 🎮\n\n"
            "Сәлем! Мен тобыңызды қызықты ойындармен толтырамын:\n\n"
            "🎯 Сан тап\n"
            "✊ Тас-Қайшы-Қағаз\n"
            "❌⭕ XO\n\n"
            "🏆 Жеңіңіз, ұпай жинаңыз және рейтингте бірінші болыңыз!\n\n"
            "▶️ Бастау: /emps"
        ),
        "menu_title": "🎮 <b>ОЙЫН ОРТАЛЫҒЫ</b>\n\nНе ойнаймыз? 👇",
        "btn_number": "🎯 Сан тап",
        "btn_rsp": "✊ Тас-Қайшы-Қағаз",
        "btn_xo": "❌⭕ XO",
        "btn_join": "🙋 Қосылу",
        "btn_again": "🎮 Тағы ойнау",
        "btn_games": "🎮 Ойындар",
        "btn_add_group": "➕ Топқа қосу",
        "busy": "⚠️ Топта ойын жүріп жатыр: <b>{game}</b>\n🛑 Тоқтату: /stop",
        "busy_alert": "⚠️ Қазір ойын жүріп жатыр: {game}",
        "no_game": "🤷 Қазір белсенді ойын жоқ.\n▶️ Бастау: /emps",
        "stop_denied": "⛔ Ойынды тек оны бастаған ойыншы немесе админ тоқтата алады.",
        "stopped": "🛑 Ойын тоқтатылды.",
        "timeout": "⌛ Уақыт бітті — ойын тоқтатылды.",
        "gone": "🤷 Бұл ойын әлдеқашан аяқталған.",
        "only_owner": "☝️ Мұны тек ойынды бастаған ойыншы таңдай алады.",
        "not_player": "🚫 Сіз бұл ойынға қатыспайсыз.",
        "number_started": (
            "🎯 <b>САН ТАП</b>\n\n"
            "🧠 Мен <b>{min}</b> мен <b>{max}</b> арасынан сан ойладым.\n"
            "💬 Чатқа сан жазыңыз — мен жол көрсетемін!\n\n"
            "🏆 Жеңімпаз: +{points} ұпай\n"
            "⚡ {fast} әрекетке дейін тапсаңыз: +{bonus} бонус\n"
            "⏱ Белсенділіксіз уақыт: {minutes} минут\n"
            "🛑 Тоқтату: /stop"
        ),
        "higher": "📈 <b>Үлкенірек!</b>",
        "lower": "📉 <b>Кішірек!</b>",
        "heat_hot": "🔥 Өте жақын!",
        "heat_warm": "♨️ Ыстық",
        "heat_cool": "🌤 Жылы",
        "heat_cold": "🧊 Суық",
        "hint_tail": "📍 Аралық: <b>{lo}–{hi}</b> · 🎲 Әрекет: {n}",
        "number_dup": "♻️ <b>{number}</b> саны айтылып қойған!",
        "number_win": (
            "🎉 <b>{name}</b> санды тапты: <b>{number}</b>! 🎯\n"
            "🎲 Әрекет саны: {attempts}\n"
            "🏆 +{points} ұпай{bonus}"
        ),
        "bonus": " ⚡ (жылдамдық бонусы!)",
        "number_timeout": "⌛ Уақыт бітті! Жасырылған сан: <b>{number}</b> еді.\n▶️ Тағы ойнау: /emps",
        "rsp_setup": "✊✂️📄 <b>ТАС · ҚАЙШЫ · ҚАҒАЗ</b>\n\n👥 Қанша ойыншы ойнайды?",
        "rsp_lobby": (
            "✊✂️📄 <b>ТАС · ҚАЙШЫ · ҚАҒАЗ</b>\n\n"
            "👥 Ойыншылар: <b>{current}/{count}</b>\n\n"
            "{players}\n\n"
            "👇 Қосылу үшін батырманы басыңыз!"
        ),
        "rsp_choose": (
            "✊✂️📄 <b>ТАС · ҚАЙШЫ · ҚАҒАЗ</b>\n\n"
            "{players}\n\n"
            "🤫 Таңдау жасырын — бәрі таңдағанда ашылады!\n"
            "⏳ Таңдады: <b>{current}/{count}</b>"
        ),
        "rsp_result": "🏁 <b>НӘТИЖЕ</b>\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 <b>Жеңімпаз: {names}</b>\n💰 Әрқайсысына +{points} ұпай",
        "rsp_draw_same": "🤝 <b>Тең ойын!</b> Бәрі бірдей таңдады.",
        "rsp_draw_three": "🤝 <b>Тең ойын!</b> Үш нұсқа да шықты.",
        "rsp_already": "✋ Сіз әлдеқашан қосылдыңыз.",
        "rsp_already_choice": "✋ Сіз таңдауыңызды жасап қойдыңыз.",
        "rsp_picked": "✅ Таңдау қабылданды: {choice}",
        "rsp_rock": "✊ Тас",
        "rsp_scissors": "✂️ Қайшы",
        "rsp_paper": "📄 Қағаз",
        "xo_lobby": "❌⭕ <b>XO</b>\n\n🙋 <b>{owner}</b> қарсылас күтіп тұр!\n👇 Ойынға қосылыңыз.",
        "xo_board": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "👉 Кезек: {mark} <b>{turn}</b>\n"
            "⏱ Әр жүріске {seconds} секунд"
        ),
        "xo_win": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🏆 <b>Жеңімпаз: {mark} {winner}!</b>\n💰 +{points} ұпай"
        ),
        "xo_draw": (
            "❌⭕ <b>XO</b>\n\n"
            "❌ <b>{x}</b>  🆚  ⭕ <b>{o}</b>\n\n"
            "🤝 <b>Тең ойын!</b>\n💰 Әрқайсысына +{points} ұпай"
        ),
        "xo_own": "☝️ Сіз ойынды бастадыңыз — қарсылас керек!",
        "xo_not_turn": "⏳ Қазір сіздің кезегіңіз емес!",
        "xo_taken": "🚫 Бұл тор бос емес!",
        "rating_title": "🏆 <b>ТОП 10 РЕЙТИНГ</b>\n━━━━━━━━━━━━━━",
        "rating_title_global": "🌍 <b>ЖАЛПЫ ТОП 10</b>\n━━━━━━━━━━━━━━",
        "rating_empty": "📭 Рейтинг әлі жоқ.\n▶️ Ойын бастаңыз: /emps",
        "profile": (
            "👤 <b>{name}</b>\n━━━━━━━━━━━━━━\n"
            "🎂 Туған күні: <b>{birth_date}</b>\n"
            "🎈 Жасы: <b>{age}</b>\n"
            "━━━━━━━━━━━━━━\n"
            "🎖 Деңгей: {level}\n"
            "💰 Ұпай: <b>{points}</b>\n"
            "💵 Ақша: <b>{money}</b>\n"
            "💼 Мамандық: <b>{profession}</b>\n"
            "⭐ Мансап XP: <b>{career_xp}</b>\n"
            "🎮 Ойындар: {games}\n"
            "🏆 Жеңістер: {wins}\n"
            "💔 Жеңілістер: {losses}\n"
            "🤝 Тең ойындар: {draws}\n"
            "📊 Жеңіс пайызы: <b>{winrate}%</b>\n"
            "{partner_info}\n{bar}{rank}"
        ),
        "profile_rank": "\n🏅 Топтағы орын: <b>#{rank}</b>",
        "levels": ["🌱 Жаңадан", "🥉 Тәжірибелі", "🥈 Шебер", "🥇 Сарапшы", "👑 Аңыз"],
        "rules": (
            "📚 <b>ЕРЕЖЕЛЕР</b>\n\n"
            "🎯 <b>Сан тап</b>\n"
            "Бот 1–100 арасынан сан ойлайды. Чатқа сан жазыңыз — бот «үлкенірек» немесе «кішірек» деп көрсетеді. "
            "Тапқан ойыншы +10 ұпай алады (7 әрекетке дейін +5 бонус).\n\n"
            "✊ <b>Тас-Қайшы-Қағаз</b>\n"
            "2, 3 немесе 5 адам ойнайды. Таңдау жасырын, бәрі таңдағанда нәтиже ашылады. Жеңімпаздар +10 ұпай алады.\n\n"
            "❌⭕ <b>XO</b>\n"
            "Екі адам кезекпен жүреді. Үш белгіні бір қатарға қою — жеңіс (+15 ұпай), тең ойын — +5 ұпай.\n\n"
            "⌛ Белсенді болмаса, ойын өздігінен тоқтатылады.\n"
            "📊 Ұпай мен рейтинг әр топ үшін бөлек есептеледі."
        ),
        "help": (
            "🤖 <b>БҰЙРЫҚТАР</b>\n\n"
            "🎮 /emps — ойын таңдау\n"
            "🛑 /stop — ойынды тоқтату\n"
            "🏆 /reyting — рейтинг\n"
            "👤 /profil — профиль\n"
            "📚 /qoidalar — ережелер\n"
            "🌐 /lang — тіл таңдау"
        ),
    },
}

LANG_ORDER = ["uz", "eng", "ru", "kz"]
# Kalit: chat_id (int) yoki inline xabardagi o'yin uchun "i:<inline_message_id>" (str).
LANG_CACHE: dict[int | str, str] = {}


def t(chat_id, key, **kwargs):
    """Chatning tilida matn qaytaradi (topilmasa — o'zbekcha)."""
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    text = LANGS[lang].get(key)
    if text is None:
        text = LANGS[DEFAULT_LANG].get(key, key)
    return text.format(**kwargs) if kwargs else text


def level_name(chat_id, points):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    idx = 0
    for i, threshold in enumerate((0, 50, 150, 400, 1000)):
        if points >= threshold:
            idx = i
    return LANGS[lang]["levels"][idx]


# ───────────────────────────── Ma'lumotlar bazasi ─────────────────────────────

_conn = None
_SEEN: dict[int, tuple] = {}
OUTCOME_COL = {"win": "wins", "loss": "losses", "draw": "draws"}


class _SharedConnection(sqlite3.Connection):
    """Butun bot bitta ulanishdan foydalanadi; c.close() uni yopib qo'ymasligi kerak."""

    def close(self):  # noqa: D401
        # Oddiy close() chaqiruvlari e'tiborga olinmaydi (ulanish umumiy).
        pass

    def real_close(self):
        super().close()


def db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_FILE, factory=_SharedConnection)
    return _conn


def init_db():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS crash_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS crash_groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT ''
        );
    """)
    c.executemany(
        "INSERT OR IGNORE INTO crash_config (key, value) VALUES (?, ?)",
        [("enabled", "1"), ("min_bet", "50"), ("tick", "1.0"), ("group_restrict", "0")],
    )
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_panel_admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_panel_admin_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, permission)
        )
    """)
    with c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                points INTEGER DEFAULT 0,
                games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS group_languages (
                chat_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'uz'
            )
        """)
        # Har bir guruh uchun alohida statistika
        c.execute("""
            CREATE TABLE IF NOT EXISTS chat_stats (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                points INTEGER NOT NULL DEFAULT 0,
                games INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                draws INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_stats_rank "
            "ON chat_stats(chat_id, points DESC, wins DESC)"
        )

        c.execute("""
            CREATE TABLE IF NOT EXISTS secret_messages (
                token TEXT PRIMARY KEY,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                recipient_username TEXT NOT NULL,
                message_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS career_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                requested_profession_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                decided_by INTEGER,
                decided_at TEXT
            )
        """)
    # Kasb tizimi sxemasi: yangi (bo'sh) bazada ham ishlashi uchun. Mavjud bazaga tegmaydi.
    ensure_career_schema(c)
    migrate_legacy(c)

    for chat_id, language in c.execute("SELECT chat_id, language FROM group_languages"):
        if language in LANGS:
            LANG_CACHE[chat_id] = language

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_gender (
            user_id INTEGER PRIMARY KEY,
            gender TEXT NOT NULL CHECK(gender IN ('male', 'female')),
            updated_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        )
    """)
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pairs_active_user1
        ON pairs(user1_id) WHERE status = 'active'
    """)
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pairs_active_user2
        ON pairs(user2_id) WHERE status = 'active'
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pair_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT NOT NULL,
            requester_id INTEGER NOT NULL,
            target_id INTEGER,
            group_id INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            decided_by INTEGER,
            decided_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_notice_state (
            notice_key TEXT PRIMARY KEY,
            completed_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_wallet (
            user_id INTEGER PRIMARY KEY,
            money INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS child_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            partner_id INTEGER NOT NULL,
            pair_id INTEGER NOT NULL,
            gender TEXT,
            child_name TEXT,
            status TEXT NOT NULL DEFAULT 'selecting',
            created_at TEXT NOT NULL,
            due_at TEXT,
            delivered_at TEXT
        )
    """)
    # Migrate older databases safely: CREATE TABLE does not add columns to existing tables.
    child_cols = {row[1] for row in c.execute("PRAGMA table_info(child_requests)").fetchall()}
    if "due_at" not in child_cols:
        c.execute("ALTER TABLE child_requests ADD COLUMN due_at TEXT")
    if "delivered_at" not in child_cols:
        c.execute("ALTER TABLE child_requests ADD COLUMN delivered_at TEXT")

    c.execute("""
        CREATE TABLE IF NOT EXISTS family_children (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            parent1_id INTEGER NOT NULL,
            parent2_id INTEGER NOT NULL,
            gender TEXT NOT NULL,
            child_name TEXT NOT NULL,
            born_at TEXT NOT NULL,
            request_id INTEGER UNIQUE
        )
    """)

def ensure_career_schema(c):
    """users kasb ustunlari va missiya/XP jadvallarini yaratadi (mavjud bo'lsa — o'zgartirmaydi)."""
    with c:
        user_cols = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        for col, ddl in (
            ("birth_date", "TEXT"),
            ("birth_confirmed", "INTEGER NOT NULL DEFAULT 0"),
            ("profession_id", "INTEGER"),
            ("profession_selected", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if col not in user_cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_career (
                user_id INTEGER PRIMARY KEY,
                career_xp INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profession_id INTEGER NOT NULL,
                mission_key TEXT NOT NULL,
                target INTEGER NOT NULL,
                reward_xp INTEGER NOT NULL DEFAULT 0,
                reward_money INTEGER NOT NULL DEFAULT 0,
                active_date TEXT NOT NULL,
                title_uz TEXT, title_eng TEXT, title_ru TEXT, title_kz TEXT,
                description_uz TEXT, description_eng TEXT,
                description_ru TEXT, description_kz TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS mission_progress (
                user_id INTEGER NOT NULL,
                mission_id INTEGER NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, mission_id)
            )
        """)


def migrate_legacy(c):
    """Eski global ballarni (agar bitta guruh bo'lsa) o'sha guruhga ko'chiradi."""
    if c.execute("PRAGMA user_version").fetchone()[0] >= 1:
        return

    chats = [r[0] for r in c.execute("SELECT chat_id FROM group_languages WHERE chat_id < 0")]
    has_stats = c.execute("SELECT 1 FROM chat_stats LIMIT 1").fetchone()

    if len(chats) == 1 and not has_stats:
        with c:
            c.execute(
                """
                INSERT INTO chat_stats(chat_id, user_id, points, games, wins, losses)
                SELECT ?, user_id, points, games, wins, MAX(games - wins, 0)
                FROM users WHERE games > 0 OR points > 0
                """,
                (chats[0],),
            )
        logger.info("Eski statistika %s guruhiga ko'chirildi", chats[0])
    else:
        logger.info("Eski statistikani ko'chirib bo'lmadi (guruhlar soni: %d)", len(chats))

    c.execute("PRAGMA user_version = 1")
    c.commit()


def set_group_lang(chat_id, language):
    if language not in LANGS:
        language = DEFAULT_LANG
    c = db()
    with c:
        c.execute(
            """
            INSERT INTO group_languages(chat_id, language) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET language = excluded.language
            """,
            (chat_id, language),
        )
    LANG_CACHE[chat_id] = language


def save_user(user):
    # Har safar DB bilan sinxronlaymiz: _SEEN yozuvi bazada foydalanuvchi
    # borligini kafolatlamaydi (masalan, DB yangilanganda yoki yozuv o‘chirilganda).
    key = (user.username, user.first_name)
    c = db()
    with c:
        c.execute(
            """
            INSERT INTO users(user_id, username, first_name) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (user.id, user.username, user.first_name),
        )
    _SEEN[user.id] = key


def record(chat_id, user_id, outcome, points=0):
    """O'yin natijasi + kasb missiyalari progressi va mukofotlari."""
    if is_inline_key(chat_id):
        chat_id = INLINE_STATS_CHAT
    col = OUTCOME_COL[outcome]
    c = db()

    with c:
        # 🎮 O'yin statistikasi
        c.execute(
            f"""
            INSERT INTO chat_stats(chat_id, user_id, points, games, {col})
            VALUES (?, ?, ?, 1, 1)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                points = points + excluded.points,
                games = games + 1,
                {col} = {col} + 1
            """,
            (chat_id, user_id, points),
        )

        # 🎯 Kasb missiyalari
        from datetime import date
        today = date.today().isoformat()

        user_row = c.execute(
            "SELECT profession_id FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if not user_row or not user_row[0]:
            return

        profession_id = user_row[0]

        missions = c.execute(
            """
            SELECT id, mission_key, target, reward_xp, reward_money
            FROM daily_missions
            WHERE profession_id=? AND active_date=?
            """,
            (profession_id, today)
        ).fetchall()

        for mission_id, mission_key, target, reward_xp, reward_money in missions:
            progress_row = c.execute(
                """
                SELECT progress, completed
                FROM mission_progress
                WHERE user_id=? AND mission_id=?
                """,
                (user_id, mission_id)
            ).fetchone()

            # Allaqachon mukofotlangan
            if progress_row and progress_row[1]:
                continue

            current = progress_row[0] if progress_row else 0

            if mission_key == "play":
                current += 1
            elif mission_key == "win" and outcome == "win":
                current += 1
            elif mission_key == "points":
                current += max(0, points)

            current = min(current, target)
            completed = int(current >= target)

            c.execute(
                """
                INSERT INTO mission_progress
                    (user_id, mission_id, progress, completed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, mission_id) DO UPDATE SET
                    progress=excluded.progress,
                    completed=excluded.completed
                """,
                (user_id, mission_id, current, completed)
            )

            # 🎁 Faqat shu o'yinda birinchi marta tugagan bo'lsa mukofot beramiz
            if completed:
                c.execute(
                    """
                    INSERT OR IGNORE INTO user_career(user_id, career_xp)
                    VALUES (?, 0)
                    """,
                    (user_id,)
                )

                c.execute(
                    """
                    UPDATE user_career
                    SET career_xp = career_xp + ?
                    WHERE user_id=?
                    """,
                    (reward_xp, user_id)
                )

                c.execute(
                    """
                    INSERT OR IGNORE INTO user_wallet(user_id, money)
                    VALUES (?, 0)
                    """,
                    (user_id,)
                )

                # Kasb mukofoti barcha foydalanuvchilarning balansiga qo'shiladi
                c.execute(
                    """
                    UPDATE user_wallet
                    SET money = money + ?
                    WHERE user_id=?
                    """,
                    (reward_money, user_id)
                    )

def get_stats(chat_id, user_id, private):
    c = db()
    if private:
        row = c.execute(
            """
            SELECT COALESCE(SUM(points),0), COALESCE(SUM(games),0), COALESCE(SUM(wins),0),
                   COALESCE(SUM(losses),0), COALESCE(SUM(draws),0)
            FROM chat_stats WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    else:
        row = c.execute(
            "SELECT points, games, wins, losses, draws FROM chat_stats WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ).fetchone()
    return row or (0, 0, 0, 0, 0)



def ensure_daily_missions():
    """Har kun uchun 16 kasbga 3 tadan yangi missiya yaratadi."""
    from datetime import date
    import random

    today = date.today().isoformat()
    c = db()

    # Har bir kasb uchun missiyalar havzasi
    templates = {
        "play": [
            (2, 20, 70),
            (3, 30, 100),
            (4, 40, 130),
            (5, 50, 160),
        ],
        "win": [
            (1, 40, 120),
            (2, 60, 180),
            (3, 90, 260),
        ],
        "points": [
            (30, 40, 100),
            (50, 60, 160),
            (70, 80, 220),
            (100, 120, 350),
        ],
    }

    texts = {
        "play": {
            "uz": "🎮 {target} ta o‘yin o‘yna",
            "eng": "🎮 Play {target} games",
            "ru": "🎮 Сыграй {target} игр",
            "kz": "🎮 {target} ойын ойна",
        },
        "win": {
            "uz": "🏆 {target} ta g‘alaba qozon",
            "eng": "🏆 Win {target} games",
            "ru": "🏆 Выиграй {target} игр",
            "kz": "🏆 {target} ойында жең",
        },
        "points": {
            "uz": "💰 {target} ball to‘pla",
            "eng": "💰 Earn {target} points",
            "ru": "💰 Набери {target} очков",
            "kz": "💰 {target} ұпай жина",
        },
    }

    for profession_id in range(1, 17):
        exists = c.execute(
            "SELECT COUNT(*) FROM daily_missions "
            "WHERE profession_id=? AND active_date=?",
            (profession_id, today),
        ).fetchone()[0]

        if exists >= 3:
            continue

        chosen = []
        for key in ("play", "win", "points"):
            target, xp, money = random.choice(templates[key])
            chosen.append((key, target, xp, money))

        for key, target, xp, money in chosen:
            title_uz = texts[key]["uz"].format(target=target)
            title_eng = texts[key]["eng"].format(target=target)
            title_ru = texts[key]["ru"].format(target=target)
            title_kz = texts[key]["kz"].format(target=target)

            c.execute(
                """
                INSERT INTO daily_missions
                (profession_id, mission_key, target, reward_xp, active_date,
                 title_uz, title_eng, title_ru, title_kz,
                 description_uz, description_eng, description_ru, description_kz,
                 reward_money)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profession_id, key, target, xp, today,
                    title_uz, title_eng, title_ru, title_kz,
                    title_uz, title_eng, title_ru, title_kz,
                    money,
                ),
            )

    c.commit()

def get_rank(chat_id, points, wins):
    row = db().execute(
        """
        SELECT COUNT(*) + 1 FROM chat_stats
        WHERE chat_id = ? AND (points > ? OR (points = ? AND wins > ?))
        """,
        (chat_id, points, points, wins),
    ).fetchone()
    return row[0]


def top_players(chat_id, private):
    c = db()
    if private:
        return c.execute(
            """
            SELECT u.first_name, u.username, SUM(s.points) AS p, SUM(s.wins) AS w
            FROM chat_stats s LEFT JOIN users u ON u.user_id = s.user_id
            GROUP BY s.user_id HAVING SUM(s.games) > 0
            ORDER BY p DESC, w DESC LIMIT 10
            """
        ).fetchall()
    return c.execute(
        """
        SELECT u.first_name, u.username, s.points, s.wins
        FROM chat_stats s LEFT JOIN users u ON u.user_id = s.user_id
        WHERE s.chat_id = ? AND s.games > 0
        ORDER BY s.points DESC, s.wins DESC LIMIT 10
        """,
        (chat_id,),
    ).fetchall()


# ───────────────────────────── Yordamchi funksiyalar ─────────────────────────────


def pretty_name(first_name, username):
    name = (first_name or "").strip() or (f"@{username}" if username else "User")
    return escape(name[:24])


def uname(user):
    return pretty_name(user.first_name, user.username)


def bar(percent, size=10):
    filled = round(percent / 100 * size)
    return "▰" * filled + "▱" * (size - filled)


async def is_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        return False
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


# ───────────────────────────── Inline xabardagi o'yinlar ─────────────────────────────
# Shaxsiy yozishmada @bot orqali yuborilgan o'yin xabarida chat_id bo'lmaydi —
# Telegram faqat inline_message_id beradi. Shunday o'yinlar GAMES ichida
# "i:<inline_message_id>" kaliti bilan saqlanadi va shu kalit chat_id o'rnida ishlatiladi.

INLINE_PREFIX = "i:"
INLINE_STATS_CHAT = 0   # inline o'yinlar statistikasi (umumiy reytingga qo'shiladi)
_INLINE_LANG_KEYS: list[str] = []


def is_inline_key(chat_id):
    return isinstance(chat_id, str) and chat_id.startswith(INLINE_PREFIX)


def game_key(q):
    """Callback tegishli bo'lgan o'yin kaliti: oddiy chat yoki inline xabar."""
    if q.inline_message_id:
        return INLINE_PREFIX + q.inline_message_id
    return q.message.chat.id


def msg_target(chat_id, message_id):
    """edit_message_* uchun manzil argumentlari."""
    if is_inline_key(chat_id):
        return {"inline_message_id": chat_id[len(INLINE_PREFIX):]}
    return {"chat_id": chat_id, "message_id": message_id}


def set_inline_lang(key, lang):
    LANG_CACHE[key] = lang if lang in LANGS else DEFAULT_LANG
    _INLINE_LANG_KEYS.append(key)
    while len(_INLINE_LANG_KEYS) > 1000:
        old = _INLINE_LANG_KEYS.pop(0)
        if old not in GAMES:
            LANG_CACHE.pop(old, None)


async def edit(bot, chat_id, message_id, text, kb=None):
    """Xabarni xavfsiz tahrirlaydi ("not modified" xatosini e'tiborsiz qoldiradi)."""
    try:
        await bot.edit_message_text(
            text, reply_markup=kb, **msg_target(chat_id, message_id)
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            logger.warning("edit xatosi: %s", e)
    except TelegramError as e:
        logger.warning("edit xatosi: %s", e)


# ───────────────────────────── O'yin holati va taymerlar ─────────────────────────────
# Har bir chatda bir vaqtda bitta o'yin. Faolsizlikdan keyin avtomatik bekor bo'ladi.

GAMES: dict[int, dict] = {}
BG_TASKS: set = set()
# /scrash bosilganda avtomatik yangi raund ochilishini ham to'xtatadi.
CRASH_STOPPED: set[int] = set()


def new_game(chat_id, kind, owner, **extra):
    game = {"type": kind, "owner": owner, "timer": None, "msg_id": None, **extra}
    GAMES[chat_id] = game
    return game


def arm(app, chat_id, game, seconds):
    """O'yin taymerini (qayta) ishga tushiradi."""
    old = game.get("timer")
    if old and not old.done():
        old.cancel()
    task = asyncio.create_task(_expire(app, chat_id, game, seconds))
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)
    game["timer"] = task


def end_game(chat_id, game):
    if game.get("type") == "crash":
        crash_refund(game)
    if GAMES.get(chat_id) is game:
        del GAMES[chat_id]
    timer = game.get("timer")
    if timer and not timer.done():
        timer.cancel()
    game["timer"] = None


async def close_game_message(bot, chat_id, game, text):
    """O'yin xabarini yakuniy matn bilan almashtiradi (yoki yangi xabar yuboradi)."""
    inline = is_inline_key(chat_id)
    if (game.get("msg_id") or inline) and game["type"] != "number":
        target = msg_target(chat_id, game.get("msg_id"))
        try:
            if game.get("media"):
                await bot.edit_message_caption(caption=text, reply_markup=None, **target)
            else:
                await bot.edit_message_text(text, reply_markup=None, **target)
            return
        except TelegramError as e:
            if inline:
                logger.warning("inline o'yin xabarini yopib bo'lmadi: %s", e)
                return
    try:
        await bot.send_message(chat_id, text)
    except TelegramError as e:
        logger.warning("send xatosi: %s", e)


async def _expire(app, chat_id, game, seconds):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return

    if GAMES.get(chat_id) is not game:
        return

    # Crash lobby taymeri faqat hali hech kim qo'shilmagan kutish oynasini yopishi
    # mumkin. Callback va taymer bir vaqtda ishlasa ham faol raundni o'chirmaymiz.
    if game.get("type") == "crash":
        if game.get("state") != "lobby" or game.get("players"):
            return

    del GAMES[chat_id]
    game["timer"] = None

    if game["type"] == "number":
        text = t(chat_id, "number_timeout", number=game["number"])
    elif game["type"] == "croc":
        text = croc_t(chat_id, "timeout", word=escape(str(game.get("word") or ""), quote=False))
    else:
        text = t(chat_id, "timeout")
    await close_game_message(app.bot, chat_id, game, text)

    # Kanaldagi Crash hech kim qo'shilmasa ham to'xtab qolmasin
    if game.get("type") == "crash" and game.get("auto_repeat"):
        task = asyncio.create_task(_crash_auto_restart(app, chat_id))
        BG_TASKS.add(task)
        task.add_done_callback(BG_TASKS.discard)


def active(q, kind):
    """Tugma bosilgan xabar hozirgi o'yinga tegishlimi? (eski xabarlardan himoya)"""
    key = game_key(q)
    game = GAMES.get(key)
    if not game or game["type"] != kind:
        return None
    # Inline o'yinning kaliti xabarning o'zi — boshqa xabar bo'lishi mumkin emas.
    if is_inline_key(key) or game.get("msg_id") == q.message.message_id:
        return game
    return None


# ───────────────────────────── Menyu va umumiy buyruqlar ─────────────────────────────


def menu_kb(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(chat_id, "btn_number"), callback_data="g:number")],
        [InlineKeyboardButton(t(chat_id, "btn_rsp"), callback_data="g:rsp")],
        [InlineKeyboardButton(t(chat_id, "btn_xo"), callback_data="g:xo")],
        [InlineKeyboardButton(memory_t(chat_id, "btn"), callback_data="g:memory")],
        [InlineKeyboardButton(croc_t(chat_id, "btn"), callback_data="g:croc")],
        [InlineKeyboardButton(casino_t(chat_id, "btn"), callback_data="g:casino")],
    ])


# 🎰 Casino bo'limi: pul tikiladigan o'yinlar shu yerga qo'shib boriladi.
CASINO_TEXT = {
    "uz": {"btn": "🎰 Casino", "title": "🎰 <b>CASINO</b>\n\nPul tikib o‘ynaladigan o‘yinni tanlang 👇", "back": "⬅️ Orqaga"},
    "eng": {"btn": "🎰 Casino", "title": "🎰 <b>CASINO</b>\n\nChoose a game to bet on 👇", "back": "⬅️ Back"},
    "ru": {"btn": "🎰 Казино", "title": "🎰 <b>КАЗИНО</b>\n\nВыберите игру на деньги 👇", "back": "⬅️ Назад"},
    "kz": {"btn": "🎰 Казино", "title": "🎰 <b>КАЗИНО</b>\n\nАқшаға ойнайтын ойынды таңдаңыз 👇", "back": "⬅️ Артқа"},
}


def casino_t(chat_id, key):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    return CASINO_TEXT.get(lang, CASINO_TEXT["uz"]).get(key) or CASINO_TEXT["uz"][key]


def casino_kb(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(cr_t(chat_id, "btn"), callback_data="g:crash")],
        [InlineKeyboardButton(frog_t(chat_id, "btn"), callback_data="g:frog")],
        [InlineKeyboardButton(casino_t(chat_id, "back"), callback_data="g:back")],
    ])


def again_row(chat_id):
    if is_inline_key(chat_id):
        # Inline xabarda guruh menyusi yo'q — o'yinlar ro'yxatini shu chatning o'zida ochamiz.
        return [InlineKeyboardButton(
            t(chat_id, "btn_again"), switch_inline_query_current_chat=""
        )]
    return [InlineKeyboardButton(t(chat_id, "btn_again"), callback_data="g:menu")]


CHILD_NAMES = {
    "boy": {
        "uz": ["Muhammad", "Ali", "Umar", "Yusuf", "Imron", "Islom"],
        "eng": ["Muhammad", "Ali", "Omar", "Joseph", "Imran", "Adam"],
        "ru": ["Мухаммад", "Али", "Умар", "Юсуф", "Имран", "Адам"],
        "kz": ["Мұхаммед", "Әли", "Омар", "Жүсіп", "Имран", "Адам"],
    },
    "girl": {
        "uz": ["Madina", "Maryam", "Soliha", "Muslima", "Yasmina", "Zaynab"],
        "eng": ["Maryam", "Amina", "Sofia", "Zaynab", "Yasmin", "Sara"],
        "ru": ["Мадина", "Марьям", "Салиха", "Амина", "Ясмина", "Зайнаб"],
        "kz": ["Мәдина", "Мәриям", "Салиха", "Әмина", "Ясмин", "Зейнеп"],
    },
}

FAMILY_TEXT = {
    "uz": {
        "title": "👨‍👩‍👧‍👦 <b>OILA BO‘LIMI</b>",
        "no_pair": "💞 Oila bo‘limidan foydalanish uchun avval juftlikda bo‘lishingiz kerak.",
        "stats": "💞 Juftlik: <b>{a}</b> ❤️ <b>{b}</b>\n🏆 Jami ball: <b>{points}</b>\n💵 Jami pul: <b>{money}</b>\n👶 Farzandlar: <b>{count}/5</b>\n💳 Keyingi farzand narxi: <b>{price}</b>",
        "rank": "\n\n🏆 <b>Juftliklar reytingi</b>\n{ranking}",
        "child": "👶 Farzand ko‘rish",
        "ask_gender": "👶 Farzandingiz uchun jinsni tanlang:",
        "boy": "👦 O‘g‘il",
        "girl": "👧 Qiz",
        "ask_name": "👶 Farzandingizning ismini yozing:",
        "request": "👶 <b>Farzand so‘rovi</b>\n{parent} siz bilan farzand ko‘rishni taklif qilmoqda.\nJins: <b>{gender}</b>\nIsm: <b>{name}</b>\n\nRozimisiz? Rozilikdan so‘ng farzand 48 soat ichida yetkaziladi.",
        "yes": "✅ Roziman",
        "no": "❌ Rad etaman",
        "sent": "📨 Taklif juftingizga yuborildi. Uning roziligi kutilmoqda.",
        "approved": "✅ Rozilik berildi! Farzandingiz 48 soat ichida yetkaziladi.",
        "approved_now": "✅ Rozilik berildi! Owner juftliklari uchun farzand kutishsiz yetkaziladi.",
        "rejected": "❌ Juftingiz farzand so‘rovini rad etdi.",
        "arrived": "🎉 <b>Farzandingiz yetib keldi!</b>\n👶 {name} — {gender}\nEndi farzandingiz profilingizda ko‘rinadi.",
        "max": "⚠️ Bu juftlikning 5 ta farzandi bor yoki yana bir so‘rov kutilmoqda.",
        "need_start": "⚠️ Juftingiz botni avval shaxsiy chatda ochishi kerak. Unga botga kirib /start bosishini ayting.",
        "pending": "⏳ Sizda farzand so‘rovi allaqachon kutilmoqda.",
    },
    "eng": {
        "title": "👨‍👩‍👧‍👦 <b>FAMILY</b>",
        "no_pair": "💞 You must be in a couple to use the family section.",
        "stats": "💞 Couple: <b>{a}</b> ❤️ <b>{b}</b>\n🏆 Combined points: <b>{points}</b>\n💵 Combined money: <b>{money}</b>\n👶 Children: <b>{count}/5</b>\n💳 Next child cost: <b>{price}</b>",
        "rank": "\n\n🏆 <b>Couples leaderboard</b>\n{ranking}",
        "child": "👶 Have a child",
        "ask_gender": "👶 Choose your child's gender:",
        "boy": "👦 Boy",
        "girl": "👧 Girl",
        "ask_name": "👶 Enter your child’s name:",
        "request": "👶 <b>Child request</b>\n{parent} wants to have a child with you.\nGender: <b>{gender}</b>\nName: <b>{name}</b>\n\nDo you agree? After consent, the child will arrive within 48 hours.",
        "yes": "✅ Agree",
        "no": "❌ Decline",
        "sent": "📨 The request was sent to your partner. Waiting for consent.",
        "approved": "✅ Consent received! Your child will arrive within 48 hours.",
        "approved_now": "✅ Consent received! For owner couples, your child will arrive without the 48-hour wait.",
        "rejected": "❌ Your partner declined the child request.",
        "arrived": "🎉 <b>Your child has arrived!</b>\n👶 {name} — {gender}\nYour child is now shown in your profile.",
        "max": "⚠️ This couple has 5 children already or has a pending request.",
        "need_start": "⚠️ Your partner must open the bot in a private chat and press /start first.",
        "pending": "⏳ You already have a pending child request.",
    },
    "ru": {
        "title": "👨‍👩‍👧‍👦 <b>СЕМЬЯ</b>",
        "no_pair": "💞 Для семейного раздела нужно состоять в паре.",
        "stats": "💞 Пара: <b>{a}</b> ❤️ <b>{b}</b>\n🏆 Общие очки: <b>{points}</b>\n💵 Общие деньги: <b>{money}</b>\n👶 Дети: <b>{count}/5</b>\n💳 Цена следующего ребёнка: <b>{price}</b>",
        "rank": "\n\n🏆 <b>Рейтинг пар</b>\n{ranking}",
        "child": "👶 Завести ребёнка",
        "ask_gender": "👶 Выберите пол ребёнка:",
        "boy": "👦 Мальчик",
        "girl": "👧 Девочка",
        "ask_name": "👶 Напишите имя вашего ребёнка:",
        "request": "👶 <b>Предложение о ребёнке</b>\n{parent} предлагает завести ребёнка вместе.\nПол: <b>{gender}</b>\nИмя: <b>{name}</b>\n\nСогласны? После согласия ребёнок появится в течение 48 часов.",
        "yes": "✅ Согласен(на)",
        "no": "❌ Отказать",
        "sent": "📨 Предложение отправлено партнёру. Ожидаем согласия.",
        "approved": "✅ Согласие получено! Ребёнок появится в течение 48 часов.",
        "approved_now": "✅ Согласие получено! Для пар с владельцем ребёнок появится без ожидания 48 часов.",
        "rejected": "❌ Партнёр отклонил предложение.",
        "arrived": "🎉 <b>Ваш ребёнок прибыл!</b>\n👶 {name} — {gender}\nРебёнок добавлен в ваш профиль.",
        "max": "⚠️ У пары уже 5 детей или есть ожидающий запрос.",
        "need_start": "⚠️ Партнёру нужно открыть бота в личном чате и нажать /start.",
        "pending": "⏳ У вас уже есть ожидающий запрос.",
    },
    "kz": {
        "title": "👨‍👩‍👧‍👦 <b>ОТБАСЫ</b>",
        "no_pair": "💞 Отбасы бөлімін пайдалану үшін жұп болуыңыз керек.",
        "stats": "💞 Жұп: <b>{a}</b> ❤️ <b>{b}</b>\n🏆 Ортақ ұпай: <b>{points}</b>\n💵 Ортақ ақша: <b>{money}</b>\n👶 Балалар: <b>{count}/5</b>\n💳 Келесі баланың бағасы: <b>{price}</b>",
        "rank": "\n\n🏆 <b>Жұптар рейтингі</b>\n{ranking}",
        "child": "👶 Бала сүю",
        "ask_gender": "👶 Баланың жынысын таңдаңыз:",
        "boy": "👦 Ұл",
        "girl": "👧 Қыз",
        "ask_name": "👶 Балаңыздың атын жазыңыз:",
        "request": "👶 <b>Бала туралы ұсыныс</b>\n{parent} сізбен бірге бала сүюді ұсынады.\nЖынысы: <b>{gender}</b>\nЕсімі: <b>{name}</b>\n\nКелісесіз бе? Келісімнен кейін бала 48 сағат ішінде жеткізіледі.",
        "yes": "✅ Келісемін",
        "no": "❌ Бас тарту",
        "sent": "📨 Ұсыныс жұбыңызға жіберілді. Келісім күтілуде.",
        "approved": "✅ Келісім алынды! Бала 48 сағат ішінде жеткізіледі.",
        "approved_now": "✅ Келісім алынды! Иесі бар жұптарға бала 48 сағат күтусіз жеткізіледі.",
        "rejected": "❌ Жұбыңыз ұсыныстан бас тартты.",
        "arrived": "🎉 <b>Балаңыз келді!</b>\n👶 {name} — {gender}\nБала профиліңізге қосылды.",
        "max": "⚠️ Жұпта 5 бала бар немесе күтілген сұрау бар.",
        "need_start": "⚠️ Жұбыңыз ботты жеке чатта ашып, /start басуы керек.",
        "pending": "⏳ Сізде күтілген сұрау бар.",
    },
}


def family_lang(user_id):
    return LANG_CACHE.get(user_id, DEFAULT_LANG)


def family_text(user_id, key, **kwargs):
    lang = family_lang(user_id)
    return FAMILY_TEXT.get(lang, FAMILY_TEXT["uz"]).get(key, FAMILY_TEXT["uz"][key]).format(**kwargs)


def child_gender_label(user_id, gender):
    lang = family_lang(user_id)
    labels = {
        "boy": {"uz": "O‘g‘il", "eng": "Boy", "ru": "Мальчик", "kz": "Ұл"},
        "girl": {"uz": "Qiz", "eng": "Girl", "ru": "Девочка", "kz": "Қыз"},
    }
    return labels[gender].get(lang, labels[gender]["uz"])


CHILD_COSTS = (0, 1000, 2500, 5000, 10000)


def next_child_cost(pair_id):
    count = family_child_count(pair_id)
    return CHILD_COSTS[min(count, 4)]


def family_child_count(pair_id):
    return db().execute("SELECT COUNT(*) FROM family_children WHERE pair_id=?", (pair_id,)).fetchone()[0]


def family_url(context, payload):
    return f"https://t.me/{context.bot.username}?start={payload}"


async def handle_family_start(update, context, payload):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return False
    if payload == "family":
        await cmd_oila(update, context)
        return True
    if payload == "child":
        pair = active_pair(user.id)
        if not pair:
            await msg.reply_text(family_text(user.id, "no_pair"))
            return True
        partner_id = pair[2] if pair[1] == user.id else pair[1]
        count = family_child_count(pair[0])
        pending = db().execute(
            "SELECT 1 FROM child_requests WHERE pair_id=? AND status IN ('selecting','pending','approved') LIMIT 1",
            (pair[0],),
        ).fetchone()
        if count >= 5 or pending:
            await msg.reply_text(family_text(user.id, "max" if count >= 5 else "pending"))
            return True
        now = datetime.now().isoformat(timespec="seconds")
        with db():
            cur = db().execute(
                "INSERT INTO child_requests(requester_id,partner_id,pair_id,status,created_at) VALUES(?,?,?,'selecting',?)",
                (user.id, partner_id, pair[0], now),
            )
            rid = cur.lastrowid
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(family_text(user.id, "boy"), url=family_url(context, f"childgender_boy_{rid}"))],
            [InlineKeyboardButton(family_text(user.id, "girl"), url=family_url(context, f"childgender_girl_{rid}"))],
        ])
        await msg.reply_text(family_text(user.id, "ask_gender"), reply_markup=kb)
        return True
    if payload.startswith("childgender_"):
        parts = payload.split("_")
        if len(parts) != 3 or parts[1] not in ("boy", "girl") or not parts[2].isdigit():
            await msg.reply_text("❌ Noto‘g‘ri tanlov.")
            return True
        gender, rid = parts[1], int(parts[2])
        row = db().execute(
            "SELECT requester_id,pair_id,status FROM child_requests WHERE id=?",
            (rid,),
        ).fetchone()
        if not row or row[0] != user.id or row[2] != "selecting":
            await msg.reply_text("⏳ Bu tanlov eskirgan.")
            return True
        with db():
            db().execute("UPDATE child_requests SET gender=? WHERE id=?", (gender, rid))
        await msg.reply_text(family_text(user.id, "ask_name"))
        return True
    if payload.startswith("childname_"):
        parts = payload.split("_")
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            await msg.reply_text("❌ Noto‘g‘ri tanlov.")
            return True
        rid, idx = int(parts[1]), int(parts[2])
        row = db().execute(
            "SELECT requester_id,partner_id,pair_id,gender,status FROM child_requests WHERE id=?",
            (rid,),
        ).fetchone()
        if not row or row[0] != user.id or row[4] != "selecting" or row[3] not in CHILD_NAMES:
            await msg.reply_text("⏳ Bu tanlov eskirgan.")
            return True
        names = CHILD_NAMES[row[3]][family_lang(user.id)]
        if idx >= len(names):
            await msg.reply_text("❌ Ism topilmadi.")
            return True
        name = names[idx]
        pair = active_pair(user.id)
        if not pair or pair[0] != row[2] or family_child_count(row[2]) >= 5:
            await msg.reply_text(family_text(user.id, "no_pair"))
            return True
        with db():
            db().execute(
                "UPDATE child_requests SET child_name=?,status='pending' WHERE id=?",
                (name, rid),
            )
        partner_lang = family_lang(row[1])
        request_text = family_text(row[1], "request", parent=person_name(user.id), gender=escape(child_gender_label(row[1], row[3])), name=escape(name))
        if user.id in CAREER_OWNER_IDS or row[1] in CAREER_OWNER_IDS:
            request_text = request_text.replace("Rozilikdan so‘ng farzand 48 soat ichida yetkaziladi.", "Owner juftliklari uchun rozilikdan so‘ng farzand kutishsiz yetkaziladi.")
            request_text = request_text.replace("After consent, the child will arrive within 48 hours.", "For owner couples, the child arrives without a 48-hour wait after consent.")
            request_text = request_text.replace("После согласия ребёнок появится в течение 48 часов.", "Для пар с владельцем ребёнок появится сразу после согласия.")
            request_text = request_text.replace("Келісімнен кейін бала 48 сағат ішінде жеткізіледі.", "Иесі бар жұптарға бала келісімнен кейін күтусіз жеткізіледі.")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(family_text(row[1], "yes"), callback_data=f"family:consent:yes:{rid}"),
            InlineKeyboardButton(family_text(row[1], "no"), callback_data=f"family:consent:no:{rid}"),
        ]])
        try:
            await context.bot.send_message(row[1], request_text, reply_markup=kb, parse_mode="HTML")
        except TelegramError:
            with db():
                db().execute("UPDATE child_requests SET status='selecting' WHERE id=?", (rid,))
            await msg.reply_text(family_text(user.id, "need_start"))
            return True
        await msg.reply_text(family_text(user.id, "sent"))
        return True
    return False


async def cmd_oila(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return
    save_user(user)
    pair = active_pair(user.id)
    if not pair:
        await msg.reply_text(family_text(user.id, "no_pair"))
        return
    uid1, uid2 = pair[1], pair[2]
    stats = db().execute(
        "SELECT COALESCE(SUM(points),0) FROM chat_stats WHERE user_id IN (?,?)",
        (uid1, uid2),
    ).fetchone()[0]
    money_rows = db().execute(
        "SELECT user_id,money FROM user_wallet WHERE user_id IN (?,?)",
        (uid1, uid2),
    ).fetchall()
    money = sum(int(r[1] or 0) for r in money_rows)
    count = family_child_count(pair[0])
    child_rows = db().execute(
        "SELECT child_name,gender,id FROM family_children WHERE pair_id=? ORDER BY id",
        (pair[0],),
    ).fetchall()
    names = [kid_summary(user.id, n, g, kid_row(kid_id)) for n, g, kid_id in child_rows]
    a, b = person_name(uid1), person_name(uid2)
    price = next_child_cost(pair[0])
    lang = family_lang(user.id)
    free_label = {"uz": "Bepul", "eng": "Free", "ru": "Бесплатно", "kz": "Тегін"}.get(lang, "Free")
    price_display = free_label if price == 0 else f"{price:,}"
    lines = [family_text(user.id, "title"), family_text(user.id, "stats", a=a, b=b, points=stats, money=money, count=count, price=price_display)]
    if names:
        lines += ["", "<b>👶 Farzandlar</b>", *names]
    rows = db().execute(
        """SELECT p.id,p.user1_id,p.user2_id,
                  COALESCE((SELECT SUM(points) FROM chat_stats WHERE user_id=p.user1_id),0)+
                  COALESCE((SELECT SUM(points) FROM chat_stats WHERE user_id=p.user2_id),0) AS total,
                  COALESCE((SELECT money FROM user_wallet WHERE user_id=p.user1_id),0)+
                  COALESCE((SELECT money FROM user_wallet WHERE user_id=p.user2_id),0) AS cash
           FROM pairs p WHERE p.status='active' ORDER BY total DESC,p.id ASC LIMIT 10"""
    ).fetchall()
    ranking = []
    for i, (_pid, x, y, total, cash) in enumerate(rows, 1):
        ranking.append(f"{i}. {person_name(x)} ❤️ {person_name(y)} — <b>{total}</b> 🏆 · <b>{cash}</b> 💵")
    lines.append(family_text(user.id, "rank", ranking="\n".join(ranking) if ranking else "—"))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(family_text(user.id, "child"), url=family_url(context, "child"))],
        [InlineKeyboardButton(kid_t(user.id, "oila_btn"), url=family_url(context, "kids"))],
    ])
    await msg.reply_text("\n".join(lines), reply_markup=kb)


def child_deliver_now(rid=None):
    """Kutayotgan (tasdiqlangan, 48 soat kutilayotgan) so'rov(lar)ni darhol yetkazishga qo'yadi.
    family_delivery_worker 3 soniya ichida yetkazadi. Qaytaradi: nechta so'rov."""
    now = datetime.now().isoformat(timespec="seconds")
    with db() as c:
        if rid is None:
            cur = c.execute("UPDATE child_requests SET due_at=? WHERE status='approved' AND (due_at IS NULL OR due_at>?)", (now, now))
        else:
            cur = c.execute("UPDATE child_requests SET due_at=? WHERE id=? AND status='approved'", (now, rid))
    return cur.rowcount


async def notify_owners_child_request(bot, rid, requester, partner, name, gender, due, cost):
    """Yangi (to'langan, kutilayotgan) farzand so'rovi haqida ownerlarga xabar + ⚡ tugma."""
    try:
        due_txt = datetime.fromisoformat(due).strftime("%d.%m %H:%M")
    except ValueError:
        due_txt = due
    text = ("👶 <b>FARZAND SO‘ROVI</b> #{rid}\n\n"
            "👨 {a} (<code>{ra}</code>)\n❤️ {b} (<code>{rb}</code>)\n\n"
            "🍼 Ism: <b>{name}</b> · {g}\n💵 To‘langan: <b>{cost}$</b>\n⏳ Yetkaziladi: <b>{due}</b> (48 soat)\n\n"
            "Hammasini birdan yetkazish: /far").format(
        rid=rid, a=person_name(requester), ra=requester, b=person_name(partner), rb=partner,
        name=escape(name or "—"), g=escape(child_gender_label(requester, gender)), cost=fmt_money(cost), due=due_txt)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Hozir yetkazish", callback_data=f"family:far:{rid}")]])
    for oid in sorted(CAREER_OWNER_IDS):
        try:
            await bot.send_message(oid, text, reply_markup=kb)
        except TelegramError:
            pass


async def cmd_far(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/far — ownerlar: kutilayotgan barcha farzandlarni darhol egalariga yetkazadi."""
    user, msg = update.effective_user, update.effective_message
    if not user or not msg:
        return
    if user.id not in CAREER_OWNER_IDS:
        await msg.reply_text("⛔ Bu buyruq faqat bot egalari uchun.")
        return
    rows = db().execute(
        "SELECT id, requester_id, partner_id, child_name FROM child_requests WHERE status='approved' ORDER BY id").fetchall()
    pending = db().execute("SELECT COUNT(*) FROM child_requests WHERE status='pending'").fetchone()[0]
    if not rows:
        await msg.reply_text("✅ Kutilayotgan farzand yo‘q." + (f"\n⏳ Juft roziligini kutayotgan so‘rovlar: <b>{pending}</b>" if pending else ""))
        return
    n = child_deliver_now()
    lines = [f"⚡ <b>{len(rows)} ta farzand egalariga yetkazilmoqda:</b>", ""]
    for rid, a, b, name in rows[:40]:
        lines.append(f"👶 <b>{escape(name or '—')}</b> — {person_name(a)} ❤️ {person_name(b)}")
    if len(rows) > 40:
        lines.append(f"… va yana {len(rows) - 40} ta")
    if pending:
        lines += ["", f"⏳ Juft roziligini kutayotganlar: <b>{pending}</b> (rozilik berilgach yetkaziladi)"]
    lines.append("\nOta-onalarga bir necha soniyada xabar boradi.")
    logger.info("/far: %s ta so'rov darhol yetkazishga qo'yildi (owner %s)", n, user.id)
    await msg.reply_text("\n".join(lines))


async def family_delivery_worker(application):
    while True:
        try:
            now = datetime.now().isoformat(timespec="seconds")
            with db() as conn:
                due = conn.execute(
                    "SELECT id,requester_id,partner_id,pair_id,gender,child_name "
                    "FROM child_requests WHERE status='approved' AND due_at IS NOT NULL AND due_at<=?",
                    (now,),
                ).fetchall()
            for rid, parent1, parent2, pair_id, gender, name in due:
                pair = active_pair(parent1)
                if not pair or pair[0] != pair_id or {pair[1], pair[2]} != {parent1, parent2}:
                    with db():
                        db().execute("UPDATE child_requests SET status='cancelled' WHERE id=?", (rid,))
                    continue
                with db():
                    db().execute(
                        """INSERT OR IGNORE INTO family_children(pair_id,parent1_id,parent2_id,gender,child_name,born_at,request_id)
                           VALUES(?,?,?,?,?,?,?)""",
                        (pair_id, parent1, parent2, gender, name, now, rid),
                    )
                    db().execute("UPDATE child_requests SET status='delivered',delivered_at=? WHERE id=?", (now, rid))
                for pid in (parent1, parent2):
                    try:
                        await application.bot.send_message(
                            pid,
                            family_text(pid, "arrived", name=escape(name), gender=escape(child_gender_label(pid, gender))),
                        )
                    except TelegramError:
                        logger.warning("Farzand yetib kelgani haqida xabar yuborilmadi: %s", pid)
        except Exception:
            logger.exception("Farzandlarni yetkazish jarayonida xato")
        await asyncio.sleep(3)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message

    if not chat or not msg:
        return

    if chat.type == ChatType.PRIVATE:
        user = update.effective_user
        if user and not user.is_bot:
            save_user(user)
            mark_started(user.id)
        if not user:
            return

        save_user(user)
        payload = context.args[0] if context.args else ""
        if payload and payload.startswith("shop_"):
            if payload == "shop_catalog":
                await cmd_shop(update, context)
            return
        if payload and await handle_family_start(update, context, payload):
            return
        if payload and await settings_start_payload(update, context, payload):
            return
        # /profil, /oila va do'kondagi URL tugmalar shu yerga olib keladi.
        section = {
            "bank": lambda: bank_banks_view(user.id, user.id),
            "birja": lambda: birja_home_view(user.id, user.id),
            "kids": lambda: kid_list_view(user.id),
            "exch": lambda: exchange_menu_view(user.id),
        }.get(payload)
        if section:
            text, kb = section()
            await msg.reply_text(text, reply_markup=kb)
            return
        gender = db().execute(
            "SELECT gender FROM user_gender WHERE user_id=?", (user.id,)
        ).fetchone()
        if not gender:
            await msg.reply_text(
                "👋 Botdan foydalanish uchun jinsingizni tanlang:",
                reply_markup=gender_keyboard(),
            )
            return

        row = career_get_user(user.id)

        # Tug‘ilgan sana hali kiritilmagan
        if not row or not row[1]:
            await msg.reply_text(
                "🎮 <b>Son Bot</b>ga xush kelibsiz!\n\n"
                "Avval profilingizni sozlaymiz.\n"
                "Bu faqat bir marta qilinadi.",
                reply_markup=career_birth_kb(),
            )
            return

        # Sana tasdiqlangan, lekin kasb tanlanmagan
        if not row[3]:
            await msg.reply_text(
                "💼 <b>Endi kasbingizni tanlang:</b>\n\n"
                "16 ta kasbdan birini tanlang.",
                reply_markup=career_profession_kb(chat.id),
            )
            return

        username = context.bot.username
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                t(chat.id, "btn_add_group"),
                url=f"https://t.me/{username}?startgroup=true",
            )
        ]])

    else:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                t(chat.id, "btn_games"),
                callback_data="g:menu"
            )
        ]])

    await msg.reply_text(
        t(chat.id, "start_text"),
        reply_markup=kb
    )




PANEL_PERMISSIONS = {
    "users": "users", "groups": "groups", "active": "active",
    "stats": "stats", "games": "games", "gifts": "gifts",
    "broadcast": "broadcast", "economy": "economy", "hadya": "hadya",
    "child_instant": "child_instant", "admin_management": "admin_management",
}


def is_panel_admin(user_id):
    if user_id in CAREER_OWNER_IDS:
        return True
    c = db()
    return c.execute(
        "SELECT 1 FROM bot_panel_admins WHERE user_id = ?",
        (int(user_id),),
    ).fetchone() is not None


def panel_has_permission(user_id, permission):
    if user_id in CAREER_OWNER_IDS:
        return True
    c = db()
    row = c.execute(
        """SELECT enabled FROM bot_panel_admin_permissions
           WHERE user_id = ? AND permission = ?""",
        (int(user_id), permission),
    ).fetchone()
    return bool(row and row[0])


def panel_permission_for_callback(data):
    if data == "panel:home":
        return None
    action = data.split(":")[1] if ":" in data else ""
    if action in ("broadcast", "broadcast_cancel", "broadcast_confirm"):
        return "broadcast"
    if action in ("give", "money_cancel", "money_confirm", "bankrupt"):
        return "economy"
    if action in ("admin", "admins"):
        return "admin_management"
    if action in PANEL_PERMISSIONS:
        return PANEL_PERMISSIONS[action]
    return "owner_only"


def panel_keyboard(user_id=None):
    rows = []
    is_owner = user_id in CAREER_OWNER_IDS
    available = {
        permission for permission in PANEL_PERMISSIONS
        if is_owner or (
            user_id is not None
            and panel_has_permission(user_id, permission)
        )
    }

    if "users" in available and "groups" in available:
        rows.append([
            InlineKeyboardButton("👤 Foydalanuvchilar", callback_data="panel:users"),
            InlineKeyboardButton("🏘 Guruhlar", callback_data="panel:groups"),
        ])
    else:
        if "users" in available:
            rows.append([InlineKeyboardButton(
                "👤 Foydalanuvchilar", callback_data="panel:users"
            )])
        if "groups" in available:
            rows.append([InlineKeyboardButton(
                "🏘 Guruhlar", callback_data="panel:groups"
            )])

    if "active" in available and "stats" in available:
        rows.append([
            InlineKeyboardButton("🎮 Faol o'yinlar", callback_data="panel:active"),
            InlineKeyboardButton("📊 Umumiy statistika", callback_data="panel:stats"),
        ])
    else:
        if "active" in available:
            rows.append([InlineKeyboardButton(
                "🎮 Faol o'yinlar", callback_data="panel:active"
            )])
        if "stats" in available:
            rows.append([InlineKeyboardButton(
                "📊 Umumiy statistika", callback_data="panel:stats"
            )])

    if "games" in available:
        rows.append([InlineKeyboardButton(
            "🏆 O'yin turlari statistikasi", callback_data="panel:games"
        )])
    if "gifts" in available:
        rows.append([InlineKeyboardButton(
            "🎁 Sovg'alar statistikasi", callback_data="panel:gifts"
        )])

    if "economy" in available:
        rows.append([
            InlineKeyboardButton("💣 Bankrot qilish", callback_data="panel:bankrupt"),
            InlineKeyboardButton("💸 Pul yuborish", callback_data="panel:give"),
        ])
    if "broadcast" in available:
        rows.append([InlineKeyboardButton("📢 Ommaviy xabar", callback_data="panel:broadcast")])
    if "child_instant" in available:
        rows.append([InlineKeyboardButton("👶 Farzandni kutishsiz olish", callback_data="panel:child_instant")])
    if "admin_management" in available:
        rows.append([InlineKeyboardButton("🛡 Adminlarni boshqarish", callback_data="panel:admins")])
    if is_owner:
        rows.append([InlineKeyboardButton("💰 Pul statistikasi", callback_data="panel:money")])
        rows.append([InlineKeyboardButton("🏦 Banklar boshqaruvi", callback_data="panel:banks")])
        rows.append([InlineKeyboardButton("💱 Pul almashuvi", callback_data="panel:exch")])
        rows.append([InlineKeyboardButton("🔢 Ko‘rsatkichlarni tahrirlash", callback_data="panel:stats_edit")])
        rows.append([InlineKeyboardButton("📢 Majburiy obuna", callback_data="panel:fsub")])
        rows.append([InlineKeyboardButton("🌐 Web App", callback_data="panel:webapp")])
        rows.append([InlineKeyboardButton("🔄 Qayta ro‘yxatdan o‘tish", callback_data="panel:rereg")])
        rows.append([InlineKeyboardButton("👶 Farzand o‘chirish", callback_data="panel:kiddel")])
        rows.append([InlineKeyboardButton("🎰 Crash sozlamalari", callback_data="panel:crash")])
        rows.append([InlineKeyboardButton("✨ Premium emoji", callback_data="panel:pemoji")])

    return InlineKeyboardMarkup(rows or [[
        InlineKeyboardButton("🔄 Panelni yangilash", callback_data="panel:home")
    ]])


# ── Owner panel: farzandni o'chirish ──
# 👶 Farzand o'chirish → foydalanuvchi ID / @username → farzandlari ro'yxati → tanlash → tasdiqlash.

PANEL_KID_CANCEL = InlineKeyboardMarkup([[
    InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:kiddel_cancel")
]])


def panel_kid_list_markup(user_id):
    rows = []
    for kid in kids_of(user_id):
        label = (
            f"🗑 {kid['child_name']} · {child_gender_label(user_id, kid['gender'])} · "
            f"{kid['age']} {KID_TEXT['uz']['age_unit']}"
        )
        rows.append([InlineKeyboardButton(label, callback_data=f"panel:kiddel_pick:{kid['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")])
    return InlineKeyboardMarkup(rows)


async def panel_kid_callback(query, context):
    data = query.data
    if data == "panel:kiddel":
        context.user_data["panel_kid_state"] = "waiting_id"
        await query.edit_message_text(
            "👶 <b>FARZAND O‘CHIRISH</b>\n\nFoydalanuvchi Telegram ID sini yoki @username sini yuboring.",
            reply_markup=PANEL_KID_CANCEL,
        )
        return
    if data == "panel:kiddel_cancel":
        context.user_data.pop("panel_kid_state", None)
        await query.edit_message_text(
            "❎ Bekor qilindi.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")]]),
        )
        return

    action, _, raw_id = data.partition(":")[2].partition(":")
    kid = kid_row(int(raw_id)) if raw_id.isdigit() else None
    if not kid:
        await query.edit_message_text(
            "❌ Farzand topilmadi (balki allaqachon o‘chirilgan).",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")]]),
        )
        return
    parents = f"{person_name(kid['parent1_id'])} ❤️ {person_name(kid['parent2_id'])}"

    if action == "kiddel_pick":
        await query.edit_message_text(
            f"⚠️ <b>{escape(kid['child_name'])}</b> ({kid['age']} yosh) farzandini o‘chirasizmi?\n"
            f"👪 Ota-onasi: {parents}\n\nBu amalni qaytarib bo‘lmaydi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 Ha, o‘chirish", callback_data=f"panel:kiddel_yes:{kid['id']}")],
                [InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:kiddel_cancel")],
            ]),
        )
        return

    if action == "kiddel_yes":
        c = db()
        with c:
            c.execute("DELETE FROM family_children WHERE id=?", (kid["id"],))
        logger.info("Owner %s farzandni o'chirdi: %s (id %s)", query.from_user.id, kid["child_name"], kid["id"])
        await query.edit_message_text(
            f"✅ <b>{escape(kid['child_name'])}</b> o‘chirildi.\n👪 Ota-onasi: {parents}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")]]),
        )


async def panel_kid_handle_text(update, context):
    msg = update.effective_message
    raw = (msg.text or "").strip()
    c = db()
    if raw.startswith("@"):
        row = c.execute(
            "SELECT user_id FROM users WHERE lower(username)=lower(?)", (raw[1:],)
        ).fetchone()
    elif raw.lstrip("-").isdigit():
        row = (int(raw),)
    else:
        row = None
    if not row:
        await msg.reply_text("❌ Foydalanuvchi topilmadi. ID yoki @username ni tekshiring.", reply_markup=PANEL_KID_CANCEL)
        return
    user_id = row[0]
    if not kids_of(user_id):
        await msg.reply_text(
            f"ℹ️ {person_name(user_id)} (<code>{user_id}</code>) da farzand yo‘q.\nBoshqa ID yuboring yoki bekor qiling.",
            reply_markup=PANEL_KID_CANCEL,
        )
        return
    context.user_data.pop("panel_kid_state", None)
    await msg.reply_text(
        f"👶 {person_name(user_id)} (<code>{user_id}</code>) farzandlari.\nO‘chiriladiganini tanlang 👇",
        reply_markup=panel_kid_list_markup(user_id),
    )


def fmt_money(n):
    return f"{int(n):,}".replace(",", " ")


def money_in_games():
    """Hozir o'yinlarda turgan (yechilgan, lekin hali natijalanmagan) depozitlar."""
    total = 0
    for game in GAMES.values():
        if game.get("type") == "crash" and game.get("charged") and not game.get("settled"):
            total += sum(
                p["bet"] for p in game["players"].values()
                if p.get("paid") and p.get("cash") is None and not p.get("refunded")
            )
    for game in FROG_GAMES.values():
        if game.get("paid") and not game.get("settled"):
            total += game["bet"]
    return total


def panel_money_text(c):
    owners = tuple(CAREER_OWNER_IDS)
    marks = ",".join("?" * len(owners))
    total, holders, users_with_wallet = c.execute(
        "SELECT COALESCE(SUM(money), 0), COALESCE(SUM(money > 0), 0), COUNT(*) FROM user_wallet"
    ).fetchone()
    owners_total = c.execute(
        f"SELECT COALESCE(SUM(money), 0) FROM user_wallet WHERE user_id IN ({marks})", owners
    ).fetchone()[0]
    others_total, others_holders, others_max = c.execute(
        f"""SELECT COALESCE(SUM(money), 0), COALESCE(SUM(money > 0), 0), COALESCE(MAX(money), 0)
            FROM user_wallet WHERE user_id NOT IN ({marks})""",
        owners,
    ).fetchone()
    top = c.execute(
        f"""SELECT w.user_id, w.money, u.first_name, u.username
            FROM user_wallet w LEFT JOIN users u ON u.user_id = w.user_id
            WHERE w.user_id NOT IN ({marks}) AND w.money > 0
            ORDER BY w.money DESC LIMIT 10""",
        owners,
    ).fetchall()
    in_games = money_in_games()
    average = others_total // others_holders if others_holders else 0
    loans_n, loans_due = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(due), 0) FROM bank_loans WHERE status='active'"
    ).fetchone()
    deps_n, deps_amount, deps_payout = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(SUM(payout), 0) FROM bank_deposits WHERE status='active'"
    ).fetchone()
    debtors, debt = c.execute(
        "SELECT COUNT(*), COALESCE(-SUM(money), 0) FROM user_wallet WHERE money < 0"
    ).fetchone()
    birja_value = sum(
        qty * (BIRJA_PRICES.get(asset) or {"price": 0.0})["price"]
        for asset, qty in c.execute("SELECT asset, qty FROM birja_holdings WHERE qty > 0")
    )

    lines = [
        "💰 <b>PUL STATISTIKASI</b>",
        "",
        f"💵 Jami pul (hamma hamyonlarda): <b>{fmt_money(total)}$</b>",
        f"👑 Bot egalarida: <b>{fmt_money(owners_total)}$</b>",
        f"👤 Foydalanuvchilarda (egalarsiz): <b>{fmt_money(others_total)}$</b>",
        f"🎰 Hozir o'yinlarda tikilgan: <b>{fmt_money(in_games)}$</b>",
        "",
        f"👥 Puli bor foydalanuvchilar: <b>{fmt_money(holders)}</b> / {fmt_money(users_with_wallet)} hamyon",
        f"📊 O'rtacha (puli borlar, egalarsiz): <b>{fmt_money(average)}$</b>",
        f"🔝 Eng katta balans (egalarsiz): <b>{fmt_money(others_max)}$</b>",
        "",
        "🏦 <b>Banklar</b>",
        f"💸 Faol kreditlar: <b>{loans_n}</b> ta · qaytarilishi kerak <b>{fmt_money(loans_due)}$</b>",
        f"🏦 Faol omonatlar: <b>{deps_n}</b> ta · <b>{fmt_money(deps_amount)}$</b> → to'lanadi {fmt_money(deps_payout)}$",
        f"🔻 Minus balanslar: <b>{debtors}</b> ta · jami qarz <b>{fmt_money(debt)}$</b>",
        f"📈 Birjadagi aktivlar qiymati: <b>{fmt_money(round(birja_value))}$</b>",
    ]
    if top:
        lines += ["", "🏆 <b>Eng boy 10 foydalanuvchi:</b>"]
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, money, first_name, username) in enumerate(top):
            mark = medals[i] if i < len(medals) else f"{i + 1}."
            lines.append(
                f"{mark} {pretty_name(first_name, username)} — <b>{fmt_money(money)}$</b> "
                f"(<code>{uid}</code>)"
            )
    return "\n".join(lines)


def panel_group_ids(c):
    ids = {
        row[0] for row in c.execute(
            "SELECT chat_id FROM group_languages WHERE chat_id < 0"
        ).fetchall()
    }
    ids.update(
        row[0] for row in c.execute(
            "SELECT DISTINCT chat_id FROM chat_stats WHERE chat_id < 0"
        ).fetchall()
    )
    return ids


async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    if not chat or not msg or not user:
        return

    if not is_panel_admin(user.id):
        await msg.reply_text("⛔ Sizga paneldan foydalanish ruxsati berilmagan.")
        return

    if chat.type != ChatType.PRIVATE:
        await msg.reply_text("🔐 Panelni bot bilan shaxsiy chatda oching.")
        return

    c = db()
    users_count = bot_users_count(c)
    seen_count = seen_users_count(c)
    group_ids = panel_group_ids(c)
    total_games = c.execute(
        "SELECT COALESCE(SUM(games), 0) FROM chat_stats"
    ).fetchone()[0]

    text = (
        "🛠 <b>BOT EGASI PANELI</b>\n\n"
        "Kerakli bo'limni tugma orqali tanlang.\n\n"
        f"👤 Foydalanuvchilar: <b>{stat_show('users', users_count)}</b>\n"
            f"👥 Guruhlarda ko‘rilgan: <b>{seen_count}</b>\n"
        f"🏘 Guruhlar: <b>{stat_show('groups', len(group_ids))}</b>\n"
        f"🎮 Faol o'yinlar: <b>{stat_show('active', len(GAMES))}</b>"
    )

    await msg.reply_text(text, reply_markup=panel_keyboard(user.id))



PANEL_PERMISSION_LABELS = {
    "users": "👤 Foydalanuvchilar",
    "groups": "🏘 Guruhlar",
    "active": "🎮 Faol o‘yinlar",
    "stats": "📊 Umumiy statistika",
    "games": "🏆 O‘yin statistikasi",
    "gifts": "🎁 Sovg‘alar statistikasi",
    "broadcast": "📢 Ommaviy xabar",
    "economy": "💸 Pul yuborish / bankrot",
    "hadya": "🎁 Hadya yaratish",
    "child_instant": "👶 Farzandni kutishsiz olish",
    "admin_management": "🛡 Adminlarni boshqarish",
}


async def show_admin_permissions(query, aid):
    c = db()
    exists = c.execute(
        "SELECT 1 FROM bot_panel_admins WHERE user_id = ?", (aid,)
    ).fetchone()
    if not exists:
        await query.edit_message_text(
            "Bu admin topilmadi.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="panel:admin:list")
            ]]),
        )
        return
    buttons = []
    for perm, label in PANEL_PERMISSION_LABELS.items():
        row = c.execute(
            "SELECT enabled FROM bot_panel_admin_permissions "
            "WHERE user_id = ? AND permission = ?",
            (aid, perm),
        ).fetchone()
        enabled = bool(row and row[0])
        buttons.append([InlineKeyboardButton(
            ("✅ " if enabled else "❌ ") + label,
            callback_data=f"panel:admin:toggle:{aid}:{perm}",
        )])
    buttons.append([
        InlineKeyboardButton("⬅️ Adminlar ro‘yxati", callback_data="panel:admin:list")
    ])
    try:
        await query.edit_message_text(
            f"🔐 <b>{aid}</b> uchun bo‘lim ruxsatlari\n\n"
            "✅ — ruxsat berilgan\n❌ — ruxsat berilmagan\n"
            "Tugmani bosib holatini o‘zgartiring.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


def crash_panel_keyboard():
    status = "🟢 Yoqilgan" if CRASH_ENABLED else "🔴 O‘chirilgan"
    group_mode = "🔒 Faqat ulangan guruhlar" if CRASH_GROUP_RESTRICT else "🌐 Barcha guruhlar"
    buttons = [
        [InlineKeyboardButton(f"Ommaviy Crash: {status}", callback_data="panel:crash:toggle")],
        [InlineKeyboardButton("➕ Guruh ulash", callback_data="panel:crash:group_add"),
         InlineKeyboardButton("➖ Guruh uzish", callback_data="panel:crash:group_remove")],
        [InlineKeyboardButton(f"💰 Minimal depozit: {CRASH_MIN_BET}$", callback_data="panel:crash:min")],
        [InlineKeyboardButton(f"⚡ Koeffitsiyent tezligi: {CRASH_TICK:.1f} s", callback_data="panel:crash:speed")],
        [InlineKeyboardButton("➕ Tezlashtirish", callback_data="panel:crash:speed_up"),
         InlineKeyboardButton("➖ Sekinlashtirish", callback_data="panel:crash:speed_down")],
        [InlineKeyboardButton(group_mode, callback_data="panel:crash:group_mode")],
        [InlineKeyboardButton("⬅️ Owner panelga qaytish", callback_data="panel:home")],
    ]
    return InlineKeyboardMarkup(buttons)


async def _crash_panel_edit(query, text, markup):
    """Panel xabarini xavfsiz tahrirlaydi ("not modified" xatosi panelni buzmasin)."""
    try:
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup,
        )
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            logger.warning("Crash panel tahrirlash xatosi: %s", exc)
    except TelegramError as exc:
        logger.warning("Crash panel tahrirlash xatosi: %s", exc)


async def crash_panel_render(query, context):
    """Crash sozlamalari bosh oynasini chizadi (hech qanday amal bajarmaydi)."""
    context.user_data.pop("panel_crash_state", None)
    load_crash_config()
    groups = db().execute("SELECT COUNT(*) FROM crash_groups").fetchone()[0]
    mode = "faqat ulangan guruhlar" if CRASH_GROUP_RESTRICT else "barcha guruhlar"
    warn = ""
    if CRASH_GROUP_RESTRICT and groups == 0:
        warn = "\n\n⚠️ <b>Diqqat:</b> «Faqat ulangan guruhlar» rejimi yoqilgan, lekin guruh ulanmagan — Crash hech qayerda ishlamaydi."
    await _crash_panel_edit(
        query,
        "🎰 <b>CRASH SOZLAMALARI</b>\n\n"
        f"Holati: <b>{'Yoqilgan' if CRASH_ENABLED else 'O‘chirilgan'}</b>\n"
        f"Minimal depozit: <b>{CRASH_MIN_BET}$</b>\n"
        f"Koeffitsiyent tezligi: <b>{CRASH_TICK:.1f} soniya</b>\n"
        f"Ulangan guruhlar: <b>{groups}</b>\n"
        f"Guruh rejimi: <b>{mode}</b>\n\n"
        "Tezlik 0.6–1.6 oralig‘ida: 0.6 — tezroq, 1.6 — sekinroq. "
        "O‘zgarish keyingi raunddan boshlab kuchga kiradi."
        f"{warn}",
        crash_panel_keyboard(),
    )


async def crash_panel_callback(query, context):
    """Har bir tugma: avval amal bajariladi, so'ng bosh oyna QAYTA CHIZILADI
    (oldingi versiyada funksiya o'zini qayta chaqirib, amalni takrorlayverardi)."""
    data = query.data
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:crash")]])

    if data == "panel:crash":
        await crash_panel_render(query, context)
        return

    if data == "panel:crash:toggle":
        load_crash_config()
        crash_config_set("enabled", "0" if CRASH_ENABLED else "1")
        await crash_panel_render(query, context)
        return

    if data == "panel:crash:group_mode":
        load_crash_config()
        crash_config_set("group_restrict", "0" if CRASH_GROUP_RESTRICT else "1")
        await crash_panel_render(query, context)
        return

    if data in ("panel:crash:speed", "panel:crash:speed_up", "panel:crash:speed_down"):
        load_crash_config()
        # Butun "o'ndan bir" birliklarida hisoblaymiz: har bosishda aynan 0.1 soniya.
        tenths = int(round(CRASH_TICK * 10))
        if data == "panel:crash:speed_up":
            tenths = max(6, tenths - 1)
        elif data == "panel:crash:speed_down":
            tenths = min(16, tenths + 1)
        if data != "panel:crash:speed":
            crash_config_set("tick", f"{tenths / 10:.1f}")
        await crash_panel_render(query, context)
        return

    if data == "panel:crash:min":
        context.user_data["panel_crash_state"] = "min_bet"
        await _crash_panel_edit(
            query,
            "💰 Crash uchun yangi minimal depozitni dollar hisobida butun son qilib yuboring.",
            cancel_kb,
        )
        return

    if data == "panel:crash:group_add":
        context.user_data["panel_crash_state"] = "group_add"
        await _crash_panel_edit(
            query,
            "➕ Crashga ulanadigan guruhning ID raqamini yuboring.\n\n"
            "Misol: <code>-1001234567890</code>\n"
            "Bot shu guruhda bo‘lishi kerak.",
            cancel_kb,
        )
        return

    if data == "panel:crash:group_remove":
        rows = db().execute("SELECT chat_id, title FROM crash_groups ORDER BY chat_id").fetchall()
        buttons = [
            [InlineKeyboardButton(
                f"➖ {(r[1] or r[0])} ({r[0]})"[:60],
                callback_data=f"panel:crash:group_del:{r[0]}",
            )]
            for r in rows
        ]
        if not buttons:
            buttons.append([InlineKeyboardButton("Ulangan guruh yo‘q", callback_data="panel:crash")])
        buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="panel:crash")])
        await _crash_panel_edit(
            query,
            "➖ <b>Crash guruhini uzish</b>\nUzmoqchi bo‘lgan guruhni tanlang:",
            InlineKeyboardMarkup(buttons),
        )
        return

    if data.startswith("panel:crash:group_del:"):
        try:
            chat_id = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        c = db()
        c.execute("DELETE FROM crash_groups WHERE chat_id = ?", (chat_id,))
        c.commit()
        await crash_panel_render(query, context)
        return

    # Noma'lum tugma bo'lsa ham panel qotib qolmasin
    await crash_panel_render(query, context)


async def cb_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    uid = query.from_user.id
    if not is_panel_admin(uid):
        await query.answer(
            "⛔ Paneldan foydalanish ruxsati yo‘q.",
            show_alert=True,
        )
        return

    required = panel_permission_for_callback(query.data)
    if required == "owner_only":
        if uid not in CAREER_OWNER_IDS:
            await query.answer("⛔ Bu amal faqat bot egalari uchun.", show_alert=True)
            return
    elif required and not panel_has_permission(uid, required):
        await query.answer("⛔ Bu bo‘lim uchun ruxsat yo‘q.", show_alert=True)
        return

    if query.data == "panel:exch" or query.data.startswith("panel:exch_"):
        await panel_exchange_callback(query, context)
        return

    if query.data == "panel:stats_edit" or query.data.startswith("panel:stat_"):
        await panel_stats_callback(query, context)
        return

    await query.answer()

    if query.data == "panel:pemoji" or query.data.startswith("panel:pemoji:"):
        await pemoji_callback(query, context)
        return

    if query.data == "panel:banks" or query.data.startswith("panel:bank_"):
        # "banks"/"bank_*" PANEL_PERMISSIONS'da yo'q → faqat bot egalari.
        await panel_bank_callback(query, context)
        return

    if query.data == "panel:kiddel" or query.data.startswith("panel:kiddel_"):
        # panel_permission_for_callback: "kiddel*" PANEL_PERMISSIONS'da yo'q → faqat bot egalari.
        await panel_kid_callback(query, context)
        return

    if query.data == "panel:fsub" or query.data.startswith("panel:fsub_"):
        # "fsub*" PANEL_PERMISSIONS'da yo'q → faqat bot egalari.
        await panel_fsub_callback(query, context)
        return

    if query.data == "panel:rereg" or query.data.startswith("panel:rereg_"):
        # "rereg*" PANEL_PERMISSIONS'da yo'q → faqat bot egalari.
        await panel_rereg_callback(query, context)
        return

    if query.data == "panel:webapp" or query.data.startswith("panel:webapp_"):
        # "webapp*" PANEL_PERMISSIONS'da yo'q → faqat bot egalari.
        if query.data == "panel:webapp":
            text, kb = panel_webapp_view()
            await query.edit_message_text(text, reply_markup=kb)
        else:
            await panel_webapp_callback(query, context)
        return

    if query.data == "panel:crash" or query.data.startswith("panel:crash:"):
        if uid not in CAREER_OWNER_IDS:
            await query.answer("⛔ Crash sozlamalari faqat bot egalari uchun.", show_alert=True)
            return
        await crash_panel_callback(query, context)
        return

    # Admin boshqaruvi: faqat bot egalari.
    if query.data == "panel:admins":
        c = db()
        admins = c.execute(
            "SELECT user_id FROM bot_panel_admins ORDER BY added_at DESC"
        ).fetchall()
        buttons = [
            [InlineKeyboardButton("➕ Admin qo‘shish", callback_data="panel:admin:add")],
            [InlineKeyboardButton("👥 Adminlar ro‘yxati", callback_data="panel:admin:list")],
            [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
        ]
        await query.edit_message_text(
            "🛡 <b>ADMIN BOSHQARUVI</b>\n\n"
            f"Qo‘shilgan adminlar: <b>{len(admins)}</b>\n"
            "Admin ID raqami orqali qo‘shiladi. Har bir bo‘limga ruxsat alohida beriladi.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if query.data == "panel:admin:add":
        context.user_data["panel_admin_add_state"] = "waiting_id"
        await query.edit_message_text(
            "➕ Admin qilmoqchi bo‘lgan foydalanuvchining Telegram ID raqamini yuboring.\n\n"
            "Bekor qilish uchun tugmani bosing.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:admins")
            ]]),
        )
        return

    if query.data == "panel:admin:list":
        c = db()
        admins = c.execute(
            "SELECT user_id FROM bot_panel_admins ORDER BY added_at DESC"
        ).fetchall()
        buttons = []
        lines = ["👥 <b>PANEL ADMINLARI</b>", ""]
        for row in admins:
            aid = int(row[0])
            lines.append(f"🆔 <code>{aid}</code>")
            buttons.append([
                InlineKeyboardButton(
                    f"🔐 Ruxsatlar: {aid}",
                    callback_data=f"panel:admin:perms:{aid}",
                ),
                InlineKeyboardButton(
                    f"🗑 O‘chirish: {aid}",
                    callback_data=f"panel:admin:remove:{aid}",
                ),
            ])
        if not admins:
            lines.append("Hozircha qo‘shilgan admin yo‘q.")
        buttons.append([
            InlineKeyboardButton("⬅️ Orqaga", callback_data="panel:admins")
        ])
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if query.data.startswith("panel:admin:remove:"):
        try:
            aid = int(query.data.rsplit(":", 1)[1])
        except ValueError:
            await query.edit_message_text("❌ Admin ID noto‘g‘ri.")
            return
        if aid in CAREER_OWNER_IDS:
            await query.answer("Bot egasini bu yerdan o‘chirib bo‘lmaydi.", show_alert=True)
            return
        c = db()
        c.execute("DELETE FROM bot_panel_admins WHERE user_id = ?", (aid,))
        c.execute("DELETE FROM bot_panel_admin_permissions WHERE user_id = ?", (aid,))
        c.commit()
        await query.edit_message_text(
            f"✅ <code>{aid}</code> adminlar ro‘yxatidan o‘chirildi.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Admin boshqaruvi", callback_data="panel:admins")
            ]]),
        )
        return

    if query.data.startswith("panel:admin:perms:"):
        try:
            aid = int(query.data.rsplit(":", 1)[1])
        except ValueError:
            await query.edit_message_text("❌ Admin ID noto‘g‘ri.")
            return
        await show_admin_permissions(query, aid)
        return

    if query.data.startswith("panel:admin:toggle:"):
        parts = query.data.split(":")
        if len(parts) != 5:
            await query.edit_message_text("❌ So‘rov noto‘g‘ri.")
            return
        try:
            aid = int(parts[3])
        except ValueError:
            await query.edit_message_text("❌ Admin ID noto‘g‘ri.")
            return
        perm = parts[4]
        allowed = {"users", "groups", "active", "stats", "games", "gifts",
                   "broadcast", "economy", "hadya", "child_instant", "admin_management"}
        if perm not in allowed:
            await query.edit_message_text("❌ Ruxsat turi noto‘g‘ri.")
            return
        c = db()
        if not c.execute(
            "SELECT 1 FROM bot_panel_admins WHERE user_id = ?", (aid,)
        ).fetchone():
            await query.edit_message_text("Admin topilmadi.")
            return
        row = c.execute(
            "SELECT enabled FROM bot_panel_admin_permissions "
            "WHERE user_id = ? AND permission = ?",
            (aid, perm),
        ).fetchone()
        new_value = 0 if row and row[0] else 1
        c.execute(
            "INSERT INTO bot_panel_admin_permissions (user_id, permission, enabled) "
            "VALUES (?, ?, ?) ON CONFLICT(user_id, permission) "
            "DO UPDATE SET enabled = excluded.enabled",
            (aid, perm, new_value),
        )
        c.commit()
        await show_admin_permissions(query, aid)
        return

    if query.data == "panel:gifts":
        c = db()
        counts = dict(c.execute(
            "SELECT gift_key, COUNT(*) FROM gift_log GROUP BY gift_key"
        ).fetchall())

        gifts = [
            ("ring", "💍 Uzuk"),
            ("bear", "🧸 Ayiqcha"),
            ("bouquet", "💐 Guldasta"),
            ("rose", "🌹 Atirgul"),
            ("diamond", "💎 Olmos"),
        ]
        total = sum(int(counts.get(key, 0)) for key, _ in gifts)
        lines = [
            f"{label}: <b>{int(counts.get(key, 0))} ta</b>"
            for key, label in gifts
        ]
        text = (
            "🎁 <b>SOVG'ALAR STATISTIKASI</b>\n\n"
            + "\n".join(lines)
            + f"\n\n📦 Jami yuborilgan: <b>{total} ta</b>"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "⬅️ Panelga qaytish",
                    callback_data="panel:home"
                )
            ]]),
        )
        return

    if query.data == "panel:broadcast":
        context.user_data["panel_broadcast_state"] = "waiting_text"
        context.user_data.pop("panel_broadcast_pending", None)
        await query.edit_message_text(
            "📢 Barcha foydalanuvchilarga yuboriladigan matnni yuboring.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:broadcast_cancel")
            ]]),
        )
        return

    if query.data == "panel:broadcast_cancel":
        context.user_data.pop("panel_broadcast_state", None)
        context.user_data.pop("panel_broadcast_pending", None)
        await query.edit_message_text(
            "❎ Ommaviy xabar bekor qilindi.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")
            ]]),
        )
        return

    if query.data == "panel:broadcast_confirm":
        text_to_send = context.user_data.get("panel_broadcast_pending")
        if not text_to_send:
            await query.edit_message_text("Xabar topilmadi. Qaytadan boshlang.")
            return

        context.user_data.pop("panel_broadcast_pending", None)
        context.user_data.pop("panel_broadcast_state", None)

        c = db()
        try:
            recipients = c.execute("SELECT user_id FROM users").fetchall()
        finally:
            c.close()

        sent = 0
        failed = 0
        await query.edit_message_text(
            f"📢 Yuborish boshlandi: {len(recipients)} foydalanuvchi."
        )

        for index, row in enumerate(recipients):
            try:
                await context.bot.send_message(
                    chat_id=int(row[0]),
                    text=text_to_send,
                )
                sent += 1
            except TelegramError:
                failed += 1
            except Exception:
                failed += 1

            # Har bir keyingi xabardan oldin taxminan 2,7 soniya kutish.
            if index + 1 < len(recipients):
                await asyncio.sleep(2.7)

        await query.edit_message_text(
            "📢 Ommaviy xabar yakunlandi.\n\n"
            f"👥 Jami: {len(recipients)}\n"
            f"✅ Yuborildi: {sent}\n"
            f"❌ Yuborilmadi: {failed}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")
            ]]),
        )
        return

    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else "home"

    try:
        page = max(0, int(parts[2])) if len(parts) > 2 else 0
    except ValueError:
        page = 0

    if query.data in ("panel:bankrupt", "panel:give"):
        kind = "bankrupt" if query.data == "panel:bankrupt" else "give"
        title = "💣 Bankrot qilish" if kind == "bankrupt" else "💸 Pul yuborish"
        await query.edit_message_text(
            f"{title} — kimga?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Hammaga", callback_data=f"panel:{kind}:all")],
                [InlineKeyboardButton("👤 Bir kishiga", callback_data=f"panel:{kind}:one")],
                [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
            ]),
        )
        return

    if query.data == "panel:money_cancel":
        context.user_data.pop("panel_money_state", None)
        context.user_data.pop("panel_money_pending", None)
        context.user_data.pop("panel_money_target", None)
        await query.edit_message_text(
            "❎ Amal bekor qilindi.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")
            ]]),
        )
        return

    if query.data in (
        "panel:bankrupt:all", "panel:bankrupt:one",
        "panel:give:all", "panel:give:one",
    ):
        kind, who = query.data.split(":")[1:]
        if kind == "bankrupt" and who == "all":
            context.user_data["panel_money_pending"] = {"kind": "bankrupt_all"}
            prompt = "⚠️ Barcha foydalanuvchilarning balansini 0 qilishni tasdiqlaysizmi?"
            buttons = [[InlineKeyboardButton("✅ Tasdiqlash", callback_data="panel:money_confirm")]]
        elif kind == "bankrupt":
            context.user_data["panel_money_state"] = "bankrupt_target"
            await query.edit_message_text(
                "Foydalanuvchi Telegram ID sini yoki @username sini yuboring.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:money_cancel")
                ]]),
            )
            return
        elif who == "all":
            context.user_data["panel_money_state"] = "give_all_amount"
            await query.edit_message_text(
                "Har bir foydalanuvchiga qancha pul qo‘shilsin? Faqat musbat butun son yuboring.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:money_cancel")
                ]]),
            )
            return
        else:
            context.user_data["panel_money_state"] = "give_target"
            await query.edit_message_text(
                "Pul oluvchining Telegram ID sini yoki @username sini yuboring.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:money_cancel")
                ]]),
            )
            return

        context.user_data["panel_money_state"] = None
        await query.edit_message_text(
            prompt,
            reply_markup=InlineKeyboardMarkup([
                buttons[0],
                [InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:money_cancel")],
            ]),
        )
        return

    if query.data == "panel:money_confirm":
        pending = context.user_data.get("panel_money_pending")
        if not pending:
            await query.edit_message_text("⏳ Tasdiqlanadigan amal topilmadi.")
            return

        c = db()
        kind = pending["kind"]
        if kind == "bankrupt_all":
            with c:
                c.execute("UPDATE user_wallet SET money=0")
            result = "Barcha balanslar 0 qilindi."
        elif kind == "bankrupt_one":
            with c:
                c.execute(
                    "INSERT OR IGNORE INTO user_wallet(user_id,money) VALUES (?,0)",
                    (pending["user_id"],),
                )
                c.execute(
                    "UPDATE user_wallet SET money=0 WHERE user_id=?",
                    (pending["user_id"],),
                )
            result = f"{escape(pending['name'])} balansini 0 qilindi."
        elif kind == "give_all":
            with c:
                c.execute(
                    "INSERT OR IGNORE INTO user_wallet(user_id,money) "
                    "SELECT user_id,0 FROM users"
                )
                cur = c.execute(
                    "UPDATE user_wallet SET money=money+? "
                    "WHERE user_id IN (SELECT user_id FROM users)",
                    (pending["amount"],),
                )
            result = f"{pending['amount']} puldan {cur.rowcount} foydalanuvchiga qo‘shildi."
        elif kind == "give_one":
            with c:
                c.execute(
                    "INSERT OR IGNORE INTO user_wallet(user_id,money) VALUES (?,0)",
                    (pending["user_id"],),
                )
                c.execute(
                    "UPDATE user_wallet SET money=money+? WHERE user_id=?",
                    (pending["amount"], pending["user_id"]),
                )
            result = f"{escape(pending['name'])} hisobiga {pending['amount']} pul qo‘shildi."
        else:
            await query.edit_message_text("❌ Noma’lum amal.")
            return

        if kind in ("give_one", "give_all"):
            if kind == "give_one":
                await log_money_event(
                    context.bot,
                    "🛡 <b>OWNER PUL QO‘SHDI</b>\n"
                    f"Owner: <code>{query.from_user.id}</code>\n"
                    f"Kimga: {escape(pending.get('name', str(pending.get('user_id'))))} "
                    f"(ID: <code>{pending.get('user_id')}</code>)\n"
                    f"Miqdor: <b>{pending['amount']}$</b>"
                )
            else:
                await log_money_event(
                    context.bot,
                    "🛡 <b>OWNER OMMAVIY PUL QO‘SHDI</b>\n"
                    f"Owner: <code>{query.from_user.id}</code>\n"
                    f"Har bir foydalanuvchiga: <b>{pending['amount']}$</b>\nNatija: {escape(result)}"
                )
        context.user_data.pop("panel_money_pending", None)
        context.user_data.pop("panel_money_state", None)
        context.user_data.pop("panel_money_target", None)
        await query.edit_message_text(
            "✅ " + result,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")
            ]]),
        )
        return

    c = db()
    users_count = bot_users_count(c)
    seen_count = seen_users_count(c)

    group_ids = panel_group_ids(c)
    total_games = c.execute(
        "SELECT COALESCE(SUM(games), 0) FROM chat_stats"
    ).fetchone()[0]

    if action == "users":
        per_page = 10
        total_pages = max(1, (users_count + per_page - 1) // per_page)
        page = min(page, total_pages - 1)

        rows = c.execute(
            """
            SELECT user_id, username, first_name
            FROM users
            ORDER BY first_name COLLATE NOCASE, user_id
            LIMIT ? OFFSET ?
            """,
            (per_page, page * per_page),
        ).fetchall()

        lines = [
            "👤 <b>FOYDALANUVCHILAR RO'YXATI</b>",
            "",
            f"Jami: <b>{users_count}</b>",
            f"Sahifa: <b>{page + 1}/{total_pages}</b>",
            "",
        ]

        for index, (user_id, username, first_name) in enumerate(
            rows, start=page * per_page + 1
        ):
            name = escape(first_name or username or str(user_id))
            mention = (
                f'<a href="tg://user?id={user_id}">{name}</a>'
            )

            if username:
                mention += f" (@{escape(username)})"

            lines.append(f"{index}. {mention}")

        if not rows:
            lines.append("Foydalanuvchilar topilmadi.")

        buttons = []
        nav = []

        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    "⬅️ Oldingi",
                    callback_data=f"panel:users:{page - 1}",
                )
            )

        if page + 1 < total_pages:
            nav.append(
                InlineKeyboardButton(
                    "Keyingi ➡️",
                    callback_data=f"panel:users:{page + 1}",
                )
            )

        if nav:
            buttons.append(nav)

        buttons.append([
            InlineKeyboardButton(
                "🏠 Panelga qaytish",
                callback_data="panel:home",
            )
        ])

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    elif action == "groups":
        lines = [
            "🏘 <b>GURUHLAR RO'YXATI</b>",
            "",
            f"Guruhlar soni: <b>{len(group_ids)}</b>",
            "",
        ]

        if not group_ids:
            lines.append("Hozircha guruhlar qayd etilmagan.")
        else:
            for group_id in sorted(group_ids):
                try:
                    group = await context.bot.get_chat(group_id)
                    title = escape(group.title or str(group_id))

                    # Ommaviy guruh uchun username havolasi.
                    # Yopiq guruh uchun faqat mavjud taklif havolasi.
                    url = None
                    if group.username:
                        url = f"https://t.me/{group.username}"
                    elif getattr(group, "invite_link", None):
                        url = group.invite_link

                    if url:
                        safe_url = escape(url, quote=True)
                        group_name = (
                            f'<a href="{safe_url}">{title}</a>'
                        )
                    else:
                        group_name = title

                    lines.append(
                        f"• {group_name}\n"
                        f"  ID: <code>{group_id}</code>"
                    )

                    if not url:
                        lines.append(
                            "  <i>Guruh havolasi botga mavjud emas.</i>"
                        )

                except TelegramError:
                    lines.append(
                        f"• Nomi olinmadi\n"
                        f"  ID: <code>{group_id}</code>"
                    )

        text = "\n\n".join(lines)

    elif action == "active":
        lines = [
            "🎮 <b>FAOL O'YINLAR</b>",
            "",
            f"Hozir faol o'yinlar: <b>{len(GAMES)}</b>",
            "",
        ]

        if not GAMES:
            lines.append("Hozir faol o'yin yo'q.")
        else:
            for chat_id, game in GAMES.items():
                kind = escape(str(game.get("type", "Noma'lum")))
                lines.append(
                    f"• Turi: <b>{kind}</b>\n"
                    f"  Chat ID: <code>{chat_id}</code>"
                )

        text = "\n\n".join(lines)

    elif action == "stats":
        text = (
            "📊 <b>UMUMIY STATISTIKA</b>\n\n"
            f"👤 Foydalanuvchilar: <b>{stat_show('users', users_count)}</b>\n"
            f"👥 Guruhlarda ko‘rilgan: <b>{seen_count}</b>\n"
            f"🏘 Qayd etilgan guruhlar: <b>{stat_show('groups', len(group_ids))}</b>\n"
            f"🎮 Faol o'yinlar: <b>{stat_show('active', len(GAMES))}</b>\n"
            f"📈 Jami o'yin ishtiroklari: <b>{stat_show('games_total', total_games)}</b>\n\n"
            "ℹ️ Ishtiroklar chat statistikasi asosida hisoblanadi."
        )

    elif action == "money":
        # panel_permission_for_callback: "money" PANEL_PERMISSIONS'da yo'q → faqat bot egalari.
        text = panel_money_text(c)

    elif action == "games":
        counts = {}

        for game in GAMES.values():
            kind = str(game.get("type", "Noma'lum"))
            counts[kind] = counts.get(kind, 0) + 1

        lines = [
            "🏆 <b>O'YIN TURLARI STATISTIKASI</b>",
            "",
            "Hozir faol o'yinlar bo'yicha:",
            "",
        ]

        if counts:
            for kind, count in sorted(counts.items()):
                lines.append(f"• {escape(kind)}: <b>{count}</b>")
        else:
            lines.append("Hozir faol o'yin yo'q.")

        lines.extend([
            "",
            "ℹ️ Tarixiy statistika hali saqlanmaydi.",
        ])
        text = "\n".join(lines)

    else:
        text = (
            "🛠 <b>BOT EGASI PANELI</b>\n\n"
            "Kerakli bo'limni tugma orqali tanlang.\n\n"
            f"👤 Foydalanuvchilar: <b>{stat_show('users', users_count)}</b>\n"
            f"👥 Guruhlarda ko‘rilgan: <b>{seen_count}</b>\n"
            f"🏘 Guruhlar: <b>{stat_show('groups', len(group_ids))}</b>\n"
            f"🎮 Faol o'yinlar: <b>{stat_show('active', len(GAMES))}</b>"
        )

        await query.edit_message_text(
            text,
            reply_markup=panel_keyboard(query.from_user.id),
        )
        return

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "⬅️ Panelga qaytish",
                    callback_data="panel:home",
                )
            ]
        ]),
        disable_web_page_preview=True,
    )


async def cmd_emps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    if chat.type == ChatType.PRIVATE:
        await msg.reply_text(t(chat.id, "use_group"))
        return

    game = GAMES.get(chat.id)
    if game:
        await msg.reply_text(t(chat.id, "busy", game=t(chat.id, "btn_" + game["type"])))
        return

    await msg.reply_text(t(chat.id, "menu_title"), reply_markup=menu_kb(chat.id))


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user
    if not chat or not msg or not user:
        return

    if chat.type == ChatType.PRIVATE:
        await msg.reply_text(t(chat.id, "use_group"))
        return

    game = GAMES.get(chat.id)
    if not game:
        await msg.reply_text(t(chat.id, "no_game"))
        return

    anonymous_admin = bool(msg.sender_chat and msg.sender_chat.id == chat.id)
    allowed = (
        user.id == game["owner"]
        or anonymous_admin
        or await is_admin(context.bot, chat.id, user.id)
    )
    if not allowed:
        await msg.reply_text(t(chat.id, "stop_denied"))
        return

    end_game(chat.id, game)
    if game.get("type") == "croc":
        stop_text = croc_t(chat.id, "stopped", word=escape(str(game.get("word") or ""), quote=False))
    else:
        stop_text = t(chat.id, "stopped")
    await close_game_message(context.bot, chat.id, game, stop_text)


async def cmd_reyting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    private = chat.type == ChatType.PRIVATE
    rows = top_players(chat.id, private)
    if not rows:
        await msg.reply_text(t(chat.id, "rating_empty"))
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = [t(chat.id, "rating_title_global" if private else "rating_title"), ""]
    for i, (first_name, username, points, wins) in enumerate(rows):
        lines.append(
            f"{medals[i]} <b>{pretty_name(first_name, username)}</b> — {points} 💰 · {wins} 🏆"
        )
    await msg.reply_text("\n".join(lines))


async def cmd_profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user
    if not chat or not msg or not user:
        return

    save_user(user)

    c = db()
    c.execute("INSERT OR IGNORE INTO user_wallet (user_id, money) VALUES (?, 0)", (user.id,))
    c.commit()
    money = c.execute(
        "SELECT money FROM user_wallet WHERE user_id=?",
        (user.id,)
    ).fetchone()[0]

    money = int(money or 0)

    private = chat.type == ChatType.PRIVATE

    career_row = c.execute(
        "SELECT birth_date, profession_id FROM users WHERE user_id=?",
        (user.id,)
    ).fetchone()

    birth_date = career_row[0] if career_row else None
    profession_id = career_row[1] if career_row else None

    age = None
    if birth_date:
        try:
            from datetime import date
            birth = date.fromisoformat(birth_date)
            today = date.today()
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        except (ValueError, TypeError):
            age = None

    birth_display = "—"
    if birth_date:
        try:
            birth_display = date.fromisoformat(birth_date).strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            birth_display = birth_date

    if age is not None:
        lang = LANG_CACHE.get(chat.id, DEFAULT_LANG)
        age_units = {
            "uz": "yosh",
            "eng": "years old",
            "ru": "лет",
            "kz": "жаста",
        }
        age_display = f"{age} {age_units.get(lang, age_units['uz'])}"
    else:
        age_display = "—"

    career_xp_row = c.execute(
        "SELECT career_xp FROM user_career WHERE user_id=?",
        (user.id,)
    ).fetchone()
    career_xp = career_xp_row[0] if career_xp_row else 0

    profession = (
        profession_name(profession_id, chat.id)
        if profession_id else "—"
    )

    points, games, wins, losses, draws = get_stats(chat.id, user.id, private)
    winrate = round(wins / games * 100, 1) if games else 0

    rank = ""
    if not private and games:
        rank = t(chat.id, "profile_rank", rank=get_rank(chat.id, points, wins))

    pair = active_pair(user.id)
    if pair:
        partner_id = pair[2] if pair[1] == user.id else pair[1]
        partner_info = f"💞 Juftingiz: {person_name(partner_id)}"
    else:
        lang = LANG_CACHE.get(chat.id, DEFAULT_LANG)
        partner_texts = {
            "uz": "💞 Juftingiz: Hozircha juftingiz yo‘q",
            "eng": "💞 Partner: You don't have a partner yet.",
            "ru": "💞 Пара: Пока у вас нет пары.",
            "kz": "💞 Жұбыңыз: Әзірге жұбыңыз жоқ.",
        }
        partner_info = partner_texts.get(lang, partner_texts["uz"])

    child_lines = []
    if pair:
        child_rows = c.execute(
            "SELECT child_name,gender,id FROM family_children WHERE pair_id=? ORDER BY id",
            (pair[0],),
        ).fetchall()
        child_lines = [
            kid_summary(user.id, child_name, child_gender, kid_row(kid_id))
            for child_name, child_gender, kid_id in child_rows
        ]
    profile_lang = family_lang(user.id)
    child_prefix = {"uz": "👶 Farzandlar", "eng": "👶 Children", "ru": "👶 Дети", "kz": "👶 Балалар"}.get(profile_lang, "👶 Children")
    none_text = {"uz": "yo‘q", "eng": "none", "ru": "нет", "kz": "жоқ"}.get(profile_lang, "none")
    child_info = child_prefix + ": " + (", ".join(child_lines) if child_lines else none_text)
    partner_info = partner_info + "\n" + child_info
    button_labels = {
        "uz": ["👨‍👩‍👧‍👦 OILA", "💞 Juftlashish arizasi", "💼 Ishdan bo‘shash arizasi", "💔 Juft bilan ajrashish arizasi"],
        "eng": ["👨‍👩‍👧‍👦 FAMILY", "💞 Pairing application", "💼 Resignation application", "💔 Divorce application"],
        "ru": ["👨‍👩‍👧‍👦 СЕМЬЯ", "💞 Заявка на пару", "💼 Заявление об увольнении", "💔 Заявление о разводе"],
        "kz": ["👨‍👩‍👧‍👦 ОТБАСЫ", "💞 Жұп болу өтініші", "💼 Жұмыстан шығу өтініші", "💔 Ажырасу өтініші"],
    }.get(profile_lang, ["👨‍👩‍👧‍👦 FAMILY", "💞 Pairing application", "💼 Resignation application", "💔 Divorce application"])
    profile_buttons = [
        [InlineKeyboardButton(button_labels[0], url=family_url(context, "family"))],
        [InlineKeyboardButton(button_labels[1], callback_data="rel:menu:pair")],
        [InlineKeyboardButton(button_labels[2], callback_data="rel:menu:quit")],
        [InlineKeyboardButton(button_labels[3], callback_data="rel:menu:divorce")],
    ]
    shop_label = {
        "uz": "🛍 DO‘KON", "eng": "🛍 SHOP",
        "ru": "🛍 МАГАЗИН", "kz": "🛍 ДҮКЕН",
    }.get(profile_lang, "🛍 DO‘KON")
    profile_buttons.insert(0, [
        InlineKeyboardButton(shop_label, callback_data="shop:open")
    ])
    bank_label, birja_label = {
        "uz": ("🏦 Banklar", "📈 Birja"), "eng": ("🏦 Banks", "📈 Exchange"),
        "ru": ("🏦 Банки", "📈 Биржа"), "kz": ("🏦 Банктер", "📈 Биржа"),
    }.get(profile_lang, ("🏦 Banklar", "📈 Birja"))
    profile_buttons.insert(1, [
        InlineKeyboardButton(bank_label, url=family_url(context, "bank")),
        InlineKeyboardButton(birja_label, url=family_url(context, "birja")),
    ])
    profile_buttons.insert(2, [
        InlineKeyboardButton(kid_t(user.id, "oila_btn"), url=family_url(context, "kids")),
    ])
    if exch_ready() and EXCHANGE_PARTNER_URL:
        exch_label = {"uz": f"💱 {EXCHANGE_PARTNER_NAME} ga o‘tkazish", "eng": f"💱 Transfer to {EXCHANGE_PARTNER_NAME}",
                      "ru": f"💱 Перевод в {EXCHANGE_PARTNER_NAME}", "kz": f"💱 {EXCHANGE_PARTNER_NAME} ішіне аудару"}.get(profile_lang)
        profile_buttons.insert(3, [InlineKeyboardButton(exch_label, url=family_url(context, "exch"))])
    profile_text = t(
        chat.id,
        "profile",
        name=uname(user),
        birth_date=birth_display,
        age=age_display,
        level=level_name(chat.id, points),
        points=points,
        money=money,
        profession=profession,
        career_xp=career_xp,
        games=games,
        wins=wins,
        losses=losses,
        draws=draws,
        winrate=winrate,
        bar=bar(winrate),
        rank=rank,
        partner_info=partner_info,
    )
    profile_text = profile_emojify(profile_text)
    # Received gifts are shown directly in the profile (newest first).
    gift_count = c.execute(
        "SELECT COUNT(*) FROM gift_log WHERE recipient_id=?", (user.id,)
    ).fetchone()[0]
    gift_rows = c.execute(
        "SELECT sender_id,gift_key,price FROM gift_log WHERE recipient_id=? ORDER BY id DESC LIMIT 5",
        (user.id,),
    ).fetchall()
    gift_titles = {"uz": "🎁 Qabul qilingan sovg‘alar", "eng": "🎁 Received gifts", "ru": "🎁 Полученные подарки", "kz": "🎁 Алған сыйлықтар"}
    no_gifts = {"uz": "Hozircha yo‘q", "eng": "None yet", "ru": "Пока нет", "kz": "Әзірге жоқ"}
    gift_lines = [f"{gift_label_html(key, SHOP_GIFTS.get(key, (key, price))[0])} — {person_name(sender_id)} ({price}$)" for sender_id, key, price in gift_rows]
    if gift_count > len(gift_rows):
        gift_lines.append({"uz": f"… va yana {gift_count-len(gift_rows)} ta", "eng": f"… and {gift_count-len(gift_rows)} more", "ru": f"… и ещё {gift_count-len(gift_rows)}", "kz": f"… және тағы {gift_count-len(gift_rows)}"}.get(profile_lang, f"… {gift_count-len(gift_rows)} more"))
    profile_text += "\n\n" + profile_emojify(gift_titles.get(profile_lang, gift_titles["uz"])) + ":\n" + ("\n".join(gift_lines) if gift_lines else no_gifts.get(profile_lang, no_gifts["uz"]))
    if rereg_allowed(user.id):
        profile_buttons.append([InlineKeyboardButton("🔄 Qayta ro‘yxatdan o‘tish", callback_data="career:rereg")])
    await msg.reply_text(
        profile_text,
        reply_markup=InlineKeyboardMarkup(profile_buttons),
        parse_mode=ParseMode.HTML,
    )




# ───────────── JINS VA JUFTLIK TIZIMI ─────────────

def active_pair(user_id):
    return db().execute(
        """SELECT id, user1_id, user2_id, group_id, started_at
           FROM pairs
           WHERE status='active' AND (user1_id=? OR user2_id=?)
           LIMIT 1""",
        (user_id, user_id),
    ).fetchone()


def person_name(user_id):
    row = db().execute(
        "SELECT first_name, username FROM users WHERE user_id=?",
        (user_id,),
    ).fetchone()

    if row:
        display_name = row[0] or row[1] or "Foydalanuvchi"
    else:
        display_name = "Foydalanuvchi"

    display_name = html.escape(str(display_name))
    return f'<a href="tg://user?id={user_id}">{display_name}</a>'

def gender_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👦 O‘g‘il bola", callback_data="rel:gender:male"),
        InlineKeyboardButton("👧 Qiz bola", callback_data="rel:gender:female"),
    ]])


async def notify_pair_owners(application, request_id, title):
    c = db()
    row = c.execute(
        "SELECT requester_id, target_id FROM pair_requests WHERE id=?",
        (request_id,),
    ).fetchone()

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"rel:owner:yes:{request_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"rel:owner:no:{request_id}"),
    ]])

    people = ""
    if row:
        people = (
            f"\n👤 Arizachi: {person_name(row[0])} (ID: {row[0]})"
            + (
                f"\n👥 Ikkinchi tomon: {person_name(row[1])} (ID: {row[1]})"
                if row[1] else ""
            )
        )

    sent = 0
    for owner_id in CAREER_OWNER_IDS:
        try:
            await application.bot.send_message(
                chat_id=owner_id,
                text=f"📨 <b>{title}</b>\nAriza raqami: {request_id}{people}",
                reply_markup=kb,
            )
            sent += 1
        except TelegramError as e:
            logger.warning("Egaga ariza yuborilmadi (%s): %s", owner_id, e)
    return sent


def parent_role(user_id):
    row = db().execute("SELECT gender FROM user_gender WHERE user_id=?", (user_id,)).fetchone()
    return row[0] if row else None


def divorce_kids(pair_id):
    return db().execute(
        "SELECT id, child_name, working FROM family_children WHERE pair_id=? ORDER BY id", (pair_id,)
    ).fetchall()


def divorce_default_custody(pair):
    """Eski arizalar uchun: ona (aniqlansa), aks holda juftlikning ikkinchi a'zosi."""
    for uid in (pair[1], pair[2]):
        if parent_role(uid) == "female":
            return uid
    return pair[2]


def divorce_terms_text(pair, custody_id=None):
    """Ajrashish oqibatlari: pul, sovg'alar, farzandlar va aliment."""
    if not pair:
        return ""
    a, b = pair[1], pair[2]
    wa, wb = wallet_balance(a), wallet_balance(b)
    total = wa + wb
    gifts = db().execute(
        "SELECT COUNT(*), COALESCE(SUM(price), 0) FROM gift_log WHERE recipient_id IN (?, ?)", (a, b)
    ).fetchone()
    lines = [
        "⚠️ <b>Ajrashish oqibatlari:</b>",
        f"💵 Ikkalangiz hamyonidagi pul jamlanib teng bo‘linadi: {person_name(a)} {fmt_money(wa)}$ + "
        f"{person_name(b)} {fmt_money(wb)}$ → har biringizga ≈ <b>{fmt_money(total // 2)}$</b>",
        f"🎁 Olingan sovg‘alar ({gifts[0]} ta, {fmt_money(gifts[1])}$) qiymati bo‘yicha teng taqsimlanadi",
    ]
    kids = divorce_kids(pair[0])
    minors = [k for k in kids if not k[2]]
    if kids:
        lines.append(
            f"👶 Farzandlar ({len(kids)} ta) bir tomonda qoladi. Ikkinchi tomon har bir farzand uchun kuniga "
            f"<b>{ALIMONY_PER_CHILD}$</b> aliment to‘laydi (farzand ishga kirguncha) — pul uning hisobidan "
            "avtomatik o‘tkaziladi, balans minusga tushishi mumkin."
        )
    if kids and custody_id:
        payer = b if custody_id == a else a
        lines.append(
            f"🏠 Farzandlar <b>{person_name(custody_id)}</b> bilan qoladi · 💸 {person_name(payer)} kuniga "
            f"<b>{fmt_money(ALIMONY_PER_CHILD * len(minors))}$</b> aliment to‘laydi"
        )
    lines.append("ℹ️ Bankdagi kredit/omonat va birjadagi aktivlar har kimning o‘zida qoladi.")
    return "\n".join(lines)


def divorce_choice_kb(pair, uid):
    if not divorce_kids(pair[0]):
        rows = [[InlineKeyboardButton("💔 Ajrashish so‘rovini yuborish", callback_data="rel:divgo:0")]]
    else:
        rows = []
        for member in (pair[1], pair[2]):
            role = parent_role(member)
            prefix = {"male": "👨 Otada", "female": "👩 Onada"}.get(role, "🏠 Shu odamda")
            name = (db().execute("SELECT first_name FROM users WHERE user_id=?", (member,)).fetchone() or ["?"])[0]
            rows.append([InlineKeyboardButton(f"{prefix} qolsin — {name}", callback_data=f"rel:divgo:{member}")])
    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="rel:divcancel")])
    return InlineKeyboardMarkup(rows)


def divorce_settle(c, pair, custody_id):
    """Ajrashish tasdiqlanganda (tranzaksiya ichida): pul va sovg'alarni teng bo'ladi,
    farzandlar vasiyligi va alimentni belgilaydi. Qaytaradi: xabar uchun ma'lumot."""
    a, b = pair[1], pair[2]
    for uid in (a, b):
        c.execute("INSERT OR IGNORE INTO user_wallet(user_id, money) VALUES (?, 0)", (uid,))
    wa = c.execute("SELECT money FROM user_wallet WHERE user_id=?", (a,)).fetchone()[0]
    wb = c.execute("SELECT money FROM user_wallet WHERE user_id=?", (b,)).fetchone()[0]
    total = int(wa) + int(wb)
    na, nb = total - total // 2, total // 2
    c.execute("UPDATE user_wallet SET money=? WHERE user_id=?", (na, a))
    c.execute("UPDATE user_wallet SET money=? WHERE user_id=?", (nb, b))

    # Sovg'alar: qimmatidan boshlab, hozircha qiymati kamroq tomonga beriladi.
    shares = {a: [0, 0], b: [0, 0]}
    gifts = c.execute(
        "SELECT id, price FROM gift_log WHERE recipient_id IN (?, ?) ORDER BY price DESC, id", (a, b)
    ).fetchall()
    for gift_id, price in gifts:
        to = a if shares[a][1] <= shares[b][1] else b
        shares[to][0] += 1
        shares[to][1] += price
        c.execute("UPDATE gift_log SET recipient_id=? WHERE id=?", (to, gift_id))

    kids = c.execute("SELECT id FROM family_children WHERE pair_id=?", (pair[0],)).fetchall()
    payer = None
    if kids:
        if custody_id not in (a, b):
            custody_id = divorce_default_custody(pair)
        payer = b if custody_id == a else a
        c.execute(
            "UPDATE family_children SET custody_id=?, alimony_payer=?, last_alimony=? WHERE pair_id=?",
            (custody_id, payer, int(time.time()), pair[0]),
        )
    return {
        "a": a, "b": b, "money": (int(wa), int(wb), na, nb), "gifts": shares,
        "kids": len(kids), "custody": custody_id if kids else None, "payer": payer,
    }


async def divorce_notify(bot, st):
    if not st:
        return
    a, b = st["a"], st["b"]
    wa, wb, na, nb = st["money"]
    lines = [
        "💔 <b>Ajrashish yakunlandi — taqsimot</b>",
        "",
        f"💵 Pul: {person_name(a)} {fmt_money(wa)}$ → <b>{fmt_money(na)}$</b> · "
        f"{person_name(b)} {fmt_money(wb)}$ → <b>{fmt_money(nb)}$</b>",
        f"🎁 Sovg‘alar: {person_name(a)} {st['gifts'][a][0]} ta ({fmt_money(st['gifts'][a][1])}$) · "
        f"{person_name(b)} {st['gifts'][b][0]} ta ({fmt_money(st['gifts'][b][1])}$)",
    ]
    if st["kids"]:
        lines.append(
            f"👶 Farzandlar ({st['kids']} ta) <b>{person_name(st['custody'])}</b> bilan qoladi.\n"
            f"💸 {person_name(st['payer'])} har bir farzand uchun kuniga {ALIMONY_PER_CHILD}$ aliment to‘laydi "
            "(farzand ishga kirguncha, hisobidan avtomatik yechiladi)."
        )
    text = "\n".join(lines)
    for uid in (a, b):
        try:
            await bot.send_message(uid, text)
        except TelegramError:
            pass
    await log_money_event(bot, text)


async def create_rel_request(application, request_type, requester_id,
                             target_id=None, group_id=None, custody_id=None):
    c = db()
    pending = c.execute(
        """SELECT id FROM pair_requests
           WHERE request_type=? AND requester_id=?
           AND status IN ('pending', 'proposal', 'partner_consent')
           LIMIT 1""",
        (request_type, requester_id),
    ).fetchone()
    if pending:
        return None

    now = datetime.now().isoformat(timespec="seconds")
    initial_status = "partner_consent" if request_type == "divorce" else "pending"

    with c:
        cur = c.execute(
            """INSERT INTO pair_requests
               (request_type, requester_id, target_id, group_id, status, created_at, custody_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (request_type, requester_id, target_id, group_id, initial_status, now, custody_id),
        )
        request_id = cur.lastrowid

    if request_type == "divorce":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Roziman", callback_data=f"rel:divorce:yes:{request_id}"),
            InlineKeyboardButton("❌ Rad etaman", callback_data=f"rel:divorce:no:{request_id}"),
        ]])
        try:
            await application.bot.send_message(
                chat_id=target_id,
                text=f"💔 <b>Ajrashish so‘rovi</b>\n"
                     f"{person_name(requester_id)} siz bilan ajrashishni so‘radi.\n\n"
                     + divorce_terms_text(active_pair(requester_id), custody_id)
                     + "\n\nShu shartlarga rozimisiz?",
                reply_markup=kb,
            )
        except TelegramError:
            logger.warning("Ajrashish so‘rovi juftiga yuborilmadi: %s", target_id)
            return request_id
    else:
        labels = {
            "pair": "💞 Juftlashish arizasi",
            "quit_job": "💼 Ishdan bo‘shash arizasi",
        }
        await notify_pair_owners(
            application, request_id, labels.get(request_type, "Ariza")
        )
    return request_id


async def cmd_juft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user
    if not chat or not msg or not user:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text("ℹ️ Guruhda kerakli odamning xabariga javob berib /juft yuboring.")
        return

    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target:
        await msg.reply_text("⚠️ Avval juft bo‘lmoqchi bo‘lgan odamning xabariga javob bering.")
        return
    if target.id == user.id or target.is_bot:
        await msg.reply_text("⚠️ O‘zingizni yoki botni tanlay olmaysiz.")
        return

    save_user(user)
    save_user(target)

    if active_pair(user.id) or active_pair(target.id):
        await msg.reply_text("💞 Sizlardan biri allaqachon juftlikda.")
        return

    c = db()
    old = c.execute(
        """SELECT id FROM pair_requests
           WHERE request_type='pair' AND requester_id=? AND target_id=?
             AND status IN ('proposal','pending')
           LIMIT 1""",
        (user.id, target.id),
    ).fetchone()
    if old:
        await msg.reply_text("⏳ Bu odamga taklif allaqachon yuborilgan.")
        return

    now = datetime.now().isoformat(timespec="seconds")
    with c:
        cur = c.execute(
            """INSERT INTO pair_requests
               (request_type, requester_id, target_id, group_id,
                status, created_at)
               VALUES ('pair', ?, ?, ?, 'proposal', ?)""",
            (user.id, target.id, chat.id, now),
        )
        rid = cur.lastrowid

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💞 Roziman", callback_data=f"rel:proposal:yes:{rid}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"rel:proposal:no:{rid}"),
    ]])
    try:
        await context.bot.send_message(
            chat_id=target.id,
            text=f"💌 <b>Juftlik taklifi!</b>\n{person_name(user.id)} sizga juft bo‘lishni taklif qildi.",
            reply_markup=kb,
        )
        await msg.reply_text("💌 Taklif shaxsiy chatga yuborildi.")
    except TelegramError:
        await msg.reply_text(
            "⚠️ Taklifni shaxsiy chatga yubora olmadim. U odam botni ochib /start bosishi kerak."
        )


async def cmd_juftim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    pair = active_pair(user.id)
    if not pair:
        await msg.reply_text("Siz bo‘ydoqsiz 💔")
        return

    partner_id = pair[2] if pair[1] == user.id else pair[1]
    try:
        started = datetime.fromisoformat(pair[4])
        duration = datetime.now() - started
        days = max(0, duration.days)
        since = started.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        days, since = 0, "—"

    await msg.reply_text(
        f"💞 <b>Juftingiz:</b> {person_name(partner_id)}\n"
        f"📅 Birga bo‘lgan vaqt: {days} kun\n"
        f"🗓 Juft bo‘lgan sana: {since}"
    )


async def cmd_juftliklar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message

    if not chat or not msg:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text("ℹ️ /juftliklar buyrug‘ini guruhda ishlating.")
        return

    rows = db().execute(
        """
        SELECT user1_id, user2_id, started_at
        FROM pairs
        WHERE status='active'
        ORDER BY started_at
        """
    ).fetchall()

    lines = ["💞 <b>Guruh juftliklari</b>\n"]
    count = 0

    for row in rows:
        user1_id, user2_id = row[0], row[1]
        present = False

        for uid in (user1_id, user2_id):
            try:
                member = await context.bot.get_chat_member(chat.id, uid)
                if member.status not in ("left", "kicked"):
                    present = True
                    break
            except TelegramError:
                continue

        if present:
            count += 1
            lines.append(
                f"{count}. {person_name(user1_id)} ❤️ {person_name(user2_id)}"
            )

    if count == 0:
        await msg.reply_text("💔 Bu guruh a’zolari orasida faol juftlik topilmadi.")
        return

    await msg.reply_text("\n".join(lines))

async def cb_relationship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        return
    data = q.data or ""
    uid = q.from_user.id
    c = db()

    if data.startswith("family:consent:"):
        parts = data.split(":")
        answer, rid = parts[2], int(parts[3])
        row = c.execute(
            "SELECT requester_id,partner_id,pair_id,gender,child_name,status FROM child_requests WHERE id=?",
            (rid,),
        ).fetchone()
        if not row or row[1] != uid or row[5] != "pending":
            await q.answer("Bu so‘rov eskirgan yoki sizga tegishli emas.", show_alert=True)
            return
        requester, partner, pair_id, child_gender, child_name, _status = row
        pair = active_pair(uid)
        if not pair or pair[0] != pair_id or {pair[1], pair[2]} != {requester, partner}:
            with c:
                c.execute("UPDATE child_requests SET status='cancelled' WHERE id=?", (rid,))
            await q.answer("Juftlik faol emas.", show_alert=True)
            return
        if answer == "no":
            with c:
                c.execute("UPDATE child_requests SET status='rejected' WHERE id=?", (rid,))
            try:
                await context.bot.send_message(requester, family_text(requester, "rejected"))
            except TelegramError:
                pass
            await q.answer("Rad etildi.")
            await q.edit_message_text("❌ So‘rov rad etildi.")
            return
        existing_children = family_child_count(pair_id)
        if existing_children >= 5:
            await q.answer(family_text(uid, "max"), show_alert=True)
            return
        cost = CHILD_COSTS[min(existing_children, 4)]
        wallet_row = c.execute("SELECT money FROM user_wallet WHERE user_id=?", (requester,)).fetchone()
        balance = int(wallet_row[0] or 0) if wallet_row else 0
        if balance < cost:
            try:
                await context.bot.send_message(
                    requester,
                    f"💸 Farzand uchun {cost:,} pul kerak. Balansingiz: {balance:,}. Pul yetarli emas."
                )
            except TelegramError:
                pass
            await q.answer("Ariza uchun mablag‘ yetarli emas.", show_alert=True)
            return
        from datetime import timedelta
        immediate_delivery = (
            requester in CAREER_OWNER_IDS or partner in CAREER_OWNER_IDS
            or panel_has_permission(requester, "child_instant")
            or panel_has_permission(partner, "child_instant")
        )
        due = (datetime.now() if immediate_delivery else datetime.now() + timedelta(hours=48)).isoformat(timespec="seconds")
        debit_failed = False
        request_updated = False
        with c:
            if cost:
                debit = c.execute(
                    "UPDATE user_wallet SET money=money-? WHERE user_id=? AND money>=?",
                    (cost, requester, cost),
                )
                debit_failed = debit.rowcount != 1
            if not debit_failed:
                updated = c.execute(
                    "UPDATE child_requests SET status='approved',due_at=? WHERE id=? AND status='pending'",
                    (due, rid),
                )
                request_updated = updated.rowcount == 1
                if not request_updated and cost:
                    c.execute(
                        "UPDATE user_wallet SET money=money+? WHERE user_id=?",
                        (cost, requester),
                    )
        if debit_failed:
            await q.answer("Ariza uchun mablag‘ yetarli emas.", show_alert=True)
            return
        if not request_updated:
            await q.answer("So‘rov avval qayta ishlangan.", show_alert=True)
            return
        if cost:
            await log_money_event(
                context.bot,
                "👶 <b>FARZAND UCHUN TO‘LOV</b>\n"
                f"To‘lovchi: {person_name(requester)} (ID: <code>{requester}</code>)\n"
                f"Jufti: {person_name(partner)} (ID: <code>{partner}</code>)\n"
                f"Narx: <b>{cost}$</b>\nFarzand: {escape(child_name)} — {escape(child_gender_label(requester, child_gender))}"
            )
        for pid in (requester, partner):
            try:
                await context.bot.send_message(pid, family_text(pid, "approved_now" if immediate_delivery else "approved"))
            except TelegramError:
                pass
        if not immediate_delivery:
            await notify_owners_child_request(context.bot, rid, requester, partner, child_name, child_gender, due, cost)
        await q.answer("Rozilik qabul qilindi.")
        await q.edit_message_text("✅ Rozilik berildi. Farzand kutishsiz yetkaziladi." if immediate_delivery else "✅ Rozilik berildi. Farzand 48 soat ichida yetkaziladi.")
        return

    if data.startswith("family:far:"):
        if uid not in CAREER_OWNER_IDS:
            await q.answer("Faqat bot egalari uchun.", show_alert=True)
            return
        rid = int(data.rsplit(":", 1)[1])
        n = child_deliver_now(rid)
        await q.answer("⚡ Farzand hozir yetkaziladi!" if n else "Bu so‘rov allaqachon yetkazilgan yoki bekor qilingan.", show_alert=not n)
        if n:
            try:
                await q.edit_message_text(q.message.text_html + "\n\n⚡ <b>Owner tomonidan darhol yetkazildi.</b>")
            except TelegramError:
                pass
        return

    if data.startswith("rel:gender:"):
        gender = data.rsplit(":", 1)[1]
        if gender not in ("male", "female"):
            await q.answer("Noto‘g‘ri tanlov.", show_alert=True)
            return
        with c:
            c.execute(
                """INSERT INTO user_gender(user_id, gender, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                   gender=excluded.gender, updated_at=excluded.updated_at""",
                (uid, gender, datetime.now().isoformat(timespec="seconds")),
            )
        await q.answer("Tanlov saqlandi!")
        await q.edit_message_text("✅ Jinsingiz saqlandi. Davom etish uchun /start bosing.")
        return

    if data.startswith("rel:menu:"):
        action = data.rsplit(":", 1)[1]
        if action == "pair":
            await q.answer()
            await q.edit_message_text(
                "💞 Juftlashish uchun guruhda kerakli odamning xabariga javob berib /juft yuboring.\n"
                "U rozi bo‘lsa, ariza bot egalariga yuboriladi."
            )
            return
        if action not in ("divorce", "quit"):
            await q.answer()
            return
        if action == "divorce" and not active_pair(uid):
            await q.answer("Sizda hozir juft yo‘q.", show_alert=True)
            return
        if action == "divorce":
            # Avval oqibatlar ko'rsatiladi; farzand bo'lsa — kim bilan qolishi tanlanadi.
            pair = active_pair(uid)
            await q.answer()
            await q.edit_message_text(
                divorce_terms_text(pair) + "\n\n" + (
                    "👶 Farzandlar kim bilan qolsin? Tanlovingiz juftingizga yuboriladi — u rozi bo‘lsa, shunday bo‘ladi."
                    if divorce_kids(pair[0]) else "Ajrashish so‘rovini yuborasizmi?"
                ),
                reply_markup=divorce_choice_kb(pair, uid),
            )
            return
        if action == "quit":
            row = c.execute(
                "SELECT profession_id FROM users WHERE user_id=?", (uid,)
            ).fetchone()
            if not row or not row[0]:
                await q.answer("Sizda tanlangan kasb yo‘q.", show_alert=True)
                return
        kind = "divorce" if action == "divorce" else "quit_job"
        target_id = None
        if action == "divorce":
            pair = active_pair(uid)
            target_id = pair[2] if pair[1] == uid else pair[1]
        rid = await create_rel_request(
            context.application, kind, uid, target_id=target_id
        )
        await q.answer()
        if not rid:
            text = "⏳ Sizda bu turdagi ariza allaqachon kutilmoqda."
        elif kind == "divorce":
            text = "💌 Ajrashish so‘rovi juftingizga shaxsiy xabarda yuborildi. Avval uning roziligi kerak."
        else:
            text = "⏳ Arizangiz bot egalariga yuborildi. Ulardan biri tasdiqlashi kerak."
        await q.edit_message_text(text)
        return

    if data == "rel:divcancel":
        await q.answer()
        await q.edit_message_text("❎ Ajrashish bekor qilindi.")
        return

    if data.startswith("rel:divgo:"):
        pair = active_pair(uid)
        if not pair:
            await q.answer("Sizda hozir juft yo‘q.", show_alert=True)
            return
        custody_id = int(data.rsplit(":", 1)[1])
        has_kids = bool(divorce_kids(pair[0]))
        if (has_kids and custody_id not in (pair[1], pair[2])) or (not has_kids and custody_id):
            await q.answer("Noto‘g‘ri tanlov.", show_alert=True)
            return
        target_id = pair[2] if pair[1] == uid else pair[1]
        rid = await create_rel_request(
            context.application, "divorce", uid, target_id=target_id, custody_id=custody_id or None
        )
        await q.answer()
        await q.edit_message_text(
            "💌 Ajrashish so‘rovi juftingizga shaxsiy xabarda yuborildi. Avval uning roziligi kerak."
            if rid else "⏳ Sizda bu turdagi ariza allaqachon kutilmoqda."
        )
        return

    if data.startswith("rel:divorce:"):
        parts = data.split(":")
        answer, rid = parts[2], int(parts[3])
        row = c.execute(
            """SELECT requester_id, target_id, status
               FROM pair_requests
               WHERE id=? AND request_type='divorce'""",
            (rid,),
        ).fetchone()

        if not row or row[1] != uid or row[2] != "partner_consent":
            await q.answer("Bu so‘rov eskirgan yoki sizga tegishli emas.",
                           show_alert=True)
            return

        requester, target, _ = row

        if answer == "no":
            with c:
                c.execute(
                    "UPDATE pair_requests SET status='rejected' "
                    "WHERE id=? AND status='partner_consent'",
                    (rid,),
                )
            try:
                await context.bot.send_message(
                    requester, "❌ Juftingiz ajrashishga rozilik bermadi."
                )
            except TelegramError:
                pass
            await q.answer("Rad etildi.")
            await q.edit_message_text("❌ Ajrashish so‘rovini rad etdingiz.")
            return

        pair = active_pair(uid)
        requester_pair = active_pair(requester)
        if (not pair or not requester_pair
                or pair[0] != requester_pair[0]
                or {pair[1], pair[2]} != {uid, requester}):
            with c:
                c.execute(
                    "UPDATE pair_requests SET status='rejected' WHERE id=?",
                    (rid,),
                )
            await q.answer("Faol juftlik topilmadi.", show_alert=True)
            await q.edit_message_text("So‘rov bekor qilindi: faol juftlik topilmadi.")
            return

        with c:
            c.execute(
                "UPDATE pair_requests SET status='pending' "
                "WHERE id=? AND status='partner_consent'",
                (rid,),
            )

        try:
            await context.bot.send_message(
                requester,
                "✅ Juftingiz ajrashishga rozilik berdi. Endi bot egalari qaror qiladi."
            )
        except TelegramError:
            pass
        await q.answer("Rozilik saqlandi.")
        await q.edit_message_text(
            "✅ Rozilik berdingiz. Ariza bot egalariga yuborildi."
        )
        await notify_pair_owners(
            context.application, rid, "💔 Ajrashish arizasi — juft rozilik berdi"
        )
        return

    if data.startswith("rel:proposal:"):
        parts = data.split(":")
        answer, rid = parts[2], int(parts[3])
        row = c.execute(
            """SELECT requester_id, target_id, group_id, status
               FROM pair_requests WHERE id=? AND request_type='pair'""",
            (rid,),
        ).fetchone()
        if not row or row[1] != uid or row[3] != "proposal":
            await q.answer("Bu taklif eskirgan.", show_alert=True)
            return
        is_random = (c.execute("SELECT random FROM pair_requests WHERE id=?", (rid,)).fetchone() or [0])[0] \
            if "random" in {r[1] for r in c.execute("PRAGMA table_info(pair_requests)")} else 0
        if answer == "no":
            with c:
                c.execute("UPDATE pair_requests SET status='rejected' WHERE id=?", (rid,))
            await q.answer("Taklif rad etildi.")
            await q.edit_message_text("❌ Taklif rad etildi.")
            if is_random:
                try:
                    await context.bot.send_message(row[0], f"💔 {person_name(uid)} juftlik taklifingizni rad etdi.\n"
                                                           "💍 Web app → Oila bo‘limida yana juft qidirishingiz mumkin.")
                except TelegramError:
                    pass
            return
        if active_pair(uid) or active_pair(row[0]):
            await q.answer("Sizlardan biri allaqachon juftlikda.", show_alert=True)
            return
        with c:
            c.execute(
                "UPDATE pair_requests SET status='pending' WHERE id=? AND status='proposal'",
                (rid,),
            )
        await q.answer("Roziligingiz saqlandi.")
        await q.edit_message_text("✅ Roziligingiz saqlandi. Endi bot egalari tasdig‘i kutilmoqda.")
        if is_random:
            try:
                await context.bot.send_message(row[0], f"💞 {person_name(uid)} juftlik taklifingizga rozi bo‘ldi!\n"
                                                       "⏳ Endi bot egalari tasdig‘i kutilmoqda.")
            except TelegramError:
                pass
        await notify_pair_owners(
            context.application, rid, "💞 Juftlashish arizasi"
        )
        return

    if data.startswith("rel:owner:"):
        if uid not in CAREER_OWNER_IDS:
            await q.answer("Bu amal faqat bot egalari uchun.", show_alert=True)
            return
        parts = data.split(":")
        answer, rid = parts[2], int(parts[3])
        row = c.execute(
            """SELECT request_type, requester_id, target_id, group_id, status
               FROM pair_requests WHERE id=?""",
            (rid,),
        ).fetchone()
        if not row or row[4] != "pending":
            await q.answer("Ariza ko‘rib chiqilgan yoki topilmadi.", show_alert=True)
            return

        kind, requester, target, group_id, _ = row
        if answer == "no":
            with c:
                c.execute(
                    """UPDATE pair_requests SET status='rejected',
                       decided_by=?, decided_at=? WHERE id=? AND status='pending'""",
                    (uid, datetime.now().isoformat(timespec="seconds"), rid),
                )
            try:
                await context.bot.send_message(requester, f"❌ {kind} arizangiz rad etildi.")
            except TelegramError:
                pass
            await q.answer("Ariza rad etildi.")
            await q.edit_message_text(f"❌ {rid}-ariza rad etildi.")
            return

        now = datetime.now().isoformat(timespec="seconds")
        if kind == "pair":
            if not target or active_pair(requester) or active_pair(target):
                await q.answer("Ishtirokchilardan biri allaqachon juftlikda.", show_alert=True)
                return
            with c:
                c.execute(
                    """INSERT INTO pairs
                       (user1_id, user2_id, group_id, started_at, status)
                       VALUES (?, ?, ?, ?, 'active')""",
                    (requester, target, group_id or 0, now),
                )
        elif kind == "divorce":
            pair = active_pair(requester)
            if (
                not pair
                or not target
                or {pair[1], pair[2]} != {requester, target}
            ):
                await q.answer(
                    "Faol juftlik mos kelmadi. Ariza tasdiqlanmadi.",
                    show_alert=True,
                )
                return
            custody = c.execute("SELECT custody_id FROM pair_requests WHERE id=?", (rid,)).fetchone()[0]
            with c:
                c.execute(
                    "UPDATE pairs SET status='ended', ended_at=? WHERE id=? AND status='active'",
                    (now, pair[0]),
                )
                settlement = divorce_settle(c, pair, custody)
        elif kind == "quit_job":
            with c:
                c.execute(
                    "UPDATE users SET profession_id=NULL, profession_selected=0 WHERE user_id=?",
                    (requester,),
                )

        with c:
            c.execute(
                """UPDATE pair_requests SET status='approved',
                   decided_by=?, decided_at=?
                   WHERE id=? AND status='pending'""",
                (uid, now, rid),
            )
            if kind == "divorce" and target:
                c.execute(
                    """UPDATE pair_requests
                       SET status='approved', decided_by=?, decided_at=?
                       WHERE request_type='divorce'
                         AND status IN ('pending', 'partner_consent')
                         AND (
                           (requester_id=? AND target_id=?)
                           OR (requester_id=? AND target_id=?)
                         )""",
                    (uid, now, requester, target, target, requester),
                )
        try:
            await context.bot.send_message(
                requester, f"✅ Arizangiz tasdiqlandi: {kind}."
            )
        except TelegramError:
            pass
        if kind == "pair" and target:
            try:
                await context.bot.send_message(
                    target, "💞 Juftlik arizasi tasdiqlandi! Endi siz juftlikdasiz."
                )
            except TelegramError:
                pass
        elif kind == "divorce" and target:
            try:
                await context.bot.send_message(target, "💔 Juftlik arizasi tasdiqlandi.")
            except TelegramError:
                pass
        if kind == "divorce":
            await divorce_notify(context.bot, settlement)
        await q.answer("Tasdiqlandi!")
        await q.edit_message_text(f"✅ {rid}-ariza tasdiqlandi.")

        if kind == "divorce":
            for owner_id in CAREER_OWNER_IDS:
                if owner_id == uid:
                    continue
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=f"✅ <b>Ajrashish arizasi tasdiqlandi</b>\n"
                             f"Ariza raqami: {rid}\n"
                             f"Tasdiqlagan owner ID: {uid}",
                    )
                except TelegramError as e:
                    logger.warning(
                        "Tasdiq xabari egaga yuborilmadi (%s): %s",
                        owner_id, e
                    )
        return

    await q.answer()


async def cmd_missiyalar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    if not chat or not msg or not user:
        return

    save_user(user)
    ensure_daily_missions()

    c = db()
    row = c.execute(
        "SELECT profession_id, profession_selected FROM users WHERE user_id=?",
        (user.id,)
    ).fetchone()

    if not row or not row[1] or not row[0]:
        await msg.reply_text(
            "❌ Avval tug‘ilgan sanangizni tasdiqlab, kasbingizni tanlang.\n"
            "▶️ /start"
        )
        return

    profession_id = row[0]

    lang = LANG_CACHE.get(chat.id, DEFAULT_LANG)
    lang_col = {
        "uz": "title_uz",
        "eng": "title_eng",
        "ru": "title_ru",
        "kz": "title_kz",
    }.get(lang, "title_uz")

    missions = c.execute(
        f"""
        SELECT id, mission_key, target, reward_xp, reward_money,
               {lang_col}
        FROM daily_missions
        WHERE profession_id=? AND active_date=?
        ORDER BY id
        """,
        (profession_id, __import__("datetime").date.today().isoformat()),
    ).fetchall()

    titles = {
        "uz": ("🎯 <b>BUGUNGI MISSIYALAR</b>", "💼 Kasb", "⭐ XP", "💵 Pul"),
        "eng": ("🎯 <b>TODAY'S MISSIONS</b>", "💼 Profession", "⭐ XP", "💵 Money"),
        "ru": ("🎯 <b>МИССИИ НА СЕГОДНЯ</b>", "💼 Профессия", "⭐ XP", "💵 Деньги"),
        "kz": ("🎯 <b>БҮГІНГІ МИССИЯЛАР</b>", "💼 Мамандық", "⭐ XP", "💵 Ақша"),
    }

    header, prof_label, xp_label, money_label = titles.get(lang, titles["uz"])

    lines = [
        header,
        "━━━━━━━━━━━━━━",
        f"{prof_label}: <b>{profession_name(profession_id, chat.id)}</b>",
        "",
    ]

    for i, (mission_id, key, target, reward_xp, reward_money, title) in enumerate(missions, 1):
        progress_row = c.execute(
            "SELECT progress, completed FROM mission_progress "
            "WHERE user_id=? AND mission_id=?",
            (user.id, mission_id),
        ).fetchone()

        progress = progress_row[0] if progress_row else 0
        completed = bool(progress_row and progress_row[1])

        if completed:
            status = "✅"
        else:
            status = f"⏳ {progress}/{target}"

        lines.append(
            f"{i}. {title}\n"
            f"   {status}  {xp_label}: +{reward_xp}  {money_label}: +{reward_money}"
        )

    await msg.reply_text("\n".join(lines))

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if chat and msg:
        await msg.reply_text(t(chat.id, "rules"))


async def cmd_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return
    is_owner = update.effective_user and update.effective_user.id in CAREER_OWNER_IDS
    if not WEBAPP_URL:
        extra = ("\n\n🛠 <b>Egalarga:</b> Railway → Variables ga <code>WEBAPP_URL=https://&lt;domeningiz&gt;</code> "
                 "qo‘shing (yoki <code>RAILWAY_PUBLIC_DOMAIN</code>) va qayta deploy qiling.") if is_owner else ""
        await msg.reply_text("🌐 Web app hali sozlanmagan (domen yo‘q)." + extra)
        return
    url = WEBAPP_URL + "/app"
    if not url.startswith("https://"):
        await msg.reply_text(
            f"⚠️ Web app manzili HTTPS bo‘lishi kerak. Hozirgi: <code>{escape(url)}</code>\n"
            "Egalar: <code>WEBAPP_URL=https://...</code> qilib tuzating." if is_owner
            else "⚠️ Web app manzili noto‘g‘ri sozlangan.")
        return
    if chat.type == ChatType.PRIVATE:
        try:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Ilovani ochish", web_app=WebAppInfo(url))]])
            await msg.reply_text("🎮 <b>Empire Stats</b> — ilovani oching 👇", reply_markup=kb)
        except BadRequest as e:
            await msg.reply_text(
                f"⚠️ Tugma ochilmadi: {escape(str(e))}\n🔗 Manzil: <code>{escape(url)}</code>" if is_owner
                else "⚠️ Ilovani ochib bo‘lmadi. Egaga xabar bering.")
    else:
        try:
            bot_un = (await context.bot.get_me()).username
        except TelegramError:
            bot_un = ""
        link = f"https://t.me/{bot_un}" if bot_un else url
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Shaxsiy chatda ochish", url=link)]])
        await msg.reply_text("🎮 Ilovani shaxsiy chatda oching 👇 (menyu tugmasi orqali ham).", reply_markup=kb)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return
    text = t(chat.id, "help")
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        text += "\n\n" + gh_t(chat.id, "admin_help")
    await msg.reply_text(text)


# ───────────────────────────── Til tanlash ─────────────────────────────


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    buttons = [
        InlineKeyboardButton(LANGS[code]["flag_name"], callback_data=f"lang:{code}")
        for code in LANG_ORDER
    ]
    kb = InlineKeyboardMarkup([buttons[:2], buttons[2:]])
    await msg.reply_text(t(chat.id, "lang_title"), reply_markup=kb)


async def cb_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat = q.message.chat
    code = q.data.split(":", 1)[1]

    if code not in LANGS:
        await q.answer()
        return

    # Guruhda tilni faqat adminlar o'zgartira oladi
    if chat.type != ChatType.PRIVATE and not await is_admin(context.bot, chat.id, q.from_user.id):
        await q.answer(t(chat.id, "lang_admin_only"), show_alert=True)
        return

    set_group_lang(chat.id, code)
    await q.answer()
    await edit(context.bot, chat.id, q.message.message_id, t(chat.id, "lang_set"))


# ───────────────────────────── O'yin menyusi ─────────────────────────────


async def cb_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    msg = q.message
    chat_id = msg.chat.id
    kind = q.data.split(":", 1)[1]
    user = q.from_user

    if msg.chat.type == ChatType.PRIVATE:
        await q.answer(t(chat_id, "use_group"), show_alert=True)
        return

    # Majburiy obuna: o'yin boshlash/kirish uchun kanalga a'zo bo'lish shart.
    if kind in ("number", "rsp", "xo", "memory", "crash", "croc", "frog", "casino"):
        if await fsub_block_cb(q, context):
            return

    # Qurbaqa GAMES'ni band qilmaydi — guruhda boshqa o'yin ketayotgan bo'lsa ham ochiladi.
    if kind == "frog":
        await q.answer()
        await edit(context.bot, chat_id, msg.message_id,
                   frog_t(chat_id, "lobby", min=FROG_MIN_BET), frog_lobby_kb(chat_id))
        return

    game = GAMES.get(chat_id)
    if game:
        await q.answer(
            t(chat_id, "busy_alert", game=t(chat_id, "btn_" + game["type"])),
            show_alert=True,
        )
        return

    await q.answer()

    if kind == "menu":
        await context.bot.send_message(
            chat_id, t(chat_id, "menu_title"), reply_markup=menu_kb(chat_id)
        )
        return

    if kind == "casino":
        await edit(context.bot, chat_id, msg.message_id, casino_t(chat_id, "title"), casino_kb(chat_id))
        return

    if kind == "back":
        await edit(context.bot, chat_id, msg.message_id, t(chat_id, "menu_title"), menu_kb(chat_id))
        return

    save_user(user)
    name = uname(user)
    app = context.application

    if kind == "number":
        game = new_game(
            chat_id, "number", user.id,
            number=random.randint(MIN_NUMBER, MAX_NUMBER),
            lo=MIN_NUMBER, hi=MAX_NUMBER,
            attempts=0, tried=set(), players=set(),
        )
        await edit(
            context.bot, chat_id, msg.message_id,
            t(
                chat_id, "number_started",
                min=MIN_NUMBER, max=MAX_NUMBER, points=NUMBER_WIN_PTS,
                fast=FAST_ATTEMPTS, bonus=NUMBER_BONUS_PTS, minutes=NUMBER_TTL // 60,
            ),
        )
        arm(app, chat_id, game, NUMBER_TTL)

    elif kind == "rsp":
        game = new_game(
            chat_id, "rsp", user.id,
            state="setup", msg_id=msg.message_id, count=0,
            names={user.id: name}, choices={},
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("👥 2", callback_data="rc:2"),
            InlineKeyboardButton("👥 3", callback_data="rc:3"),
            InlineKeyboardButton("👥 5", callback_data="rc:5"),
        ]])
        await edit(context.bot, chat_id, msg.message_id, t(chat_id, "rsp_setup"), kb)
        arm(app, chat_id, game, RSP_SETUP_TTL)

    elif kind == "xo":
        game = new_game(
            chat_id, "xo", user.id,
            state="lobby", msg_id=msg.message_id,
            names={user.id: name}, board=[""] * 9, seat={}, turn="X",
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(t(chat_id, "btn_join"), callback_data="xj")
        ]])
        await edit(context.bot, chat_id, msg.message_id, t(chat_id, "xo_lobby", owner=name), kb)
        arm(app, chat_id, game, XO_LOBBY_TTL)

    elif kind == "memory":
        game = new_game(
            chat_id, "memory", user.id,
            state="setup", msg_id=msg.message_id,
            names={user.id: name},
        )
        await edit(
            context.bot, chat_id, msg.message_id,
            memory_t(chat_id, "choose"), memory_category_kb()
        )
        arm(app, chat_id, game, MEMORY_SETUP_TTL)

    elif kind == "crash":
        if not CRASH_ENABLED:
            await context.bot.send_message(chat_id, "⛔ Crash o‘yini bot egasi tomonidan vaqtincha o‘chirib qo‘yilgan.")
            return
        if not crash_group_allowed(chat_id):
            await context.bot.send_message(chat_id, "⛔ Bu guruh Crash uchun ulanmagan. Bot egasidan guruhni ulashni so‘rang.")
            return
        game = new_game(
            chat_id, "crash", user.id,
            state="lobby", msg_id=msg.message_id,
            players={}, dropped=[], cp=None, t0=None, t_crash=None,
            charged=False, settled=False,
        )
        await edit(
            context.bot, chat_id, msg.message_id,
            cr_t(chat_id, "lobby", min=CRASH_MIN_BET, sec=CRASH_COUNTDOWN),
            crash_kb(chat_id, game),
        )
        arm(app, chat_id, game, CRASH_LOBBY_TTL)

    elif kind == "croc":
        game = new_game(
            chat_id, "croc", user.id,
            state="play", msg_id=msg.message_id,
            host_id=user.id, host_name=name,
            round=1, finished=False, word=None, used=set(),
        )
        game["word"] = croc_pick_word(chat_id, game)
        await edit(
            context.bot, chat_id, msg.message_id,
            croc_round_text(chat_id, game), croc_kb(chat_id),
        )
        arm(app, chat_id, game, CROC_TTL)



# ───────────────────────────── 🧠 Juftini top ─────────────────────────────

MEMORY_SETUP_TTL = 120
MEMORY_LOBBY_TTL = 180
MEMORY_GAME_TTL = 900
MEMORY_HIDE_DELAY = 0.9

MEMORY_EMOJI_CATEGORIES = {
    "animals": "🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🙈 🙉 🙊 🐔 🐧 🐦 🐤 🦆 🦅 🦉 🦇 🐺 🐗 🐴 🦄 🐝 🪲 🐞 🦋 🐌 🐢 🐍 🦎 🦂 🦀 🦑 🐙 🦐 🐠 🐟 🐬 🐳 🦈 🐊 🐘 🦒 🦓 🦍 🦛 🦘 🐪 🐫 🦙 🦌 🐿️ 🦔 🦚 🦜 🦢 🦩 🦃 🪿 🦦 🦥 🦨 🦡 🦫 🦬 🦣 🐄 🐎 🐑 🐐 🐕 🐈 🐓 🦮".split(),
    "food": "🍎 🍏 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍈 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🍆 🥑 🥦 🥬 🥒 🌶️ 🌽 🥕 🧄 🧅 🥔 🍠 🥐 🥯 🍞 🥖 🥨 🧀 🥚 🍳 🧈 🥞 🧇 🥓 🍗 🍖 🌭 🍔 🍟 🍕 🥪 🌮 🌯 🥙 🧆 🍝 🍜 🍲 🍛 🍣 🍱 🥟 🍤 🍙 🍚 🍘 🍥 🥮 🍢 🍡 🍧 🍨 🍦 🥧 🧁 🍰 🎂 🍮 🍭 🍬 🍫 🍿 🍩 🍪 🥛 🧋 ☕ 🍵 🧃 🥤 🧉 🥗 🥘 🫕 🥫 🥜 🌰 🍯 🥠 🥡".split(),
    "faces": "😀 😃 😄 😁 😆 😅 🤣 😂 🙂 🙃 🫠 😉 😊 😇 🥰 😍 🤩 😘 😗 ☺️ 😚 😙 🥲 😋 😛 😜 🤪 😝 🤑 🤗 🤭 🫢 🫣 🤫 🤔 🫡 🤐 🤨 😐 😑 😶 🫥 😏 😒 🙄 😬 😮‍💨 🤥 🫨 😌 😔 😪 🤤 😴 😷 🤒 🤕 🤢 🤮 🥵 🥶 🥴 😵 🤯 🤠 🥳 🥸 😎 🤓 🧐 😕 🫤 😟 🙁 ☹️ 😮 😯 😲 😳 🥺 🥹 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 😫 🥱 😤 😡 😠 🤬 😈 👿 💀 ☠️ 💩 🤡 👻 👽 🤖 🎃".split(),
}

MEMORY_TEXT = {
    "uz": {
        "btn": "🧠 Juftini top",
        "choose": "🧠 <b>Juftini top</b>\n\nMaydonni tanlang:",
        "lobby": "🧠 <b>Juftini top</b>\n\n👥 O‘yinchilar: {players}/2\n\n{names}\n\nIkkinchi o‘yinchini kuting 👇",
        "join": "🙋 Qo‘shilish",
        "already": "Siz allaqachon o‘yindasiz.",
        "full": "O‘yinchilar to‘ldi.",
        "turn": "🎯 Navbat: <b>{name}</b>\n🏆 {a}: {ap} juft\n🏆 {b}: {bp} juft",
        "not_turn": "⏳ Hozir navbat boshqa o‘yinchida.",
        "one": "Avval birinchi katakni tanlang.",
        "same": "Boshqa katakni tanlang.",
        "match": "🎉 <b>{name}</b> juftlikni topdi! +1 juft. Yana yuradi.",
        "miss": "❌ Juftlik topilmadi. Navbat <b>{name}</b>ga.",
        "result": "🧠 <b>JUFTINI TOP — NATIJA</b>\n\n🏆 {a}: <b>{ap}</b> juft\n🏆 {b}: <b>{bp}</b> juft\n\n{result}",
        "winner": "👑 G‘olib: <b>{name}</b>!",
        "draw": "🤝 Durang!",
        "waiting": "⏳ Ikkinchi o‘yinchini kuting.",
    },
    "eng": {
        "btn": "🧠 Find the Pair",
        "choose": "🧠 <b>Find the Pair</b>\n\nChoose the board:",
        "lobby": "🧠 <b>Find the Pair</b>\n\n👥 Players: {players}/2\n\n{names}\n\nWaiting for the second player 👇",
        "join": "🙋 Join",
        "already": "You are already in the game.",
        "full": "The game is full.",
        "turn": "🎯 Turn: <b>{name}</b>\n🏆 {a}: {ap} pairs\n🏆 {b}: {bp} pairs",
        "not_turn": "⏳ It is the other player's turn.",
        "one": "Choose the first cell first.",
        "same": "Choose another cell.",
        "match": "🎉 <b>{name}</b> found a pair! +1 pair. Play again.",
        "miss": "❌ No pair. Turn goes to <b>{name}</b>.",
        "result": "🧠 <b>FIND THE PAIR — RESULT</b>\n\n🏆 {a}: <b>{ap}</b> pairs\n🏆 {b}: <b>{bp}</b> pairs\n\n{result}",
        "winner": "👑 Winner: <b>{name}</b>!",
        "draw": "🤝 Draw!",
        "waiting": "⏳ Waiting for the second player.",
    },
    "ru": {
        "btn": "🧠 Найди пару",
        "choose": "🧠 <b>Найди пару</b>\n\nВыберите поле:",
        "lobby": "🧠 <b>Найди пару</b>\n\n👥 Игроки: {players}/2\n\n{names}\n\nЖдём второго игрока 👇",
        "join": "🙋 Войти",
        "already": "Вы уже участвуете.",
        "full": "Игра заполнена.",
        "turn": "🎯 Ход: <b>{name}</b>\n🏆 {a}: {ap} пар\n🏆 {b}: {bp} пар",
        "not_turn": "⏳ Сейчас ход другого игрока.",
        "one": "Сначала выберите первую клетку.",
        "same": "Выберите другую клетку.",
        "match": "🎉 <b>{name}</b> нашёл пару! +1 пара. Ход продолжается.",
        "miss": "❌ Пара не найдена. Ход переходит к <b>{name}</b>.",
        "result": "🧠 <b>НАЙДИ ПАРУ — РЕЗУЛЬТАТ</b>\n\n🏆 {a}: <b>{ap}</b> пар\n🏆 {b}: <b>{bp}</b> пар\n\n{result}",
        "winner": "👑 Победитель: <b>{name}</b>!",
        "draw": "🤝 Ничья!",
        "waiting": "⏳ Ждём второго игрока.",
    },
    "kz": {
        "btn": "🧠 Жұбын тап",
        "choose": "🧠 <b>Жұбын тап</b>\n\nӨрісті таңдаңыз:",
        "lobby": "🧠 <b>Жұбын тап</b>\n\n👥 Ойыншылар: {players}/2\n\n{names}\n\nЕкінші ойыншы күтілуде 👇",
        "join": "🙋 Қосылу",
        "already": "Сіз ойынға қатысып жатырсыз.",
        "full": "Ойыншылар толды.",
        "turn": "🎯 Кезек: <b>{name}</b>\n🏆 {a}: {ap} жұп\n🏆 {b}: {bp} жұп",
        "not_turn": "⏳ Қазір басқа ойыншының кезегі.",
        "one": "Алдымен бірінші ұяшықты таңдаңыз.",
        "same": "Басқа ұяшықты таңдаңыз.",
        "match": "🎉 <b>{name}</b> жұпты тапты! +1 жұп. Кезек жалғасады.",
        "miss": "❌ Жұп табылмады. Кезек <b>{name}</b> ойыншыға өтті.",
        "result": "🧠 <b>ЖҰБЫН ТАП — НӘТИЖЕ</b>\n\n🏆 {a}: <b>{ap}</b> жұп\n🏆 {b}: <b>{bp}</b> жұп\n\n{result}",
        "winner": "👑 Жеңімпаз: <b>{name}</b>!",
        "draw": "🤝 Тең түсті!",
        "waiting": "⏳ Екінші ойыншы күтілуде.",
    },
}


def memory_t(chat_id, key, **kwargs):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    data = MEMORY_TEXT.get(lang, MEMORY_TEXT["uz"])
    return data[key].format(**kwargs)


def memory_lobby_kb(chat_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            memory_t(chat_id, "join"),
            callback_data="m:join"
        )
    ]])


def memory_category_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐾 Hayvonlar", callback_data="m:cat:animals"),
            InlineKeyboardButton("🍕 Taomlar", callback_data="m:cat:food"),
        ],
        [
            InlineKeyboardButton("😀 Yuzlar", callback_data="m:cat:faces"),
        ],
    ])


def memory_begin(game):
    game["state"] = "play"
    game["board"] = memory_make_board(game["size"], game.get("category", "animals"))
    game["revealed"] = set()
    game["locked"] = set()
    game["scores"] = {uid: 0 for uid in game["names"]}
    game["turn"] = list(game["names"])[0]
    game["first"] = None
    game["second"] = None
    game["busy"] = False


def memory_lobby_text(chat_id, game):
    names = "\n".join(
        f"🙋 {name}" for name in game["names"].values()
    )
    return memory_t(
        chat_id, "lobby",
        players=len(game["names"]),
        names=names,
    )


def memory_make_board(size, category="animals"):
    pairs = (size * size) // 2
    pool = MEMORY_EMOJI_CATEGORIES.get(
        category, MEMORY_EMOJI_CATEGORIES["animals"]
    )
    emojis = random.sample(pool, pairs)
    values = emojis * 2
    random.shuffle(values)
    return values

def memory_keyboard(game):
    size = game["size"]
    board = game["board"]
    revealed = game["revealed"]
    locked = game["locked"]
    first = game.get("first")
    second = game.get("second")
    rows = []

    for r in range(size):
        row = []
        for c in range(size):
            i = r * size + c

            if i in locked or i in revealed or i == first or i == second:
                label = board[i]
            else:
                label = "⬜"

            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"m:cell:{i}"
                )
            )
        rows.append(row)

    return InlineKeyboardMarkup(rows)


def memory_text(chat_id, game):
    ids = list(game["names"])
    a = ids[0]
    b = ids[1]

    return memory_t(
        chat_id,
        "turn",
        name=game["names"][game["turn"]],
        a=game["names"][a],
        b=game["names"][b],
        ap=game["scores"].get(a, 0),
        bp=game["scores"].get(b, 0),
    )


async def memory_finish(context, chat_id, game):
    ids = list(game["names"])
    a, b = ids[0], ids[1]
    ap = game["scores"].get(a, 0)
    bp = game["scores"].get(b, 0)

    if ap > bp:
        winner = a
        result = memory_t(
            chat_id, "winner",
            name=game["names"][winner]
        )
        record(chat_id, winner, "win", ap)
        record(chat_id, b, "loss")
    elif bp > ap:
        winner = b
        result = memory_t(
            chat_id, "winner",
            name=game["names"][winner]
        )
        record(chat_id, winner, "win", bp)
        record(chat_id, a, "loss")
    else:
        result = memory_t(chat_id, "draw")
        record(chat_id, a, "draw")
        record(chat_id, b, "draw")

    end_game(chat_id, game)

    await edit(
        context.bot,
        chat_id,
        game["msg_id"],
        memory_t(
            chat_id, "result",
            a=game["names"][a],
            b=game["names"][b],
            ap=ap,
            bp=bp,
            result=result,
        ),
        None,
    )


async def cb_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return

    chat_id = game_key(q)
    game = GAMES.get(chat_id)

    if not game or game.get("type") != "memory":
        await _cb_memory_locked(update, context)
        return

    lock = game.setdefault("_callback_lock", asyncio.Lock())
    async with lock:
        await _cb_memory_locked(update, context)


async def _cb_memory_locked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = game_key(q)
    user = q.from_user
    data = q.data

    game = active(q, "memory")

    if not game:
        await q.answer(memory_t(chat_id, "waiting"), show_alert=True)
        return

    # Emoji kategoriyasini tanlash
    if data.startswith("m:cat:"):
        if game["state"] != "setup":
            await q.answer("Bu o'yin bosqichi tugagan.", show_alert=True)
            return

        if user.id != game["owner"]:
            await q.answer("Faqat o'yinni ochgan odam tanlay oladi.", show_alert=True)
            return

        category = data.rsplit(":", 1)[1]
        if category not in MEMORY_EMOJI_CATEGORIES:
            await q.answer("Kategoriya topilmadi.", show_alert=True)
            return

        game["category"] = category
        await q.answer()

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("4×4", callback_data="m:size:4"),
                InlineKeyboardButton("6×6", callback_data="m:size:6"),
            ]
        ])
        await edit(
            context.bot, chat_id, game["msg_id"],
            memory_t(chat_id, "choose"), kb
        )
        return

    # Maydon tanlash
    if data.startswith("m:size:"):
        if game["state"] != "setup":
            await q.answer(memory_t(chat_id, "waiting"), show_alert=True)
            return

        if user.id != game["owner"]:
            await q.answer(t(chat_id, "only_owner"), show_alert=True)
            return

        size = int(data.rsplit(":", 1)[1])

        game["size"] = size
        game["state"] = "lobby"

        await q.answer()

        # Inline o'yinda ikkinchi o'yinchi oldinroq qo'shilgan bo'lishi mumkin.
        if len(game["names"]) >= 2:
            memory_begin(game)
            await edit(
                context.bot, chat_id, game["msg_id"],
                memory_text(chat_id, game), memory_keyboard(game),
            )
            arm(context.application, chat_id, game, MEMORY_GAME_TTL)
            return

        await edit(
            context.bot,
            chat_id,
            game["msg_id"],
            memory_lobby_text(chat_id, game),
            memory_lobby_kb(chat_id),
        )
        arm(context.application, chat_id, game, MEMORY_LOBBY_TTL)
        return

    # Ikkinchi o'yinchi qo'shilishi
    if data == "m:join":
        if game["state"] != "lobby":
            await q.answer(t(chat_id, "gone"), show_alert=True)
            return

        if user.id in game["names"]:
            await q.answer(memory_t(chat_id, "already"), show_alert=True)
            return

        if len(game["names"]) >= 2:
            await q.answer(memory_t(chat_id, "full"), show_alert=True)
            return

        if await fsub_block_cb(q, context):
            return

        save_user(user)
        game["names"][user.id] = uname(user)
        await q.answer()

        if len(game["names"]) < 2:
            await edit(
                context.bot,
                chat_id,
                game["msg_id"],
                memory_lobby_text(chat_id, game),
                memory_lobby_kb(chat_id),
            )
            return

        memory_begin(game)

        await edit(
            context.bot,
            chat_id,
            game["msg_id"],
            memory_text(chat_id, game),
            memory_keyboard(game),
        )
        arm(context.application, chat_id, game, MEMORY_GAME_TTL)
        return

    # Katak
    if data.startswith("m:cell:"):
        if game["state"] != "play":
            await q.answer(t(chat_id, "gone"), show_alert=True)
            return

        if user.id not in game["names"]:
            await q.answer(t(chat_id, "not_player"), show_alert=True)
            return

        if user.id != game["turn"]:
            await q.answer(memory_t(chat_id, "not_turn"), show_alert=True)
            return

        if game.get("busy"):
            await q.answer()
            return

        idx = int(data.rsplit(":", 1)[1])

        if idx in game["locked"] or idx in game["revealed"]:
            await q.answer()
            return

        if game["first"] == idx:
            await q.answer(memory_t(chat_id, "same"), show_alert=True)
            return

        await q.answer()

        if game["first"] is None:
            game["first"] = idx

            await edit(
                context.bot,
                chat_id,
                game["msg_id"],
                memory_text(chat_id, game),
                memory_keyboard(game),
            )
            return

        game["second"] = idx
        game["busy"] = True

        await edit(
            context.bot,
            chat_id,
            game["msg_id"],
            memory_text(chat_id, game),
            memory_keyboard(game),
        )

        first = game["first"]
        second = game["second"]

        if game["board"][first] == game["board"][second]:
            await asyncio.sleep(0.25)

            game["locked"].add(first)
            game["locked"].add(second)
            game["scores"][user.id] += 1
            game["first"] = None
            game["second"] = None
            game["busy"] = False

            pairs_total = (game["size"] * game["size"]) // 2

            if len(game["locked"]) == pairs_total * 2:
                await memory_finish(context, chat_id, game)
                return

            await edit(
                context.bot,
                chat_id,
                game["msg_id"],
                memory_t(chat_id, "match", name=game["names"][user.id])
                + "\n\n" + memory_text(chat_id, game),
                memory_keyboard(game),
            )
            arm(context.application, chat_id, game, MEMORY_GAME_TTL)
            return

        # Mos kelmasa, ikkisini qisqa vaqt ko'rsatib turamiz.
        await asyncio.sleep(MEMORY_HIDE_DELAY)

        if GAMES.get(chat_id) is not game:
            return

        game["first"] = None
        game["second"] = None
        game["busy"] = False

        ids = list(game["names"])
        other = ids[0] if ids[1] == user.id else ids[1]
        game["turn"] = other

        await edit(
            context.bot,
            chat_id,
            game["msg_id"],
            memory_t(
                chat_id, "miss",
                name=game["names"][other]
            ) + "\n\n" + memory_text(chat_id, game),
            memory_keyboard(game),
        )
        arm(context.application, chat_id, game, MEMORY_GAME_TTL)
        return


# ───────────────────────────── 🐸 Qurbaqa (Casino) ─────────────────────────────
# Maydon: FROG_ROWS qator × FROG_COLS nilufar bargi. Har qatorda rejimga qarab
# 1 / 2 / 3 ta xavfli barg bor — ular har o'yinda tasodifiy joylashadi.
# Qurbaqa faqat o'zidan bitta oldingi qatordagi istalgan bargga sakraydi.
# Koeffitsiyent: RTP × (4 / xavfsiz barglar soni) ^ qadamlar — har qanday
# to'xtash strategiyasida o'rtacha qaytim RTP ga teng.
# O'yin GAMES'dan alohida saqlanadi (bitta chatda bir nechta odam o'ynay oladi).

FROG_ROWS = 5
FROG_COLS = 4
FROG_RTP = 0.97
FROG_MIN_BET = 50
FROG_STEP = 50
FROG_SETUP_TTL = 180        # qo'shilish / rejim / depozit bosqichi (soniya)
FROG_PLAY_TTL = 300         # o'yin davomida faolsizlik → avtomatik pul olish
FROG_MODES = {"easy": 1, "medium": 2, "hard": 3}   # qatordagi xavfli barglar soni
FROG_MODE_ICON = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
FROG_CELL = {"next": "🪷", "future": "🌿", "frog": "🐸", "path": "✅", "past": "〰️",
             "trap": "🌊", "hit": "💥", "safe": "🪷"}
FROG_GAMES: dict[str, dict] = {}

FROG_TEXT = {
    "uz": {
        "btn": "🐸 Qurbaqa",
        "desc": "Qurbaqani nilufar barglaridan o‘tkazing",
        "lobby": (
            "🐸 <b>QURBAQA</b>\n\n"
            "Qurbaqani nilufar barglari ustidan o‘tkazing! Har qatorda ba’zi barglar ostida xavf bor — "
            "ular har o‘yinda boshqa joyda.\n"
            "Har sakrashda koeffitsiyent oshadi, istalgan payt pulni olishingiz mumkin.\n\n"
            "💵 Minimal depozit: <b>{min}$</b>\n\n👇 O‘yinga qo‘shiling"
        ),
        "join": "🙋 O‘yinga qo‘shilish",
        "mode": (
            "🐸 <b>QURBAQA</b>\n👤 {name}\n\nRejimni tanlang:\n"
            "🟢 Oson — qatorda 1 ta xavf · oxirgi qator x{easy}\n"
            "🟡 O‘rta — qatorda 2 ta xavf · oxirgi qator x{medium}\n"
            "🔴 Qiyin — qatorda 3 ta xavf · oxirgi qator x{hard}"
        ),
        "easy": "🟢 Oson", "medium": "🟡 O‘rta", "hard": "🔴 Qiyin",
        "bet": "🐸 <b>QURBAQA</b> · {mode}\n👤 {name}\n\n💵 Depozit: <b>{bet}$</b>\n💰 Balans: {bal}$\n\nDepozitni tanlang va o‘yinni boshlang 👇",
        "start": "✅ Boshlash",
        "play": (
            "🐸 <b>QURBAQA</b> · {mode}\n👤 {name} · 💵 {bet}$\n\n"
            "⏭ Keyingi qadam: <b>x{next}</b> → {next_win}$\n"
            "💰 Hozir olsangiz: <b>x{cur}</b> → {cur_win}$\n\n"
            "👇 Oldingi qatordagi istalgan bargni tanlang"
        ),
        "shore": "🏝 Qurbaqa qirg‘oqda — birinchi qatorga sakrang",
        "cash": "💰 Pulni olish · {win}$",
        "lose": "🐸 <b>QURBAQA</b> · {mode}\n👤 {name}\n\n💥 Qurbaqa suvga tushdi!\n💔 Yutqazdi: <b>−{bet}$</b>",
        "win": "🐸 <b>QURBAQA</b> · {mode}\n👤 {name}\n\n🏆 x{mult} da pulni oldi!\n💵 Tikdi: {bet}$ → olindi <b>{payout}$</b> (foyda <b>+{profit}$</b>)",
        "finish": "🎉 Qurbaqa narigi qirg‘oqqa yetdi!",
        "timeout_cash": "⌛ Faolsizlik — pul avtomatik olindi.",
        "timeout_refund": "⌛ Faolsizlik — o‘yin bekor qilindi, depozit qaytarildi.",
        "timeout": "⌛ Vaqt tugadi — o‘yin bekor qilindi.",
        "not_yours": "⛔ Bu o‘yin sizniki emas. O‘zingiz yangi o‘yin oching.",
        "no_funds": "💸 Balansingiz yetarli emas (kamida {min}$ kerak).",
        "no_more": "💸 Balansingiz {bal}$ — bundan ko‘p tikib bo‘lmaydi.",
        "jump_first": "🐸 Avval kamida bitta sakrang.",
        "wrong_row": "🐸 Faqat oldingi qatordagi barglarga sakrash mumkin.",
        "closed": "⌛ Bu o‘yin tugagan.",
        "error": "⚠️ Xatolik yuz berdi, qayta urinib ko‘ring.",
    },
    "eng": {
        "btn": "🐸 Frog",
        "desc": "Hop the frog across the lily pads",
        "lobby": (
            "🐸 <b>FROG</b>\n\n"
            "Hop the frog across the lily pads! Some pads in every row hide a danger — "
            "they move every game.\n"
            "Each hop raises the multiplier, and you can cash out at any time.\n\n"
            "💵 Minimum deposit: <b>{min}$</b>\n\n👇 Join the game"
        ),
        "join": "🙋 Join the game",
        "mode": (
            "🐸 <b>FROG</b>\n👤 {name}\n\nChoose a mode:\n"
            "🟢 Easy — 1 danger per row · last row x{easy}\n"
            "🟡 Medium — 2 dangers per row · last row x{medium}\n"
            "🔴 Hard — 3 dangers per row · last row x{hard}"
        ),
        "easy": "🟢 Easy", "medium": "🟡 Medium", "hard": "🔴 Hard",
        "bet": "🐸 <b>FROG</b> · {mode}\n👤 {name}\n\n💵 Deposit: <b>{bet}$</b>\n💰 Balance: {bal}$\n\nChoose a deposit and start 👇",
        "start": "✅ Start",
        "play": (
            "🐸 <b>FROG</b> · {mode}\n👤 {name} · 💵 {bet}$\n\n"
            "⏭ Next hop: <b>x{next}</b> → {next_win}$\n"
            "💰 Cash out now: <b>x{cur}</b> → {cur_win}$\n\n"
            "👇 Pick any pad in the next row"
        ),
        "shore": "🏝 The frog is on the shore — hop to the first row",
        "cash": "💰 Cash out · {win}$",
        "lose": "🐸 <b>FROG</b> · {mode}\n👤 {name}\n\n💥 The frog fell into the water!\n💔 Lost: <b>−{bet}$</b>",
        "win": "🐸 <b>FROG</b> · {mode}\n👤 {name}\n\n🏆 Cashed out at x{mult}!\n💵 Bet: {bet}$ → received <b>{payout}$</b> (profit <b>+{profit}$</b>)",
        "finish": "🎉 The frog reached the far shore!",
        "timeout_cash": "⌛ Inactive — cashed out automatically.",
        "timeout_refund": "⌛ Inactive — game cancelled, deposit refunded.",
        "timeout": "⌛ Time is up — the game was cancelled.",
        "not_yours": "⛔ This is not your game. Open a new one yourself.",
        "no_funds": "💸 Not enough balance (at least {min}$ needed).",
        "no_more": "💸 Your balance is {bal}$ — you can't bet more.",
        "jump_first": "🐸 Make at least one hop first.",
        "wrong_row": "🐸 You can only hop to a pad in the next row.",
        "closed": "⌛ This game has ended.",
        "error": "⚠️ Something went wrong, please try again.",
    },
    "ru": {
        "btn": "🐸 Лягушка",
        "desc": "Проведите лягушку по листьям кувшинок",
        "lobby": (
            "🐸 <b>ЛЯГУШКА</b>\n\n"
            "Проведите лягушку по листьям кувшинок! В каждом ряду под некоторыми листьями опасность — "
            "в каждой игре она в другом месте.\n"
            "Каждый прыжок повышает коэффициент, забрать выигрыш можно в любой момент.\n\n"
            "💵 Минимальный депозит: <b>{min}$</b>\n\n👇 Присоединяйтесь"
        ),
        "join": "🙋 Присоединиться",
        "mode": (
            "🐸 <b>ЛЯГУШКА</b>\n👤 {name}\n\nВыберите режим:\n"
            "🟢 Лёгкий — 1 опасность в ряду · последний ряд x{easy}\n"
            "🟡 Средний — 2 опасности в ряду · последний ряд x{medium}\n"
            "🔴 Сложный — 3 опасности в ряду · последний ряд x{hard}"
        ),
        "easy": "🟢 Лёгкий", "medium": "🟡 Средний", "hard": "🔴 Сложный",
        "bet": "🐸 <b>ЛЯГУШКА</b> · {mode}\n👤 {name}\n\n💵 Депозит: <b>{bet}$</b>\n💰 Баланс: {bal}$\n\nВыберите депозит и начните 👇",
        "start": "✅ Начать",
        "play": (
            "🐸 <b>ЛЯГУШКА</b> · {mode}\n👤 {name} · 💵 {bet}$\n\n"
            "⏭ Следующий прыжок: <b>x{next}</b> → {next_win}$\n"
            "💰 Забрать сейчас: <b>x{cur}</b> → {cur_win}$\n\n"
            "👇 Выберите любой лист в следующем ряду"
        ),
        "shore": "🏝 Лягушка на берегу — прыгайте в первый ряд",
        "cash": "💰 Забрать · {win}$",
        "lose": "🐸 <b>ЛЯГУШКА</b> · {mode}\n👤 {name}\n\n💥 Лягушка упала в воду!\n💔 Проигрыш: <b>−{bet}$</b>",
        "win": "🐸 <b>ЛЯГУШКА</b> · {mode}\n👤 {name}\n\n🏆 Забрал на x{mult}!\n💵 Ставка: {bet}$ → получено <b>{payout}$</b> (прибыль <b>+{profit}$</b>)",
        "finish": "🎉 Лягушка добралась до другого берега!",
        "timeout_cash": "⌛ Нет активности — выигрыш забран автоматически.",
        "timeout_refund": "⌛ Нет активности — игра отменена, депозит возвращён.",
        "timeout": "⌛ Время вышло — игра отменена.",
        "not_yours": "⛔ Это не ваша игра. Откройте свою.",
        "no_funds": "💸 Недостаточно средств (нужно минимум {min}$).",
        "no_more": "💸 Ваш баланс {bal}$ — больше поставить нельзя.",
        "jump_first": "🐸 Сначала сделайте хотя бы один прыжок.",
        "wrong_row": "🐸 Прыгать можно только на лист в следующем ряду.",
        "closed": "⌛ Эта игра закончена.",
        "error": "⚠️ Произошла ошибка, попробуйте ещё раз.",
    },
    "kz": {
        "btn": "🐸 Бақа",
        "desc": "Бақаны тұңғиық жапырақтарынан өткізіңіз",
        "lobby": (
            "🐸 <b>БАҚА</b>\n\n"
            "Бақаны тұңғиық жапырақтары арқылы өткізіңіз! Әр қатарда кейбір жапырақтың астында қауіп бар — "
            "әр ойында басқа жерде.\n"
            "Әр секірген сайын коэффициент өседі, ұтысты кез келген уақытта алуға болады.\n\n"
            "💵 Ең аз депозит: <b>{min}$</b>\n\n👇 Ойынға қосылыңыз"
        ),
        "join": "🙋 Ойынға қосылу",
        "mode": (
            "🐸 <b>БАҚА</b>\n👤 {name}\n\nРежимді таңдаңыз:\n"
            "🟢 Оңай — қатарда 1 қауіп · соңғы қатар x{easy}\n"
            "🟡 Орташа — қатарда 2 қауіп · соңғы қатар x{medium}\n"
            "🔴 Қиын — қатарда 3 қауіп · соңғы қатар x{hard}"
        ),
        "easy": "🟢 Оңай", "medium": "🟡 Орташа", "hard": "🔴 Қиын",
        "bet": "🐸 <b>БАҚА</b> · {mode}\n👤 {name}\n\n💵 Депозит: <b>{bet}$</b>\n💰 Баланс: {bal}$\n\nДепозитті таңдап, ойынды бастаңыз 👇",
        "start": "✅ Бастау",
        "play": (
            "🐸 <b>БАҚА</b> · {mode}\n👤 {name} · 💵 {bet}$\n\n"
            "⏭ Келесі секіру: <b>x{next}</b> → {next_win}$\n"
            "💰 Қазір алсаңыз: <b>x{cur}</b> → {cur_win}$\n\n"
            "👇 Келесі қатардағы кез келген жапырақты таңдаңыз"
        ),
        "shore": "🏝 Бақа жағада — бірінші қатарға секіріңіз",
        "cash": "💰 Ұтысты алу · {win}$",
        "lose": "🐸 <b>БАҚА</b> · {mode}\n👤 {name}\n\n💥 Бақа суға түсті!\n💔 Ұтылды: <b>−{bet}$</b>",
        "win": "🐸 <b>БАҚА</b> · {mode}\n👤 {name}\n\n🏆 x{mult} кезінде ұтысты алды!\n💵 Салды: {bet}$ → алынды <b>{payout}$</b> (пайда <b>+{profit}$</b>)",
        "finish": "🎉 Бақа арғы жағаға жетті!",
        "timeout_cash": "⌛ Белсенділік жоқ — ұтыс автоматты түрде алынды.",
        "timeout_refund": "⌛ Белсенділік жоқ — ойын тоқтатылды, депозит қайтарылды.",
        "timeout": "⌛ Уақыт бітті — ойын тоқтатылды.",
        "not_yours": "⛔ Бұл сіздің ойыныңыз емес. Өзіңіз жаңасын ашыңыз.",
        "no_funds": "💸 Балансыңыз жеткіліксіз (кемінде {min}$ керек).",
        "no_more": "💸 Балансыңыз {bal}$ — бұдан көп салуға болмайды.",
        "jump_first": "🐸 Алдымен кемінде бір рет секіріңіз.",
        "wrong_row": "🐸 Тек келесі қатардағы жапыраққа секіруге болады.",
        "closed": "⌛ Бұл ойын аяқталды.",
        "error": "⚠️ Қате шықты, қайталап көріңіз.",
    },
}


def frog_t(chat, key, **kwargs):
    lang = LANG_CACHE.get(chat, DEFAULT_LANG)
    text = FROG_TEXT.get(lang, FROG_TEXT["uz"]).get(key) or FROG_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def frog_mult(mode, steps):
    if steps <= 0:
        return 1.0
    safe = FROG_COLS - FROG_MODES[mode]
    return math.floor(FROG_RTP * (FROG_COLS / safe) ** steps * 100) / 100


def frog_key(q):
    """Har bir o'yin xabari — alohida o'yin (inline yoki chat:xabar)."""
    if q.inline_message_id:
        return INLINE_PREFIX + q.inline_message_id
    return f"{q.message.chat.id}:{q.message.message_id}"


def frog_lobby_kb(chat):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(frog_t(chat, "join"), callback_data="fr:join")
    ]])


def frog_mode_text(chat, game):
    return frog_t(
        chat, "mode", name=game["name"],
        **{m: f"{frog_mult(m, FROG_ROWS):g}" for m in FROG_MODES},
    )


def frog_mode_kb(chat):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(frog_t(chat, m), callback_data=f"fr:mode:{m}") for m in FROG_MODES
    ]])


def frog_bet_text(chat, game):
    return frog_t(
        chat, "bet", mode=frog_t(chat, game["mode"]), name=game["name"],
        bet=game["bet"], bal=wallet_balance(game["player"]),
    )


def frog_bet_kb(chat):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"➖{FROG_STEP}", callback_data="fr:bet:minus"),
            InlineKeyboardButton(f"➕{FROG_STEP}", callback_data="fr:bet:plus"),
            InlineKeyboardButton("✖️2", callback_data="fr:bet:x2"),
            InlineKeyboardButton(f"🔽{FROG_MIN_BET}", callback_data="fr:bet:min"),
        ],
        [InlineKeyboardButton(frog_t(chat, "start"), callback_data="fr:go")],
    ])


def frog_payout(game):
    return game["bet"] * int(round(frog_mult(game["mode"], len(game["path"])) * 100)) // 100


def frog_play_text(chat, game):
    steps = len(game["path"])
    nxt = frog_mult(game["mode"], steps + 1)
    cur = frog_mult(game["mode"], steps)
    text = frog_t(
        chat, "play", mode=frog_t(chat, game["mode"]), name=game["name"], bet=game["bet"],
        next=f"{nxt:.2f}", next_win=game["bet"] * int(round(nxt * 100)) // 100,
        cur=f"{cur:.2f}", cur_win=frog_payout(game),
    )
    if not steps:
        text += "\n\n" + frog_t(chat, "shore")
    return text


def frog_board_kb(chat, game, reveal=False, hit=None):
    """Yuqorida — oxirgi qator, pastda — birinchi qator (qurbaqa pastdan yuqoriga sakraydi)."""
    steps = len(game["path"])
    rows = []
    for r in reversed(range(FROG_ROWS)):
        row = []
        for c in range(FROG_COLS):
            data = "noop"
            if hit == (r, c):
                label = FROG_CELL["hit"]
            elif r < steps and game["path"][r] == c:
                label = FROG_CELL["frog"] if r == steps - 1 and hit is None else FROG_CELL["path"]
            elif reveal and c in game["traps"][r]:
                label = FROG_CELL["trap"]
            elif reveal:
                label = FROG_CELL["safe"]
            elif r < steps:
                label = FROG_CELL["past"]
            elif r == steps:
                label = FROG_CELL["next"]
                data = f"fr:c:{r}:{c}"
            else:
                label = FROG_CELL["future"]
            row.append(InlineKeyboardButton(label, callback_data=data))
        rows.append(row)
    if reveal:
        rows.append(again_row(chat))
    else:
        rows.append([InlineKeyboardButton(
            frog_t(chat, "cash", win=frog_payout(game)), callback_data="fr:cash"
        )])
    return InlineKeyboardMarkup(rows)


async def frog_edit(bot, game, text, kb):
    await edit(bot, game["chat"], game["msg_id"], text, kb)


def frog_arm(app, key, game, seconds):
    old = game.get("timer")
    if old and not old.done():
        old.cancel()
    task = asyncio.create_task(_frog_expire(app, key, game, seconds))
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)
    game["timer"] = task


def frog_close(key, game):
    if FROG_GAMES.get(key) is game:
        del FROG_GAMES[key]
    game["state"] = "end"
    timer = game.get("timer")
    if timer and not timer.done() and timer is not asyncio.current_task():
        timer.cancel()


def frog_settle(game):
    """Yakunlanmagan o'yinni pul bilan yopadi: sakragan bo'lsa — yutuq, aks holda depozit qaytadi.
    Qaytaradi: to'langan summa (0 — to'lov yo'q)."""
    if not game.get("paid") or game.get("settled"):
        return 0
    game["settled"] = True
    amount = frog_payout(game) if game["path"] else game["bet"]
    wallet_change(game["player"], amount)
    return amount


async def _frog_expire(app, key, game, seconds):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    async with game["lock"]:
        if FROG_GAMES.get(key) is not game:
            return
        chat = game["chat"]
        if game["state"] == "play":
            try:
                frog_settle(game)
            except sqlite3.Error:
                logger.exception("Qurbaqa: avtomatik to'lov yozilmadi (user %s)", game["player"])
            frog_close(key, game)
            if game["path"]:
                record(chat, game["player"], "win")
                text = frog_result_text(chat, game) + "\n\n" + frog_t(chat, "timeout_cash")
                await frog_log(app.bot, chat, game, f"+{frog_payout(game) - game['bet']}$ (avto)")
            else:
                text = frog_t(chat, "timeout_refund")
            await frog_edit(app.bot, game, text, frog_board_kb(chat, game, reveal=True))
            return
        frog_close(key, game)
        await frog_edit(app.bot, game, frog_t(chat, "timeout"), None)


def frog_result_text(chat, game):
    payout = frog_payout(game) if game["path"] else game["bet"]
    return frog_t(
        chat, "win", mode=frog_t(chat, game["mode"]), name=game["name"],
        mult=f"{frog_mult(game['mode'], len(game['path'])):.2f}", bet=game["bet"],
        payout=payout, profit=payout - game["bet"],
    )


async def frog_log(bot, chat, game, result):
    await log_money_event(
        bot,
        "🐸 <b>QURBAQA</b>\n"
        f"Chat: <code>{escape(str(chat))}</code>\n"
        f"{person_name(game['player'])} · {game['mode']} · {game['bet']}$ · "
        f"{len(game['path'])}/{FROG_ROWS} qadam\n{result}",
    )


async def cb_frog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    key = frog_key(q)
    parts = q.data.split(":")
    chat = game_key(q)
    if is_inline_key(chat) and chat not in LANG_CACHE and len(parts) > 2 and parts[1] == "join":
        set_inline_lang(chat, parts[2])

    game = FROG_GAMES.get(key)
    if not game:
        if parts[1] != "join":
            await q.answer(frog_t(chat, "closed"), show_alert=True)
            return
        game = {"chat": chat, "msg_id": None if q.inline_message_id else q.message.message_id,
                "player": None, "state": "join", "lock": asyncio.Lock(), "timer": None,
                "path": [], "paid": False, "settled": False}
        FROG_GAMES[key] = game
    async with game["lock"]:
        if FROG_GAMES.get(key) is not game:
            await q.answer(frog_t(chat, "closed"), show_alert=True)
            return
        try:
            await _frog_action(q, context, key, game, parts)
        except sqlite3.Error:
            logger.exception("Qurbaqa: bazada xato")
            await q.answer(frog_t(chat, "error"), show_alert=True)


async def _frog_action(q, context, key, game, parts):
    chat = game["chat"]
    user = q.from_user
    action = parts[1]
    app = context.application

    if action == "join":
        if game["player"] == user.id:
            await q.answer()
            return
        if game["player"] is not None:
            await q.answer(frog_t(chat, "not_yours"), show_alert=True)
            return
        if await fsub_block_cb(q, context):
            frog_close(key, game)   # lobby ochiq qolmasin
            return
        if wallet_balance(user.id) < FROG_MIN_BET:
            await q.answer(frog_t(chat, "no_funds", min=FROG_MIN_BET), show_alert=True)
            frog_close(key, game)   # lobby xabari qoladi — keyingi bosgan odam uchun yangidan ochiladi
            return
        save_user(user)
        game.update(player=user.id, name=uname(user), state="mode", bet=FROG_MIN_BET)
        await q.answer()
        await frog_edit(context.bot, game, frog_mode_text(chat, game), frog_mode_kb(chat))
        frog_arm(app, key, game, FROG_SETUP_TTL)
        return

    if user.id != game["player"]:
        await q.answer(frog_t(chat, "not_yours"), show_alert=True)
        return

    if action == "mode":
        if game["state"] != "mode" or parts[2] not in FROG_MODES:
            await q.answer()
            return
        game.update(mode=parts[2], state="bet")
        await q.answer()
        await frog_edit(context.bot, game, frog_bet_text(chat, game), frog_bet_kb(chat))
        frog_arm(app, key, game, FROG_SETUP_TTL)
        return

    if action == "bet":
        if game["state"] != "bet":
            await q.answer()
            return
        balance = wallet_balance(user.id)
        bet = {"minus": game["bet"] - FROG_STEP, "plus": game["bet"] + FROG_STEP,
               "x2": game["bet"] * 2, "min": FROG_MIN_BET}.get(parts[2], game["bet"])
        bet = max(FROG_MIN_BET, bet)
        if bet > balance:
            await q.answer(frog_t(chat, "no_more", bal=balance), show_alert=True)
            return
        game["bet"] = bet
        await q.answer()
        await frog_edit(context.bot, game, frog_bet_text(chat, game), frog_bet_kb(chat))
        frog_arm(app, key, game, FROG_SETUP_TTL)
        return

    if action == "go":
        if game["state"] != "bet":
            await q.answer()
            return
        c = db()
        with c:
            cur = c.execute(
                "UPDATE user_wallet SET money=money-? WHERE user_id=? AND money>=?",
                (game["bet"], user.id, game["bet"]),
            )
        if cur.rowcount != 1:
            await q.answer(frog_t(chat, "no_funds", min=game["bet"]), show_alert=True)
            return
        bad = FROG_MODES[game["mode"]]
        game.update(
            paid=True, state="play",
            traps=[set(_CRASH_RNG.sample(range(FROG_COLS), bad)) for _ in range(FROG_ROWS)],
        )
        await q.answer()
        await frog_edit(context.bot, game, frog_play_text(chat, game), frog_board_kb(chat, game))
        frog_arm(app, key, game, FROG_PLAY_TTL)
        return

    if action == "c":
        if game["state"] != "play":
            await q.answer(frog_t(chat, "closed"), show_alert=True)
            return
        r, col = int(parts[2]), int(parts[3])
        if r != len(game["path"]) or not 0 <= col < FROG_COLS:
            await q.answer(frog_t(chat, "wrong_row"), show_alert=True)
            return
        await q.answer()

        if col in game["traps"][r]:
            game["settled"] = True
            frog_close(key, game)
            record(chat, user.id, "loss")
            await frog_edit(
                context.bot, game,
                frog_t(chat, "lose", mode=frog_t(chat, game["mode"]), name=game["name"], bet=game["bet"]),
                frog_board_kb(chat, game, reveal=True, hit=(r, col)),
            )
            await frog_log(context.bot, chat, game, f"−{game['bet']}$")
            return

        game["path"].append(col)
        if len(game["path"]) < FROG_ROWS:
            await frog_edit(context.bot, game, frog_play_text(chat, game), frog_board_kb(chat, game))
            frog_arm(app, key, game, FROG_PLAY_TTL)
            return
        # Oxirgi qatordan o'tdi — yutuq avtomatik olinadi.
        await _frog_cashout(context, key, game, frog_t(chat, "finish"))
        return

    if action == "cash":
        if game["state"] != "play":
            await q.answer(frog_t(chat, "closed"), show_alert=True)
            return
        if not game["path"]:
            await q.answer(frog_t(chat, "jump_first"), show_alert=True)
            return
        await q.answer()
        await _frog_cashout(context, key, game)
        return

    await q.answer()


async def _frog_cashout(context, key, game, note=""):
    chat = game["chat"]
    payout = frog_settle(game)
    frog_close(key, game)
    record(chat, game["player"], "win")
    text = frog_result_text(chat, game) + (f"\n\n{note}" if note else "")
    await frog_edit(context.bot, game, text, frog_board_kb(chat, game, reveal=True))
    await frog_log(context.bot, chat, game, f"+{payout - game['bet']}$ (x{frog_mult(game['mode'], len(game['path'])):.2f})")


# ───────────────────────────── 🎯 Son topish ─────────────────────────────

HEAT =[(3, "heat_hot"), (10, "heat_warm"), (25, "heat_cool"), (10**9, "heat_cold")]


# ───────────────────────────── 📢 "bot" — guruh a'zolarini chaqirish ─────────────────────────────
# Bot egasi (yoki bot egasi xabariga reply qilib "ruxsat" bergan a'zo) guruhda "bot" deb yozsa, bot guruh a'zolarini
# bittadan, har biri alohida xabarda chaqiradi. "bot kelish" — har bir a'zo "@username kelish" ko'rinishida
# chaqiriladi. "stop" — jarayonni to'xtatadi. "tez 0.7" — xabarlar oralig'i (soniya).
# Telegram botga guruh a'zolarining to'liq ro'yxatini bermaydi, shuning uchun bot
# guruhda yozgan / qo'shilgan a'zolarni group_members jadvalida o'zi yig'ib boradi.

TAG_WORDS = {"bot", "бот"}
TAG_STOP_WORDS = {"stop", "стоп", "bot stop", "бот стоп"}
TAG_TEXT_MAX = 200      # "bot ..." dan keyingi matnning eng katta uzunligi
TAG_BATCH = 1           # bitta xabardagi belgilar soni (har bir a'zo — alohida xabar)
TAG_DELAY = 1.5         # xabarlar orasidagi standart pauza (soniya)
TAG_DELAY_MIN = 0.7     # "tez" bilan o'rnatiladigan eng qisqa pauza
TAG_DELAY_MAX = 1.5     # "tez" bilan o'rnatiladigan eng uzun pauza
TAG_SPEED_WORDS = {"tez", "speed", "скорость", "жылдамдық"}
TAG_GRANT_WORDS = {"ruxsat", "разрешить", "рұқсат"}
TAG_REVOKE_WORDS = {"xayr", "запретить", "тыйым"}
TAG_TASKS: dict[int, asyncio.Task] = {}

TAG_TEXT = {
    "uz": {
        "head": "📢 <b>Diqqat!</b>",
        "busy": "⏳ A'zolar hozir chaqirilyapti. To'xtatish: <b>stop</b>",
        "empty": "🤷 Bot hali bu guruh a'zolarini bilmaydi. A'zolar guruhda yozganda ular ro'yxatga qo'shiladi.",
        "done": "✅ <b>{n}</b> ta a'zo chaqirildi.",
        "stopped": "🛑 Chaqirish to'xtatildi ({n} ta a'zo chaqirildi).",
        "speed_set": "⚡ Tag tezligi: har bir xabar oralig'i <b>{d}</b> soniya.",
        "speed_now": "⚡ Hozirgi tag tezligi: <b>{d}</b> soniya.\nO'zgartirish: <b>tez {lo}</b> … <b>tez {hi}</b>",
        "speed_bad": "⚠️ Tezlik {lo} dan {hi} soniyagacha bo'lishi kerak. Masalan: <b>tez 0.7</b>",
        "perm_granted": "✅ <b>{name}</b> endi bu guruhda tag buyruqlaridan foydalana oladi (bot, stop, tez).",
        "perm_revoked": "🚫 <b>{name}</b> tag buyruqlaridan foydalanish huquqidan mahrum qilindi.",
        "perm_owner": "👑 <b>{name}</b> — bot egasi, uning huquqi doim bor.",
    },
    "eng": {
        "head": "📢 <b>Attention!</b>",
        "busy": "⏳ Members are being tagged right now. To stop: <b>stop</b>",
        "empty": "🤷 The bot doesn't know this group's members yet. Members are added when they write in the group.",
        "done": "✅ <b>{n}</b> members tagged.",
        "stopped": "🛑 Tagging stopped ({n} members tagged).",
        "speed_set": "⚡ Tag speed: <b>{d}</b> s between messages.",
        "speed_now": "⚡ Current tag speed: <b>{d}</b> s.\nChange it: <b>speed {lo}</b> … <b>speed {hi}</b>",
        "speed_bad": "⚠️ Speed must be between {lo} and {hi} seconds. Example: <b>speed 0.7</b>",
        "perm_granted": "✅ <b>{name}</b> can now use the tag commands in this group (bot, stop, speed).",
        "perm_revoked": "🚫 <b>{name}</b> can no longer use the tag commands.",
        "perm_owner": "👑 <b>{name}</b> is a bot owner and always has access.",
    },
    "ru": {
        "head": "📢 <b>Внимание!</b>",
        "busy": "⏳ Участники уже упоминаются. Остановить: <b>стоп</b>",
        "empty": "🤷 Бот пока не знает участников этой группы. Они добавляются, когда пишут в группе.",
        "done": "✅ Упомянуто участников: <b>{n}</b>.",
        "stopped": "🛑 Упоминание остановлено (упомянуто: {n}).",
        "speed_set": "⚡ Скорость упоминаний: <b>{d}</b> с между сообщениями.",
        "speed_now": "⚡ Текущая скорость: <b>{d}</b> с.\nИзменить: <b>скорость {lo}</b> … <b>скорость {hi}</b>",
        "speed_bad": "⚠️ Скорость должна быть от {lo} до {hi} секунд. Например: <b>скорость 0.7</b>",
        "perm_granted": "✅ <b>{name}</b> теперь может использовать команды упоминания в этой группе.",
        "perm_revoked": "🚫 <b>{name}</b> больше не может использовать команды упоминания.",
        "perm_owner": "👑 <b>{name}</b> — владелец бота, доступ есть всегда.",
    },
    "kz": {
        "head": "📢 <b>Назар аударыңыз!</b>",
        "busy": "⏳ Мүшелер қазір белгіленуде. Тоқтату: <b>стоп</b>",
        "empty": "🤷 Бот бұл топтың мүшелерін әлі білмейді. Олар топта жазғанда тізімге қосылады.",
        "done": "✅ <b>{n}</b> мүше белгіленді.",
        "stopped": "🛑 Белгілеу тоқтатылды ({n} мүше белгіленді).",
        "speed_set": "⚡ Белгілеу жылдамдығы: хабарлар арасы <b>{d}</b> секунд.",
        "speed_now": "⚡ Қазіргі жылдамдық: <b>{d}</b> секунд.\nӨзгерту: <b>жылдамдық {lo}</b> … <b>жылдамдық {hi}</b>",
        "speed_bad": "⚠️ Жылдамдық {lo} мен {hi} секунд аралығында болуы керек. Мысалы: <b>жылдамдық 0.7</b>",
        "perm_granted": "✅ <b>{name}</b> енді бұл топта белгілеу командаларын қолдана алады.",
        "perm_revoked": "🚫 <b>{name}</b> белгілеу командаларын қолдана алмайды.",
        "perm_owner": "👑 <b>{name}</b> — бот иесі, оның рұқсаты әрқашан бар.",
    },
}


def tag_t(chat_id, key, **kwargs):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    text = TAG_TEXT.get(lang, TAG_TEXT["uz"]).get(key) or TAG_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def init_group_members():
    c = db()
    with c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                last_seen TEXT NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS member_activity (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                messages INTEGER NOT NULL DEFAULT 0,
                since TEXT NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_member_activity_top "
            "ON member_activity(chat_id, messages DESC)"
        )
        c.execute("""
            CREATE TABLE IF NOT EXISTS member_words (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                cnt INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id, word)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS tag_permissions (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                granted_by INTEGER NOT NULL,
                granted_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS tag_speed (
                chat_id INTEGER PRIMARY KEY,
                delay REAL NOT NULL
            )
        """)
        # Birinchi ishga tushishda guruhda o'ynagan a'zolarni ro'yxatga olamiz.
        c.execute("""
            INSERT OR IGNORE INTO group_members(chat_id, user_id, last_seen)
            SELECT chat_id, user_id, ? FROM chat_stats WHERE chat_id < 0
        """, (datetime.utcnow().isoformat(),))


def tag_delay(chat_id):
    row = db().execute("SELECT delay FROM tag_speed WHERE chat_id=?", (chat_id,)).fetchone()
    if not row:
        return TAG_DELAY
    return min(TAG_DELAY_MAX, max(TAG_DELAY_MIN, float(row[0])))


def set_tag_delay(chat_id, delay):
    c = db()
    with c:
        c.execute(
            "INSERT INTO tag_speed(chat_id, delay) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET delay = excluded.delay",
            (chat_id, delay),
        )


def member_seen(chat_id, user):
    if not user or user.is_bot:
        return
    if _SEEN.get(user.id) != (user.username, user.first_name):
        save_user(user)
    c = db()
    with c:
        c.execute(
            """
            INSERT INTO group_members(chat_id, user_id, last_seen) VALUES (?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (chat_id, user.id, datetime.utcnow().isoformat()),
        )


def member_left(chat_id, user_id):
    c = db()
    with c:
        c.execute("DELETE FROM group_members WHERE chat_id=? AND user_id=?", (chat_id, user_id))


async def track_group_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guruhdagi har bir xabardan a'zolar ro'yxatini yangilaydi (boshqa handlerlarga ta'sir qilmaydi)."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    try:
        member_seen(chat.id, update.effective_user)
        if update.message:   # tahrirlangan xabarlar qayta sanalmaydi
            count_activity(chat.id, update.effective_user, msg.text or msg.caption or "")
        for new in msg.new_chat_members or ():
            member_seen(chat.id, new)
        if msg.left_chat_member:
            member_left(chat.id, msg.left_chat_member.id)
    except sqlite3.Error:
        logger.exception("group_members yangilanmadi")


# ───────────────────────────── 📊 /aktiv — eng faol a'zolar ─────────────────────────────
# Bot guruhdagi har bir xabarni sanaydi (shu funksiya qo'shilgan paytdan boshlab —
# Telegram botga eski xabarlar tarixini bermaydi) va har bir a'zoning so'zlarini yig'adi.

AKTIV_TOP = 15
AKTIV_MIN_WORD = 3          # bundan qisqa so'zlar ("va", "u") hisobga olinmaydi
AKTIV_MAX_WORDS = 100       # bitta xabardan olinadigan so'zlar soni
_AKTIV_CLEAN_RE = re.compile(r"(https?://\S+|www\.\S+|[@/#]\w+)", re.I)
_AKTIV_WORD_RE = re.compile(r"[^\W\d_]+(?:['’ʻʼ‘`][^\W\d_]+)*")

AKTIV_TEXT = {
    "uz": {
        "title": "📊 <b>ENG FAOL {n} A'ZO</b>\n🗓 {since} dan beri",
        "line": "{medal} <b>{name}</b> — {count} ta xabar",
        "word": "\n      💬 Ko'p yozgan so'zi: <i>{word}</i> ({times} marta)",
        "empty": "📭 Hali hisob yo'q. Bot shu paytdan boshlab guruhdagi xabarlarni sanaydi.",
        "admins_only": "⛔ /aktiv faqat guruh adminlari uchun.",
    },
    "eng": {
        "title": "📊 <b>TOP {n} MOST ACTIVE MEMBERS</b>\n🗓 since {since}",
        "line": "{medal} <b>{name}</b> — {count} messages",
        "word": "\n      💬 Favourite word: <i>{word}</i> ({times} times)",
        "empty": "📭 No stats yet. The bot counts group messages from now on.",
        "admins_only": "⛔ /aktiv is for group admins only.",
    },
    "ru": {
        "title": "📊 <b>ТОП-{n} САМЫХ АКТИВНЫХ</b>\n🗓 с {since}",
        "line": "{medal} <b>{name}</b> — {count} сообщ.",
        "word": "\n      💬 Любимое слово: <i>{word}</i> ({times} раз)",
        "empty": "📭 Статистики пока нет. Бот считает сообщения группы с этого момента.",
        "admins_only": "⛔ /aktiv только для администраторов группы.",
    },
    "kz": {
        "title": "📊 <b>ЕҢ БЕЛСЕНДІ {n} МҮШЕ</b>\n🗓 {since} бастап",
        "line": "{medal} <b>{name}</b> — {count} хабарлама",
        "word": "\n      💬 Жиі жазған сөзі: <i>{word}</i> ({times} рет)",
        "empty": "📭 Әзірге статистика жоқ. Бот топ хабарламаларын осы сәттен бастап санайды.",
        "admins_only": "⛔ /aktiv тек топ әкімшілері үшін.",
    },
}


def aktiv_t(chat_id, key, **kwargs):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    text = AKTIV_TEXT.get(lang, AKTIV_TEXT["uz"]).get(key) or AKTIV_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def aktiv_words(text):
    text = _AKTIV_CLEAN_RE.sub(" ", text.lower())
    words = [w for w in _AKTIV_WORD_RE.findall(text) if len(w) >= AKTIV_MIN_WORD]
    return words[:AKTIV_MAX_WORDS]


def count_activity(chat_id, user, text):
    if not user or user.is_bot:
        return
    now = datetime.utcnow().isoformat()
    c = db()
    with c:
        c.execute(
            """
            INSERT INTO member_activity(chat_id, user_id, messages, since) VALUES (?, ?, 1, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET messages = messages + 1
            """,
            (chat_id, user.id, now),
        )
        words = {}
        for w in aktiv_words(text):
            words[w] = words.get(w, 0) + 1
        if words:
            c.executemany(
                """
                INSERT INTO member_words(chat_id, user_id, word, cnt) VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id, word) DO UPDATE SET cnt = cnt + excluded.cnt
                """,
                [(chat_id, user.id, w, n) for w, n in words.items()],
            )


async def cmd_aktiv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return
    if chat.type == ChatType.PRIVATE:
        await msg.reply_text(t(chat.id, "use_group"))
        return

    user = update.effective_user
    anonymous_admin = bool(msg.sender_chat and msg.sender_chat.id == chat.id)
    allowed = anonymous_admin or (user and (
        user.id in CAREER_OWNER_IDS or await is_admin(context.bot, chat.id, user.id)
    ))
    if not allowed:
        await msg.reply_text(aktiv_t(chat.id, "admins_only"))
        return

    c = db()
    rows = c.execute(
        """
        SELECT a.user_id, a.messages, u.first_name, u.username
        FROM member_activity a LEFT JOIN users u ON u.user_id = a.user_id
        WHERE a.chat_id = ?
        ORDER BY a.messages DESC LIMIT ?
        """,
        (chat.id, AKTIV_TOP),
    ).fetchall()
    if not rows:
        await msg.reply_text(aktiv_t(chat.id, "empty"))
        return

    since = c.execute(
        "SELECT MIN(since) FROM member_activity WHERE chat_id = ?", (chat.id,)
    ).fetchone()[0]
    medals = ["🥇", "🥈", "🥉"]
    lines = [aktiv_t(chat.id, "title", n=len(rows), since=since[:10]), ""]
    for i, (uid, count, first_name, username) in enumerate(rows):
        line = aktiv_t(
            chat.id, "line",
            medal=medals[i] if i < len(medals) else f"{i + 1}.",
            name=f'<a href="tg://user?id={uid}">{pretty_name(first_name, username)}</a>', count=count,
        )
        top = c.execute(
            """
            SELECT word, cnt FROM member_words
            WHERE chat_id = ? AND user_id = ?
            ORDER BY cnt DESC, word LIMIT 1
            """,
            (chat.id, uid),
        ).fetchone()
        if top:
            line += aktiv_t(chat.id, "word", word=escape(top[0]), times=top[1])
        lines.append(line)
    await msg.reply_text("\n".join(lines))


async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot admin bo'lgan guruhlarda kirish/chiqishlarni kuzatadi."""
    event = update.chat_member
    if not event or event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    member = event.new_chat_member
    await announce_new_admin(context, event)
    try:
        if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            member_left(event.chat.id, member.user.id)
        else:
            member_seen(event.chat.id, member.user)
    except sqlite3.Error:
        logger.exception("group_members yangilanmadi")


async def tag_members(bot, chat_id, note=""):
    c = db()
    rows = c.execute(
        """
        SELECT g.user_id, u.first_name, u.username
        FROM group_members g LEFT JOIN users u ON u.user_id = g.user_id
        WHERE g.chat_id = ?
        ORDER BY g.last_seen DESC
        """,
        (chat_id,),
    ).fetchall()
    members = {
        uid: escape(f"@{username}") if username else pretty_name(first, username)
        for uid, first, username in rows
    }

    # Guruh adminlari har doim ma'lum — ularni ham qo'shamiz.
    try:
        for admin in await bot.get_chat_administrators(chat_id):
            a = admin.user
            if not a.is_bot and a.id not in members:
                members[a.id] = escape(f"@{a.username}") if a.username else uname(a)
    except TelegramError as e:
        logger.warning("Adminlar ro'yxati olinmadi: %s", e)

    if not members:
        await bot.send_message(chat_id, tag_t(chat_id, "empty"))
        return

    tagged = 0
    items = list(members.items())
    try:
        for i in range(0, len(items), TAG_BATCH):
            batch = items[i:i + TAG_BATCH]
            links = [f'<a href="tg://user?id={uid}">{name}</a>' for uid, name in batch]
            if note:
                # "bot kelish" → har bir qatorda: @username kelish
                text = "\n".join(f"{link} {note}" for link in links)
            else:
                text = f"{tag_t(chat_id, 'head')}\n" + " ".join(links)
            await _send_retry(lambda: bot.send_message(chat_id, text))
            tagged += len(batch)
            if i + TAG_BATCH < len(items):
                # Har safar o'qiymiz — "tez" jarayon davomida ham darhol ta'sir qiladi.
                await asyncio.sleep(tag_delay(chat_id))
    except asyncio.CancelledError:
        await bot.send_message(chat_id, tag_t(chat_id, "stopped", n=tagged))
        raise
    await bot.send_message(chat_id, tag_t(chat_id, "done", n=tagged))


def can_tag(chat_id, user_id):
    """Bot egalari va bot egasi shu guruhda "ruxsat" bergan a'zolar."""
    if user_id in CAREER_OWNER_IDS:
        return True
    return db().execute(
        "SELECT 1 FROM tag_permissions WHERE chat_id=? AND user_id=?", (chat_id, user_id)
    ).fetchone() is not None


async def maybe_tag_permission(msg, user):
    """Bot egasi xabarga reply qilib "ruxsat" / "xayr" yozsa — tag huquqini beradi / oladi."""
    text = msg.text.strip().lower()
    if text not in TAG_GRANT_WORDS and text not in TAG_REVOKE_WORDS:
        return False
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if user.id not in CAREER_OWNER_IDS or not target or target.is_bot:
        return False

    chat_id = msg.chat_id
    name = uname(target)
    if target.id in CAREER_OWNER_IDS:
        await msg.reply_text(tag_t(chat_id, "perm_owner", name=name))
        return True

    c = db()
    with c:
        if text in TAG_GRANT_WORDS:
            save_user(target)
            c.execute(
                """
                INSERT INTO tag_permissions(chat_id, user_id, granted_by, granted_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    granted_by = excluded.granted_by, granted_at = excluded.granted_at
                """,
                (chat_id, target.id, user.id, datetime.utcnow().isoformat()),
            )
            key = "perm_granted"
        else:
            c.execute(
                "DELETE FROM tag_permissions WHERE chat_id=? AND user_id=?", (chat_id, target.id)
            )
            key = "perm_revoked"
    await msg.reply_text(tag_t(chat_id, key, name=name))
    return True


async def maybe_tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'bot [matn]' / 'stop' buyrug'i bo'lsa — bajaradi va True qaytaradi."""
    msg = update.effective_message
    user = update.effective_user
    if await maybe_tag_permission(msg, user):
        return True
    raw = msg.text.strip()
    text = raw.lower()
    first, _, rest = raw.partition(" ")
    is_start = first.lower() in TAG_WORDS
    is_speed = first.lower() in TAG_SPEED_WORDS and len(rest.split()) <= 1
    if not is_start and not is_speed and text not in TAG_STOP_WORDS:
        return False

    chat_id = msg.chat_id
    if not can_tag(chat_id, user.id):
        return False

    if is_speed:
        limits = {"lo": TAG_DELAY_MIN, "hi": TAG_DELAY_MAX}
        value = rest.strip().replace(",", ".")
        if not value:
            await msg.reply_text(tag_t(chat_id, "speed_now", d=tag_delay(chat_id), **limits))
            return True
        try:
            delay = round(float(value), 2)
        except ValueError:
            return False   # "tez ketdi" kabi oddiy gap — buyruq emas
        if not TAG_DELAY_MIN <= delay <= TAG_DELAY_MAX:
            await msg.reply_text(tag_t(chat_id, "speed_bad", **limits))
            return True
        set_tag_delay(chat_id, delay)
        await msg.reply_text(tag_t(chat_id, "speed_set", d=delay))
        return True
    running = TAG_TASKS.get(chat_id)

    if text in TAG_STOP_WORDS:
        if not running or running.done():
            return False   # oddiy "stop" so'zi — tag ketmayapti, boshqa handlerlarga o'tkazamiz
        running.cancel()
        return True

    note = escape(" ".join(rest.split())[:TAG_TEXT_MAX])

    if running and not running.done():
        await msg.reply_text(tag_t(chat_id, "busy"))
        return True

    task = asyncio.create_task(tag_members(context.bot, chat_id, note))
    TAG_TASKS[chat_id] = task
    BG_TASKS.add(task)

    def _done(t):
        BG_TASKS.discard(t)
        if TAG_TASKS.get(chat_id) is t:
            del TAG_TASKS[chat_id]
        if not t.cancelled() and t.exception():
            logger.error("A'zolarni chaqirishda xato", exc_info=t.exception())

    task.add_done_callback(_done)
    return True


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not msg.text or not user or user.is_bot:
        return

    if await maybe_tag_all(update, context):
        return

    chat_id = msg.chat_id

    # Group Help filtrlari: admin belgilagan so'zga avtomatik javob.
    reply = gh_filter_match(chat_id, msg.text)
    if reply:
        try:
            await msg.reply_text(reply)
        except TelegramError:
            pass
        return

    game = GAMES.get(chat_id)
    if not game:
        return

    if game["type"] == "croc":
        await croc_on_text(update, context, game)
        return

    if game["type"] != "number":
        return

    text = msg.text.strip()
    if not (text.isascii() and text.isdigit()):
        return
    guess = int(text)
    if not MIN_NUMBER <= guess <= MAX_NUMBER:
        return

    if await fsub_block_msg(update, context):
        return

    save_user(user)

    if guess in game["tried"]:
        await msg.reply_text(t(chat_id, "number_dup", number=guess))
        return

    game["tried"].add(guess)
    game["attempts"] += 1
    game["players"].add(user.id)
    number = game["number"]

    if guess == number:
        attempts = game["attempts"]
        fast = attempts <= FAST_ATTEMPTS
        points = NUMBER_WIN_PTS + (NUMBER_BONUS_PTS if fast else 0)
        end_game(chat_id, game)

        for uid in game["players"]:
            if uid == user.id:
                record(chat_id, uid, "win", points)
            else:
                record(chat_id, uid, "loss")

        await msg.reply_text(
            t(
                chat_id, "number_win",
                name=uname(user), number=number, attempts=attempts,
                points=points, bonus=t(chat_id, "bonus") if fast else "",
            )
        )
        return

    if guess < number:
        game["lo"] = max(game["lo"], guess + 1)
        head = t(chat_id, "higher")
    else:
        game["hi"] = min(game["hi"], guess - 1)
        head = t(chat_id, "lower")

    diff = abs(guess - number)
    heat = next(t(chat_id, key) for limit, key in HEAT if diff <= limit)
    tail = t(chat_id, "hint_tail", lo=game["lo"], hi=game["hi"], n=game["attempts"])

    arm(context.application, chat_id, game, NUMBER_TTL)
    await msg.reply_text(f"{head} {heat}\n{tail}")


# ───────────────────────────── ✊ Tosh-Qaychi-Qog'oz ─────────────────────────────

RSP_CHOICES = {"rock": "rsp_rock", "scissors": "rsp_scissors", "paper": "rsp_paper"}
RSP_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}


def rsp_lobby_text(chat_id, game):
    names = list(game["names"].values())
    lines = [f"🙋 {n}" for n in names] + ["⬜ …"] * (game["count"] - len(names))
    return t(
        chat_id, "rsp_lobby",
        current=len(names), count=game["count"], players="\n".join(lines),
    )


def rsp_join_kb(chat_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(chat_id, "btn_join"), callback_data="rj")
    ]])


def rsp_choice_kb(chat_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t(chat_id, label), callback_data=f"rp:{key}")
        for key, label in RSP_CHOICES.items()
    ]])


def rsp_choose_text(chat_id, game):
    lines = [
        ("✅ " if uid in game["choices"] else "⌛ ") + name
        for uid, name in game["names"].items()
    ]
    return t(
        chat_id, "rsp_choose",
        players="\n".join(lines), current=len(game["choices"]), count=game["count"],
    )


async def cb_rsp_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = game_key(q)
    game = active(q, "rsp")

    if not game or game["state"] != "setup":
        await q.answer(t(chat_id, "gone"), show_alert=True)
        return
    if q.from_user.id != game["owner"]:
        await q.answer(t(chat_id, "only_owner"), show_alert=True)
        return

    count = int(q.data.split(":", 1)[1])
    game["count"] = count
    game["state"] = "lobby"

    await q.answer()
    await edit(context.bot, chat_id, game["msg_id"], rsp_lobby_text(chat_id, game), rsp_join_kb(chat_id))
    arm(context.application, chat_id, game, RSP_LOBBY_TTL)


async def cb_rsp_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = game_key(q)
    user = q.from_user
    game = active(q, "rsp")

    if not game or game["state"] != "lobby":
        await q.answer(t(chat_id, "gone"), show_alert=True)
        return
    if user.id in game["names"]:
        await q.answer(t(chat_id, "rsp_already"), show_alert=True)
        return

    if await fsub_block_cb(q, context):
        return

    save_user(user)
    game["names"][user.id] = uname(user)
    await q.answer()

    if len(game["names"]) >= game["count"]:
        game["state"] = "choose"
        await edit(context.bot, chat_id, game["msg_id"], rsp_choose_text(chat_id, game), rsp_choice_kb(chat_id))
        arm(context.application, chat_id, game, RSP_CHOOSE_TTL)
    else:
        await edit(context.bot, chat_id, game["msg_id"], rsp_lobby_text(chat_id, game), rsp_join_kb(chat_id))
        arm(context.application, chat_id, game, RSP_LOBBY_TTL)


async def cb_rsp_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = game_key(q)
    user = q.from_user
    game = active(q, "rsp")

    if not game or game["state"] != "choose":
        await q.answer(t(chat_id, "gone"), show_alert=True)
        return
    if user.id not in game["names"]:
        await q.answer(t(chat_id, "not_player"), show_alert=True)
        return
    if user.id in game["choices"]:
        await q.answer(t(chat_id, "rsp_already_choice"), show_alert=True)
        return

    choice = q.data.split(":", 1)[1]
    game["choices"][user.id] = choice
    await q.answer(t(chat_id, "rsp_picked", choice=t(chat_id, RSP_CHOICES[choice])))

    if len(game["choices"]) >= game["count"]:
        await finish_rsp(context, chat_id, game)
    else:
        await edit(context.bot, chat_id, game["msg_id"], rsp_choose_text(chat_id, game), rsp_choice_kb(chat_id))
        arm(context.application, chat_id, game, RSP_CHOOSE_TTL)


def rsp_winners(choices):
    """G'oliblar ro'yxati (durang bo'lsa bo'sh) va natija turi."""
    values = set(choices.values())
    if len(values) == 1:
        return [], "same"
    if len(values) == 3:
        return [], "three"
    a, b = tuple(values)
    win = a if RSP_BEATS[a] == b else b
    return [uid for uid, c in choices.items() if c == win], "win"


async def finish_rsp(context, chat_id, game):
    end_game(chat_id, game)
    choices = game["choices"]
    names = game["names"]
    winners, kind = rsp_winners(choices)

    for uid in choices:
        if kind != "win":
            record(chat_id, uid, "draw")
        elif uid in winners:
            record(chat_id, uid, "win", RSP_WIN_PTS)
        else:
            record(chat_id, uid, "loss")

    lines = []
    for uid, choice in choices.items():
        mark = "🏆" if uid in winners else "▫️"
        lines.append(f"{mark} {names[uid]} — {t(chat_id, RSP_CHOICES[choice])}")

    if kind == "win":
        result = t(chat_id, "rsp_winner", names=", ".join(names[u] for u in winners), points=RSP_WIN_PTS)
    elif kind == "same":
        result = t(chat_id, "rsp_draw_same")
    else:
        result = t(chat_id, "rsp_draw_three")

    await edit(
        context.bot, chat_id, game["msg_id"],
        t(chat_id, "rsp_result", players="\n".join(lines), result=result),
        InlineKeyboardMarkup([again_row(chat_id)]),
    )


# ───────────────────────────── ❌⭕ XO ─────────────────────────────

XO_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]
MARK = {"X": "❌", "O": "⭕"}
WIN_MARK = {"X": "❎", "O": "🅾️"}


def xo_winner(board):
    for line in XO_LINES:
        a, b, c = line
        if board[a] and board[a] == board[b] == board[c]:
            return board[a], line
    return None, ()


def xo_text(chat_id, game, key="xo_board", **kwargs):
    names, seat = game["names"], game["seat"]
    return t(chat_id, key, x=names[seat["X"]], o=names[seat["O"]], **kwargs)


def xo_keyboard(chat_id, game, finished=False, line=()):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            cell = game["board"][i]
            if cell:
                label = (WIN_MARK if i in line else MARK)[cell]
                data = "noop"
            else:
                label = "⬜"
                data = "noop" if finished else f"xm:{i}"
            row.append(InlineKeyboardButton(label, callback_data=data))
        rows.append(row)
    if finished:
        rows.append(again_row(chat_id))
    return InlineKeyboardMarkup(rows)


def xo_turn_text(chat_id, game):
    turn = game["turn"]
    return xo_text(
        chat_id, game, "xo_board",
        mark=MARK[turn], turn=game["names"][game["seat"][turn]], seconds=XO_MOVE_TTL,
    )


async def cb_xo_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = game_key(q)
    user = q.from_user
    game = active(q, "xo")

    if not game or game["state"] != "lobby":
        await q.answer(t(chat_id, "gone"), show_alert=True)
        return
    if user.id == game["owner"]:
        await q.answer(t(chat_id, "xo_own"), show_alert=True)
        return

    if await fsub_block_cb(q, context):
        return

    save_user(user)
    game["names"][user.id] = uname(user)

    # Kim birinchi yurishini tasodifiy aniqlaymiz (X boshlaydi)
    ids = [game["owner"], user.id]
    random.shuffle(ids)
    game["seat"] = {"X": ids[0], "O": ids[1]}
    game["state"] = "play"
    game["turn"] = "X"

    await q.answer()
    await edit(context.bot, chat_id, game["msg_id"], xo_turn_text(chat_id, game), xo_keyboard(chat_id, game))
    arm(context.application, chat_id, game, XO_MOVE_TTL)


async def cb_xo_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = game_key(q)
    user = q.from_user
    game = active(q, "xo")

    if not game or game["state"] != "play":
        await q.answer(t(chat_id, "gone"), show_alert=True)
        return

    seat = game["seat"]
    if user.id not in seat.values():
        await q.answer(t(chat_id, "not_player"), show_alert=True)
        return
    if seat[game["turn"]] != user.id:
        await q.answer(t(chat_id, "xo_not_turn"), show_alert=True)
        return

    idx = int(q.data.split(":", 1)[1])
    board = game["board"]
    if board[idx]:
        await q.answer(t(chat_id, "xo_taken"), show_alert=True)
        return

    mark = game["turn"]
    board[idx] = mark
    await q.answer()

    winner, line = xo_winner(board)

    if winner:
        loser = "O" if winner == "X" else "X"
        end_game(chat_id, game)
        record(chat_id, seat[winner], "win", XO_WIN_PTS)
        record(chat_id, seat[loser], "loss")
        text = xo_text(
            chat_id, game, "xo_win",
            mark=MARK[winner], winner=game["names"][seat[winner]], points=XO_WIN_PTS,
        )
        await edit(context.bot, chat_id, game["msg_id"], text, xo_keyboard(chat_id, game, True, line))
        return

    if all(board):
        end_game(chat_id, game)
        record(chat_id, seat["X"], "draw", XO_DRAW_PTS)
        record(chat_id, seat["O"], "draw", XO_DRAW_PTS)
        text = xo_text(chat_id, game, "xo_draw", points=XO_DRAW_PTS)
        await edit(context.bot, chat_id, game["msg_id"], text, xo_keyboard(chat_id, game, True))
        return

    game["turn"] = "O" if mark == "X" else "X"
    await edit(context.bot, chat_id, game["msg_id"], xo_turn_text(chat_id, game), xo_keyboard(chat_id, game))
    arm(context.application, chat_id, game, XO_MOVE_TTL)


#   6. Oxirida kim qancha yutgani/yutqazgani {mention} bilan chiqadi.

CRASH_MIN_BET = 50          # minimal depozit ($)
CRASH_STEP = 50             # ➕ tugmasi har bosilganda qo'shiladigan summa ($)
CRASH_COUNTDOWN = 20        # birinchi o'yinchi qo'shilgach teskari sanoq (soniya)
CRASH_LOBBY_TTL = 120       # hech kim qo'shilmasa o'yin bekor bo'ladigan vaqt (soniya)
CRASH_GROWTH = 0.10         # asosiy koeffitsiyent o'sish tezligi
CRASH_RTP = 0.97            # 0.97 → uzoq muddatda ~3% bot foydasi
CRASH_MAX_MULT = 100.0      # eng katta koeffitsiyent
CRASH_TICK = 1.0            # owner panelda 0.6–1.6 soniya oralig'ida sozlanadi
CRASH_ENABLED = True
CRASH_GROUP_RESTRICT = False
CRASH_LIST_LIMIT = 25       # xabarda ko'rsatiladigan o'yinchilar soni (ro'yxat boshiga)
_CRASH_RNG = secrets.SystemRandom()


def crash_config_set(key, value):
    c = db()
    c.execute(
        "INSERT INTO crash_config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(key), str(value)),
    )
    c.commit()


def load_crash_config():
    global CRASH_ENABLED, CRASH_MIN_BET, CRASH_TICK, CRASH_GROUP_RESTRICT
    c = db()
    rows = dict(c.execute("SELECT key, value FROM crash_config").fetchall())
    CRASH_ENABLED = rows.get("enabled", "1") == "1"
    try:
        CRASH_MIN_BET = max(1, int(rows.get("min_bet", "50")))
    except (TypeError, ValueError):
        CRASH_MIN_BET = 50
    try:
        CRASH_TICK = min(1.6, max(0.6, round(float(rows.get("tick", "1.0")), 1)))
    except (TypeError, ValueError):
        CRASH_TICK = 1.0
    CRASH_GROUP_RESTRICT = rows.get("group_restrict", "0") == "1"


def crash_growth_rate():
    # 1.0 s — standart tezlik; 0.6 s tezroq, 1.6 s sekinroq koeffitsiyent.
    return CRASH_GROWTH / CRASH_TICK


def crash_group_allowed(chat_id):
    if not CRASH_GROUP_RESTRICT:
        return True
    if is_inline_key(chat_id):
        # Faqat ulangan guruhlar rejimida shaxsiy yozishmadagi Crash ham yopiq.
        return False
    return db().execute(
        "SELECT 1 FROM crash_groups WHERE chat_id = ?", (int(chat_id),)
    ).fetchone() is not None

CRASH_TEXT = {
    "uz": {
        "btn": "🚀 Crash",
        "lobby": (
            "🚀 <b>CRASH</b>\n\n"
            "Roket uchadi va koeffitsiyent oshib boradi. Portlashdan oldin pulni olishga ulguring!\n\n"
            "💵 Minimal depozit: <b>{min}$</b>\n\n"
            "👇 Qo‘shiling — birinchi o‘yinchi kirganidan 20 soniya o‘tib raund boshlanadi."
        ),
        "count": (
            "🚀 <b>CRASH</b>\n\n"
            "⏳ Birinchi o‘yinchi qo‘shilgach, raund 20 soniyada boshlanadi.\n\n"
            "👥 O‘yinchilar:\n{players}\n\n"
            "➕ Depozitni oshiring (+{step}$) yoki 🔽 {min}$ ga tushiring."
        ),
        "fly": "🚀 <b>x{mult}</b>\n\n💰 Portlashdan oldin pulni oling!",
        "fly_media": "🚀 <b>CRASH</b>\n\n💰 Portlashdan oldin pulni oling!",
        "crashed_short": "💥 <b>Portlash: x{cp}</b>",
        "result": (
            "💥 <b>Roket x{cp} da portladi!</b>\n\n"
            "🏆 <b>Yutganlar:</b>\n{winners}\n\n"
            "😔 <b>Yutqazganlar:</b>\n{losers}"
        ),
        "win_line": "✅ {mention}\n    💵 Tikdi: <b>{bet}$</b> · x{mult} → 🏆 Foyda: <b>+{profit}$</b> (olindi {payout}$)",
        "lose_line": "❌ {mention}\n    💵 Tikdi: <b>{bet}$</b> · 💔 Yutqazdi: <b>−{bet}$</b>",
        "cancelled": "🚀 <b>CRASH</b>\n\n😕 O‘yin bekor qilindi: depozit uchun mablag‘ yetmadi.",
        "b_join": "✅ Qo‘shilish",
        "b_plus": "➕ Depozit +{step}$",
        "b_min": "🔽 Minimal {min}$",
        "b_cash": "💰 Pulni olish",
        "joined": "✅ Qo‘shildingiz! Depozit: {bet}$",
        "already": "Siz allaqachon qo‘shilgansiz.",
        "no_funds": "💸 Balansingiz yetarli emas (kamida {min}$ kerak).",
        "no_more": "💸 Balansingizda bundan ortiq pul yo‘q ({bal}$).",
        "closed": "⌛ Bu raund uchun vaqt tugadi.",
        "not_in": "Avval «Qo‘shilish» tugmasini bosing.",
        "not_in_round": "Siz bu raundda qatnashmayapsiz.",
        "bet_set": "💵 Depozit: {bet}$",
        "cashed": "✅ x{mult} da oldingiz: +{profit}$",
        "already_cashed": "Siz pulni allaqachon olgansiz.",
        "late": "💥 Kech qoldingiz — roket portladi!",
        "dropped": "\n\n⚠️ Mablag‘ yetmagani uchun chiqarildi: {names}",
        "none": "—",
        "error": "⚠️ Xatolik. Qayta urinib ko‘ring.",
    },
    "eng": {
        "btn": "🚀 Crash",
        "lobby": (
            "🚀 <b>CRASH</b>\n\n"
            "The rocket takes off and the multiplier keeps growing. Cash out before it crashes!\n\n"
            "💵 Minimum deposit: <b>{min}$</b>\n\n"
            "👇 Join — the round starts 20 seconds after the first player joins."
        ),
        "count": (
            "🚀 <b>CRASH</b>\n\n"
            "⏳ The round starts 20 seconds after the first player joins.\n\n"
            "👥 Players:\n{players}\n\n"
            "➕ Raise your deposit (+{step}$) or 🔽 drop it to {min}$."
        ),
        "fly": "🚀 <b>x{mult}</b>\n\n💰 Cash out before it crashes!",
        "fly_media": "🚀 <b>CRASH</b>\n\n💰 Cash out before it crashes!",
        "crashed_short": "💥 <b>Crashed at x{cp}</b>",
        "result": (
            "💥 <b>The rocket crashed at x{cp}!</b>\n\n"
            "🏆 <b>Winners:</b>\n{winners}\n\n"
            "😔 <b>Losers:</b>\n{losers}"
        ),
        "win_line": "✅ {mention}\n    💵 Bet: <b>{bet}$</b> · x{mult} → 🏆 Profit: <b>+{profit}$</b> (received {payout}$)",
        "lose_line": "❌ {mention}\n    💵 Bet: <b>{bet}$</b> · 💔 Lost: <b>−{bet}$</b>",
        "cancelled": "🚀 <b>CRASH</b>\n\n😕 Round cancelled: not enough funds for the deposit.",
        "b_join": "✅ Join",
        "b_plus": "➕ Deposit +{step}$",
        "b_min": "🔽 Minimum {min}$",
        "b_cash": "💰 Cash out",
        "joined": "✅ You joined! Deposit: {bet}$",
        "already": "You have already joined.",
        "no_funds": "💸 Not enough balance (at least {min}$ needed).",
        "no_more": "💸 You don't have more money than that ({bal}$).",
        "closed": "⌛ Time is up for this round.",
        "not_in": "Press “Join” first.",
        "not_in_round": "You are not in this round.",
        "bet_set": "💵 Deposit: {bet}$",
        "cashed": "✅ Cashed out at x{mult}: +{profit}$",
        "already_cashed": "You have already cashed out.",
        "late": "💥 Too late — the rocket crashed!",
        "dropped": "\n\n⚠️ Removed (not enough funds): {names}",
        "none": "—",
        "error": "⚠️ Error. Please try again.",
    },
    "ru": {
        "btn": "🚀 Crash",
        "lobby": (
            "🚀 <b>CRASH</b>\n\n"
            "Ракета взлетает, множитель растёт. Успейте забрать деньги до взрыва!\n\n"
            "💵 Минимальный депозит: <b>{min}$</b>\n\n"
            "👇 Войдите в игру — раунд начнётся через 20 секунд после входа первого игрока."
        ),
        "count": (
            "🚀 <b>CRASH</b>\n\n"
            "⏳ Раунд начнётся через 20 секунд после входа первого игрока.\n\n"
            "👥 Игроки:\n{players}\n\n"
            "➕ Увеличьте депозит (+{step}$) или 🔽 снизьте до {min}$."
        ),
        "fly": "🚀 <b>x{mult}</b>\n\n💰 Заберите деньги до взрыва!",
        "fly_media": "🚀 <b>CRASH</b>\n\n💰 Заберите деньги до взрыва!",
        "crashed_short": "💥 <b>Взрыв на x{cp}</b>",
        "result": (
            "💥 <b>Ракета взорвалась на x{cp}!</b>\n\n"
            "🏆 <b>Выиграли:</b>\n{winners}\n\n"
            "😔 <b>Проиграли:</b>\n{losers}"
        ),
        "win_line": "✅ {mention}\n    💵 Ставка: <b>{bet}$</b> · x{mult} → 🏆 Прибыль: <b>+{profit}$</b> (получено {payout}$)",
        "lose_line": "❌ {mention}\n    💵 Ставка: <b>{bet}$</b> · 💔 Проигрыш: <b>−{bet}$</b>",
        "cancelled": "🚀 <b>CRASH</b>\n\n😕 Раунд отменён: не хватило средств на депозит.",
        "b_join": "✅ Войти",
        "b_plus": "➕ Депозит +{step}$",
        "b_min": "🔽 Минимум {min}$",
        "b_cash": "💰 Забрать",
        "joined": "✅ Вы в игре! Депозит: {bet}$",
        "already": "Вы уже в игре.",
        "no_funds": "💸 Недостаточно средств (нужно минимум {min}$).",
        "no_more": "💸 На балансе нет больше ({bal}$).",
        "closed": "⌛ Время этого раунда истекло.",
        "not_in": "Сначала нажмите «Войти».",
        "not_in_round": "Вы не участвуете в этом раунде.",
        "bet_set": "💵 Депозит: {bet}$",
        "cashed": "✅ Забрали на x{mult}: +{profit}$",
        "already_cashed": "Вы уже забрали деньги.",
        "late": "💥 Опоздали — ракета взорвалась!",
        "dropped": "\n\n⚠️ Исключены (не хватило средств): {names}",
        "none": "—",
        "error": "⚠️ Ошибка. Попробуйте ещё раз.",
    },
    "kz": {
        "btn": "🚀 Crash",
        "lobby": (
            "🚀 <b>CRASH</b>\n\n"
            "Зымыран ұшады, коэффициент өсе береді. Жарылғанға дейін ақшаны алып үлгеріңіз!\n\n"
            "💵 Ең аз депозит: <b>{min}$</b>\n\n"
            "👇 Қосылыңыз — раунд бірінші ойыншы кіргеннен кейін 20 секундтан соң басталады."
        ),
        "count": (
            "🚀 <b>CRASH</b>\n\n"
            "⏳ Раунд бірінші ойыншы кіргеннен кейін 20 секундтан соң басталады.\n\n"
            "👥 Ойыншылар:\n{players}\n\n"
            "➕ Депозитті көбейтіңіз (+{step}$) немесе 🔽 {min}$ дейін түсіріңіз."
        ),
        "fly": "🚀 <b>x{mult}</b>\n\n💰 Жарылғанға дейін ақшаны алыңыз!",
        "fly_media": "🚀 <b>CRASH</b>\n\n💰 Жарылғанға дейін ақшаны алыңыз!",
        "crashed_short": "💥 <b>Жарылу: x{cp}</b>",
        "result": (
            "💥 <b>Зымыран x{cp} кезінде жарылды!</b>\n\n"
            "🏆 <b>Ұтқандар:</b>\n{winners}\n\n"
            "😔 <b>Ұтылғандар:</b>\n{losers}"
        ),
        "win_line": "✅ {mention}\n    💵 Салды: <b>{bet}$</b> · x{mult} → 🏆 Пайда: <b>+{profit}$</b> (алынды {payout}$)",
        "lose_line": "❌ {mention}\n    💵 Салды: <b>{bet}$</b> · 💔 Ұтылды: <b>−{bet}$</b>",
        "cancelled": "🚀 <b>CRASH</b>\n\n😕 Раунд тоқтатылды: депозитке қаражат жетпеді.",
        "b_join": "✅ Қосылу",
        "b_plus": "➕ Депозит +{step}$",
        "b_min": "🔽 Ең аз {min}$",
        "b_cash": "💰 Ақшаны алу",
        "joined": "✅ Қосылдыңыз! Депозит: {bet}$",
        "already": "Сіз қосылып қойғансыз.",
        "no_funds": "💸 Баланс жеткіліксіз (кемінде {min}$ керек).",
        "no_more": "💸 Балансыңызда одан көп ақша жоқ ({bal}$).",
        "closed": "⌛ Бұл раундтың уақыты бітті.",
        "not_in": "Алдымен «Қосылу» батырмасын басыңыз.",
        "not_in_round": "Сіз бұл раундқа қатыспайсыз.",
        "bet_set": "💵 Депозит: {bet}$",
        "cashed": "✅ x{mult} кезінде алдыңыз: +{profit}$",
        "already_cashed": "Сіз ақшаны алып қойғансыз.",
        "late": "💥 Кеш қалдыңыз — зымыран жарылды!",
        "dropped": "\n\n⚠️ Қаражат жетпегендіктен шығарылды: {names}",
        "none": "—",
        "error": "⚠️ Қате. Қайта көріңіз.",
    },
}



# ───────────────────────────── 🚀 Crash animatsiyasi (GIF) ─────────────────────────────
# Portlash nuqtasi (cp) raund boshida ma'lum bo'lgani uchun butun parvoz oldindan,
# o'yin vaqtiga (crash_mult) moslab chiziladi. Faqat Pillow kerak; bo'lmasa — matnli rejim.

import io

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except Exception:  # noqa: BLE001
    PIL_OK = False

ANIM_W, ANIM_H = 480, 270
ANIM_FPS = 20
ANIM_MAX_SECONDS = 50.0          # shundan uzun parvoz chizilmaydi (x100 ≈ 46s)
ANIM_LAG = 0.0                   # GIF yuborilgach server koeffitsiyenti kechikmasin
_ANIM_SS = 2                     # supersampling (silliq chiziqlar uchun)

_FONT_CACHE: dict = {}


def _anim_font(size):
    f = _FONT_CACHE.get(size)
    if f:
        return f
    for path in (
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arialbd.ttf",
    ):
        try:
            f = ImageFont.truetype(path, size)
            break
        except Exception:  # noqa: BLE001
            f = None
    if f is None:
        try:
            f = ImageFont.load_default(size=size)
        except Exception:  # noqa: BLE001
            f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def _plane_sprite(px=64):
    """Original samolyot (yon ko'rinish, o'ngga qaragan). 8x kattalikda chizilib kichraytiriladi."""
    k = 8
    w, h = px * k, int(px * 0.62) * k
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cy = h // 2
    body = (236, 242, 255, 255)
    shade = (170, 190, 230, 255)
    accent = (255, 176, 32, 255)
    glass = (60, 190, 255, 255)
    # dum qanoti
    d.polygon([(w*0.10, cy-h*0.40), (w*0.22, cy-h*0.40), (w*0.30, cy-h*0.02), (w*0.12, cy-h*0.02)], fill=accent)
    # orqa gorizontal stabilizator
    d.polygon([(w*0.10, cy+h*0.02), (w*0.30, cy+h*0.02), (w*0.26, cy+h*0.14), (w*0.08, cy+h*0.14)], fill=shade)
    # asosiy qanot (pastga)
    d.polygon([(w*0.42, cy+h*0.04), (w*0.66, cy+h*0.04), (w*0.50, cy+h*0.46), (w*0.36, cy+h*0.46)], fill=shade)
    # fyuzelyaj
    d.rounded_rectangle([w*0.06, cy-h*0.13, w*0.94, cy+h*0.17], radius=int(h*0.15), fill=body)
    # burun
    d.ellipse([w*0.78, cy-h*0.13, w*0.98, cy+h*0.17], fill=body)
    # kabina oynasi
    d.rounded_rectangle([w*0.60, cy-h*0.11, w*0.78, cy+h*0.02], radius=int(h*0.05), fill=glass)
    # chiziq (akcent)
    d.rectangle([w*0.20, cy+h*0.03, w*0.58, cy+h*0.07], fill=accent)
    # propeller
    d.rounded_rectangle([w*0.965, cy-h*0.30, w*0.99, cy+h*0.34], radius=int(h*0.02), fill=(255, 255, 255, 200))
    return im.resize((px, h // k), Image.LANCZOS)


_PLANE = None


def _get_plane():
    global _PLANE
    if _PLANE is None:
        _PLANE = _plane_sprite()
    return _PLANE


def _mult_color(m):
    if m < 2.0:
        return (255, 255, 255)
    if m < 5.0:
        return (120, 220, 255)
    if m < 10.0:
        return (180, 140, 255)
    return (255, 200, 60)


def _nice_step(span, target=4):
    raw = span / target
    for s in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100):
        if s >= raw:
            return s
    return 100


def _scene(t, cp, growth, state, fly_p=0.0):
    """Bitta kadr. state: 'fly' | 'out' (uchib ketish) | 'gone'."""
    S = _ANIM_SS
    W, H = ANIM_W * S, ANIM_H * S
    img = Image.new("RGB", (W, H), (11, 15, 32))
    d = ImageDraw.Draw(img, "RGBA")

    # gradient fon
    for y in range(0, H, 4):
        v = y / H
        d.rectangle([0, y, W, y + 4], fill=(int(11 + 12 * v), int(15 + 12 * v), int(32 + 26 * v)))

    left, right = 46 * S, W - 18 * S
    top, bottom = 22 * S, H - 28 * S
    pw, ph = right - left, bottom - top

    # Grafik masshtabi butun raund davomida o'zgarmaydi: samolyot chapdan
    # o'ngga haqiqiy vaqt bilan yuradi, egri chiziq esa real koeffitsiyentga mos o'sadi.
    t_crash = math.log(cp) / growth if cp > 1.0 else 0.0
    t_eff = min(max(t, 0.0), t_crash)
    m_now = min(cp, math.exp(growth * t_eff))

    # Har raund uchun yakuniy vaqt/koeffitsiyentga mos bir xil koordinata masshtabi.
    x_rng = max(0.5, t_crash * 1.06)
    y_rng = max(1.3, 1.0 + (cp - 1.0) * 1.12)

    def px(tt):
        return left + (tt / x_rng) * pw

    def py(mm):
        return bottom - ((mm - 1.0) / (y_rng - 1.0)) * ph

    # to'r va chap shkala
    step = _nice_step(y_rng - 1.0)
    g = 1.0
    gl = []
    while g <= y_rng + 1e-9:
        gl.append(g)
        g = round(g + step, 6)
    for gv in gl:
        yy = py(gv)
        d.line([(left, yy), (right, yy)], fill=(255, 255, 255, 22), width=S)
        lab = f"{gv:g}x"
        d.text((8 * S, yy - 7 * S), lab, font=_anim_font(11 * S), fill=(150, 160, 190, 255))
    xs = _nice_step(x_rng, 5)
    xv = 0.0
    while xv <= x_rng + 1e-9:
        xx = px(xv)
        d.line([(xx, top), (xx, bottom)], fill=(255, 255, 255, 14), width=S)
        xv += xs
    d.line([(left, bottom), (right, bottom)], fill=(255, 255, 255, 60), width=S)
    d.line([(left, top), (left, bottom)], fill=(255, 255, 255, 60), width=S)

    # egri chiziq
    n = max(8, int(40 * min(1.0, t_eff / 6.0 + 0.2)) + 20)
    pts = [(px(t_eff * i / n), py(math.exp(growth * t_eff * i / n))) for i in range(n + 1)]
    tip = pts[-1]
    poly = [(left, bottom)] + pts + [(tip[0], bottom)]
    d.polygon(poly, fill=(255, 45, 85, 70))
    d.line(pts, fill=(255, 60, 95, 255), width=3 * S, joint="curve")

    # samolyot yo'nalishi (egri chiziq urinmasi)
    dm = growth * m_now  # dm/dt
    dx = pw / x_rng
    dy = (dm / (y_rng - 1.0)) * ph
    ang = math.degrees(math.atan2(dy, dx))
    ang = min(ang, 48.0)

    plane = _get_plane().resize(
        (_get_plane().width * S // 1, _get_plane().height * S // 1), Image.LANCZOS
    ) if S != 1 else _get_plane()

    cx, cy_ = tip
    if state == "out":
        # chiqib ketish: tezlanib kadrdan uchib chiqadi
        run = (fly_p ** 1.6) * 1.3 * W
        cx += run * math.cos(math.radians(ang))
        cy_ -= run * math.sin(math.radians(ang))
    if state != "gone":
        rot = plane.rotate(ang, resample=Image.BICUBIC, expand=True)
        img.paste(rot, (int(cx - rot.width * 0.62), int(cy_ - rot.height * 0.5)), rot)

    # katta koeffitsiyent
    if state == "fly":
        txt, col = f"x{math.floor(m_now * 100) / 100:.2f}", _mult_color(m_now)
        big = _anim_font(58 * S)
    else:
        txt, col = f"x{cp:.2f}", (255, 70, 90)
        big = _anim_font(58 * S)
    bb = d.textbbox((0, 0), txt, font=big)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx = left + (pw - tw) / 2
    ty = top + (ph - th) / 2 - 24 * S
    d.text((tx + 2 * S, ty + 2 * S), txt, font=big, fill=(0, 0, 0, 140))
    d.text((tx, ty), txt, font=big, fill=col + (255,))
    if state != "fly":
        sub = "CRASH"
        sf = _anim_font(20 * S)
        sb = d.textbbox((0, 0), sub, font=sf)
        d.text((left + (pw - (sb[2] - sb[0])) / 2, ty + th + 14 * S), sub, font=sf, fill=(255, 120, 135, 255))

    return img.reduce(S)


def render_crash_gif(cp, growth=None, fps=ANIM_FPS):
    """Parvozning to'liq GIF'ini (bytes) qaytaradi yoki None. Og'ir — thread'da chaqiring."""
    if not PIL_OK:
        return None
    growth = crash_growth_rate() if growth is None else growth
    t_crash = math.log(cp) / growth if cp > 1.0 else 0.0
    t_draw = min(t_crash, ANIM_MAX_SECONDS)
    dt = 1.0 / fps

    frames, durs = [], []
    n = int(t_draw / dt)
    for i in range(n + 1):
        frames.append(_scene(i * dt, cp, growth, "fly"))
        durs.append(int(dt * 1000))
    # oxirgi "fly" kadrni portlash vaqtigacha davom ettirish (agar chizish cheklangan bo'lsa)
    if t_crash > t_draw:
        durs[-1] = int((t_crash - t_draw) * 1000) + int(dt * 1000)
    else:
        rest = t_crash - n * dt
        if rest > 0.001:
            frames.append(_scene(t_crash, cp, growth, "fly"))
            durs.append(max(20, int(rest * 1000)))

    # uchib ketish
    out_n = 12
    for i in range(1, out_n + 1):
        frames.append(_scene(t_crash, cp, growth, "out", i / out_n))
        durs.append(int(dt * 1000))
    # Yakuniy portlash kadri qisqa ushlab turiladi; GIF loop qilmaydi,
    # shuning uchun animatsiya qayta boshidan aylanib ketmaydi.
    frames.append(_scene(t_crash, cp, growth, "gone"))
    durs.append(2_000)

    # umumiy palitra
    sample = [frames[0], frames[len(frames) // 3], frames[len(frames) // 2], frames[-1]]
    strip = Image.new("RGB", (ANIM_W, ANIM_H * len(sample)))
    for i, f in enumerate(sample):
        strip.paste(f, (0, i * ANIM_H))
    pal = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qf = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]

    buf = io.BytesIO()
    # `loop` parametrini bermaslik — GIF bir marta ijro etiladi va
    # portlash kadrida to'xtaydi (loop=0 esa cheksiz takrorlaydi).
    qf[0].save(
        buf, format="GIF", save_all=True, append_images=qf[1:],
        duration=durs, optimize=False, disposal=1,
    )
    return buf.getvalue()


_RENDER_SEM = asyncio.Semaphore(2)   # bir vaqtda ko'pi bilan 2 ta GIF chiziladi (server yuklanmasligi uchun)
CRASH_TICK_MEDIA = 1.0               # GIF captionidagi o'yinchilar holatini tezroq yangilash
CRASH_CAPTION_MAX = 1000             # Telegram caption limiti 1024


def _safe_render(cp):
    try:
        return render_crash_gif(cp)
    except Exception:  # noqa: BLE001
        logger.exception("Crash animatsiyasini chizib bo'lmadi (cp=%s)", cp)
        return None


async def _render_async(cp):
    async with _RENDER_SEM:
        return await asyncio.to_thread(_safe_render, cp)


def crash_fit(builder, limit=None, max_len=None):
    """builder(lim) → matn. Matn limitdan oshmaguncha ro'yxatni qisqartiradi."""
    lim = CRASH_LIST_LIMIT if limit is None else limit
    max_len = CRASH_CAPTION_MAX if max_len is None else max_len
    while True:
        text = builder(lim)
        if len(text) <= max_len or lim <= 1:
            return text
        lim = max(1, lim // 2)


CRASH_MIN_EDIT_GAP = 1.0   # koeffitsiyent taxminan har soniyada yangilanadi; flood-limitdan saqlaydi


async def cr_edit(bot, chat_id, game, text, kb=None):
    """Crash parvoz xabarini yangilaydi.

    Telegram flood-limitiga (RetryAfter) tushsak, shu muddat tugaguncha tahrirlarni
    o'tkazib yuboramiz — raund esa to'xtamaydi va natija baribir chiqadi."""
    now = time.monotonic()
    if now < game.get("edit_block_until", 0.0):
        return False
    if now - game.get("last_edit", 0.0) < CRASH_MIN_EDIT_GAP:
        return False
    game["last_edit"] = now
    target = msg_target(chat_id, game["msg_id"])
    try:
        if game.get("media"):
            await bot.edit_message_caption(
                caption=text, reply_markup=kb, parse_mode=ParseMode.HTML, **target,
            )
        else:
            await bot.edit_message_text(
                text, reply_markup=kb, parse_mode=ParseMode.HTML, **target,
            )
        return True
    except RetryAfter as e:
        wait = float(getattr(e, "retry_after", 5) or 5)
        game["edit_block_until"] = time.monotonic() + wait + 0.5
        logger.warning("Crash: flood-limit, %.0f s tahrir to'xtatildi", wait)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            logger.warning("Crash tahrir xatosi: %s", e)
    except TelegramError as e:
        logger.warning("Crash tahrir xatosi: %s", e)
    return False


async def _send_retry(call, attempts=6):
    """RetryAfter bo'lsa kutib, qayta urinadi (natija xabari yo'qolib ketmasin)."""
    last = None
    for _ in range(attempts):
        try:
            return await call()
        except RetryAfter as e:
            last = e
            await asyncio.sleep(min(65.0, float(getattr(e, "retry_after", 3) or 3) + 0.5))
        except (TimedOut, NetworkError) as e:
            last = e
            await asyncio.sleep(2.0)
    if last:
        raise last


async def crash_publish_result(bot, chat_id, game, text, kb):
    """Natijani HAR DOIM alohida yangi xabar sifatida chiqaradi (flood bo'lsa ham kutib yuboradi),
    eski parvoz xabarini esa qisqa 'portladi' holatiga o'tkazadi."""
    if is_inline_key(chat_id):
        # Inline xabar egasi bo'lmagan chatga yangi xabar yuborib bo'lmaydi —
        # natija o'yin xabarining o'zida chiqadi.
        async def edit_inline():
            return await bot.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup([again_row(chat_id)]),
                parse_mode=ParseMode.HTML, disable_web_page_preview=True,
                **msg_target(chat_id, None),
            )
        await _send_retry(edit_inline)
        return

    short = cr_t(chat_id, "crashed_short", cp=f"{game['cp']:.2f}")

    async def close_old():
        if game.get("media"):
            await bot.edit_message_caption(
                chat_id=chat_id, message_id=game["msg_id"], caption=short,
                reply_markup=None, parse_mode=ParseMode.HTML,
            )
        else:
            await bot.edit_message_text(
                short, chat_id=chat_id, message_id=game["msg_id"],
                reply_markup=None, parse_mode=ParseMode.HTML,
            )

    async def send_new():
        return await bot.send_message(
            chat_id=chat_id, text=text, reply_markup=kb,
            parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )

    # Avval natijani yuboramiz (eng muhimi), keyin eski xabarni yopamiz.
    await _send_retry(send_new)
    try:
        await _send_retry(close_old, attempts=2)
    except TelegramError as e:
        logger.warning("Crash eski parvoz xabarini yopib bo'lmadi: %s", e)


CRASH_SUMMARY = {
    "uz": "\n\n📊 <b>Jami:</b> {n} o‘yinchi · tikilgan <b>{bets}$</b> · to‘langan <b>{paid}$</b>",
    "eng": "\n\n📊 <b>Total:</b> {n} players · wagered <b>{bets}$</b> · paid out <b>{paid}$</b>",
    "ru": "\n\n📊 <b>Итого:</b> {n} игроков · ставки <b>{bets}$</b> · выплачено <b>{paid}$</b>",
    "kz": "\n\n📊 <b>Барлығы:</b> {n} ойыншы · салынған <b>{bets}$</b> · төленген <b>{paid}$</b>",
}


def cr_summary(chat_id, n, bets, paid):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    return CRASH_SUMMARY.get(lang, CRASH_SUMMARY["uz"]).format(n=n, bets=bets, paid=paid)


def cr_t(chat_id, key, **kwargs):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    text = CRASH_TEXT.get(lang, CRASH_TEXT["uz"]).get(key)
    if text is None:
        text = CRASH_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def crash_point():
    """Roket portlaydigan koeffitsiyent (raund boshida bir marta aniqlanadi)."""
    r = _CRASH_RNG.random()  # [0, 1)
    cp = math.floor(CRASH_RTP / (1.0 - r) * 100) / 100
    return min(CRASH_MAX_MULT, max(1.0, cp))


def crash_mult(elapsed, growth=None):
    """Parvoz boshlanganidan beri `elapsed` soniya o'tgandagi koeffitsiyent."""
    growth = crash_growth_rate() if growth is None else growth
    return math.floor(math.exp(growth * elapsed) * 100) / 100


def crash_payout(bet, mult):
    """Depozit × koeffitsiyent (butun songa, kasr yo'qotilmaydi)."""
    return bet * int(round(mult * 100)) // 100


def crash_mention(uid, player):
    return f'<a href="tg://user?id={uid}">{escape(html.unescape(str(player["name"])))}</a>'


def crash_players_text(chat_id, game, limit=None):
    limit = CRASH_LIST_LIMIT if limit is None else limit
    items = list(game["players"].items())
    if not items:
        return cr_t(chat_id, "none")
    lines = []
    for uid, p in items[:limit]:
        line = f"👤 {crash_mention(uid, p)} — <b>{p['bet']}$</b>"
        if p["cash"] is not None:
            line += f" ✅ x{p['cash']:.2f}"
        lines.append(line)
    if len(items) > limit:
        lines.append(f"… +{len(items) - limit}")
    return "\n".join(lines)


def crash_kb(chat_id, game):
    if game["state"] == "fly":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(cr_t(chat_id, "b_cash"), callback_data="cr:cash")
        ]])
    rows = [[InlineKeyboardButton(cr_t(chat_id, "b_join"), callback_data="cr:join")]]
    if game["state"] == "count":
        rows.append([
            InlineKeyboardButton(cr_t(chat_id, "b_plus", step=CRASH_STEP), callback_data="cr:plus"),
            InlineKeyboardButton(cr_t(chat_id, "b_min", min=CRASH_MIN_BET), callback_data="cr:min"),
        ])
    return InlineKeyboardMarkup(rows)


def crash_fly_text(chat_id, game, mult, limit=None):
    dropped = ""
    if game["dropped"]:
        dropped = cr_t(chat_id, "dropped", names=", ".join(game["dropped"]))
    players = crash_players_text(chat_id, game, limit)
    if game.get("media"):
        return cr_t(chat_id, "fly_media", players=players, dropped=dropped)
    return cr_t(chat_id, "fly", mult=f"{mult:.2f}", players=players, dropped=dropped)


def crash_charge(game):
    """Depozitlarni hamyondan yechadi (atomik). Puli yetmaganlar o'yindan chiqariladi."""
    c = db()
    for uid in list(game["players"]):
        p = game["players"][uid]
        try:
            with c:
                cur = c.execute(
                    "UPDATE user_wallet SET money=money-? WHERE user_id=? AND money>=?",
                    (p["bet"], uid, p["bet"]),
                )
            paid = cur.rowcount == 1
        except sqlite3.Error:
            logger.exception("Crash: depozitni yechib bo'lmadi (user %s)", uid)
            paid = False
        if paid:
            p["paid"] = True
        else:
            game["dropped"].append(crash_mention(uid, p))
            del game["players"][uid]
    game["charged"] = True


def crash_refund(game):
    """Natijalanmagan depozitlarni takroriy to'lovsiz qaytaradi."""
    if not game.get("charged") or game.get("settled"):
        return

    failed = False
    for uid, p in game["players"].items():
        if not p.get("paid") or p.get("cash") is not None:
            continue
        if p.get("refunded", False):
            continue

        try:
            wallet_change(uid, p["bet"])
            p["refunded"] = True
        except Exception:
            failed = True
            logger.exception(
                "Crash: depozitni qaytarib bo'lmadi (user %s)", uid
            )

    if not failed:
        pending = any(
            p.get("paid")
            and p.get("cash") is None
            and not p.get("refunded", False)
            for p in game["players"].values()
        )
        if not pending:
            game["settled"] = True

async def crash_round(app, chat_id, game):
    bot = app.bot
    try:
        # Crash nuqtasi raund boshida aniqlanadi. GIF ishlatilmaydi:
        # bitta oddiy matn xabari tahrirlanadi — Telegram ancha yengil ishlaydi.
        game["cp"] = crash_point()
        game["growth"] = crash_growth_rate()
        game["tick"] = CRASH_TICK

        # Qo'shilish oynasi saqlanadi, ammo har soniyada countdown xabari yuborilmaydi.
        # Shu vaqt ichida o'yinchilar bitta lobby xabaridagi tugmalar orqali qo'shilishi mumkin.
        deadline = time.monotonic() + CRASH_COUNTDOWN
        while True:
            if GAMES.get(chat_id) is not game:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(0.25, remaining))

        if GAMES.get(chat_id) is not game:
            return

        # Depozitlar bir marta yechiladi.
        crash_charge(game)
        if not game["players"]:
            game["state"] = "end"
            end_game(chat_id, game)
            await edit(
                bot, chat_id, game["msg_id"], cr_t(chat_id, "cancelled"),
                None,
            )
            return

        game["t_crash"] = math.log(game["cp"]) / game.get("growth", crash_growth_rate())
        game["t0"] = time.monotonic()
        game["media"] = False
        game["state"] = "fly"

        # Mavjud xabarning o'zi tahrirlanadi; yangi GIF/xabar yuborilmaydi.
        await edit(
            bot, chat_id, game["msg_id"],
            crash_fit(lambda lim: crash_fly_text(chat_id, game, 1.0, lim)),
            crash_kb(chat_id, game),
        )

        # Sikl tez aylanadi (portlash aniq vaqtda bo'lsin), lekin xabar faqat cr_edit ichidagi
        # CRASH_MIN_EDIT_GAP oralig'ida va flood-limit bo'lmaganda tahrirlanadi.
        while True:
            elapsed = time.monotonic() - game["t0"]
            if elapsed >= game["t_crash"]:
                break
            await asyncio.sleep(min(0.4, max(0.05, game["t_crash"] - elapsed)))
            if GAMES.get(chat_id) is not game:
                return  # /stop — depozitlar finally ichida qaytariladi
            elapsed = time.monotonic() - game["t0"]
            if elapsed >= game["t_crash"]:
                break
            mult_now = crash_mult(max(0.0, elapsed), game.get("growth"))
            await cr_edit(
                bot, chat_id, game,
                crash_fit(lambda lim: crash_fly_text(chat_id, game, mult_now, lim)),
                crash_kb(chat_id, game),
            )

        # 4) Portlash va natijalar
        game["state"] = "end"
        game["settled"] = True
        end_game(chat_id, game)

        winners, losers, log_lines = [], [], []
        total_bets = 0
        total_paid = 0
        for uid, p in game["players"].items():
            total_bets += p["bet"]
            mention = crash_mention(uid, p)
            if p["cash"] is not None:
                payout = crash_payout(p["bet"], p["cash"])
                profit = payout - p["bet"]
                total_paid += payout
                winners.append(cr_t(
                    chat_id, "win_line",
                    mention=mention, bet=p["bet"], mult=f"{p['cash']:.2f}",
                    profit=profit, payout=payout,
                ))
                outcome = "win"
                log_lines.append(f"{person_name(uid)}: +{profit}$ (x{p['cash']:.2f})")
            else:
                losers.append(cr_t(chat_id, "lose_line", mention=mention, bet=p["bet"]))
                outcome = "loss"
                log_lines.append(f"{person_name(uid)}: −{p['bet']}$")
            try:
                record(chat_id, uid, outcome, 0)
            except sqlite3.Error:
                logger.exception("Crash: statistikani yozib bo'lmadi (user %s)", uid)

        def _cut(lines, lim):
            if not lines:
                return cr_t(chat_id, "none")
            extra = len(lines) - lim
            shown = lines[:lim] + ([f"… +{extra}"] if extra > 0 else [])
            return "\n".join(shown)

        summary = cr_summary(chat_id, len(game["players"]), total_bets, total_paid)
        result_text = crash_fit(lambda lim: cr_t(
            chat_id, "result", cp=f"{game['cp']:.2f}",
            winners=_cut(winners, lim), losers=_cut(losers, lim),
        ) + summary, limit=None, max_len=3900)
        await crash_publish_result(
            bot, chat_id, game, result_text,
            None,
        )
        await log_money_event(
            bot,
            "🚀 <b>CRASH</b>\n"
            f"Chat: <code>{chat_id}</code>\n"
            f"Portlash: <b>x{game['cp']:.2f}</b>\n" + "\n".join(log_lines),
        )
    except Exception:  # noqa: BLE001 — xato bo'lsa ham foydalanuvchi eski tugmalarda qolmasin
        logger.exception("Crash raundida xato")
        try:
            game["state"] = "end"
            await close_game_message(
                bot, chat_id, game,
                "⚠️ <b>Crash raundida texnik xatolik yuz berdi.</b>\n"
                "Depozit qaytarilishi tekshirilmoqda. Iltimos, yangi raundni qayta boshlang.",
            )
        except Exception:  # noqa: BLE001
            logger.exception("Crash xatosi haqida xabar yuborilmadi")
    finally:
        crash_refund(game)
        was_finished = game.get("state") == "end"
        auto_repeat = bool(game.get("auto_repeat"))
        end_game(chat_id, game)
        if auto_repeat and was_finished and chat_id not in CRASH_STOPPED:
            task = asyncio.create_task(_crash_auto_restart(app, chat_id))
            BG_TASKS.add(task)
            task.add_done_callback(BG_TASKS.discard)


async def cmd_crash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Crash directly with /crash; channel mode automatically repeats rounds."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or chat.type == ChatType.PRIVATE:
        if msg:
            await msg.reply_text("👥 /crash buyrug‘ini guruh yoki kanalda ishlating.")
        return
    chat_id = chat.id
    if not CRASH_ENABLED:
        await msg.reply_text("⛔ Crash o‘yini bot egasi tomonidan vaqtincha o‘chirib qo‘yilgan.")
        return
    if not crash_group_allowed(chat_id):
        await msg.reply_text("⛔ Bu guruh Crash uchun ulanmagan. Bot egasidan guruhni ulashni so‘rang.")
        return
    if GAMES.get(chat_id):
        await msg.reply_text("⚠️ Bu chatda boshqa o‘yin ishlayapti. Avval uni yakunlang.")
        return
    # Yangi /crash buyrug'i avvalgi /scrash stop holatini bekor qiladi.
    CRASH_STOPPED.discard(chat_id)
    # Guruh va kanallarda /crash raund tugagach avtomatik qayta boshlanadi.
    if chat.type == ChatType.CHANNEL:
        starter = 0
    else:
        if not user:
            # Guruh nomidan yuborilgan admin posti uchun egasi 0 bo'lishi mumkin.
            starter = 0 if msg.sender_chat and msg.sender_chat.id == chat_id else None
            if starter is None:
                return
        else:
            starter = user.id
    auto_repeat = True
    # O'yin avval ro'yxatga olinadi (ikkita /crash bir vaqtda ochilib ketmasin)
    game = new_game(
        chat_id, "crash", starter, state="lobby", msg_id=None,
        players={}, dropped=[], cp=None, t0=None, t_crash=None,
        charged=False, settled=False, auto_repeat=auto_repeat,
    )
    try:
        lobby = await context.bot.send_message(
            chat_id=chat_id,
            text=cr_t(chat_id, "lobby", min=CRASH_MIN_BET, sec=CRASH_COUNTDOWN),
            reply_markup=crash_kb(chat_id, game),
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        end_game(chat_id, game)
        raise
    game["msg_id"] = lobby.message_id
    arm(context.application, chat_id, game, CRASH_LOBBY_TTL)


async def cmd_scrash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop Crash in a group/channel and suppress automatic restarts until /crash."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or chat.type == ChatType.PRIVATE:
        if msg:
            await msg.reply_text("👥 /scrash buyrug‘ini guruh yoki kanalda ishlating.")
        return

    chat_id = chat.id
    game = GAMES.get(chat_id)
    # To'xtatish ruxsati: o'yin egasi, guruh administratori yoki anonim kanal/guruh admini.
    anonymous_admin = bool(msg.sender_chat and msg.sender_chat.id == chat_id)
    allowed = anonymous_admin or bool(
        user and (
            (game and user.id == game.get("owner"))
            or await is_admin(context.bot, chat_id, user.id)
        )
    )
    if not allowed:
        await msg.reply_text("⛔ /scrash buyrug‘ini faqat admin yoki o‘yin egasi ishlata oladi.")
        return

    CRASH_STOPPED.add(chat_id)
    if not game or game.get("type") != "crash":
        await msg.reply_text("🛑 Crash avtomatik qayta boshlashi to‘xtatildi. Faol Crash raundi yo‘q.")
        return

    game["state"] = "stopped"
    end_game(chat_id, game)  # cashout qilinmagan depozitlar qaytariladi
    await close_game_message(
        context.bot, chat_id, game,
        "🛑 <b>CRASH TO‘XTATILDI</b>\nYangi raund boshlanmaydi. Qayta yoqish uchun /crash yuboring."
    )
    await msg.reply_text("🛑 Crash to‘xtatildi. Avtomatik qayta boshlash o‘chirildi; qayta boshlash uchun /crash.")


async def _crash_auto_restart(app, chat_id):
    await asyncio.sleep(4)
    if chat_id in CRASH_STOPPED or not CRASH_ENABLED or not crash_group_allowed(chat_id) or GAMES.get(chat_id):
        return
    try:
        msg = await app.bot.send_message(
            chat_id=chat_id,
            text=cr_t(chat_id, "lobby", min=CRASH_MIN_BET, sec=CRASH_COUNTDOWN),
            parse_mode=ParseMode.HTML,
        )
        game = new_game(
            chat_id, "crash", 0, state="lobby", msg_id=msg.message_id,
            players={}, dropped=[], cp=None, t0=None, t_crash=None,
            charged=False, settled=False, auto_repeat=True,
        )
        await edit(app.bot, chat_id, msg.message_id,
                   cr_t(chat_id, "lobby", min=CRASH_MIN_BET, sec=CRASH_COUNTDOWN),
                   crash_kb(chat_id, game))
        arm(app, chat_id, game, CRASH_LOBBY_TTL)
    except TelegramError:
        logger.exception("Crash kanalida avtomatik yangi raund ochilmadi")


async def cb_crash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await crash_action(q, context, q.data.split(":", 1)[1])


async def crash_action(q, context, action):
    chat_id = game_key(q)
    user = q.from_user
    game = active(q, "crash")

    if action in ("join", "plus", "min") and (
        not CRASH_ENABLED or not crash_group_allowed(chat_id)
    ):
        await q.answer("⛔ Bu guruhda Crash hozir faol emas.", show_alert=True)
        return

    # ── Qo'shilish ──
    if action == "join":
        if not game or game["state"] not in ("lobby", "count"):
            await q.answer(cr_t(chat_id, "closed"), show_alert=True)
            return
        if user.id in game["players"]:
            await q.answer(cr_t(chat_id, "already"), show_alert=True)
            return
        if wallet_balance(user.id) < CRASH_MIN_BET:
            await q.answer(cr_t(chat_id, "no_funds", min=CRASH_MIN_BET), show_alert=True)
            return
        if await fsub_block_cb(q, context):
            return
        save_user(user)
        game["players"][user.id] = {
            "name": uname(user), "bet": CRASH_MIN_BET, "cash": None, "paid": False, "refunded": False,
        }
        if game["state"] == "lobby":
            # Birinchi o'yinchi — umumiy sanoqni boshlaymiz
            game["state"] = "count"
            timer = game.get("timer")
            if timer and not timer.done():
                timer.cancel()
            game["timer"] = None
            task = asyncio.create_task(crash_round(context.application, chat_id, game))
            BG_TASKS.add(task)
            task.add_done_callback(BG_TASKS.discard)
        try:
            await edit(
                context.bot, chat_id, game["msg_id"],
                cr_t(chat_id, "count", left=CRASH_COUNTDOWN,
                     players=crash_players_text(chat_id, game),
                     step=CRASH_STEP, min=CRASH_MIN_BET),
                crash_kb(chat_id, game),
            )
        except TelegramError:
            logger.exception("Crash qo'shilganda lobby xabarini yangilab bo'lmadi")
        await q.answer(cr_t(chat_id, "joined", bet=CRASH_MIN_BET))
        return

    # ── Depozitni o'zgartirish ──
    if action in ("plus", "min"):
        if not game or game["state"] != "count":
            await q.answer(cr_t(chat_id, "closed"), show_alert=True)
            return
        p = game["players"].get(user.id)
        if not p:
            await q.answer(cr_t(chat_id, "not_in"), show_alert=True)
            return
        if action == "plus":
            new_bet = p["bet"] + CRASH_STEP
            balance = wallet_balance(user.id)
            if new_bet > balance:
                await q.answer(cr_t(chat_id, "no_more", bal=balance), show_alert=True)
                return
            p["bet"] = new_bet
        else:
            p["bet"] = CRASH_MIN_BET
        try:
            await edit(
                context.bot, chat_id, game["msg_id"],
                cr_t(chat_id, "count", left=CRASH_COUNTDOWN,
                     players=crash_players_text(chat_id, game),
                     step=CRASH_STEP, min=CRASH_MIN_BET),
                crash_kb(chat_id, game),
            )
        except TelegramError:
            logger.exception("Crash depozit xabarini yangilashda xato")
        await q.answer(cr_t(chat_id, "bet_set", bet=p["bet"]))
        return

    # ── Pulni olish ──
    if action == "cash":
        if not game or game["state"] != "fly":
            await q.answer(cr_t(chat_id, "closed"), show_alert=True)
            return
        p = game["players"].get(user.id)
        if not p:
            await q.answer(cr_t(chat_id, "not_in_round"), show_alert=True)
            return
        if p["cash"] is not None:
            await q.answer(cr_t(chat_id, "already_cashed"), show_alert=True)
            return
        if game.get("t0") is None or time.monotonic() < game["t0"]:
            await q.answer()  # animatsiya hali boshlanmadi (x1.00) — hozircha hech narsa
            return
        elapsed = time.monotonic() - game["t0"]
        if elapsed >= game["t_crash"]:
            await q.answer(cr_t(chat_id, "late"), show_alert=True)
            return
        mult = crash_mult(elapsed, game.get("growth"))
        payout = crash_payout(p["bet"], mult)
        p["cash"] = mult
        try:
            wallet_change(user.id, payout)
        except sqlite3.Error:
            logger.exception("Crash: yutuqni yozib bo'lmadi (user %s)", user.id)
            p["cash"] = None
            await q.answer(cr_t(chat_id, "error"), show_alert=True)
            return
        await q.answer(cr_t(chat_id, "cashed", mult=f"{mult:.2f}", profit=payout - p["bet"]))
        return

    await q.answer()

# ───────────────────────────── Boshqa callback'lar ─────────────────────────────


# ───────────────────────────── 🐊 Krokodil ─────────────────────────────
# Boshlovchi maxfiy so'zni "👁 So'zni ko'rish" tugmasi orqali ko'radi va uni
# aytmasdan tushuntiradi. Guruhdagi boshqalar so'zni chatga yozib topadi.
# So'zni birinchi topgan o'yinchi ball oladi va keyingi boshlovchi bo'ladi.
# So'zlar guruh tiliga qarab olinadi (/lang): uz / eng / ru / kz.

CROC_WIN_PTS = 10          # to'g'ri javob uchun ball
CROC_TTL = 900             # faolsizlik vaqti (soniya): shundan keyin o'yin bekor bo'ladi
CROC_WORDS_FILE = os.path.join(VOLUME_PATH or BASE_DIR, "krokodil_words.json")

# Bot tillari -> so'zlar bazasi tillari
CROC_WORD_LANG = {"uz": "uz", "eng": "en", "ru": "ru", "kz": "kk"}

# Haqiqiy lug'atlar: bot ishga tushganda fonda yuklanadi va CROC_WORDS_FILE'ga keshlanadi.
CROC_WORD_URLS = {
    "uz": "https://raw.githubusercontent.com/kaharjan/uzb-dict-words/master/words_list.txt",
    "ru": "https://raw.githubusercontent.com/JackShannon/1000-most-common-words/master/1000-most-common-russian-words.txt",
    "en": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-usa-no-swears.txt",
    "kk": "https://raw.githubusercontent.com/SMenigat/thousand-most-common-words/master/words/kk.json",
}
CROC_TARGET_COUNTS = {"uz": 150, "ru": 150, "en": 150, "kk": 150}

# Lug'at yuklanmaguncha (yoki internet bo'lmasa) o'yin shu so'zlar bilan ishlaydi.
CROC_FALLBACK_WORDS = {'uz': ['olma',
        'kitob',
        'mashina',
        'telefon',
        'kompyuter',
        'maktab',
        'daraxt',
        'shahar',
        'samolyot',
        'quyosh',
        'yulduz',
        'mushuk',
        'qalam',
        'stol',
        'kalit',
        'oyna',
        'daryo',
        "tog'",
        'bulut',
        'gul',
        'uy',
        'non',
        'soat',
        'televizor',
        'futbol',
        'velosiped',
        'koptok',
        'sumka',
        'eshik',
        'avtobus',
        'poyezd',
        'choynak',
        'qoshiq',
        'stakan',
        'divan',
        'kursi',
        'karavot',
        'meva',
        'banan',
        'anor',
        'uzum',
        'shaftoli',
        'nok',
        'gilos',
        'tarvuz',
        'qovun',
        'sabzi',
        'kartoshka',
        'piyoz',
        'pomidor',
        'bodring',
        'osh',
        'somsa',
        'manti',
        "sho'rva",
        "lag'mon",
        'palov',
        'sut',
        'pishloq',
        'asal',
        'shakar',
        'tuz',
        'qahva',
        'choy',
        'sher',
        'fil',
        'jirafa',
        'maymun',
        'quyon',
        'it',
        'sigir',
        'ot',
        'echki',
        'tovuq',
        'burgut',
        'kapalak',
        'ari',
        'ilon',
        'toshbaqa',
        'qor',
        'shamol',
        'chaqmoq',
        'osmon',
        'yer',
        'dunyo',
        'orol',
        'dengiz',
        'bozor',
        'shifoxona',
        'qayiq',
        'qaychi',
        'qop',
        'quti',
        'qovoq',
        'quduq',
        'qasr',
        'qalqon',
        "qaldirg'och",
        "qo'ng'iroq",
        "o'rdak",
        "o'rmon",
        "ko'prik",
        "ko'cha",
        "bog'",
        "g'isht",
        'chiroq',
        'gilam',
        "ko'zoynak",
        'pichoq',
        'bolta',
        'arra',
        'vertolyot',
        'kema',
        'mototsikl',
        'traktor',
        'kamera',
        'gitara',
        "nog'ora",
        "do'ppi",
        'chopon',
        'daftar',
        'ruchka',
        'zaryadlagich',
        'muzlatgich',
        'kir',
        'yuvish',
        'likopcha',
        'piyola',
        'chelak',
        'supurgi',
        'sochiq',
        "ko'rpa",
        'yostiq',
        'gilamcha',
        'tokcha',
        'javon',
        'sandiq',
        'qulf',
        'kalitdon',
        'taroq',
        'sovun',
        'shampun',
        'tish',
        "cho'tkasi",
        'pasta',
        'atir',
        "ko'ylak",
        'shim',
        'etik',
        'tufli'],
 'ru': ['дом',
        'книга',
        'машина',
        'телефон',
        'компьютер',
        'школа',
        'дерево',
        'город',
        'самолет',
        'солнце',
        'звезда',
        'кошка',
        'ручка',
        'стол',
        'ключ',
        'окно',
        'река',
        'гора',
        'облако',
        'цветок',
        'хлеб',
        'часы',
        'автобус',
        'поезд',
        'вода',
        'море',
        'собака',
        'семья',
        'друг',
        'слон',
        'жираф',
        'обезьяна',
        'заяц',
        'корова',
        'лошадь',
        'курица',
        'орел',
        'бабочка',
        'пчела',
        'змея',
        'черепаха',
        'снег',
        'ветер',
        'молния',
        'остров',
        'рынок',
        'больница',
        'лодка',
        'ножницы',
        'мост',
        'улица',
        'лес',
        'гитара',
        'барабан',
        'велосипед',
        'мяч',
        'зонт',
        'лампа',
        'ковер',
        'очки',
        'камера',
        'тетрадь',
        'карандаш',
        'дверь',
        'стул',
        'кровать',
        'диван',
        'подушка',
        'одеяло',
        'полотенце',
        'зеркало',
        'шкаф',
        'полка',
        'сундук',
        'замок',
        'расческа',
        'мыло',
        'шампунь',
        'зубная',
        'паста',
        'платье',
        'брюки',
        'ботинок',
        'носок',
        'шапка',
        'перчатка',
        'шарф',
        'ремень',
        'кольцо',
        'браслет',
        'ожерелье',
        'кошелек',
        'билет',
        'карта',
        'глобус',
        'компас',
        'бинокль',
        'телескоп',
        'микроскоп',
        'принтер',
        'клавиатура',
        'мышь',
        'экран',
        'наушники',
        'микрофон',
        'колонка',
        'батарея',
        'фонарь',
        'свеча',
        'спичка',
        'термометр',
        'весы',
        'молоток',
        'гвоздь',
        'отвертка',
        'лопата',
        'тяпка',
        'колесо',
        'руль',
        'тормоз',
        'мотор',
        'бензин',
        'гонка',
        'стадион',
        'поле',
        'ворота',
        'судья',
        'тренер',
        'футболист',
        'баскетбол',
        'волейбол',
        'теннис',
        'шахматы',
        'домино',
        'кубик',
        'подарок',
        'праздник',
        'свадьба',
        'гость',
        'ребенок',
        'мать',
        'отец',
        'брат',
        'сестра',
        'бабушка',
        'дедушка',
        'сосед',
        'учитель',
        'ученик',
        'врач'],
 'en': ['apple',
        'book',
        'car',
        'phone',
        'computer',
        'school',
        'tree',
        'city',
        'airplane',
        'sun',
        'star',
        'cat',
        'pen',
        'table',
        'key',
        'window',
        'river',
        'mountain',
        'cloud',
        'flower',
        'house',
        'bread',
        'clock',
        'bus',
        'train',
        'water',
        'sea',
        'dog',
        'family',
        'friend',
        'elephant',
        'giraffe',
        'monkey',
        'rabbit',
        'horse',
        'eagle',
        'butterfly',
        'snake',
        'turtle',
        'snow',
        'wind',
        'lightning',
        'island',
        'market',
        'hospital',
        'boat',
        'scissors',
        'bridge',
        'street',
        'forest',
        'guitar',
        'drum',
        'bicycle',
        'ball',
        'umbrella',
        'lamp',
        'carpet',
        'glasses',
        'camera',
        'notebook',
        'pencil',
        'door',
        'chair',
        'bed',
        'sofa',
        'pillow',
        'blanket',
        'towel',
        'mirror',
        'wardrobe',
        'shelf',
        'chest',
        'lock',
        'comb',
        'soap',
        'shampoo',
        'toothpaste',
        'dress',
        'trousers',
        'shoe',
        'sock',
        'hat',
        'glove',
        'scarf',
        'belt',
        'ring',
        'bracelet',
        'necklace',
        'wallet',
        'ticket',
        'map',
        'globe',
        'compass',
        'binoculars',
        'telescope',
        'microscope',
        'printer',
        'keyboard',
        'mouse',
        'screen',
        'headphones',
        'microphone',
        'speaker',
        'battery',
        'flashlight',
        'candle',
        'match',
        'thermometer',
        'scales',
        'hammer',
        'nail',
        'screwdriver',
        'shovel',
        'hoe',
        'wheel',
        'steering',
        'brake',
        'engine',
        'petrol',
        'race',
        'stadium',
        'field',
        'goal',
        'referee',
        'coach',
        'footballer',
        'basketball',
        'volleyball',
        'tennis',
        'chess',
        'domino',
        'card',
        'dice',
        'gift',
        'holiday',
        'wedding',
        'guest',
        'child',
        'mother',
        'father',
        'brother',
        'sister',
        'grandmother',
        'grandfather',
        'neighbor',
        'teacher',
        'student',
        'doctor',
        'nurse',
        'cook'],
 'kk': ['алма',
        'кітап',
        'машина',
        'телефон',
        'компьютер',
        'мектеп',
        'ағаш',
        'қала',
        'ұшақ',
        'күн',
        'жұлдыз',
        'мысық',
        'қалам',
        'үстел',
        'кілт',
        'терезе',
        'өзен',
        'тау',
        'бұлт',
        'гүл',
        'үй',
        'нан',
        'сағат',
        'автобус',
        'пойыз',
        'су',
        'теңіз',
        'ит',
        'отбасы',
        'дос',
        'піл',
        'керік',
        'маймыл',
        'қоян',
        'жылқы',
        'бүркіт',
        'көбелек',
        'жылан',
        'тасбақа',
        'қар',
        'жел',
        'найзағай',
        'арал',
        'базар',
        'аурухана',
        'қайық',
        'қайшы',
        'көпір',
        'көше',
        'орман',
        'гитара',
        'барабан',
        'велосипед',
        'доп',
        'қолшатыр',
        'шам',
        'кілем',
        'көзілдірік',
        'камера',
        'дәптер',
        'қарындаш',
        'есік',
        'орындық',
        'төсек',
        'диван',
        'жастық',
        'көрпе',
        'сүлгі',
        'айна',
        'шкаф',
        'сөре',
        'сандық',
        'құлып',
        'тарақ',
        'сабын',
        'сусабын',
        'тіс',
        'пастасы',
        'көйлек',
        'шалбар',
        'аяқкиім',
        'шұлық',
        'бөрік',
        'қолғап',
        'шарф',
        'белдік',
        'сақина',
        'білезік',
        'алқа',
        'әмиян',
        'билет',
        'карта',
        'глобус',
        'тұсбағар',
        'дүрбі',
        'телескоп',
        'микроскоп',
        'принтер',
        'пернетақта',
        'тышқан',
        'экран',
        'құлаққап',
        'микрофон',
        'дауысзорайтқыш',
        'батарея',
        'шамшырақ',
        'майшам',
        'сіріңке',
        'термометр',
        'таразы',
        'балға',
        'шеге',
        'бұрауыш',
        'күрек',
        'кетпен',
        'доңғалақ',
        'рөл',
        'тежегіш',
        'қозғалтқыш',
        'жанармай',
        'жарыс',
        'стадион',
        'алаң',
        'қақпа',
        'төреші',
        'жаттықтырушы',
        'футболшы',
        'баскетбол',
        'волейбол',
        'теннис',
        'шахмат',
        'домино',
        'текше',
        'сыйлық',
        'мереке',
        'той',
        'қонақ',
        'бала',
        'ана',
        'әке',
        'аға',
        'әпке',
        'іні',
        'сіңлі',
        'әже',
        'ата',
        'көрші',
        'мұғалім',
        'оқушы',
        'дәрігер']}

_CROC_WORDS: dict[str, list[str]] = {}   # yuklangan lug'atlar (til -> so'zlar)
_CROC_FALLBACK_CLEAN: dict[str, list[str]] = {}


def croc_norm(text):
    """Javob va so'zni solishtirish uchun bir xil ko'rinishga keltiradi."""
    text = (text or "").strip().casefold()
    for ch in ("’", "ʻ", "ʼ", "‘", "`", "´"):
        text = text.replace(ch, "'")
    text = text.replace("ё", "е")
    return " ".join(text.split())


def croc_answer_matches(answer, word, lang):
    """Javobni aynan tanlangan til lug'atidagi so'z bilan solishtiradi."""
    a = croc_norm(answer)
    w = croc_norm(word)
    if lang == "uz":
        # O'zbek apostroflari (o‘, g‘, ʼ) yozilmagan bo'lsa ham javob qabul qilinadi.
        a = a.replace("'", "")
        w = w.replace("'", "")
    return a == w


def croc_clean_word(word, lang):
    if not isinstance(word, str):
        return None
    word = croc_norm(word)
    if len(word) < 2 or len(word) > 35 or " " in word:
        return None

    # Har bir til faqat o'z yozuv tizimidan foydalanadi.
    if lang == "en":
        ok = re.fullmatch(r"[a-z]+(?:'[a-z]+)?", word)
    elif lang == "ru":
        ok = re.fullmatch(r"[а-я-]+", word)
    elif lang == "kk":
        ok = re.fullmatch(r"[а-яәіңғқһөұү-]+", word)
    else:
        # O'zbek: lotin yozuvi (kirill so'zlar kirmaydi).
        ok = re.fullmatch(r"[a-z']+", word)
    return word if ok else None


def croc_parse_source(text, lang):
    raw = []
    if lang == "kk" and text.lstrip().startswith("{"):
        try:
            obj = json.loads(text)
            for item in obj.get("words", []):
                if isinstance(item, dict):
                    raw.append(item.get("targetWord", ""))
        except Exception:  # noqa: BLE001
            pass
    else:
        raw.extend(text.splitlines())

    cleaned, seen = [], set()
    for item in raw:
        w = croc_clean_word(item, lang)
        if w and w not in seen:
            seen.add(w)
            cleaned.append(w)
    return cleaned


def croc_download_words(lang):
    from urllib.request import Request, urlopen

    try:
        req = Request(CROC_WORD_URLS[lang], headers={"User-Agent": "EmpireKrakadil/1.0"})
        with urlopen(req, timeout=20) as response:
            data = response.read().decode("utf-8", errors="ignore")
        return croc_parse_source(data, lang)
    except Exception as e:  # noqa: BLE001
        logger.warning("Krokodil: %s lug'ati yuklanmadi: %r", lang, e)
        return []


def croc_fallback(lang):
    if lang not in _CROC_FALLBACK_CLEAN:
        words = [croc_clean_word(w, lang) for w in CROC_FALLBACK_WORDS.get(lang, [])]
        _CROC_FALLBACK_CLEAN[lang] = list(dict.fromkeys(w for w in words if w))
    return _CROC_FALLBACK_CLEAN[lang]


def croc_build_words():
    """Keshdagi lug'atni o'qiydi, yetmasa internetdan to'ldiradi (fonda ishlaydi)."""
    saved = {}
    try:
        if os.path.exists(CROC_WORDS_FILE):
            with open(CROC_WORDS_FILE, encoding="utf-8") as f:
                saved = json.load(f)
    except Exception:  # noqa: BLE001
        saved = {}

    final = {}
    for lang, target in CROC_TARGET_COUNTS.items():
        words = []
        if isinstance(saved.get(lang), list):
            words = [croc_clean_word(w, lang) for w in saved[lang]]
            words = list(dict.fromkeys(w for w in words if w))

        if len(words) < target:
            words = list(dict.fromkeys(words + croc_download_words(lang)))

        for w in croc_fallback(lang):
            if w not in words:
                words.append(w)

        final[lang] = words[:target]

    try:
        tmp = CROC_WORDS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False)
        os.replace(tmp, CROC_WORDS_FILE)
    except Exception as e:  # noqa: BLE001
        logger.warning("Krokodil: lug'atni saqlab bo'lmadi: %r", e)

    return final


async def croc_prepare_words():
    try:
        words = await asyncio.to_thread(croc_build_words)
        _CROC_WORDS.update(words)
        logger.info(
            "Krokodil lug'atlari tayyor: %s",
            ", ".join(f"{k}={len(v)}" for k, v in words.items()),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Krokodil lug'atlarini tayyorlab bo'lmadi")


def croc_lang_code(chat_id):
    return CROC_WORD_LANG.get(LANG_CACHE.get(chat_id, DEFAULT_LANG), "uz")


def croc_pick_word(chat_id, game):
    """Guruh tilidagi tasodifiy so'z (iloji boricha takrorlanmaydi)."""
    lang = croc_lang_code(chat_id)
    words = _CROC_WORDS.get(lang) or croc_fallback(lang)
    used = game.setdefault("used", set())
    fresh = [w for w in words if w not in used]
    if not fresh:
        used.clear()
        fresh = [w for w in words if w != game.get("word")] or words
    word = random.choice(fresh)
    used.add(word)
    return word


CROC_TEXT = {
    "uz": {
        "btn": "🐊 Krokodil",
        "round": (
            "🐊 <b>KROKODIL</b>\n\n"
            "👑 Boshlovchi: <b>{host}</b>\n"
            "🔁 Raund: <b>{round}</b>\n\n"
            "🔎 <b>So‘zni toping!</b>\n"
            "Boshlovchi so‘zni aytmasdan tushuntiradi, qolganlar javobni chatga yozadi.\n"
            "🏆 To‘g‘ri javob: +{points} ball va keyingi boshlovchi bo‘lish huquqi\n"
            "🛑 To‘xtatish: /stop"
        ),
        "show": "👁 So‘zni ko‘rish",
        "not_host": "❌ Bu tugma faqat boshlovchi uchun.",
        "win": (
            "🎉 <b>TO‘G‘RI JAVOB!</b>\n\n"
            "💬 So‘z: <b>{word}</b>\n"
            "👑 {name}\n"
            "🏆 +{points} ball\n\n"
            "👑 Endi u keyingi boshlovchi!"
        ),
        "timeout": "⌛ Vaqt tugadi — o‘yin bekor qilindi.\n🐊 So‘z: <b>{word}</b> edi.\n▶️ Yana o‘ynash: /emps",
        "stopped": "🛑 O‘yin to‘xtatildi.\n🐊 So‘z: <b>{word}</b> edi.",
        "send_error": "⚠️ Yangi raundni yuborib bo‘lmadi. O‘yin to‘xtatildi.\n▶️ Yana o‘ynash: /emps",
    },
    "eng": {
        "btn": "🐊 Crocodile",
        "round": (
            "🐊 <b>CROCODILE</b>\n\n"
            "👑 Host: <b>{host}</b>\n"
            "🔁 Round: <b>{round}</b>\n\n"
            "🔎 <b>Guess the word!</b>\n"
            "The host explains the word without saying it, everyone else types their guess in the chat.\n"
            "🏆 Correct answer: +{points} points and becomes the next host\n"
            "🛑 Stop: /stop"
        ),
        "show": "👁 Show the word",
        "not_host": "❌ This button is only for the host.",
        "win": (
            "🎉 <b>CORRECT ANSWER!</b>\n\n"
            "💬 Word: <b>{word}</b>\n"
            "👑 {name}\n"
            "🏆 +{points} points\n\n"
            "👑 They are the next host!"
        ),
        "timeout": "⌛ Time is up — the game was cancelled.\n🐊 The word was <b>{word}</b>.\n▶️ Play again: /emps",
        "stopped": "🛑 The game was stopped.\n🐊 The word was <b>{word}</b>.",
        "send_error": "⚠️ Could not send the next round. The game was stopped.\n▶️ Play again: /emps",
    },
    "ru": {
        "btn": "🐊 Крокодил",
        "round": (
            "🐊 <b>КРОКОДИЛ</b>\n\n"
            "👑 Ведущий: <b>{host}</b>\n"
            "🔁 Раунд: <b>{round}</b>\n\n"
            "🔎 <b>Угадайте слово!</b>\n"
            "Ведущий объясняет слово, не называя его, остальные пишут ответ в чат.\n"
            "🏆 Правильный ответ: +{points} очков и роль следующего ведущего\n"
            "🛑 Остановить: /stop"
        ),
        "show": "👁 Показать слово",
        "not_host": "❌ Эта кнопка только для ведущего.",
        "win": (
            "🎉 <b>ПРАВИЛЬНЫЙ ОТВЕТ!</b>\n\n"
            "💬 Слово: <b>{word}</b>\n"
            "👑 {name}\n"
            "🏆 +{points} очков\n\n"
            "👑 Теперь он следующий ведущий!"
        ),
        "timeout": "⌛ Время вышло — игра отменена.\n🐊 Слово было: <b>{word}</b>.\n▶️ Сыграть ещё: /emps",
        "stopped": "🛑 Игра остановлена.\n🐊 Слово было: <b>{word}</b>.",
        "send_error": "⚠️ Не удалось отправить новый раунд. Игра остановлена.\n▶️ Сыграть ещё: /emps",
    },
    "kz": {
        "btn": "🐊 Қолтырау",
        "round": (
            "🐊 <b>ҚОЛТЫРАУ</b>\n\n"
            "👑 Жүргізуші: <b>{host}</b>\n"
            "🔁 Раунд: <b>{round}</b>\n\n"
            "🔎 <b>Сөзді табыңыз!</b>\n"
            "Жүргізуші сөзді атамай түсіндіреді, қалғандары жауабын чатқа жазады.\n"
            "🏆 Дұрыс жауап: +{points} ұпай және келесі жүргізуші болу\n"
            "🛑 Тоқтату: /stop"
        ),
        "show": "👁 Сөзді көру",
        "not_host": "❌ Бұл түйме тек жүргізушіге арналған.",
        "win": (
            "🎉 <b>ДҰРЫС ЖАУАП!</b>\n\n"
            "💬 Сөз: <b>{word}</b>\n"
            "👑 {name}\n"
            "🏆 +{points} ұпай\n\n"
            "👑 Енді ол келесі жүргізуші!"
        ),
        "timeout": "⌛ Уақыт бітті — ойын тоқтатылды.\n🐊 Сөз: <b>{word}</b> еді.\n▶️ Тағы ойнау: /emps",
        "stopped": "🛑 Ойын тоқтатылды.\n🐊 Сөз: <b>{word}</b> еді.",
        "send_error": "⚠️ Жаңа раундты жіберу мүмкін болмады. Ойын тоқтатылды.\n▶️ Тағы ойнау: /emps",
    },
}

# Menyu tugmasi ("btn_croc") va qoidalar bo'limi uchun umumiy lug'atga ulaymiz.
_CROC_RULES = {
    "uz": (
        "🐊 <b>Krokodil</b>\n"
        "Boshlovchi maxfiy so‘zni tugma orqali ko‘radi va aytmasdan tushuntiradi. "
        "So‘zni birinchi topgan +10 ball oladi va keyingi boshlovchi bo‘ladi.\n\n"
    ),
    "eng": (
        "🐊 <b>Crocodile</b>\n"
        "The host sees a secret word via the button and explains it without saying it. "
        "The first to guess gets +10 points and becomes the next host.\n\n"
    ),
    "ru": (
        "🐊 <b>Крокодил</b>\n"
        "Ведущий видит тайное слово по кнопке и объясняет его, не называя. "
        "Первый угадавший получает +10 очков и становится следующим ведущим.\n\n"
    ),
    "kz": (
        "🐊 <b>Қолтырау</b>\n"
        "Жүргізуші құпия сөзді түйме арқылы көріп, атамай түсіндіреді. "
        "Бірінші тапқан +10 ұпай алады және келесі жүргізуші болады.\n\n"
    ),
}
_CROC_RULES_ANCHOR = {
    "uz": "⌛ Faol bo‘lmasa",
    "eng": "⌛ Inactive games",
    "ru": "⌛ Неактивные игры",
    "kz": "⌛ Белсенді болмаса",
}
for _code, _texts in CROC_TEXT.items():
    LANGS[_code]["btn_croc"] = _texts["btn"]
    _rules = LANGS[_code].get("rules", "")
    if _CROC_RULES[_code] not in _rules and _CROC_RULES_ANCHOR[_code] in _rules:
        LANGS[_code]["rules"] = _rules.replace(
            _CROC_RULES_ANCHOR[_code], _CROC_RULES[_code] + _CROC_RULES_ANCHOR[_code], 1
        )


def croc_t(chat_id, key, **kwargs):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    data = CROC_TEXT.get(lang, CROC_TEXT["uz"])
    text = data.get(key) or CROC_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def croc_kb(chat_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(croc_t(chat_id, "show"), callback_data="croc:show")
    ]])


def croc_round_text(chat_id, game):
    return croc_t(
        chat_id, "round",
        host=game["host_name"], round=game["round"], points=CROC_WIN_PTS,
    )


async def croc_on_text(update: Update, context: ContextTypes.DEFAULT_TYPE, game):
    """Guruhdagi matnni krokodil javobi sifatida tekshiradi."""
    msg = update.effective_message
    user = update.effective_user
    chat_id = msg.chat_id

    if game.get("finished") or not game.get("word"):
        return

    # Boshlovchi o'zi so'zni yozsa yutmaydi.
    if user.id == game.get("host_id"):
        return

    lang = croc_lang_code(chat_id)
    if not croc_answer_matches(msg.text, game["word"], lang):
        return

    if await fsub_block_msg(update, context):
        return

    # Keyingi xabar bilan poyga bo'lmasligi uchun avval yakunlaymiz.
    game["finished"] = True
    save_user(user)

    word = game["word"]
    name = uname(user)
    old_msg_id = game.get("msg_id")

    record(chat_id, user.id, "win", CROC_WIN_PTS)

    # G'olib keyingi boshlovchi bo'ladi.
    game["host_id"] = user.id
    game["host_name"] = name
    game["owner"] = user.id          # /stop uchun
    game["round"] = game.get("round", 1) + 1
    game["word"] = croc_pick_word(chat_id, game)
    game["finished"] = False

    await msg.reply_text(
        croc_t(chat_id, "win", word=escape(word, quote=False), name=name, points=CROC_WIN_PTS)
    )

    # Eski raund xabaridagi "So'zni ko'rish" tugmasini olib tashlaymiz.
    if old_msg_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=old_msg_id, reply_markup=None
            )
        except TelegramError:
            pass

    try:
        sent = await context.bot.send_message(
            chat_id, croc_round_text(chat_id, game), reply_markup=croc_kb(chat_id)
        )
    except TelegramError as e:
        logger.warning("Krokodil: yangi raundni yuborib bo'lmadi: %s", e)
        end_game(chat_id, game)
        try:
            await context.bot.send_message(chat_id, croc_t(chat_id, "send_error"))
        except TelegramError:
            pass
        return

    game["msg_id"] = sent.message_id
    arm(context.application, chat_id, game, CROC_TTL)


async def cb_croc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """👁 So'zni ko'rish — faqat joriy boshlovchi uchun."""
    q = update.callback_query
    if not q or not q.message:
        return

    chat_id = q.message.chat.id
    game = GAMES.get(chat_id)
    if not game or game.get("type") != "croc":
        await q.answer(t(chat_id, "gone"), show_alert=True)
        return

    if q.from_user.id != game.get("host_id"):
        await q.answer(croc_t(chat_id, "not_host"), show_alert=True)
        return

    await q.answer(f"🔐 {game['word'].upper()}", show_alert=True)
    # Boshlovchi faol — faolsizlik taymerini yangilaymiz.
    arm(context.application, chat_id, game, CROC_TTL)


async def cb_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


# ───────────────────────────── Xatolar va ishga tushirish ─────────────────────────────


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Kutilmagan xato", exc_info=context.error)


async def post_init(application: Application):
    application.create_task(family_delivery_worker(application), name="family-delivery-worker")
    application.create_task(croc_prepare_words(), name="croc-words")
    application.create_task(bank_worker(application), name="bank-worker")
    application.create_task(birja_worker(application), name="birja-worker")
    application.create_task(kid_worker(application), name="kid-worker")
    application.create_task(night_worker(application), name="night-worker")
    exchange_start_server(application)
    application.create_task(exchange_retry_worker(application), name="exchange-retry")
    application.create_task(web_crash_round_worker(application), name="web-crash-rounds")
    sets = {
        None: [
            ("emps", "🎮 O‘yin tanlash"), ("stop", "🛑 O‘yinni to‘xtatish"),
            ("reyting", "🏆 Reyting"), ("aktiv", "📊 Eng faollar"), ("profil", "👤 Profil"), ("farzand", "👶 Farzandlarim"), ("settings", "⚙️ Guruh sozlamalari"), ("scrash", "🛑 Crashni to‘xtatish"),
            ("qoidalar", "📚 Qoidalar"), ("lang", "🌐 Til"), ("help", "❓ Yordam"),
        ],
        "en": [
            ("emps", "🎮 Choose a game"), ("stop", "🛑 Stop the game"),
            ("reyting", "🏆 Leaderboard"), ("aktiv", "📊 Most active"), ("profil", "👤 Profile"), ("farzand", "👶 My children"), ("settings", "⚙️ Group settings"), ("scrash", "🛑 Stop Crash"),
            ("qoidalar", "📚 Rules"), ("lang", "🌐 Language"), ("help", "❓ Help"),
        ],
        "ru": [
            ("emps", "🎮 Выбрать игру"), ("stop", "🛑 Остановить игру"),
            ("reyting", "🏆 Рейтинг"), ("aktiv", "📊 Самые активные"), ("profil", "👤 Профиль"), ("farzand", "👶 Мои дети"), ("settings", "⚙️ Настройки группы"), ("scrash", "🛑 Остановить Crash"),
            ("qoidalar", "📚 Правила"), ("lang", "🌐 Язык"), ("help", "❓ Помощь"),
        ],
    }
    try:
        for lang, cmds in sets.items():
            await application.bot.set_my_commands(
                [BotCommand(c, d) for c, d in cmds], language_code=lang
            )
    except TelegramError as e:
        logger.warning("Buyruqlar menyusini o'rnatib bo'lmadi: %s", e)

    # Guruh "/" menyusi: o'yin + barcha admin/moderatsiya buyruqlari ko'rinadi.
    group_cmds = [
        ("emps", "🎮 O‘yin tanlash"), ("settings", "⚙️ Guruh sozlamalari"),
        ("aktiv", "📊 Eng faollar"), ("reyting", "🏆 Reyting"),
        ("warn", "⚠️ Ogohlantirish"), ("unwarn", "🧽 Ogohlantirishni olib tashlash"),
        ("warns", "📋 Ogohlantirishlar soni"),
        ("mute", "🤐 Jim qilish (muddat: 10m/2h/1d)"), ("tmute", "⏳🤐 Vaqtincha jim"),
        ("unmute", "🗣 Jimlikdan chiqarish"),
        ("ban", "🚀 Ban"), ("tban", "⏳🚀 Vaqtincha ban"), ("unban", "🕊 Bandan chiqarish"),
        ("kick", "🦶 Guruhdan chiqarish"),
        ("promote", "👮 Admin qilish"), ("demote", "⬇️ Adminlikdan olish"),
        ("title", "🎖 Admin unvoni"),
        ("del", "🗑 Xabarni o‘chirish"), ("purge", "🧹 Ko‘p xabarni o‘chirish"),
        ("pin", "📌 Mahkamlash"), ("unpin", "📌 Mahkamlashni olish"),
        ("lock", "🔒 Cheklash"), ("unlock", "🔓 Cheklovni olish"), ("locks", "🔒 Cheklovlar ro‘yxati"),
        ("addword", "🚫 Taqiqlangan so‘z qo‘shish"), ("delword", "✅ So‘zni olib tashlash"),
        ("words", "📃 Taqiqlangan so‘zlar"),
        ("filter", "💬 Filtr qo‘shish"), ("filters", "💬 Filtrlar"), ("delfilter", "🗑 Filtr o‘chirish"),
        ("setwelcome", "👋 Salomlashish matni"), ("setrules", "📜 Qoidalarni o‘rnatish"),
        ("rules", "📜 Guruh qoidalari"), ("badmute", "🔇 Taqiq. so‘z mute muddati"),
        ("setlog", "📋 Log kanal"), ("report", "📣 Adminlarga shikoyat"),
        ("info", "🪪 Foydalanuvchi ma’lumoti"), ("id", "🆔 ID"), ("admins", "👮 Adminlar"),
        ("help", "❓ Yordam"),
    ]
    try:
        await application.bot.set_my_commands(
            [BotCommand(c, d) for c, d in group_cmds],
            scope=BotCommandScopeAllGroupChats(),
        )
    except TelegramError as e:
        logger.warning("Guruh buyruqlar menyusini o'rnatib bo'lmadi: %s", e)

    # Web app menyu tugmasi (shaxsiy chatlarda input yonida chiqadi)
    if WEBAPP_URL:
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🎮 Ilova", web_app=WebAppInfo(WEBAPP_URL + "/app")))
            logger.info("Web app menyu tugmasi o'rnatildi: %s/app", WEBAPP_URL)
        except TelegramError as e:
            logger.warning("Web app menyu tugmasini o'rnatib bo'lmadi: %s", e)



async def post_shutdown(application: Application):
    try:
        web_crash_refund_open()   # web Crash: yechilmagan tikishlar qaytadi
        web_kami_settle_open()    # web Kamikaze: o'rtadagi o'yinlar hisoblanadi
    except Exception:  # noqa: BLE001
        logger.exception("Web crash tikishlarini qaytarishda xato")
    for game in list(FROG_GAMES.values()):
        try:
            frog_settle(game)   # sakragan bo'lsa — yutuq, aks holda depozit qaytadi
        except Exception:  # noqa: BLE001
            logger.exception("Qurbaqa: to'xtash paytida depozitni qaytarib bo'lmadi")
    for game in list(GAMES.values()):
        # Restart/deploy paytida Crash depozitlari yo'qolib qolmasin
        if game.get("type") == "crash":
            try:
                crash_refund(game)
            except Exception:  # noqa: BLE001
                logger.exception("Crash: to'xtash paytida depozitlarni qaytarib bo'lmadi")
        timer = game.get("timer")
        if timer and not timer.done():
            timer.cancel()
    if _conn is not None:
        _conn.real_close()


# ───────────────────────────── Kasb tizimi ─────────────────────────────

PROFESSION_NAMES = {
    1: {"uz": "👨‍💻 Dasturchi", "eng": "👨‍💻 Programmer", "ru": "👨‍💻 Программист", "kz": "👨‍💻 Бағдарламашы"},
    2: {"uz": "👨‍⚕️ Shifokor", "eng": "👨‍⚕️ Doctor", "ru": "👨‍⚕️ Врач", "kz": "👨‍⚕️ Дәрігер"},
    3: {"uz": "👨‍🏫 O‘qituvchi", "eng": "👨‍🏫 Teacher", "ru": "👨‍🏫 Учитель", "kz": "👨‍🏫 Мұғалім"},
    4: {"uz": "⚖️ Advokat", "eng": "⚖️ Lawyer", "ru": "⚖️ Адвокат", "kz": "⚖️ Адвокат"},
    5: {"uz": "🏗️ Muhandis", "eng": "🏗️ Engineer", "ru": "🏗️ Инженер", "kz": "🏗️ Инженер"},
    6: {"uz": "🔬 Olim", "eng": "🔬 Scientist", "ru": "🔬 Учёный", "kz": "🔬 Ғалым"},
    7: {"uz": "✈️ Uchuvchi", "eng": "✈️ Pilot", "ru": "✈️ Пилот", "kz": "✈️ Ұшқыш"},
    8: {"uz": "👮 Politsiyachi", "eng": "👮 Police Officer", "ru": "👮 Полицейский", "kz": "👮 Полиция қызметкері"},
    9: {"uz": "👨‍🚒 O‘t o‘chiruvchi", "eng": "👨‍🚒 Firefighter", "ru": "👨‍🚒 Пожарный", "kz": "👨‍🚒 Өрт сөндіруші"},
    10: {"uz": "👨‍🍳 Oshpaz", "eng": "👨‍🍳 Chef", "ru": "👨‍🍳 Повар", "kz": "👨‍🍳 Аспаз"},
    11: {"uz": "🎨 Dizayner", "eng": "🎨 Designer", "ru": "🎨 Дизайнер", "kz": "🎨 Дизайнер"},
    12: {"uz": "📸 Fotograf", "eng": "📸 Photographer", "ru": "📸 Фотограф", "kz": "📸 Фотограф"},
    13: {"uz": "🎤 Qo‘shiqchi", "eng": "🎤 Singer", "ru": "🎤 Певец", "kz": "🎤 Әнші"},
    14: {"uz": "🎬 Aktyor", "eng": "🎬 Actor", "ru": "🎬 Актёр", "kz": "🎬 Актер"},
    15: {"uz": "💼 Tadbirkor", "eng": "💼 Entrepreneur", "ru": "💼 Предприниматель", "kz": "💼 Кәсіпкер"},
    16: {"uz": "📰 Jurnalist", "eng": "📰 Journalist", "ru": "📰 Журналист", "kz": "📰 Журналист"},
}

def profession_name(pid, chat_id):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    return PROFESSION_NAMES[pid].get(lang, PROFESSION_NAMES[pid]["uz"])


def career_get_user(user_id):
    c = db()
    return c.execute(
        """
        SELECT birth_date, birth_confirmed, profession_id, profession_selected
        FROM users WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


def career_birth_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📅 Tug‘ilgan sanani kiritish",
                callback_data="career:birth"
            )
        ]
    ])


def career_confirm_birth_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Tasdiqlayman",
                callback_data="career:birth_yes"
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ Qayta kiritish",
                callback_data="career:birth"
            )
        ],
    ])


def career_profession_kb(chat_id, request_mode=False):
    rows = []
    ids = list(PROFESSION_NAMES.keys())
    for i in range(0, len(ids), 2):
        row = []
        for pid in ids[i:i + 2]:
            callback = (
                f"career:request:{pid}"
                if request_mode
                else f"career:prof:{pid}"
            )
            row.append(
                InlineKeyboardButton(
                    profession_name(pid, chat_id),
                    callback_data=callback
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def career_start_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    context.user_data["career_state"] = "birth_input"

    await update.effective_message.reply_text(
        "🎂 <b>Tug‘ilgan sanangizni kiriting</b>\n\n"
        "Masalan: <code>15.08.2005</code>\n\n"
        "⚠️ <b>Muhim:</b> sana tasdiqlangandan keyin uni o‘zgartirib "
        "bo‘lmaydi. Sanani aniq kiriting."
    )


def career_parse_birth(text):
    try:
        value = datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None

    today = date.today()

    if value > today:
        return None

    age = today.year - value.year
    if (today.month, today.day) < (value.month, value.day):
        age -= 1

    if age < 1 or age > 120:
        return None

    return value, age


async def career_handle_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message

    if not user or not msg or not msg.text:
        return False

    if context.user_data.get("career_state") != "birth_input":
        return False

    parsed = career_parse_birth(msg.text)

    if not parsed:
        await msg.reply_text(
            "❌ Sana noto‘g‘ri.\n\n"
            "Quyidagi formatda kiriting:\n"
            "<code>15.08.2005</code>"
        )
        return True

    birth, age = parsed

    context.user_data["career_birth"] = birth.isoformat()
    context.user_data["career_age"] = age
    context.user_data["career_state"] = "birth_confirm"

    await msg.reply_text(
        f"🎂 Tug‘ilgan sana: <b>{birth.strftime('%d.%m.%Y')}</b>\n"
        f"🎈 Yosh: <b>{age}</b>\n\n"
        "⚠️ <b>Diqqat!</b>\n"
        "Tasdiqlaganingizdan keyin tug‘ilgan sanani o‘zgartirib "
        "bo‘lmaydi.\n\n"
        "Sana to‘g‘rimi?",
        reply_markup=career_confirm_birth_kb(),
    )

    return True


async def cb_career(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data
    user = q.from_user
    if not user:
        return

    # 🔄 Qayta ro'yxatdan o'tish (rereg_allowed): jins → tug'ilgan sana → kasb
    if data == "career:rereg" or data.startswith("career:rgender:"):
        if not rereg_allowed(user.id):
            await q.message.reply_text("⛔ Bu funksiya siz uchun yoqilmagan.")
            return
        if q.message.chat.type != ChatType.PRIVATE:
            await q.message.reply_text("👤 Qayta ro‘yxatdan o‘tish uchun botning shaxsiy chatida /profil oching.")
            return
        if data == "career:rereg":
            await q.message.reply_text(
                "🔄 <b>Qayta ro‘yxatdan o‘tish</b>\n\n1️⃣ Jinsingizni tanlang:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👦 Erkak", callback_data="career:rgender:male"),
                    InlineKeyboardButton("👧 Ayol", callback_data="career:rgender:female"),
                ]]),
            )
            return
        gender = data.rsplit(":", 1)[1]
        if gender not in ("male", "female"):
            return
        c = db()
        with c:
            c.execute(
                """INSERT INTO user_gender(user_id, gender, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET gender=excluded.gender, updated_at=excluded.updated_at""",
                (user.id, gender, datetime.now().isoformat(timespec="seconds")),
            )
            c.execute(
                "UPDATE users SET birth_date=NULL, birth_confirmed=0, profession_id=NULL, profession_selected=0 "
                "WHERE user_id=?", (user.id,),
            )
        await q.message.reply_text("✅ Jins saqlandi.\n\n2️⃣ Endi tug‘ilgan sana:")
        await career_start_birth(update, context)
        return

    if data == "career:birth":
        await career_start_birth(update, context)
        return

    if data == "career:birth_yes":
        birth = context.user_data.get("career_birth")
        if not birth:
            await q.message.reply_text("❌ Sana topilmadi. Qaytadan kiriting.")
            return

        c = db()
        c.execute(
            """INSERT OR IGNORE INTO users
               (user_id, username, first_name, points, games, wins)
               VALUES (?, ?, ?, 0, 0, 0)""",
            (user.id, user.username, user.first_name)
        )
        c.execute(
            "UPDATE users SET birth_date=?, birth_confirmed=1 WHERE user_id=?",
            (birth, user.id)
        )
        c.execute(
            "INSERT OR IGNORE INTO user_career (user_id, career_xp) VALUES (?, 0)",
            (user.id,)
        )
        c.commit()

        context.user_data["career_state"] = "profession"
        await q.message.reply_text(
            "✅ Tug‘ilgan sana saqlandi!\n\n"
            "💼 <b>Endi kasbingizni tanlang:</b>",
            reply_markup=career_profession_kb(q.message.chat.id),
        )
        return

    if data == "career:apply_no":
        lang = LANG_CACHE.get(user.id, DEFAULT_LANG)
        text = CAREER_APPLY_TEXT.get(lang, CAREER_APPLY_TEXT["uz"])
        await q.edit_message_text(text["cancelled"])
        return

    if data == "career:apply_yes":
        row = career_get_user(user.id)
        lang = LANG_CACHE.get(user.id, DEFAULT_LANG)
        text = CAREER_APPLY_TEXT.get(lang, CAREER_APPLY_TEXT["uz"])

        if not row or not row[2]:
            await q.edit_message_text(
                {
                    "uz": "⚠️ Avval kasbingizni tanlang.",
                    "eng": "⚠️ Choose your profession first.",
                    "ru": "⚠️ Сначала выберите профессию.",
                    "kz": "⚠️ Алдымен мамандығыңызды таңдаңыз.",
                }.get(lang)
            )
            return

        await q.edit_message_text(
            text["choose"],
            parse_mode="HTML",
            reply_markup=career_profession_kb(user.id, request_mode=True),
        )
        return

    if data.startswith("career:request:"):
        try:
            profession_id = int(data.split(":")[-1])
        except ValueError:
            return

        if profession_id not in PROFESSION_NAMES:
            return

        row = career_get_user(user.id)
        lang = LANG_CACHE.get(user.id, DEFAULT_LANG)
        text = CAREER_APPLY_TEXT.get(lang, CAREER_APPLY_TEXT["uz"])

        if not row or not row[2]:
            await q.answer(
                {
                    "uz": "Avval kasbingizni tanlang.",
                    "eng": "Choose your profession first.",
                    "ru": "Сначала выберите профессию.",
                    "kz": "Алдымен мамандығыңызды таңдаңыз.",
                }.get(lang),
                show_alert=True,
            )
            return

        current_profession = row[2]

        if profession_id == current_profession:
            await q.answer(text["same"], show_alert=True)
            return

        pending = db().execute(
            """
            SELECT id FROM career_requests
            WHERE user_id=? AND status='pending'
            LIMIT 1
            """,
            (user.id,)
        ).fetchone()

        if pending:
            await q.answer(text["pending"], show_alert=True)
            return

        c = db()

        c.execute(
            """
            INSERT INTO career_requests
                (user_id, requested_profession_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (user.id, profession_id, datetime.utcnow().isoformat()),
        )

        request_id = c.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        c.commit()

        current_name = profession_name(current_profession, user.id)
        new_name = profession_name(profession_id, user.id)

        await q.edit_message_text(
            text["sent"].format(
                current=current_name,
                new=new_name,
            ),
            parse_mode="HTML",
        )

        applicant_name = escape(
            user.full_name or user.username or str(user.id)
        )

        for owner_id in CAREER_OWNER_IDS:
            owner_lang = LANG_CACHE.get(owner_id, DEFAULT_LANG)
            owner_text = CAREER_APPLY_TEXT.get(
                owner_lang,
                CAREER_APPLY_TEXT["uz"]
            )

            owner_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        owner_text["approve"],
                        callback_data=f"career:approve:{request_id}"
                    ),
                    InlineKeyboardButton(
                        owner_text["reject"],
                        callback_data=f"career:reject:{request_id}"
                    ),
                ]
            ])

            try:
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=owner_text["boss"].format(
                        name=applicant_name,
                        id=user.id,
                        current=current_name,
                        new=new_name,
                    ),
                    parse_mode="HTML",
                    reply_markup=owner_kb,
                )
            except Exception as e:
                logger.warning(
                    "Boshliqqa ariza yuborilmadi %s: %s",
                    owner_id,
                    e,
                )

        return

    if data.startswith("career:approve:") or data.startswith("career:reject:"):
        if user.id not in CAREER_OWNER_IDS:
            await q.answer("❌ Sizda bu amalni bajarish huquqi yo‘q.", show_alert=True)
            return

        parts = data.split(":")
        try:
            request_id = int(parts[-1])
        except ValueError:
            return

        c = db()

        request = c.execute(
            """
            SELECT user_id, requested_profession_id, status
            FROM career_requests
            WHERE id=?
            """,
            (request_id,)
        ).fetchone()

        if not request:
            await q.answer("❌ Ariza topilmadi.", show_alert=True)
            return

        target_user_id, requested_profession_id, status = request

        if status != "pending":
            await q.answer(
                f"ℹ️ Bu ariza allaqachon {status}.",
                show_alert=True,
            )
            return

        if data.startswith("career:approve:"):
            c.execute(
                """
                UPDATE users
                SET profession_id=?, profession_selected=1
                WHERE user_id=?
                """,
                (requested_profession_id, target_user_id),
            )

            c.execute(
                """
                UPDATE career_requests
                SET status='approved',
                    decided_by=?,
                    decided_at=?
                WHERE id=? AND status='pending'
                """,
                (
                    user.id,
                    datetime.utcnow().isoformat(),
                    request_id,
                ),
            )

            c.commit()

            await q.edit_message_reply_markup(reply_markup=None)
            await q.message.reply_text("✅ Ariza tasdiqlandi.")

            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=(
                        "🎉 <b>Kasb almashtirish arizangiz tasdiqlandi!</b>\n\n"
                        f"💼 Yangi kasbingiz: "
                        f"<b>{profession_name(requested_profession_id, target_user_id)}</b>"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(
                    "Foydalanuvchiga tasdiq xabari yuborilmadi: %s", e
                )

        else:
            c.execute(
                """
                UPDATE career_requests
                SET status='rejected',
                    decided_by=?,
                    decided_at=?
                WHERE id=? AND status='pending'
                """,
                (
                    user.id,
                    datetime.utcnow().isoformat(),
                    request_id,
                ),
            )

            c.commit()

            await q.edit_message_reply_markup(reply_markup=None)
            await q.message.reply_text("❌ Ariza rad etildi.")

            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=(
                        "❌ <b>Kasb almashtirish arizangiz rad etildi.</b>\n\n"
                        "💼 Hozirgi kasbingiz o‘zgarmadi."
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(
                    "Foydalanuvchiga rad javobi yuborilmadi: %s", e
                )

        return

    if data.startswith("career:request:"):
        try:
            profession_id = int(data.split(":")[-1])
        except ValueError:
            return

        if profession_id not in PROFESSION_NAMES:
            return

        row = career_get_user(user.id)

        if not row or not row[2]:
            await q.answer("Avval kasbingizni tanlang.", show_alert=True)
            return

        current_profession = row[2]

        if profession_id == current_profession:
            await q.answer(
                "❌ Hozirgi kasbingizni qayta tanlay olmaysiz.",
                show_alert=True,
            )
            return

        pending = db().execute(
            """
            SELECT id FROM career_requests
            WHERE user_id=? AND status='pending'
            LIMIT 1
            """,
            (user.id,)
        ).fetchone()

        if pending:
            await q.answer(
                "⏳ Sizda allaqachon pending ariza bor.",
                show_alert=True,
            )
            return

        c = db()

        c.execute(
            """
            INSERT INTO career_requests
                (user_id, requested_profession_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (
                user.id,
                profession_id,
                datetime.utcnow().isoformat(),
            ),
        )

        request_id = c.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        c.commit()

        current_name = profession_name(current_profession, user.id)
        new_name = profession_name(profession_id, user.id)

        await q.edit_message_text(
            "📨 <b>Ariza boshliqqa yuborildi!</b>\n\n"
            f"💼 Hozirgi kasb: {current_name}\n"
            f"🔄 Yangi kasb: {new_name}\n\n"
            "⏳ Boshliq qarorini kuting.",
            parse_mode="HTML",
        )

        applicant_name = escape(
            user.full_name or user.username or str(user.id)
        )

        owner_text = (
            "📨 <b>Yangi kasb almashtirish arizasi</b>\n\n"
            f"👤 Foydalanuvchi: <b>{applicant_name}</b>\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"💼 Hozirgi kasb: <b>{current_name}</b>\n"
            f"🔄 Yangi kasb: <b>{new_name}</b>\n\n"
            "Arizani ko‘rib chiqing:"
        )

        owner_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Tasdiqlash",
                    callback_data=f"career:approve:{request_id}"
                ),
                InlineKeyboardButton(
                    "❌ Rad etish",
                    callback_data=f"career:reject:{request_id}"
                ),
            ]
        ])

        for owner_id in CAREER_OWNER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=owner_text,
                    parse_mode="HTML",
                    reply_markup=owner_kb,
                )
            except Exception as e:
                logger.warning(
                    "Boshliqqa ariza yuborilmadi %s: %s",
                    owner_id,
                    e,
                )

        return

    if data.startswith("career:prof:"):
        try:
            profession_id = int(data.split(":")[-1])
        except ValueError:
            return

        if profession_id not in PROFESSION_NAMES:
            return

        c = db()
        row = c.execute(
            "SELECT birth_confirmed, profession_selected FROM users WHERE user_id=?",
            (user.id,)
        ).fetchone()

        if not row or not row[0]:
            await q.message.reply_text("❌ Avval tug‘ilgan sanangizni tasdiqlang.")
            return

        c.execute(
            """UPDATE users
               SET profession_id=?, profession_selected=1
               WHERE user_id=?""",
            (profession_id, user.id)
        )
        c.execute(
            "INSERT OR IGNORE INTO user_career (user_id, career_xp) VALUES (?, 0)",
            (user.id,)
        )
        c.commit()

        context.user_data.pop("career_state", None)
        context.user_data.pop("career_birth", None)
        context.user_data.pop("career_age", None)

        await q.message.reply_text(
            f"🎉 <b>Kasbingiz tanlandi!</b>\n\n"
            f"💼 {profession_name(profession_id, q.message.chat.id)}\n"
            f"⭐ Kasb XP: <b>0</b>\n\n"
            f"Endi o‘yinlarda qatnashib, kasb bo‘yicha XP va missiyalarni to‘plashingiz mumkin."
        )



CAREER_APPLY_TEXT = {
    "uz": {
        "confirm": "⚠️ <b>Kasb almashtirish</b>\n\nRostan ham ishdan bo‘shab, boshqa kasbga o‘tish haqidagi arizani boshliqqa yubormoqchimisiz?",
        "yes": "✅ Ha, yuborish",
        "no": "❌ Yo‘q, bekor qilish",
        "choose": "💼 <b>Yangi kasbingizni tanlang:</b>\n\nTanlagan kasbingiz boshliqqa ariza sifatida yuboriladi.",
        "sent": "📨 <b>Ariza boshliqqa yuborildi!</b>\n\n💼 Hozirgi kasb: {current}\n🔄 Yangi kasb: {new}\n\n⏳ Boshliq qarorini kuting.",
        "approved": "🎉 <b>Kasb almashtirish arizangiz tasdiqlandi!</b>\n\n💼 Yangi kasbingiz: <b>{new}</b>",
        "rejected": "❌ <b>Kasb almashtirish arizangiz rad etildi.</b>\n\n💼 Hozirgi kasbingiz o‘zgarmadi.",
        "boss": "📨 <b>Yangi kasb almashtirish arizasi</b>\n\n👤 Foydalanuvchi: <b>{name}</b>\n🆔 ID: <code>{id}</code>\n💼 Hozirgi kasb: <b>{current}</b>\n🔄 Yangi kasb: <b>{new}</b>\n\nArizani ko‘rib chiqing:",
        "approve": "✅ Tasdiqlash",
        "reject": "❌ Rad etish",
        "cancelled": "❌ Ariza bekor qilindi.",
        "pending": "⏳ Sizning kasb almashtirish arizangiz allaqachon ko‘rib chiqilmoqda.",
        "same": "❌ Hozirgi kasbingizni qayta tanlay olmaysiz.",
        "approved_boss": "✅ Ariza tasdiqlandi.",
        "rejected_boss": "❌ Ariza rad etildi.",
    },
    "eng": {
        "confirm": "⚠️ <b>Change of profession</b>\n\nAre you sure you want to resign from your current profession and send a request to the boss to change profession?",
        "yes": "✅ Yes, send",
        "no": "❌ No, cancel",
        "choose": "💼 <b>Choose your new profession:</b>\n\nYour selected profession will be sent to the boss as a request.",
        "sent": "📨 <b>Request sent to the boss!</b>\n\n💼 Current profession: {current}\n🔄 New profession: {new}\n\n⏳ Please wait for the boss's decision.",
        "approved": "🎉 <b>Your profession change request was approved!</b>\n\n💼 New profession: <b>{new}</b>",
        "rejected": "❌ <b>Your profession change request was rejected.</b>\n\n💼 Your current profession remains unchanged.",
        "boss": "📨 <b>New profession change request</b>\n\n👤 User: <b>{name}</b>\n🆔 ID: <code>{id}</code>\n💼 Current profession: <b>{current}</b>\n🔄 New profession: <b>{new}</b>\n\nPlease review the request:",
        "approve": "✅ Approve",
        "reject": "❌ Reject",
        "cancelled": "❌ Request cancelled.",
        "pending": "⏳ Your profession change request is already being reviewed.",
        "same": "❌ You cannot select your current profession.",
        "approved_boss": "✅ Request approved.",
        "rejected_boss": "❌ Request rejected.",
    },
    "ru": {
        "confirm": "⚠️ <b>Смена профессии</b>\n\nВы действительно хотите уволиться с текущей профессии и отправить начальнику заявление на смену профессии?",
        "yes": "✅ Да, отправить",
        "no": "❌ Нет, отменить",
        "choose": "💼 <b>Выберите новую профессию:</b>\n\nВыбранная профессия будет отправлена начальнику на рассмотрение.",
        "sent": "📨 <b>Заявление отправлено начальнику!</b>\n\n💼 Текущая профессия: {current}\n🔄 Новая профессия: {new}\n\n⏳ Ожидайте решения начальника.",
        "approved": "🎉 <b>Ваше заявление на смену профессии одобрено!</b>\n\n💼 Новая профессия: <b>{new}</b>",
        "rejected": "❌ <b>Ваше заявление на смену профессии отклонено.</b>\n\n💼 Ваша текущая профессия не изменена.",
        "boss": "📨 <b>Новое заявление на смену профессии</b>\n\n👤 Пользователь: <b>{name}</b>\n🆔 ID: <code>{id}</code>\n💼 Текущая профессия: <b>{current}</b>\n🔄 Новая профессия: <b>{new}</b>\n\nРассмотрите заявление:",
        "approve": "✅ Одобрить",
        "reject": "❌ Отклонить",
        "cancelled": "❌ Заявление отменено.",
        "pending": "⏳ Ваше заявление на смену профессии уже рассматривается.",
        "same": "❌ Нельзя выбрать текущую профессию.",
        "approved_boss": "✅ Заявление одобрено.",
        "rejected_boss": "❌ Заявление отклонено.",
    },
    "kz": {
        "confirm": "⚠️ <b>Мамандық ауыстыру</b>\n\nҚазіргі мамандығыңыздан шығып, басқа мамандыққа ауысу туралы өтінішті басшыға жібергіңіз келе ме?",
        "yes": "✅ Иә, жіберу",
        "no": "❌ Жоқ, бас тарту",
        "choose": "💼 <b>Жаңа мамандығыңызды таңдаңыз:</b>\n\nТаңдаған мамандығыңыз басшыға өтініш ретінде жіберіледі.",
        "sent": "📨 <b>Өтініш басшыға жіберілді!</b>\n\n💼 Қазіргі мамандық: {current}\n🔄 Жаңа мамандық: {new}\n\n⏳ Басшының шешімін күтіңіз.",
        "approved": "🎉 <b>Мамандық ауыстыру өтінішіңіз мақұлданды!</b>\n\n💼 Жаңа мамандығыңыз: <b>{new}</b>",
        "rejected": "❌ <b>Мамандық ауыстыру өтінішіңіз қабылданбады.</b>\n\n💼 Қазіргі мамандығыңыз өзгеріссіз қалды.",
        "boss": "📨 <b>Жаңа мамандық ауыстыру өтініші</b>\n\n👤 Пайдаланушы: <b>{name}</b>\n🆔 ID: <code>{id}</code>\n💼 Қазіргі мамандық: <b>{current}</b>\n🔄 Жаңа мамандық: <b>{new}</b>\n\nӨтінішті қараңыз:",
        "approve": "✅ Мақұлдау",
        "reject": "❌ Қабылдамау",
        "cancelled": "❌ Өтініш тоқтатылды.",
        "pending": "⏳ Мамандық ауыстыру өтінішіңіз қазірдің өзінде қаралуда.",
        "same": "❌ Қазіргі мамандығыңызды қайта таңдай алмайсыз.",
        "approved_boss": "✅ Өтініш мақұлданды.",
        "rejected_boss": "❌ Өтініш қабылданбады.",
    },
}

async def cmd_ariza(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kasb almashtirish arizasini boshlash."""
    if not update.effective_chat or update.effective_chat.type != ChatType.PRIVATE:
        lang = LANG_CACHE.get(update.effective_user.id, DEFAULT_LANG)
        await update.message.reply_text(
            {
                "uz": "ℹ️ /ariza buyrug‘ini bot bilan shaxsiy chatda ishlating.",
                "eng": "ℹ️ Use /ariza in a private chat with the bot.",
                "ru": "ℹ️ Используйте /ariza в личном чате с ботом.",
                "kz": "ℹ️ /ariza командасын ботпен жеке чатта пайдаланыңыз.",
            }.get(lang, "ℹ️ Use /ariza in a private chat with the bot.")
        )
        return

    user = update.effective_user
    save_user(user)

    lang = LANG_CACHE.get(user.id, DEFAULT_LANG)
    text = CAREER_APPLY_TEXT.get(lang, CAREER_APPLY_TEXT["uz"])

    row = career_get_user(user.id)

    if not row or not row[2]:
        await update.message.reply_text(
            {
                "uz": "⚠️ Avval kasbingizni tanlashingiz kerak.",
                "eng": "⚠️ You must choose a profession first.",
                "ru": "⚠️ Сначала выберите профессию.",
                "kz": "⚠️ Алдымен мамандығыңызды таңдауыңыз керек.",
            }.get(lang)
        )
        return

    pending = db().execute(
        """
        SELECT id FROM career_requests
        WHERE user_id=? AND status='pending'
        LIMIT 1
        """,
        (user.id,)
    ).fetchone()

    if pending:
        await update.message.reply_text(text["pending"])
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text["yes"],
                callback_data="career:apply_yes"
            ),
            InlineKeyboardButton(
                text["no"],
                callback_data="career:apply_no"
            ),
        ]
    ])

    await update.message.reply_text(
        text["confirm"],
        parse_mode="HTML",
        reply_markup=kb,
    )


async def career_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != ChatType.PRIVATE:
        return

    user = update.effective_user
    msg = update.effective_message
    if not user or not msg or not msg.text:
        return
    if not user.is_bot:
        save_user(user)
        mark_started(user.id)

    raw = msg.text.strip()
    if context.user_data.get("bank_purpose") and await bank_purpose_text(update, context):
        return
    if (context.user_data.get("gs_wait_welcome") or context.user_data.get("gs_wait_words")) \
            and await settings_private_text(update, context):
        return
    crash_state = context.user_data.get("panel_crash_state")
    if crash_state and user.id in CAREER_OWNER_IDS:
        if crash_state == "group_add":
            try:
                chat_id = int(raw)
                if chat_id >= 0:
                    raise ValueError
            except ValueError:
                await msg.reply_text("❌ Guruh ID manfiy son bo‘lishi kerak (masalan, -1001234567890). Qaytadan yuboring.")
                return
            title = str(chat_id)
            try:
                chat_obj = await context.bot.get_chat(chat_id)
                title = chat_obj.title or title
            except TelegramError:
                await msg.reply_text(
                    "❌ Bot bu guruhni topa olmadi. Bot guruhda borligini va ID to‘g‘riligini tekshiring."
                )
                return
            c = db()
            c.execute(
                "INSERT INTO crash_groups (chat_id, title) VALUES (?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title",
                (chat_id, title),
            )
            c.commit()
            crash_config_set("group_restrict", "1")
            load_crash_config()
            context.user_data.pop("panel_crash_state", None)
            await msg.reply_text(
                f"✅ Crash uchun <code>{chat_id}</code> guruhi ulandi.\n"
                "Endi Crash faqat ulangan guruhlarda ishlaydi.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Crash sozlamalari", callback_data="panel:crash")]]),
            )
            return
        if crash_state == "min_bet":
            try:
                amount = int(raw)
                if amount < 1 or amount > 1_000_000_000:
                    raise ValueError
            except ValueError:
                await msg.reply_text("❌ Minimal depozit 1 dan 1 000 000 000 gacha butun son bo‘lsin. Qaytadan yuboring.")
                return
            crash_config_set("min_bet", amount)
            load_crash_config()
            context.user_data.pop("panel_crash_state", None)
            await msg.reply_text(
                f"✅ Crash minimal depoziti <b>{amount}$</b> qilib belgilandi.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Crash sozlamalari", callback_data="panel:crash")]]),
            )
            return
    if context.user_data.get("panel_admin_add_state") == "waiting_id" and (
        user.id in CAREER_OWNER_IDS or panel_has_permission(user.id, "admin_management")
    ):
        try:
            aid = int(raw)
            if aid <= 0:
                raise ValueError
        except ValueError:
            await msg.reply_text("❌ Telegram ID musbat son bo‘lishi kerak. Qaytadan yuboring.")
            return

        if aid in CAREER_OWNER_IDS:
            await msg.reply_text("ℹ️ Bu foydalanuvchi allaqachon bot egasi.")
            return

        c = db()
        c.execute(
            "INSERT OR IGNORE INTO bot_panel_admins (user_id, added_by) VALUES (?, ?)",
            (aid, user.id),
        )
        c.commit()
        context.user_data.pop("panel_admin_add_state", None)

        if c.execute(
            "SELECT 1 FROM bot_panel_admins WHERE user_id = ?", (aid,)
        ).fetchone():
            await msg.reply_text(
                f"✅ <code>{aid}</code> adminlar ro‘yxatida.\n"
                "Bo‘lim ruxsatlarini adminlar ro‘yxatidan sozlang.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛡 Admin boshqaruvi", callback_data="panel:admins")
                ]]),
            )
        return

    if user.id in CAREER_OWNER_IDS and context.user_data.get("panel_stat_state"):
        await panel_stats_text(update, context)
        return

    if user.id in CAREER_OWNER_IDS and context.user_data.get("panel_bank_state"):
        await panel_bank_text(update, context)
        return

    if user.id in CAREER_OWNER_IDS and context.user_data.get("panel_kid_state") == "waiting_id":
        await panel_kid_handle_text(update, context)
        return

    if user.id in CAREER_OWNER_IDS and context.user_data.get("panel_rereg_state"):
        await panel_rereg_text(update, context)
        return

    if user.id in CAREER_OWNER_IDS and context.user_data.get("panel_fsub_state") == "waiting_channel":
        await panel_fsub_text(update, context)
        return

    if user.id in CAREER_OWNER_IDS and context.user_data.get("pemoji_state"):
        if await pemoji_handle_text(update, context):
            return

    if user.id in CAREER_OWNER_IDS:
        if context.user_data.get("panel_broadcast_state") == "waiting_text":
            if not raw:
                await msg.reply_text("Xabar matni bo‘sh bo‘lmasin.")
                return
            if len(raw) > 4096:
                await msg.reply_text("Xabar 4096 belgidan oshmasin.")
                return

            context.user_data["panel_broadcast_pending"] = raw
            context.user_data.pop("panel_broadcast_state", None)
            await msg.reply_text(
                "📢 Xabarni tekshiring:\n\n"
                f"{escape(raw)}\n\nYuborishni tasdiqlaysizmi?",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Tasdiqlash va yuborish", callback_data="panel:broadcast_confirm")],
                    [InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:broadcast_cancel")],
                ]),
            )
            return

        state = context.user_data.get("panel_money_state")
        raw = msg.text.strip()

        if state in ("bankrupt_target", "give_target"):
            target_row = None
            c = db()
            if raw.startswith("@"):
                target_row = c.execute(
                    "SELECT user_id, username, first_name FROM users "
                    "WHERE lower(username)=lower(?)",
                    (raw[1:],),
                ).fetchone()
            else:
                try:
                    target_id = int(raw)
                    target_row = c.execute(
                        "SELECT user_id, username, first_name FROM users WHERE user_id=?",
                        (target_id,),
                    ).fetchone()
                except ValueError:
                    pass

            if not target_row:
                await msg.reply_text(
                    "❌ Foydalanuvchi bazadan topilmadi. ID yoki @username ni tekshiring."
                )
                return

            target_id, username, first_name = target_row
            name = first_name or (f"@{username}" if username else str(target_id))
            context.user_data.pop("panel_money_state", None)

            if state == "bankrupt_target":
                context.user_data["panel_money_pending"] = {
                    "kind": "bankrupt_one", "user_id": target_id, "name": name
                }
                prompt = f"⚠️ {escape(name)} balansini 0 qilishni tasdiqlaysizmi?"
                buttons = [[InlineKeyboardButton("✅ Tasdiqlash", callback_data="panel:money_confirm")]]
            else:
                context.user_data["panel_money_target"] = {
                    "user_id": target_id, "name": name
                }
                context.user_data["panel_money_state"] = "give_one_amount"
                await msg.reply_text(
                    f"💸 {escape(name)} ga qancha pul yuborilsin? Faqat musbat butun son yuboring.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:money_cancel")
                    ]]),
                )
                return

            await msg.reply_text(
                prompt,
                reply_markup=InlineKeyboardMarkup([
                    buttons[0],
                    [InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:money_cancel")],
                ]),
            )
            return

        if state in ("give_all_amount", "give_one_amount"):
            try:
                amount = int(raw)
                if amount < 1 or amount > 1000000000:
                    raise ValueError
            except ValueError:
                await msg.reply_text("❌ 1 dan 1 000 000 000 gacha musbat butun son yuboring.")
                return

            if state == "give_all_amount":
                pending = {"kind": "give_all", "amount": amount}
                prompt = f"⚠️ Har bir foydalanuvchiga {amount} pul qo‘shilsinmi?"
            else:
                target = context.user_data.get("panel_money_target")
                if not target:
                    context.user_data.pop("panel_money_state", None)
                    await msg.reply_text("❌ Oluvchi topilmadi. Amalni qaytadan boshlang.")
                    return
                pending = {
                    "kind": "give_one", "amount": amount,
                    "user_id": target["user_id"], "name": target["name"],
                }
                prompt = f"⚠️ {escape(target['name'])} hisobiga {amount} pul qo‘shilsinmi?"

            context.user_data["panel_money_pending"] = pending
            context.user_data.pop("panel_money_state", None)
            await msg.reply_text(
                prompt,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Tasdiqlash", callback_data="panel:money_confirm")],
                    [InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:money_cancel")],
                ]),
            )
            return

    if context.user_data.get("shop_state") == "recipient":
        raw = msg.text.strip()
        target = None
        c = db()
        try:
            if raw.startswith("@"):
                username = raw[1:].strip()
                if not username or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
                    raise ValueError("invalid username")
                row = c.execute(
                    """SELECT user_id FROM users
                       WHERE lower(trim(username))=lower(?) LIMIT 1""",
                    (username,),
                ).fetchone()
                if row:
                    target = int(row[0])
                else:
                    # Username DBda eskirgan yoki yozuv tushib qolgan bo‘lishi mumkin.
                    # Telegram topa olsa, foydalanuvchi ma’lumotini DB bilan sinxronlaymiz.
                    chat = await context.bot.get_chat("@" + username)
                    if getattr(chat, "type", None) == ChatType.PRIVATE:
                        save_user(chat)
                        target = int(chat.id)
            else:
                if not re.fullmatch(r"[1-9]\d{4,19}", raw):
                    raise ValueError("invalid id")
                target_id = int(raw)
                row = c.execute("SELECT user_id FROM users WHERE user_id=?", (target_id,)).fetchone()
                if row:
                    target = target_id
            if target is None:
                raise ValueError("not started or not found")
            if target == user.id:
                await msg.reply_text("O‘zingizga sovg‘a yubora olmaysiz.")
                return
        except (TelegramError, ValueError):
            await msg.reply_text(
                "Foydalanuvchi topilmadi yoki botda /start bosmagan. ID yoki @username ni tekshiring."
            )
            return
        context.user_data.pop("shop_state", None)
        await show_gifts(user.id, context, target)
        return

    child = db().execute(
        """SELECT id,partner_id,pair_id,gender
           FROM child_requests
           WHERE requester_id=? AND status='selecting'
           AND gender IN ('boy','girl') AND child_name IS NULL
           ORDER BY id DESC LIMIT 1""",
        (user.id,),
    ).fetchone()

    if child:
        name = msg.text.strip()
        if not name or len(name) > 40:
            await msg.reply_text(family_text(user.id, "ask_name"))
            return

        rid, partner_id, pair_id, gender = child
        pair = active_pair(user.id)
        if not pair or pair[0] != pair_id or family_child_count(pair_id) >= 5:
            await msg.reply_text(family_text(user.id, "no_pair"))
            return

        with db():
            db().execute(
                "UPDATE child_requests SET child_name=?,status='pending' WHERE id=?",
                (name, rid),
            )

        request_text = family_text(
            partner_id, "request",
            parent=person_name(user.id),
            gender=escape(child_gender_label(partner_id, gender)),
            name=escape(name),
        )

        if user.id in CAREER_OWNER_IDS or partner_id in CAREER_OWNER_IDS:
            request_text = request_text.replace(
                "Rozilikdan so‘ng farzand 48 soat ichida yetkaziladi.",
                "Owner juftliklari uchun rozilikdan so‘ng farzand kutishsiz yetkaziladi.",
            )
            request_text = request_text.replace(
                "After consent, the child will arrive within 48 hours.",
                "For owner couples, the child arrives without a 48-hour wait after consent.",
            )
            request_text = request_text.replace(
                "После согласия ребёнок появится в течение 48 часов.",
                "Для пар с владельцем ребёнок появится сразу после согласия.",
            )
            request_text = request_text.replace(
                "Келісімнен кейін бала 48 сағат ішінде жеткізіледі.",
                "Иесі бар жұптарға бала келісімнен кейін күтусіз жеткізіледі.",
            )

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                family_text(partner_id, "yes"),
                callback_data=f"family:consent:yes:{rid}",
            ),
            InlineKeyboardButton(
                family_text(partner_id, "no"),
                callback_data=f"family:consent:no:{rid}",
            ),
        ]])

        try:
            await context.bot.send_message(
                partner_id, request_text, reply_markup=kb, parse_mode="HTML"
            )
        except TelegramError:
            with db():
                db().execute(
                    "UPDATE child_requests SET child_name=NULL,status='selecting' WHERE id=?",
                    (rid,),
                )
            await msg.reply_text(family_text(user.id, "need_start"))
            return

        await msg.reply_text(family_text(user.id, "sent"))
        return

    await career_handle_birth(update, context)



# ───────────────────── 🔐 YASHIRIN INLINE XABAR ─────────────────────

SECRET_LANGS = {
    "uz": {
        "title": "🔐 Yashirin xabar",
        "read": "👁 Xabarni o‘qish",
        "for": "Kimga",
        "not_found": "❌ Bu foydalanuvchi botda hali ro‘yxatdan o‘tmagan.",
        "empty": "✍️ Xabar yozing va oxiriga @username qo‘shing.",
        "not_for_you": "⛔ Bu xabar siz uchun emas.",
        "message": "🔐 Yashirin xabar:\n\n{}",
        "too_long": "📩 Xabar juda uzun. To‘liq xabarni olish uchun botga /start yuboring.",
    },
    "eng": {
        "title": "🔐 Secret message",
        "read": "👁 Read message",
        "for": "For",
        "not_found": "❌ This user has not registered with the bot yet.",
        "empty": "✍️ Write a message and add @username at the end.",
        "not_for_you": "⛔ This message is not for you.",
        "message": "🔐 Secret message:\n\n{}",
        "too_long": "📩 Message is too long. Send /start to the bot to receive it.",
    },
    "ru": {
        "title": "🔐 Секретное сообщение",
        "read": "👁 Прочитать",
        "for": "Для",
        "not_found": "❌ Этот пользователь ещё не зарегистрирован в боте.",
        "empty": "✍️ Напишите сообщение и добавьте @username в конце.",
        "not_for_you": "⛔ Это сообщение не для вас.",
        "message": "🔐 Секретное сообщение:\n\n{}",
        "too_long": "📩 Сообщение слишком длинное. Отправьте боту /start.",
    },
    "kz": {
        "title": "🔐 Құпия хабарлама",
        "read": "👁 Оқу",
        "for": "Кімге",
        "not_found": "❌ Бұл қолданушы ботта әлі тіркелмеген.",
        "empty": "✍️ Хабарлама жазып, соңына @username қосыңыз.",
        "not_for_you": "⛔ Бұл хабарлама сізге арналмаған.",
        "message": "🔐 Құпия хабарлама:\n\n{}",
        "too_long": "📩 Хабарлама тым ұзын. Ботқа /start жіберіңіз.",
    },
}


def secret_lang(user):
    """Inline rejimida guruh chat_id bo'lmagani uchun Telegram tilidan foydalanamiz."""
    code = (getattr(user, "language_code", None) or "").lower()

    if code.startswith("uz"):
        return "uz"
    if code.startswith("ru"):
        return "ru"
    if code.startswith(("kk", "kz")):
        return "kz"
    if code.startswith("en"):
        return "eng"

    return DEFAULT_LANG if DEFAULT_LANG in SECRET_LANGS else "uz"



async def secret_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query
    if not query:
        return

    user = query.from_user
    text = (query.query or "").strip()
    lang = secret_lang(user)
    tr = SECRET_LANGS[lang]

    # Format:
    #   Salom @username
    #   Salom 123456789
    m = re.match(
        r"^(?P<message>.+?)\s+(?:(?:@(?P<username>[A-Za-z0-9_]{5,32}))|(?P<user_id>\d+))$",
        text,
        re.S,
    )

    if not m:
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    id="secret-help",
                    title=tr["title"],
                    description=tr["empty"],
                    input_message_content=InputTextMessageContent(
                        tr["empty"]
                    ),
                )
            ] + inline_game_results(user),
            cache_time=0,
            is_personal=True,
        )
        return

    message_text = m.group("message").strip()
    username = m.group("username")
    user_id_text = m.group("user_id")

    if not message_text:
        await query.answer(
            results=[],
            cache_time=0,
            is_personal=True,
        )
        return

    if user_id_text:
        recipient_id = int(user_id_text)
        recipient_username = ""
        display_recipient = f"ID: {recipient_id}"
    else:
        recipient_id = 0
        recipient_username = username.lower()
        display_recipient = f"@{username}"

    token = secrets.token_urlsafe(18)

    c = db()
    with c:
        c.execute(
            """
            INSERT INTO secret_messages(
                token,
                sender_id,
                recipient_id,
                recipient_username,
                message_text,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                user.id,
                recipient_id,
                recipient_username,
                message_text,
                datetime.utcnow().isoformat(),
            ),
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                tr["read"],
                callback_data=f"secret:{token}",
            )
        ]
    ])

    card_text = (
        f"{tr['title']}\n"
        f"👤 {tr['for']}: {escape(display_recipient)}\n\n"
        f"👁 {tr['read']}"
    )

    await query.answer(
        results=[
            InlineQueryResultArticle(
                id=token,
                title=tr["title"],
                description=display_recipient,
                input_message_content=InputTextMessageContent(
                    card_text,
                    parse_mode=ParseMode.HTML,
                ),
                reply_markup=keyboard,
            )
        ],
        cache_time=0,
        is_personal=True,
    )


# ───────────────────── 🎮 INLINE O'YINLAR (XO · RSP · CRASH) ─────────────────────
# @bot yozilganda chiqadigan ro'yxatda o'yinlar ham bor. Tanlangan o'yin xabari
# yuboriladi; o'yin esa birinchi tugma bosilganda (inline_message_id ma'lum
# bo'lganda) yaratiladi va oddiy XO / RSP / Crash callback'lari bilan davom etadi.

INLINE_GAME_DESC = {
    "uz": {"xo": "Do‘stingiz bilan XO o‘ynang", "rsp": "Ikki kishilik tosh-qaychi-qog‘oz", "crash": "Pul tikib roketni kuzating",
           "memory": "Ikki kishilik juftlik topish o‘yini"},
    "eng": {"xo": "Play XO with a friend", "rsp": "Rock-paper-scissors for two", "crash": "Bet and watch the rocket",
            "memory": "Memory pairs game for two"},
    "ru": {"xo": "Сыграйте в XO с другом", "rsp": "Камень-ножницы-бумага на двоих", "crash": "Сделайте ставку и следите за ракетой",
           "memory": "Игра «найди пару» на двоих"},
    "kz": {"xo": "Досыңызбен XO ойнаңыз", "rsp": "Екі адамға тас-қайшы-қағаз", "crash": "Ақша салып, зымыранды бақылаңыз",
           "memory": "Екі адамға арналған жұп табу ойыны"},
}


def inline_lang(user):
    return LANG_CACHE.get(user.id) or secret_lang(user)


def inline_game_results(user):
    lang = inline_lang(user)
    save_user(user)
    name = uname(user)
    texts = LANGS.get(lang, LANGS[DEFAULT_LANG])
    crash_texts = CRASH_TEXT.get(lang, CRASH_TEXT["uz"])
    desc = INLINE_GAME_DESC.get(lang, INLINE_GAME_DESC["uz"])

    def article(kind, title, text, join_label, data=None, description=None):
        return InlineQueryResultArticle(
            id=f"game-{kind}",
            title=title,
            description=description or desc[kind],
            input_message_content=InputTextMessageContent(text, parse_mode=ParseMode.HTML),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                join_label, callback_data=data or f"ix:{kind}:{user.id}:{lang}",
            )]]),
        )

    memory_texts = MEMORY_TEXT.get(lang, MEMORY_TEXT["uz"])
    frog_texts = FROG_TEXT.get(lang, FROG_TEXT["uz"])

    results = [
        article("xo", texts["btn_xo"], texts["xo_lobby"].format(owner=name), texts["btn_join"]),
        article(
            "rsp", texts["btn_rsp"],
            texts["rsp_lobby"].format(current=1, count=2, players=f"🙋 {name}\n⬜ …"),
            texts["btn_join"],
        ),
        article(
            "memory", memory_texts["btn"],
            memory_texts["lobby"].format(players=1, names=f"🙋 {name}"),
            memory_texts["join"],
        ),
        # Qurbaqa — bir kishilik: birinchi "Qo'shilish" ni bosgan odam o'ynaydi.
        article(
            "frog", frog_texts["btn"],
            frog_texts["lobby"].format(min=FROG_MIN_BET),
            frog_texts["join"], data=f"fr:join:{lang}", description=frog_texts["desc"],
        ),
    ]
    if CRASH_ENABLED and not CRASH_GROUP_RESTRICT:
        results.append(article(
            "crash", crash_texts["btn"],
            crash_texts["lobby"].format(min=CRASH_MIN_BET, sec=CRASH_COUNTDOWN),
            crash_texts["b_join"],
        ))
    return results


async def cb_inline_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q.inline_message_id:
        await q.answer()
        return

    _, kind, owner_text, lang = q.data.split(":")
    owner_id = int(owner_text)
    key = game_key(q)
    user = q.from_user

    # Majburiy obuna: inline o'yinlarda ham a'zolik tekshiriladi.
    if await fsub_block_cb(q, context):
        return

    if key not in LANG_CACHE:
        set_inline_lang(key, lang)

    game = GAMES.get(key)
    if game:
        # O'yin allaqachon boshlangan (masalan, tugma eski holatda qolgan).
        if kind == "crash" and game["type"] == "crash":
            await crash_action(q, context, "join")
        else:
            await q.answer(t(key, "gone"), show_alert=True)
        return

    app = context.application

    if kind == "crash":
        if not CRASH_ENABLED or not crash_group_allowed(key):
            await q.answer("⛔ Crash hozir faol emas.", show_alert=True)
            return
        # Puli yetmagan foydalanuvchi bosganda bo'sh raund ochilib qolmasin.
        if wallet_balance(user.id) < CRASH_MIN_BET:
            await q.answer(cr_t(key, "no_funds", min=CRASH_MIN_BET), show_alert=True)
            return
        game = new_game(
            key, "crash", owner_id,
            state="lobby", players={}, dropped=[], cp=None, t0=None, t_crash=None,
            charged=False, settled=False,
        )
        arm(app, key, game, CRASH_LOBBY_TTL)
        await crash_action(q, context, "join")
        return

    if kind == "memory":
        # O'yinni yuborgan odam maydonni tanlaydi; boshqa odam bosgan bo'lsa, u darhol ikkinchi o'yinchi.
        save_user(user)
        names = {owner_id: pretty_name(*inline_owner_row(owner_id))}
        if user.id != owner_id:
            names[user.id] = uname(user)
        game = new_game(key, "memory", owner_id, state="setup", names=names)
        await q.answer()
        await edit(context.bot, key, None, memory_t(key, "choose"), memory_category_kb())
        arm(app, key, game, MEMORY_SETUP_TTL)
        return

    if user.id == owner_id:
        await q.answer(t(key, "xo_own" if kind == "xo" else "rsp_already"), show_alert=True)
        return

    save_user(user)
    names = {owner_id: pretty_name(*inline_owner_row(owner_id)), user.id: uname(user)}

    if kind == "xo":
        ids = [owner_id, user.id]
        random.shuffle(ids)
        game = new_game(
            key, "xo", owner_id,
            state="play", names=names, board=[""] * 9,
            seat={"X": ids[0], "O": ids[1]}, turn="X",
        )
        await q.answer()
        await edit(context.bot, key, None, xo_turn_text(key, game), xo_keyboard(key, game))
        arm(app, key, game, XO_MOVE_TTL)
        return

    # kind == "rsp": shaxsiy yozishmada ikki kishi o'ynaydi
    game = new_game(
        key, "rsp", owner_id,
        state="choose", count=2, names=names, choices={},
    )
    await q.answer()
    await edit(context.bot, key, None, rsp_choose_text(key, game), rsp_choice_kb(key))
    arm(app, key, game, RSP_CHOOSE_TTL)


def inline_owner_row(user_id):
    row = db().execute(
        "SELECT first_name, username FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    return row if row else (None, None)


async def secret_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    token = data.split(":", 1)[1] if ":" in data else ""

    if not token:
        await query.answer()
        return

    c = db()

    row = c.execute(
        """
        SELECT
            recipient_id,
            recipient_username,
            message_text
        FROM secret_messages
        WHERE token = ?
        LIMIT 1
        """,
        (token,),
    ).fetchone()

    if not row:
        await query.answer(
            "❌ Xabar topilmadi yoki muddati tugagan.",
            show_alert=True,
        )
        return

    recipient_id, recipient_username, message_text = row

    clicker_id = query.from_user.id
    clicker_username = (
        query.from_user.username or ""
    ).lower()

    # ID orqali yuborilgan yashirin xabar
    if recipient_id:
        if clicker_id != int(recipient_id):
            await query.answer(
                "⛔ Bu xabar siz uchun emas.",
                show_alert=True,
            )
            return

    # Username orqali yuborilgan yashirin xabar
    else:
        if (
            not clicker_username
            or clicker_username != recipient_username.lower()
        ):
            await query.answer(
                "⛔ Bu xabar siz uchun emas.",
                show_alert=True,
            )
            return

    if len(message_text) <= 200:
        await query.answer(
            message_text,
            show_alert=True,
        )
        return

    lang = secret_lang(query.from_user)
    tr = SECRET_LANGS[lang]

    try:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=tr["message"].format(message_text),
        )

        await query.answer(
            "📩 To‘liq yashirin xabar shaxsiy chatga yuborildi.",
            show_alert=True,
        )

    except TelegramError:
        await query.answer(
            message_text[:197] + "...",
            show_alert=True,
        )




SHOP_GIFTS = {"ring": ("💍 Uzuk", 100), "bear": ("🧸 Ayiqcha", 75),
              "bouquet": ("💐 Guldasta", 50), "rose": ("🌹 Atirgul", 25),
              "diamond": ("💎 Olmos", 200)}

def init_economy():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS contest_config (
        key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS money_contests (
      id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
      owner_id INTEGER NOT NULL, amount INTEGER NOT NULL, winners INTEGER NOT NULL,
      remaining INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL, message_id INTEGER);
    CREATE TABLE IF NOT EXISTS money_contest_claims (
      contest_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
      PRIMARY KEY(contest_id,user_id));
    CREATE TABLE IF NOT EXISTS gift_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER NOT NULL,
      recipient_id INTEGER NOT NULL, gift_key TEXT NOT NULL, price INTEGER NOT NULL,
      created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS hadya_contests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            remaining INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            message_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS premium_emoji (
            scope TEXT NOT NULL,
            key TEXT NOT NULL,
            emoji_id TEXT NOT NULL,
            PRIMARY KEY (scope, key)
        );
        CREATE TABLE IF NOT EXISTS hadya_claims (
            contest_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            gift_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (contest_id, user_id)
        );

    """)
    # Existing DB migration: remember the public contest message so it can be edited live.
    contest_columns = {row[1] for row in c.execute("PRAGMA table_info(money_contests)").fetchall()}
    if "message_id" not in contest_columns:
        c.execute("ALTER TABLE money_contests ADD COLUMN message_id INTEGER")
    c.commit()


# ───────────────────── Premium emoji (Telegram custom emoji) ─────────────────────
# Owner paneldan sozlanadi: "✨ Premium emoji". Ikki alohida bo'lim:
#   • gift    — sovg'alar (uzuk, ayiqcha, ...) uchun premium emoji
#   • profile — profil matnidagi oddiy emojilarni almashtirish
# Premium emoji ID egasi premium emojini botga yuborganda avtomatik olinadi.

PEMOJI_GIFT_KEYS = ["ring", "bear", "bouquet", "rose", "diamond"]
# Profilda ishlatiladigan belgilarni alohida premium emoji bilan sozlash.
PEMOJI_PROFILE_KEYS = [
    ("👤", "Ism / profil sarlavhasi"),
    ("🎂", "Tug‘ilgan sana"),
    ("🎈", "Yosh"),
    ("🎖", "Daraja"),
    ("💰", "Ball"),
    ("💵", "Pul"),
    ("💼", "Kasb"),
    ("⭐", "Kasb XP"),
    ("🎮", "O‘yinlar"),
    ("🏆", "G‘alabalar"),
    ("💔", "Mag‘lubiyatlar"),
    ("🤝", "Duranglar / juftlik"),
    ("📊", "G‘alaba foizi"),
]
_FE0F = "️"


def pemoji_enabled(scope):
    row = db().execute(
        "SELECT value FROM contest_config WHERE key=?", (f"pemoji_{scope}",)
    ).fetchone()
    return bool(row and str(row[0]) == "1")


def pemoji_set_enabled(scope, value):
    c = db()
    with c:
        c.execute(
            "INSERT INTO contest_config(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (f"pemoji_{scope}", "1" if value else "0"),
        )


def pemoji_get(scope, key):
    row = db().execute(
        "SELECT emoji_id FROM premium_emoji WHERE scope=? AND key=?",
        (scope, key),
    ).fetchone()
    return row[0] if row else None


def pemoji_save(scope, key, emoji_id):
    c = db()
    with c:
        c.execute(
            "INSERT INTO premium_emoji(scope, key, emoji_id) VALUES(?,?,?) "
            "ON CONFLICT(scope, key) DO UPDATE SET emoji_id=excluded.emoji_id",
            (scope, key, str(emoji_id)),
        )


def pemoji_delete(scope, key):
    c = db()
    with c:
        c.execute("DELETE FROM premium_emoji WHERE scope=? AND key=?", (scope, key))


def pemoji_tag(emoji_id, fallback):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def gift_label_html(key, label=None):
    """Sovg'a nomi (HTML). Premium emoji yoqilgan bo'lsa, boshidagi emoji almashadi."""
    if label is None:
        label = SHOP_GIFTS.get(key, (key, 0))[0]
    safe = escape(label)
    try:
        if key in SHOP_GIFTS and pemoji_enabled("gift"):
            emoji_id = pemoji_get("gift", key)
            if emoji_id:
                first, sep, rest = label.partition(" ")
                if sep:
                    return pemoji_tag(emoji_id, first) + " " + escape(rest)
                return pemoji_tag(emoji_id, first)
    except sqlite3.Error:
        logger.exception("Premium emoji (gift) o'qishda xato")
    return safe


def profile_emojify(text):
    """Profil matnidagi sozlangan oddiy emojilarni premium emojiga almashtiradi."""
    try:
        if not pemoji_enabled("profile"):
            return text
        rows = db().execute(
            "SELECT key, emoji_id FROM premium_emoji WHERE scope='profile'"
        ).fetchall()
    except sqlite3.Error:
        logger.exception("Premium emoji (profile) o'qishda xato")
        return text
    if not rows:
        return text
    mapping = {k: i for k, i in rows}
    pattern = "|".join(
        re.escape(k) + _FE0F + "?"
        for k in sorted(mapping, key=len, reverse=True)
    )

    def repl(m):
        ch = m.group(0).replace(_FE0F, "")
        return pemoji_tag(mapping[ch], m.group(0)) if ch in mapping else m.group(0)

    return re.sub(pattern, repl, text)


def pemoji_menu_markup():
    g_on = pemoji_enabled("gift")
    p_on = pemoji_enabled("profile")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Sovg‘alar emojisi " + ("✅" if g_on else "❌"),
                              callback_data="panel:pemoji:gifts")],
        [InlineKeyboardButton("👤 Profil emojilari " + ("✅" if p_on else "❌"),
                              callback_data="panel:pemoji:profile")],
        [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
    ])


PEMOJI_NOTE = (
    "ℹ️ Premium emoji ko‘rinishi uchun: ID ni emojini <b>Premium akkauntdan</b> "
    "yuborganingizda bot o‘zi oladi. Telegram qoidasiga ko‘ra botning matnlarida "
    "premium emoji ko‘rinishi uchun bot egasi Premium bo‘lishi yoki botda qo‘shimcha "
    "username (Fragment) bo‘lishi kerak. Aks holda oddiy emoji ko‘rinaveradi."
)


async def _pemoji_edit(query, text, markup):
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


async def pemoji_show_gifts(query):
    lines = [
        "🎁 <b>SOVG‘ALAR — PREMIUM EMOJI</b>",
        "",
        "Sovg‘ani tanlang va unga premium emoji yuboring.",
        "Holati: " + ("✅ yoqilgan" if pemoji_enabled("gift") else "❌ o‘chirilgan"),
        "",
    ]
    buttons = []
    for key in PEMOJI_GIFT_KEYS:
        label = SHOP_GIFTS[key][0]
        emoji_id = pemoji_get("gift", key)
        lines.append(f"{escape(label)} — " + (f"✅ <code>{emoji_id}</code>" if emoji_id else "❌ o‘rnatilmagan"))
        row = [InlineKeyboardButton(("✏️ " if emoji_id else "➕ ") + label,
                                    callback_data=f"panel:pemoji:gset:{key}")]
        if emoji_id:
            row.append(InlineKeyboardButton("🗑", callback_data=f"panel:pemoji:gdel:{key}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(
        "🔴 O‘chirish" if pemoji_enabled("gift") else "🟢 Yoqish",
        callback_data="panel:pemoji:gtoggle")])
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="panel:pemoji")])
    lines += ["", PEMOJI_NOTE]
    await _pemoji_edit(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def pemoji_show_profile(query):
    rows = db().execute(
        "SELECT key, emoji_id FROM premium_emoji WHERE scope='profile' ORDER BY rowid"
    ).fetchall()
    saved = {key: emoji_id for key, emoji_id in rows}
    lines = [
        "👤 <b>PROFIL — PREMIUM EMOJI</b>",
        "",
        "Profil ko‘rinishidagi belgini tanlang. Har bir belgi uchun alohida premium emoji o‘rnatish yoki o‘chirish mumkin.",
        "Holati: " + ("✅ yoqilgan" if pemoji_enabled("profile") else "❌ o‘chirilgan"),
        "",
    ]
    buttons = []
    for key, label in PEMOJI_PROFILE_KEYS:
        emoji_id = saved.get(key)
        lines.append(
            f"{key} <b>{escape(label)}</b> — " +
            (f"✅ <code>{emoji_id}</code>" if emoji_id else "▫️ standart emoji")
        )
        row = [InlineKeyboardButton(
            ("✏️ " if emoji_id else "➕ ") + key + " " + label,
            callback_data=f"panel:pemoji:pset:{key}"
        )]
        if emoji_id:
            row.append(InlineKeyboardButton(
                "🗑", callback_data=f"panel:pemoji:pdelkey:{key}"
            ))
        buttons.append(row)
    known = {key for key, _ in PEMOJI_PROFILE_KEYS}
    extras = [(key, emoji_id) for key, emoji_id in rows if key not in known]
    if extras:
        lines += ["", "<b>Qo‘shimcha saqlangan emojilar:</b>"]
        for key, emoji_id in extras:
            lines.append(f"{escape(key)} → <code>{emoji_id}</code>")
            buttons.append([InlineKeyboardButton(
                f"🗑 {key} ni o‘chirish", callback_data=f"panel:pemoji:pdelkey:{key}"
            )])
    buttons.append([InlineKeyboardButton(
        "🔴 O‘chirish" if pemoji_enabled("profile") else "🟢 Yoqish",
        callback_data="panel:pemoji:ptoggle")])
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="panel:pemoji")])
    lines += ["", PEMOJI_NOTE]
    await _pemoji_edit(query, "\n".join(lines), InlineKeyboardMarkup(buttons))

async def pemoji_callback(query, context):
    """panel:pemoji... callbacklari (faqat bot egalari)."""
    data = query.data
    context.user_data.pop("pemoji_state", None)
    parts = data.split(":")  # panel:pemoji[:action[:arg]]
    action = parts[2] if len(parts) > 2 else ""
    arg = parts[3] if len(parts) > 3 else ""

    if action == "":
        await _pemoji_edit(
            query,
            "✨ <b>PREMIUM EMOJI SOZLAMALARI</b>\n\nQaysi bo‘limni sozlaysiz?",
            pemoji_menu_markup(),
        )
    elif action == "gifts":
        await pemoji_show_gifts(query)
    elif action == "profile":
        await pemoji_show_profile(query)
    elif action == "gtoggle":
        pemoji_set_enabled("gift", not pemoji_enabled("gift"))
        await pemoji_show_gifts(query)
    elif action == "ptoggle":
        pemoji_set_enabled("profile", not pemoji_enabled("profile"))
        await pemoji_show_profile(query)
    elif action == "gdel" and arg in SHOP_GIFTS:
        pemoji_delete("gift", arg)
        await pemoji_show_gifts(query)
    elif action == "pdel":
        rows = db().execute(
            "SELECT key FROM premium_emoji WHERE scope='profile' ORDER BY rowid"
        ).fetchall()
        try:
            pemoji_delete("profile", rows[int(arg)][0])
        except (ValueError, IndexError):
            pass
        await pemoji_show_profile(query)
    elif action == "pdelkey" and arg:
        pemoji_delete("profile", arg)
        await pemoji_show_profile(query)
    elif action == "pset" and arg:
        context.user_data["pemoji_state"] = {"scope": "profile", "key": arg}
        await _pemoji_edit(
            query,
            f"<b>{escape(arg)}</b> belgisi uchun premium emoji yuboring. "
            "Yuborgan premium emoji tanlangan belgining o‘rnida ko‘rinadi.",
            InlineKeyboardMarkup([[InlineKeyboardButton(
                "❌ Bekor qilish", callback_data="panel:pemoji:profile")]]),
        )
    elif action == "gset" and arg in SHOP_GIFTS:
        context.user_data["pemoji_state"] = {"scope": "gift", "key": arg}
        await _pemoji_edit(
            query,
            f"{escape(SHOP_GIFTS[arg][0])} uchun <b>premium emoji</b> yuboring "
            "(bitta emoji bo‘lgan xabar).",
            InlineKeyboardMarkup([[InlineKeyboardButton(
                "❌ Bekor qilish", callback_data="panel:pemoji:gifts")]]),
        )
    elif action == "padd":
        context.user_data["pemoji_state"] = {"scope": "profile", "key": None}
        await _pemoji_edit(
            query,
            "Premium emoji(lar)ni yuboring. Bot ularning oddiy ko‘rinishini topib, "
            "profilda shu oddiy emoji o‘rniga premium emojini qo‘yadi.\n"
            "Masalan, 💞 ning premium variantini yuborsangiz — profildagi barcha 💞 almashadi.",
            InlineKeyboardMarkup([[InlineKeyboardButton(
                "❌ Bekor qilish", callback_data="panel:pemoji:profile")]]),
        )
    else:
        await _pemoji_edit(query, "✨ <b>PREMIUM EMOJI SOZLAMALARI</b>", pemoji_menu_markup())


async def pemoji_handle_text(update, context):
    """Owner premium emoji yuborganda ID ni saqlaydi. Qayta ishlangan bo'lsa True."""
    state = context.user_data.get("pemoji_state")
    msg = update.effective_message
    if not state or not msg:
        return False

    entities = [e for e in (msg.entities or msg.caption_entities or [])
                if e.type == "custom_emoji"]
    if not entities:
        await msg.reply_text(
            "❌ Xabarda premium emoji topilmadi. Premium akkauntdan premium emoji yuboring.",
        )
        return True

    if state["scope"] == "gift":
        pemoji_save("gift", state["key"], entities[0].custom_emoji_id)
        context.user_data.pop("pemoji_state", None)
        pemoji_set_enabled("gift", True)
        await msg.reply_text(
            f"✅ {escape(SHOP_GIFTS[state['key']][0])} uchun premium emoji saqlandi "
            "va sovg‘alar premium emoji yoqildi.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                "🎁 Sovg‘alar emojisi", callback_data="panel:pemoji:gifts")]]),
        )
        return True

    saved = []
    selected_key = state.get("key")
    if selected_key:
        pemoji_save("profile", selected_key, entities[0].custom_emoji_id)
        saved.append(selected_key)
    else:
        for e in entities:
            fallback = msg.parse_entity(e).replace(_FE0F, "")
            if not fallback:
                continue
            pemoji_save("profile", fallback, e.custom_emoji_id)
            saved.append(fallback)
    context.user_data.pop("pemoji_state", None)
    if saved:
        pemoji_set_enabled("profile", True)
    await msg.reply_text(
        ("✅ Saqlandi: " + " ".join(escape(x) for x in saved) + "\nProfil premium emoji yoqildi.")
        if saved else "❌ Emoji aniqlanmadi.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
            "👤 Profil emojilari", callback_data="panel:pemoji:profile")]]),
    )
    return True


def wallet_balance(user_id):
    c = db()
    row = c.execute(
        "SELECT money FROM user_wallet WHERE user_id=?",
        (user_id,)
    ).fetchone()
    return int(row[0] or 0) if row else 0

def is_money_owner(user_id):
    return False


async def cmd_hisob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message

    if not user or user.id not in CAREER_OWNER_IDS:
        await msg.reply_text("⛔ Bu buyruq faqat bot egalari uchun.")
        return

    if len(context.args) != 1:
        await msg.reply_text("Foydalanish: /hisob 100000")
        return

    try:
        amount = int(context.args[0])
    except (ValueError, TypeError):
        await msg.reply_text("❌ Miqdor butun son bo‘lishi kerak.")
        return

    if amount <= 0 or amount > 10**9:
        await msg.reply_text("❌ Miqdor 1 dan 1 000 000 000 gacha bo‘lishi kerak.")
        return

    wallet_change(user.id, amount)
    balance = wallet_balance(user.id)
    await msg.reply_text(
        f"✅ Hamyoningizga {amount:,}$ qo‘shildi.\\n"
        f"💰 Joriy balans: {balance:,}$"
    )


async def log_money_event(bot, text):
    """Moliyaviy hodisani audit chatiga yuboradi; log xatosi asosiy amalni bekor qilmaydi."""
    try:
        await bot.send_message(
            chat_id=MONEY_LOG_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except TelegramError as exc:
        logger.warning("Moliyaviy log chatiga xabar yuborilmadi: %s", exc)

def wallet_change(user_id, delta):
    c = db()
    c.execute("INSERT OR IGNORE INTO user_wallet(user_id,money) VALUES(?,0)", (user_id,))
    c.execute("UPDATE user_wallet SET money=money+? WHERE user_id=?", (int(delta), user_id))
    c.commit()

def shop_url(context, payload):
    return f"https://t.me/{context.bot.username}?start=shop_{payload}"

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return
    lang = family_lang(user.id)
    labels = {"uz":"🛍 DO‘KON","eng":"🛍 SHOP","ru":"🛍 МАГАЗИН","kz":"🛍 ДҮКЕН"}
    who = {"uz":"Kimga yubormoqchisiz?","eng":"Who do you want to send it to?","ru":"Кому хотите отправить?","kz":"Кімге жібергіңіз келеді?"}
    kb = InlineKeyboardMarkup([
      [InlineKeyboardButton({"uz":"💞 Juftimga","eng":"💞 To my partner","ru":"💞 Моей паре","kz":"💞 Жұбыма"}.get(lang,"💞 Juftimga"), callback_data="shop:partner"),
       InlineKeyboardButton({"uz":"👤 Boshqaga","eng":"👤 Someone else","ru":"👤 Другому","kz":"👤 Басқаға"}.get(lang,"👤 Boshqaga"), callback_data="shop:other")],
      [InlineKeyboardButton(kid_t(user.id, "shop_btn"), url=family_url(context, "kids"))],
    ])
    await update.effective_message.reply_text(f"{labels.get(lang, labels['uz'])}\n\n{who.get(lang, who['uz'])}", reply_markup=kb)

async def show_gifts(chat_id, context, recipient_id):
    lang = family_lang(chat_id)
    title = {"uz":"🎁 Sovg‘ani tanlang:","eng":"🎁 Choose a gift:","ru":"🎁 Выберите подарок:","kz":"🎁 Сыйлықты таңдаңыз:"}.get(lang,"🎁 Sovg‘ani tanlang:")
    rows=[]
    for key,(name,price) in SHOP_GIFTS.items():
        localized = {
          "ring":{"uz":"💍 Uzuk","eng":"💍 Ring","ru":"💍 Кольцо","kz":"💍 Сақина"},
          "bear":{"uz":"🧸 Ayiqcha","eng":"🧸 Teddy bear","ru":"🧸 Мишка","kz":"🧸 Қонжық"},
          "bouquet":{"uz":"💐 Guldasta","eng":"💐 Bouquet","ru":"💐 Букет","kz":"💐 Гүл шоғы"},
          "rose":{"uz":"🌹 Atirgul","eng":"🌹 Rose","ru":"🌹 Роза","kz":"🌹 Раушан"},
          "diamond":{"uz":"💎 Olmos","eng":"💎 Diamond","ru":"💎 Алмаз","kz":"💎 Алмас"}
        }[key].get(lang,name)
        rows.append([InlineKeyboardButton(f"{localized} — {price}$", callback_data=f"shop:gift:{recipient_id}:{key}")])
    rows.append([InlineKeyboardButton({"uz":"🎁 Sovg‘alar","eng":"🎁 Gifts","ru":"🎁 Подарки","kz":"🎁 Сыйлықтар"}.get(lang,"🎁 Sovg‘alar"), url=shop_url(context,"catalog"))])
    await context.bot.send_message(chat_id, title, reply_markup=InlineKeyboardMarkup(rows))

async def cb_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    await q.answer()
    parts = q.data.split(":")

    if len(parts) < 2:
        return

    if parts[1] == "open":
        await cmd_shop(update, context)
        return

    if parts[1] == "partner":
        pair = active_pair(user.id)
        if not pair:
            await q.message.reply_text(family_text(user.id, "no_pair"))
            return
        recipient = pair[2] if pair[1] == user.id else pair[1]
        await show_gifts(user.id, context, recipient)
        return

    if parts[1] == "other":
        context.user_data["shop_state"] = "recipient"
        await q.message.reply_text({
            "uz": "Qabul qiluvchining Telegram ID raqami yoki @username'ini yuboring.",
            "eng": "Send recipient Telegram ID or @username.",
            "ru": "Отправьте Telegram ID или @username получателя.",
            "kz": "Алушының Telegram ID-сін немесе @username жіберіңіз.",
        }.get(family_lang(user.id), "ID yoki @username yuboring."))
        return

    if parts[1] != "gift" or len(parts) != 4:
        return

    try:
        recipient = int(parts[2])
    except ValueError:
        return

    key = parts[3]
    if key not in SHOP_GIFTS or recipient == user.id:
        await q.message.reply_text("Sovg‘a oluvchisi noto‘g‘ri.")
        return

    name, price = SHOP_GIFTS[key]
    c = db()
    owner = is_money_owner(user.id)
    gift_id = None

    try:
        with c:
            if not owner:
                cur = c.execute(
                    "UPDATE user_wallet SET money=money-? "
                    "WHERE user_id=? AND money>=?",
                    (price, user.id, price),
                )
                if cur.rowcount != 1:
                    insufficient = True
                else:
                    insufficient = False
            else:
                insufficient = False

            if not insufficient:
                cur = c.execute(
                    "INSERT INTO gift_log"
                    "(sender_id,recipient_id,gift_key,price,created_at) "
                    "VALUES(?,?,?,?,?)",
                    (
                        user.id, recipient, key, price,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                gift_id = cur.lastrowid
    except sqlite3.Error:
        await q.message.reply_text("Xatolik yuz berdi. Qayta urinib ko‘ring.")
        return

    if insufficient:
        await q.message.reply_text({
            "uz": "Hisobingizda yetarli pul mavjud emas.",
            "eng": "Insufficient balance.",
            "ru": "Недостаточно средств на счёте.",
            "kz": "Шотыңызда қаражат жеткіліксіз.",
        }.get(family_lang(user.id), "Hisobingizda yetarli pul mavjud emas."))
        return

    try:
        await context.bot.send_message(
            recipient,
            f"🎁 {person_name(user.id)} sizga {gift_label_html(key, name)} sovg‘a qildi!",
        )
    except TelegramError:
        try:
            with c:
                c.execute("DELETE FROM gift_log WHERE id=?", (gift_id,))
                if not owner:
                    c.execute(
                        "UPDATE user_wallet SET money=money+? WHERE user_id=?",
                        (price, user.id),
                    )
        except sqlite3.Error:
            await q.message.reply_text(
                "Sovg‘a yuborilmadi. Pulni avtomatik qaytarishda xatolik yuz berdi; "
                "balansni tekshirish kerak."
            )
            return

        await q.message.reply_text(
            "Sovg‘a yuborilmadi. Qabul qiluvchi bot bilan shaxsiy chatda /start "
            "qilishi kerak. To‘lov qaytarildi."
        )
        return

    await log_money_event(
        context.bot,
        "🎁 <b>SOVG‘A O‘TKAZMASI</b>\n"
        f"Kimdan: {person_name(user.id)} (ID: <code>{user.id}</code>)\n"
        f"Kimga: {person_name(recipient)} (ID: <code>{recipient}</code>)\n"
        f"Sovg‘a: {escape(name)}\nNarxi: <b>{price}$</b>\n"
        f"To‘lovchi owner: {'ha' if owner else 'yo‘q'}"
    )
    await q.message.reply_text(f"✅ {gift_label_html(key, name)} yuborildi!")

async def cmd_pul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    sender = update.effective_user

    if not msg or not sender or msg.chat.type not in (
        ChatType.GROUP, ChatType.SUPERGROUP
    ):
        return

    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text(
            "Pul yuborish uchun odamning xabariga reply qiling: /pul 200"
        )
        return

    try:
        amount = int(context.args[0]) if context.args else 0
    except (ValueError, TypeError):
        amount = 0

    if amount <= 0 or amount > 10**9:
        await msg.reply_text("Miqdor noto‘g‘ri. Masalan: /pul 200")
        return

    recipient = msg.reply_to_message.from_user
    if recipient.is_bot or recipient.id == sender.id:
        await msg.reply_text("O‘zingizga yoki botga pul yuborib bo‘lmaydi.")
        return

    c = db()
    owner = is_money_owner(sender.id)
    # Kredit pulini boshqa akkauntga o'tkazib, qarzni tashlab ketishning oldini olamiz.
    if not owner and active_loan(sender.id):
        await msg.reply_text("⛔ Faol kreditingiz bor — uni to‘lamaguningizcha pul yubora olmaysiz.")
        return
    try:
        with c:
            if not owner:
                # Pul faqat balans yetarli bo‘lsa yechiladi.
                cur = c.execute(
                    "UPDATE user_wallet SET money=money-? "
                    "WHERE user_id=? AND money>=?",
                    (amount, sender.id, amount),
                )
                if cur.rowcount != 1:
                    failed = True
                else:
                    failed = False
            else:
                failed = False

            if not failed:
                c.execute(
                    "INSERT OR IGNORE INTO user_wallet(user_id,money) "
                    "VALUES(?,0)",
                    (recipient.id,),
                )
                c.execute(
                    "UPDATE user_wallet SET money=money+? WHERE user_id=?",
                    (amount, recipient.id),
                )
    except sqlite3.Error:
        await msg.reply_text("Pul o‘tkazishda xatolik. Qayta urinib ko‘ring.")
        return

    if failed:
        await msg.reply_text("Hisobingizda yetarli pul mavjud emas.")
        return

    await log_money_event(
        context.bot,
        "💸 <b>PUL O‘TKAZMASI</b>\n"
        f"Kimdan: {person_name(sender.id)} (ID: <code>{sender.id}</code>)\n"
        f"Kimga: {person_name(recipient.id)} (ID: <code>{recipient.id}</code>)\n"
        f"Miqdor: <b>{amount}$</b>\nOwner orqali: {'ha' if owner else 'yo‘q'}"
    )
    await msg.reply_text(
        f"💸 {person_name(sender.id)} → "
        f"{person_name(recipient.id)}: {amount}$ yuborildi."
    )

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    event = update.my_chat_member
    if not event or event.chat.type != ChatType.CHANNEL:
        return

    member = event.new_chat_member
    if (
        member.status == ChatMemberStatus.ADMINISTRATOR
        and getattr(member, "can_post_messages", False)
        and event.from_user
        and event.from_user.id in CAREER_OWNER_IDS
    ):
        c = db()
        with c:
            c.execute(
                """INSERT INTO contest_config(key, value)
                   VALUES('contest_channel_id', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (str(event.chat.id),),
            )
        logger.info("Konkurs kanali avtomatik saqlandi: %s", event.chat.id)



def hadya_keyboard(contest_id, active=True):
    if not active:
        return None
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🎁 Sovg‘ani olish", callback_data=f"hadya:claim:{contest_id}")
    ]])


def hadya_post_text(contest_id):
    c = db()
    try:
        contest = c.execute(
            "SELECT id, amount, remaining, active FROM hadya_contests WHERE id=?",
            (contest_id,),
        ).fetchone()
        if not contest:
            return "🎁 Hadya topilmadi.", None

        _, amount, remaining, active = contest
        claims = c.execute(
            "SELECT display_name, gift_key FROM hadya_claims WHERE contest_id=? "
            "ORDER BY rowid DESC LIMIT 20",
            (contest_id,),
        ).fetchall()
        count = c.execute(
            "SELECT COUNT(*) FROM hadya_claims WHERE contest_id=?",
            (contest_id,),
        ).fetchone()[0]
    finally:
        c.close()

    _is_open = bool(active) and int(remaining) > 0
    lines = [
        "🎁 <b>HADYA BOSHLANDI!</b>" if _is_open else "🎁 <b>HADYA</b>",
        "",
        f"🎁 Sovg‘alar soni: <b>{amount}</b>",
        f"📦 Qolgan sovg‘alar: <b>{remaining}</b>",
        f"👥 Sovg‘a olganlar: <b>{count}</b>",
        "",
    ]
    if claims:
        lines.append("<b>🏆 G‘oliblar:</b>")
        for name, key in claims:
            lines.append(f"• {escape(name)} — {gift_label_html(key) if key in SHOP_GIFTS else escape(key)}")
    else:
        lines.append("🎉 Birinchi bo‘lib sovg‘ani oling!")

    is_active = bool(active) and int(remaining) > 0
    if not is_active:
        lines.extend(["", "✅ <b>Hadya yakunlandi.</b>"])
    return "\n".join(lines), hadya_keyboard(contest_id, is_active)


async def cmd_hadya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat:
        return
    args = context.args or []

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        await context.bot.send_message(
            chat_id=chat.id,
            text="Bu buyruqni guruhda yoki sozlangan kanalda ishlating."
        )
        return

    if len(args) != 1 or not args[0].isdigit() or not 1 <= int(args[0]) <= 1000:
        await context.bot.send_message(
            chat_id=chat.id,
            text="Foydalanish: /hadya 50\nSovg‘alar soni 1 dan 1000 gacha bo‘lishi kerak."
        )
        return

    if chat.type == ChatType.CHANNEL:
        c = db()
        try:
            row = c.execute(
                "SELECT value FROM contest_config WHERE key='contest_channel_id'"
            ).fetchone()
        finally:
            c.close()
        if not row or str(row[0]) != str(chat.id):
            return
        owner_id = user.id if user else min(CAREER_OWNER_IDS)
    else:
        if not user:
            return
        # Anonim guruh admini (guruh nomidan yozgan) — admin hisoblanadi.
        anonymous_admin = bool(
            msg.sender_chat and msg.sender_chat.id == chat.id
        )
        allowed = (
            anonymous_admin
            or user.id in CAREER_OWNER_IDS
            or panel_has_permission(user.id, "hadya")
        )
        if not allowed:
            try:
                member = await context.bot.get_chat_member(chat.id, user.id)
            except TelegramError:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text="⛔ Admin huquqini tekshirib bo‘lmadi."
                )
                return
            allowed = member.status in (
                ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
            )
        if not allowed:
            await context.bot.send_message(
                chat_id=chat.id,
                text="⛔ Hadya boshlash uchun guruh administratori bo‘lishingiz kerak."
            )
            return
        owner_id = user.id

    amount = int(args[0])
    c = db()
    try:
        cur = c.execute(
            "INSERT INTO hadya_contests "
            "(chat_id, owner_id, amount, remaining, active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (chat.id, owner_id, amount, amount, datetime.now().isoformat(timespec="seconds")),
        )
        contest_id = cur.lastrowid
        c.commit()
    finally:
        c.close()

    text, keyboard = hadya_post_text(contest_id)
    try:
        posted = await context.bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    except TelegramError:
        c = db()
        try:
            c.execute("DELETE FROM hadya_contests WHERE id=?", (contest_id,))
            c.commit()
        finally:
            c.close()
        raise

    c = db()
    try:
        c.execute(
            "UPDATE hadya_contests SET message_id=? WHERE id=?",
            (posted.message_id, contest_id),
        )
        c.commit()
    finally:
        c.close()


async def cb_hadya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.from_user:
        return

    match = re.fullmatch(r"hadya:claim:(\d+)", query.data or "")
    if not match:
        await query.answer()
        return

    contest_id = int(match.group(1))
    user = query.from_user
    save_user(user)
    c = db()
    result = None
    try:
        # Bitta foydalanuvchi bir hadyadan faqat bir marta olishi mumkin.
        if c.in_transaction:
            c.commit()
        c.execute("BEGIN IMMEDIATE")
        contest = c.execute(
            "SELECT chat_id, remaining, active, message_id "
            "FROM hadya_contests WHERE id=?",
            (contest_id,),
        ).fetchone()

        if not contest:
            result = "❌ Hadya topilmadi."
        else:
            chat_id, remaining, active, message_id = contest
            already = c.execute(
                "SELECT 1 FROM hadya_claims WHERE contest_id=? AND user_id=?",
                (contest_id, user.id),
            ).fetchone()

            if already:
                result = "ℹ️ Siz bu hadyadan allaqachon sovg‘a olgansiz."
            elif not active or remaining <= 0:
                result = "😔 Hadya tugagan."
            else:
                gifts = list(SHOP_GIFTS.keys())
                if not gifts:
                    result = "❌ Sovg‘alar ro‘yxati bo‘sh."
                else:
                    gift_key = random.choice(gifts)
                    display_name = user.full_name or user.username or str(user.id)
                    now = datetime.now().isoformat(timespec="seconds")
                    c.execute(
                        "INSERT INTO hadya_claims "
                        "(contest_id, user_id, gift_key, display_name, claimed_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (contest_id, user.id, gift_key, display_name, now),
                    )
                    c.execute(
                        "UPDATE hadya_contests SET remaining=remaining-1, "
                        "active=CASE WHEN remaining-1<=0 THEN 0 ELSE 1 END "
                        "WHERE id=? AND remaining>0",
                        (contest_id,),
                    )
                    c.execute(
                        "INSERT INTO gift_log "
                        "(sender_id, recipient_id, gift_key, price, created_at) "
                        "VALUES (?, ?, ?, 0, ?)",
                        (0, user.id, gift_key, now),
                    )
                    c.commit()
                    gift_names = {
                        "ring": "💍 Uzuk",
                        "bear": "🧸 Ayiqcha",
                        "bouquet": "💐 Guldasta",
                        "rose": "🌹 Atirgul",
                        "diamond": "💎 Olmos",
                    }
                    result = f"🎉 Tabriklaymiz! Siz {gift_names.get(gift_key, gift_key)} yutdingiz! Sovg‘a profilda premium emoji bilan ko‘rinadi."
    except sqlite3.IntegrityError:
        c.rollback()
        result = "ℹ️ Siz bu hadyadan allaqachon sovg‘a olgansiz."
    except Exception:
        c.rollback()
        logger.exception("Hadya sovg‘asini berishda xato")
        result = "❌ Xatolik yuz berdi. Qayta urinib ko‘ring."
    finally:
        c.close()

    await query.answer(result or "🎁", show_alert=True)

    # Postdagi qolgan sovg'alar va g'oliblar ro'yxatini yangilash.
    try:
        text, keyboard = hadya_post_text(contest_id)
        c = db()
        try:
            row = c.execute(
                "SELECT chat_id, message_id FROM hadya_contests WHERE id=?",
                (contest_id,),
            ).fetchone()
        finally:
            c.close()
        if row and row[1]:
            await context.bot.edit_message_text(
                chat_id=row[0],
                message_id=row[1],
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            logger.warning("Hadya postini yangilashda xato: %s", exc)
    except TelegramError:
        logger.exception("Hadya postini yangilashda xato")


async def cmd_konkurs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not chat or chat.type not in (
        ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL
    ):
        return

    is_channel = chat.type == ChatType.CHANNEL
    # Kanal postlarida yuboruvchi (user) bo'lmaydi.
    if not is_channel and not user:
        return

    args = context.args
    if not args and msg.text:
        parts = msg.text.split()
        args = parts[1:]
    raw = args[0] if args else ""
    m = re.fullmatch(r"([1-9]\d{0,8})-([1-9]\d{0,3})", raw)
    if not m:
        await msg.reply_text("Format: /konkurs 100-5")
        return

    amount, winners = map(int, m.groups())
    total = amount * winners

    if winners > 1000 or total > 10**9:
        await msg.reply_text("Konkurs miqdori juda katta.")
        return

    if is_channel:
        # Kanalda kim yozganini bilib bo'lmaydi: faqat owner ro'yxatdan o'tkazgan
        # kanallarda (bot owner tomonidan admin qilingan) ishlaydi, pul hisobdan yechilmaydi.
        row = db().execute(
            "SELECT value FROM contest_config WHERE key='contest_channel_id'"
        ).fetchone()
        if not row or str(row[0]) != str(chat.id):
            await msg.reply_text(
                "Bu kanal ruxsat etilmagan. Botni kanalga owner administrator qilib qo'shishi kerak."
            )
            return
        owner_id = next(iter(CAREER_OWNER_IDS))
        owner = True
    else:
        owner_id = user.id
        owner = is_money_owner(user.id)

    c = db()
    cid = None
    insufficient = False

    try:
        with c:
            if not owner:
                cur = c.execute(
                    "UPDATE user_wallet SET money=money-? "
                    "WHERE user_id=? AND money>=?",
                    (total, owner_id, total),
                )
                if cur.rowcount != 1:
                    insufficient = True

            if not insufficient:
                cur = c.execute(
                    "INSERT INTO money_contests"
                    "(chat_id,owner_id,amount,winners,remaining,active,created_at) "
                    "VALUES(?,?,?,?,?,1,?)",
                    (
                        msg.chat.id, owner_id, amount, winners, winners,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                cid = cur.lastrowid

    except sqlite3.Error:
        await msg.reply_text("Xatolik yuz berdi. Qayta urinib ko‘ring.")
        return

    if insufficient:
        await msg.reply_text("Hisobingizda yetarli pul mavjud emas.")
        return

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💰 Pulni olish", callback_data=f"contest:{cid}")
    ]])

    try:
        contest_message = await context.bot.send_message(
            chat_id=chat.id,
            text=f"🎉 <b>KONKURS</b>\n"
            f"Har bir g‘olibga: <b>{amount}$</b>\n"
            f"G‘oliblar: <b>0/{winners}</b>\n"
            "\n🏆 G‘oliblar ro‘yxati: hozircha yo‘q\n"
            "\n👇 Mukofotni olish uchun tugmani bosing!",
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
        with c:
            c.execute("UPDATE money_contests SET chat_id=?, message_id=? WHERE id=?", (contest_message.chat.id, contest_message.message_id, cid))
        await log_money_event(
            context.bot,
            "🎉 <b>KONKURS OCHILDI</b>\n"
            f"Tashkilotchi: {person_name(owner_id)} (ID: <code>{owner_id}</code>)\n"
            f"Chat: <code>{msg.chat.id}</code>\n"
            f"Har bir g‘olibga: <b>{amount}$</b>\nG‘oliblar soni: <b>{winners}</b>\n"
            f"Jami mukofot: <b>{total}$</b>\nOwner orqali: {'ha' if owner else 'yo‘q'}"
        )
    except TelegramError as exc:
        logger.error("Konkurs xabarini yuborib bo'lmadi: %s", exc)
        # Xabar yuborilmasa, konkursni bekor qilib, to‘lovni qaytaramiz.
        try:
            with c:
                c.execute(
                    "UPDATE money_contests SET active=0, remaining=0 WHERE id=?",
                    (cid,),
                )
                if not owner:
                    c.execute(
                        "UPDATE user_wallet SET money=money+? WHERE user_id=?",
                        (total, owner_id),
                    )
        except sqlite3.Error:
            await msg.reply_text(
                "Konkurs xabari yuborilmadi va pulni qaytarishda xatolik yuz berdi. "
                "Balansni tekshirish kerak."
            )

async def cb_contest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    save_user(user)
    try:
        contest_id = int(q.data.split(":")[1])
    except (ValueError, IndexError):
        await q.answer("Konkurs ma’lumoti noto‘g‘ri.", show_alert=True)
        return

    c = db()
    amount = None
    remaining = None

    try:
        # Bitta tranzaksiyada joyni band qilish va mukofotni berish.
        with c:
            row = c.execute(
                "SELECT amount, remaining, active FROM money_contests WHERE id=?",
                (contest_id,),
            ).fetchone()

            if not row or not row[2] or row[1] <= 0:
                status = "ended"
            else:
                cur = c.execute(
                    "INSERT OR IGNORE INTO money_contest_claims(contest_id,user_id) "
                    "VALUES(?,?)",
                    (contest_id, user.id),
                )
                if cur.rowcount == 0:
                    status = "claimed"
                else:
                    amount = int(row[0])
                    cur = c.execute(
                        "UPDATE money_contests SET remaining=remaining-1 "
                        "WHERE id=? AND active=1 AND remaining>0",
                        (contest_id,),
                    )
                    if cur.rowcount != 1:
                        # Undo this user's claim if no place remained.
                        c.execute(
                            "DELETE FROM money_contest_claims "
                            "WHERE contest_id=? AND user_id=?",
                            (contest_id, user.id),
                        )
                        status = "ended"
                        amount = None
                    else:
                        c.execute(
                            "INSERT OR IGNORE INTO user_wallet(user_id,money) "
                            "VALUES(?,0)",
                            (user.id,),
                        )
                        c.execute(
                            "UPDATE user_wallet SET money=money+? WHERE user_id=?",
                            (amount, user.id),
                        )
                        c.execute(
                            "UPDATE money_contests SET active=0 "
                            "WHERE id=? AND remaining<=0",
                            (contest_id,),
                        )
                        remaining = c.execute(
                            "SELECT remaining FROM money_contests WHERE id=?",
                            (contest_id,),
                        ).fetchone()[0]
                        status = "ok"
    except sqlite3.Error:
        await q.answer(
            "Xatolik yuz berdi. Qayta urinib ko‘ring.",
            show_alert=True,
        )
        return

    if status == "ended":
        await q.answer("Konkurs tugagan.", show_alert=True)
        return
    if status == "claimed":
        await q.answer(
            "Siz pulni oldingiz yoki allaqachon olgansiz.",
            show_alert=True,
        )
        return

    await q.answer(f"✅ {amount}$ hisobingizga qo‘shildi!", show_alert=True)
    contest_owner = db().execute(
        "SELECT owner_id,chat_id,message_id,amount,winners FROM money_contests WHERE id=?", (contest_id,)
    ).fetchone()
    # Update the original contest post after every successful claim, showing the actual winners.
    if contest_owner:
        winner_rows = db().execute(
            "SELECT user_id FROM money_contest_claims WHERE contest_id=? ORDER BY rowid",
            (contest_id,),
        ).fetchall()
        winner_lines = [
            f'{i}. {person_name(int(row[0]))} — {contest_owner[3]}$'
            for i, row in enumerate(winner_rows, 1)
        ]
        progress_text = (
            "🎉 <b>KONKURS</b>\n"
            f"Har bir g‘olibga: <b>{contest_owner[3]}$</b>\n"
            f"G‘oliblar: <b>{len(winner_rows)}/{contest_owner[4]}</b>\n\n"
            "🏆 <b>G‘oliblar ro‘yxati:</b>\n" + ("\n".join(winner_lines) if winner_lines else "Hozircha yo‘q")
        )
        progress_kb = None if remaining == 0 else InlineKeyboardMarkup([[
            InlineKeyboardButton("💰 Pulni olish", callback_data=f"contest:{contest_id}")
        ]])
        if contest_owner[2]:
            try:
                await context.bot.edit_message_text(
                    chat_id=contest_owner[1], message_id=contest_owner[2],
                    text=progress_text, parse_mode=ParseMode.HTML,
                    reply_markup=progress_kb, disable_web_page_preview=True,
                )
            except TelegramError as exc:
                logger.warning("Konkurs xabarini yangilab bo‘lmadi: %s", exc)
    await log_money_event(
        context.bot,
        "🏆 <b>KONKURS MUKOFOTI O‘TKAZILDI</b>\n"
        f"Konkurs ID: <code>{contest_id}</code>\n"
        f"Tashkilotchi: {person_name(contest_owner[0]) if contest_owner else 'Noma’lum'} "
        f"(ID: <code>{contest_owner[0] if contest_owner else 0}</code>)\n"
        f"G‘olib: {person_name(user.id)} (ID: <code>{user.id}</code>)\n"
        f"Mukofot: <b>{amount}$</b>\nQolgan o‘rinlar: <b>{remaining}</b>"
    )
    if remaining == 0:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            pass




async def cmd_tasdiq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message

    if not user or not msg:
        return

    if user.id not in CAREER_OWNER_IDS:
        await msg.reply_text("⛔ Bu buyruq faqat bot egalari uchun.")
        return

    c = db()
    now = datetime.now().isoformat(timespec="seconds")
    approved = 0
    skipped = 0
    details = []

    # Kasb almashtirish arizalari
    career_rows = c.execute(
        """SELECT id, user_id, requested_profession_id
           FROM career_requests
           WHERE status='pending'
           ORDER BY id"""
    ).fetchall()

    for rid, target_user, profession_id in career_rows:
        with c:
            current = c.execute(
                "SELECT status FROM career_requests WHERE id=?", (rid,)
            ).fetchone()
            if not current or current[0] != "pending":
                continue

            c.execute(
                """UPDATE users
                   SET profession_id=?, profession_selected=1
                   WHERE user_id=?""",
                (profession_id, target_user),
            )
            changed = c.execute(
                """UPDATE career_requests
                   SET status='approved', decided_by=?, decided_at=?
                   WHERE id=? AND status='pending'""",
                (user.id, now, rid),
            )

        if changed.rowcount == 1:
            approved += 1
            try:
                await context.bot.send_message(
                    chat_id=target_user,
                    text="✅ Kasb almashtirish arizangiz bot egasi tomonidan tasdiqlandi.",
                )
            except TelegramError:
                pass
        else:
            skipped += 1

    # Juftlashish, ajrashish va ishdan bo‘shash arizalari
    rows = c.execute(
        """SELECT id, request_type, requester_id, target_id, group_id
           FROM pair_requests
           WHERE status='pending'
           ORDER BY id"""
    ).fetchall()

    for rid, kind, requester, target, group_id in rows:
        current = c.execute(
            "SELECT status FROM pair_requests WHERE id=?", (rid,)
        ).fetchone()
        if not current or current[0] != "pending":
            continue

        try:
            with c:
                if kind == "pair":
                    if not target or active_pair(requester) or active_pair(target):
                        skipped += 1
                        details.append(f"#{rid}: juftlik holati mos emas")
                        continue

                    c.execute(
                        """INSERT INTO pairs
                           (user1_id, user2_id, group_id, started_at, status)
                           VALUES (?, ?, ?, ?, 'active')""",
                        (requester, target, group_id or 0, now),
                    )

                elif kind == "divorce":
                    pair = active_pair(requester)
                    if (
                        not pair or not target
                        or {pair[1], pair[2]} != {requester, target}
                    ):
                        skipped += 1
                        details.append(f"#{rid}: faol juftlik topilmadi")
                        continue

                    c.execute(
                        """UPDATE pairs SET status='ended', ended_at=?
                           WHERE id=? AND status='active'""",
                        (now, pair[0]),
                    )
                    custody = c.execute(
                        "SELECT custody_id FROM pair_requests WHERE id=?", (rid,)
                    ).fetchone()[0]
                    settlement = divorce_settle(c, pair, custody)

                    # Shu juftlikning boshqa ochiq ajrashish arizalari
                    # ham kutilyotgan holatda qolmasin.
                    c.execute(
                        """UPDATE pair_requests SET status='cancelled'
                           WHERE request_type='divorce'
                             AND id<>?
                             AND status IN ('pending','partner_consent')
                             AND (
                               (requester_id=? AND target_id=?)
                               OR (requester_id=? AND target_id=?)
                             )""",
                        (rid, requester, target, target, requester),
                    )

                elif kind == "quit_job":
                    c.execute(
                        """UPDATE users
                           SET profession_id=NULL, profession_selected=0
                           WHERE user_id=?""",
                        (requester,),
                    )
                else:
                    skipped += 1
                    details.append(f"#{rid}: noma’lum ariza turi")
                    continue

                changed = c.execute(
                    """UPDATE pair_requests
                       SET status='approved', decided_by=?, decided_at=?
                       WHERE id=? AND status='pending'""",
                    (user.id, now, rid),
                )

            if changed.rowcount != 1:
                skipped += 1
                continue

            approved += 1
            try:
                await context.bot.send_message(
                    chat_id=requester,
                    text=f"✅ Arizangiz tasdiqlandi. Ariza raqami: {rid}",
                )
            except TelegramError:
                pass

            if kind == "divorce":
                await divorce_notify(context.bot, settlement)

            if target and kind in ("pair", "divorce"):
                try:
                    notice = (
                        "💞 Juftlik arizasi tasdiqlandi."
                        if kind == "pair"
                        else "💔 Ajrashish arizasi tasdiqlandi."
                    )
                    await context.bot.send_message(target, notice)
                except TelegramError:
                    pass

        except Exception:
            logger.exception("/tasdiq: #%s arizasini ko‘rib chiqishda xato", rid)
            skipped += 1
            details.append(f"#{rid}: xatolik, ariza tekshirish uchun qoldirildi")

    result = (
        "📋 <b>KUTILAYOTGAN ARIZALAR</b>\n\n"
        f"✅ Tasdiqlangan: <b>{approved} ta</b>\n"
        f"⚠️ O‘tkazib yuborilgan: <b>{skipped} ta</b>"
    )
    if details:
        result += "\n\n" + "\n".join(details[:15])

    await msg.reply_text(result)


# ───────────────────────────── 🏦 BANKLAR (ko'p bankli) ─────────────────────────────
# /profil → 🏦 Banklar. Banklar `banks` jadvalida (1-bank — Gold Invest); owner panel → 🏦 Banklar boshqaruvi:
# bank qo'shish, foizlar, ariza rejimi (kredit bank egasi tasdig'i bilan), egasi, yopish/ochish.
# Quyidagi qiymatlar — yangi bank uchun standart foizlar.
#   Kredit: kuniga 13%, 1–7 kun. Birinchi kredit — 1 000$, keyingilari 1 000$ … 50 000$.
#           Muddat tugaganda summa hamyondan avtomatik yechiladi (balans minusga tushishi mumkin).
#   Omonat: 5 000$ … 30 000$, 3–10 kun, kuniga 5%. Muddatidan oldin yechilmaydi,
#           muddat tugaganda pul foizi bilan hamyonga avtomatik tushadi.
# Callback: "bk:<uid>:<amal>:..." — menyuni faqat profil egasi boshqaradi.

LOAN_RATE = 0.13
LOAN_FIRST = 1000
LOAN_AMOUNTS = [1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 25000, 30000, 40000, 50000]
LOAN_DAYS = range(1, 8)
DEPOSIT_RATE = 0.05
DEPOSIT_AMOUNTS = [5000, 10000, 15000, 20000, 25000, 30000]
DEPOSIT_DAYS = range(3, 11)
BANK_TICK = 30              # muddati kelgan kredit/omonatlarni tekshirish oralig'i (soniya)
DAY_SECONDS = 86400
TASHKENT_OFFSET = 5 * 3600

BANK_TEXT = {
    "uz": {
        "banks": "🏦 <b>BANKLAR</b>\n\nBankni tanlang 👇\n\n🎮 Simulator — haqiqiy pul emas",
        "home": (
            "🏦 <b>{bank}</b>\n\n💵 Hamyon: <b>{wallet}$</b>\n\n"
            "💸 Kredit: {loan}\n🏦 Omonat: {deposit}\n\n"
            "📈 Kredit — kuniga {loan_rate}% · 1–7 kun\n📈 Omonat — kuniga {dep_rate}% · 3–10 kun"
        ),
        "none": "yo‘q",
        "loan_line": "<b>{due}$</b> qaytariladi · {when} gacha · 🏦 {bank}",
        "dep_line": "<b>{amount}$</b> → <b>{payout}$</b> · {when} da tushadi · 🏦 {bank}",
        "b_loan": "💸 Kredit olish", "b_repay": "✅ Kreditni to‘lash · {due}$", "b_deposit": "🏦 Omonat ochish",
        "b_back": "⬅️ Orqaga", "b_banks": "🏦 Banklar",
        "loan_first": (
            "💸 <b>KREDIT</b>\n\nBu sizning birinchi kreditingiz — <b>{amount}$</b>.\n"
            "Keyingi safar 1 000$ dan 50 000$ gacha olishingiz mumkin bo‘ladi.\n\n"
            "📈 Foiz: kuniga <b>{rate}%</b>\nMuddatni tanlang — tugmada qaytariladigan summa 👇\n\n{warn}"
        ),
        "loan_amount": "💸 <b>KREDIT</b>\n\n📈 Foiz: kuniga <b>{rate}%</b>\nSummani tanlang — yonida kunlik foizi 👇",
        "loan_term": "💸 <b>KREDIT · {amount}$</b>\n\n📈 Foiz: kuniga <b>{rate}%</b>\nMuddatni tanlang — tugmada qaytariladigan summa 👇\n\n{warn}",
        "warn": "⚠️ Muddat tugaganda summa hamyondan avtomatik yechiladi — balans minusga tushishi mumkin.",
        "per_day": "/kun", "days": "kun",
        "loan_ok": "✅ Kredit berildi: <b>+{amount}$</b>\n📅 {days} kun · qaytariladi: <b>{due}$</b>\n⏰ Muddat: {when}",
        "loan_has": "⛔ Sizda to‘lanmagan kredit bor.",
        "loan_debt": "⛔ Balansingiz minusda — avval qarzni yoping.",
        "repay_ok": "✅ Kredit to‘landi: <b>−{due}$</b>",
        "dep_amount": (
            "🏦 <b>OMONAT</b>\n\n📈 Foiz: kuniga <b>{rate}%</b>\n💵 {min}$ dan {max}$ gacha · 3–10 kun\n"
            "🔒 Muddatidan oldin yechib bo‘lmaydi\n💰 Hamyon: {wallet}$\n\nSummani tanlang 👇"
        ),
        "dep_term": "🏦 <b>OMONAT · {amount}$</b>\n\n📈 Kuniga {rate}%\nMuddatni tanlang — tugmada muddat oxirida tushadigan summa 👇",
        "dep_ok": "✅ Omonat ochildi: <b>−{amount}$</b>\n📅 {days} kun · {when} da hamyonga <b>{payout}$</b> tushadi",
        "dep_has": "⛔ Sizda faol omonat bor — u tugagach yangisini ochishingiz mumkin.",
        "dep_loan": "⛔ Kredit to‘lanmaguncha (yoki balans minusda bo‘lsa) omonat ochib bo‘lmaydi.",
        "no_funds": "💸 Hamyonda yetarli pul yo‘q (balans: {bal}$).",
        "not_yours": "⛔ Bu menyu sizniki emas — o‘zingiz /profil yozing.",
        "apply_note": "📝 Bu bankda kredit <b>ariza orqali</b> beriladi — bank egasi ko‘rib chiqib tasdiqlaydi.",
        "apply_private": "📝 Ariza shaxsiy chatda beriladi: /profil → 🏦 Banklar.",
        "purpose_ask": "📝 <b>{bank}</b> · {amount}$ · {days} kun → qaytariladi {due}$\n\nKredit olish <b>maqsadini</b> yozing (masalan: biznes, uy, birja…) 👇",
        "purpose_sent": "📨 Arizangiz bank egasiga yuborildi. Javobni kuting ⏳",
        "apply_pending": "⏳ Sizda ko‘rib chiqilayotgan kredit arizasi bor.",
        "apply_ok": "✅ <b>{bank}</b> kredit arizangizni tasdiqladi! <b>+{amount}$</b>\n📅 {days} kun · qaytariladi {due}$ · muddat {when}",
        "apply_no": "❌ <b>{bank}</b> kredit arizangizni rad etdi.",
        "apply_fail_owner": "😓 Bank egasiga xabar yetib bormadi — keyinroq urinib ko‘ring.",
        "bank_closed": "⛔ Bu bank hozir ishlamayapti.",
        "n_loan": "🏦 <b>{bank}</b>: kredit muddati tugadi — hamyondan <b>{due}$</b> yechildi.\n💰 Balans: {bal}$",
        "n_dep": "🏦 <b>{bank}</b>: omonat muddati tugadi — hamyonga <b>{payout}$</b> tushdi (foyda +{profit}$).\n💰 Balans: {bal}$",
    },
    "eng": {
        "banks": "🏦 <b>BANKS</b>\n\nChoose a bank 👇\n\n🎮 Simulator — not real money",
        "home": (
            "🏦 <b>{bank}</b>\n\n💵 Wallet: <b>{wallet}$</b>\n\n"
            "💸 Loan: {loan}\n🏦 Deposit: {deposit}\n\n"
            "📈 Loan — {loan_rate}% per day · 1–7 days\n📈 Deposit — {dep_rate}% per day · 3–10 days"
        ),
        "none": "none",
        "loan_line": "<b>{due}$</b> to repay · until {when} · 🏦 {bank}",
        "dep_line": "<b>{amount}$</b> → <b>{payout}$</b> · paid on {when} · 🏦 {bank}",
        "b_loan": "💸 Take a loan", "b_repay": "✅ Repay loan · {due}$", "b_deposit": "🏦 Open a deposit",
        "b_back": "⬅️ Back", "b_banks": "🏦 Banks",
        "loan_first": (
            "💸 <b>LOAN</b>\n\nThis is your first loan — <b>{amount}$</b>.\n"
            "Next time you can borrow from 1 000$ to 50 000$.\n\n"
            "📈 Interest: <b>{rate}%</b> per day\nChoose the term — the button shows the amount to repay 👇\n\n{warn}"
        ),
        "loan_amount": "💸 <b>LOAN</b>\n\n📈 Interest: <b>{rate}%</b> per day\nChoose the amount — daily interest shown next to it 👇",
        "loan_term": "💸 <b>LOAN · {amount}$</b>\n\n📈 Interest: <b>{rate}%</b> per day\nChoose the term — the button shows the amount to repay 👇\n\n{warn}",
        "warn": "⚠️ When the term ends, the amount is taken from your wallet automatically — the balance may go negative.",
        "per_day": "/day", "days": "d",
        "loan_ok": "✅ Loan granted: <b>+{amount}$</b>\n📅 {days} days · repay: <b>{due}$</b>\n⏰ Due: {when}",
        "loan_has": "⛔ You have an unpaid loan.",
        "loan_debt": "⛔ Your balance is negative — clear the debt first.",
        "repay_ok": "✅ Loan repaid: <b>−{due}$</b>",
        "dep_amount": (
            "🏦 <b>DEPOSIT</b>\n\n📈 Interest: <b>{rate}%</b> per day\n💵 {min}$ to {max}$ · 3–10 days\n"
            "🔒 Cannot be withdrawn early\n💰 Wallet: {wallet}$\n\nChoose the amount 👇"
        ),
        "dep_term": "🏦 <b>DEPOSIT · {amount}$</b>\n\n📈 {rate}% per day\nChoose the term — the button shows the payout 👇",
        "dep_ok": "✅ Deposit opened: <b>−{amount}$</b>\n📅 {days} days · <b>{payout}$</b> will be paid on {when}",
        "dep_has": "⛔ You already have an active deposit — open a new one after it ends.",
        "dep_loan": "⛔ You can't open a deposit while you have a loan or a negative balance.",
        "no_funds": "💸 Not enough money in your wallet (balance: {bal}$).",
        "not_yours": "⛔ This menu is not yours — type /profile yourself.",
        "apply_note": "📝 Loans here are by <b>application</b> — the bank owner reviews and approves.",
        "apply_private": "📝 Applications are made in private chat: /profile → 🏦 Banks.",
        "purpose_ask": "📝 <b>{bank}</b> · {amount}$ · {days} days → repay {due}$\n\nWrite the <b>purpose</b> of the loan 👇",
        "purpose_sent": "📨 Your application was sent to the bank owner. Please wait ⏳",
        "apply_pending": "⏳ You already have a loan application under review.",
        "apply_ok": "✅ <b>{bank}</b> approved your loan! <b>+{amount}$</b>\n📅 {days} days · repay {due}$ · due {when}",
        "apply_no": "❌ <b>{bank}</b> rejected your loan application.",
        "apply_fail_owner": "😓 Couldn't reach the bank owner — try again later.",
        "bank_closed": "⛔ This bank is closed now.",
        "n_loan": "🏦 <b>{bank}</b>: your loan is due — <b>{due}$</b> was taken from your wallet.\n💰 Balance: {bal}$",
        "n_dep": "🏦 <b>{bank}</b>: your deposit matured — <b>{payout}$</b> was paid to your wallet (profit +{profit}$).\n💰 Balance: {bal}$",
    },
    "ru": {
        "banks": "🏦 <b>БАНКИ</b>\n\nВыберите банк 👇\n\n🎮 Симулятор — не настоящие деньги",
        "home": (
            "🏦 <b>{bank}</b>\n\n💵 Кошелёк: <b>{wallet}$</b>\n\n"
            "💸 Кредит: {loan}\n🏦 Вклад: {deposit}\n\n"
            "📈 Кредит — {loan_rate}% в день · 1–7 дней\n📈 Вклад — {dep_rate}% в день · 3–10 дней"
        ),
        "none": "нет",
        "loan_line": "<b>{due}$</b> к возврату · до {when} · 🏦 {bank}",
        "dep_line": "<b>{amount}$</b> → <b>{payout}$</b> · выплата {when} · 🏦 {bank}",
        "b_loan": "💸 Взять кредит", "b_repay": "✅ Погасить кредит · {due}$", "b_deposit": "🏦 Открыть вклад",
        "b_back": "⬅️ Назад", "b_banks": "🏦 Банки",
        "loan_first": (
            "💸 <b>КРЕДИТ</b>\n\nЭто ваш первый кредит — <b>{amount}$</b>.\n"
            "В следующий раз можно взять от 1 000$ до 50 000$.\n\n"
            "📈 Ставка: <b>{rate}%</b> в день\nВыберите срок — на кнопке сумма к возврату 👇\n\n{warn}"
        ),
        "loan_amount": "💸 <b>КРЕДИТ</b>\n\n📈 Ставка: <b>{rate}%</b> в день\nВыберите сумму — рядом проценты за день 👇",
        "loan_term": "💸 <b>КРЕДИТ · {amount}$</b>\n\n📈 Ставка: <b>{rate}%</b> в день\nВыберите срок — на кнопке сумма к возврату 👇\n\n{warn}",
        "warn": "⚠️ По окончании срока сумма списывается с кошелька автоматически — баланс может уйти в минус.",
        "per_day": "/день", "days": "дн.",
        "loan_ok": "✅ Кредит выдан: <b>+{amount}$</b>\n📅 {days} дн. · к возврату: <b>{due}$</b>\n⏰ Срок: {when}",
        "loan_has": "⛔ У вас есть непогашенный кредит.",
        "loan_debt": "⛔ Ваш баланс в минусе — сначала погасите долг.",
        "repay_ok": "✅ Кредит погашен: <b>−{due}$</b>",
        "dep_amount": (
            "🏦 <b>ВКЛАД</b>\n\n📈 Ставка: <b>{rate}%</b> в день\n💵 От {min}$ до {max}$ · 3–10 дней\n"
            "🔒 Досрочно снять нельзя\n💰 Кошелёк: {wallet}$\n\nВыберите сумму 👇"
        ),
        "dep_term": "🏦 <b>ВКЛАД · {amount}$</b>\n\n📈 {rate}% в день\nВыберите срок — на кнопке сумма к выплате 👇",
        "dep_ok": "✅ Вклад открыт: <b>−{amount}$</b>\n📅 {days} дн. · {when} на кошелёк поступит <b>{payout}$</b>",
        "dep_has": "⛔ У вас уже есть активный вклад — новый можно открыть после его окончания.",
        "dep_loan": "⛔ Нельзя открыть вклад, пока есть кредит или баланс в минусе.",
        "no_funds": "💸 Недостаточно денег в кошельке (баланс: {bal}$).",
        "not_yours": "⛔ Это не ваше меню — напишите /profil сами.",
        "apply_note": "📝 Кредит в этом банке выдаётся <b>по заявке</b> — владелец банка рассматривает и одобряет.",
        "apply_private": "📝 Заявка подаётся в личке: /profil → 🏦 Банки.",
        "purpose_ask": "📝 <b>{bank}</b> · {amount}$ · {days} дн. → к возврату {due}$\n\nНапишите <b>цель</b> кредита 👇",
        "purpose_sent": "📨 Заявка отправлена владельцу банка. Ждите ответа ⏳",
        "apply_pending": "⏳ У вас уже есть заявка на рассмотрении.",
        "apply_ok": "✅ <b>{bank}</b> одобрил ваш кредит! <b>+{amount}$</b>\n📅 {days} дн. · к возврату {due}$ · срок {when}",
        "apply_no": "❌ <b>{bank}</b> отклонил вашу заявку.",
        "apply_fail_owner": "😓 Не удалось связаться с владельцем банка — попробуйте позже.",
        "bank_closed": "⛔ Этот банк сейчас закрыт.",
        "n_loan": "🏦 <b>{bank}</b>: срок кредита истёк — с кошелька списано <b>{due}$</b>.\n💰 Баланс: {bal}$",
        "n_dep": "🏦 <b>{bank}</b>: срок вклада истёк — на кошелёк поступило <b>{payout}$</b> (прибыль +{profit}$).\n💰 Баланс: {bal}$",
    },
    "kz": {
        "banks": "🏦 <b>БАНКТЕР</b>\n\nБанкті таңдаңыз 👇\n\n🎮 Симулятор — нақты ақша емес",
        "home": (
            "🏦 <b>{bank}</b>\n\n💵 Әмиян: <b>{wallet}$</b>\n\n"
            "💸 Несие: {loan}\n🏦 Салым: {deposit}\n\n"
            "📈 Несие — күніне {loan_rate}% · 1–7 күн\n📈 Салым — күніне {dep_rate}% · 3–10 күн"
        ),
        "none": "жоқ",
        "loan_line": "<b>{due}$</b> қайтарылады · {when} дейін · 🏦 {bank}",
        "dep_line": "<b>{amount}$</b> → <b>{payout}$</b> · {when} түседі · 🏦 {bank}",
        "b_loan": "💸 Несие алу", "b_repay": "✅ Несиені өтеу · {due}$", "b_deposit": "🏦 Салым ашу",
        "b_back": "⬅️ Артқа", "b_banks": "🏦 Банктер",
        "loan_first": (
            "💸 <b>НЕСИЕ</b>\n\nБұл сіздің алғашқы несиеңіз — <b>{amount}$</b>.\n"
            "Келесі жолы 1 000$-дан 50 000$-ға дейін алуға болады.\n\n"
            "📈 Пайыз: күніне <b>{rate}%</b>\nМерзімді таңдаңыз — батырмада қайтарылатын сома 👇\n\n{warn}"
        ),
        "loan_amount": "💸 <b>НЕСИЕ</b>\n\n📈 Пайыз: күніне <b>{rate}%</b>\nСоманы таңдаңыз — қасында күндік пайызы 👇",
        "loan_term": "💸 <b>НЕСИЕ · {amount}$</b>\n\n📈 Пайыз: күніне <b>{rate}%</b>\nМерзімді таңдаңыз — батырмада қайтарылатын сома 👇\n\n{warn}",
        "warn": "⚠️ Мерзім біткенде сома әмияннан автоматты түрде алынады — баланс минусқа түсуі мүмкін.",
        "per_day": "/күн", "days": "күн",
        "loan_ok": "✅ Несие берілді: <b>+{amount}$</b>\n📅 {days} күн · қайтарылады: <b>{due}$</b>\n⏰ Мерзімі: {when}",
        "loan_has": "⛔ Сізде өтелмеген несие бар.",
        "loan_debt": "⛔ Балансыңыз минуста — алдымен қарызды жабыңыз.",
        "repay_ok": "✅ Несие өтелді: <b>−{due}$</b>",
        "dep_amount": (
            "🏦 <b>САЛЫМ</b>\n\n📈 Пайыз: күніне <b>{rate}%</b>\n💵 {min}$-дан {max}$-ға дейін · 3–10 күн\n"
            "🔒 Мерзімінен бұрын алуға болмайды\n💰 Әмиян: {wallet}$\n\nСоманы таңдаңыз 👇"
        ),
        "dep_term": "🏦 <b>САЛЫМ · {amount}$</b>\n\n📈 Күніне {rate}%\nМерзімді таңдаңыз — батырмада түсетін сома 👇",
        "dep_ok": "✅ Салым ашылды: <b>−{amount}$</b>\n📅 {days} күн · {when} әмиянға <b>{payout}$</b> түседі",
        "dep_has": "⛔ Сізде белсенді салым бар — ол біткен соң жаңасын ашуға болады.",
        "dep_loan": "⛔ Несие өтелмейінше (немесе баланс минуста болса) салым ашуға болмайды.",
        "no_funds": "💸 Әмиянда ақша жеткіліксіз (баланс: {bal}$).",
        "not_yours": "⛔ Бұл мәзір сіздікі емес — өзіңіз /profil жазыңыз.",
        "apply_note": "📝 Бұл банкте несие <b>өтініш арқылы</b> беріледі — банк иесі қарап, бекітеді.",
        "apply_private": "📝 Өтініш жеке чатта беріледі: /profil → 🏦 Банктер.",
        "purpose_ask": "📝 <b>{bank}</b> · {amount}$ · {days} күн → қайтарылады {due}$\n\nНесие алу <b>мақсатын</b> жазыңыз 👇",
        "purpose_sent": "📨 Өтінішіңіз банк иесіне жіберілді. Жауапты күтіңіз ⏳",
        "apply_pending": "⏳ Сізде қаралып жатқан несие өтініші бар.",
        "apply_ok": "✅ <b>{bank}</b> несиеңізді бекітті! <b>+{amount}$</b>\n📅 {days} күн · қайтарылады {due}$ · мерзімі {when}",
        "apply_no": "❌ <b>{bank}</b> өтінішіңізді қабылдамады.",
        "apply_fail_owner": "😓 Банк иесіне хабар жетпеді — кейінірек көріңіз.",
        "bank_closed": "⛔ Бұл банк қазір жабық.",
        "n_loan": "🏦 <b>{bank}</b>: несие мерзімі бітті — әмияннан <b>{due}$</b> алынды.\n💰 Баланс: {bal}$",
        "n_dep": "🏦 <b>{bank}</b>: салым мерзімі бітті — әмиянға <b>{payout}$</b> түсті (пайда +{profit}$).\n💰 Баланс: {bal}$",
    },
}


def bank_t(chat_id, key, **kwargs):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    text = BANK_TEXT.get(lang, BANK_TEXT["uz"]).get(key) or BANK_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def fmt_when(ts):
    """Unix vaqt → Toshkent vaqti (dd.mm HH:MM)."""
    return time.strftime("%d.%m %H:%M", time.gmtime(int(ts) + TASHKENT_OFFSET))


def loan_due(amount, days, rate=LOAN_RATE):
    return amount + round(amount * rate * days)


def deposit_payout(amount, days, rate=DEPOSIT_RATE):
    return amount + round(amount * rate * days)


def init_bank():
    c = db()
    with c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS bank_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                days INTEGER NOT NULL,
                due INTEGER NOT NULL,
                taken_at INTEGER NOT NULL,
                due_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                closed_at INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_bank_loans_user ON bank_loans(user_id, status)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS bank_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                days INTEGER NOT NULL,
                payout INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                matures_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                closed_at INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_bank_deposits_user ON bank_deposits(user_id, status)")
        # Ko'p bankli tizim: har bir bankning o'z foizlari, egasi va kredit berish tartibi bor.
        c.execute("""
            CREATE TABLE IF NOT EXISTS banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                loan_rate REAL NOT NULL,
                deposit_rate REAL NOT NULL,
                apply_mode INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS bank_loan_apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                days INTEGER NOT NULL,
                due INTEGER NOT NULL,
                purpose TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                decided_by INTEGER,
                decided_at INTEGER
            )
        """)
        for table in ("bank_loans", "bank_deposits"):
            if "bank_id" not in {r[1] for r in c.execute(f"PRAGMA table_info({table})")}:
                c.execute(f"ALTER TABLE {table} ADD COLUMN bank_id INTEGER NOT NULL DEFAULT 1")
        c.execute("UPDATE banks SET active=1 WHERE id=1")
        if not c.execute("SELECT 1 FROM banks LIMIT 1").fetchone():
            # Avvalgi yagona bank — Gold Invest — o'sha sozlamalar bilan 1-bank bo'ladi.
            c.execute(
                "INSERT INTO banks(id, name, owner_id, loan_rate, deposit_rate, apply_mode, active, created_at) "
                "VALUES (1, 'Gold Invest', ?, ?, ?, 0, 1, ?)",
                (min(CAREER_OWNER_IDS), LOAN_RATE, DEPOSIT_RATE, int(time.time())),
            )


BANK_FIELDS = ("id", "name", "owner_id", "loan_rate", "deposit_rate", "apply_mode", "active")
MAIN_BANK_ID = 1   # Gold Invest — asosiy bank: boshqariladi, lekin yopilmaydi


def bank_get(bank_id):
    row = db().execute(f"SELECT {', '.join(BANK_FIELDS)} FROM banks WHERE id=?", (bank_id,)).fetchone()
    return dict(zip(BANK_FIELDS, row)) if row else None


def banks_all(only_active=False):
    sql = f"SELECT {', '.join(BANK_FIELDS)} FROM banks" + (" WHERE active=1" if only_active else "") + " ORDER BY id"
    return [dict(zip(BANK_FIELDS, r)) for r in db().execute(sql)]


def pct(rate):
    return f"{rate * 100:g}"


def active_loan(user_id):
    return db().execute(
        "SELECT id, amount, days, due, due_at, bank_id FROM bank_loans WHERE user_id=? AND status='active'",
        (user_id,),
    ).fetchone()


def active_deposit(user_id):
    return db().execute(
        "SELECT id, amount, days, payout, matures_at, bank_id FROM bank_deposits WHERE user_id=? AND status='active'",
        (user_id,),
    ).fetchone()


def pending_app(user_id):
    return db().execute(
        "SELECT id, bank_id FROM bank_loan_apps WHERE user_id=? AND status='pending'", (user_id,)
    ).fetchone()


def had_loan_before(user_id):
    return db().execute(
        "SELECT 1 FROM bank_loans WHERE user_id=? AND status!='active' LIMIT 1", (user_id,)
    ).fetchone() is not None


def _wallet_add(c, user_id, delta):
    """Tranzaksiya ichida ishlatiladi (commit qilmaydi)."""
    c.execute("INSERT OR IGNORE INTO user_wallet(user_id, money) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE user_wallet SET money = money + ? WHERE user_id = ?", (int(delta), user_id))


def _wallet_take(c, user_id, amount):
    """Puli yetsa yechadi (tranzaksiya ichida). True — yechildi."""
    cur = c.execute(
        "UPDATE user_wallet SET money = money - ? WHERE user_id = ? AND money >= ?",
        (int(amount), user_id, int(amount)),
    )
    return cur.rowcount == 1


def bank_btn(uid, label, *parts):
    return InlineKeyboardButton(label, callback_data=":".join(["bk", str(uid), *map(str, parts)]))


def bank_name(bank_id):
    bank = bank_get(bank_id)
    return escape(bank["name"]) if bank else "?"


def bank_banks_view(chat_id, uid):
    rows = [
        [bank_btn(uid, f"🏦 {b['name']} · 💸 {pct(b['loan_rate'])}% · 🏦 {pct(b['deposit_rate'])}%"
                       + (" · 📝" if b["apply_mode"] else ""), "b", b["id"])]
        for b in banks_all(only_active=True)
    ]
    return bank_t(chat_id, "banks"), InlineKeyboardMarkup(rows or [[bank_btn(uid, "🔄", "banks")]])


def bank_home_view(chat_id, uid, bank):
    loan = active_loan(uid)
    dep = active_deposit(uid)
    loan_text = (
        bank_t(chat_id, "loan_line", due=fmt_money(loan[3]), when=fmt_when(loan[4]), bank=bank_name(loan[5]))
        if loan else bank_t(chat_id, "none")
    )
    dep_text = (
        bank_t(chat_id, "dep_line", amount=fmt_money(dep[1]), payout=fmt_money(dep[3]), when=fmt_when(dep[4]),
               bank=bank_name(dep[5]))
        if dep else bank_t(chat_id, "none")
    )
    text = bank_t(
        chat_id, "home", bank=escape(bank["name"]), wallet=fmt_money(wallet_balance(uid)), loan=loan_text,
        deposit=dep_text, loan_rate=pct(bank["loan_rate"]), dep_rate=pct(bank["deposit_rate"]),
    )
    if bank["apply_mode"]:
        text += "\n" + bank_t(chat_id, "apply_note")
    rows = []
    if loan:
        rows.append([bank_btn(uid, bank_t(chat_id, "b_repay", due=fmt_money(loan[3])), "repay", bank["id"])])
    else:
        rows.append([bank_btn(uid, bank_t(chat_id, "b_loan"), "loan", bank["id"])])
    if not dep:
        rows.append([bank_btn(uid, bank_t(chat_id, "b_deposit"), "dep", bank["id"])])
    rows.append([bank_btn(uid, bank_t(chat_id, "b_banks"), "banks")])
    return text, InlineKeyboardMarkup(rows)


def bank_back_row(chat_id, uid, bank):
    return [bank_btn(uid, bank_t(chat_id, "b_back"), "b", bank["id"])]


def bank_loan_term_view(chat_id, uid, bank, amount, first):
    rate = bank["loan_rate"]
    buttons = [
        bank_btn(uid, f"{d} {bank_t(chat_id, 'days')} → {fmt_money(loan_due(amount, d, rate))}$", "lt", bank["id"], amount, d)
        for d in LOAN_DAYS
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append(bank_back_row(chat_id, uid, bank))
    warn = bank_t(chat_id, "warn")
    key = "loan_first" if first else "loan_term"
    text = bank_t(chat_id, key, amount=fmt_money(amount), rate=pct(rate), warn=warn)
    if bank["apply_mode"]:
        text += "\n\n" + bank_t(chat_id, "apply_note")
    return text, InlineKeyboardMarkup(rows)


def bank_loan_amount_view(chat_id, uid, bank):
    per_day = bank_t(chat_id, "per_day")
    rate = bank["loan_rate"]
    buttons = [
        bank_btn(uid, f"{fmt_money(a)}$ · +{fmt_money(round(a * rate))}${per_day}", "la", bank["id"], a)
        for a in LOAN_AMOUNTS
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append(bank_back_row(chat_id, uid, bank))
    return bank_t(chat_id, "loan_amount", rate=pct(rate)), InlineKeyboardMarkup(rows)


def bank_dep_amount_view(chat_id, uid, bank):
    buttons = [bank_btn(uid, f"{fmt_money(a)}$", "da", bank["id"], a) for a in DEPOSIT_AMOUNTS]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append(bank_back_row(chat_id, uid, bank))
    text = bank_t(
        chat_id, "dep_amount", rate=pct(bank["deposit_rate"]),
        min=fmt_money(DEPOSIT_AMOUNTS[0]), max=fmt_money(DEPOSIT_AMOUNTS[-1]),
        wallet=fmt_money(wallet_balance(uid)),
    )
    return text, InlineKeyboardMarkup(rows)


def bank_dep_term_view(chat_id, uid, bank, amount):
    days_label = bank_t(chat_id, "days")
    rate = bank["deposit_rate"]
    buttons = [
        bank_btn(uid, f"{d} {days_label} → {fmt_money(deposit_payout(amount, d, rate))}$", "dt", bank["id"], amount, d)
        for d in DEPOSIT_DAYS
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append(bank_back_row(chat_id, uid, bank))
    return bank_t(chat_id, "dep_term", amount=fmt_money(amount), rate=pct(rate)), InlineKeyboardMarkup(rows)


def issue_loan(c, uid, bank_id, amount, days, due, now):
    """Kreditni beradi (tranzaksiya ichida). Qaytaradi: due_at."""
    due_at = now + days * DAY_SECONDS
    c.execute(
        "INSERT INTO bank_loans(user_id, amount, days, due, taken_at, due_at, bank_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, amount, days, due, now, due_at, bank_id),
    )
    _wallet_add(c, uid, amount)
    return due_at


async def cb_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    chat_id = q.message.chat.id
    uid = int(parts[1])
    action = parts[2]
    user = q.from_user

    if user.id != uid:
        await q.answer(bank_t(chat_id, "not_yours"), show_alert=True)
        return

    async def show(view, notice=None):
        text, kb = view
        if notice:
            text = notice + "\n\n" + text
        if action == "open":
            await context.bot.send_message(chat_id, text, reply_markup=kb)
        else:
            await edit(context.bot, chat_id, q.message.message_id, text, kb)

    if action in ("open", "banks"):
        await q.answer()
        await show(bank_banks_view(chat_id, uid))
        return

    # "gold" — eski xabarlardagi tugma (1-bank).
    try:
        bank = bank_get(1 if action == "gold" else int(parts[3]))
    except (IndexError, ValueError):
        bank = None
    if not bank or not bank["active"]:
        await q.answer(bank_t(chat_id, "bank_closed"), show_alert=True)
        await show(bank_banks_view(chat_id, uid))
        return
    nums = [int(p) for p in parts[4:] if p.lstrip("-").isdigit()]

    if action in ("b", "gold"):
        await q.answer()
        await show(bank_home_view(chat_id, uid, bank))
        return

    c = db()
    now = int(time.time())

    async def loan_blocked():
        if active_loan(uid):
            await q.answer(bank_t(chat_id, "loan_has"), show_alert=True)
            return True
        if pending_app(uid):
            await q.answer(bank_t(chat_id, "apply_pending"), show_alert=True)
            return True
        if wallet_balance(uid) < 0:
            await q.answer(bank_t(chat_id, "loan_debt"), show_alert=True)
            return True
        return False

    if action == "loan":
        if await loan_blocked():
            return
        await q.answer()
        if had_loan_before(uid):
            await show(bank_loan_amount_view(chat_id, uid, bank))
        else:
            await show(bank_loan_term_view(chat_id, uid, bank, LOAN_FIRST, first=True))
        return

    if action == "la":
        amount = nums[0] if nums else 0
        if amount not in LOAN_AMOUNTS or not had_loan_before(uid):
            await q.answer()
            return
        await q.answer()
        await show(bank_loan_term_view(chat_id, uid, bank, amount, first=False))
        return

    if action == "lt":
        amount, days = (nums + [0, 0])[:2]
        allowed = LOAN_AMOUNTS if had_loan_before(uid) else [LOAN_FIRST]
        if amount not in allowed or days not in LOAN_DAYS:
            await q.answer()
            return
        if await loan_blocked():
            return
        due = loan_due(amount, days, bank["loan_rate"])
        save_user(user)
        if bank["apply_mode"]:
            # Ariza rejimi: faqat maqsad so'raladi, keyin bank egasi ko'rib chiqadi.
            if q.message.chat.type != ChatType.PRIVATE:
                await q.answer(bank_t(chat_id, "apply_private"), show_alert=True)
                return
            context.user_data["bank_purpose"] = {"bank": bank["id"], "amount": amount, "days": days, "due": due}
            await q.answer()
            await show((bank_t(chat_id, "purpose_ask", bank=escape(bank["name"]), amount=fmt_money(amount),
                               days=days, due=fmt_money(due)),
                        InlineKeyboardMarkup([bank_back_row(chat_id, uid, bank)])))
            return
        with c:
            due_at = issue_loan(c, uid, bank["id"], amount, days, due, now)
        await q.answer()
        await show(bank_home_view(chat_id, uid, bank), bank_t(
            chat_id, "loan_ok", amount=fmt_money(amount), days=days, due=fmt_money(due), when=fmt_when(due_at),
        ))
        await log_money_event(
            context.bot,
            f"🏦 <b>KREDIT</b> · {escape(bank['name'])}\n{person_name(uid)}: +{amount}$ · {days} kun · qaytariladi {due}$",
        )
        return

    if action == "repay":
        loan = active_loan(uid)
        if not loan:
            await q.answer()
            await show(bank_home_view(chat_id, uid, bank))
            return
        loan_id, _, _, due, _, loan_bank = loan
        with c:
            paid = _wallet_take(c, uid, due)
            if paid:
                c.execute(
                    "UPDATE bank_loans SET status='paid', closed_at=? WHERE id=? AND status='active'",
                    (now, loan_id),
                )
        if not paid:
            await q.answer(bank_t(chat_id, "no_funds", bal=fmt_money(wallet_balance(uid))), show_alert=True)
            return
        await q.answer()
        await show(bank_home_view(chat_id, uid, bank), bank_t(chat_id, "repay_ok", due=fmt_money(due)))
        await log_money_event(context.bot, f"🏦 <b>KREDIT TO‘LANDI</b> · {bank_name(loan_bank)}\n{person_name(uid)}: −{due}$")
        return

    if action == "dep":
        if active_deposit(uid):
            await q.answer(bank_t(chat_id, "dep_has"), show_alert=True)
            return
        if active_loan(uid) or wallet_balance(uid) < 0:
            await q.answer(bank_t(chat_id, "dep_loan"), show_alert=True)
            return
        await q.answer()
        await show(bank_dep_amount_view(chat_id, uid, bank))
        return

    if action == "da":
        amount = nums[0] if nums else 0
        if amount not in DEPOSIT_AMOUNTS:
            await q.answer()
            return
        if wallet_balance(uid) < amount:
            await q.answer(bank_t(chat_id, "no_funds", bal=fmt_money(wallet_balance(uid))), show_alert=True)
            return
        await q.answer()
        await show(bank_dep_term_view(chat_id, uid, bank, amount))
        return

    if action == "dt":
        amount, days = (nums + [0, 0])[:2]
        if amount not in DEPOSIT_AMOUNTS or days not in DEPOSIT_DAYS:
            await q.answer()
            return
        if active_deposit(uid):
            await q.answer(bank_t(chat_id, "dep_has"), show_alert=True)
            return
        if active_loan(uid):
            await q.answer(bank_t(chat_id, "dep_loan"), show_alert=True)
            return
        payout = deposit_payout(amount, days, bank["deposit_rate"])
        matures_at = now + days * DAY_SECONDS
        with c:
            taken = _wallet_take(c, uid, amount)
            if taken:
                c.execute(
                    """INSERT INTO bank_deposits(user_id, amount, days, payout, created_at, matures_at, bank_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (uid, amount, days, payout, now, matures_at, bank["id"]),
                )
        if not taken:
            await q.answer(bank_t(chat_id, "no_funds", bal=fmt_money(wallet_balance(uid))), show_alert=True)
            return
        await q.answer()
        await show(bank_home_view(chat_id, uid, bank), bank_t(
            chat_id, "dep_ok", amount=fmt_money(amount), days=days, payout=fmt_money(payout), when=fmt_when(matures_at),
        ))
        await log_money_event(
            context.bot,
            f"🏦 <b>OMONAT</b> · {escape(bank['name'])}\n{person_name(uid)}: −{amount}$ · {days} kun · tushadi {payout}$",
        )
        return

    await q.answer()


# ── 📝 Kredit arizasi (bank ariza rejimida) ──

def applicant_info(uid):
    """Bank egasi uchun kredit oluvchi haqida to'liq ma'lumot."""
    c = db()
    wallet = wallet_balance(uid)
    hist = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(SUM(status='paid'), 0), COALESCE(SUM(status='auto'), 0) "
        "FROM bank_loans WHERE user_id=?", (uid,)
    ).fetchone()
    dep = active_deposit(uid)
    games = c.execute(
        "SELECT COALESCE(SUM(games), 0), COALESCE(SUM(wins), 0), COALESCE(SUM(points), 0) FROM chat_stats WHERE user_id=?",
        (uid,),
    ).fetchone()
    birja = sum(value for *_, value in birja_portfolio_value(uid))
    pair = active_pair(uid)
    kids = c.execute(
        "SELECT COUNT(*) FROM family_children WHERE parent1_id=? OR parent2_id=?", (uid, uid)
    ).fetchone()[0]
    lines = [
        f"💰 Hamyon: <b>{fmt_money(wallet)}$</b>" + (" 🔻 (minusda)" if wallet < 0 else ""),
        f"🏦 Faol omonat: " + (f"{fmt_money(dep[1])}$ → {fmt_money(dep[3])}$ ({bank_name(dep[5])})" if dep else "yo‘q"),
        f"📈 Birja portfeli: {fmt_money(round(birja))}$",
        f"📜 Kredit tarixi: {hist[0]} ta (jami {fmt_money(hist[1])}$) · ✅ o‘z vaqtida: {hist[2]} · ⚠️ avto-yechilgan: {hist[3]}",
        f"🎮 O‘yinlar: {games[0]} ta · g‘alaba {games[1]} · {games[2]} ball",
        f"💞 Juftlik: {'bor' if pair else 'yo‘q'} · 👶 Farzandlar: {kids}",
    ]
    return "\n".join(lines)


async def submit_loan_app(bot, uid, first_name, bank, amount, days, due, purpose):
    """Ariza rejimidagi bankka kredit arizasini yaratib, bank egasiga yuboradi. True — yetkazildi."""
    c = db()
    with c:
        app_id = c.execute(
            "INSERT INTO bank_loan_apps(bank_id, user_id, amount, days, due, purpose, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bank["id"], uid, amount, days, due, purpose, int(time.time())),
        ).lastrowid
    text = (
        f"📝 <b>KREDIT ARIZASI</b> #{app_id}\n\n"
        f"{user_mention(uid, first_name)} (<code>{uid}</code>) sizning <b>{escape(bank['name'])}</b> "
        f"bankingizdan kredit olmoqchi.\n\n"
        f"💵 Summa: <b>{fmt_money(amount)}$</b> · 📅 {days} kun · "
        f"💳 qaytaradi: <b>{fmt_money(due)}$</b> ({pct(bank['loan_rate'])}% / kun)\n"
        f"🎯 Maqsad: <i>{escape(purpose)}</i>\n\n"
        f"<b>Ma’lumotlar:</b>\n{applicant_info(uid)}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"bka:{app_id}:yes"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"bka:{app_id}:no"),
    ]])
    recipients = [bank["owner_id"]] + [o for o in sorted(CAREER_OWNER_IDS) if o != bank["owner_id"]]
    delivered = 0
    for rid in recipients:
        try:
            await bot.send_message(rid, text, reply_markup=kb)
            delivered += 1
        except TelegramError:
            pass
        if delivered and rid == bank["owner_id"]:
            break   # bank egasiga yetdi — bot egalarini bezovta qilmaymiz
    if not delivered:
        with c:
            c.execute("UPDATE bank_loan_apps SET status='cancelled' WHERE id=?", (app_id,))
        return False
    return True


async def bank_purpose_text(update, context):
    """Shaxsiy chatda kredit maqsadini qabul qilib, arizani bank egasiga yuboradi. True — qayta ishlandi."""
    state = context.user_data.pop("bank_purpose", None)
    if not state:
        return False
    msg = update.effective_message
    user = update.effective_user
    uid = user.id
    bank = bank_get(state["bank"])
    purpose = msg.text.strip()[:500]
    if not bank or not bank["active"] or not bank["apply_mode"]:
        await msg.reply_text(bank_t(uid, "bank_closed"))
        return True
    if active_loan(uid) or pending_app(uid) or wallet_balance(uid) < 0:
        await msg.reply_text(bank_t(uid, "apply_pending" if pending_app(uid) else "loan_has"))
        return True
    ok = await submit_loan_app(context.bot, uid, user.first_name, bank,
                               state["amount"], state["days"], state["due"], purpose)
    if not ok:
        await msg.reply_text(bank_t(uid, "apply_fail_owner"))
        return True
    await msg.reply_text(bank_t(uid, "purpose_sent"))
    return True


async def cb_bank_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, app_text, answer = q.data.split(":")
    c = db()
    row = c.execute(
        "SELECT bank_id, user_id, amount, days, due, status FROM bank_loan_apps WHERE id=?", (int(app_text),)
    ).fetchone()
    if not row:
        await q.answer("Ariza topilmadi.", show_alert=True)
        return
    bank_id, uid, amount, days, due, status = row
    bank = bank_get(bank_id)
    decider = q.from_user.id
    if decider not in CAREER_OWNER_IDS and (not bank or decider != bank["owner_id"]):
        await q.answer("⛔ Faqat bank egasi qaror qila oladi.", show_alert=True)
        return
    if status != "pending":
        await q.answer("Bu ariza allaqachon ko‘rib chiqilgan.", show_alert=True)
        return
    now = int(time.time())
    name = escape(bank["name"]) if bank else "?"
    if answer == "yes":
        if active_loan(uid) or wallet_balance(uid) < 0:
            verdict, ok = "rejected", False
            note = "⚠️ Tasdiqlab bo‘lmadi: foydalanuvchida faol kredit bor yoki balansi minusda — ariza yopildi."
        else:
            with c:
                cur = c.execute(
                    "UPDATE bank_loan_apps SET status='approved', decided_by=?, decided_at=? WHERE id=? AND status='pending'",
                    (decider, now, int(app_text)),
                )
                due_at = issue_loan(c, uid, bank_id, amount, days, due, now) if cur.rowcount == 1 else None
            if due_at is None:
                await q.answer("Bu ariza allaqachon ko‘rib chiqilgan.", show_alert=True)
                return
            verdict, ok = "approved", True
            note = f"✅ Tasdiqlandi — {fmt_money(amount)}$ berildi ({user_mention(decider, q.from_user.first_name)})"
            await bank_notify(context.bot, uid, "apply_ok", bank=name, amount=fmt_money(amount), days=days,
                              due=fmt_money(due), when=fmt_when(due_at))
            await log_money_event(
                context.bot,
                f"🏦 <b>KREDIT (ariza #{app_text})</b> · {name}\n{person_name(uid)}: +{amount}$ · {days} kun · qaytariladi {due}$",
            )
    else:
        verdict, ok = "rejected", False
        note = f"❌ Rad etildi ({user_mention(decider, q.from_user.first_name)})"
    if not ok:
        with c:
            c.execute(
                "UPDATE bank_loan_apps SET status=?, decided_by=?, decided_at=? WHERE id=? AND status='pending'",
                (verdict, decider, now, int(app_text)),
            )
        await bank_notify(context.bot, uid, "apply_no", bank=name)
    await q.answer()
    try:
        await q.edit_message_text(q.message.text_html + "\n\n" + note, reply_markup=None)
    except TelegramError:
        pass


# ── 👑 Owner panel: banklar boshqaruvi ──

def panel_banks_view():
    rows = []
    for b in banks_all():
        mark = "" if b["active"] else " ⛔"
        mode = " 📝" if b["apply_mode"] else ""
        rows.append([InlineKeyboardButton(
            f"🏦 {b['name']} · {pct(b['loan_rate'])}% / {pct(b['deposit_rate'])}%{mode}{mark}",
            callback_data=f"panel:bank_v:{b['id']}",
        )])
    rows.append([InlineKeyboardButton("➕ Bank qo‘shish", callback_data="panel:bank_add")])
    rows.append([InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")])
    text = (
        "🏦 <b>BANKLAR BOSHQARUVI</b>\n\n"
        "Bankni tanlang yoki yangisini qo‘shing.\n"
        "💸 kredit % / 🏦 omonat % (kunlik) · 📝 — kredit ariza orqali · ⛔ — yopiq"
    )
    return text, InlineKeyboardMarkup(rows)


def panel_bank_view(bank_id):
    b = bank_get(bank_id)
    if not b:
        return panel_banks_view()
    c = db()
    loans = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(due), 0) FROM bank_loans WHERE bank_id=? AND status='active'", (bank_id,)
    ).fetchone()
    deps = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM bank_deposits WHERE bank_id=? AND status='active'", (bank_id,)
    ).fetchone()
    apps = c.execute(
        "SELECT COUNT(*) FROM bank_loan_apps WHERE bank_id=? AND status='pending'", (bank_id,)
    ).fetchone()[0]
    text = (
        f"🏦 <b>{escape(b['name'])}</b>{'' if b['active'] else ' ⛔ yopiq'}\n\n"
        f"👤 Egasi: {person_name(b['owner_id'])} (<code>{b['owner_id']}</code>)\n"
        f"💸 Kredit foizi: <b>{pct(b['loan_rate'])}%</b> / kun\n"
        f"🏦 Omonat foizi: <b>{pct(b['deposit_rate'])}%</b> / kun\n"
        f"📝 Kredit berish: <b>{'ariza orqali (egasi tasdiqlaydi)' if b['apply_mode'] else 'avtomatik'}</b>\n\n"
        f"📊 Faol kreditlar: {loans[0]} ta · {fmt_money(loans[1])}$\n"
        f"🏦 Faol omonatlar: {deps[0]} ta · {fmt_money(deps[1])}$\n"
        f"⏳ Kutilayotgan arizalar: {apps} ta"
    )
    bid = b["id"]
    rows = [
        [InlineKeyboardButton("➖ Kredit %", callback_data=f"panel:bank_lr:{bid}:down"),
         InlineKeyboardButton("➕ Kredit %", callback_data=f"panel:bank_lr:{bid}:up")],
        [InlineKeyboardButton("➖ Omonat %", callback_data=f"panel:bank_dr:{bid}:down"),
         InlineKeyboardButton("➕ Omonat %", callback_data=f"panel:bank_dr:{bid}:up")],
        [InlineKeyboardButton(f"📝 Ariza orqali: {'✅' if b['apply_mode'] else '❌'}", callback_data=f"panel:bank_mode:{bid}")],
        [InlineKeyboardButton("👤 Egasini o‘zgartirish", callback_data=f"panel:bank_owner:{bid}")],
    ]
    if bid != MAIN_BANK_ID:
        rows.append([InlineKeyboardButton("⛔ Bankni yopish" if b["active"] else "✅ Bankni ochish",
                                          callback_data=f"panel:bank_act:{bid}")])
    else:
        text += "\n\n🏅 Asosiy bank — doim ochiq, faqat sozlamalari o‘zgaradi."
    rows.append([InlineKeyboardButton("⬅️ Banklar", callback_data="panel:banks")])
    return text, InlineKeyboardMarkup(rows)


PANEL_BANK_CANCEL = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:banks")]])


async def panel_bank_callback(query, context):
    parts = query.data.split(":")
    action = parts[1]
    bid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    context.user_data.pop("panel_bank_state", None)
    c = db()
    if action == "bank_add":
        context.user_data["panel_bank_state"] = {"kind": "add"}
        await query.edit_message_text("🏦 Yangi bank nomini yuboring (2–40 belgi):", reply_markup=PANEL_BANK_CANCEL)
        return
    if action == "bank_owner" and bid:
        context.user_data["panel_bank_state"] = {"kind": "owner", "bank": bid}
        await query.edit_message_text(
            "👤 Bankning yangi egasining Telegram ID sini yoki @username ini yuboring:", reply_markup=PANEL_BANK_CANCEL,
        )
        return
    b = bank_get(bid) if bid else None
    if b:
        if action in ("bank_lr", "bank_dr"):
            col, lo, hi = ("loan_rate", 0.01, 0.50) if action == "bank_lr" else ("deposit_rate", 0.0, 0.20)
            step = 0.01 if parts[3] == "up" else -0.01
            value = round(min(hi, max(lo, b[col] + step)), 4)
            with c:
                c.execute(f"UPDATE banks SET {col}=? WHERE id=?", (value, bid))
        elif action == "bank_mode":
            with c:
                c.execute("UPDATE banks SET apply_mode=1-apply_mode WHERE id=?", (bid,))
        elif action == "bank_act" and bid != MAIN_BANK_ID:
            with c:
                c.execute("UPDATE banks SET active=1-active WHERE id=?", (bid,))
        text, kb = panel_bank_view(bid)
    else:
        text, kb = panel_banks_view()
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def panel_bank_text(update, context):
    """Owner panel: yangi bank nomi yoki bank egasi ID si."""
    state = context.user_data.get("panel_bank_state")
    msg = update.effective_message
    raw = (msg.text or "").strip()
    c = db()
    if state["kind"] == "add":
        if not 2 <= len(raw) <= 40:
            await msg.reply_text("❌ Nom 2–40 belgi bo‘lsin. Qayta yuboring:", reply_markup=PANEL_BANK_CANCEL)
            return
        with c:
            bid = c.execute(
                "INSERT INTO banks(name, owner_id, loan_rate, deposit_rate, apply_mode, active, created_at) "
                "VALUES (?, ?, ?, ?, 0, 1, ?)",
                (raw, update.effective_user.id, LOAN_RATE, DEPOSIT_RATE, int(time.time())),
            ).lastrowid
        context.user_data.pop("panel_bank_state", None)
        text, kb = panel_bank_view(bid)
        await msg.reply_text("✅ Yangi bank qo‘shildi!\n\n" + text, reply_markup=kb)
        return
    # kind == "owner"
    if raw.startswith("@"):
        row = c.execute("SELECT user_id FROM users WHERE lower(username)=lower(?)", (raw[1:],)).fetchone()
    elif raw.isdigit():
        row = (int(raw),)
    else:
        row = None
    if not row:
        await msg.reply_text("❌ Foydalanuvchi topilmadi. ID yoki @username yuboring:", reply_markup=PANEL_BANK_CANCEL)
        return
    with c:
        c.execute("UPDATE banks SET owner_id=? WHERE id=?", (row[0], state["bank"]))
    context.user_data.pop("panel_bank_state", None)
    text, kb = panel_bank_view(state["bank"])
    await msg.reply_text("✅ Bank egasi o‘zgartirildi.\n\n" + text, reply_markup=kb)


async def bank_settle_due(bot):
    """Muddati kelgan kreditlarni yechadi va omonatlarni to'laydi."""
    now = int(time.time())
    c = db()
    loans = c.execute(
        "SELECT id, user_id, due, bank_id FROM bank_loans WHERE status='active' AND due_at<=?", (now,)
    ).fetchall()
    for loan_id, uid, due, bank_id in loans:
        with c:
            cur = c.execute(
                "UPDATE bank_loans SET status='auto', closed_at=? WHERE id=? AND status='active'",
                (now, loan_id),
            )
            if cur.rowcount != 1:
                continue
            _wallet_add(c, uid, -due)   # balans minusga tushishi mumkin — bu qarz
        bal = wallet_balance(uid)
        await bank_notify(bot, uid, "n_loan", due=fmt_money(due), bal=fmt_money(bal), bank=bank_name(bank_id))
        await log_money_event(bot, f"🏅 <b>KREDIT AVTO-YECHILDI</b>\n{person_name(uid)}: −{due}$ (balans {bal}$)")

    deposits = c.execute(
        "SELECT id, user_id, amount, payout, bank_id FROM bank_deposits WHERE status='active' AND matures_at<=?", (now,)
    ).fetchall()
    for dep_id, uid, amount, payout, bank_id in deposits:
        with c:
            cur = c.execute(
                "UPDATE bank_deposits SET status='paid', closed_at=? WHERE id=? AND status='active'",
                (now, dep_id),
            )
            if cur.rowcount != 1:
                continue
            _wallet_add(c, uid, payout)
        bal = wallet_balance(uid)
        await bank_notify(bot, uid, "n_dep", payout=fmt_money(payout), profit=fmt_money(payout - amount),
                          bal=fmt_money(bal), bank=bank_name(bank_id))
        await log_money_event(bot, f"🏅 <b>OMONAT TUSHDI</b>\n{person_name(uid)}: +{payout}$")


async def bank_notify(bot, uid, key, **kwargs):
    try:
        await bot.send_message(uid, bank_t(uid, key, **kwargs))
    except TelegramError:
        pass   # foydalanuvchi botni bloklagan / /start bosmagan


async def bank_worker(application):
    while True:
        try:
            await bank_settle_due(application.bot)
        except Exception:  # noqa: BLE001
            logger.exception("Bank: muddatlarni tekshirishda xato")
        await asyncio.sleep(BANK_TICK)


# ───────────────────────────── 📈 BIRJA (simulator) ─────────────────────────────
# /profil → 📈 Birja. Narxlar real bozordan: Binance ochiq bozor API (data-api.binance.vision),
# ishlamasa — CoinGecko. Har BIRJA_TICK soniyada yangilanadi. Savdo bot pulida (hamyon).
# Iqtisodni himoya qilish: 0.5% komissiya, sotib olingandan keyin 10 daqiqa sotib bo'lmaydi
# (real birjadan kechikish orqali "kafolatlangan foyda" olishning oldini oladi), narx eskirsa savdo to'xtaydi.

BIRJA_ASSETS = {
    # kalit: (nomi, belgi, Binance juftligi, CoinGecko id)
    "BTC": ("Bitcoin", "₿", "BTCUSDT", "bitcoin"),
    "ETH": ("Ethereum", "Ξ", "ETHUSDT", "ethereum"),
    "TON": ("Toncoin", "💎", "TONUSDT", "the-open-network"),
    "SOL": ("Solana", "◎", "SOLUSDT", "solana"),
    "BNB": ("BNB", "🔶", "BNBUSDT", "binancecoin"),
    "GOLD": ("Oltin · 1 unsiya", "🥇", "PAXGUSDT", "pax-gold"),
}
BIRJA_FEE = 0.005
BIRJA_HOLD = 600            # sotib olingandan keyin sotish mumkin bo'lmagan vaqt (soniya)
BIRJA_TICK = 60
BIRJA_STALE = 300           # narx shundan eski bo'lsa savdo to'xtatiladi
BIRJA_MIN_ORDER = 10
BIRJA_MAX_ORDER = 100000
BIRJA_BUY_FIXED = [100, 500, 1000, 5000]
BIRJA_PCTS = [25, 50, 100]
BIRJA_PRICES: dict[str, dict] = {}   # {"BTC": {"price": .., "change": .., "ts": ..}}
_BINANCE_URL = "https://data-api.binance.vision/api/v3"
_COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

BIRJA_TEXT = {
    "uz": {
        "home": "📈 <b>BIRJA</b> · 🎮 simulator\n\nNarxlar real bozordan har daqiqada yangilanadi.\n💵 Hamyon: <b>{wallet}$</b>\n\n{rows}\n\n💸 Komissiya: {fee}% · ⏳ sotib olingandan keyin {hold} daqiqa sotib bo‘lmaydi",
        "asset": "{icon} <b>{name}</b> ({sym})\n\n💲 Narx: <b>{price}$</b>\n📊 24 soat: {change}\n🕒 Yangilandi: {ago} soniya oldin\n\n💼 Sizda: <b>{qty} {sym}</b> ≈ {value}$\n📈 Foyda/zarar: {pnl}",
        "buy_menu": "🟢 <b>{sym} SOTIB OLISH</b>\n\n💲 Narx: {price}$\n💵 Hamyon: {wallet}$\n💸 Komissiya: {fee}%\n\nQancha dollarlik sotib olasiz? 👇",
        "sell_menu": "🔴 <b>{sym} SOTISH</b>\n\n💲 Narx: {price}$\n💼 Sizda: {qty} {sym} ≈ {value}$\n💸 Komissiya: {fee}%\n\nQanchasini sotasiz? 👇",
        "bought": "✅ Sotib olindi: <b>{qty} {sym}</b> · {usd}$ (komissiya {fee}$)",
        "sold": "✅ Sotildi: {qty} {sym} → <b>+{usd}$</b> (komissiya {fee}$)",
        "portfolio": "💼 <b>PORTFELIM</b>\n\n{rows}\n\n💰 Jami qiymat: <b>{total}$</b>\n📈 Jami foyda/zarar: {pnl}\n💵 Hamyon: {wallet}$",
        "portfolio_empty": "💼 <b>PORTFELIM</b>\n\nHozircha aktivlaringiz yo‘q. Birjadan biror aktiv tanlang 👇",
        "top": "🏆 <b>BIRJA REYTINGI</b>\n(portfel qiymati bo‘yicha)\n\n{rows}",
        "top_empty": "🏆 <b>BIRJA REYTINGI</b>\n\nHali hech kim savdo qilmagan.",
        "b_buy": "🟢 Sotib olish", "b_sell": "🔴 Sotish", "b_chart": "📊 Grafik (24 soat)",
        "b_portfolio": "💼 Portfelim", "b_top": "🏆 Reyting", "b_back": "⬅️ Birja", "b_refresh": "🔄 Yangilash",
        "all": "Hammasi",
        "stale": "⏳ Narxlar hozir yangilanmayapti — birozdan keyin urinib ko‘ring.",
        "hold": "⏳ {sym} ni sotish uchun yana {min} daqiqa kuting (sotib olingandan keyin {hold} daqiqa).",
        "min_order": "Minimal savdo — {min}$.",
        "max_order": "Bitta savdo ko‘pi bilan {max}$.",
        "no_funds": "💸 Hamyonda yetarli pul yo‘q (balans: {bal}$).",
        "nothing": "Sizda {sym} yo‘q.",
        "chart_none": "📊 Grafik hozircha mavjud emas — birozdan keyin urinib ko‘ring.",
        "not_yours": "⛔ Bu menyu sizniki emas — o‘zingiz /profil yozing.",
    },
    "eng": {
        "home": "📈 <b>EXCHANGE</b> · 🎮 simulator\n\nPrices follow the real market and update every minute.\n💵 Wallet: <b>{wallet}$</b>\n\n{rows}\n\n💸 Fee: {fee}% · ⏳ can't sell for {hold} minutes after buying",
        "asset": "{icon} <b>{name}</b> ({sym})\n\n💲 Price: <b>{price}$</b>\n📊 24h: {change}\n🕒 Updated: {ago} s ago\n\n💼 You hold: <b>{qty} {sym}</b> ≈ {value}$\n📈 Profit/loss: {pnl}",
        "buy_menu": "🟢 <b>BUY {sym}</b>\n\n💲 Price: {price}$\n💵 Wallet: {wallet}$\n💸 Fee: {fee}%\n\nHow much in dollars? 👇",
        "sell_menu": "🔴 <b>SELL {sym}</b>\n\n💲 Price: {price}$\n💼 You hold: {qty} {sym} ≈ {value}$\n💸 Fee: {fee}%\n\nHow much will you sell? 👇",
        "bought": "✅ Bought: <b>{qty} {sym}</b> · {usd}$ (fee {fee}$)",
        "sold": "✅ Sold: {qty} {sym} → <b>+{usd}$</b> (fee {fee}$)",
        "portfolio": "💼 <b>MY PORTFOLIO</b>\n\n{rows}\n\n💰 Total value: <b>{total}$</b>\n📈 Total profit/loss: {pnl}\n💵 Wallet: {wallet}$",
        "portfolio_empty": "💼 <b>MY PORTFOLIO</b>\n\nYou have no assets yet. Pick one on the exchange 👇",
        "top": "🏆 <b>EXCHANGE LEADERBOARD</b>\n(by portfolio value)\n\n{rows}",
        "top_empty": "🏆 <b>EXCHANGE LEADERBOARD</b>\n\nNobody has traded yet.",
        "b_buy": "🟢 Buy", "b_sell": "🔴 Sell", "b_chart": "📊 Chart (24h)",
        "b_portfolio": "💼 Portfolio", "b_top": "🏆 Leaderboard", "b_back": "⬅️ Exchange", "b_refresh": "🔄 Refresh",
        "all": "All",
        "stale": "⏳ Prices are not updating right now — try again a bit later.",
        "hold": "⏳ Wait {min} more minutes to sell {sym} ({hold} minutes after buying).",
        "min_order": "Minimum trade is {min}$.",
        "max_order": "One trade can be at most {max}$.",
        "no_funds": "💸 Not enough money in your wallet (balance: {bal}$).",
        "nothing": "You don't hold any {sym}.",
        "chart_none": "📊 The chart is not available right now — try again later.",
        "not_yours": "⛔ This menu is not yours — type /profile yourself.",
    },
    "ru": {
        "home": "📈 <b>БИРЖА</b> · 🎮 симулятор\n\nЦены следуют реальному рынку и обновляются каждую минуту.\n💵 Кошелёк: <b>{wallet}$</b>\n\n{rows}\n\n💸 Комиссия: {fee}% · ⏳ после покупки нельзя продать {hold} минут",
        "asset": "{icon} <b>{name}</b> ({sym})\n\n💲 Цена: <b>{price}$</b>\n📊 24 часа: {change}\n🕒 Обновлено: {ago} с назад\n\n💼 У вас: <b>{qty} {sym}</b> ≈ {value}$\n📈 Прибыль/убыток: {pnl}",
        "buy_menu": "🟢 <b>КУПИТЬ {sym}</b>\n\n💲 Цена: {price}$\n💵 Кошелёк: {wallet}$\n💸 Комиссия: {fee}%\n\nНа сколько долларов купить? 👇",
        "sell_menu": "🔴 <b>ПРОДАТЬ {sym}</b>\n\n💲 Цена: {price}$\n💼 У вас: {qty} {sym} ≈ {value}$\n💸 Комиссия: {fee}%\n\nСколько продать? 👇",
        "bought": "✅ Куплено: <b>{qty} {sym}</b> · {usd}$ (комиссия {fee}$)",
        "sold": "✅ Продано: {qty} {sym} → <b>+{usd}$</b> (комиссия {fee}$)",
        "portfolio": "💼 <b>МОЙ ПОРТФЕЛЬ</b>\n\n{rows}\n\n💰 Общая стоимость: <b>{total}$</b>\n📈 Общая прибыль/убыток: {pnl}\n💵 Кошелёк: {wallet}$",
        "portfolio_empty": "💼 <b>МОЙ ПОРТФЕЛЬ</b>\n\nУ вас пока нет активов. Выберите актив на бирже 👇",
        "top": "🏆 <b>РЕЙТИНГ БИРЖИ</b>\n(по стоимости портфеля)\n\n{rows}",
        "top_empty": "🏆 <b>РЕЙТИНГ БИРЖИ</b>\n\nПока никто не торговал.",
        "b_buy": "🟢 Купить", "b_sell": "🔴 Продать", "b_chart": "📊 График (24 ч)",
        "b_portfolio": "💼 Портфель", "b_top": "🏆 Рейтинг", "b_back": "⬅️ Биржа", "b_refresh": "🔄 Обновить",
        "all": "Всё",
        "stale": "⏳ Цены сейчас не обновляются — попробуйте чуть позже.",
        "hold": "⏳ Продать {sym} можно через {min} мин. ({hold} минут после покупки).",
        "min_order": "Минимальная сделка — {min}$.",
        "max_order": "Одна сделка — не больше {max}$.",
        "no_funds": "💸 Недостаточно денег в кошельке (баланс: {bal}$).",
        "nothing": "У вас нет {sym}.",
        "chart_none": "📊 График сейчас недоступен — попробуйте позже.",
        "not_yours": "⛔ Это не ваше меню — напишите /profil сами.",
    },
    "kz": {
        "home": "📈 <b>БИРЖА</b> · 🎮 симулятор\n\nБағалар нақты нарыққа сай әр минут сайын жаңарады.\n💵 Әмиян: <b>{wallet}$</b>\n\n{rows}\n\n💸 Комиссия: {fee}% · ⏳ сатып алғаннан кейін {hold} минут сатуға болмайды",
        "asset": "{icon} <b>{name}</b> ({sym})\n\n💲 Баға: <b>{price}$</b>\n📊 24 сағат: {change}\n🕒 Жаңарды: {ago} с бұрын\n\n💼 Сізде: <b>{qty} {sym}</b> ≈ {value}$\n📈 Пайда/шығын: {pnl}",
        "buy_menu": "🟢 <b>{sym} САТЫП АЛУ</b>\n\n💲 Баға: {price}$\n💵 Әмиян: {wallet}$\n💸 Комиссия: {fee}%\n\nҚанша долларға аласыз? 👇",
        "sell_menu": "🔴 <b>{sym} САТУ</b>\n\n💲 Баға: {price}$\n💼 Сізде: {qty} {sym} ≈ {value}$\n💸 Комиссия: {fee}%\n\nҚаншасын сатасыз? 👇",
        "bought": "✅ Сатып алынды: <b>{qty} {sym}</b> · {usd}$ (комиссия {fee}$)",
        "sold": "✅ Сатылды: {qty} {sym} → <b>+{usd}$</b> (комиссия {fee}$)",
        "portfolio": "💼 <b>ПОРТФЕЛІМ</b>\n\n{rows}\n\n💰 Жалпы құны: <b>{total}$</b>\n📈 Жалпы пайда/шығын: {pnl}\n💵 Әмиян: {wallet}$",
        "portfolio_empty": "💼 <b>ПОРТФЕЛІМ</b>\n\nӘзірге активтеріңіз жоқ. Биржадан актив таңдаңыз 👇",
        "top": "🏆 <b>БИРЖА РЕЙТИНГІ</b>\n(портфель құны бойынша)\n\n{rows}",
        "top_empty": "🏆 <b>БИРЖА РЕЙТИНГІ</b>\n\nӘзірге ешкім сауда жасамаған.",
        "b_buy": "🟢 Сатып алу", "b_sell": "🔴 Сату", "b_chart": "📊 График (24 сағ)",
        "b_portfolio": "💼 Портфель", "b_top": "🏆 Рейтинг", "b_back": "⬅️ Биржа", "b_refresh": "🔄 Жаңарту",
        "all": "Барлығы",
        "stale": "⏳ Бағалар қазір жаңармай тұр — сәл кейін көріңіз.",
        "hold": "⏳ {sym} сату үшін тағы {min} минут күтіңіз (сатып алғаннан кейін {hold} минут).",
        "min_order": "Ең аз сауда — {min}$.",
        "max_order": "Бір сауда {max}$-дан аспайды.",
        "no_funds": "💸 Әмиянда ақша жеткіліксіз (баланс: {bal}$).",
        "nothing": "Сізде {sym} жоқ.",
        "chart_none": "📊 График қазір қолжетімсіз — кейінірек көріңіз.",
        "not_yours": "⛔ Бұл мәзір сіздікі емес — өзіңіз /profil жазыңыз.",
    },
}


def birja_t(chat_id, key, **kwargs):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    text = BIRJA_TEXT.get(lang, BIRJA_TEXT["uz"]).get(key) or BIRJA_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def fmt_price(p):
    if p >= 100:
        return f"{p:,.2f}".replace(",", " ")
    if p >= 1:
        return f"{p:,.4f}".replace(",", " ")
    return f"{p:.6f}"


def fmt_qty(q):
    text = f"{q:.8f}".rstrip("0").rstrip(".")
    return text or "0"


def fmt_change(ch):
    icon = "🟢" if ch >= 0 else "🔴"
    return f"{icon} {ch:+.2f}%"


def fmt_pnl(value):
    icon = "🟢" if value >= 0 else "🔴"
    return f"{icon} {'+' if value >= 0 else '−'}{fmt_money(abs(round(value)))}$"


def init_birja():
    c = db()
    with c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS birja_holdings (
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                qty REAL NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0,
                last_buy INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, asset)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS birja_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                side TEXT NOT NULL,
                qty REAL NOT NULL,
                price REAL NOT NULL,
                usd INTEGER NOT NULL,
                fee INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS birja_prices (
                asset TEXT PRIMARY KEY,
                price REAL NOT NULL,
                change REAL NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
    for asset, price, change, ts in c.execute("SELECT asset, price, change, updated_at FROM birja_prices"):
        if asset in BIRJA_ASSETS:
            BIRJA_PRICES[asset] = {"price": price, "change": change, "ts": ts}


def _http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "son_bot/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_binance():
    symbols = json.dumps([v[2] for v in BIRJA_ASSETS.values()], separators=(",", ":"))
    data = _http_json(f"{_BINANCE_URL}/ticker/24hr?symbols={urllib.parse.quote(symbols)}")
    by_symbol = {row["symbol"]: row for row in data}
    out = {}
    for asset, (_, _, symbol, _) in BIRJA_ASSETS.items():
        row = by_symbol.get(symbol)
        if row and float(row["lastPrice"]) > 0:
            out[asset] = (float(row["lastPrice"]), float(row["priceChangePercent"]))
    return out


def _fetch_coingecko():
    ids = ",".join(v[3] for v in BIRJA_ASSETS.values())
    data = _http_json(f"{_COINGECKO_URL}?ids={ids}&vs_currencies=usd&include_24hr_change=true")
    out = {}
    for asset, (_, _, _, cg_id) in BIRJA_ASSETS.items():
        row = data.get(cg_id)
        if row and row.get("usd"):
            out[asset] = (float(row["usd"]), float(row.get("usd_24h_change") or 0.0))
    return out


async def birja_refresh_prices():
    prices = {}
    for fetch in (_fetch_binance, _fetch_coingecko):
        try:
            prices = await asyncio.to_thread(fetch)
        except Exception as e:  # noqa: BLE001 — tarmoq/format xatosi: keyingi manbani sinaymiz
            logger.warning("Birja: %s ishlamadi: %s", fetch.__name__, e)
            continue
        if len(prices) == len(BIRJA_ASSETS):
            break
    if not prices:
        return
    now = int(time.time())
    c = db()
    with c:
        for asset, (price, change) in prices.items():
            BIRJA_PRICES[asset] = {"price": price, "change": change, "ts": now}
            c.execute(
                """INSERT INTO birja_prices(asset, price, change, updated_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(asset) DO UPDATE SET price=excluded.price, change=excluded.change,
                   updated_at=excluded.updated_at""",
                (asset, price, change, now),
            )


async def birja_worker(application):
    while True:
        try:
            await birja_refresh_prices()
        except Exception:  # noqa: BLE001
            logger.exception("Birja: narxlarni yangilashda xato")
        await asyncio.sleep(BIRJA_TICK)


def birja_price(asset):
    """Joriy narx (eskirgan bo'lsa — None)."""
    p = BIRJA_PRICES.get(asset)
    if not p or time.time() - p["ts"] > BIRJA_STALE:
        return None
    return p["price"]


def birja_holding(uid, asset):
    row = db().execute(
        "SELECT qty, cost, last_buy FROM birja_holdings WHERE user_id=? AND asset=?", (uid, asset)
    ).fetchone()
    return row if row else (0.0, 0.0, 0)


def birja_btn(uid, label, *parts):
    return InlineKeyboardButton(label, callback_data=":".join(["bx", str(uid), *map(str, parts)]))


def birja_home_view(chat_id, uid):
    rows_text = []
    buttons = []
    for asset, (name, icon, _, _) in BIRJA_ASSETS.items():
        p = BIRJA_PRICES.get(asset)
        if p:
            rows_text.append(f"{icon} <b>{asset}</b> — {fmt_price(p['price'])}$ ({fmt_change(p['change'])})")
        else:
            rows_text.append(f"{icon} <b>{asset}</b> — …")
        buttons.append(birja_btn(uid, f"{icon} {asset}", "a", asset))
    kb = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    kb.append([
        birja_btn(uid, birja_t(chat_id, "b_portfolio"), "pf"),
        birja_btn(uid, birja_t(chat_id, "b_top"), "top"),
    ])
    kb.append([birja_btn(uid, birja_t(chat_id, "b_refresh"), "home")])
    text = birja_t(
        chat_id, "home", wallet=fmt_money(wallet_balance(uid)), rows="\n".join(rows_text),
        fee=f"{BIRJA_FEE * 100:g}", hold=BIRJA_HOLD // 60,
    )
    return text, InlineKeyboardMarkup(kb)


def birja_back_row(chat_id, uid):
    return [birja_btn(uid, birja_t(chat_id, "b_back"), "home")]


def birja_asset_view(chat_id, uid, asset):
    name, icon, _, _ = BIRJA_ASSETS[asset]
    p = BIRJA_PRICES.get(asset) or {"price": 0.0, "change": 0.0, "ts": 0}
    qty, cost, _ = birja_holding(uid, asset)
    value = qty * p["price"]
    text = birja_t(
        chat_id, "asset", icon=icon, name=name, sym=asset, price=fmt_price(p["price"]),
        change=fmt_change(p["change"]), ago=max(0, int(time.time() - p["ts"])),
        qty=fmt_qty(qty), value=fmt_money(round(value)), pnl=fmt_pnl(value - cost) if qty > 0 else "—",
    )
    kb = [
        [birja_btn(uid, birja_t(chat_id, "b_buy"), "bm", asset), birja_btn(uid, birja_t(chat_id, "b_sell"), "sm", asset)],
        [birja_btn(uid, birja_t(chat_id, "b_chart"), "ch", asset)],
        [birja_btn(uid, birja_t(chat_id, "b_refresh"), "a", asset)],
        birja_back_row(chat_id, uid),
    ]
    return text, InlineKeyboardMarkup(kb)


def birja_buy_view(chat_id, uid, asset):
    p = BIRJA_PRICES.get(asset) or {"price": 0.0}
    fixed = [birja_btn(uid, f"{fmt_money(a)}$", "b", asset, f"a{a}") for a in BIRJA_BUY_FIXED]
    pct = [birja_btn(uid, f"{x}%" if x < 100 else birja_t(chat_id, "all"), "b", asset, f"p{x}") for x in BIRJA_PCTS]
    kb = [fixed[:2], fixed[2:], pct, [birja_btn(uid, "⬅️ " + asset, "a", asset)]]
    text = birja_t(
        chat_id, "buy_menu", sym=asset, price=fmt_price(p["price"]),
        wallet=fmt_money(wallet_balance(uid)), fee=f"{BIRJA_FEE * 100:g}",
    )
    return text, InlineKeyboardMarkup(kb)


def birja_sell_view(chat_id, uid, asset):
    p = BIRJA_PRICES.get(asset) or {"price": 0.0}
    qty, _, _ = birja_holding(uid, asset)
    pct = [birja_btn(uid, f"{x}%" if x < 100 else birja_t(chat_id, "all"), "s", asset, f"p{x}") for x in BIRJA_PCTS]
    kb = [pct, [birja_btn(uid, "⬅️ " + asset, "a", asset)]]
    text = birja_t(
        chat_id, "sell_menu", sym=asset, price=fmt_price(p["price"]), qty=fmt_qty(qty),
        value=fmt_money(round(qty * p["price"])), fee=f"{BIRJA_FEE * 100:g}",
    )
    return text, InlineKeyboardMarkup(kb)


def birja_portfolio_value(uid):
    rows = db().execute(
        "SELECT asset, qty, cost FROM birja_holdings WHERE user_id=? AND qty > 0", (uid,)
    ).fetchall()
    out = []
    for asset, qty, cost in rows:
        if asset not in BIRJA_ASSETS:
            continue
        price = (BIRJA_PRICES.get(asset) or {"price": 0.0})["price"]
        out.append((asset, qty, cost, qty * price))
    return out


def birja_portfolio_view(chat_id, uid):
    items = birja_portfolio_value(uid)
    kb = InlineKeyboardMarkup([birja_back_row(chat_id, uid)])
    if not items:
        return birja_t(chat_id, "portfolio_empty"), kb
    lines = []
    total = total_cost = 0.0
    for asset, qty, cost, value in sorted(items, key=lambda x: -x[3]):
        icon = BIRJA_ASSETS[asset][1]
        lines.append(f"{icon} <b>{fmt_qty(qty)} {asset}</b> ≈ {fmt_money(round(value))}$ · {fmt_pnl(value - cost)}")
        total += value
        total_cost += cost
    text = birja_t(
        chat_id, "portfolio", rows="\n".join(lines), total=fmt_money(round(total)),
        pnl=fmt_pnl(total - total_cost), wallet=fmt_money(wallet_balance(uid)),
    )
    return text, kb


def birja_top_view(chat_id, uid):
    rows = db().execute("SELECT user_id, asset, qty FROM birja_holdings WHERE qty > 0").fetchall()
    totals = {}
    for user_id, asset, qty in rows:
        price = (BIRJA_PRICES.get(asset) or {"price": 0.0})["price"]
        totals[user_id] = totals.get(user_id, 0.0) + qty * price
    kb = InlineKeyboardMarkup([birja_back_row(chat_id, uid)])
    if not totals:
        return birja_t(chat_id, "top_empty"), kb
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (user_id, value) in enumerate(sorted(totals.items(), key=lambda x: -x[1])[:10]):
        row = db().execute("SELECT first_name, username FROM users WHERE user_id=?", (user_id,)).fetchone()
        name = pretty_name(*(row or (None, None)))
        lines.append(f"{medals[i] if i < 3 else f'{i + 1}.'} <b>{name}</b> — {fmt_money(round(value))}$")
    return birja_t(chat_id, "top", rows="\n".join(lines)), kb


def birja_buy(uid, asset, usd, price):
    """Hamyondan usd yechib, komissiyadan keyingi summaga aktiv beradi. (qty, fee) yoki None."""
    fee = max(1, round(usd * BIRJA_FEE))
    qty = (usd - fee) / price
    now = int(time.time())
    c = db()
    with c:
        if not _wallet_take(c, uid, usd):
            return None
        c.execute(
            """INSERT INTO birja_holdings(user_id, asset, qty, cost, last_buy) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, asset) DO UPDATE SET qty = qty + excluded.qty,
               cost = cost + excluded.cost, last_buy = excluded.last_buy""",
            (uid, asset, qty, usd, now),
        )
        c.execute(
            "INSERT INTO birja_trades(user_id, asset, side, qty, price, usd, fee, created_at) VALUES (?, ?, 'buy', ?, ?, ?, ?, ?)",
            (uid, asset, qty, price, usd, fee, now),
        )
    return qty, fee


def birja_sell(uid, asset, pct, price):
    """Aktivning pct% ini sotadi. (qty, usd, fee) yoki None."""
    qty_have, cost, _ = birja_holding(uid, asset)
    if qty_have <= 0:
        return None
    qty = qty_have if pct >= 100 else qty_have * pct / 100
    gross = qty * price
    fee = max(1, round(gross * BIRJA_FEE)) if gross >= 1 else 0
    usd = max(0, int(gross) - fee)
    left = qty_have - qty
    now = int(time.time())
    c = db()
    with c:
        if left <= 1e-12:
            c.execute("DELETE FROM birja_holdings WHERE user_id=? AND asset=?", (uid, asset))
        else:
            c.execute(
                "UPDATE birja_holdings SET qty=?, cost=? WHERE user_id=? AND asset=?",
                (left, cost * left / qty_have, uid, asset),
            )
        _wallet_add(c, uid, usd)
        c.execute(
            "INSERT INTO birja_trades(user_id, asset, side, qty, price, usd, fee, created_at) VALUES (?, ?, 'sell', ?, ?, ?, ?, ?)",
            (uid, asset, qty, price, usd, fee, now),
        )
    return qty, usd, fee


def render_birja_chart(asset, points):
    """points: [(ts, close)] → PNG baytlari."""
    from PIL import Image, ImageDraw, ImageFont

    w, h, pad_l, pad_r, pad_t, pad_b = 900, 450, 20, 120, 60, 40
    img = Image.new("RGB", (w, h), (17, 22, 31))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=20)
        small = ImageFont.load_default(size=16)
    except TypeError:   # eski Pillow
        font = small = ImageFont.load_default()
    prices = [p for _, p in points]
    lo, hi = min(prices), max(prices)
    span = (hi - lo) or hi * 0.001 or 1
    up = prices[-1] >= prices[0]
    color = (38, 194, 129) if up else (234, 84, 85)

    def xy(i, p):
        x = pad_l + (w - pad_l - pad_r) * i / max(1, len(prices) - 1)
        y = pad_t + (h - pad_t - pad_b) * (1 - (p - lo) / span)
        return x, y

    for k in range(5):   # gorizontal chiziqlar va narx yorliqlari
        y = pad_t + (h - pad_t - pad_b) * k / 4
        draw.line([(pad_l, y), (w - pad_r, y)], fill=(40, 48, 61), width=1)
        draw.text((w - pad_r + 10, y - 9), fmt_price(hi - span * k / 4), fill=(150, 160, 175), font=small)
    line = [xy(i, p) for i, p in enumerate(prices)]
    draw.polygon(line + [(line[-1][0], h - pad_b), (line[0][0], h - pad_b)], fill=tuple(v // 4 for v in color))
    draw.line(line, fill=color, width=3)
    change = (prices[-1] / prices[0] - 1) * 100 if prices[0] else 0
    draw.text((pad_l, 18), f"{asset}/USD  24h", fill=(235, 238, 243), font=font)
    draw.text((pad_l + 220, 18), f"{fmt_price(prices[-1])}$  ({change:+.2f}%)", fill=color, font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fetch_chart(asset):
    symbol = BIRJA_ASSETS[asset][2]
    data = _http_json(f"{_BINANCE_URL}/klines?symbol={symbol}&interval=15m&limit=96")
    points = [(int(row[0]) // 1000, float(row[4])) for row in data]
    if len(points) < 2:
        raise ValueError("grafik uchun ma'lumot yetarli emas")
    return render_birja_chart(asset, points)


async def cb_birja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    chat_id = q.message.chat.id
    uid = int(parts[1])
    action = parts[2]

    if q.from_user.id != uid:
        await q.answer(birja_t(chat_id, "not_yours"), show_alert=True)
        return

    async def show(view, notice=None):
        text, kb = view
        if notice:
            text = notice + "\n\n" + text
        if action == "open":
            await context.bot.send_message(chat_id, text, reply_markup=kb)
        else:
            await edit(context.bot, chat_id, q.message.message_id, text, kb)

    if action in ("open", "home"):
        await q.answer()
        await show(birja_home_view(chat_id, uid))
        return
    if action == "pf":
        await q.answer()
        await show(birja_portfolio_view(chat_id, uid))
        return
    if action == "top":
        await q.answer()
        await show(birja_top_view(chat_id, uid))
        return

    asset = parts[3] if len(parts) > 3 else ""
    if asset not in BIRJA_ASSETS:
        await q.answer()
        return

    if action == "a":
        await q.answer()
        await show(birja_asset_view(chat_id, uid, asset))
        return
    if action == "bm":
        await q.answer()
        await show(birja_buy_view(chat_id, uid, asset))
        return
    if action == "sm":
        qty, _, _ = birja_holding(uid, asset)
        if qty <= 0:
            await q.answer(birja_t(chat_id, "nothing", sym=asset), show_alert=True)
            return
        await q.answer()
        await show(birja_sell_view(chat_id, uid, asset))
        return

    if action == "ch":
        await q.answer()
        try:
            png = await asyncio.to_thread(_fetch_chart, asset)
        except Exception as e:  # noqa: BLE001
            logger.warning("Birja grafigi chizilmadi (%s): %s", asset, e)
            await context.bot.send_message(chat_id, birja_t(chat_id, "chart_none"))
            return
        name, icon, _, _ = BIRJA_ASSETS[asset]
        await context.bot.send_photo(chat_id, png, caption=f"{icon} <b>{name}</b> ({asset}) · 24h")
        return

    price = birja_price(asset)
    if price is None:
        await q.answer(birja_t(chat_id, "stale"), show_alert=True)
        return
    code = parts[4] if len(parts) > 4 else ""

    if action == "b":
        wallet = wallet_balance(uid)
        if code.startswith("a"):
            usd = int(code[1:])
        elif code.startswith("p"):
            usd = int(max(0, wallet) * int(code[1:]) / 100)
        else:
            await q.answer()
            return
        usd = min(usd, BIRJA_MAX_ORDER) if code.startswith("p") else usd
        if usd < BIRJA_MIN_ORDER:
            await q.answer(birja_t(chat_id, "min_order", min=BIRJA_MIN_ORDER), show_alert=True)
            return
        if usd > BIRJA_MAX_ORDER:
            await q.answer(birja_t(chat_id, "max_order", max=fmt_money(BIRJA_MAX_ORDER)), show_alert=True)
            return
        if usd > wallet:
            await q.answer(birja_t(chat_id, "no_funds", bal=fmt_money(wallet)), show_alert=True)
            return
        save_user(q.from_user)
        result = birja_buy(uid, asset, usd, price)
        if not result:
            await q.answer(birja_t(chat_id, "no_funds", bal=fmt_money(wallet_balance(uid))), show_alert=True)
            return
        qty, fee = result
        await q.answer()
        await show(birja_asset_view(chat_id, uid, asset), birja_t(
            chat_id, "bought", qty=fmt_qty(qty), sym=asset, usd=fmt_money(usd), fee=fmt_money(fee),
        ))
        return

    if action == "s":
        qty_have, _, last_buy = birja_holding(uid, asset)
        if qty_have <= 0:
            await q.answer(birja_t(chat_id, "nothing", sym=asset), show_alert=True)
            return
        wait = BIRJA_HOLD - (int(time.time()) - last_buy)
        if wait > 0:
            await q.answer(birja_t(
                chat_id, "hold", sym=asset, min=max(1, math.ceil(wait / 60)), hold=BIRJA_HOLD // 60,
            ), show_alert=True)
            return
        try:
            pct = int(code[1:]) if code.startswith("p") else 0
        except ValueError:
            pct = 0
        if pct not in BIRJA_PCTS:
            await q.answer()
            return
        if qty_have * price * pct / 100 < BIRJA_MIN_ORDER and pct < 100:
            await q.answer(birja_t(chat_id, "min_order", min=BIRJA_MIN_ORDER), show_alert=True)
            return
        result = birja_sell(uid, asset, pct, price)
        if not result:
            await q.answer(birja_t(chat_id, "nothing", sym=asset), show_alert=True)
            return
        qty, usd, fee = result
        await q.answer()
        await show(birja_asset_view(chat_id, uid, asset), birja_t(
            chat_id, "sold", qty=fmt_qty(qty), sym=asset, usd=fmt_money(usd), fee=fmt_money(fee),
        ))
        return

    await q.answer()


# ───────────────────────────── 👶 FARZANDLAR (o'sish, parvarish, ta'lim, ish) ─────────────────────────────
# Farzand real vaqtda o'sadi: KID_YEAR soniya (1 kun) = 1 yosh — lekin faqat to'q va xursand bo'lsa
# va ta'lim bosqichida shu yilgi to'lov qilingan bo'lsa. To'qlik / kayfiyat soatiga kamayadi.
# Bosqichlar: 👶 0–2 · 🧒 bog'cha 3–6 · 🎒 maktab 7–15 · 🏫 kollej 16–18 · 🎓 universitet 19–22 · 💼 ish.
# 16 yoshda: kollej yoki ish; 19 yoshda: universitet yoki ish; 23 da universitetdan keyin ishga kiradi.
# Ishlayotgan farzand har kuni ma'lumotiga qarab maosh olib keladi (ota-onaga teng bo'linadi).
# Callback: "kid:<uid>:<amal>:..." — menyuni ochgan ota/ona boshqaradi.

KID_YEAR = 86400
KID_TICK = 60
KID_MAX_CATCHUP = 3600      # bot to'xtab qolgan vaqt farzandga "jarima" bo'lmasin
KID_HUNGER_RATE = 4.0       # to'qlik soatiga kamayishi (100 → 0 ~25 soatda)
KID_HAPPY_RATE = 3.0        # kayfiyat soatiga kamayishi (100 → 0 ~33 soatda)
KID_FEES = {"kinder": 100, "school": 200, "college": 500, "uni": 1000}   # $ / yil
KID_SALARY = {"school": 100, "college": 200, "uni": 400}                 # $ / kun
KID_ALERT_HUNGRY, KID_ALERT_SAD, KID_ALERT_FEE, KID_ALERT_DECIDE = 1, 2, 4, 8

# kalit: (tur, yoshdan, yoshgacha, narx, ta'sir, {til: nomi})
KID_ITEMS = {
    "milk": ("food", 0, 2, 20, 40, {"uz": "🍼 Sut aralashmasi", "eng": "🍼 Baby formula", "ru": "🍼 Детская смесь", "kz": "🍼 Балалар қоспасы"}),
    "puree": ("food", 0, 3, 25, 45, {"uz": "🥕 Pyure", "eng": "🥕 Puree", "ru": "🥕 Пюре", "kz": "🥕 Пюре"}),
    "porridge": ("food", 1, 6, 30, 50, {"uz": "🥣 Bo‘tqa", "eng": "🥣 Porridge", "ru": "🥣 Каша", "kz": "🥣 Ботқа"}),
    "fruit": ("food", 1, 22, 15, 20, {"uz": "🍎 Mevalar", "eng": "🍎 Fruit", "ru": "🍎 Фрукты", "kz": "🍎 Жемістер"}),
    "lunch": ("food", 3, 22, 45, 60, {"uz": "🍲 Issiq ovqat", "eng": "🍲 Hot meal", "ru": "🍲 Горячий обед", "kz": "🍲 Ыстық тамақ"}),
    "pizza": ("food", 7, 22, 70, 70, {"uz": "🍕 Pitsa", "eng": "🍕 Pizza", "ru": "🍕 Пицца", "kz": "🍕 Пицца"}),
    "feast": ("food", 12, 22, 110, 100, {"uz": "🍱 To‘yimli tushlik", "eng": "🍱 Big lunch", "ru": "🍱 Сытный обед", "kz": "🍱 Тойымды түскі ас"}),
    "rattle": ("toy", 0, 2, 15, 25, {"uz": "🪇 Shaqildoq", "eng": "🪇 Rattle", "ru": "🪇 Погремушка", "kz": "🪇 Сылдырмақ"}),
    "teddy": ("toy", 0, 6, 40, 45, {"uz": "🧸 Ayiqcha", "eng": "🧸 Teddy bear", "ru": "🧸 Мишка", "kz": "🧸 Қонжық"}),
    "blocks": ("toy", 2, 8, 35, 40, {"uz": "🧱 Kubiklar", "eng": "🧱 Blocks", "ru": "🧱 Кубики", "kz": "🧱 Текшелер"}),
    "ball": ("toy", 4, 15, 30, 35, {"uz": "⚽ To‘p", "eng": "⚽ Ball", "ru": "⚽ Мяч", "kz": "⚽ Доп"}),
    "bike": ("toy", 6, 15, 150, 80, {"uz": "🚲 Velosiped", "eng": "🚲 Bicycle", "ru": "🚲 Велосипед", "kz": "🚲 Велосипед"}),
    "console": ("toy", 10, 22, 300, 100, {"uz": "🎮 O‘yin pristavkasi", "eng": "🎮 Game console", "ru": "🎮 Игровая приставка", "kz": "🎮 Ойын приставкасы"}),
    "phone": ("toy", 13, 22, 450, 100, {"uz": "📱 Smartfon", "eng": "📱 Smartphone", "ru": "📱 Смартфон", "kz": "📱 Смартфон"}),
    "laptop": ("toy", 16, 22, 700, 100, {"uz": "💻 Noutbuk", "eng": "💻 Laptop", "ru": "💻 Ноутбук", "kz": "💻 Ноутбук"}),
    # 🎒 Buyumlar (gear): har davr uchun, har farzandga bir marta — kayfiyat +eff va shu davrda kayfiyat sekinroq tushadi
    "cradle": ("gear", 0, 2, 120, 30, {"uz": "🛏 Beshik", "eng": "🛏 Cradle", "ru": "🛏 Колыбель", "kz": "🛏 Бесік"}),
    "swing": ("gear", 0, 2, 90, 25, {"uz": "🎠 Belanchak", "eng": "🎠 Baby swing", "ru": "🎠 Качели", "kz": "🎠 Әткеншек"}),
    "stroller": ("gear", 0, 2, 200, 30, {"uz": "🚼 Aravacha", "eng": "🚼 Stroller", "ru": "🚼 Коляска", "kz": "🚼 Арба"}),
    "pacifier": ("gear", 0, 2, 25, 15, {"uz": "🍼 So‘rg‘ich va idishlar", "eng": "🍼 Pacifier & bottles", "ru": "🍼 Соска и бутылочки", "kz": "🍼 Емізік пен бөтелке"}),
    "k_uniform": ("gear", 3, 6, 80, 25, {"uz": "🧥 Bog‘cha formasi", "eng": "🧥 Kindergarten uniform", "ru": "🧥 Форма для садика", "kz": "🧥 Балабақша формасы"}),
    "crayons": ("gear", 3, 6, 40, 20, {"uz": "🖍️ Rangli qalamlar", "eng": "🖍️ Crayons", "ru": "🖍️ Карандаши", "kz": "🖍️ Түрлі түсті қарындаш"}),
    "scooter": ("gear", 3, 6, 150, 30, {"uz": "🛴 Samokat", "eng": "🛴 Scooter", "ru": "🛴 Самокат", "kz": "🛴 Самокат"}),
    "s_uniform": ("gear", 7, 15, 150, 25, {"uz": "👔 Maktab formasi", "eng": "👔 School uniform", "ru": "👔 Школьная форма", "kz": "👔 Мектеп формасы"}),
    "backpack": ("gear", 7, 15, 90, 25, {"uz": "🎒 Ryukzak", "eng": "🎒 Backpack", "ru": "🎒 Рюкзак", "kz": "🎒 Рюкзак"}),
    "books": ("gear", 7, 15, 120, 20, {"uz": "📚 Darsliklar to‘plami", "eng": "📚 Textbook set", "ru": "📚 Комплект учебников", "kz": "📚 Оқулықтар жинағы"}),
    "stationery": ("gear", 7, 15, 40, 15, {"uz": "✏️ Kanselyariya", "eng": "✏️ Stationery", "ru": "✏️ Канцелярия", "kz": "✏️ Кеңсе тауарлары"}),
    "labcoat": ("gear", 16, 18, 180, 25, {"uz": "🥼 Laboratoriya xalati", "eng": "🥼 Lab coat", "ru": "🥼 Лабораторный халат", "kz": "🥼 Зертхана халаты"}),
    "calculator": ("gear", 16, 18, 60, 15, {"uz": "🧮 Muhandislik kalkulyatori", "eng": "🧮 Scientific calculator", "ru": "🧮 Инженерный калькулятор", "kz": "🧮 Инженерлік калькулятор"}),
    "headphones": ("gear", 16, 22, 120, 25, {"uz": "🎧 Quloqchin", "eng": "🎧 Headphones", "ru": "🎧 Наушники", "kz": "🎧 Құлаққап"}),
    "suit": ("gear", 19, 22, 300, 30, {"uz": "🤵 Talaba kostyumi", "eng": "🤵 Student suit", "ru": "🤵 Студенческий костюм", "kz": "🤵 Студент костюмі"}),
    "tablet": ("gear", 19, 22, 400, 30, {"uz": "📱 Planshet", "eng": "📱 Tablet", "ru": "📱 Планшет", "kz": "📱 Планшет"}),
    "dorm": ("gear", 19, 22, 500, 35, {"uz": "🏠 Yotoqxona jihozlari", "eng": "🏠 Dorm essentials", "ru": "🏠 Вещи для общежития", "kz": "🏠 Жатақхана заттары"}),
}
KID_MEAL_GAP = 12 * 3600    # farzand 12 soatda 1 marta ovqatlanadi


def kid_meals_need(age):
    """Bir yosh o'sish uchun kerakli ovqatlar: 0–2 yosh — 7 ta, har 3 yoshda +1 (haqiqiy odamdek yil uzayib boradi)."""
    return 7 + max(0, age) // 3


def kid_gear(kid):
    return set(filter(None, (kid.get("gear") or "").split(",")))


def kid_gear_now(kid):
    """Joriy yoshga mos, sotib olingan buyumlar soni."""
    owned = kid_gear(kid)
    return sum(1 for k, v in KID_ITEMS.items() if v[0] == "gear" and k in owned and v[1] <= kid["age"] <= v[2])


def kid_eat_check(kid, now):
    """Ovqatlanish mumkinmi: None yoki keyingi ovqatgacha qolgan soniya."""
    wait = KID_MEAL_GAP - (now - (kid.get("last_meal") or 0))
    return wait if wait > 0 else None


def kid_eat(kid, now):
    kid["last_meal"] = now
    kid["meals"] = (kid.get("meals") or 0) + 1

KID_TEXT = {
    "uz": {
        "list": "👶 <b>FARZANDLARIM</b>\n\n🍽 Farzand 12 soatda 1 marta ovqatlanadi; yetarli ovqatdan keyin 1 yosh o‘sadi (0–2 yosh — 7 ta, katta bo‘lgan sari ko‘proq).\n\nFarzandni tanlang 👇",
        "none": "👶 Sizda hali farzand yo‘q. /oila bo‘limidan farzand ko‘rishingiz mumkin.",
        "head": "{icon} <b>{name}</b> · {gender}\n🎂 Yoshi: <b>{age}</b> · {stage}",
        "needs": "🍽 To‘qlik: {hbar} {h}%\n😊 Kayfiyat: {jbar} {j}%\n📈 Keyingi yoshgacha: {left}",
        "work": "🎓 Ma’lumoti: {edu}\n💵 Kunlik maosh: <b>{salary}$</b> (ota-onaga teng bo‘linadi)\n⏰ Keyingi maosh: {left}",
        "ok": "✅ Sog‘lom va baxtli — o‘syapti",
        "custody": "🏠 {name} bilan yashaydi · 💸 Aliment: {payer} kuniga {amount}$",
        "hungry": "⚠️ Och — o‘sish to‘xtagan. Ovqatlantiring!",
        "sad": "⚠️ Zerikkan — o‘sish to‘xtagan. O‘yinchoq oling!",
        "fee": "⚠️ {place} to‘lovi to‘lanmagan ({fee}$) — o‘sish to‘xtagan.",
        "decide16": "🎓 Maktabni tugatdi! Keyingi yo‘lni tanlang 👇",
        "decide19": "🎓 Kollejni tugatdi! Keyingi yo‘lni tanlang 👇",
        "hours": "{h} soat {m} daq",
        "b_food": "🍽 Ovqatlantirish", "b_toy": "🧸 O‘yinchoq", "b_fee": "💳 {place} to‘lovi · {fee}$",
        "b_back": "⬅️ Orqaga", "b_list": "👶 Farzandlarim", "b_kid": "⬅️ {name}",
        "b_college": "🏫 Kollejga ({fee}$/yil)", "b_uni": "🎓 Universitetga ({fee}$/yil)", "b_work": "💼 Ishga ({salary}$/kun)",
        "food_menu": "🍽 <b>{name} uchun ovqat</b>\n\n🍽 To‘qlik: {h}%\n💵 Hamyon: {wallet}$\n\nTanlang 👇",
        "toy_menu": "🧸 <b>{name} uchun o‘yinchoq</b>\n\n😊 Kayfiyat: {j}%\n💵 Hamyon: {wallet}$\n\nTanlang 👇",
        "food_line": "+{eff} to‘qlik", "toy_line": "+{eff} kayfiyat",
        "bought": "✅ {item} olindi (−{price}$)",
        "too_soon": "⏳ {name} yaqinda ovqatlandi. Keyingi ovqat: <b>{left}</b> dan keyin (12 soatda 1 marta).",
        "meal_prog": "{m}/{n} ovqat · keyingi ovqat: {next}", "now": "hozir ✅",
        "b_gear": "🎒 Buyumlar", "gear_menu": "🎒 <b>{name} uchun buyumlar</b>\n\nHar biri bir marta olinadi: kayfiyatni ko‘taradi va shu davrda kayfiyat sekinroq tushadi.\n💵 Hamyon: {wallet}$\n\nTanlang 👇",
        "gear_line": "+{eff} kayfiyat", "owned": "✅ bor", "gear_owned": "✅ {name}da bu buyum allaqachon bor.",
        "full_food": "😋 {name} to‘q — hozir ovqat kerak emas.",
        "full_toy": "😊 {name} juda xursand — hozir o‘yinchoq kerak emas.",
        "fee_ok": "✅ {place} to‘lovi to‘landi (−{fee}$)",
        "path_college": "🏫 {name} kollejga o‘qishga kirdi!",
        "path_uni": "🎓 {name} universitetga o‘qishga kirdi!",
        "path_work": "💼 {name} ishga kirdi! Kuniga {salary}$ maosh olib keladi.",
        "no_funds": "💸 Hamyonda yetarli pul yo‘q (balans: {bal}$).",
        "not_parent": "⛔ Bu sizning farzandingiz emas.",
        "not_yours": "⛔ Bu menyu sizniki emas.",
        "n_hungry": "🍼 <b>{name}</b> och qoldi — o‘sishi to‘xtadi! Ovqatlantiring: /farzand",
        "n_sad": "🧸 <b>{name}</b> zerikib qoldi — o‘sishi to‘xtadi! O‘yinchoq oling: /farzand",
        "n_stage": "🎉 <b>{name}</b> {age} yoshga to‘ldi — endi {stage}!",
        "n_fee": "💳 <b>{name}</b> {age} yoshda: {place} to‘lovi ({fee}$) kerak, aks holda o‘sish to‘xtaydi: /farzand",
        "n_decide": "🎓 <b>{name}</b> {place}ni tugatdi! Keyingi yo‘lni tanlang: /farzand",
        "n_work": "💼 <b>{name}</b> universitetni tugatib ishga kirdi! Kuniga {salary}$ maosh olib keladi.",
        "shop_btn": "👶 Farzandlar uchun (ovqat, o‘yinchoq)",
        "oila_btn": "👶 Farzandlarim",
        "stages": {"baby": "👶 Chaqaloq", "kinder": "🧒 Bog‘cha", "school": "🎒 Maktab", "college": "🏫 Kollej",
                   "uni": "🎓 Universitet", "work": "💼 Ishlaydi"},
        "places": {"kinder": "Bog‘cha", "school": "Maktab", "college": "Kollej", "uni": "Universitet"},
        "edu": {"school": "o‘rta maktab", "college": "kollej", "uni": "oliy (universitet)"},
        "age_unit": "yosh",
    },
    "eng": {
        "list": "👶 <b>MY CHILDREN</b>\n\n🍽 A child eats once every 12 hours and grows a year after enough meals (7 at age 0–2, more as they grow).\n\nChoose a child 👇",
        "none": "👶 You have no children yet. You can have one in the /family section.",
        "head": "{icon} <b>{name}</b> · {gender}\n🎂 Age: <b>{age}</b> · {stage}",
        "needs": "🍽 Fullness: {hbar} {h}%\n😊 Mood: {jbar} {j}%\n📈 Until next birthday: {left}",
        "work": "🎓 Education: {edu}\n💵 Daily salary: <b>{salary}$</b> (split between parents)\n⏰ Next salary: {left}",
        "ok": "✅ Healthy and happy — growing",
        "custody": "🏠 Lives with {name} · 💸 Child support: {payer} pays {amount}$ a day",
        "hungry": "⚠️ Hungry — growth stopped. Feed them!",
        "sad": "⚠️ Bored — growth stopped. Buy a toy!",
        "fee": "⚠️ {place} fee unpaid ({fee}$) — growth stopped.",
        "decide16": "🎓 Finished school! Choose the next path 👇",
        "decide19": "🎓 Finished college! Choose the next path 👇",
        "hours": "{h} h {m} min",
        "b_food": "🍽 Feed", "b_toy": "🧸 Toy", "b_fee": "💳 {place} fee · {fee}$",
        "b_back": "⬅️ Back", "b_list": "👶 My children", "b_kid": "⬅️ {name}",
        "b_college": "🏫 College ({fee}$/yr)", "b_uni": "🎓 University ({fee}$/yr)", "b_work": "💼 Work ({salary}$/day)",
        "food_menu": "🍽 <b>Food for {name}</b>\n\n🍽 Fullness: {h}%\n💵 Wallet: {wallet}$\n\nChoose 👇",
        "toy_menu": "🧸 <b>A toy for {name}</b>\n\n😊 Mood: {j}%\n💵 Wallet: {wallet}$\n\nChoose 👇",
        "food_line": "+{eff} fullness", "toy_line": "+{eff} mood",
        "bought": "✅ Bought {item} (−{price}$)",
        "too_soon": "⏳ {name} ate recently. Next meal in <b>{left}</b> (once every 12 hours).",
        "meal_prog": "{m}/{n} meals · next meal: {next}", "now": "now ✅",
        "b_gear": "🎒 Gear", "gear_menu": "🎒 <b>Gear for {name}</b>\n\nEach is bought once: lifts mood and mood drops slower during this stage.\n💵 Wallet: {wallet}$\n\nChoose 👇",
        "gear_line": "+{eff} mood", "owned": "✅ owned", "gear_owned": "✅ {name} already has this item.",
        "full_food": "😋 {name} is full — no food needed now.",
        "full_toy": "😊 {name} is very happy — no toy needed now.",
        "fee_ok": "✅ {place} fee paid (−{fee}$)",
        "path_college": "🏫 {name} entered college!",
        "path_uni": "🎓 {name} entered university!",
        "path_work": "💼 {name} started working! Brings {salary}$ a day.",
        "no_funds": "💸 Not enough money in your wallet (balance: {bal}$).",
        "not_parent": "⛔ This is not your child.",
        "not_yours": "⛔ This menu is not yours.",
        "n_hungry": "🍼 <b>{name}</b> is hungry — growth stopped! Feed them: /farzand",
        "n_sad": "🧸 <b>{name}</b> is bored — growth stopped! Buy a toy: /farzand",
        "n_stage": "🎉 <b>{name}</b> turned {age} — now {stage}!",
        "n_fee": "💳 <b>{name}</b> is {age}: the {place} fee ({fee}$) is due, otherwise growth stops: /farzand",
        "n_decide": "🎓 <b>{name}</b> finished {place}! Choose the next path: /farzand",
        "n_work": "💼 <b>{name}</b> graduated and started working! Brings {salary}$ a day.",
        "shop_btn": "👶 For children (food, toys)",
        "oila_btn": "👶 My children",
        "stages": {"baby": "👶 Baby", "kinder": "🧒 Kindergarten", "school": "🎒 School", "college": "🏫 College",
                   "uni": "🎓 University", "work": "💼 Working"},
        "places": {"kinder": "Kindergarten", "school": "School", "college": "College", "uni": "University"},
        "edu": {"school": "secondary school", "college": "college", "uni": "higher (university)"},
        "age_unit": "y.o.",
    },
    "ru": {
        "list": "👶 <b>МОИ ДЕТИ</b>\n\nВыберите ребёнка 👇",
        "none": "👶 У вас пока нет детей. Завести ребёнка можно в разделе /oila.",
        "head": "{icon} <b>{name}</b> · {gender}\n🎂 Возраст: <b>{age}</b> · {stage}",
        "needs": "🍽 Сытость: {hbar} {h}%\n😊 Настроение: {jbar} {j}%\n📈 До следующего дня рождения: {left}",
        "work": "🎓 Образование: {edu}\n💵 Зарплата в день: <b>{salary}$</b> (поровну родителям)\n⏰ Следующая зарплата: {left}",
        "ok": "✅ Здоров и счастлив — растёт",
        "custody": "🏠 Живёт с: {name} · 💸 Алименты: {payer} — {amount}$ в день",
        "hungry": "⚠️ Голоден — рост остановлен. Покормите!",
        "sad": "⚠️ Скучает — рост остановлен. Купите игрушку!",
        "fee": "⚠️ Не оплачено: {place} ({fee}$) — рост остановлен.",
        "decide16": "🎓 Окончил школу! Выберите дальнейший путь 👇",
        "decide19": "🎓 Окончил колледж! Выберите дальнейший путь 👇",
        "hours": "{h} ч {m} мин",
        "b_food": "🍽 Покормить", "b_toy": "🧸 Игрушка", "b_fee": "💳 Оплата: {place} · {fee}$",
        "b_back": "⬅️ Назад", "b_list": "👶 Мои дети", "b_kid": "⬅️ {name}",
        "b_college": "🏫 В колледж ({fee}$/год)", "b_uni": "🎓 В университет ({fee}$/год)", "b_work": "💼 Работать ({salary}$/день)",
        "food_menu": "🍽 <b>Еда для: {name}</b>\n\n🍽 Сытость: {h}%\n💵 Кошелёк: {wallet}$\n\nВыберите 👇",
        "toy_menu": "🧸 <b>Игрушка для: {name}</b>\n\n😊 Настроение: {j}%\n💵 Кошелёк: {wallet}$\n\nВыберите 👇",
        "food_line": "+{eff} сытость", "toy_line": "+{eff} настроение",
        "bought": "✅ Куплено: {item} (−{price}$)",
        "too_soon": "⏳ {name} недавно поел(а). Следующий приём пищи через <b>{left}</b> (раз в 12 часов).",
        "meal_prog": "{m}/{n} приёмов пищи · следующий: {next}", "now": "сейчас ✅",
        "b_gear": "🎒 Вещи", "gear_menu": "🎒 <b>Вещи для: {name}</b>\n\nКаждая покупается один раз: поднимает настроение, и в этот период оно падает медленнее.\n💵 Кошелёк: {wallet}$\n\nВыберите 👇",
        "gear_line": "+{eff} настроение", "owned": "✅ есть", "gear_owned": "✅ У ребёнка {name} это уже есть.",
        "full_food": "😋 {name} сыт(а) — еда сейчас не нужна.",
        "full_toy": "😊 {name} очень доволен(льна) — игрушка сейчас не нужна.",
        "fee_ok": "✅ Оплачено: {place} (−{fee}$)",
        "path_college": "🏫 {name} поступил(а) в колледж!",
        "path_uni": "🎓 {name} поступил(а) в университет!",
        "path_work": "💼 {name} начал(а) работать! Приносит {salary}$ в день.",
        "no_funds": "💸 Недостаточно денег в кошельке (баланс: {bal}$).",
        "not_parent": "⛔ Это не ваш ребёнок.",
        "not_yours": "⛔ Это не ваше меню.",
        "n_hungry": "🍼 <b>{name}</b> голоден(дна) — рост остановлен! Покормите: /farzand",
        "n_sad": "🧸 <b>{name}</b> скучает — рост остановлен! Купите игрушку: /farzand",
        "n_stage": "🎉 <b>{name}</b> исполнилось {age} — теперь {stage}!",
        "n_fee": "💳 <b>{name}</b> {age} лет: нужна оплата — {place} ({fee}$), иначе рост остановится: /farzand",
        "n_decide": "🎓 <b>{name}</b> окончил(а) обучение ({place})! Выберите дальнейший путь: /farzand",
        "n_work": "💼 <b>{name}</b> окончил(а) университет и начал(а) работать! Приносит {salary}$ в день.",
        "shop_btn": "👶 Для детей (еда, игрушки)",
        "oila_btn": "👶 Мои дети",
        "stages": {"baby": "👶 Малыш", "kinder": "🧒 Детский сад", "school": "🎒 Школа", "college": "🏫 Колледж",
                   "uni": "🎓 Университет", "work": "💼 Работает"},
        "places": {"kinder": "Детский сад", "school": "Школа", "college": "Колледж", "uni": "Университет"},
        "edu": {"school": "среднее", "college": "колледж", "uni": "высшее (университет)"},
        "age_unit": "лет",
    },
    "kz": {
        "list": "👶 <b>БАЛАЛАРЫМ</b>\n\nБаланы таңдаңыз 👇",
        "none": "👶 Сізде әлі бала жоқ. /oila бөлімінен бала сүюге болады.",
        "head": "{icon} <b>{name}</b> · {gender}\n🎂 Жасы: <b>{age}</b> · {stage}",
        "needs": "🍽 Тоқтық: {hbar} {h}%\n😊 Көңіл-күй: {jbar} {j}%\n📈 Келесі жасқа дейін: {left}",
        "work": "🎓 Білімі: {edu}\n💵 Күндік жалақы: <b>{salary}$</b> (ата-анаға тең бөлінеді)\n⏰ Келесі жалақы: {left}",
        "ok": "✅ Сау әрі бақытты — өсіп жатыр",
        "custody": "🏠 {name} қасында тұрады · 💸 Алимент: {payer} күніне {amount}$",
        "hungry": "⚠️ Аш — өсу тоқтады. Тамақтандырыңыз!",
        "sad": "⚠️ Жалықты — өсу тоқтады. Ойыншық алыңыз!",
        "fee": "⚠️ {place} төлемі төленбеген ({fee}$) — өсу тоқтады.",
        "decide16": "🎓 Мектепті бітірді! Келесі жолды таңдаңыз 👇",
        "decide19": "🎓 Колледжді бітірді! Келесі жолды таңдаңыз 👇",
        "hours": "{h} сағ {m} мин",
        "b_food": "🍽 Тамақтандыру", "b_toy": "🧸 Ойыншық", "b_fee": "💳 {place} төлемі · {fee}$",
        "b_back": "⬅️ Артқа", "b_list": "👶 Балаларым", "b_kid": "⬅️ {name}",
        "b_college": "🏫 Колледжге ({fee}$/жыл)", "b_uni": "🎓 Университетке ({fee}$/жыл)", "b_work": "💼 Жұмысқа ({salary}$/күн)",
        "food_menu": "🍽 <b>{name} үшін тамақ</b>\n\n🍽 Тоқтық: {h}%\n💵 Әмиян: {wallet}$\n\nТаңдаңыз 👇",
        "toy_menu": "🧸 <b>{name} үшін ойыншық</b>\n\n😊 Көңіл-күй: {j}%\n💵 Әмиян: {wallet}$\n\nТаңдаңыз 👇",
        "food_line": "+{eff} тоқтық", "toy_line": "+{eff} көңіл-күй",
        "bought": "✅ {item} алынды (−{price}$)",
        "too_soon": "⏳ {name} жақында тамақтанды. Келесі тамақ: <b>{left}</b> кейін (12 сағатта 1 рет).",
        "meal_prog": "{m}/{n} тамақ · келесі: {next}", "now": "қазір ✅",
        "b_gear": "🎒 Заттар", "gear_menu": "🎒 <b>{name} үшін заттар</b>\n\nӘрқайсысы бір рет алынады: көңіл-күйді көтереді, осы кезеңде көңіл-күй баяу түседі.\n💵 Әмиян: {wallet}$\n\nТаңдаңыз 👇",
        "gear_line": "+{eff} көңіл-күй", "owned": "✅ бар", "gear_owned": "✅ {name} бұл затқа ие.",
        "full_food": "😋 {name} тоқ — қазір тамақ керек емес.",
        "full_toy": "😊 {name} өте бақытты — қазір ойыншық керек емес.",
        "fee_ok": "✅ {place} төлемі төленді (−{fee}$)",
        "path_college": "🏫 {name} колледжге түсті!",
        "path_uni": "🎓 {name} университетке түсті!",
        "path_work": "💼 {name} жұмысқа орналасты! Күніне {salary}$ әкеледі.",
        "no_funds": "💸 Әмиянда ақша жеткіліксіз (баланс: {bal}$).",
        "not_parent": "⛔ Бұл сіздің балаңыз емес.",
        "not_yours": "⛔ Бұл мәзір сіздікі емес.",
        "n_hungry": "🍼 <b>{name}</b> ашығып қалды — өсуі тоқтады! Тамақтандырыңыз: /farzand",
        "n_sad": "🧸 <b>{name}</b> жалығып қалды — өсуі тоқтады! Ойыншық алыңыз: /farzand",
        "n_stage": "🎉 <b>{name}</b> {age} жасқа толды — енді {stage}!",
        "n_fee": "💳 <b>{name}</b> {age} жаста: {place} төлемі ({fee}$) керек, әйтпесе өсу тоқтайды: /farzand",
        "n_decide": "🎓 <b>{name}</b> оқуын бітірді ({place})! Келесі жолды таңдаңыз: /farzand",
        "n_work": "💼 <b>{name}</b> университетті бітіріп, жұмысқа орналасты! Күніне {salary}$ әкеледі.",
        "shop_btn": "👶 Балалар үшін (тамақ, ойыншық)",
        "oila_btn": "👶 Балаларым",
        "stages": {"baby": "👶 Нәресте", "kinder": "🧒 Балабақша", "school": "🎒 Мектеп", "college": "🏫 Колледж",
                   "uni": "🎓 Университет", "work": "💼 Жұмыс істейді"},
        "places": {"kinder": "Балабақша", "school": "Мектеп", "college": "Колледж", "uni": "Университет"},
        "edu": {"school": "орта мектеп", "college": "колледж", "uni": "жоғары (университет)"},
        "age_unit": "жас",
    },
}

KID_COLUMNS = {
    "age": "INTEGER NOT NULL DEFAULT 0",
    "hunger": "REAL NOT NULL DEFAULT 100",
    "happy": "REAL NOT NULL DEFAULT 100",
    "growth": "REAL NOT NULL DEFAULT 0",          # joriy yoshdagi o'sish (soniya)
    "last_tick": "INTEGER NOT NULL DEFAULT 0",
    "fee_age": "INTEGER NOT NULL DEFAULT -1",     # qaysi yosh uchun ta'lim to'lovi qilingan
    "track": "TEXT NOT NULL DEFAULT ''",          # '' | 'college' | 'uni'
    "working": "INTEGER NOT NULL DEFAULT 0",
    "edu": "TEXT NOT NULL DEFAULT ''",            # ishlayotgan bo'lsa: school | college | uni
    "last_salary": "INTEGER NOT NULL DEFAULT 0",
    "alerts": "INTEGER NOT NULL DEFAULT 0",       # yuborilgan ogohlantirishlar (takrorlanmasin)
    "custody_id": "INTEGER NOT NULL DEFAULT 0",   # ajrashgandan keyin farzand kim bilan qoladi
    "alimony_payer": "INTEGER NOT NULL DEFAULT 0",  # kuniga aliment to'laydigan ota/ona
    "last_alimony": "INTEGER NOT NULL DEFAULT 0",
    "inst_id": "INTEGER NOT NULL DEFAULT 0",      # yozilgan ta'lim muassasasi (edu_institutions.id)
    "meals": "INTEGER NOT NULL DEFAULT 0",        # joriy yoshda yeyilgan ovqatlar (kid_meals_need ga yetganda +1 yosh)
    "last_meal": "INTEGER NOT NULL DEFAULT 0",    # oxirgi ovqat vaqti (12 soat oralig'i)
    "gear": "TEXT NOT NULL DEFAULT ''",           # sotib olingan buyumlar (vergul bilan)
    "outfit": "TEXT NOT NULL DEFAULT ''",         # 3D personaj kiyimlari (JSON: hat/top/bottom/shoes/acc/emo)
}
ALIMONY_PER_CHILD = 75      # $ / kun / farzand — farzand ishga kirguncha
KID_FIELDS = ("id", "pair_id", "parent1_id", "parent2_id", "gender", "child_name", *KID_COLUMNS)


def kid_lang(user_id):
    lang = family_lang(user_id)
    return lang if lang in KID_TEXT else "uz"


def kid_t(user_id, key, **kwargs):
    text = KID_TEXT[kid_lang(user_id)].get(key) or KID_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def kid_word(user_id, group, key):
    return KID_TEXT[kid_lang(user_id)][group][key]


def init_kids():
    c = db()
    have = {row[1] for row in c.execute("PRAGMA table_info(family_children)")}
    req_cols = {row[1] for row in c.execute("PRAGMA table_info(pair_requests)")}
    with c:
        for col, decl in KID_COLUMNS.items():
            if col not in have:
                c.execute(f"ALTER TABLE family_children ADD COLUMN {col} {decl}")
        if "meals" not in have:
            # eski vaqt bo'yicha o'sish → ovqatlar soniga (o'sish jarayoni yo'qolmasin)
            c.execute("UPDATE family_children SET meals=CAST(growth * 7 / 86400 AS INTEGER) WHERE growth > 0")
        if "custody_id" not in req_cols:
            c.execute("ALTER TABLE pair_requests ADD COLUMN custody_id INTEGER")
    init_edu()   # ta'lim muassasalari jadvali farzandlar bilan birga


# ── 🏫 Ta'lim muassasalari: ownerlar ochadi (nomi + yillik to'lov); farzand shu bosqichdagi muassasaga yoziladi ──
EDU_KINDS = ("kinder", "school", "college", "uni")
EDU_MIN_AGE = {"kinder": 3, "school": 7, "college": 16, "uni": 19}
EDU_FEE_MAX = 1_000_000


def init_edu():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS edu_institutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL,
            fee INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, owner_id INTEGER, created_at INTEGER)""")


def edu_get(inst_id):
    row = db().execute("SELECT id, kind, name, fee, active FROM edu_institutions WHERE id=?", (inst_id,)).fetchone()
    return dict(zip(("id", "kind", "name", "fee", "active"), row)) if row else None


def edu_list(only_active=True):
    q = "SELECT id, kind, name, fee, active FROM edu_institutions" + (" WHERE active=1" if only_active else "") + " ORDER BY kind, fee, id"
    return [dict(zip(("id", "kind", "name", "fee", "active"), r)) for r in db().execute(q)]


def kid_inst(kid):
    """Farzand hozirgi bosqichiga mos (faol) muassasada o'qisa — o'sha muassasa."""
    if not kid.get("inst_id"):
        return None
    inst = edu_get(kid["inst_id"])
    return inst if inst and inst["active"] and inst["kind"] == kid_stage(kid) else None


def kid_fee(kid):
    """Joriy yil uchun ta'lim to'lovi: muassasa narxi (owner belgilagan), aks holda standart KID_FEES."""
    stage = kid_stage(kid)
    if stage not in KID_FEES:
        return 0
    inst = kid_inst(kid)
    return inst["fee"] if inst else KID_FEES[stage]


def kid_stage(kid):
    age = kid["age"]
    if kid["working"]:
        return "work"
    if age <= 2:
        return "baby"
    if age <= 6:
        return "kinder"
    if age <= 15:
        return "school"
    if age <= 18:
        return "college" if kid["track"] else "school"     # 16 yosh: tanlov kutilmoqda
    return "uni" if kid["track"] == "uni" else "college"   # 19 yosh: tanlov kutilmoqda


def kid_block(kid):
    """O'sishni nima to'xtatib turibdi: None | hungry | sad | fee | decide."""
    if kid["working"]:
        return None
    if kid["age"] == 16 and kid["track"] == "":
        return "decide"
    if kid["age"] == 19 and kid["track"] == "college":
        return "decide"
    if kid["hunger"] <= 0:
        return "hungry"
    if kid["happy"] <= 0:
        return "sad"
    stage = kid_stage(kid)
    if stage in KID_FEES and kid["fee_age"] < kid["age"]:
        return "fee"
    return None


def kid_row(kid_id):
    row = db().execute(f"SELECT {', '.join(KID_FIELDS)} FROM family_children WHERE id=?", (kid_id,)).fetchone()
    return dict(zip(KID_FIELDS, row)) if row else None


def kids_of(user_id):
    rows = db().execute(
        f"SELECT {', '.join(KID_FIELDS)} FROM family_children WHERE parent1_id=? OR parent2_id=? ORDER BY id",
        (user_id, user_id),
    ).fetchall()
    return [dict(zip(KID_FIELDS, r)) for r in rows]


def kid_save(c, kid):
    cols = [col for col in KID_COLUMNS]
    c.execute(
        f"UPDATE family_children SET {', '.join(f'{col}=?' for col in cols)} WHERE id=?",
        [kid[col] for col in cols] + [kid["id"]],
    )


def kid_tick(kid, now):
    """Farzand holatini `now` gacha yangilaydi. Qaytaradi: [(hodisa, {..})] — xabar yuborish uchun."""
    events = []
    if not kid["last_tick"]:
        kid["last_tick"] = now
        if kid["working"] and not kid["last_salary"]:
            kid["last_salary"] = now
        return events
    dt = min(max(0, now - kid["last_tick"]), KID_MAX_CATCHUP)
    kid["last_tick"] = now

    if kid["alimony_payer"] and not kid["working"] and now - kid["last_alimony"] >= KID_YEAR:
        days = (now - kid["last_alimony"]) // KID_YEAR
        kid["last_alimony"] += KID_YEAR * days
        events.append(("alimony", {"amount": ALIMONY_PER_CHILD * min(days, 2)}))

    if kid["working"]:
        if not kid["last_salary"]:
            kid["last_salary"] = now
        elif now - kid["last_salary"] >= KID_YEAR:
            kid["last_salary"] += KID_YEAR * ((now - kid["last_salary"]) // KID_YEAR)
            events.append(("salary", {"salary": KID_SALARY.get(kid["edu"], 0)}))
        return events

    kid["hunger"] = max(0.0, kid["hunger"] - KID_HUNGER_RATE * dt / 3600)
    kid["happy"] = max(0.0, kid["happy"] - KID_HAPPY_RATE * (1 - min(0.6, 0.15 * kid_gear_now(kid))) * dt / 3600)
    if kid["hunger"] <= 0 and not kid["alerts"] & KID_ALERT_HUNGRY:
        kid["alerts"] |= KID_ALERT_HUNGRY
        events.append(("n_hungry", {}))
    if kid["happy"] <= 0 and not kid["alerts"] & KID_ALERT_SAD:
        kid["alerts"] |= KID_ALERT_SAD
        events.append(("n_sad", {}))

    block = kid_block(kid)
    if block == "fee" and not kid["alerts"] & KID_ALERT_FEE:
        kid["alerts"] |= KID_ALERT_FEE
        stage = kid_stage(kid)
        events.append(("n_fee", {"place": stage, "fee": kid_fee(kid)}))
    if block == "decide" and not kid["alerts"] & KID_ALERT_DECIDE:
        kid["alerts"] |= KID_ALERT_DECIDE
        events.append(("n_decide", {"place": "school" if kid["age"] == 16 else "college"}))
    if block:
        return events

    # O'sish endi vaqt bo'yicha emas — ovqat bo'yicha: kid_meals_need(age) ta ovqatdan keyin +1 yosh
    if kid["meals"] >= kid_meals_need(kid["age"]):
        kid["meals"] = 0
        kid["growth"] = 0.0
        before = kid_stage(kid)
        kid["age"] += 1
        kid["alerts"] &= ~(KID_ALERT_FEE | KID_ALERT_DECIDE)
        if kid["age"] >= 23 and kid["track"] == "uni":
            kid.update(working=1, edu="uni", last_salary=now)
            events.append(("n_work", {"salary": KID_SALARY["uni"]}))
            return events
        after = kid_stage(kid)
        if after != before and after not in ("college", "uni"):
            events.append(("n_stage", {"stage": after}))
    return events


KID_MONEY_EVENTS = ("salary", "alimony")


def kid_apply_money(kid, events):
    """Pul hodisalari (maosh, aliment) — xabar yuborilmasa ham albatta bajarilishi kerak."""
    c = db()
    for event, data in events:
        if event == "alimony":
            # Farzand bilan yashamaydigan tomon hisobidan avtomatik (balans minusga tushishi mumkin).
            with c:
                _wallet_add(c, kid["alimony_payer"], -data["amount"])
                _wallet_add(c, kid["custody_id"], data["amount"])
        elif event == "salary":
            salary = data["salary"]
            share = salary // 2
            with c:
                _wallet_add(c, kid["parent1_id"], salary - share)
                _wallet_add(c, kid["parent2_id"], share)


async def kid_apply_events(bot, kid, events):
    """Pul hodisalarini bajaradi va ota-onaga xabar yuboradi."""
    kid_apply_money(kid, events)
    parents = [kid["parent1_id"], kid["parent2_id"]]
    for event, data in events:
        if event in KID_MONEY_EVENTS:
            continue
        for pid in parents:
            kwargs = {"name": escape(kid["child_name"]), "age": kid["age"]}
            if "stage" in data:
                kwargs["stage"] = kid_word(pid, "stages", data["stage"])
            if "place" in data:
                kwargs["place"] = kid_word(pid, "places", data["place"])
            if "fee" in data:
                kwargs["fee"] = data["fee"]
            if "salary" in data:
                kwargs["salary"] = data["salary"]
            try:
                await bot.send_message(pid, kid_t(pid, event, **kwargs))
            except TelegramError:
                pass


async def kid_worker(application):
    while True:
        try:
            now = int(time.time())
            ids = [r[0] for r in db().execute("SELECT id FROM family_children")]
            for kid_id in ids:
                kid = kid_row(kid_id)
                if not kid:
                    continue
                events = kid_tick(kid, now)
                c = db()
                with c:
                    kid_save(c, kid)
                if events:
                    await kid_apply_events(application.bot, kid, events)
        except Exception:  # noqa: BLE001
            logger.exception("Farzandlar: holatni yangilashda xato")
        await asyncio.sleep(KID_TICK)


def kid_fresh(kid_id):
    """Ko'rsatishdan oldin holatni hozirgi vaqtga yangilaydi (xabarlarsiz)."""
    kid = kid_row(kid_id)
    if not kid:
        return None
    events = kid_tick(kid, int(time.time()))
    c = db()
    with c:
        kid_save(c, kid)
    kid_apply_money(kid, events)
    return kid


def kid_icon(kid):
    return {"baby": "👶", "kinder": "🧒", "school": "🎒", "college": "🏫", "uni": "🎓", "work": "💼"}[kid_stage(kid)]


def kid_summary(user_id, name, gender, kid=None):
    """Profil va oila bo'limidagi qisqa qator."""
    base = f"{escape(name)} — {escape(child_gender_label(user_id, gender))}"
    if not kid:
        return f"👶 {base}"
    unit = KID_TEXT[kid_lang(user_id)]["age_unit"]
    return f"{kid_icon(kid)} {base} · {kid['age']} {unit} ({kid_word(user_id, 'stages', kid_stage(kid))})"


def kid_btn(uid, label, *parts):
    return InlineKeyboardButton(label, callback_data=":".join(["kid", str(uid), *map(str, parts)]))


def kid_hours(uid, seconds):
    seconds = max(0, int(seconds))
    return kid_t(uid, "hours", h=seconds // 3600, m=seconds % 3600 // 60)


def kid_list_view(uid):
    kids = kids_of(uid)
    if not kids:
        return kid_t(uid, "none"), None
    unit = KID_TEXT[kid_lang(uid)]["age_unit"]
    rows = [
        [kid_btn(uid, f"{kid_icon(k)} {k['child_name']} · {k['age']} {unit}", "v", k["id"])]
        for k in kids
    ]
    return kid_t(uid, "list"), InlineKeyboardMarkup(rows)


def kid_view(uid, kid):
    stage = kid_stage(kid)
    lines = [kid_t(
        uid, "head", icon=kid_icon(kid), name=escape(kid["child_name"]),
        gender=escape(child_gender_label(uid, kid["gender"])), age=kid["age"],
        stage=kid_word(uid, "stages", stage),
    ), ""]
    rows = []
    if kid["alimony_payer"] and not kid["working"]:
        lines.append(kid_t(
            uid, "custody", name=person_name(kid["custody_id"]), payer=person_name(kid["alimony_payer"]),
            amount=ALIMONY_PER_CHILD,
        ) + "\n")
    if kid["working"]:
        lines.append(kid_t(
            uid, "work", edu=kid_word(uid, "edu", kid["edu"]), salary=KID_SALARY.get(kid["edu"], 0),
            left=kid_hours(uid, KID_YEAR - (time.time() - kid["last_salary"])),
        ))
    else:
        h, j = round(kid["hunger"]), round(kid["happy"])
        wait = kid_eat_check(kid, int(time.time()))
        lines.append(kid_t(
            uid, "needs", hbar=bar(h, 8), h=h, jbar=bar(j, 8), j=j,
            left=kid_t(uid, "meal_prog", m=kid["meals"], n=kid_meals_need(kid["age"]),
                       next=kid_hours(uid, wait) if wait else kid_t(uid, "now")),
        ))
        block = kid_block(kid)
        if block == "fee":
            lines.append(kid_t(uid, "fee", place=kid_word(uid, "places", stage), fee=kid_fee(kid)))
        elif block == "decide":
            lines.append(kid_t(uid, "decide16" if kid["age"] == 16 else "decide19"))
        elif block:
            lines.append(kid_t(uid, block))
        else:
            lines.append(kid_t(uid, "ok"))

        if block == "decide":
            nxt = "college" if kid["age"] == 16 else "uni"
            done = "school" if kid["age"] == 16 else "college"
            rows.append([kid_btn(uid, kid_t(uid, f"b_{nxt}", fee=KID_FEES[nxt]), "p", kid["id"], nxt)])
            rows.append([kid_btn(uid, kid_t(uid, "b_work", salary=KID_SALARY[done]), "p", kid["id"], "work")])
        rows.append([
            kid_btn(uid, kid_t(uid, "b_food"), "f", kid["id"]),
            kid_btn(uid, kid_t(uid, "b_toy"), "t", kid["id"]),
            kid_btn(uid, kid_t(uid, "b_gear"), "g", kid["id"]),
        ])
        if stage in KID_FEES and kid["fee_age"] < kid["age"] and block != "decide":
            rows.append([kid_btn(
                uid, kid_t(uid, "b_fee", place=kid_word(uid, "places", stage), fee=kid_fee(kid)), "fee", kid["id"],
            )])
    rows.append([kid_btn(uid, kid_t(uid, "b_list"), "list")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def kid_items_view(uid, kid, kind):
    lang = kid_lang(uid)
    rows = []
    owned = kid_gear(kid)
    for key, (k, lo, hi, price, eff, names) in KID_ITEMS.items():
        if k != kind or not lo <= kid["age"] <= hi:
            continue
        effect = kid_t(uid, {"food": "food_line", "toy": "toy_line", "gear": "gear_line"}[kind], eff=eff)
        tail = kid_t(uid, "owned") if kind == "gear" and key in owned else f"{price}$ · {effect}"
        rows.append([kid_btn(uid, f"{names.get(lang, names['uz'])} — {tail}", "b", kid["id"], key)])
    rows.append([kid_btn(uid, kid_t(uid, "b_kid", name=kid["child_name"]), "v", kid["id"])])
    text = kid_t(
        uid, {"food": "food_menu", "toy": "toy_menu", "gear": "gear_menu"}[kind], name=escape(kid["child_name"]),
        h=round(kid["hunger"]), j=round(kid["happy"]), wallet=fmt_money(wallet_balance(uid)),
    )
    return text, InlineKeyboardMarkup(rows)


async def cmd_farzand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return
    save_user(user)
    text, kb = kid_list_view(user.id)
    await msg.reply_text(text, reply_markup=kb)


async def cb_kid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    uid = int(parts[1])
    action = parts[2]
    user = q.from_user
    if user.id != uid:
        await q.answer(kid_t(user.id, "not_yours"), show_alert=True)
        return

    async def show(view, notice=None):
        text, kb = view
        if notice:
            text = notice + "\n\n" + text
        if action == "open":
            await context.bot.send_message(q.message.chat.id, text, reply_markup=kb)
        else:
            await edit(context.bot, q.message.chat.id, q.message.message_id, text, kb)

    if action in ("open", "list"):
        await q.answer()
        await show(kid_list_view(uid))
        return

    kid = kid_fresh(int(parts[3])) if len(parts) > 3 and parts[3].isdigit() else None
    if not kid or uid not in (kid["parent1_id"], kid["parent2_id"]):
        await q.answer(kid_t(uid, "not_parent"), show_alert=True)
        return
    name = escape(kid["child_name"])

    if action == "v":
        await q.answer()
        await show(kid_view(uid, kid))
        return

    if kid["working"]:
        await q.answer()
        await show(kid_view(uid, kid))
        return

    if action in ("f", "t", "g"):
        await q.answer()
        await show(kid_items_view(uid, kid, {"f": "food", "t": "toy", "g": "gear"}[action]))
        return

    c = db()
    if action == "b":
        item = KID_ITEMS.get(parts[4] if len(parts) > 4 else "")
        if not item or not item[1] <= kid["age"] <= item[2]:
            await q.answer()
            return
        kind, _, _, price, eff, names = item
        stat = "hunger" if kind == "food" else "happy"
        now = int(time.time())
        if kind == "gear":
            if parts[4] in kid_gear(kid):
                await q.answer(kid_t(uid, "gear_owned", name=kid["child_name"]), show_alert=True)
                return
            kid["gear"] = ",".join(sorted(kid_gear(kid) | {parts[4]}))
        elif kind == "food":
            wait = kid_eat_check(kid, now)
            if wait:
                await q.answer(re.sub(r"<[^>]+>", "", kid_t(uid, "too_soon", name=kid["child_name"], left=kid_hours(uid, wait))), show_alert=True)
                return
        if kind != "gear" and kid[stat] >= 100:
            await q.answer(kid_t(uid, "full_food" if kind == "food" else "full_toy", name=kid["child_name"]), show_alert=True)
            return
        if kind == "food":
            kid_eat(kid, now)
        kid[stat] = min(100.0, kid[stat] + eff)
        kid["alerts"] &= ~(KID_ALERT_HUNGRY if kind == "food" else KID_ALERT_SAD)
        with c:
            paid = _wallet_take(c, uid, price)
            if paid:
                kid_save(c, kid)
        if not paid:
            await q.answer(kid_t(uid, "no_funds", bal=fmt_money(wallet_balance(uid))), show_alert=True)
            return
        await q.answer()
        item_name = names.get(kid_lang(uid), names["uz"])
        await show(kid_items_view(uid, kid, kind), kid_t(uid, "bought", item=item_name, price=price))
        return

    if action == "fee":
        stage = kid_stage(kid)
        if stage not in KID_FEES or kid["fee_age"] >= kid["age"]:
            await q.answer()
            await show(kid_view(uid, kid))
            return
        fee = kid_fee(kid)
        kid["fee_age"] = kid["age"]
        kid["alerts"] &= ~KID_ALERT_FEE
        with c:
            paid = _wallet_take(c, uid, fee)
            if paid:
                kid_save(c, kid)
        if not paid:
            await q.answer(kid_t(uid, "no_funds", bal=fmt_money(wallet_balance(uid))), show_alert=True)
            return
        await q.answer()
        await show(kid_view(uid, kid), kid_t(uid, "fee_ok", place=kid_word(uid, "places", stage), fee=fee))
        return

    if action == "p":
        choice = parts[4] if len(parts) > 4 else ""
        if kid_block(kid) != "decide":
            await q.answer()
            await show(kid_view(uid, kid))
            return
        done = "school" if kid["age"] == 16 else "college"
        nxt = "college" if kid["age"] == 16 else "uni"
        if choice == "work":
            kid.update(working=1, edu=done, last_salary=int(time.time()))
            notice = kid_t(uid, "path_work", name=name, salary=KID_SALARY[done])
        elif choice == nxt:
            kid["track"] = nxt
            notice = kid_t(uid, f"path_{nxt}", name=name)
        else:
            await q.answer()
            return
        kid["alerts"] &= ~KID_ALERT_DECIDE
        with c:
            kid_save(c, kid)
        await q.answer()
        await show(kid_view(uid, kid), notice)
        return

    await q.answer()


# ───────────────────────────── 🛡 GURUH HIMOYASI (Group Help uslubida, kulgili) ─────────────────────────────
# Captcha (emoji tanlash), xush kelibsiz, anti-reklama, anti-flood, /warn /mute /ban /kick va /settings.
# Sozlamalar guruh bo'yicha `group_settings` jadvalida. Standart: faqat salomlashish yoqiq — qolganini
# adminlar /settings orqali yoqadi. Bot guruhda admin bo'lishi kerak (o'chirish va bloklash huquqi bilan).

GUARD_DEFAULTS = {"captcha": 0, "welcome": 1, "antilink": 0, "antiflood": 0, "warn_limit": 3, "warn_action": "mute",
                  "welcome_text": "", "night": 0, "night_start": 0, "night_end": 7, "night_active": 0,
                  "night_saved": "", "log_chat": 0, "locks": 0, "rules": "", "badword_mute": 1800}
CAPTCHA_TTL = 120               # captcha uchun vaqt (soniya)
FLOOD_COUNT, FLOOD_WINDOW = 7, 5   # 5 soniyada 7 ta xabar — flood
FLOOD_MUTE = 300                # flood uchun jim qilish (soniya)
BADWORD_MUTE = 1800             # taqiqlangan so'z → 30 daqiqa jim
WARN_MUTE = 86400               # ogohlantirish limiti → 1 kun jim
NOTICE_TTL = 20                 # anti-reklama/flood xabarlari shuncha soniyadan keyin o'chadi
ADMIN_CACHE_TTL = 300
CAPTCHA_ITEMS = [
    ("🍌", {"uz": "bananni", "eng": "the banana", "ru": "банан", "kz": "бананды"}),
    ("🍉", {"uz": "tarvuzni", "eng": "the watermelon", "ru": "арбуз", "kz": "қарбызды"}),
    ("🐸", {"uz": "qurbaqani", "eng": "the frog", "ru": "лягушку", "kz": "бақаны"}),
    ("🚀", {"uz": "raketani", "eng": "the rocket", "ru": "ракету", "kz": "зымыранды"}),
    ("🍕", {"uz": "pitsani", "eng": "the pizza", "ru": "пиццу", "kz": "пиццаны"}),
    ("🐱", {"uz": "mushukni", "eng": "the cat", "ru": "кота", "kz": "мысықты"}),
    ("⚽", {"uz": "to‘pni", "eng": "the ball", "ru": "мяч", "kz": "допты"}),
    ("🎈", {"uz": "sharni", "eng": "the balloon", "ru": "шарик", "kz": "шарды"}),
]
_LINK_RE = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/|\b[\w-]+\.(com|ru|uz|net|org|io|me|xyz|link|site|info)\b)", re.I)
ADMIN_CACHE: dict[int, tuple[float, set]] = {}
FLOOD_TRACK: dict[tuple, list] = {}
CAPTCHA_PENDING: dict[tuple, dict] = {}

MOD_TEXT = {
    "uz": {
        "welcome": [
            "🎉 Diqqat, diqqat! Guruhga {name} tashrif buyurdi! Choy qo‘yinglar ☕",
            "👋 {name}, xush kelibsiz! Bu yerda o‘yin, kulgi va ozgina tartib bor 😎",
            "🚪 Eshik ochildi va… {name} kirib keldi! Qarsaklar 👏👏👏",
            "🛸 Yangi mehmon qo‘ndi: {name}. Kosmik salom! 👽",
            "🍉 {name} keldi — endi guruh yanada shirinroq bo‘ldi!",
            "🎺 Tan-ta-ram! {name} sahnaga chiqdi! Kutib oling 🥳",
        ],
        "captcha": "🤖 {name}, avval isbotla — odammisan yoki robot?\n\n👇 <b>{emoji} {thing}</b> bos! ({sec} soniya)",
        "cap_ok": "✅ Tabriklaymiz, {name} — 100% inson! 🧬 Endi bemalol yozishingiz mumkin.",
        "cap_wrong": "🤖 Bip-bup! {name} robot ekani aniqlandi. Zavodga qaytarildi 🏭",
        "cap_timeout": "⌛ {name} o‘ylab-o‘ylab uxlab qoldi 😴 — guruhdan chiqarildi.",
        "cap_not_you": "✋ Bu tugma sen uchun emas — sen allaqachon odamsan 😄",
        "link": [
            "🧹 {name}, reklama supurib tashlandi! Bu yer bozor emas 😅",
            "🚫 {name}, havola tashlash mumkin emas — internetni boshqa joyga olib boring 🌐",
            "🕵️ {name}, havola ushlandi va yo‘q qilindi. Biz hammasini ko‘ramiz 👀",
        ],
        "flood": [
            "🐢 {name}, sekinroq! Klaviaturang yonib ketyapti 🔥 — {dur} dam ol.",
            "🌊 {name} xabarlar to‘foni boshladi! Qutqaruv xizmati {dur} jimlik e’lon qildi 🛟",
        ],
        "warn": "⚠️ {name} sariq kartochka oldi! ({n}/{limit})",
        "warn_reason": "\n📝 Sabab: {reason}",
        "warn_mute": "🟥 Qizil kartochka! {name} {limit}/{limit} — {dur}ga og‘ziga skotch yopishtirildi 🤐",
        "warn_ban": "🟥 Qizil kartochka! {name} maydondan butunlay chiqarildi 🚀",
        "unwarn": "🧽 {name} ning bitta ogohlantirishi o‘chirildi ({n}/{limit}).",
        "warns": "📋 {name}: {n}/{limit} ogohlantirish.",
        "mute": [
            "🤐 {name} ning og‘ziga {dur}ga skotch yopishtirildi.",
            "🔇 {name} {dur}ga ovozsiz rejimga o‘tkazildi. Dam ol, do‘stim 🧘",
        ],
        "unmute": "🗣 {name} yana gapira oladi! Skotch olib tashlandi 🎉",
        "ban": [
            "🚀 {name} kosmosga uchirildi! Qaytib kelmasa kerak 👋",
            "🔨 Hakam hushtagi! {name} butunlay chetlatildi.",
        ],
        "unban": "🕊 {name} amnistiya oldi — qaytib kirishi mumkin.",
        "kick": "🦶 {name} guruhdan tepib chiqarildi! (xohlasa qaytib kirishi mumkin)",
        "tban": "⏳🚀 {name} {dur}ga chetlatildi — keyin qaytib kira oladi.",
        "need_target": "↩️ Kimningdir xabariga reply qilib yozing yoki ID / @username kiriting.",
        "not_admin": "⛔ Bu buyruq faqat adminlar uchun. Yaxshi urinish edi 😏",
        "target_admin": "😅 Adminga qarshi? Yo‘q, bunday qilmaymiz.",
        "target_bot": "🤖 O‘zimni jazolamayman — men bu yerda kerakman!",
        "no_rights": "😓 Menda bunga huquq yo‘q. Meni admin qilib, «a’zolarni bloklash» va «xabarlarni o‘chirish» huquqini bering.",
        "group_only": "👥 Bu buyruq faqat guruhda ishlaydi.",
        "settings": "⚙️ <b>GURUH SOZLAMALARI</b>\n\nTugmani bosib yoqing / o‘chiring 👇",
        "s_captcha": "🤖 Captcha", "s_welcome": "👋 Salomlashish", "s_antilink": "🔗 Anti-reklama",
        "s_antiflood": "🌊 Anti-flood", "s_limit": "⚠️ Ogohlantirish limiti: {n}",
        "s_action": "🟥 Limitdan keyin: {a}", "a_mute": "🤐 1 kun jim", "a_ban": "🚀 Ban",
        "s_saved": "✅ Saqlandi",
        "units": {"m": "daqiqa", "h": "soat", "d": "kun"},
    },
    "eng": {
        "welcome": ["🎉 Attention! {name} has entered the chat! Put the kettle on ☕",
                    "🚪 The door opened and… {name} walked in! Applause 👏👏👏"],
        "captcha": "🤖 {name}, prove it first — human or robot?\n\n👇 Tap <b>{emoji} {thing}</b>! ({sec} s)",
        "cap_ok": "✅ Congrats, {name} — 100% human! 🧬 You can chat now.",
        "cap_wrong": "🤖 Beep-boop! {name} turned out to be a robot. Sent back to the factory 🏭",
        "cap_timeout": "⌛ {name} thought so long they fell asleep 😴 — removed from the group.",
        "cap_not_you": "✋ This button isn't for you — you're already human 😄",
        "link": ["🧹 {name}, the ad was swept away! This isn't a bazaar 😅"],
        "flood": ["🐢 {name}, slow down! Your keyboard is on fire 🔥 — rest for {dur}."],
        "warn": "⚠️ {name} got a yellow card! ({n}/{limit})", "warn_reason": "\n📝 Reason: {reason}",
        "warn_mute": "🟥 Red card! {name} {limit}/{limit} — taped shut for {dur} 🤐",
        "warn_ban": "🟥 Red card! {name} is sent off for good 🚀",
        "unwarn": "🧽 One warning removed from {name} ({n}/{limit}).", "warns": "📋 {name}: {n}/{limit} warnings.",
        "mute": ["🤐 {name} got their mouth taped for {dur}."],
        "unmute": "🗣 {name} can talk again! Tape removed 🎉",
        "ban": ["🚀 {name} was launched into space! Bye 👋"],
        "unban": "🕊 {name} got amnesty — they may come back.",
        "kick": "🦶 {name} was kicked out! (they can rejoin)",
        "need_target": "↩️ Reply to someone's message or give an ID / @username.",
        "not_admin": "⛔ Admins only. Nice try 😏", "target_admin": "😅 Against an admin? Nope.",
        "target_bot": "🤖 I won't punish myself — I'm needed here!",
        "no_rights": "😓 I don't have the rights. Make me admin with «ban users» and «delete messages».",
        "group_only": "👥 This command works only in groups.",
        "settings": "⚙️ <b>GROUP SETTINGS</b>\n\nTap to turn on / off 👇",
        "s_captcha": "🤖 Captcha", "s_welcome": "👋 Welcome", "s_antilink": "🔗 Anti-ads",
        "s_antiflood": "🌊 Anti-flood", "s_limit": "⚠️ Warn limit: {n}",
        "s_action": "🟥 After limit: {a}", "a_mute": "🤐 1 day mute", "a_ban": "🚀 Ban", "s_saved": "✅ Saved",
        "units": {"m": "min", "h": "h", "d": "d"},
    },
    "ru": {
        "welcome": ["🎉 Внимание! В группу пришёл(ла) {name}! Ставьте чайник ☕",
                    "🚪 Дверь открылась и… вошёл(ла) {name}! Аплодисменты 👏👏👏"],
        "captcha": "🤖 {name}, сначала докажи — человек или робот?\n\n👇 Нажми <b>{emoji} {thing}</b>! ({sec} с)",
        "cap_ok": "✅ Поздравляем, {name} — 100% человек! 🧬 Можно писать.",
        "cap_wrong": "🤖 Бип-буп! {name} оказался роботом. Отправлен обратно на завод 🏭",
        "cap_timeout": "⌛ {name} так долго думал(а), что уснул(а) 😴 — удалён(а) из группы.",
        "cap_not_you": "✋ Эта кнопка не для тебя — ты уже человек 😄",
        "link": ["🧹 {name}, реклама выметена! Здесь не базар 😅"],
        "flood": ["🐢 {name}, помедленнее! Клавиатура горит 🔥 — отдохни {dur}."],
        "warn": "⚠️ {name} получил(а) жёлтую карточку! ({n}/{limit})", "warn_reason": "\n📝 Причина: {reason}",
        "warn_mute": "🟥 Красная карточка! {name} {limit}/{limit} — рот заклеен скотчем на {dur} 🤐",
        "warn_ban": "🟥 Красная карточка! {name} удалён(а) с поля навсегда 🚀",
        "unwarn": "🧽 С {name} снято одно предупреждение ({n}/{limit}).", "warns": "📋 {name}: {n}/{limit} предупреждений.",
        "mute": ["🤐 {name} заклеили рот скотчем на {dur}."],
        "unmute": "🗣 {name} снова может говорить! Скотч снят 🎉",
        "ban": ["🚀 {name} отправлен(а) в космос! Пока 👋"],
        "unban": "🕊 {name} амнистирован(а) — можно вернуться.",
        "kick": "🦶 {name} выгнан(а) из группы! (может вернуться)",
        "need_target": "↩️ Ответьте на сообщение человека или укажите ID / @username.",
        "not_admin": "⛔ Только для админов. Хорошая попытка 😏", "target_admin": "😅 Против админа? Нет уж.",
        "target_bot": "🤖 Себя наказывать не буду — я тут нужен!",
        "no_rights": "😓 У меня нет прав. Сделайте меня админом с правами «блокировка» и «удаление сообщений».",
        "group_only": "👥 Команда работает только в группах.",
        "settings": "⚙️ <b>НАСТРОЙКИ ГРУППЫ</b>\n\nНажмите, чтобы включить / выключить 👇",
        "s_captcha": "🤖 Капча", "s_welcome": "👋 Приветствие", "s_antilink": "🔗 Антиреклама",
        "s_antiflood": "🌊 Антифлуд", "s_limit": "⚠️ Лимит предупреждений: {n}",
        "s_action": "🟥 После лимита: {a}", "a_mute": "🤐 Мут на 1 день", "a_ban": "🚀 Бан", "s_saved": "✅ Сохранено",
        "units": {"m": "мин", "h": "ч", "d": "дн"},
    },
    "kz": {
        "welcome": ["🎉 Назар аударыңыз! Топқа {name} келді! Шай қойыңыздар ☕",
                    "🚪 Есік ашылды да… {name} кірді! Қол шапалақ 👏👏👏"],
        "captcha": "🤖 {name}, алдымен дәлелде — адамсың ба, робот па?\n\n👇 <b>{emoji} {thing}</b> бас! ({sec} с)",
        "cap_ok": "✅ Құттықтаймыз, {name} — 100% адам! 🧬 Енді жаза аласыз.",
        "cap_wrong": "🤖 Бип-буп! {name} робот болып шықты. Зауытқа қайтарылды 🏭",
        "cap_timeout": "⌛ {name} ойлана-ойлана ұйықтап қалды 😴 — топтан шығарылды.",
        "cap_not_you": "✋ Бұл батырма саған емес — сен онсыз да адамсың 😄",
        "link": ["🧹 {name}, жарнама сыпырылып тасталды! Бұл базар емес 😅"],
        "flood": ["🐢 {name}, ақырынырақ! Пернетақтаң өртеніп кетті 🔥 — {dur} демал."],
        "warn": "⚠️ {name} сары карточка алды! ({n}/{limit})", "warn_reason": "\n📝 Себебі: {reason}",
        "warn_mute": "🟥 Қызыл карточка! {name} {limit}/{limit} — {dur} аузына скотч жапсырылды 🤐",
        "warn_ban": "🟥 Қызыл карточка! {name} алаңнан біржола шығарылды 🚀",
        "unwarn": "🧽 {name} бір ескертуден босатылды ({n}/{limit}).", "warns": "📋 {name}: {n}/{limit} ескерту.",
        "mute": ["🤐 {name} аузына {dur} скотч жапсырылды."],
        "unmute": "🗣 {name} қайта сөйлей алады! Скотч алынды 🎉",
        "ban": ["🚀 {name} ғарышқа ұшырылды! Сау бол 👋"],
        "unban": "🕊 {name} рақымшылық алды — қайта кіре алады.",
        "kick": "🦶 {name} топтан шығарылды! (қайта кіре алады)",
        "need_target": "↩️ Біреудің хабарына жауап беріп жазыңыз немесе ID / @username көрсетіңіз.",
        "not_admin": "⛔ Тек әкімшілер үшін. Жақсы әрекет 😏", "target_admin": "😅 Әкімшіге қарсы ма? Жоқ.",
        "target_bot": "🤖 Өзімді жазаламаймын — мен мұнда керекпін!",
        "no_rights": "😓 Менде құқық жоқ. Мені «бұғаттау» және «хабарды өшіру» құқығымен әкімші етіңіз.",
        "group_only": "👥 Бұл команда тек топта жұмыс істейді.",
        "settings": "⚙️ <b>ТОП БАПТАУЛАРЫ</b>\n\nҚосу / өшіру үшін басыңыз 👇",
        "s_captcha": "🤖 Капча", "s_welcome": "👋 Сәлемдесу", "s_antilink": "🔗 Антижарнама",
        "s_antiflood": "🌊 Антифлуд", "s_limit": "⚠️ Ескерту шегі: {n}",
        "s_action": "🟥 Шектен кейін: {a}", "a_mute": "🤐 1 күн үнсіз", "a_ban": "🚀 Бан", "s_saved": "✅ Сақталды",
        "units": {"m": "мин", "h": "сағ", "d": "күн"},
    },
}


def mod_lang(chat_id):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    return lang if lang in MOD_TEXT else "uz"


def mod_t(chat_id, key, **kwargs):
    text = MOD_TEXT[mod_lang(chat_id)].get(key) or MOD_TEXT["uz"][key]
    if isinstance(text, list):
        text = random.choice(text)
    return text.format(**kwargs) if kwargs else text


def user_mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{escape(str(name or user_id))}</a>'


def init_guard():
    c = db()
    with c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS group_settings (
                chat_id INTEGER PRIMARY KEY,
                captcha INTEGER NOT NULL DEFAULT 0,
                welcome INTEGER NOT NULL DEFAULT 1,
                antilink INTEGER NOT NULL DEFAULT 0,
                antiflood INTEGER NOT NULL DEFAULT 0,
                warn_limit INTEGER NOT NULL DEFAULT 3,
                warn_action TEXT NOT NULL DEFAULT 'mute'
            )
        """)
        if "welcome_text" not in {r[1] for r in c.execute("PRAGMA table_info(group_settings)")}:
            c.execute("ALTER TABLE group_settings ADD COLUMN welcome_text TEXT NOT NULL DEFAULT ''")
        c.execute("""
            CREATE TABLE IF NOT EXISTS group_warns (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)


def gs_get(chat_id):
    row = db().execute(
        f"SELECT {', '.join(GUARD_DEFAULTS)} FROM group_settings WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    return dict(zip(GUARD_DEFAULTS, row)) if row else dict(GUARD_DEFAULTS)


def gs_set(chat_id, key, value):
    if key not in GUARD_DEFAULTS:
        return
    c = db()
    with c:
        c.execute("INSERT OR IGNORE INTO group_settings(chat_id) VALUES (?)", (chat_id,))
        c.execute(f"UPDATE group_settings SET {key}=? WHERE chat_id=?", (value, chat_id))


async def admin_ids(bot, chat_id):
    cached = ADMIN_CACHE.get(chat_id)
    if cached and time.time() - cached[0] < ADMIN_CACHE_TTL:
        return cached[1]
    try:
        ids = {m.user.id for m in await bot.get_chat_administrators(chat_id)}
    except TelegramError:
        ids = cached[1] if cached else set()
    ADMIN_CACHE[chat_id] = (time.time(), ids)
    return ids


async def is_moderator(bot, msg, user):
    """Bot egalari, guruh adminlari va anonim admin."""
    if msg.sender_chat and msg.sender_chat.id == msg.chat_id:
        return True
    if not user or user.is_bot:
        return False
    return user.id in CAREER_OWNER_IDS or user.id in await admin_ids(bot, msg.chat_id)


async def chat_default_permissions(bot, chat_id):
    try:
        chat = await bot.get_chat(chat_id)
        if chat.permissions:
            return chat.permissions
    except TelegramError:
        pass
    return ChatPermissions(
        can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True,
        can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True,
        can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True,
    )


async def mod_mute(bot, chat_id, user_id, seconds):
    await bot.restrict_chat_member(
        chat_id, user_id, ChatPermissions(can_send_messages=False),
        until_date=int(time.time()) + seconds if seconds else None,
    )


async def mod_unmute(bot, chat_id, user_id):
    await bot.restrict_chat_member(chat_id, user_id, await chat_default_permissions(bot, chat_id))


async def mod_kick(bot, chat_id, user_id):
    await bot.ban_chat_member(chat_id, user_id, until_date=int(time.time()) + 60)
    await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)


def fmt_dur(chat_id, seconds):
    units = MOD_TEXT[mod_lang(chat_id)]["units"]
    if seconds % 86400 == 0:
        return f"{seconds // 86400} {units['d']}"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} {units['h']}"
    return f"{max(1, seconds // 60)} {units['m']}"


def parse_dur(text, default=3600):
    m = re.fullmatch(r"(\d{1,4})\s*([mhd]?)", (text or "").strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    mult = {"": 60, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    return max(60, min(n * mult, 366 * 86400)) if n else default


async def delete_later(bot, chat_id, message_id, delay):
    async def _job():
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id, message_id)
        except TelegramError:
            pass
    task = asyncio.create_task(_job())
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)


def has_link(msg):
    for ent in (msg.entities or ()) + (msg.caption_entities or ()):
        if ent.type in ("url", "text_link"):
            return True
    text = msg.text or msg.caption or ""
    if _LINK_RE.search(text):
        return True
    origin = getattr(msg, "forward_origin", None)
    return bool(origin and getattr(origin, "type", "") in ("channel", "chat"))


# ── Kirish: captcha va salomlashish ──

async def guard_new_members(context, msg):
    chat_id = msg.chat_id
    settings = gs_get(chat_id)
    for member in msg.new_chat_members:
        if member.is_bot:
            continue
        name = user_mention(member.id, member.first_name)
        if settings["captcha"]:
            try:
                await mod_mute(context.bot, chat_id, member.id, 0)
            except TelegramError:
                # Huquq yo'q — captcha'siz salomlashamiz.
                if settings["welcome"]:
                    await context.bot.send_message(chat_id, welcome_for(chat_id, name, msg.chat.title))
                continue
            options = random.sample(range(len(CAPTCHA_ITEMS)), 4)
            answer = random.choice(options)
            emoji, things = CAPTCHA_ITEMS[answer]
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(CAPTCHA_ITEMS[i][0], callback_data=f"cap:{member.id}:{i}") for i in options
            ]])
            sent = await context.bot.send_message(
                chat_id,
                mod_t(chat_id, "captcha", name=name, emoji=emoji,
                      thing=things.get(mod_lang(chat_id), things["uz"]), sec=CAPTCHA_TTL),
                reply_markup=kb,
            )
            key = (chat_id, member.id)
            old = CAPTCHA_PENDING.pop(key, None)
            if old and old.get("task"):
                old["task"].cancel()
            entry = {"answer": answer, "msg_id": sent.message_id, "name": name}
            entry["task"] = asyncio.create_task(captcha_timeout(context.bot, key, entry))
            BG_TASKS.add(entry["task"])
            entry["task"].add_done_callback(BG_TASKS.discard)
            CAPTCHA_PENDING[key] = entry
        elif settings["welcome"]:
            await context.bot.send_message(chat_id, welcome_for(chat_id, name, msg.chat.title))


async def captcha_timeout(bot, key, entry):
    try:
        await asyncio.sleep(CAPTCHA_TTL)
    except asyncio.CancelledError:
        return
    if CAPTCHA_PENDING.get(key) is not entry:
        return
    CAPTCHA_PENDING.pop(key, None)
    chat_id, user_id = key
    try:
        await mod_kick(bot, chat_id, user_id)
    except TelegramError:
        pass
    await edit(bot, chat_id, entry["msg_id"], mod_t(chat_id, "cap_timeout", name=entry["name"]))
    await mod_log(bot, chat_id, f"⌛ Captcha vaqti tugadi — {entry['name']} chiqarildi")
    await delete_later(bot, chat_id, entry["msg_id"], NOTICE_TTL)


async def cb_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, uid_text, choice = q.data.split(":")
    chat_id = q.message.chat.id
    user_id = int(uid_text)
    if q.from_user.id != user_id:
        await q.answer(mod_t(chat_id, "cap_not_you"), show_alert=True)
        return
    entry = CAPTCHA_PENDING.pop((chat_id, user_id), None)
    if not entry:
        await q.answer()
        return
    if entry.get("task"):
        entry["task"].cancel()
    await q.answer()
    if int(choice) == entry["answer"]:
        try:
            await mod_unmute(context.bot, chat_id, user_id)
        except TelegramError:
            pass
        text = mod_t(chat_id, "cap_ok", name=entry["name"])
        if gs_get(chat_id)["welcome"]:
            text += "\n\n" + welcome_for(chat_id, entry["name"], q.message.chat.title)
        await edit(context.bot, chat_id, entry["msg_id"], text)
    else:
        try:
            await mod_kick(context.bot, chat_id, user_id)
        except TelegramError:
            pass
        await edit(context.bot, chat_id, entry["msg_id"], mod_t(chat_id, "cap_wrong", name=entry["name"]))
        await mod_log(context.bot, chat_id, f"🤖 Captcha xato — {entry['name']} chiqarildi")
        await delete_later(context.bot, chat_id, entry["msg_id"], NOTICE_TTL)


# ── Har bir guruh xabari: anti-flood va anti-reklama ──

async def guard_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if msg.new_chat_members:
        try:
            await guard_new_members(context, msg)
        except TelegramError as e:
            logger.warning("Guruh himoyasi: yangi a'zo bilan ishlashda xato: %s", e)
        return
    user = msg.from_user
    if not user or user.is_bot or msg.sender_chat:
        return
    if (msg.text or "").strip().lower() in ("@admin", "@admins") and msg.reply_to_message:
        await do_report(context, msg, user)
        raise ApplicationHandlerStop
    settings = gs_get(msg.chat_id)
    if not (settings["antilink"] or settings["antiflood"] or settings["night_active"]
            or settings["locks"] or badwords(msg.chat_id)):
        return
    if user.id in CAREER_OWNER_IDS or user.id in await admin_ids(context.bot, msg.chat_id):
        return
    chat_id = msg.chat_id
    name = user_mention(user.id, user.first_name)

    if settings["night_active"]:
        # Guruhni yopib bo'lmagan bo'lsa ham tunda oddiy a'zolar xabari o'chiriladi.
        try:
            await msg.delete()
        except TelegramError:
            pass
        raise ApplicationHandlerStop

    if settings["antiflood"]:
        now = time.monotonic()
        stamps = [t for t in FLOOD_TRACK.get((chat_id, user.id), []) if now - t < FLOOD_WINDOW]
        stamps.append(now)
        FLOOD_TRACK[(chat_id, user.id)] = stamps
        if len(stamps) >= FLOOD_COUNT:
            FLOOD_TRACK.pop((chat_id, user.id), None)
            try:
                await mod_mute(context.bot, chat_id, user.id, FLOOD_MUTE)
                sent = await context.bot.send_message(
                    chat_id, mod_t(chat_id, "flood", name=name, dur=fmt_dur(chat_id, FLOOD_MUTE))
                )
                await delete_later(context.bot, chat_id, sent.message_id, NOTICE_TTL * 3)
                await mod_log(context.bot, chat_id, f"🌊 Flood — {name} {fmt_dur(chat_id, FLOOD_MUTE)} jim")
            except TelegramError as e:
                logger.warning("Anti-flood: jim qilib bo'lmadi: %s", e)
            raise ApplicationHandlerStop

    if settings["antilink"] and has_link(msg):
        try:
            await msg.delete()
        except TelegramError as e:
            logger.warning("Anti-reklama: o'chirib bo'lmadi: %s", e)
            return
        sent = await context.bot.send_message(chat_id, mod_t(chat_id, "link", name=name))
        await delete_later(context.bot, chat_id, sent.message_id, NOTICE_TTL)
        await mod_log(context.bot, chat_id, f"🔗 Reklama o‘chirildi — {name}")
        raise ApplicationHandlerStop

    kind = lock_kind(msg)
    if kind and settings["locks"] & (1 << LOCK_TYPES.index(kind)):
        try:
            await msg.delete()
        except TelegramError:
            return
        sent = await context.bot.send_message(chat_id, g2_word(chat_id, "locked", kind).format(name=name))
        await delete_later(context.bot, chat_id, sent.message_id, NOTICE_TTL // 2)
        raise ApplicationHandlerStop

    word = find_badword(chat_id, msg.text or msg.caption)
    if word:
        try:
            await msg.delete()
        except TelegramError:
            return
        # Empire Security uslubi: xabarni o'chirib, a'zoni (sozlangan muddatga) jim qilamiz va
        # «✅ Bekor qilish» tugmasi bilan muddatni ko'rsatamiz. Muddat guruh bo'yicha sozlanadi (/badmute).
        dur = settings.get("badword_mute") or BADWORD_MUTE
        until = int(time.time()) + dur
        muted = False
        try:
            await mod_mute(context.bot, chat_id, user.id, dur)
            muted = True
        except TelegramError as e:
            logger.warning("Taqiqlangan so'z: jim qilib bo'lmadi: %s", e)
        if muted:
            await context.bot.send_message(
                chat_id,
                g2_t(chat_id, "bw_mute", name=name, id=user.id, until=tashkent_dt(until)),
                reply_markup=undo_kb(chat_id, "mute", user.id),
            )
        else:
            sent = await context.bot.send_message(chat_id, g2_t(chat_id, "badword", name=name))
            await delete_later(context.bot, chat_id, sent.message_id, NOTICE_TTL)
        await mod_log(context.bot, chat_id,
                      f"🧼 Taqiqlangan so‘z «{escape(word)}» — {name}"
                      + (f" · 🔇 {tashkent_dt(until)} gacha" if muted else ""))
        raise ApplicationHandlerStop


# ── Moderatsiya buyruqlari ──

async def mod_target(update, context):
    """(user_id, ism, qolgan argumentlar) — reply yoki ID / @username orqali."""
    msg = update.effective_message
    args = list(context.args or [])
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return u.id, user_mention(u.id, u.first_name), u.is_bot, args
    if args:
        raw = args.pop(0)
        c = db()
        if raw.startswith("@"):
            row = c.execute(
                "SELECT user_id, first_name FROM users WHERE lower(username)=lower(?)", (raw[1:],)
            ).fetchone()
        elif raw.lstrip("-").isdigit():
            row = c.execute("SELECT user_id, first_name FROM users WHERE user_id=?", (int(raw),)).fetchone() \
                or (int(raw), raw)
        else:
            row = None
        if row:
            return row[0], user_mention(row[0], row[1]), False, args
    return None, None, False, args


async def cmd_mod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id, "group_only"))
        return
    command = msg.text.split()[0].lstrip("/.!").split("@")[0].lower()
    if not await is_moderator(context.bot, msg, user):
        await msg.reply_text(mod_t(chat.id, "not_admin"))
        return
    target, name, target_is_bot, args = await mod_target(update, context)
    if not target:
        await msg.reply_text(mod_t(chat.id, "need_target"))
        return
    if target == context.bot.id:
        await msg.reply_text(mod_t(chat.id, "target_bot"))
        return
    if command not in ("warns", "unwarn", "unmute", "unban") and (
        target in CAREER_OWNER_IDS or target in await admin_ids(context.bot, chat.id)
    ):
        await msg.reply_text(mod_t(chat.id, "target_admin"))
        return

    settings = gs_get(chat.id)
    limit = settings["warn_limit"]
    undo_act = None   # "mute" / "ban" bo'lsa — xabar tagiga «Bekor qilish» tugmasi qo'yiladi
    c = db()
    try:
        if command in ("warn", "unwarn", "warns"):
            row = c.execute("SELECT count FROM group_warns WHERE chat_id=? AND user_id=?", (chat.id, target)).fetchone()
            count = row[0] if row else 0
            if command == "warns":
                await msg.reply_text(mod_t(chat.id, "warns", name=name, n=count, limit=limit))
                return
            count = count + 1 if command == "warn" else max(0, count - 1)
            if command == "warn" and count >= limit:
                count = 0
                if settings["warn_action"] == "ban":
                    await context.bot.ban_chat_member(chat.id, target)
                    text = mod_t(chat.id, "warn_ban", name=name)
                    undo_act = "ban"
                else:
                    await mod_mute(context.bot, chat.id, target, WARN_MUTE)
                    text = mod_t(chat.id, "warn_mute", name=name, limit=limit, dur=fmt_dur(chat.id, WARN_MUTE))
                    undo_act = "mute"
            elif command == "warn":
                text = mod_t(chat.id, "warn", name=name, n=count, limit=limit)
                reason = " ".join(args).strip()
                if reason:
                    text += mod_t(chat.id, "warn_reason", reason=escape(reason[:200]))
            else:
                text = mod_t(chat.id, "unwarn", name=name, n=count, limit=limit)
            with c:
                c.execute(
                    """INSERT INTO group_warns(chat_id, user_id, count) VALUES (?, ?, ?)
                       ON CONFLICT(chat_id, user_id) DO UPDATE SET count=excluded.count""",
                    (chat.id, target, count),
                )
        elif command in ("mute", "tmute"):
            seconds = parse_dur(args[0]) if args else 3600
            seconds = seconds or 3600
            await mod_mute(context.bot, chat.id, target, seconds)
            text = mod_t(chat.id, "mute", name=name, dur=fmt_dur(chat.id, seconds))
            undo_act = "mute"
        elif command == "unmute":
            await mod_unmute(context.bot, chat.id, target)
            text = mod_t(chat.id, "unmute", name=name)
        elif command == "tban":
            seconds = parse_dur(args[0]) if args else 3600
            seconds = seconds or 3600
            await context.bot.ban_chat_member(chat.id, target, until_date=int(time.time()) + seconds)
            text = mod_t(chat.id, "tban", name=name, dur=fmt_dur(chat.id, seconds))
            undo_act = "ban"
        elif command == "ban":
            await context.bot.ban_chat_member(chat.id, target)
            text = mod_t(chat.id, "ban", name=name)
            undo_act = "ban"
        elif command == "unban":
            await context.bot.unban_chat_member(chat.id, target, only_if_banned=True)
            text = mod_t(chat.id, "unban", name=name)
        elif command == "kick":
            await mod_kick(context.bot, chat.id, target)
            text = mod_t(chat.id, "kick", name=name)
        else:
            return
    except TelegramError as e:
        logger.warning("Moderatsiya /%s bajarilmadi: %s", command, e)
        await msg.reply_text(mod_t(chat.id, "no_rights"))
        return
    # Jazo (mute/ban) xabari tagida «Bekor qilish» tugmasi — faqat huquqli admin bosadi, xabar o'chmaydi.
    kb = undo_kb(chat.id, undo_act, target) if undo_act else None
    await msg.reply_text(text, reply_markup=kb)
    if command != "warns":
        await mod_log(context.bot, chat.id, f"⚖️ /{command} — {name} ← {user_mention(user.id, user.first_name) if user else 'admin'}"
                      + (f"\n📝 {escape(' '.join(args)[:200])}" if args else ""))


# ── /settings: bo'limli menyu (guruhda yoki shaxsiy chatda) va 👮 admin boshqaruvi ──
# /settings → "⚙️ Shu yerda ochish" (gs:<chat>:home) yoki "👤 Shaxsiy chatda ochish" (?start=gs_<|chat|>).
# Admin paneli: ga:<chat>:<uid>[:r<i>|:demote], /promote va /demote. Telegram qoidasi: bot faqat o'zi
# tayinlagan adminlarning huquqlarini o'zgartira oladi (can_be_edited).

ADMIN_RIGHTS = [
    "can_change_info", "can_delete_messages", "can_restrict_members", "can_invite_users",
    "can_pin_messages", "can_manage_video_chats", "can_promote_members",
]
PROMOTE_DEFAULTS = {
    "can_change_info": False, "can_delete_messages": True, "can_restrict_members": True,
    "can_invite_users": True, "can_pin_messages": True, "can_manage_video_chats": True,
    "can_promote_members": False,
}

SETTINGS_TEXT = {
    "uz": {
        "where": "⚙️ <b>Guruh sozlamalari</b>\n\nQayerda ochamiz? 👇",
        "b_here": "⚙️ Shu yerda ochish", "b_private": "👤 Shaxsiy chatda ochish",
        "home": "⚙️ <b>«{group}» SOZLAMALARI</b>\n\nBo‘limni tanlang 👇",
        "b_prot": "🛡 Himoya", "b_welc": "👋 Salomlashish", "b_warn": "⚠️ Ogohlantirishlar",
        "b_adm": "👮 Adminlar", "b_close": "❌ Yopish", "b_back": "⬅️ Orqaga",
        "prot": "🛡 <b>HIMOYA</b>\n\n🤖 Captcha — yangi a’zo emoji tanlab odamligini isbotlaydi\n🔗 Anti-reklama — link va kanal forwardlari o‘chiriladi\n🌊 Anti-flood — 5 soniyada 7 xabar yozgan 5 daqiqa jim bo‘ladi",
        "welc": "👋 <b>SALOMLASHISH</b>\n\nHozirgi matn:\n{text}",
        "welc_random": "🎲 Kulgili tasodifiy matnlar",
        "b_wtext": "✏️ O‘z matnimni yozish", "b_wreset": "🎲 Kulgili matnlarga qaytish",
        "wtext_prompt": "✏️ Yangi salomlashish matnini yuboring.\n\n<code>{name}</code> — yangi a’zo, <code>{group}</code> — guruh nomi.\nMasalan: <i>Salom {name}! {group} ga xush kelibsiz 🎉</i>",
        "wtext_private": "✏️ Matnni shaxsiy chatda o‘zgartiring: /settings → 👤 Shaxsiy chatda ochish",
        "wtext_bad": "❌ Matnda faqat {name} va {group} ishlatilishi mumkin. Qayta yuboring.",
        "wtext_ok": "✅ Saqlandi! Namuna:\n\n{sample}",
        "warn_menu": "⚠️ <b>OGOHLANTIRISHLAR</b>\n\n/warn — sariq kartochka. Limitga yetganda — qizil kartochka.",
        "adm": "👮 <b>ADMINLAR</b>\n\nAdminni tanlang — huquqlarini ko‘rish va sozlash uchun.\n➕ Yangi admin: guruhda kimningdir xabariga reply qilib <b>/promote</b> yozing.",
        "adm_panel": "👮 <b>{name}</b> — admin huquqlari\n\n{note}",
        "adm_owner": "👑 Guruh egasi — huquqlari cheklanmagan.",
        "adm_locked": "ℹ️ Bu adminni men tayinlamaganman — Telegram qoidasiga ko‘ra uning huquqlarini faqat uni tayinlagan odam o‘zgartira oladi.",
        "adm_editable": "Tugmani bosib huquqni yoqing / o‘chiring 👇",
        "adm_not": "ℹ️ Bu foydalanuvchi hozir admin emas.",
        "b_demote": "⬇️ Adminlikdan olish", "b_admins": "⬅️ Adminlar",
        "rights": {
            "can_change_info": "ℹ️ Guruh ma’lumotlari", "can_delete_messages": "🗑 Xabarlarni o‘chirish",
            "can_restrict_members": "🚫 Bloklash / jim qilish", "can_invite_users": "🔗 Odam qo‘shish",
            "can_pin_messages": "📌 Xabar qadash", "can_manage_video_chats": "🎥 Videochat",
            "can_promote_members": "👮 Admin tayinlash",
        },
        "promoted": "🎖 {name} endi admin! Tabriklaymiz 🎉\nHuquqlarini sozlash 👇",
        "promoted_ext": "🎖 {name} yangi admin bo‘ldi! Huquqlarini ko‘rish / sozlash 👇",
        "demoted": "🧢 {name} adminlikdan olindi — endi oddiy fuqaro.",
        "b_rights": "⚙️ Huquqlarni sozlash",
        "no_promote": "😓 Bajara olmadim. Menga «adminlarni tayinlash» huquqini bering (o‘zimda yo‘q huquqni boshqaga ham bera olmayman).",
        "need_promoter": "⛔ Buning uchun guruh egasi yoki «admin tayinlash» huquqi bor admin bo‘lish kerak.",
        "not_admin_of": "⛔ Siz bu guruhda admin emassiz.",
        "closed": "✅ Sozlamalar yopildi.",
        "use_in_group": "👥 Guruhda /settings yozing — keyin shu yerda ochish tugmasi chiqadi.",
    },
    "eng": {
        "where": "⚙️ <b>Group settings</b>\n\nWhere should I open them? 👇",
        "b_here": "⚙️ Open here", "b_private": "👤 Open in private chat",
        "home": "⚙️ <b>«{group}» SETTINGS</b>\n\nChoose a section 👇",
        "b_prot": "🛡 Protection", "b_welc": "👋 Welcome", "b_warn": "⚠️ Warnings",
        "b_adm": "👮 Admins", "b_close": "❌ Close", "b_back": "⬅️ Back",
        "prot": "🛡 <b>PROTECTION</b>\n\n🤖 Captcha — new members prove they're human\n🔗 Anti-ads — links and channel forwards are deleted\n🌊 Anti-flood — 7 messages in 5 s means 5 minutes of silence",
        "welc": "👋 <b>WELCOME</b>\n\nCurrent text:\n{text}", "welc_random": "🎲 Random funny texts",
        "b_wtext": "✏️ Write my own text", "b_wreset": "🎲 Back to funny texts",
        "wtext_prompt": "✏️ Send the new welcome text.\n\n<code>{name}</code> — new member, <code>{group}</code> — group name.",
        "wtext_private": "✏️ Change the text in private chat: /settings → 👤 Open in private chat",
        "wtext_bad": "❌ Only {name} and {group} can be used. Send it again.",
        "wtext_ok": "✅ Saved! Preview:\n\n{sample}",
        "warn_menu": "⚠️ <b>WARNINGS</b>\n\n/warn — yellow card. At the limit — red card.",
        "adm": "👮 <b>ADMINS</b>\n\nPick an admin to view and edit rights.\n➕ New admin: reply to someone in the group with <b>/promote</b>.",
        "adm_panel": "👮 <b>{name}</b> — admin rights\n\n{note}",
        "adm_owner": "👑 Group owner — unlimited rights.",
        "adm_locked": "ℹ️ I didn't promote this admin — by Telegram rules only whoever promoted them can change their rights.",
        "adm_editable": "Tap to turn a right on / off 👇", "adm_not": "ℹ️ This user is not an admin now.",
        "b_demote": "⬇️ Remove admin", "b_admins": "⬅️ Admins",
        "rights": {
            "can_change_info": "ℹ️ Group info", "can_delete_messages": "🗑 Delete messages",
            "can_restrict_members": "🚫 Ban / mute", "can_invite_users": "🔗 Add members",
            "can_pin_messages": "📌 Pin messages", "can_manage_video_chats": "🎥 Video chats",
            "can_promote_members": "👮 Add admins",
        },
        "promoted": "🎖 {name} is now an admin! Congrats 🎉\nSet up their rights 👇",
        "promoted_ext": "🎖 {name} became an admin! View / set rights 👇",
        "demoted": "🧢 {name} is no longer an admin.", "b_rights": "⚙️ Set rights",
        "no_promote": "😓 I couldn't do it. Give me the «add admins» right (I can't grant rights I don't have).",
        "need_promoter": "⛔ You must be the owner or an admin with the «add admins» right.",
        "not_admin_of": "⛔ You are not an admin of this group.", "closed": "✅ Settings closed.",
        "use_in_group": "👥 Type /settings in the group — then use the private-chat button.",
    },
    "ru": {
        "where": "⚙️ <b>Настройки группы</b>\n\nГде открыть? 👇",
        "b_here": "⚙️ Открыть здесь", "b_private": "👤 Открыть в личке",
        "home": "⚙️ <b>НАСТРОЙКИ «{group}»</b>\n\nВыберите раздел 👇",
        "b_prot": "🛡 Защита", "b_welc": "👋 Приветствие", "b_warn": "⚠️ Предупреждения",
        "b_adm": "👮 Админы", "b_close": "❌ Закрыть", "b_back": "⬅️ Назад",
        "prot": "🛡 <b>ЗАЩИТА</b>\n\n🤖 Капча — новичок доказывает, что он человек\n🔗 Антиреклама — ссылки и пересылки из каналов удаляются\n🌊 Антифлуд — 7 сообщений за 5 с = 5 минут тишины",
        "welc": "👋 <b>ПРИВЕТСТВИЕ</b>\n\nТекущий текст:\n{text}", "welc_random": "🎲 Случайные смешные тексты",
        "b_wtext": "✏️ Свой текст", "b_wreset": "🎲 Вернуть смешные тексты",
        "wtext_prompt": "✏️ Отправьте новый текст приветствия.\n\n<code>{name}</code> — новичок, <code>{group}</code> — название группы.",
        "wtext_private": "✏️ Текст меняется в личке: /settings → 👤 Открыть в личке",
        "wtext_bad": "❌ Можно использовать только {name} и {group}. Отправьте ещё раз.",
        "wtext_ok": "✅ Сохранено! Пример:\n\n{sample}",
        "warn_menu": "⚠️ <b>ПРЕДУПРЕЖДЕНИЯ</b>\n\n/warn — жёлтая карточка. На лимите — красная.",
        "adm": "👮 <b>АДМИНЫ</b>\n\nВыберите админа, чтобы посмотреть и изменить права.\n➕ Новый админ: ответьте на сообщение в группе командой <b>/promote</b>.",
        "adm_panel": "👮 <b>{name}</b> — права админа\n\n{note}",
        "adm_owner": "👑 Владелец группы — права не ограничены.",
        "adm_locked": "ℹ️ Этого админа назначил не я — по правилам Telegram менять его права может только тот, кто назначил.",
        "adm_editable": "Нажмите, чтобы включить / выключить право 👇", "adm_not": "ℹ️ Сейчас этот пользователь не админ.",
        "b_demote": "⬇️ Снять админку", "b_admins": "⬅️ Админы",
        "rights": {
            "can_change_info": "ℹ️ Инфо группы", "can_delete_messages": "🗑 Удаление сообщений",
            "can_restrict_members": "🚫 Бан / мут", "can_invite_users": "🔗 Приглашение",
            "can_pin_messages": "📌 Закрепление", "can_manage_video_chats": "🎥 Видеочаты",
            "can_promote_members": "👮 Назначение админов",
        },
        "promoted": "🎖 {name} теперь админ! Поздравляем 🎉\nНастройте права 👇",
        "promoted_ext": "🎖 {name} стал(а) админом! Посмотреть / настроить права 👇",
        "demoted": "🧢 {name} больше не админ.", "b_rights": "⚙️ Настроить права",
        "no_promote": "😓 Не получилось. Дайте мне право «назначать админов» (права, которых нет у меня, выдать не могу).",
        "need_promoter": "⛔ Нужно быть владельцем или админом с правом «назначать админов».",
        "not_admin_of": "⛔ Вы не админ этой группы.", "closed": "✅ Настройки закрыты.",
        "use_in_group": "👥 Напишите /settings в группе — там будет кнопка для лички.",
    },
    "kz": {
        "where": "⚙️ <b>Топ баптаулары</b>\n\nҚайда ашамыз? 👇",
        "b_here": "⚙️ Осы жерде ашу", "b_private": "👤 Жеке чатта ашу",
        "home": "⚙️ <b>«{group}» БАПТАУЛАРЫ</b>\n\nБөлімді таңдаңыз 👇",
        "b_prot": "🛡 Қорғау", "b_welc": "👋 Сәлемдесу", "b_warn": "⚠️ Ескертулер",
        "b_adm": "👮 Әкімшілер", "b_close": "❌ Жабу", "b_back": "⬅️ Артқа",
        "prot": "🛡 <b>ҚОРҒАУ</b>\n\n🤖 Капча — жаңа мүше адам екенін дәлелдейді\n🔗 Антижарнама — сілтемелер мен арна форвардтары өшіріледі\n🌊 Антифлуд — 5 с ішінде 7 хабар = 5 минут үнсіздік",
        "welc": "👋 <b>СӘЛЕМДЕСУ</b>\n\nҚазіргі мәтін:\n{text}", "welc_random": "🎲 Кездейсоқ күлкілі мәтіндер",
        "b_wtext": "✏️ Өз мәтінім", "b_wreset": "🎲 Күлкілі мәтіндерге қайту",
        "wtext_prompt": "✏️ Жаңа сәлемдесу мәтінін жіберіңіз.\n\n<code>{name}</code> — жаңа мүше, <code>{group}</code> — топ атауы.",
        "wtext_private": "✏️ Мәтінді жеке чатта өзгертіңіз: /settings → 👤 Жеке чатта ашу",
        "wtext_bad": "❌ Тек {name} және {group} қолдануға болады. Қайта жіберіңіз.",
        "wtext_ok": "✅ Сақталды! Үлгі:\n\n{sample}",
        "warn_menu": "⚠️ <b>ЕСКЕРТУЛЕР</b>\n\n/warn — сары карточка. Шекке жеткенде — қызыл.",
        "adm": "👮 <b>ӘКІМШІЛЕР</b>\n\nҚұқықтарын көру және баптау үшін әкімшіні таңдаңыз.\n➕ Жаңа әкімші: топта біреудің хабарына <b>/promote</b> деп жауап беріңіз.",
        "adm_panel": "👮 <b>{name}</b> — әкімші құқықтары\n\n{note}",
        "adm_owner": "👑 Топ иесі — құқықтары шектелмеген.",
        "adm_locked": "ℹ️ Бұл әкімшіні мен тағайындаған жоқпын — Telegram ережесі бойынша оның құқықтарын тек тағайындаған адам өзгерте алады.",
        "adm_editable": "Құқықты қосу / өшіру үшін басыңыз 👇", "adm_not": "ℹ️ Бұл қолданушы қазір әкімші емес.",
        "b_demote": "⬇️ Әкімшіліктен алу", "b_admins": "⬅️ Әкімшілер",
        "rights": {
            "can_change_info": "ℹ️ Топ ақпараты", "can_delete_messages": "🗑 Хабар өшіру",
            "can_restrict_members": "🚫 Бұғаттау / үнсіз ету", "can_invite_users": "🔗 Адам қосу",
            "can_pin_messages": "📌 Бекіту", "can_manage_video_chats": "🎥 Бейнечат",
            "can_promote_members": "👮 Әкімші тағайындау",
        },
        "promoted": "🎖 {name} енді әкімші! Құттықтаймыз 🎉\nҚұқықтарын баптау 👇",
        "promoted_ext": "🎖 {name} жаңа әкімші болды! Құқықтарын көру / баптау 👇",
        "demoted": "🧢 {name} әкімшіліктен алынды.", "b_rights": "⚙️ Құқықтарды баптау",
        "no_promote": "😓 Орындай алмадым. Маған «әкімші тағайындау» құқығын беріңіз.",
        "need_promoter": "⛔ Ол үшін топ иесі немесе «әкімші тағайындау» құқығы бар әкімші болу керек.",
        "not_admin_of": "⛔ Сіз бұл топтың әкімшісі емессіз.", "closed": "✅ Баптаулар жабылды.",
        "use_in_group": "👥 Топта /settings жазыңыз — сонда жеке чатқа өту батырмасы шығады.",
    },
}


def st_t(chat_id, key, **kwargs):
    text = SETTINGS_TEXT[mod_lang(chat_id)].get(key) or SETTINGS_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def welcome_for(chat_id, name, group):
    custom = gs_get(chat_id)["welcome_text"]
    if custom:
        try:
            return custom.format(name=name, group=escape(group or ""))
        except (KeyError, IndexError, ValueError):
            pass
    return mod_t(chat_id, "welcome", name=name)


async def chat_title(bot, chat_id):
    try:
        return (await bot.get_chat(chat_id)).title or str(chat_id)
    except TelegramError:
        return str(chat_id)


def gs_btn(chat_id, label, key):
    return InlineKeyboardButton(label, callback_data=f"gs:{chat_id}:{key}")


def gs_private_url(context, chat_id):
    return family_url(context, f"gs_{abs(chat_id)}")


async def settings_page(bot, chat_id, page):
    s = gs_get(chat_id)
    on = lambda v: "✅" if v else "❌"
    back = [gs_btn(chat_id, st_t(chat_id, "b_back"), "home")]
    if page == "prot":
        rows = [
            [gs_btn(chat_id, f"{mod_t(chat_id, 's_captcha')} {on(s['captcha'])}", "captcha")],
            [gs_btn(chat_id, f"{mod_t(chat_id, 's_antilink')} {on(s['antilink'])}", "antilink")],
            [gs_btn(chat_id, f"{mod_t(chat_id, 's_antiflood')} {on(s['antiflood'])}", "antiflood")],
            back,
        ]
        return st_t(chat_id, "prot"), InlineKeyboardMarkup(rows)
    if page == "welc":
        current = escape(s["welcome_text"]) if s["welcome_text"] else st_t(chat_id, "welc_random")
        rows = [
            [gs_btn(chat_id, f"{mod_t(chat_id, 's_welcome')} {on(s['welcome'])}", "welcome")],
            [gs_btn(chat_id, st_t(chat_id, "b_wtext"), "wtext")],
        ]
        if s["welcome_text"]:
            rows.append([gs_btn(chat_id, st_t(chat_id, "b_wreset"), "wreset")])
        rows.append(back)
        return st_t(chat_id, "welc", text=f"<i>{current}</i>"), InlineKeyboardMarkup(rows)
    if page == "warn":
        rows = [
            [gs_btn(chat_id, mod_t(chat_id, "s_limit", n=s["warn_limit"]), "warn_limit")],
            [gs_btn(chat_id, mod_t(chat_id, "s_action", a=mod_t(chat_id, "a_ban" if s["warn_action"] == "ban" else "a_mute")),
                    "warn_action")],
            back,
        ]
        return st_t(chat_id, "warn_menu"), InlineKeyboardMarkup(rows)
    if page == "adm":
        rows = []
        try:
            admins = await bot.get_chat_administrators(chat_id)
        except TelegramError:
            admins = []
        for m in admins:
            if m.user.is_bot:
                continue
            icon = "👑" if m.status == ChatMemberStatus.OWNER else "👮"
            rows.append([InlineKeyboardButton(f"{icon} {m.user.first_name}", callback_data=f"ga:{chat_id}:{m.user.id}")])
        rows.append(back)
        return st_t(chat_id, "adm"), InlineKeyboardMarkup(rows)
    if page == "words":
        words = badwords(chat_id)
        listing = ", ".join(f"<code>{escape(w)}</code>" for w in words[:60]) if words else g2_t(chat_id, "words_none")
        if len(words) > 60:
            listing += f" … +{len(words) - 60}"
        rows = [[gs_btn(chat_id, g2_t(chat_id, "b_wadd"), "wadd")]]
        if words:
            rows.append([gs_btn(chat_id, g2_t(chat_id, "b_wclear"), "wclear")])
        rows.append(back)
        return g2_t(chat_id, "words", list=listing), InlineKeyboardMarkup(rows)
    if page == "locks":
        rows = [
            [gs_btn(chat_id, f"{g2_word(chat_id, 'lock_names', kind)} {'❌' if s['locks'] & (1 << i) else '✅'}", f"lk{i}")]
            for i, kind in enumerate(LOCK_TYPES)
        ]
        rows.append(back)
        return g2_t(chat_id, "locks"), InlineKeyboardMarkup(rows)
    if page == "night":
        state = g2_t(chat_id, "night_on" if s["night"] else "night_off")
        if s["night_active"]:
            state += g2_t(chat_id, "night_now")
        rows = [
            [gs_btn(chat_id, g2_t(chat_id, "b_night_toggle", on=on(s["night"])), "nt")],
            [gs_btn(chat_id, g2_t(chat_id, "b_ns", h=f"{s['night_start']:02d}"), "ns"),
             gs_btn(chat_id, g2_t(chat_id, "b_ne", h=f"{s['night_end']:02d}"), "ne")],
            back,
        ]
        return (g2_t(chat_id, "night", state=state, start=f"{s['night_start']:02d}", end=f"{s['night_end']:02d}"),
                InlineKeyboardMarkup(rows))
    if page == "log":
        current = g2_t(chat_id, "log_none")
        if s["log_chat"]:
            current = f"✅ {escape(await chat_title(bot, s['log_chat']))} (<code>{s['log_chat']}</code>)"
        return g2_t(chat_id, "log", current=current), InlineKeyboardMarkup([back])
    # home
    rows = [
        [gs_btn(chat_id, st_t(chat_id, "b_prot"), "prot"), gs_btn(chat_id, st_t(chat_id, "b_welc"), "welc")],
        [gs_btn(chat_id, st_t(chat_id, "b_warn"), "warn"), gs_btn(chat_id, st_t(chat_id, "b_adm"), "adm")],
        [gs_btn(chat_id, g2_t(chat_id, "b_words"), "words"), gs_btn(chat_id, g2_t(chat_id, "b_locks"), "locks")],
        [gs_btn(chat_id, g2_t(chat_id, "b_night"), "night"), gs_btn(chat_id, g2_t(chat_id, "b_log"), "log")],
        [gs_btn(chat_id, st_t(chat_id, "b_close"), "close")],
    ]
    return st_t(chat_id, "home", group=escape(await chat_title(bot, chat_id))), InlineKeyboardMarkup(rows)


async def user_is_chat_admin(bot, chat_id, user_id):
    if user_id in CAREER_OWNER_IDS:
        return True
    return user_id in await admin_ids(bot, chat_id)


async def can_manage_admins(bot, chat_id, user_id):
    if user_id in CAREER_OWNER_IDS:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        return False
    return m.status == ChatMemberStatus.OWNER or (
        m.status == ChatMemberStatus.ADMINISTRATOR and getattr(m, "can_promote_members", False)
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(st_t(chat.id, "use_in_group"))
        return
    if not await is_moderator(context.bot, msg, update.effective_user):
        await msg.reply_text(mod_t(chat.id, "not_admin"))
        return
    kb = InlineKeyboardMarkup([
        [gs_btn(chat.id, st_t(chat.id, "b_here"), "home")],
        [InlineKeyboardButton(st_t(chat.id, "b_private"), url=gs_private_url(context, chat.id))],
    ])
    await msg.reply_text(st_t(chat.id, "where"), reply_markup=kb)


async def cb_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, chat_text, key = q.data.split(":")
    chat_id = int(chat_text)
    user = q.from_user
    if not await user_is_chat_admin(context.bot, chat_id, user.id):
        await q.answer(st_t(chat_id, "not_admin_of"), show_alert=True)
        return
    here = q.message.chat
    s = gs_get(chat_id)
    page = "home"
    if key in ("home", "prot", "welc", "warn", "adm", "words", "locks", "night", "log"):
        page = key
    elif key.startswith("lk") and key[2:].isdigit() and int(key[2:]) < len(LOCK_TYPES):
        gs_set(chat_id, "locks", s["locks"] ^ (1 << int(key[2:])))
        page = "locks"
    elif key == "nt":
        gs_set(chat_id, "night", 0 if s["night"] else 1)
        if s["night"] and s["night_active"]:
            await night_open(context.bot, chat_id)   # o'chirilganda guruh darhol ochiladi
        page = "night"
    elif key in ("ns", "ne"):
        col = "night_start" if key == "ns" else "night_end"
        gs_set(chat_id, col, (s[col] + 1) % 24)
        page = "night"
    elif key == "wclear":
        c = db()
        with c:
            c.execute("DELETE FROM group_badwords WHERE chat_id=?", (chat_id,))
        BADWORDS_CACHE.pop(chat_id, None)
        page = "words"
    elif key == "wadd":
        if here.type != ChatType.PRIVATE:
            await q.answer(g2_t(chat_id, "wadd_private"), show_alert=True)
            return
        context.user_data.pop("gs_wait_welcome", None)
        context.user_data["gs_wait_words"] = chat_id
        await q.answer()
        await edit(context.bot, here.id, q.message.message_id, g2_t(chat_id, "wadd_prompt"),
                   InlineKeyboardMarkup([[gs_btn(chat_id, st_t(chat_id, "b_back"), "words")]]))
        return
    elif key in ("captcha", "antilink", "antiflood"):
        gs_set(chat_id, key, 0 if s[key] else 1)
        page = "prot"
    elif key == "welcome":
        gs_set(chat_id, key, 0 if s[key] else 1)
        page = "welc"
    elif key == "wreset":
        gs_set(chat_id, "welcome_text", "")
        page = "welc"
    elif key == "wtext":
        if here.type != ChatType.PRIVATE:
            await q.answer(st_t(chat_id, "wtext_private"), show_alert=True)
            return
        context.user_data.pop("gs_wait_words", None)
        context.user_data["gs_wait_welcome"] = chat_id
        await q.answer()
        await edit(context.bot, here.id, q.message.message_id, st_t(chat_id, "wtext_prompt"),
                   InlineKeyboardMarkup([[gs_btn(chat_id, st_t(chat_id, "b_back"), "welc")]]))
        return
    elif key == "warn_limit":
        gs_set(chat_id, key, s[key] % 5 + 1 if s[key] < 5 else 2)
        page = "warn"
    elif key == "warn_action":
        gs_set(chat_id, key, "ban" if s[key] == "mute" else "mute")
        page = "warn"
    elif key == "close":
        await q.answer()
        await edit(context.bot, here.id, q.message.message_id, st_t(chat_id, "closed"))
        return
    context.user_data.pop("gs_wait_welcome", None)
    context.user_data.pop("gs_wait_words", None)
    await q.answer()
    text, kb = await settings_page(context.bot, chat_id, page)
    await edit(context.bot, here.id, q.message.message_id, text, kb)


async def settings_private_text(update, context):
    """Shaxsiy chatda kutilayotgan salomlashish matni / taqiqlangan so'zlarni qabul qiladi. True — qayta ishlandi."""
    msg = update.effective_message
    user = update.effective_user
    words_chat = context.user_data.get("gs_wait_words")
    if words_chat:
        context.user_data.pop("gs_wait_words", None)
        if not await user_is_chat_admin(context.bot, words_chat, user.id):
            await msg.reply_text(st_t(words_chat, "not_admin_of"))
            return True
        added = badwords_add(words_chat, msg.text.split(","))
        await msg.reply_text(
            g2_t(words_chat, "wadd_ok", words=", ".join(f"<code>{escape(w)}</code>" for w in added) or "—"),
            reply_markup=InlineKeyboardMarkup([[gs_btn(words_chat, st_t(words_chat, "b_back"), "words")]]),
        )
        return True
    chat_id = context.user_data.get("gs_wait_welcome")
    if not chat_id:
        return False
    if not await user_is_chat_admin(context.bot, chat_id, user.id):
        context.user_data.pop("gs_wait_welcome", None)
        await msg.reply_text(st_t(chat_id, "not_admin_of"))
        return True
    text = escape(msg.text.strip())[:1000]
    try:
        sample = text.format(name=user_mention(user.id, user.first_name), group="Empire")
    except (KeyError, IndexError, ValueError):
        await msg.reply_text(st_t(chat_id, "wtext_bad"))
        return True
    gs_set(chat_id, "welcome_text", text)
    context.user_data.pop("gs_wait_welcome", None)
    await msg.reply_text(
        st_t(chat_id, "wtext_ok", sample=sample),
        reply_markup=InlineKeyboardMarkup([[gs_btn(chat_id, st_t(chat_id, "b_back"), "welc")]]),
    )
    return True


# ── 👮 Admin paneli ──

async def admin_panel(bot, chat_id, user_id):
    try:
        m = await bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        m = None
    name = user_mention(user_id, m.user.first_name if m else user_id)
    rows = []
    if m and m.status == ChatMemberStatus.OWNER:
        note = st_t(chat_id, "adm_owner")
    elif not m or m.status != ChatMemberStatus.ADMINISTRATOR:
        note = st_t(chat_id, "adm_not")
    else:
        editable = getattr(m, "can_be_edited", False)
        note = st_t(chat_id, "adm_editable" if editable else "adm_locked")
        labels = SETTINGS_TEXT[mod_lang(chat_id)]["rights"]
        for i, right in enumerate(ADMIN_RIGHTS):
            mark = "✅" if getattr(m, right, False) else "❌"
            data = f"ga:{chat_id}:{user_id}:r{i}" if editable else "noop"
            rows.append([InlineKeyboardButton(f"{mark} {labels[right]}", callback_data=data)])
        if editable:
            rows.append([InlineKeyboardButton(st_t(chat_id, "b_demote"), callback_data=f"ga:{chat_id}:{user_id}:demote")])
    rows.append([gs_btn(chat_id, st_t(chat_id, "b_admins"), "adm")])
    return st_t(chat_id, "adm_panel", name=name, note=note), InlineKeyboardMarkup(rows)


def admin_panel_buttons(context, chat_id, user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(st_t(chat_id, "b_rights"), callback_data=f"ga:{chat_id}:{user_id}")],
        [InlineKeyboardButton(st_t(chat_id, "b_private"), url=family_url(context, f"ga_{abs(chat_id)}_{user_id}"))],
    ])


async def set_admin_rights(bot, chat_id, user_id, rights):
    await bot.promote_chat_member(chat_id, user_id, can_manage_chat=any(rights.values()), **rights)
    ADMIN_CACHE.pop(chat_id, None)


async def cb_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    chat_id, user_id = int(parts[1]), int(parts[2])
    action = parts[3] if len(parts) > 3 else ""
    here = q.message.chat
    if not await can_manage_admins(context.bot, chat_id, q.from_user.id):
        await q.answer(st_t(chat_id, "need_promoter"), show_alert=True)
        return
    try:
        if action.startswith("r") and action[1:].isdigit() and int(action[1:]) < len(ADMIN_RIGHTS):
            m = await context.bot.get_chat_member(chat_id, user_id)
            rights = {r: bool(getattr(m, r, False)) for r in ADMIN_RIGHTS}
            right = ADMIN_RIGHTS[int(action[1:])]
            rights[right] = not rights[right]
            await set_admin_rights(context.bot, chat_id, user_id, rights)
        elif action == "demote":
            await set_admin_rights(context.bot, chat_id, user_id, {r: False for r in ADMIN_RIGHTS})
            await q.answer()
            name = user_mention(user_id, (await context.bot.get_chat_member(chat_id, user_id)).user.first_name)
            await edit(context.bot, here.id, q.message.message_id, st_t(chat_id, "demoted", name=name),
                       InlineKeyboardMarkup([[gs_btn(chat_id, st_t(chat_id, "b_admins"), "adm")]]))
            return
    except TelegramError as e:
        logger.warning("Admin paneli: huquq o'zgarmadi: %s", e)
        await q.answer(st_t(chat_id, "no_promote"), show_alert=True)
        return
    await q.answer()
    text, kb = await admin_panel(context.bot, chat_id, user_id)
    await edit(context.bot, here.id, q.message.message_id, text, kb)


async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id, "group_only"))
        return
    command = msg.text.split()[0].lstrip("/.!").split("@")[0].lower()
    if not user or not await can_manage_admins(context.bot, chat.id, user.id):
        await msg.reply_text(st_t(chat.id, "need_promoter"))
        return
    target, name, target_is_bot, args = await mod_target(update, context)
    if not target:
        await msg.reply_text(mod_t(chat.id, "need_target"))
        return
    if target == context.bot.id:
        await msg.reply_text(mod_t(chat.id, "target_bot"))
        return
    try:
        if command == "promote":
            await set_admin_rights(context.bot, chat.id, target, dict(PROMOTE_DEFAULTS))
            title = " ".join(args).strip()[:16]
            if title:
                try:
                    await context.bot.set_chat_administrator_custom_title(chat.id, target, title)
                except TelegramError:
                    pass
            await msg.reply_text(st_t(chat.id, "promoted", name=name),
                                 reply_markup=admin_panel_buttons(context, chat.id, target))
            await mod_log(context.bot, chat.id, f"🎖 Admin qilindi — {name} ← {user_mention(user.id, user.first_name)}")
        else:
            await set_admin_rights(context.bot, chat.id, target, {r: False for r in ADMIN_RIGHTS})
            await msg.reply_text(st_t(chat.id, "demoted", name=name))
            await mod_log(context.bot, chat.id, f"🧢 Adminlikdan olindi — {name} ← {user_mention(user.id, user.first_name)}")
    except TelegramError as e:
        logger.warning("/%s bajarilmadi: %s", command, e)
        await msg.reply_text(st_t(chat.id, "no_promote"))


async def announce_new_admin(context, event):
    """Kimdir Telegram orqali admin qilinsa — panelga o'tish tugmasini chiqaradi."""
    old, new = event.old_chat_member, event.new_chat_member
    ADMIN_CACHE.pop(event.chat.id, None)
    if new.status != ChatMemberStatus.ADMINISTRATOR or old.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return
    if new.user.is_bot or (event.from_user and event.from_user.id == context.bot.id):
        return   # /promote orqali — xabar allaqachon chiqqan
    chat_id = event.chat.id
    try:
        await context.bot.send_message(
            chat_id, st_t(chat_id, "promoted_ext", name=user_mention(new.user.id, new.user.first_name)),
            reply_markup=admin_panel_buttons(context, chat_id, new.user.id),
        )
    except TelegramError as e:
        logger.warning("Yangi admin e'loni yuborilmadi: %s", e)


async def settings_start_payload(update, context, payload):
    """?start=gs_<|chat|> yoki ga_<|chat|>_<uid> — shaxsiy chatda ochish. True — qayta ishlandi."""
    m = re.fullmatch(r"gs_(\d+)|ga_(\d+)_(\d+)", payload or "")
    if not m:
        return False
    msg = update.effective_message
    user = update.effective_user
    if m.group(1):
        chat_id = -int(m.group(1))
        if not await user_is_chat_admin(context.bot, chat_id, user.id):
            await msg.reply_text(st_t(chat_id, "not_admin_of"))
            return True
        text, kb = await settings_page(context.bot, chat_id, "home")
    else:
        chat_id, target = -int(m.group(2)), int(m.group(3))
        if not await can_manage_admins(context.bot, chat_id, user.id):
            await msg.reply_text(st_t(chat_id, "need_promoter"))
            return True
        text, kb = await admin_panel(context.bot, chat_id, target)
    await msg.reply_text(text, reply_markup=kb)
    return True



# ───────────────────────────── 🛡 2-bosqich: so'zlar, tungi rejim, /report, log, cheklovlar ─────────────────────────────

LOCK_TYPES = ["sticker", "animation", "voice", "video_note", "forward"]   # locks bitmaskasi tartibi
NIGHT_TICK = 60
REPORT_COOLDOWN = 60
BADWORDS_CACHE: dict[int, list] = {}
FILTERS_CACHE: dict[int, dict] = {}
REPORT_LAST: dict[tuple, float] = {}

G2_TEXT = {
    "uz": {
        "b_words": "🚫 So‘zlar", "b_locks": "🔒 Cheklovlar", "b_night": "🌙 Tungi rejim", "b_log": "📋 Log kanal",
        "words": "🚫 <b>TAQIQLANGAN SO‘ZLAR</b>\n\n{list}\n\nGuruhda: <code>/addword so‘z</code>, <code>/delword so‘z</code>, <code>/words</code>",
        "words_none": "Hali hech narsa yo‘q — guruh juda madaniyatli 😇",
        "b_wadd": "➕ So‘z qo‘shish", "b_wclear": "🗑 Hammasini o‘chirish",
        "wadd_prompt": "➕ Taqiqlanadigan so‘zlarni yuboring (vergul bilan ajrating).\nMasalan: <i>reklama, kazino, spam</i>",
        "wadd_private": "➕ So‘zlarni shaxsiy chatda qo‘shing yoki guruhda /addword so‘z yozing.",
        "wadd_ok": "✅ Qo‘shildi: {words}",
        "word_added": "🚫 «{word}» qora ro‘yxatga tushdi. Endi uni yozganlarning og‘zi sovun bilan yuviladi 🧼",
        "word_removed": "✅ «{word}» qora ro‘yxatdan chiqarildi — endi bemalol 😌",
        "word_missing": "🤷 «{word}» ro‘yxatda yo‘q.", "word_need": "✍️ So‘zni yozing: /addword so‘z",
        "badword": ["🧼 {name}, og‘zingni sovun bilan yuvdik! Bu so‘z taqiqlangan 🙊",
                    "🙊 {name}, voy-voy-voy! Bunday so‘zlar bizda ishlatilmaydi 🚫"],
        "bw_mute": "🚫 {name} [{id}] taqiqlangan so‘zdan foydalandi.\nHolati: <b>Mute holatida</b> 🔇\nMuddat: <b>{until}</b> gacha",
        "bw_undo": "✅ Bekor qilish",
        "undo_no_right": "⛔ Buni faqat «a’zolarni cheklash» huquqiga ega adminlar bosa oladi.",
        "undo_unmuted": "\n\n♻️ {admin} mute’ni bekor qildi — {name} yana yoza oladi.",
        "undo_unbanned": "\n\n♻️ {admin} ban’ni bekor qildi — {name} qaytib kira oladi.",
        "badmute_now": "🔇 Taqiqlangan so‘z uchun mute muddati: <b>{dur}</b>.\nO‘zgartirish: <code>/badmute 1h</code> (yoki 30m, 1d).",
        "badmute_set": "✅ Taqiqlangan so‘z mute muddati <b>{dur}</b> qilib belgilandi.",
        "locks": "🔒 <b>CHEKLOVLAR</b>\n\n❌ — shu turdagi xabarlar oddiy a’zolardan o‘chiriladi.",
        "lock_names": {"sticker": "🎭 Stikerlar", "animation": "🎞 GIF", "voice": "🎤 Ovozli xabar",
                       "video_note": "⭕ Dumaloq video", "forward": "↪️ Forward"},
        "locked": {"sticker": "🎭 {name}, stikerlar bugun ta’tilda 🏖",
                   "animation": "🎞 {name}, GIF’lar dam olyapti 😴",
                   "voice": "🎤 {name}, ovozli xabar taqiqlangan — yozib yuboring ✍️",
                   "video_note": "⭕ {name}, dumaloq videolar dumalab ketdi 🛞",
                   "forward": "↪️ {name}, forward qilish mumkin emas — o‘z so‘zlaringiz bilan yozing 😉"},
        "night": "🌙 <b>TUNGI REJIM</b>\n\nHolat: {state}\n🕐 Toshkent vaqti bilan: <b>{start}:00 — {end}:00</b>\nBu vaqtda oddiy a’zolar yoza olmaydi.",
        "night_on": "✅ yoqilgan", "night_off": "❌ o‘chirilgan", "night_now": " · 😴 hozir uxlayapti",
        "b_night_toggle": "🌙 Tungi rejim {on}", "b_ns": "🌙 Boshlanish: {h}:00", "b_ne": "☀️ Tugash: {h}:00",
        "night_close": "🌙 <b>Tungi rejim!</b> Guruh uxlayapti 😴\nErtalab soat {end}:00 da uyg‘onamiz. Xayrli tun! 🌜",
        "night_open": "☀️ <b>Xayrli tong!</b> Guruh uyg‘ondi — choy ichib, suhbatni boshlaymiz ☕",
        "log": "📋 <b>LOG KANAL</b>\n\nHozir: {current}\n\nUlash: botni kanalga admin qiling va guruhda <code>/setlog @kanal</code> (yoki kanal ID si) yozing.\nO‘chirish: <code>/setlog off</code>",
        "log_none": "ulanmagan", "log_set": "✅ Log kanal ulandi: {chat}", "log_off": "✅ Log kanal o‘chirildi.",
        "log_fail": "❌ Kanalga yoza olmadim. Botni kanalga admin qilib, qayta urinib ko‘ring.",
        "log_need": "✍️ Masalan: /setlog @mening_kanalim",
        "log_test": "📋 Bu kanal endi «{group}» guruhi uchun log kanal 👍",
        "report_need": "↩️ Shikoyat qilish uchun xabarga reply qilib /report yozing.",
        "report_sent": "🚨 Shikoyat qabul qilindi! {n} ta admin chaqirildi 👮‍♂️",
        "report_none": "🚨 Shikoyat qabul qilindi, lekin adminlarning hech biri botga /start bosmagan 😅",
        "report_wait": "⏳ Biroz kuting — adminlar hali kofe ichishyapti ☕",
        "report_self_admin": "😄 Adminni adminga shikoyat qilish? Qiziq…",
        "report_pm": "🚨 <b>SHIKOYAT</b> · {group}\n\n👤 Kim: {reporter}\n🎯 Kimga: {target}\n💬 {text}{link}",
        "b_r_del": "🗑 O‘chirish", "b_r_mute": "🔇 1 soat jim", "b_r_ban": "🚀 Ban",
        "r_done": "✅ Bajarildi: {act}", "r_fail": "😓 Bajarib bo‘lmadi (xabar o‘chgan yoki huquq yo‘q).",
    },
    "eng": {
        "b_words": "🚫 Words", "b_locks": "🔒 Locks", "b_night": "🌙 Night mode", "b_log": "📋 Log channel",
        "words": "🚫 <b>BANNED WORDS</b>\n\n{list}\n\nIn the group: <code>/addword word</code>, <code>/delword word</code>, <code>/words</code>",
        "words_none": "Nothing yet — such a polite group 😇",
        "b_wadd": "➕ Add words", "b_wclear": "🗑 Clear all",
        "wadd_prompt": "➕ Send the words to ban, separated by commas.",
        "wadd_private": "➕ Add words in private chat or use /addword word in the group.",
        "wadd_ok": "✅ Added: {words}",
        "word_added": "🚫 «{word}» is blacklisted. Mouths will be washed with soap 🧼",
        "word_removed": "✅ «{word}» removed from the blacklist 😌",
        "word_missing": "🤷 «{word}» is not on the list.", "word_need": "✍️ Write the word: /addword word",
        "badword": ["🧼 {name}, mouth washed with soap! That word is banned 🙊"],
        "locks": "🔒 <b>LOCKS</b>\n\n❌ — such messages from regular members are deleted.",
        "lock_names": {"sticker": "🎭 Stickers", "animation": "🎞 GIFs", "voice": "🎤 Voice",
                       "video_note": "⭕ Video notes", "forward": "↪️ Forwards"},
        "locked": {"sticker": "🎭 {name}, stickers are on vacation 🏖", "animation": "🎞 {name}, GIFs are resting 😴",
                   "voice": "🎤 {name}, voice messages are off — type it ✍️", "video_note": "⭕ {name}, round videos rolled away 🛞",
                   "forward": "↪️ {name}, no forwards — use your own words 😉"},
        "night": "🌙 <b>NIGHT MODE</b>\n\nStatus: {state}\n🕐 Tashkent time: <b>{start}:00 — {end}:00</b>\nRegular members can't write during this time.",
        "night_on": "✅ on", "night_off": "❌ off", "night_now": " · 😴 sleeping now",
        "b_night_toggle": "🌙 Night mode {on}", "b_ns": "🌙 Start: {h}:00", "b_ne": "☀️ End: {h}:00",
        "night_close": "🌙 <b>Night mode!</b> The group is sleeping 😴\nWe wake up at {end}:00. Good night! 🌜",
        "night_open": "☀️ <b>Good morning!</b> The group is awake — tea and chat ☕",
        "log": "📋 <b>LOG CHANNEL</b>\n\nNow: {current}\n\nConnect: make the bot a channel admin and send <code>/setlog @channel</code> in the group.\nDisable: <code>/setlog off</code>",
        "log_none": "not connected", "log_set": "✅ Log channel connected: {chat}", "log_off": "✅ Log channel disabled.",
        "log_fail": "❌ I can't post there. Make the bot a channel admin and try again.",
        "log_need": "✍️ Example: /setlog @my_channel", "log_test": "📋 This channel now logs «{group}» 👍",
        "report_need": "↩️ Reply to a message with /report.",
        "report_sent": "🚨 Report received! {n} admins called 👮‍♂️",
        "report_none": "🚨 Report received, but no admin has started the bot 😅",
        "report_wait": "⏳ Hold on — admins are still drinking coffee ☕", "report_self_admin": "😄 Reporting an admin to admins? Interesting…",
        "report_pm": "🚨 <b>REPORT</b> · {group}\n\n👤 From: {reporter}\n🎯 About: {target}\n💬 {text}{link}",
        "b_r_del": "🗑 Delete", "b_r_mute": "🔇 Mute 1h", "b_r_ban": "🚀 Ban",
        "r_done": "✅ Done: {act}", "r_fail": "😓 Couldn't do it (message gone or no rights).",
    },
    "ru": {
        "b_words": "🚫 Слова", "b_locks": "🔒 Ограничения", "b_night": "🌙 Ночной режим", "b_log": "📋 Лог-канал",
        "words": "🚫 <b>ЗАПРЕЩЁННЫЕ СЛОВА</b>\n\n{list}\n\nВ группе: <code>/addword слово</code>, <code>/delword слово</code>, <code>/words</code>",
        "words_none": "Пока пусто — очень культурная группа 😇",
        "b_wadd": "➕ Добавить слова", "b_wclear": "🗑 Очистить всё",
        "wadd_prompt": "➕ Отправьте слова через запятую.",
        "wadd_private": "➕ Добавляйте слова в личке или командой /addword слово в группе.",
        "wadd_ok": "✅ Добавлено: {words}",
        "word_added": "🚫 «{word}» в чёрном списке. Рот будем мыть с мылом 🧼",
        "word_removed": "✅ «{word}» убрано из чёрного списка 😌",
        "word_missing": "🤷 «{word}» нет в списке.", "word_need": "✍️ Напишите слово: /addword слово",
        "badword": ["🧼 {name}, рот помыт с мылом! Это слово запрещено 🙊"],
        "locks": "🔒 <b>ОГРАНИЧЕНИЯ</b>\n\n❌ — такие сообщения от обычных участников удаляются.",
        "lock_names": {"sticker": "🎭 Стикеры", "animation": "🎞 GIF", "voice": "🎤 Голосовые",
                       "video_note": "⭕ Кружочки", "forward": "↪️ Пересылки"},
        "locked": {"sticker": "🎭 {name}, стикеры в отпуске 🏖", "animation": "🎞 {name}, гифки отдыхают 😴",
                   "voice": "🎤 {name}, голосовые запрещены — напишите текстом ✍️", "video_note": "⭕ {name}, кружочки укатились 🛞",
                   "forward": "↪️ {name}, пересылать нельзя — своими словами 😉"},
        "night": "🌙 <b>НОЧНОЙ РЕЖИМ</b>\n\nСтатус: {state}\n🕐 По Ташкенту: <b>{start}:00 — {end}:00</b>\nВ это время обычные участники не могут писать.",
        "night_on": "✅ включён", "night_off": "❌ выключен", "night_now": " · 😴 сейчас спит",
        "b_night_toggle": "🌙 Ночной режим {on}", "b_ns": "🌙 Начало: {h}:00", "b_ne": "☀️ Конец: {h}:00",
        "night_close": "🌙 <b>Ночной режим!</b> Группа спит 😴\nПросыпаемся в {end}:00. Спокойной ночи! 🌜",
        "night_open": "☀️ <b>Доброе утро!</b> Группа проснулась — чай и болтовня ☕",
        "log": "📋 <b>ЛОГ-КАНАЛ</b>\n\nСейчас: {current}\n\nПодключить: сделайте бота админом канала и напишите в группе <code>/setlog @канал</code>.\nОтключить: <code>/setlog off</code>",
        "log_none": "не подключён", "log_set": "✅ Лог-канал подключён: {chat}", "log_off": "✅ Лог-канал отключён.",
        "log_fail": "❌ Не могу писать в канал. Сделайте бота админом канала.",
        "log_need": "✍️ Пример: /setlog @my_channel", "log_test": "📋 Этот канал теперь лог группы «{group}» 👍",
        "report_need": "↩️ Ответьте на сообщение командой /report.",
        "report_sent": "🚨 Жалоба принята! Вызвано админов: {n} 👮‍♂️",
        "report_none": "🚨 Жалоба принята, но ни один админ не запускал бота 😅",
        "report_wait": "⏳ Подождите — админы ещё пьют кофе ☕", "report_self_admin": "😄 Жаловаться админам на админа? Интересно…",
        "report_pm": "🚨 <b>ЖАЛОБА</b> · {group}\n\n👤 От: {reporter}\n🎯 На: {target}\n💬 {text}{link}",
        "b_r_del": "🗑 Удалить", "b_r_mute": "🔇 Мут 1ч", "b_r_ban": "🚀 Бан",
        "r_done": "✅ Выполнено: {act}", "r_fail": "😓 Не получилось (сообщение удалено или нет прав).",
    },
    "kz": {
        "b_words": "🚫 Сөздер", "b_locks": "🔒 Шектеулер", "b_night": "🌙 Түнгі режим", "b_log": "📋 Лог арна",
        "words": "🚫 <b>ТЫЙЫМ САЛЫНҒАН СӨЗДЕР</b>\n\n{list}\n\nТопта: <code>/addword сөз</code>, <code>/delword сөз</code>, <code>/words</code>",
        "words_none": "Әзірге бос — өте мәдениетті топ 😇",
        "b_wadd": "➕ Сөз қосу", "b_wclear": "🗑 Барлығын өшіру",
        "wadd_prompt": "➕ Сөздерді үтір арқылы жіберіңіз.",
        "wadd_private": "➕ Сөздерді жеке чатта қосыңыз немесе топта /addword сөз жазыңыз.",
        "wadd_ok": "✅ Қосылды: {words}",
        "word_added": "🚫 «{word}» қара тізімге түсті 🧼", "word_removed": "✅ «{word}» қара тізімнен шықты 😌",
        "word_missing": "🤷 «{word}» тізімде жоқ.", "word_need": "✍️ Сөзді жазыңыз: /addword сөз",
        "badword": ["🧼 {name}, аузың сабынмен жуылды! Бұл сөзге тыйым салынған 🙊"],
        "locks": "🔒 <b>ШЕКТЕУЛЕР</b>\n\n❌ — мұндай хабарлар қарапайым мүшелерден өшіріледі.",
        "lock_names": {"sticker": "🎭 Стикерлер", "animation": "🎞 GIF", "voice": "🎤 Дауыстық",
                       "video_note": "⭕ Дөңгелек видео", "forward": "↪️ Форвард"},
        "locked": {"sticker": "🎭 {name}, стикерлер демалыста 🏖", "animation": "🎞 {name}, GIF-тер демалып жатыр 😴",
                   "voice": "🎤 {name}, дауыстық хабарға тыйым — жазып жіберіңіз ✍️", "video_note": "⭕ {name}, дөңгелек видеолар домалап кетті 🛞",
                   "forward": "↪️ {name}, форвардқа болмайды — өз сөзіңізбен 😉"},
        "night": "🌙 <b>ТҮНГІ РЕЖИМ</b>\n\nКүйі: {state}\n🕐 Ташкент уақыты: <b>{start}:00 — {end}:00</b>\nБұл уақытта қарапайым мүшелер жаза алмайды.",
        "night_on": "✅ қосулы", "night_off": "❌ өшірулі", "night_now": " · 😴 қазір ұйықтап жатыр",
        "b_night_toggle": "🌙 Түнгі режим {on}", "b_ns": "🌙 Басталуы: {h}:00", "b_ne": "☀️ Аяқталуы: {h}:00",
        "night_close": "🌙 <b>Түнгі режим!</b> Топ ұйықтап жатыр 😴\nСағат {end}:00-де оянамыз. Қайырлы түн! 🌜",
        "night_open": "☀️ <b>Қайырлы таң!</b> Топ оянды — шай мен әңгіме ☕",
        "log": "📋 <b>ЛОГ АРНА</b>\n\nҚазір: {current}\n\nҚосу: ботты арнаға әкімші етіп, топта <code>/setlog @арна</code> жазыңыз.\nӨшіру: <code>/setlog off</code>",
        "log_none": "қосылмаған", "log_set": "✅ Лог арна қосылды: {chat}", "log_off": "✅ Лог арна өшірілді.",
        "log_fail": "❌ Арнаға жаза алмадым. Ботты арнаға әкімші етіңіз.",
        "log_need": "✍️ Мысалы: /setlog @my_channel", "log_test": "📋 Бұл арна енді «{group}» тобының логы 👍",
        "report_need": "↩️ Хабарға /report деп жауап беріңіз.",
        "report_sent": "🚨 Шағым қабылданды! {n} әкімші шақырылды 👮‍♂️",
        "report_none": "🚨 Шағым қабылданды, бірақ әкімшілердің ешқайсысы ботты іске қоспаған 😅",
        "report_wait": "⏳ Күте тұрыңыз — әкімшілер әлі кофе ішіп жатыр ☕", "report_self_admin": "😄 Әкімшіге әкімші туралы шағым? Қызық…",
        "report_pm": "🚨 <b>ШАҒЫМ</b> · {group}\n\n👤 Кімнен: {reporter}\n🎯 Кім туралы: {target}\n💬 {text}{link}",
        "b_r_del": "🗑 Өшіру", "b_r_mute": "🔇 1 сағ үнсіз", "b_r_ban": "🚀 Бан",
        "r_done": "✅ Орындалды: {act}", "r_fail": "😓 Орындалмады (хабар өшкен немесе құқық жоқ).",
    },
}


def g2_t(chat_id, key, **kwargs):
    text = G2_TEXT[mod_lang(chat_id)].get(key) or G2_TEXT["uz"][key]
    if isinstance(text, list):
        text = random.choice(text)
    return text.format(**kwargs) if kwargs else text


def g2_word(chat_id, group, key):
    return (G2_TEXT[mod_lang(chat_id)].get(group) or G2_TEXT["uz"][group])[key]


def init_guard2():
    c = db()
    have = {r[1] for r in c.execute("PRAGMA table_info(group_settings)")}
    extra = {
        "night": "INTEGER NOT NULL DEFAULT 0", "night_start": "INTEGER NOT NULL DEFAULT 0",
        "night_end": "INTEGER NOT NULL DEFAULT 7", "night_active": "INTEGER NOT NULL DEFAULT 0",
        "night_saved": "TEXT NOT NULL DEFAULT ''", "log_chat": "INTEGER NOT NULL DEFAULT 0",
        "locks": "INTEGER NOT NULL DEFAULT 0",
    }
    with c:
        for col, decl in extra.items():
            if col not in have:
                c.execute(f"ALTER TABLE group_settings ADD COLUMN {col} {decl}")
        c.execute("""
            CREATE TABLE IF NOT EXISTS group_badwords (
                chat_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                PRIMARY KEY (chat_id, word)
            )
        """)


# ── Log kanal ──

async def mod_log(bot, chat_id, text):
    log_chat = gs_get(chat_id)["log_chat"]
    if not log_chat:
        return
    try:
        title = escape(await chat_title(bot, chat_id))
        await bot.send_message(log_chat, f"🏷 <b>{title}</b> · <code>{chat_id}</code>\n{text}")
    except TelegramError as e:
        logger.warning("Log kanalga yozilmadi (%s): %s", log_chat, e)


async def cmd_setlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id, "group_only"))
        return
    if not await is_moderator(context.bot, msg, update.effective_user):
        await msg.reply_text(mod_t(chat.id, "not_admin"))
        return
    arg = (context.args[0] if context.args else "").strip()
    if not arg:
        await msg.reply_text(g2_t(chat.id, "log_need"))
        return
    if arg.lower() in ("off", "o'chir", "0"):
        gs_set(chat.id, "log_chat", 0)
        await msg.reply_text(g2_t(chat.id, "log_off"))
        return
    target = int(arg) if arg.lstrip("-").isdigit() else arg
    try:
        sent = await context.bot.send_message(target, g2_t(chat.id, "log_test", group=escape(chat.title or "")))
    except TelegramError:
        await msg.reply_text(g2_t(chat.id, "log_fail"))
        return
    gs_set(chat.id, "log_chat", sent.chat.id)
    await msg.reply_text(g2_t(chat.id, "log_set", chat=escape(sent.chat.title or str(sent.chat.id))))


# ── Taqiqlangan so'zlar ──

def badwords(chat_id):
    if chat_id not in BADWORDS_CACHE:
        BADWORDS_CACHE[chat_id] = [
            r[0] for r in db().execute("SELECT word FROM group_badwords WHERE chat_id=? ORDER BY word", (chat_id,))
        ]
    return BADWORDS_CACHE[chat_id]


def badwords_add(chat_id, words):
    added = []
    c = db()
    with c:
        for w in words:
            w = " ".join(w.lower().split())[:50]
            if w and c.execute("INSERT OR IGNORE INTO group_badwords(chat_id, word) VALUES (?, ?)", (chat_id, w)).rowcount:
                added.append(w)
    BADWORDS_CACHE.pop(chat_id, None)
    return added


def find_badword(chat_id, text):
    low = (text or "").lower()
    for w in badwords(chat_id):
        if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low):
            return w
    return None


async def cmd_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id, "group_only"))
        return
    if not await is_moderator(context.bot, msg, update.effective_user):
        await msg.reply_text(mod_t(chat.id, "not_admin"))
        return
    command = msg.text.split()[0].lstrip("/.!").split("@")[0].lower()
    word = " ".join(context.args or []).strip()
    if command == "words":
        text, _ = await settings_page(context.bot, chat.id, "words")
        await msg.reply_text(text)
        return
    if not word:
        await msg.reply_text(g2_t(chat.id, "word_need"))
        return
    if command == "addword":
        for w in badwords_add(chat.id, [word]) or [word.lower()]:
            await msg.reply_text(g2_t(chat.id, "word_added", word=escape(w)))
        return
    c = db()
    with c:
        removed = c.execute("DELETE FROM group_badwords WHERE chat_id=? AND word=?", (chat.id, word.lower())).rowcount
    BADWORDS_CACHE.pop(chat.id, None)
    await msg.reply_text(g2_t(chat.id, "word_removed" if removed else "word_missing", word=escape(word.lower())))


# ── Cheklovlar ──

def lock_kind(msg):
    if getattr(msg, "forward_origin", None):
        return "forward"
    for kind in ("sticker", "animation", "voice", "video_note"):
        if getattr(msg, kind, None):
            return kind
    return None


# ── Tungi rejim ──

def night_in_window(start, end, hour):
    if start == end:
        return False
    return start <= hour < end if start < end else (hour >= start or hour < end)


def tashkent_hour():
    return time.gmtime(time.time() + TASHKENT_OFFSET).tm_hour


def tashkent_dt(ts):
    """Epoch → Toshkent vaqti 'KK.OO.YY SS:DD' ko'rinishida."""
    return time.strftime("%d.%m.%y %H:%M", time.gmtime(ts + TASHKENT_OFFSET))


async def night_close(bot, chat_id):
    try:
        chat = await bot.get_chat(chat_id)
        saved = json.dumps(chat.permissions.to_dict()) if chat.permissions else ""
        await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
    except TelegramError as e:
        saved = ""
        logger.warning("Tungi rejim: guruh yopilmadi (%s): %s — xabarlar o'chiriladi", chat_id, e)
    gs_set(chat_id, "night_saved", saved)
    gs_set(chat_id, "night_active", 1)
    try:
        await bot.send_message(chat_id, g2_t(chat_id, "night_close", end=f"{gs_get(chat_id)['night_end']:02d}"))
    except TelegramError:
        pass
    await mod_log(bot, chat_id, "🌙 Tungi rejim boshlandi")


async def night_open(bot, chat_id):
    saved = gs_get(chat_id)["night_saved"]
    try:
        # Yopishdan oldingi ruxsatlar qaytariladi; ular bo'lmasa — oddiy "hamma yoza oladi" ruxsatlari.
        perms = ChatPermissions.de_json(json.loads(saved), bot) if saved else None
        if not perms or not perms.can_send_messages:
            perms = ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True,
                can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True,
                can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True,
            )
        await bot.set_chat_permissions(chat_id, perms)
    except (TelegramError, ValueError) as e:
        logger.warning("Tungi rejim: guruh ochilmadi (%s): %s", chat_id, e)
    gs_set(chat_id, "night_active", 0)
    try:
        await bot.send_message(chat_id, g2_t(chat_id, "night_open"))
    except TelegramError:
        pass
    await mod_log(bot, chat_id, "☀️ Tungi rejim tugadi")


async def night_worker(application):
    while True:
        try:
            hour = tashkent_hour()
            rows = db().execute(
                "SELECT chat_id, night, night_start, night_end, night_active FROM group_settings "
                "WHERE night=1 OR night_active=1"
            ).fetchall()
            for chat_id, night, start, end, active in rows:
                should = bool(night) and night_in_window(start, end, hour)
                if should and not active:
                    await night_close(application.bot, chat_id)
                elif active and not should:
                    await night_open(application.bot, chat_id)
        except Exception:  # noqa: BLE001
            logger.exception("Tungi rejim: tekshirishda xato")
        await asyncio.sleep(NIGHT_TICK)


# ── /report va @admin ──

def message_link(chat_id, message_id):
    s = str(chat_id)
    return f"https://t.me/c/{s[4:]}/{message_id}" if s.startswith("-100") else ""


async def do_report(context, msg, reporter):
    chat_id = msg.chat_id
    target_msg = msg.reply_to_message
    if not target_msg or not target_msg.from_user:
        await msg.reply_text(g2_t(chat_id, "report_need"))
        return
    target = target_msg.from_user
    admins = await admin_ids(context.bot, chat_id)
    if target.id in admins:
        await msg.reply_text(g2_t(chat_id, "report_self_admin"))
        return
    key = (chat_id, reporter.id)
    if time.monotonic() - REPORT_LAST.get(key, -1e9) < REPORT_COOLDOWN:
        await msg.reply_text(g2_t(chat_id, "report_wait"))
        return
    REPORT_LAST[key] = time.monotonic()
    excerpt = escape((target_msg.text or target_msg.caption or "[media]")[:300])
    link = message_link(chat_id, target_msg.message_id)
    sent = 0
    for admin_id in admins:
        if admin_id == context.bot.id:
            continue
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(g2_t(admin_id, "b_r_del"), callback_data=f"rp:{chat_id}:{target.id}:{target_msg.message_id}:del"),
            InlineKeyboardButton(g2_t(admin_id, "b_r_mute"), callback_data=f"rp:{chat_id}:{target.id}:{target_msg.message_id}:mute"),
            InlineKeyboardButton(g2_t(admin_id, "b_r_ban"), callback_data=f"rp:{chat_id}:{target.id}:{target_msg.message_id}:ban"),
        ]])
        try:
            await context.bot.send_message(
                admin_id,
                g2_t(chat_id, "report_pm", group=escape(msg.chat.title or ""),
                     reporter=user_mention(reporter.id, reporter.first_name),
                     target=user_mention(target.id, target.first_name), text=excerpt,
                     link=f"\n🔗 {link}" if link else ""),
                reply_markup=kb, disable_web_page_preview=True,
            )
            sent += 1
        except TelegramError:
            pass
    await msg.reply_text(g2_t(chat_id, "report_sent", n=sent) if sent else g2_t(chat_id, "report_none"))
    await mod_log(context.bot, chat_id,
                  f"🚨 Shikoyat: {user_mention(reporter.id, reporter.first_name)} → {user_mention(target.id, target.first_name)}")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id, "group_only"))
        return
    if update.effective_user:
        await do_report(context, msg, update.effective_user)


async def cb_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, chat_text, uid_text, mid_text, act = q.data.split(":")
    chat_id, uid, mid = int(chat_text), int(uid_text), int(mid_text)
    if not await user_is_chat_admin(context.bot, chat_id, q.from_user.id):
        await q.answer(st_t(chat_id, "not_admin_of"), show_alert=True)
        return
    labels = {"del": "b_r_del", "mute": "b_r_mute", "ban": "b_r_ban"}
    try:
        if act == "del":
            await context.bot.delete_message(chat_id, mid)
        elif act == "mute":
            await mod_mute(context.bot, chat_id, uid, 3600)
        elif act == "ban":
            await context.bot.ban_chat_member(chat_id, uid)
        else:
            await q.answer()
            return
    except TelegramError:
        await q.answer(g2_t(chat_id, "r_fail"), show_alert=True)
        return
    done = g2_t(chat_id, "r_done", act=g2_t(chat_id, labels[act]))
    await q.answer(done)
    try:
        await q.edit_message_text(q.message.text_html + "\n\n" + done, reply_markup=q.message.reply_markup)
    except TelegramError:
        pass
    await mod_log(context.bot, chat_id,
                  f"{done} — {user_mention(uid, uid)} ({user_mention(q.from_user.id, q.from_user.first_name)})")


def undo_kb(chat_id, act, uid):
    """Jazo xabari tagidagi «✅ Bekor qilish» tugmasi. act: 'mute' yoki 'ban'."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        g2_t(chat_id, "bw_undo"), callback_data=f"undo:{act}:{uid}")]])


async def admin_can_restrict(bot, chat_id, user_id):
    """Foydalanuvchi — a'zolarni cheklash huquqiga ega adminmi (yoki guruh/bot egasi)?"""
    if user_id in CAREER_OWNER_IDS:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        return False
    if m.status == ChatMemberStatus.OWNER:
        return True
    return m.status == ChatMemberStatus.ADMINISTRATOR and bool(getattr(m, "can_restrict_members", False))


async def cb_mod_undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jazo (mute/ban) xabari tagidagi «✅ Bekor qilish» — faqat cheklash huquqiga ega admin bosadi."""
    q = update.callback_query
    chat_id = q.message.chat.id if q.message else None
    act, uid = "mute", None
    parts = q.data.split(":")
    try:
        if parts[0] == "undo":           # undo:<mute|ban>:<uid>
            act, uid = parts[1], int(parts[2])
        elif parts[0] == "bw":           # eski format: bw:<chat>:<uid> (= mute)
            chat_id, uid, act = int(parts[1]), int(parts[2]), "mute"
    except (ValueError, IndexError):
        await q.answer()
        return
    if uid is None or chat_id is None:
        await q.answer()
        return
    if not await admin_can_restrict(context.bot, chat_id, q.from_user.id):
        await q.answer(g2_t(chat_id, "undo_no_right"), show_alert=True)
        return
    try:
        if act == "ban":
            await context.bot.unban_chat_member(chat_id, uid, only_if_banned=True)
        else:
            await mod_unmute(context.bot, chat_id, uid)
    except TelegramError:
        await q.answer(g2_t(chat_id, "r_fail"), show_alert=True)
        return
    admin = user_mention(q.from_user.id, q.from_user.first_name)
    key = "undo_unbanned" if act == "ban" else "undo_unmuted"
    await q.answer("✅")
    try:
        await q.edit_message_text(
            q.message.text_html + g2_t(chat_id, key, admin=admin, name=user_mention(uid, uid)),
            reply_markup=None,
        )
    except TelegramError:
        pass
    await mod_log(context.bot, chat_id, f"♻️ {act} bekor qilindi — {user_mention(uid, uid)} ({admin})")


async def cmd_badmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Taqiqlangan so'z uchun mute muddatini guruh bo'yicha sozlaydi."""
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    cur = gs_get(chat.id).get("badword_mute") or BADWORD_MUTE
    if not context.args:
        await msg.reply_text(g2_t(chat.id, "badmute_now", dur=fmt_dur(chat.id, cur)))
        return
    seconds = parse_dur(context.args[0])
    if not seconds:
        await msg.reply_text(g2_t(chat.id, "badmute_now", dur=fmt_dur(chat.id, cur)))
        return
    gs_set(chat.id, "badword_mute", seconds)
    await msg.reply_text(g2_t(chat.id, "badmute_set", dur=fmt_dur(chat.id, seconds)))


# ───────────────────────────── 🛡 GROUP HELP QO'SHIMCHA BUYRUQLARI ─────────────────────────────
# Group Help uslubidagi to'liq admin buyruqlari: /del /purge /pin /unpin /id /info /admins
# /lock /unlock /locks /title /setwelcome /setrules /rules (guruh) /filter /filters /delfilter.
# Hammasi mavjud yordamchilarни qayta ishlatadi (is_moderator, admin_ids, mod_target, mod_log).

GH_TEXT = {
    "uz": {
        "del_ok": "🗑 Xabar o‘chirildi.",
        "del_need": "↩️ O‘chirmoqchi bo‘lgan xabarga reply qiling.",
        "purge_need": "↩️ Qaysi xabardan o‘chirishni boshlashini ko‘rsatish uchun o‘sha xabarga reply qiling.",
        "purge_ok": "🧹 {n} ta xabar o‘chirildi.",
        "purge_big": "⚠️ Juda ko‘p xabar (max {max}). Kichikroq oraliqni tanlang.",
        "pin_ok": "📌 Xabar mahkamlandi.",
        "pin_need": "↩️ Mahkamlamoqchi bo‘lgan xabarga reply qiling.",
        "unpin_ok": "📌 Mahkamlangan xabar olib tashlandi.",
        "unpin_all": "📌 Barcha mahkamlangan xabarlar olib tashlandi.",
        "id_self": "🪪 <b>ID ma’lumot</b>\n\n👥 Guruh: <code>{chat}</code>\n🙋 Siz: <code>{you}</code>",
        "id_reply": "\n↩️ U kishi: <code>{uid}</code>",
        "info": ("🪪 <b>FOYDALANUVCHI</b>\n\n👤 Ism: {name}\n🆔 ID: <code>{uid}</code>\n"
                 "🔖 Username: {uname}\n🎖 Holat: {status}\n⚠️ Ogohlantirish: {warns}/{limit}"),
        "admins": "👮 <b>GURUH ADMINLARI</b> ({n})\n\n{list}",
        "lock_ok": "🔒 <b>{kind}</b> cheklandi.",
        "unlock_ok": "🔓 <b>{kind}</b> chekLovdan chiqarildi.",
        "lock_bad": "❓ Noma’lum tur. Mavjud: {types}.",
        "locks_head": "🔒 <b>CHEKLOVLAR</b>\n\n",
        "lock_on": "🔒 yoqilgan", "lock_off": "🔓 ochiq",
        "title_ok": "🎖 {name} ning unvoni: <b>{title}</b>",
        "title_need": "↩️ Admin xabariga reply qilib unvonni yozing: <code>/title Boshqaruvchi</code>",
        "welcome_set": "👋 Yangi salomlashish matni saqlandi. Namuna:\n\n{sample}",
        "welcome_bad": "❌ Matnda faqat <code>{{name}}</code> va <code>{{group}}</code> ishlatilsin.",
        "welcome_need": "✏️ Matnni yozing: <code>/setwelcome Salom {{name}}! {{group}}ga xush kelibsiz 🎉</code>",
        "rules_set": "📜 Guruh qoidalari saqlandi.",
        "rules_need": "✏️ Qoidalarni yozing: <code>/setrules 1. Hurmat 2. Spam yo‘q ...</code>",
        "rules_show": "📜 <b>GURUH QOIDALARI</b>\n\n{text}",
        "rules_empty": "📜 Bu guruhda hali qoida o‘rnatilmagan. Admin <code>/setrules</code> bilan qo‘shadi.",
        "filter_set": "💬 Filtr saqlandi: <b>{trig}</b>",
        "filter_need": "✏️ <code>/filter so‘z javob matni</code> ko‘rinishida yozing (yoki javob o‘rniga xabarga reply qiling).",
        "filter_del": "🗑 Filtr o‘chirildi: <b>{trig}</b>",
        "filter_missing": "❓ Bunday filtr yo‘q: <b>{trig}</b>",
        "filters_list": "💬 <b>FILTRLAR</b> ({n})\n\n{list}",
        "filters_empty": "💬 Hali filtr yo‘q. <code>/filter so‘z javob</code> bilan qo‘shing.",
        "admin_help": (
            "🛡 <b>ADMIN BUYRUQLARI</b> (reply yoki @username/ID bilan)\n\n"
            "👮 <b>Jazo:</b> /warn /unwarn /warns · /mute /tmute /unmute · /ban /tban /unban · /kick\n"
            "   (muddat: <code>/mute 10m</code>, <code>/tban 2h</code>, <code>/tmute 1d</code>)\n"
            "🧹 <b>Xabar:</b> /del (reply) · /purge (reply) · /pin /unpin\n"
            "👑 <b>Adminlar:</b> /promote /demote · /title (reply) · /admins\n"
            "🔒 <b>Cheklov:</b> /lock /unlock /locks (stiker, gif, ovozli, dumaloq, forward, all)\n"
            "🚫 <b>So‘zlar:</b> /addword /delword /words\n"
            "💬 <b>Filtr:</b> /filter so‘z javob · /filters · /delfilter so‘z\n"
            "⚙️ <b>Sozlash:</b> /settings · /setwelcome · /setrules · /rules · /setlog\n"
            "🪪 <b>Ma’lumot:</b> /info · /id · /report (yoki @admin)"
        ),
    },
}
GH_TYPES_UZ = {
    "sticker": "stiker", "animation": "GIF", "voice": "ovozli",
    "video_note": "dumaloq video", "forward": "forward",
}


def gh_t(chat_id, key, **kw):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    d = GH_TEXT.get(lang) or GH_TEXT["uz"]
    s = d.get(key) or GH_TEXT["uz"][key]
    return s.format(**kw) if kw else s


def init_grouphelp():
    c = db()
    with c:
        have = {r[1] for r in c.execute("PRAGMA table_info(group_settings)")}
        if "rules" not in have:
            c.execute("ALTER TABLE group_settings ADD COLUMN rules TEXT NOT NULL DEFAULT ''")
        if "badword_mute" not in have:
            c.execute("ALTER TABLE group_settings ADD COLUMN badword_mute INTEGER NOT NULL DEFAULT 1800")
        c.execute(
            "CREATE TABLE IF NOT EXISTS group_filters ("
            "chat_id INTEGER NOT NULL, trigger TEXT NOT NULL, reply TEXT NOT NULL, "
            "PRIMARY KEY (chat_id, trigger))"
        )


async def gh_admin_guard(update, context):
    """Guruh + admin tekshiruvi. (msg, chat, user) yoki (None, None, None)."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat:
        return None, None, None
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id if chat else 0, "group_only"))
        return None, None, None
    if not await is_moderator(context.bot, msg, user):
        await msg.reply_text(mod_t(chat.id, "not_admin"))
        return None, None, None
    return msg, chat, user


async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    if not msg.reply_to_message:
        await msg.reply_text(gh_t(chat.id, "del_need"))
        return
    try:
        await context.bot.delete_message(chat.id, msg.reply_to_message.message_id)
        await msg.delete()
    except TelegramError:
        await msg.reply_text(mod_t(chat.id, "no_rights"))
        return
    sent = await context.bot.send_message(chat.id, gh_t(chat.id, "del_ok"))
    await delete_later(context.bot, chat.id, sent.message_id, NOTICE_TTL)


async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    if not msg.reply_to_message:
        await msg.reply_text(gh_t(chat.id, "purge_need"))
        return
    start = msg.reply_to_message.message_id
    end = msg.message_id
    ids = list(range(start, end + 1))
    if len(ids) > 400:
        await msg.reply_text(gh_t(chat.id, "purge_big", max=400))
        return
    deleted = 0
    # delete_messages 100 tadan ko'p qabul qilmaydi
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            await context.bot.delete_messages(chat.id, chunk)
            deleted += len(chunk)
        except TelegramError:
            # bir xato bo'lsa, bittalab urinib ko'ramiz (eski xabarlar o'chmasligi mumkin)
            for mid in chunk:
                try:
                    await context.bot.delete_message(chat.id, mid)
                    deleted += 1
                except TelegramError:
                    pass
    sent = await context.bot.send_message(chat.id, gh_t(chat.id, "purge_ok", n=deleted))
    await delete_later(context.bot, chat.id, sent.message_id, NOTICE_TTL)
    await mod_log(context.bot, chat.id, f"🧹 /purge — {deleted} ta xabar ({user_mention(user.id, user.first_name)})")


async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    command = msg.text.split()[0].lstrip("/.!").split("@")[0].lower()
    if command == "unpin":
        try:
            if msg.reply_to_message:
                await context.bot.unpin_chat_message(chat.id, msg.reply_to_message.message_id)
                await msg.reply_text(gh_t(chat.id, "unpin_ok"))
            else:
                await context.bot.unpin_all_chat_messages(chat.id)
                await msg.reply_text(gh_t(chat.id, "unpin_all"))
        except TelegramError:
            await msg.reply_text(mod_t(chat.id, "no_rights"))
        return
    if not msg.reply_to_message:
        await msg.reply_text(gh_t(chat.id, "pin_need"))
        return
    loud = bool(context.args) and context.args[0].lower() in ("loud", "ovoz", "ovozli", "signal")
    try:
        await context.bot.pin_chat_message(
            chat.id, msg.reply_to_message.message_id, disable_notification=not loud)
        await msg.reply_text(gh_t(chat.id, "pin_ok"))
    except TelegramError:
        await msg.reply_text(mod_t(chat.id, "no_rights"))


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat:
        return
    text = gh_t(chat.id, "id_self", chat=chat.id, you=user.id if user else "?")
    if msg.reply_to_message and msg.reply_to_message.from_user:
        text += gh_t(chat.id, "id_reply", uid=msg.reply_to_message.from_user.id)
    await msg.reply_text(text)


STATUS_LABEL = {
    ChatMemberStatus.OWNER: "👑 Egasi", ChatMemberStatus.ADMINISTRATOR: "👮 Admin",
    ChatMemberStatus.MEMBER: "👤 A’zo", ChatMemberStatus.RESTRICTED: "🔇 Cheklangan",
    ChatMemberStatus.LEFT: "🚪 Chiqib ketgan", ChatMemberStatus.BANNED: "🚫 Bloklangan",
}


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id, "group_only"))
        return
    target, name, _, _ = await mod_target(update, context)
    if not target:
        u = update.effective_user
        target, name = u.id, user_mention(u.id, u.first_name)
    status, uname_s = "—", "—"
    try:
        member = await context.bot.get_chat_member(chat.id, target)
        status = STATUS_LABEL.get(member.status, str(member.status))
        if member.user and member.user.username:
            uname_s = "@" + member.user.username
    except TelegramError:
        pass
    row = db().execute("SELECT count FROM group_warns WHERE chat_id=? AND user_id=?", (chat.id, target)).fetchone()
    warns = row[0] if row else 0
    limit = gs_get(chat.id)["warn_limit"]
    await msg.reply_text(gh_t(chat.id, "info", name=name, uid=target, uname=uname_s,
                              status=status, warns=warns, limit=limit))


async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text(mod_t(chat.id, "group_only"))
        return
    try:
        members = await context.bot.get_chat_administrators(chat.id)
    except TelegramError:
        await msg.reply_text(mod_t(chat.id, "no_rights"))
        return
    lines = []
    for m in members:
        if m.user.is_bot:
            continue
        crown = "👑" if m.status == ChatMemberStatus.OWNER else "👮"
        title = f" · <i>{escape(m.custom_title)}</i>" if getattr(m, "custom_title", None) else ""
        lines.append(f"{crown} {user_mention(m.user.id, m.user.first_name)}{title}")
    await msg.reply_text(gh_t(chat.id, "admins", n=len(lines), list="\n".join(lines) or "—"))


LOCK_ALIASES = {
    "sticker": "sticker", "stiker": "sticker", "стикер": "sticker",
    "gif": "animation", "animation": "animation", "гиф": "animation",
    "voice": "voice", "ovoz": "voice", "ovozli": "voice", "голос": "voice",
    "video": "video_note", "video_note": "video_note", "dumaloq": "video_note", "round": "video_note",
    "forward": "forward", "fwd": "forward", "форвард": "forward",
}


async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    command = msg.text.split()[0].lstrip("/.!").split("@")[0].lower()
    settings = gs_get(chat.id)
    if command == "locks":
        lines = [gh_t(chat.id, "locks_head").rstrip("\n")]
        for i, kind in enumerate(LOCK_TYPES):
            on = settings["locks"] & (1 << i)
            lines.append(f"• {GH_TYPES_UZ[kind]}: {gh_t(chat.id, 'lock_on' if on else 'lock_off')}")
        await msg.reply_text("\n".join(lines))
        return
    arg = (context.args[0].lower() if context.args else "")
    if arg in ("all", "hammasi", "все"):
        bits = (1 << len(LOCK_TYPES)) - 1
        new = bits if command == "lock" else 0
        gs_set(chat.id, "locks", new)
        await msg.reply_text(gh_t(chat.id, "lock_ok" if command == "lock" else "unlock_ok", kind="hammasi"))
        return
    kind = LOCK_ALIASES.get(arg)
    if not kind:
        await msg.reply_text(gh_t(chat.id, "lock_bad", types=", ".join(GH_TYPES_UZ[k] for k in LOCK_TYPES)))
        return
    bit = 1 << LOCK_TYPES.index(kind)
    new = settings["locks"] | bit if command == "lock" else settings["locks"] & ~bit
    gs_set(chat.id, "locks", new)
    await msg.reply_text(gh_t(chat.id, "lock_ok" if command == "lock" else "unlock_ok", kind=GH_TYPES_UZ[kind]))


async def cmd_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    if not (msg.reply_to_message and msg.reply_to_message.from_user) or not context.args:
        await msg.reply_text(gh_t(chat.id, "title_need"))
        return
    target = msg.reply_to_message.from_user
    title = " ".join(context.args)[:16]
    try:
        await context.bot.set_chat_administrator_custom_title(chat.id, target.id, title)
    except TelegramError:
        await msg.reply_text(mod_t(chat.id, "no_rights"))
        return
    await msg.reply_text(gh_t(chat.id, "title_ok", name=user_mention(target.id, target.first_name), title=escape(title)))


def _welcome_valid(text):
    probe = text
    for token in ("{name}", "{group}"):
        probe = probe.replace(token, "")
    return "{" not in probe and "}" not in probe


async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    text = msg.text.split(None, 1)[1].strip() if len(msg.text.split(None, 1)) > 1 else ""
    if not text and msg.reply_to_message and msg.reply_to_message.text:
        text = msg.reply_to_message.text.strip()
    if not text:
        await msg.reply_text(gh_t(chat.id, "welcome_need"))
        return
    if not _welcome_valid(text):
        await msg.reply_text(gh_t(chat.id, "welcome_bad"))
        return
    gs_set(chat.id, "welcome_text", text[:2000])
    gs_set(chat.id, "welcome", 1)
    sample = text.replace("{name}", user_mention(user.id, user.first_name)).replace("{group}", escape(chat.title or ""))
    await msg.reply_text(gh_t(chat.id, "welcome_set", sample=sample))


async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    text = msg.text.split(None, 1)[1].strip() if len(msg.text.split(None, 1)) > 1 else ""
    if not text and msg.reply_to_message and msg.reply_to_message.text:
        text = msg.reply_to_message.text.strip()
    if not text:
        await msg.reply_text(gh_t(chat.id, "rules_need"))
        return
    gs_set(chat.id, "rules", text[:3000])
    await msg.reply_text(gh_t(chat.id, "rules_set"))


async def cmd_grules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rules — guruhda: o'rnatilgan qoidalar bo'lsa shuni, bo'lmasa o'yin qoidalarini (cmd_rules)."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        rules = gs_get(chat.id).get("rules") or ""
        if rules:
            await msg.reply_text(gh_t(chat.id, "rules_show", text=escape(rules)))
            return
    await cmd_rules(update, context)


# ── Filtrlar (so'zga avtomatik javob) ──

def gh_filters(chat_id):
    if chat_id not in FILTERS_CACHE:
        FILTERS_CACHE[chat_id] = {
            r[0]: r[1] for r in db().execute(
                "SELECT trigger, reply FROM group_filters WHERE chat_id=?", (chat_id,))
        }
    return FILTERS_CACHE[chat_id]


def gh_filter_match(chat_id, text):
    if not text:
        return None
    low = text.lower()
    for trig, reply in gh_filters(chat_id).items():
        if re.search(rf"(?<!\w){re.escape(trig)}(?!\w)", low):
            return reply
    return None


async def cmd_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat, user = await gh_admin_guard(update, context)
    if not msg:
        return
    command = msg.text.split()[0].lstrip("/.!").split("@")[0].lower()
    if command == "filters":
        f = gh_filters(chat.id)
        if not f:
            await msg.reply_text(gh_t(chat.id, "filters_empty"))
            return
        lst = "\n".join(f"• <b>{escape(k)}</b>" for k in sorted(f))
        await msg.reply_text(gh_t(chat.id, "filters_list", n=len(f), list=lst))
        return
    parts = msg.text.split(None, 2)
    if command == "delfilter":
        trig = (parts[1].lower() if len(parts) > 1 else "").strip()
        if not trig:
            await msg.reply_text(gh_t(chat.id, "filter_need"))
            return
        c = db()
        with c:
            removed = c.execute("DELETE FROM group_filters WHERE chat_id=? AND trigger=?", (chat.id, trig)).rowcount
        FILTERS_CACHE.pop(chat.id, None)
        await msg.reply_text(gh_t(chat.id, "filter_del" if removed else "filter_missing", trig=escape(trig)))
        return
    # /filter <trigger> <reply>  (yoki reply orqali javob)
    trig = (parts[1].lower() if len(parts) > 1 else "").strip()
    reply = parts[2].strip() if len(parts) > 2 else ""
    if not reply and msg.reply_to_message and msg.reply_to_message.text:
        reply = msg.reply_to_message.text.strip()
    if not trig or not reply:
        await msg.reply_text(gh_t(chat.id, "filter_need"))
        return
    c = db()
    with c:
        c.execute(
            "INSERT INTO group_filters(chat_id, trigger, reply) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, trigger) DO UPDATE SET reply=excluded.reply",
            (chat.id, trig[:60], reply[:2000]),
        )
    FILTERS_CACHE.pop(chat.id, None)
    await msg.reply_text(gh_t(chat.id, "filter_set", trig=escape(trig[:60])))


# ───────────────────────────── 💱 BOTLAR ARO PUL ALMASHUVI (bridge) ─────────────────────────────
# Ikki bot o'rtasida xavfsiz pul o'tkazish. Har bir so'rov umumiy maxfiy kalit (EXCHANGE_SECRET) bilan
# HMAC-imzolanadi; takroriy tushishning oldini olish uchun har o'tkazmaning noyob txid'i bor (idempotent).
#   Kiruvchi: hamkor bot bizning foydalanuvchiga $ qo'shadi (HTTP /exchange/credit).
#   Chiquvchi: bizning foydalanuvchi $ ni hamkor botga 1:1 yuboradi (xatoda avtomatik qaytadi).
# DB bitta ip bilan ishlagani uchun HTTP server so'rovni bot asyncio sikliga uzatadi.
# Env: EXCHANGE_SECRET (majburiy), EXCHANGE_PARTNER_URL (hamkor bridge manzili), EXCHANGE_PARTNER_NAME,
#      PORT (Railway bergan — kiruvchi server shunga bog'lanadi).

EXCHANGE_SECRET = os.getenv("EXCHANGE_SECRET", "").strip()
EXCHANGE_PARTNER_URL = os.getenv("EXCHANGE_PARTNER_URL", "").strip().rstrip("/")
EXCHANGE_PARTNER_NAME = os.getenv("EXCHANGE_PARTNER_NAME", "Hamkor bot").strip()
EXCHANGE_PORT = os.getenv("PORT", "").strip()
EXCHANGE_TS_WINDOW = 300          # imzo yangiligi (soniya)
EXCHANGE_HTTP_TIMEOUT = 15        # hamkorga so'rov kutish vaqti
EXCHANGE_AMOUNTS = [100, 500, 1000, 5000, 10000]
EXCHANGE_MIN = 10
EXCHANGE_RETRY_TICK = 60
EXCHANGE_MAX_RETRY = 30
_EXCHANGE_LOOP = None             # bot asyncio sikli (post_init'da o'rnatiladi)
_EXCHANGE_SERVER = None

EXCH_TEXT = {
    "uz": {
        "title": "💱 <b>{partner} ga pul o‘tkazish</b>\n\n💵 Hamyon: <b>{wallet}$</b>\n💸 Komissiya: {fee}%\n📅 Bugungi limit: {left}$ qoldi\n\nMiqdorni tanlang 👇\n\n🎮 Simulator — haqiqiy pul emas",
        "off": "💱 Pul almashuvi hozircha ulanmagan.",
        "not_yours": "⛔ Bu menyu sizniki emas — o‘zingiz /profil yozing.",
        "confirm": "💱 <b>Tasdiqlang</b>\n\n{amount}$ yuborasiz · komissiya {fee}$\n➡️ {partner}da hisobingizga <b>{net}$</b> tushadi.",
        "b_confirm": "✅ Yuborish", "b_cancel": "❌ Bekor", "b_back": "⬅️ Orqaga",
        "no_funds": "💸 Hamyonda yetarli pul yo‘q (balans: {bal}$).",
        "loan": "⛔ Faol kreditingiz bor — avval uni to‘lang.",
        "limit": "⛔ Bugungi almashuv limiti tugadi.",
        "too_small": "Minimal miqdor — {min}$.",
        "sent": "✅ <b>{net}$</b> {partner}ga yuborildi! U yerda hisobingizga tushdi.",
        "pending": "⏳ O‘tkazma yuborildi, hamkor bot javobini kutyapmiz. Pul tez orada tushadi yoki qaytariladi.",
        "failed": "😓 O‘tkazib bo‘lmadi — pul hamyoningizga qaytarildi.",
        "got": "💱 {partner}dan hisobingizga <b>+{amount}$</b> tushdi!\n💰 Balans: {bal}$",
    },
    "eng": {
        "title": "💱 <b>Transfer to {partner}</b>\n\n💵 Wallet: <b>{wallet}$</b>\n💸 Fee: {fee}%\n📅 Left today: {left}$\n\nChoose an amount 👇\n\n🎮 Simulator — not real money",
        "off": "💱 Exchange is not connected yet.",
        "not_yours": "⛔ This menu is not yours — type /profile yourself.",
        "confirm": "💱 <b>Confirm</b>\n\nYou send {amount}$ · fee {fee}$\n➡️ <b>{net}$</b> arrives in your {partner} account.",
        "b_confirm": "✅ Send", "b_cancel": "❌ Cancel", "b_back": "⬅️ Back",
        "no_funds": "💸 Not enough money (balance: {bal}$).",
        "loan": "⛔ You have an active loan — repay it first.",
        "limit": "⛔ Today's exchange limit is reached.",
        "too_small": "Minimum is {min}$.",
        "sent": "✅ <b>{net}$</b> sent to {partner}! It arrived in your account there.",
        "pending": "⏳ Sent, waiting for the partner bot. The money will arrive or be refunded soon.",
        "failed": "😓 Couldn't transfer — the money was refunded to your wallet.",
        "got": "💱 <b>+{amount}$</b> arrived from {partner}!\n💰 Balance: {bal}$",
    },
    "ru": {
        "title": "💱 <b>Перевод в {partner}</b>\n\n💵 Кошелёк: <b>{wallet}$</b>\n💸 Комиссия: {fee}%\n📅 Остаток на сегодня: {left}$\n\nВыберите сумму 👇\n\n🎮 Симулятор — не настоящие деньги",
        "off": "💱 Обмен пока не подключён.",
        "not_yours": "⛔ Это не ваше меню — напишите /profil сами.",
        "confirm": "💱 <b>Подтвердите</b>\n\nВы отправляете {amount}$ · комиссия {fee}$\n➡️ <b>{net}$</b> поступит на ваш счёт в {partner}.",
        "b_confirm": "✅ Отправить", "b_cancel": "❌ Отмена", "b_back": "⬅️ Назад",
        "no_funds": "💸 Недостаточно средств (баланс: {bal}$).",
        "loan": "⛔ У вас есть активный кредит — сначала погасите.",
        "limit": "⛔ Дневной лимит обмена исчерпан.",
        "too_small": "Минимум — {min}$.",
        "sent": "✅ <b>{net}$</b> отправлено в {partner}! Зачислено на ваш счёт там.",
        "pending": "⏳ Отправлено, ждём ответа бота-партнёра. Деньги скоро поступят или вернутся.",
        "failed": "😓 Не удалось перевести — деньги возвращены в кошелёк.",
        "got": "💱 <b>+{amount}$</b> поступило из {partner}!\n💰 Баланс: {bal}$",
    },
    "kz": {
        "title": "💱 <b>{partner} ішіне аудару</b>\n\n💵 Әмиян: <b>{wallet}$</b>\n💸 Комиссия: {fee}%\n📅 Бүгінгі қалдық: {left}$\n\nСоманы таңдаңыз 👇\n\n🎮 Симулятор — нақты ақша емес",
        "off": "💱 Айырбас әзірге қосылмаған.",
        "not_yours": "⛔ Бұл мәзір сіздікі емес — өзіңіз /profil жазыңыз.",
        "confirm": "💱 <b>Растаңыз</b>\n\n{amount}$ жібересіз · комиссия {fee}$\n➡️ {partner}дегі шотыңызға <b>{net}$</b> түседі.",
        "b_confirm": "✅ Жіберу", "b_cancel": "❌ Болдырмау", "b_back": "⬅️ Артқа",
        "no_funds": "💸 Қаражат жеткіліксіз (баланс: {bal}$).",
        "loan": "⛔ Белсенді несиеңіз бар — алдымен өтеңіз.",
        "limit": "⛔ Бүгінгі айырбас лимиті бітті.",
        "too_small": "Ең азы — {min}$.",
        "sent": "✅ <b>{net}$</b> {partner}ға жіберілді! Ондағы шотыңызға түсті.",
        "pending": "⏳ Жіберілді, серіктес боттың жауабын күтудеміз. Ақша жақында түседі немесе қайтарылады.",
        "failed": "😓 Аудару мүмкін болмады — ақша әмияныңызға қайтарылды.",
        "got": "💱 {partner}дан шотыңызға <b>+{amount}$</b> түсті!\n💰 Баланс: {bal}$",
    },
}


def exch_t(uid, key, **kwargs):
    lang = LANG_CACHE.get(uid, DEFAULT_LANG)
    text = EXCH_TEXT.get(lang, EXCH_TEXT["uz"]).get(key) or EXCH_TEXT["uz"][key]
    return text.format(**kwargs) if kwargs else text


def init_exchange():
    c = db()
    with c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS exchange_config (
                id INTEGER PRIMARY KEY CHECK (id=1),
                enabled INTEGER NOT NULL DEFAULT 0,
                fee_pct REAL NOT NULL DEFAULT 5,
                daily_limit INTEGER NOT NULL DEFAULT 50000
            )
        """)
        c.execute("INSERT OR IGNORE INTO exchange_config(id) VALUES (1)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS exchange_txns (
                txid TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                retries INTEGER NOT NULL DEFAULT 0,
                net INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)
        if "net" not in {r[1] for r in c.execute("PRAGMA table_info(exchange_txns)")}:
            c.execute("ALTER TABLE exchange_txns ADD COLUMN net INTEGER NOT NULL DEFAULT 0")
        c.execute("CREATE INDEX IF NOT EXISTS idx_exch_out ON exchange_txns(direction, status)")


def exch_config():
    row = db().execute("SELECT enabled, fee_pct, daily_limit FROM exchange_config WHERE id=1").fetchone()
    return dict(zip(("enabled", "fee_pct", "daily_limit"), row)) if row else {"enabled": 0, "fee_pct": 5, "daily_limit": 50000}


def exch_ready():
    """Almashuv sozlanganmi (kalit bor + yoqilgan)."""
    return bool(EXCHANGE_SECRET) and exch_config()["enabled"]


def exch_sign(body: bytes) -> str:
    return hmac.new(EXCHANGE_SECRET.encode(), body, hashlib.sha256).hexdigest()


def exch_today_out(uid):
    start = int(time.time()) - 86400
    row = db().execute(
        "SELECT COALESCE(SUM(amount), 0) FROM exchange_txns WHERE direction='out' AND user_id=? "
        "AND status IN ('done','pending') AND created_at>=?",
        (uid, start),
    ).fetchone()
    return int(row[0] or 0)


# ── Kiruvchi: hamkor bot bizning foydalanuvchiga pul qo'shadi ──

async def exchange_apply_incoming(txid, user_id, amount):
    """Bot sikli ichida: idempotent kreditlash. Qaytaradi: (ok, data)."""
    cfg = exch_config()
    if not EXCHANGE_SECRET or not cfg["enabled"]:
        return False, {"error": "disabled"}
    if amount <= 0 or amount > 10 ** 9:
        return False, {"error": "bad_amount"}
    c = db()
    try:
        with c:
            cur = c.execute(
                "INSERT OR IGNORE INTO exchange_txns(txid, direction, user_id, amount, status, created_at) "
                "VALUES (?, 'in', ?, ?, 'done', ?)",
                (txid, user_id, amount, int(time.time())),
            )
            fresh = cur.rowcount == 1
            if fresh:
                _wallet_add(c, user_id, amount)
        balance = wallet_balance(user_id)
    except sqlite3.Error:
        logger.exception("Almashuv: kiruvchi kredit yozilmadi (txid %s)", txid)
        return False, {"error": "db"}
    if fresh:
        try:
            await _EXCHANGE_LOOP_BOT.send_message(
                user_id, exch_t(user_id, "got", partner=escape(EXCHANGE_PARTNER_NAME),
                                amount=fmt_money(amount), bal=fmt_money(balance)))
        except TelegramError:
            pass
        await log_money_event(
            _EXCHANGE_LOOP_BOT,
            f"💱 <b>ALMASHUV (kirdi)</b> · {escape(EXCHANGE_PARTNER_NAME)}\n{person_name(user_id)}: +{amount}$ (txid {txid})",
        )
    return True, {"balance": balance, "duplicate": not fresh}


# ── HTTP server (alohida ipda; so'rovni bot sikliga uzatadi) ──

class _ExchangeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # jim
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code, html):
        body = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/exchange/ping":
            self._send(200, {"ok": True, "bot": "son_bot"})
        elif path in ("", "/app"):
            self._send_html(200, WEBAPP_HTML)
        elif path.startswith("/app/avatar/") and path.rsplit("/", 1)[1].isdigit():
            self._avatar(int(path.rsplit("/", 1)[1]))
        elif path.startswith("/app/a/") and path.rsplit("/", 1)[1] in WEBAPP_ASSETS:
            self._asset(path.rsplit("/", 1)[1])
        else:
            self._send(404, {"ok": False})

    def _asset(self, name):
        """Web app rasmlari (Kazino bannerlari) — repo ichidagi webapp_assets/ dan."""
        try:
            with open(os.path.join(BASE_DIR, "webapp_assets", name), "rb") as f:
                data = f.read()
        except OSError:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", WEBAPP_ASSETS[name])
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _avatar(self, uid):
        """Telegram profil rasmi (faqat botni ishlatgan foydalanuvchilar uchun)."""
        data = b""
        if _EXCHANGE_LOOP is not None:
            async def _get():
                if not db().execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone():
                    return b""
                return await web_avatar_bytes(uid)
            try:
                data = asyncio.run_coroutine_threadsafe(_get(), _EXCHANGE_LOOP).result(timeout=10)
            except Exception:  # noqa: BLE001
                data = b""
        if not data:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _web_api(self, path):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw.decode()) if raw else {}
        except (ValueError, OSError, json.JSONDecodeError):
            self._send(400, {"ok": False, "error": "body"})
            return
        user = webapp_check_init_data(body.get("initData", ""))
        if not user:
            self._send(401, {"ok": False, "error": "auth"})
            return
        if _EXCHANGE_LOOP is None:
            self._send(503, {"ok": False, "error": "starting"})
            return
        uid = int(user["id"])
        if path == "/app/api/data":
            coro = webapp_fetch(uid)
        elif path in ("/app/api/crash/start", "/app/api/crash/bet"):
            coro = web_crash_bet(uid, body.get("bet"))
        elif path == "/app/api/crash/cancel":
            coro = web_crash_cancel(uid)
        elif path == "/app/api/crash/state":
            coro = web_crash_state(uid)
        elif path == "/app/api/crash/cashout":
            coro = web_crash_cashout(uid)
        elif path == "/app/api/frog/start":
            coro = web_frog_start(uid, body.get("bet"), body.get("mode"))
        elif path == "/app/api/frog/step":
            coro = web_frog_step(uid, body.get("col"))
        elif path == "/app/api/frog/cashout":
            coro = web_frog_cashout(uid)
        elif path == "/app/api/kami/start":
            coro = web_kami_start(uid, body.get("bet"))
        elif path == "/app/api/kami/step":
            coro = web_kami_step(uid, body.get("row"))
        elif path == "/app/api/kami/cashout":
            coro = web_kami_cashout(uid)
        elif path == "/app/api/kami/state":
            coro = web_kami_state(uid)
        elif path == "/app/api/shop/buy":
            coro = web_shop_buy(uid, body.get("gift"), body.get("to"))
        elif path == "/app/api/bank/loan":
            coro = web_bank_loan(uid, body.get("bank"), body.get("amount"), body.get("days"), body.get("purpose"))
        elif path == "/app/api/bank/repay":
            coro = web_bank_repay(uid)
        elif path == "/app/api/bank/deposit":
            coro = web_bank_deposit(uid, body.get("bank"), body.get("amount"), body.get("days"))
        elif path == "/app/api/birja/buy":
            coro = web_birja_buy(uid, body.get("asset"), body.get("usd"))
        elif path == "/app/api/birja/sell":
            coro = web_birja_sell(uid, body.get("asset"), body.get("pct"))
        elif path == "/app/api/chat/find":
            coro = web_chat_find(uid, body.get("q"))
        elif path == "/app/api/chat/list":
            coro = web_chat_list(uid)
        elif path == "/app/api/chat/history":
            coro = web_chat_history(uid, body.get("with"), body.get("after"))
        elif path == "/app/api/chat/send":
            coro = web_chat_send(uid, body.get("to"), body.get("text"))
        elif path == "/app/api/chat/block":
            coro = web_chat_block(uid, body.get("with"), bool(body.get("on")))
        elif path == "/app/api/pair/propose":
            coro = web_pair_propose(uid, body.get("q"))
        elif path == "/app/api/randpair/find":
            coro = web_randpair(uid)
        elif path == "/app/api/randpair/cancel":
            coro = web_randpair_cancel(uid)
        elif path == "/app/api/avatar/save":
            coro = web_avatar_save(uid, body.get("avatar"))
        elif path == "/app/api/kid/outfit":
            coro = web_kid_outfit(uid, body.get("kid"), body.get("outfit"))
        elif path == "/app/api/edu/enroll":
            coro = web_edu_enroll(uid, body.get("kid"), body.get("inst"))
        elif path in ("/app/api/edu/add", "/app/api/edu/update", "/app/api/edu/toggle"):
            coro = web_edu_admin(uid, path.rsplit("/", 1)[1], body)
        elif path == "/app/api/kid":
            coro = web_kid_action(uid, body.get("kid"), body.get("act"), body.get("item"))
        else:
            self._send(404, {"ok": False})
            return
        try:
            res = asyncio.run_coroutine_threadsafe(coro, _EXCHANGE_LOOP).result(timeout=10)
        except Exception as e:  # noqa: BLE001
            logger.warning("WebApp API %s xato: %s", path, e)
            self._send(500, {"ok": False, "error": "internal"})
            return
        self._send(200, {"ok": True, **res})

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path.startswith("/app/api/"):
            self._web_api(path)
            return
        if path != "/exchange/credit":
            self._send(404, {"ok": False})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
        except (ValueError, OSError):
            self._send(400, {"ok": False, "error": "body"})
            return
        if not EXCHANGE_SECRET:
            self._send(503, {"ok": False, "error": "disabled"})
            return
        sig = self.headers.get("X-Signature", "")
        if not hmac.compare_digest(sig, exch_sign(raw)):
            self._send(401, {"ok": False, "error": "bad_signature"})
            return
        try:
            data = json.loads(raw.decode())
            txid = str(data["txid"])[:80]
            user_id = int(data["user_id"])
            amount = int(data["amount"])
            ts = int(data.get("ts", 0))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            self._send(400, {"ok": False, "error": "bad_json"})
            return
        if abs(time.time() - ts) > EXCHANGE_TS_WINDOW:
            self._send(401, {"ok": False, "error": "stale"})
            return
        if _EXCHANGE_LOOP is None:
            self._send(503, {"ok": False, "error": "starting"})
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(
                exchange_apply_incoming(txid, user_id, amount), _EXCHANGE_LOOP)
            ok, payload = fut.result(timeout=EXCHANGE_HTTP_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            logger.warning("Almashuv: kiruvchi so'rov bajarilmadi: %s", e)
            self._send(500, {"ok": False, "error": "internal"})
            return
        self._send(200 if ok else 409, {"ok": ok, **payload})


def exchange_start_server(application):
    """Kiruvchi HTTP serverni alohida ipda ishga tushiradi (PORT va kalit bo'lsa)."""
    global _EXCHANGE_LOOP, _EXCHANGE_SERVER, _EXCHANGE_LOOP_BOT
    _EXCHANGE_LOOP = asyncio.get_running_loop()
    _EXCHANGE_LOOP_BOT = application.bot
    # Server PORT bo'lsa ishga tushadi (web app uchun); almashuv yo'llari EXCHANGE_SECRET bo'lsa ishlaydi.
    if not EXCHANGE_PORT.isdigit():
        logger.info("HTTP server ishga tushmadi (PORT yo'q) — web app va almashuv o'chiq.")
        return
    try:
        _EXCHANGE_SERVER = ThreadingHTTPServer(("0.0.0.0", int(EXCHANGE_PORT)), _ExchangeHandler)
    except OSError as e:
        logger.warning("HTTP server portga bog'lanmadi (%s): %s", EXCHANGE_PORT, e)
        return
    threading.Thread(target=_EXCHANGE_SERVER.serve_forever, name="http-server", daemon=True).start()
    logger.info("HTTP server ishga tushdi: port %s (web app%s)",
                EXCHANGE_PORT, ", almashuv" if EXCHANGE_SECRET else "")


# ── Chiquvchi: bizning foydalanuvchi hamkor botga pul yuboradi ──

def _exch_post(txid, user_id, amount):
    """Hamkorga imzolangan so'rov (alohida ipda chaqiriladi). Qaytaradi: (holat, javob)."""
    body = json.dumps({"txid": txid, "user_id": user_id, "amount": amount, "ts": int(time.time())}).encode()
    req = urllib.request.Request(
        EXCHANGE_PARTNER_URL + "/exchange/credit", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Signature": exch_sign(body)})
    try:
        with urllib.request.urlopen(req, timeout=EXCHANGE_HTTP_TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:  # noqa: BLE001
            return e.code, {}
    except Exception as e:  # noqa: BLE001 — tarmoq/timeout: noaniq, qaytarmaymiz
        return 0, {"error": str(e)[:80]}


async def exchange_finalize_out(txid, uid):
    """Pending 'out' o'tkazmani hamkorga yuborib yakunlaydi. True — hal bo'ldi (done/failed)."""
    row = db().execute("SELECT amount, net FROM exchange_txns WHERE txid=? AND status='pending'", (txid,)).fetchone()
    if not row:
        return True
    gross, net = row
    status, resp = await asyncio.to_thread(_exch_post, txid, uid, net)
    c = db()
    if status == 200 and resp.get("ok"):
        with c:
            c.execute("UPDATE exchange_txns SET status='done' WHERE txid=? AND status='pending'", (txid,))
        try:
            await _EXCHANGE_LOOP_BOT.send_message(
                uid, exch_t(uid, "sent", partner=escape(EXCHANGE_PARTNER_NAME), net=fmt_money(net)))
        except TelegramError:
            pass
        await log_money_event(
            _EXCHANGE_LOOP_BOT,
            f"💱 <b>ALMASHUV (chiqdi)</b> · {escape(EXCHANGE_PARTNER_NAME)}\n{person_name(uid)}: −{gross}$ (hamkorga {net}$, txid {txid})")
        return True
    # Aniq rad (imzo/summа/o'chiq) — to'liq summani qaytaramiz.
    if status in (400, 401, 403, 404, 409, 503) and resp.get("error") != "starting":
        with c:
            cur = c.execute("UPDATE exchange_txns SET status='failed' WHERE txid=? AND status='pending'", (txid,))
            if cur.rowcount == 1:
                _wallet_add(c, uid, gross)
        if cur.rowcount == 1:
            try:
                await _EXCHANGE_LOOP_BOT.send_message(uid, exch_t(uid, "failed"))
            except TelegramError:
                pass
            await log_money_event(
                _EXCHANGE_LOOP_BOT,
                f"💱 <b>ALMASHUV QAYTDI</b>\n{person_name(uid)}: +{gross}$ (txid {txid}, sabab {resp.get('error')})")
        return True
    # Noaniq (timeout/5xx/tarmoq) — qaytarmaymiz, keyin qayta urinamiz.
    with c:
        c.execute("UPDATE exchange_txns SET retries=retries+1 WHERE txid=? AND status='pending'", (txid,))
    return False


async def exchange_send(uid, amount):
    """Foydalanuvchi $ ni hamkorga yuboradi. Qaytaradi: 'done' | 'pending' | xato kaliti."""
    cfg = exch_config()
    if not exch_ready() or not EXCHANGE_PARTNER_URL:
        return "off"
    if active_loan(uid):
        return "loan"
    if amount < EXCHANGE_MIN:
        return "too_small"
    fee = round(amount * cfg["fee_pct"] / 100)
    net = amount - fee
    if net <= 0:
        return "too_small"
    if exch_today_out(uid) + amount > cfg["daily_limit"]:
        return "limit"
    txid = f"se-{uid}-{secrets.token_hex(8)}"
    c = db()
    with c:
        if not _wallet_take(c, uid, amount):
            return "no_funds"
        c.execute(
            "INSERT INTO exchange_txns(txid, direction, user_id, amount, net, status, created_at) "
            "VALUES (?, 'out', ?, ?, ?, 'pending', ?)",
            (txid, uid, amount, net, int(time.time())),
        )
    done = await exchange_finalize_out(txid, uid)
    if not done:
        return "pending"
    row = db().execute("SELECT status FROM exchange_txns WHERE txid=?", (txid,)).fetchone()
    return "done" if row and row[0] == "done" else "failed"


async def exchange_retry_worker(application):
    while True:
        await asyncio.sleep(EXCHANGE_RETRY_TICK)
        try:
            if not EXCHANGE_PARTNER_URL:
                continue
            rows = db().execute(
                "SELECT txid, user_id, amount, retries FROM exchange_txns WHERE direction='out' AND status='pending'"
            ).fetchall()
            for txid, uid, amount, retries in rows:
                if retries >= EXCHANGE_MAX_RETRY:
                    await log_money_event(
                        application.bot,
                        f"⚠️ <b>ALMASHUV OSILIB QOLDI</b>\n{person_name(uid)}: {amount}$ (txid {txid}) — qo‘lda tekshiring.")
                    with db() as c:
                        c.execute("UPDATE exchange_txns SET status='stuck' WHERE txid=?", (txid,))
                    continue
                await exchange_finalize_out(txid, uid)
        except Exception:  # noqa: BLE001
            logger.exception("Almashuv: qayta urinishda xato")


# ── UI: foydalanuvchi menyusi ──

def exchange_menu_view(uid):
    cfg = exch_config()
    if not exch_ready() or not EXCHANGE_PARTNER_URL:
        return exch_t(uid, "off"), None
    left = max(0, cfg["daily_limit"] - exch_today_out(uid))
    text = exch_t(uid, "title", partner=escape(EXCHANGE_PARTNER_NAME), wallet=fmt_money(wallet_balance(uid)),
                  fee=f"{cfg['fee_pct']:g}", left=fmt_money(left))
    buttons = [InlineKeyboardButton(f"{fmt_money(a)}$", callback_data=f"ex:{uid}:a:{a}") for a in EXCHANGE_AMOUNTS]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return text, InlineKeyboardMarkup(rows)


async def cb_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    uid = int(parts[1])
    action = parts[2]
    if q.from_user.id != uid:
        await q.answer(exch_t(uid, "not_yours"), show_alert=True)
        return
    chat_id = q.message.chat.id
    if not exch_ready() or not EXCHANGE_PARTNER_URL:
        await q.answer(exch_t(uid, "off"), show_alert=True)
        return
    cfg = exch_config()

    if action == "menu":
        await q.answer()
        text, kb = exchange_menu_view(uid)
        await edit(context.bot, chat_id, q.message.message_id, text, kb)
        return

    amount = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    if amount not in EXCHANGE_AMOUNTS:
        await q.answer()
        return

    if action == "a":
        if wallet_balance(uid) < amount:
            await q.answer(exch_t(uid, "no_funds", bal=fmt_money(wallet_balance(uid))), show_alert=True)
            return
        fee = round(amount * cfg["fee_pct"] / 100)
        await q.answer()
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(exch_t(uid, "b_confirm"), callback_data=f"ex:{uid}:go:{amount}"),
            InlineKeyboardButton(exch_t(uid, "b_cancel"), callback_data=f"ex:{uid}:menu"),
        ]])
        await edit(context.bot, chat_id, q.message.message_id, exch_t(
            uid, "confirm", amount=fmt_money(amount), fee=fmt_money(fee),
            net=fmt_money(amount - fee), partner=escape(EXCHANGE_PARTNER_NAME)), kb)
        return

    if action == "go":
        await q.answer()
        result = await exchange_send(uid, amount)
        keys = {"no_funds": ("no_funds", {"bal": fmt_money(wallet_balance(uid))}), "loan": ("loan", {}),
                "limit": ("limit", {}), "too_small": ("too_small", {"min": EXCHANGE_MIN}), "off": ("off", {})}
        if result == "done":
            fee = round(amount * cfg["fee_pct"] / 100)
            msg = exch_t(uid, "sent", partner=escape(EXCHANGE_PARTNER_NAME), net=fmt_money(amount - fee))
        elif result == "pending":
            msg = exch_t(uid, "pending")
        elif result == "failed":
            msg = exch_t(uid, "failed")
        else:
            key, kw = keys.get(result, ("off", {}))
            msg = exch_t(uid, key, **kw)
        text, kb = exchange_menu_view(uid)
        await edit(context.bot, chat_id, q.message.message_id, msg + "\n\n" + (text or ""), kb)
        return

    await q.answer()


# ── 👑 Owner panel: ko'rsatkichlarni tahrirlash (faqat ko'rinish) ──

PANEL_STAT_KEYS = [
    ("users", "👤 Foydalanuvchilar"), ("groups", "🏘 Guruhlar"),
    ("active", "🎮 Faol o‘yinlar"), ("games_total", "📈 Jami ishtiroklar"),
]
PANEL_STAT_CANCEL = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="panel:stats_edit")]])


def init_panel_overrides():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS panel_overrides (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")


def stat_show(key, real):
    """Owner panel ko'rsatkichi: qo'lda belgilangani bo'lsa — o'sha, bo'lmasa haqiqiy son."""
    row = db().execute("SELECT value FROM panel_overrides WHERE key=?", (key,)).fetchone()
    return row[0] if row else real


def set_override(key, value):
    with db() as c:
        if value is None:
            c.execute("DELETE FROM panel_overrides WHERE key=?", (key,))
        else:
            c.execute(
                "INSERT INTO panel_overrides(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, int(value)))


def panel_stats_edit_view():
    lines = [
        "🔢 <b>KO‘RSATKICHLARNI TAHRIRLASH</b>", "",
        "Bu faqat <b>panel ko‘rinishiga</b> ta’sir qiladi — haqiqiy bazaga tegmaydi.", "",
    ]
    rows = []
    c = db()
    for key, label in PANEL_STAT_KEYS:
        row = c.execute("SELECT value FROM panel_overrides WHERE key=?", (key,)).fetchone()
        lines.append(f"{label}: <b>{'✍️ ' + fmt_money(row[0]) if row else '🔄 avto'}</b>")
        rows.append([
            InlineKeyboardButton(f"✍️ {label}", callback_data=f"panel:stat_set:{key}"),
            InlineKeyboardButton("🔄 Avto", callback_data=f"panel:stat_auto:{key}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def panel_stats_callback(query, context):
    parts = query.data.split(":")
    action = parts[1]
    context.user_data.pop("panel_stat_state", None)
    if action == "stat_set" and len(parts) > 2 and parts[2] in dict(PANEL_STAT_KEYS):
        context.user_data["panel_stat_state"] = parts[2]
        label = dict(PANEL_STAT_KEYS)[parts[2]]
        await query.edit_message_text(
            f"✍️ <b>{label}</b> uchun ko‘rsatiladigan sonni yuboring (0 dan katta butun son):",
            reply_markup=PANEL_STAT_CANCEL)
        return
    if action == "stat_auto" and len(parts) > 2:
        set_override(parts[2], None)
    text, kb = panel_stats_edit_view()
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def cmd_taxrir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return
    if user.id not in CAREER_OWNER_IDS:
        await msg.reply_text("⛔ Bu buyruq faqat bot egalari uchun.")
        return
    text, kb = panel_stats_edit_view()
    await msg.reply_text(text, reply_markup=kb)


async def cmd_haqiqiy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return
    if user.id not in CAREER_OWNER_IDS:
        await msg.reply_text("⛔ Bu buyruq faqat bot egalari uchun.")
        return
    c = db()
    users_count = bot_users_count(c)
    seen_count = seen_users_count(c)
    groups = len(panel_group_ids(c))
    total_games = c.execute("SELECT COALESCE(SUM(games), 0) FROM chat_stats").fetchone()[0]
    over = {k: v for k, v in c.execute("SELECT key, value FROM panel_overrides")}
    note = "\n\n✍️ Hozir tahrirlangan ko‘rsatkichlar bor — panelda boshqa son chiqadi. /taxrir orqali sozlang." if over else ""
    await msg.reply_text(
        "📊 <b>HAQIQIY STATISTIKA</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{users_count}</b>\n"
        f"👥 Guruhlarda ko‘rilgan: <b>{seen_count}</b>\n"
        f"🏘 Guruhlar: <b>{groups}</b>\n"
        f"🎮 Faol o‘yinlar: <b>{len(GAMES)}</b>\n"
        f"📈 Jami ishtiroklar: <b>{total_games}</b>" + note
    )


async def panel_stats_text(update, context):
    key = context.user_data.get("panel_stat_state")
    msg = update.effective_message
    raw = (msg.text or "").strip().replace(" ", "")
    if not raw.isdigit() or len(raw) > 15:
        await msg.reply_text("❌ Faqat musbat butun son yuboring:", reply_markup=PANEL_STAT_CANCEL)
        return
    set_override(key, int(raw))
    context.user_data.pop("panel_stat_state", None)
    text, kb = panel_stats_edit_view()
    await msg.reply_text("✅ Saqlandi.\n\n" + text, reply_markup=kb)


# ── 📢 Majburiy obuna (force subscribe) ──
# Owner panel orqali kanal @username bilan ulanadi. Obuna bo'lmagan a'zo o'yin o'ynay olmaydi.
# Bot kanalda admin bo'lishi shart — aks holda a'zolikni tekshira olmaydi (bunday holatda fail-open:
# hamma uchun bloklab qo'ymaslik uchun ruxsat beriladi).

_FSUB_CACHE: dict[int, float] = {}   # user_id -> obuna tasdiqlangan "muddat" (epoch)
FSUB_CACHE_TTL = 300                  # ijobiy natijani 5 daqiqa eslab turamiz

FSUB_TEXT = {
    "uz": {
        "alert": "📢 O‘ynash uchun avval kanalga obuna bo‘ling!",
        "prompt": ("📢 <b>Majburiy obuna</b>\n\n"
                   "O‘yinlarni o‘ynash uchun avval kanalimizga obuna bo‘ling:\n{ch}\n\n"
                   "Obuna bo‘lgach, «✅ Tekshirish» tugmasini bosing."),
        "btn_join": "📢 Kanalga obuna bo‘lish",
        "btn_check": "✅ Tekshirish",
        "ok": "✅ Obuna tasdiqlandi! Endi o‘ynashingiz mumkin.",
        "ok_msg": "✅ Obuna tasdiqlandi! Endi o‘yinlarni o‘ynashingiz mumkin.",
        "still": "❌ Hali obuna bo‘lmagansiz. Obuna bo‘lib, qayta tekshiring.",
    },
    "eng": {
        "alert": "📢 Subscribe to the channel first to play!",
        "prompt": ("📢 <b>Subscription required</b>\n\n"
                   "To play the games, first subscribe to our channel:\n{ch}\n\n"
                   "After subscribing, tap «✅ Check»."),
        "btn_join": "📢 Subscribe to channel",
        "btn_check": "✅ Check",
        "ok": "✅ Subscription confirmed! You can play now.",
        "ok_msg": "✅ Subscription confirmed! You can play the games now.",
        "still": "❌ You are not subscribed yet. Subscribe and check again.",
    },
    "ru": {
        "alert": "📢 Сначала подпишитесь на канал, чтобы играть!",
        "prompt": ("📢 <b>Обязательная подписка</b>\n\n"
                   "Чтобы играть, сначала подпишитесь на наш канал:\n{ch}\n\n"
                   "После подписки нажмите «✅ Проверить»."),
        "btn_join": "📢 Подписаться на канал",
        "btn_check": "✅ Проверить",
        "ok": "✅ Подписка подтверждена! Теперь можно играть.",
        "ok_msg": "✅ Подписка подтверждена! Теперь вы можете играть.",
        "still": "❌ Вы ещё не подписаны. Подпишитесь и проверьте снова.",
    },
    "kz": {
        "alert": "📢 Ойнау үшін алдымен арнаға жазылыңыз!",
        "prompt": ("📢 <b>Міндетті жазылым</b>\n\n"
                   "Ойындарды ойнау үшін алдымен арнамызға жазылыңыз:\n{ch}\n\n"
                   "Жазылғаннан кейін «✅ Тексеру» түймесін басыңыз."),
        "btn_join": "📢 Арнаға жазылу",
        "btn_check": "✅ Тексеру",
        "ok": "✅ Жазылым расталды! Енді ойнай аласыз.",
        "ok_msg": "✅ Жазылым расталды! Енді ойындарды ойнай аласыз.",
        "still": "❌ Сіз әлі жазылмағансыз. Жазылып, қайта тексеріңіз.",
    },
}


def fsub_t(chat_id, key, **kw):
    lang = LANG_CACHE.get(chat_id, DEFAULT_LANG)
    d = FSUB_TEXT.get(lang) or FSUB_TEXT[DEFAULT_LANG]
    s = d.get(key) or FSUB_TEXT[DEFAULT_LANG][key]
    return s.format(**kw) if kw else s


def init_forcesub():
    with db() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS forcesub ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "channel_id INTEGER, username TEXT, title TEXT, "
            "enabled INTEGER NOT NULL DEFAULT 0)"
        )


def fsub_get():
    row = db().execute(
        "SELECT channel_id, username, title, enabled FROM forcesub WHERE id = 1"
    ).fetchone()
    if not row:
        return None
    return {"channel_id": row[0], "username": row[1], "title": row[2], "enabled": bool(row[3])}


def fsub_set(**fields):
    """forcesub yozuvini yangilaydi (bo'lmasa yaratadi)."""
    cur = fsub_get() or {"channel_id": None, "username": None, "title": None, "enabled": False}
    cur.update(fields)
    with db() as c:
        c.execute(
            "INSERT INTO forcesub (id, channel_id, username, title, enabled) "
            "VALUES (1, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "channel_id=excluded.channel_id, username=excluded.username, "
            "title=excluded.title, enabled=excluded.enabled",
            (cur["channel_id"], cur["username"], cur["title"], 1 if cur["enabled"] else 0),
        )


def fsub_clear():
    with db() as c:
        c.execute("DELETE FROM forcesub WHERE id = 1")


def fsub_active():
    """Majburiy obuna yoqilgan va kanal ulangan bo'lsa — config, aks holda None."""
    cfg = fsub_get()
    if cfg and cfg["enabled"] and cfg["channel_id"]:
        return cfg
    return None


async def fsub_is_member(bot, user_id):
    """Foydalanuvchi ulangan kanalga a'zomi? Majburiy obuna o'chiq bo'lsa — True.
    Bot kanalni tekshira olmasa (admin emas / xato) — True (fail-open)."""
    cfg = fsub_active()
    if not cfg:
        return True
    if user_id in CAREER_OWNER_IDS:
        return True
    now = time.time()
    if _FSUB_CACHE.get(user_id, 0) > now:
        return True
    try:
        member = await bot.get_chat_member(cfg["channel_id"], user_id)
    except TelegramError as e:
        logger.warning("Majburiy obuna: %s uchun tekshirib bo'lmadi: %s", user_id, e)
        return True
    ok = member.status in (
        ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER,
    )
    if ok:
        _FSUB_CACHE[user_id] = now + FSUB_CACHE_TTL
    else:
        _FSUB_CACHE.pop(user_id, None)
    return ok


def fsub_prompt_kb(chat_id, cfg):
    rows = []
    if cfg.get("username"):
        rows.append([InlineKeyboardButton(
            fsub_t(chat_id, "btn_join"), url=f"https://t.me/{cfg['username']}")])
    rows.append([InlineKeyboardButton(fsub_t(chat_id, "btn_check"), callback_data="fsub:check")])
    return InlineKeyboardMarkup(rows)


def fsub_channel_label(cfg):
    if cfg.get("username"):
        return "@" + cfg["username"]
    return escape(cfg.get("title") or "kanal")


async def fsub_block_cb(query, context):
    """Callback-dan chaqiriladi. Obuna bo'lmasa — ogohlantiradi va True qaytaradi (to'xtatish kerak)."""
    cfg = fsub_active()
    if not cfg:
        return False
    user = query.from_user
    if await fsub_is_member(context.bot, user.id):
        return False
    chat_id = query.message.chat.id if query.message else user.id
    try:
        await query.answer(fsub_t(chat_id, "alert"), show_alert=True)
    except TelegramError:
        pass
    try:
        await context.bot.send_message(
            chat_id,
            fsub_t(chat_id, "prompt", ch=fsub_channel_label(cfg)),
            reply_markup=fsub_prompt_kb(chat_id, cfg),
        )
    except TelegramError:
        pass
    return True


async def fsub_block_msg(update, context):
    """Matnli (guruhdagi) o'yin javobidan chaqiriladi. Obuna bo'lmasa — True qaytaradi."""
    cfg = fsub_active()
    if not cfg:
        return False
    user = update.effective_user
    if await fsub_is_member(context.bot, user.id):
        return False
    chat_id = update.effective_chat.id
    try:
        await update.effective_message.reply_text(
            fsub_t(chat_id, "prompt", ch=fsub_channel_label(cfg)),
            reply_markup=fsub_prompt_kb(chat_id, cfg),
        )
    except TelegramError:
        pass
    return True


async def cb_fsub_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    user = q.from_user
    chat_id = q.message.chat.id if q.message else user.id
    cfg = fsub_active()
    if not cfg:
        await q.answer()
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            pass
        return
    _FSUB_CACHE.pop(user.id, None)   # yangi tekshiruv
    if await fsub_is_member(context.bot, user.id):
        await q.answer(fsub_t(chat_id, "ok"), show_alert=True)
        try:
            await q.edit_message_text(fsub_t(chat_id, "ok_msg"))
        except TelegramError:
            pass
    else:
        await q.answer(fsub_t(chat_id, "still"), show_alert=True)


# ── 👑 Owner panel: majburiy obuna sozlamalari ──

PANEL_FSUB_CANCEL = InlineKeyboardMarkup([[
    InlineKeyboardButton("⬅️ Orqaga", callback_data="panel:fsub")
]])


def panel_fsub_view():
    cfg = fsub_get()
    lines = ["📢 <b>MAJBURIY OBUNA</b>", ""]
    if cfg and cfg["channel_id"]:
        on = "✅ yoqilgan" if cfg["enabled"] else "❌ o‘chiq"
        ch = ("@" + cfg["username"]) if cfg["username"] else str(cfg["channel_id"])
        lines.append(f"Kanal: <b>{escape(cfg['title'] or ch)}</b> ({ch})")
        lines.append(f"Holat: <b>{on}</b>")
        lines.append("")
        lines.append("Obuna bo‘lmagan a’zolar o‘yin o‘ynay olmaydi.")
        rows = [
            [InlineKeyboardButton(
                "🔴 O‘chirish" if cfg["enabled"] else "🟢 Yoqish",
                callback_data="panel:fsub_toggle")],
            [InlineKeyboardButton("♻️ Kanalni almashtirish", callback_data="panel:fsub_set")],
            [InlineKeyboardButton("🗑 Kanalni uzish", callback_data="panel:fsub_del")],
            [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
        ]
    else:
        lines.append("Hali kanal ulanmagan.")
        lines.append("")
        lines.append("Kanal <b>@username</b> orqali ulanadi. Bot o‘sha kanalda <b>admin</b> bo‘lishi shart.")
        rows = [
            [InlineKeyboardButton("➕ Kanal ulash", callback_data="panel:fsub_set")],
            [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
        ]
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def panel_fsub_callback(query, context):
    data = query.data
    if data == "panel:fsub":
        context.user_data.pop("panel_fsub_state", None)
        text, kb = panel_fsub_view()
        try:
            await query.edit_message_text(text, reply_markup=kb)
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                raise
        return
    if data == "panel:fsub_set":
        context.user_data["panel_fsub_state"] = "waiting_channel"
        await query.edit_message_text(
            "📢 Kanal <b>@username</b> sini yuboring (masalan: <code>@mychannel</code>).\n\n"
            "⚠️ Bot o‘sha kanalda <b>admin</b> bo‘lishi shart — aks holda obunani tekshira olmaydi.",
            reply_markup=PANEL_FSUB_CANCEL,
        )
        return
    if data == "panel:fsub_toggle":
        cfg = fsub_get()
        if not cfg or not cfg["channel_id"]:
            await query.answer("Avval kanal ulang.", show_alert=True)
            return
        fsub_set(enabled=0 if cfg["enabled"] else 1)
        _FSUB_CACHE.clear()
        text, kb = panel_fsub_view()
        await query.edit_message_text(text, reply_markup=kb)
        return
    if data == "panel:fsub_del":
        fsub_clear()
        _FSUB_CACHE.clear()
        context.user_data.pop("panel_fsub_state", None)
        text, kb = panel_fsub_view()
        await query.edit_message_text("🗑 Kanal uzildi.\n\n" + text, reply_markup=kb)
        return


async def panel_fsub_text(update, context):
    msg = update.effective_message
    raw = (msg.text or "").strip()
    # @username, t.me/username yoki oddiy username qabul qilamiz
    name = raw
    if "t.me/" in name:
        name = name.split("t.me/", 1)[1]
    name = name.lstrip("@").strip().strip("/").split("/")[0].split("?")[0]
    if not re.fullmatch(r"[A-Za-z0-9_]{4,32}", name):
        await msg.reply_text(
            "❌ To‘g‘ri @username yuboring (masalan: <code>@mychannel</code>).",
            reply_markup=PANEL_FSUB_CANCEL,
        )
        return
    try:
        chat_obj = await context.bot.get_chat("@" + name)
    except TelegramError:
        await msg.reply_text(
            "❌ Kanal topilmadi. @username to‘g‘riligini va botni kanalga qo‘shganingizni tekshiring.",
            reply_markup=PANEL_FSUB_CANCEL,
        )
        return
    if chat_obj.type not in (ChatType.CHANNEL, ChatType.SUPERGROUP):
        await msg.reply_text(
            "❌ Bu kanal (yoki superguruh) emas. Faqat kanal/superguruh ulash mumkin.",
            reply_markup=PANEL_FSUB_CANCEL,
        )
        return
    # Bot o'sha kanalda admin ekanligini tekshiramiz
    try:
        me = await context.bot.get_chat_member(chat_obj.id, context.bot.id)
        if me.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await msg.reply_text(
                "⚠️ Bot bu kanalda admin emas. Avval botni kanalga admin qiling, keyin qayta urinib ko‘ring.",
                reply_markup=PANEL_FSUB_CANCEL,
            )
            return
    except TelegramError:
        await msg.reply_text(
            "⚠️ Botning kanaldagi holatini tekshirib bo‘lmadi. Botni kanalga admin qiling va qayta urinib ko‘ring.",
            reply_markup=PANEL_FSUB_CANCEL,
        )
        return
    fsub_set(
        channel_id=chat_obj.id,
        username=chat_obj.username or name,
        title=chat_obj.title or "",
        enabled=1,
    )
    _FSUB_CACHE.clear()
    context.user_data.pop("panel_fsub_state", None)
    text, kb = panel_fsub_view()
    await msg.reply_text("✅ Kanal ulandi va majburiy obuna yoqildi.\n\n" + text, reply_markup=kb)


# ── 👑 Owner panel: 🔄 Qayta ro'yxatdan o'tish ruxsati ──

PANEL_REREG_BACK = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="panel:rereg")]])


def panel_rereg_view():
    on = rereg_all_on()
    ids = [r[0] for r in db().execute("SELECT user_id FROM rereg_users ORDER BY user_id")]
    lines = ["🔄 <b>QAYTA RO‘YXATDAN O‘TISH</b>", "",
             "Profilda «🔄 Qayta ro‘yxatdan o‘tish» tugmasi chiqadi: jins, yosh va kasb qayta tanlanadi.", "",
             f"👥 Hamma uchun: <b>{'✅ yoqilgan' if on else '❌ o‘chiq'}</b>",
             f"👤 Alohida ruxsat berilganlar ({len(ids)}):"]
    lines += [f"• {person_name(i)} — <code>{i}</code>" for i in ids[:30]] or ["—"]
    rows = [
        [InlineKeyboardButton("🔴 Hamma uchun o‘chirish" if on else "🟢 Hamma uchun yoqish", callback_data="panel:rereg_all")],
        [InlineKeyboardButton("➕ Bir kishiga yoqish", callback_data="panel:rereg_add"),
         InlineKeyboardButton("➖ Bir kishidan o‘chirish", callback_data="panel:rereg_del")],
        [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def panel_rereg_callback(query, context):
    data = query.data
    context.user_data.pop("panel_rereg_state", None)
    if data == "panel:rereg_all":
        with db() as c:
            c.execute("INSERT INTO rereg_config(key, value) VALUES ('all', ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (0 if rereg_all_on() else 1,))
    elif data in ("panel:rereg_add", "panel:rereg_del"):
        context.user_data["panel_rereg_state"] = "add" if data.endswith("add") else "del"
        await query.edit_message_text(
            ("➕ Ruxsat beriladigan" if data.endswith("add") else "➖ Ruxsati olinadigan")
            + " foydalanuvchining <b>ID</b> sini yoki <b>@username</b> ini yuboring:",
            reply_markup=PANEL_REREG_BACK)
        return
    text, kb = panel_rereg_view()
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def panel_rereg_text(update, context):
    msg = update.effective_message
    raw = (msg.text or "").strip()
    uid = None
    if raw.startswith("@"):
        row = db().execute("SELECT user_id FROM users WHERE lower(username)=lower(?)", (raw[1:],)).fetchone()
        uid = row[0] if row else None
    elif raw.lstrip("-").isdigit():
        uid = int(raw)
    if not uid:
        await msg.reply_text("❌ Foydalanuvchi topilmadi. ID (raqam) yoki @username yuboring.", reply_markup=PANEL_REREG_BACK)
        return
    state = context.user_data.pop("panel_rereg_state", None)
    with db() as c:
        if state == "add":
            c.execute("INSERT OR IGNORE INTO rereg_users(user_id) VALUES (?)", (uid,))
        else:
            c.execute("DELETE FROM rereg_users WHERE user_id=?", (uid,))
    text, kb = panel_rereg_view()
    note = f"✅ <code>{uid}</code> ga ruxsat berildi." if state == "add" else f"✅ <code>{uid}</code> dan ruxsat olindi."
    await msg.reply_text(note + "\n\n" + text, reply_markup=kb)


# ── 👑 Owner panel: 🌐 Web App ──

def panel_webapp_view():
    flags = webapp_flags()
    url = (WEBAPP_URL + "/app") if WEBAPP_URL else None
    lines = ["🌐 <b>WEB APP</b>", ""]
    if url:
        lines.append(f"🔗 Manzil: <code>{escape(url)}</code>")
    else:
        lines.append("⚠️ Domen yo‘q. Railway → Settings → Networking → <b>Generate Domain</b> oling,\n"
                     "so‘ng <code>WEBAPP_URL</code> (yoki <code>RAILWAY_PUBLIC_DOMAIN</code>) env qo‘shing.")
    lines += ["",
              f"👥 Hamma uchun: <b>{'✅ yoqilgan' if flags['all'] else '❌ o‘chiq'}</b>",
              f"👑 Ownerlar uchun: <b>{'✅ yoqilgan' if flags['owner'] else '❌ o‘chiq'}</b>",
              f"🛩 Kamikaze: <b>{'✅ hamma uchun' if flags.get('kami') else '🧪 faqat ownerlar (test)'}</b>",
              f"🧍 3D avatar: <b>{'✅ hamma uchun' if flags.get('avatar') else '🧪 faqat ownerlar (test)'}</b>"]
    rows = [
        [InlineKeyboardButton("🔴 Hamma uchun o‘chirish" if flags["all"] else "🟢 Hamma uchun yoqish",
                              callback_data="panel:webapp_all")],
        [InlineKeyboardButton("🔴 Ownerlar uchun o‘chirish" if flags["owner"] else "🟢 Ownerlar uchun yoqish",
                              callback_data="panel:webapp_owner")],
        [InlineKeyboardButton("🧪 Kamikaze: faqat ownerlarga" if flags.get("kami") else "🛩 Kamikaze: hamma uchun ochish",
                              callback_data="panel:webapp_kami")],
        [InlineKeyboardButton("🧪 3D avatar: faqat ownerlarga" if flags.get("avatar") else "🧍 3D avatar: hamma uchun ochish",
                              callback_data="panel:webapp_avatar")],
        [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def panel_webapp_callback(query, context):
    data = query.data
    if data == "panel:webapp_all":
        webapp_set("all", 0 if webapp_flags()["all"] else 1)
    elif data == "panel:webapp_owner":
        webapp_set("owner", 0 if webapp_flags()["owner"] else 1)
    elif data == "panel:webapp_kami":
        webapp_set("kami", 0 if webapp_flags().get("kami") else 1)
    elif data == "panel:webapp_avatar":
        webapp_set("avatar", 0 if webapp_flags().get("avatar") else 1)
    text, kb = panel_webapp_view()
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ── 👑 Owner panel: almashuv sozlamalari ──

def panel_exchange_view():
    cfg = exch_config()
    on = "✅ yoqilgan" if cfg["enabled"] else "❌ o‘chiq"
    text = (
        "💱 <b>PUL ALMASHUVI</b>\n\n"
        f"Holat: <b>{on}</b>\n"
        f"🤝 Hamkor: <b>{escape(EXCHANGE_PARTNER_NAME)}</b>\n"
        f"🔑 Maxfiy kalit: {'✅ o‘rnatilgan' if EXCHANGE_SECRET else '❌ yo‘q (EXCHANGE_SECRET env)'}\n"
        f"🔗 Hamkor manzili: {'✅ o‘rnatilgan' if EXCHANGE_PARTNER_URL else '❌ yo‘q (EXCHANGE_PARTNER_URL env)'}\n"
        f"🖧 Kiruvchi server: {'✅ port ' + EXCHANGE_PORT if (EXCHANGE_SECRET and EXCHANGE_PORT.isdigit()) else '❌ ishlamayapti (PORT env + domen kerak)'}\n\n"
        f"💸 Komissiya: <b>{cfg['fee_pct']:g}%</b>\n"
        f"📅 Kunlik limit: <b>{fmt_money(cfg['daily_limit'])}$</b>\n\n"
        "ℹ️ Kalit va manzil Railway Variables orqali o‘rnatiladi."
    )
    rows = [
        [InlineKeyboardButton("🔴 O‘chirish" if cfg["enabled"] else "🟢 Yoqish", callback_data="panel:exch_toggle")],
        [InlineKeyboardButton("➖ Komissiya", callback_data="panel:exch_fee:down"),
         InlineKeyboardButton("➕ Komissiya", callback_data="panel:exch_fee:up")],
        [InlineKeyboardButton("➖ Limit", callback_data="panel:exch_lim:down"),
         InlineKeyboardButton("➕ Limit", callback_data="panel:exch_lim:up")],
        [InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="panel:home")],
    ]
    return text, InlineKeyboardMarkup(rows)


async def panel_exchange_callback(query, context):
    parts = query.data.split(":")
    action = parts[1]
    c = db()
    cfg = exch_config()
    if action == "exch_toggle":
        if not EXCHANGE_SECRET or not EXCHANGE_PARTNER_URL:
            await query.answer("Avval EXCHANGE_SECRET va EXCHANGE_PARTNER_URL ni Railway'da o‘rnating.", show_alert=True)
        else:
            with c:
                c.execute("UPDATE exchange_config SET enabled=1-enabled WHERE id=1")
            await query.answer()
    elif action == "exch_fee":
        val = min(50.0, max(0.0, cfg["fee_pct"] + (1 if parts[2] == "up" else -1)))
        with c:
            c.execute("UPDATE exchange_config SET fee_pct=? WHERE id=1", (val,))
        await query.answer()
    elif action == "exch_lim":
        val = max(1000, cfg["daily_limit"] + (10000 if parts[2] == "up" else -10000))
        with c:
            c.execute("UPDATE exchange_config SET daily_limit=? WHERE id=1", (val,))
        await query.answer()
    else:
        await query.answer()
    text, kb = panel_exchange_view()
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ───────────────────────────── 🌐 WEB APP (Telegram Mini App) ─────────────────────────────
# Botning mavjud HTTP serveridan (PORT) web app sahifasi (/app) va ma'lumot API'si (/app/api/data) uzatiladi.
# Foydalanuvchi Telegram initData (bot token bilan HMAC) orqali aniqlanadi. Owner panel → 🌐 Web App:
# hamma uchun yoqish/o'chirish va ownerlar uchun yoqish/o'chirish. URL: WEBAPP_URL (yoki RAILWAY_PUBLIC_DOMAIN).

WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
if not WEBAPP_URL:
    WEBAPP_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
# Scheme bo'lmasa (masalan faqat domen yozilgan bo'lsa) — https:// qo'shamiz
if WEBAPP_URL and not WEBAPP_URL.startswith(("http://", "https://")):
    WEBAPP_URL = "https://" + WEBAPP_URL


def init_webapp():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS webapp_config (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS user_avatar (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')")
        # 💬 Web chat: shaxsiy xabarlar va bloklar
        c.execute("""CREATE TABLE IF NOT EXISTS web_chat_msgs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
            text TEXT NOT NULL, created_at INTEGER NOT NULL, read INTEGER NOT NULL DEFAULT 0)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wchat_pair ON web_chat_msgs(from_id, to_id, id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wchat_unread ON web_chat_msgs(to_id, read)")
        c.execute("""CREATE TABLE IF NOT EXISTS web_chat_blocks (
            user_id INTEGER NOT NULL, blocked_id INTEGER NOT NULL, PRIMARY KEY(user_id, blocked_id))""")
        cols = {r[1] for r in c.execute("PRAGMA table_info(pair_requests)")}
        if cols and "random" not in cols:     # 💍 random juft so'rovlari belgisi
            c.execute("ALTER TABLE pair_requests ADD COLUMN random INTEGER NOT NULL DEFAULT 0")


# ── 🧍 Realistik 3D avatar (web app) — test: standart faqat ownerlar ──
AVATAR_SLOTS = ("g", "outfit", "shoes", "hat", "hair", "hcol", "skin", "bg")


def avatar_enabled_for(uid):
    if not web_enabled_for(uid):
        return False
    return bool(webapp_flags().get("avatar", 0)) or uid in CAREER_OWNER_IDS


def avatar_get(uid):
    row = db().execute("SELECT data FROM user_avatar WHERE user_id=?", (uid,)).fetchone()
    try:
        d = json.loads(row[0]) if row else {}
        return {k: v for k, v in d.items() if k in AVATAR_SLOTS and isinstance(v, str)}
    except (ValueError, TypeError):
        return {}


# ── 💍 Random juft (web app → Oila): faqat jufti yo'qlar, faqat qarama-qarshi jins ──
RANDPAIR_COOLDOWN = 60          # s — ketma-ket qidirishlar orasidagi minimal vaqt
RANDPAIR_TTL = 24 * 3600        # s — javobsiz random taklif shundan keyin eskiradi
RANDPAIR_REJECT_DAYS = 7        # rad etgan odamga shu muddat ichida qayta tushmaydi
RANDPAIR_TRIES = 3              # yetkazib bo'lmasa (botni bloklagan) — boshqa nomzod


def _iso_ago(sec):
    return (datetime.now() - timedelta(seconds=sec)).isoformat(timespec="seconds")


def user_card(uid):
    """Juftlik so'rovidagi ma'lumot kartasi: pul, reyting, daraja, kasb, yosh, ajrashganlik, farzandlar."""
    c = db()
    row = c.execute("SELECT first_name, username, birth_date, profession_id FROM users WHERE user_id=?", (uid,)).fetchone()
    name = (row[0] if row else None) or (row[1] if row else None) or str(uid)
    age = None
    if row and row[2]:
        try:
            b = date.fromisoformat(row[2]); t = date.today()
            age = t.year - b.year - ((t.month, t.day) < (b.month, b.day))
        except (ValueError, TypeError):
            age = None
    money = wallet_balance(uid)
    owners = tuple(CAREER_OWNER_IDS)
    marks = ",".join("?" * len(owners)) or "NULL"
    rank = None if uid in CAREER_OWNER_IDS else c.execute(
        f"SELECT COUNT(*)+1 FROM user_wallet WHERE money > ? AND user_id NOT IN ({marks})", (money, *owners)).fetchone()[0]
    points, games, wins, _l, _d = get_stats(None, uid, True)
    pid = row[3] if row else None
    divorces = c.execute("SELECT COUNT(*) FROM pairs WHERE status='ended' AND (user1_id=? OR user2_id=?)",
                         (uid, uid)).fetchone()[0]
    kids = c.execute("SELECT COUNT(*) FROM family_children WHERE parent1_id=? OR parent2_id=?", (uid, uid)).fetchone()[0]
    return {"id": uid, "name": name, "username": row[1] if row else None, "gender": parent_role(uid), "age": age,
            "money": money, "money_fmt": fmt_money(money), "rank": rank, "level": level_name(None, points),
            "points": points, "games": games, "wins": wins,
            "profession": profession_name(pid, uid) if pid in PROFESSION_NAMES else None,
            "divorces": divorces, "kids": kids}


def user_card_text(card):
    g = {"male": "👦 Yigit", "female": "👧 Qiz"}.get(card["gender"], "—")
    lines = ["👤 <b>Taklif qiluvchi haqida:</b>", f"⚧ Jinsi: <b>{g}</b>"]
    if card["age"] is not None:
        lines.append(f"🎂 Yoshi: <b>{card['age']}</b>")
    lines += [f"💰 Puli: <b>{card['money_fmt']}$</b>",
              f"🏆 Reytingi: <b>{'#' + str(card['rank']) if card['rank'] else '👑 Bot egasi'}</b>",
              f"⭐ Darajasi: <b>{html.escape(str(card['level']))}</b> · 📈 {card['points']} ball · "
              f"🎮 {card['games']} o‘yin (✅ {card['wins']})",
              f"💼 Kasbi: <b>{html.escape(card['profession']) if card['profession'] else 'yo‘q'}</b>",
              "💔 Oldin ajrashgan: " + (f"<b>Ha, {card['divorces']} marta</b>" if card["divorces"] else "<b>Yo‘q</b>")]
    if card["kids"]:
        lines.append(f"👶 Farzandlari: <b>{card['kids']}</b>")
    return "\n".join(lines)


def randpair_open(uid):
    """Foydalanuvchining javob kutayotgan random taklifi (eskirganlari 'expired' bo'ladi)."""
    c = db()
    with c:
        c.execute("""UPDATE pair_requests SET status='expired' WHERE random=1 AND status='proposal'
                     AND requester_id=? AND created_at < ?""", (uid, _iso_ago(RANDPAIR_TTL)))
    return c.execute("""SELECT id, target_id, created_at FROM pair_requests
                        WHERE random=1 AND status='proposal' AND requester_id=? ORDER BY id DESC LIMIT 1""",
                     (uid,)).fetchone()


def randpair_candidate(uid, want, skip=()):
    owners = tuple(skip)
    extra = (" AND u.user_id NOT IN (" + ",".join("?" * len(owners)) + ")") if owners else ""
    row = db().execute(
        f"""SELECT u.user_id FROM users u JOIN user_gender g ON g.user_id=u.user_id
            WHERE g.gender=? AND u.user_id<>? AND (u.started=1 OR u.birth_confirmed=1)
              AND NOT EXISTS (SELECT 1 FROM pairs p WHERE p.status='active' AND (p.user1_id=u.user_id OR p.user2_id=u.user_id))
              AND NOT EXISTS (SELECT 1 FROM pair_requests r WHERE r.request_type='pair'
                    AND ((r.requester_id=? AND r.target_id=u.user_id) OR (r.requester_id=u.user_id AND r.target_id=?))
                    AND (r.status IN ('proposal','pending') OR (r.status='rejected' AND r.created_at > ?))){extra}
            ORDER BY RANDOM() LIMIT 1""",
        (want, uid, uid, uid, _iso_ago(RANDPAIR_REJECT_DAYS * 86400), *owners)).fetchone()
    return row[0] if row else None


def randpair_status(uid):
    g = parent_role(uid)
    pair = active_pair(uid)
    st = {"gender": g, "has_pair": bool(pair), "partner": None, "pending": None, "cooldown": 0}
    if pair:
        st["partner"] = _plain_person(pair[2] if pair[1] == uid else pair[1])
        return st
    op = randpair_open(uid)
    if op:
        st["pending"] = {"id": op[0], "name": _plain_person(op[1]), "at": tashkent_dt(int(datetime.fromisoformat(op[2]).timestamp()))}
    last = db().execute("SELECT MAX(created_at) FROM pair_requests WHERE random=1 AND requester_id=?", (uid,)).fetchone()[0]
    if last:
        try:
            st["cooldown"] = max(0, RANDPAIR_COOLDOWN - int((datetime.now() - datetime.fromisoformat(last)).total_seconds()))
        except ValueError:
            pass
    return st


def _plain_person(uid):
    row = db().execute("SELECT first_name, username FROM users WHERE user_id=?", (uid,)).fetchone()
    return (row[0] if row else None) or (row[1] if row else None) or str(uid)


async def web_randpair(uid):
    """Tasodifiy qarama-qarshi jinsli, jufti yo'q foydalanuvchiga juftlik taklifi (ma'lumot kartasi bilan)."""
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    me = parent_role(uid)
    if me not in ("male", "female"):
        return {"error": "no_gender"}
    if active_pair(uid):
        return {"error": "has_pair"}
    if randpair_open(uid):
        return {"error": "waiting", "status": randpair_status(uid)}
    cd = randpair_status(uid)["cooldown"]
    if cd:
        return {"error": "cooldown", "wait": cd}
    bot = _EXCHANGE_LOOP_BOT
    if bot is None:
        return {"error": "bot"}
    want = "female" if me == "male" else "male"
    card = user_card(uid)
    tried = []
    for _ in range(RANDPAIR_TRIES):
        tid = randpair_candidate(uid, want, tried)
        if not tid:
            break
        tried.append(tid)
        now = datetime.now().isoformat(timespec="seconds")
        c = db()
        with c:
            rid = c.execute("""INSERT INTO pair_requests (request_type, requester_id, target_id, group_id, status, created_at, random)
                               VALUES ('pair', ?, ?, 0, 'proposal', ?, 1)""", (uid, tid, now)).lastrowid
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💞 Roziman", callback_data=f"rel:proposal:yes:{rid}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"rel:proposal:no:{rid}"),
        ]])
        try:
            await bot.send_message(
                chat_id=tid,
                text="💍 <b>Random juftlik taklifi!</b>\n"
                     f"{person_name(uid)} sizga juft bo‘lishni taklif qildi.\n\n" + user_card_text(card)
                     + "\n\nRozimisiz? Rozilikdan so‘ng juftlik bot egalari tasdig‘idan keyin tuziladi.",
                reply_markup=kb)
        except TelegramError as e:
            logger.info("Random juft taklifi yetkazilmadi (%s): %s", tid, e)
            with c:
                c.execute("UPDATE pair_requests SET status='failed' WHERE id=?", (rid,))
            continue
        tc = user_card(tid)
        return {"result": "sent", "target": {"name": tc["name"], "gender": tc["gender"], "age": tc["age"],
                                             "level": tc["level"], "profession": tc["profession"]},
                "status": randpair_status(uid)}
    return {"error": "none"}


async def web_randpair_cancel(uid):
    op = randpair_open(uid)
    if not op:
        return {"error": "no_request"}
    c = db()
    with c:
        c.execute("UPDATE pair_requests SET status='cancelled' WHERE id=? AND status='proposal'", (op[0],))
    return {"result": "cancelled", "status": randpair_status(uid)}


# ── 💬 Web chat: ID / @username orqali topib, shaxsiy suhbat ──
CHAT_MAX_LEN = 1000
CHAT_RATE = (8, 10)              # 10 s ichida ko'pi bilan 8 ta xabar
CHAT_NOTIFY_GAP = 300            # s — bitta suhbat bo'yicha Telegram bildirishnomalari oralig'i
CHAT_PAGE = 60
_CHAT_SENT: dict[int, list] = {}
_CHAT_NOTIFIED: dict[tuple, float] = {}


def chat_resolve(q):
    """ID yoki @username → botni ishlatgan foydalanuvchi ID si (yoki None)."""
    q = str(q or "").strip()
    c = db()
    if re.fullmatch(r"\d{3,15}", q):
        row = c.execute("SELECT user_id FROM users WHERE user_id=? AND (started=1 OR birth_confirmed=1)", (int(q),)).fetchone()
    else:
        un = q.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", un):
            return None
        row = c.execute("SELECT user_id FROM users WHERE LOWER(username)=LOWER(?) AND (started=1 OR birth_confirmed=1)",
                        (un,)).fetchone()
    return row[0] if row else None


def chat_blocked(a, b):
    """a yoki b bir-birini bloklaganmi."""
    return bool(db().execute("SELECT 1 FROM web_chat_blocks WHERE (user_id=? AND blocked_id=?) OR (user_id=? AND blocked_id=?)",
                             (a, b, b, a)).fetchone())


def chat_peer(uid, me=None):
    card = user_card(uid)
    pair = active_pair(uid)
    out = {"id": uid, "name": card["name"], "username": card["username"], "gender": card["gender"],
           "age": card["age"], "level": card["level"], "money_fmt": card["money_fmt"], "rank": card["rank"],
           "profession": card["profession"], "divorces": card["divorces"], "kids": card["kids"],
           "has_pair": bool(pair)}
    if me is not None:
        out["blocked_by_me"] = bool(db().execute("SELECT 1 FROM web_chat_blocks WHERE user_id=? AND blocked_id=?",
                                                 (me, uid)).fetchone())
        out["my_partner"] = bool(pair and me in (pair[1], pair[2]))
    return out


def chat_unread(uid):
    return db().execute("SELECT COUNT(*) FROM web_chat_msgs WHERE to_id=? AND read=0", (uid,)).fetchone()[0]


async def web_chat_find(uid, q):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    tid = chat_resolve(q)
    if not tid:
        return {"error": "not_found"}
    if tid == uid:
        return {"error": "self"}
    return {"result": "found", "user": chat_peer(tid, uid)}


async def web_chat_list(uid):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    c = db()
    rows = c.execute("""
        SELECT peer, MAX(id) AS last FROM (
            SELECT CASE WHEN from_id=? THEN to_id ELSE from_id END AS peer, id
            FROM web_chat_msgs WHERE from_id=? OR to_id=?)
        GROUP BY peer ORDER BY last DESC LIMIT 50""", (uid, uid, uid)).fetchall()
    out = []
    for peer, last in rows:
        m = c.execute("SELECT from_id, text, created_at FROM web_chat_msgs WHERE id=?", (last,)).fetchone()
        unread = c.execute("SELECT COUNT(*) FROM web_chat_msgs WHERE from_id=? AND to_id=? AND read=0", (peer, uid)).fetchone()[0]
        out.append({"id": peer, "name": _plain_person(peer), "last": m[1][:80], "mine": m[0] == uid,
                    "at": tashkent_dt(m[2]), "unread": unread})
    return {"result": "ok", "chats": out, "unread": chat_unread(uid)}


async def web_chat_history(uid, peer, after=0):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        peer = int(peer); after = int(after or 0)
    except (TypeError, ValueError):
        return {"error": "user"}
    c = db()
    rows = c.execute("""SELECT id, from_id, text, created_at, read FROM web_chat_msgs
                        WHERE ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?)) AND id>?
                        ORDER BY id DESC LIMIT ?""", (uid, peer, peer, uid, after, CHAT_PAGE)).fetchall()[::-1]
    with c:
        c.execute("UPDATE web_chat_msgs SET read=1 WHERE from_id=? AND to_id=? AND read=0", (peer, uid))
    seen = c.execute("SELECT COALESCE(MAX(id),0) FROM web_chat_msgs WHERE from_id=? AND to_id=? AND read=1",
                     (uid, peer)).fetchone()[0]
    res = {"result": "ok", "msgs": [{"id": r[0], "mine": r[1] == uid, "text": r[2], "at": tashkent_dt(r[3])} for r in rows],
           "seen": seen, "unread": chat_unread(uid)}
    if not after:
        res["peer"] = chat_peer(peer, uid)
    return res


async def web_chat_send(uid, peer, text):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        peer = int(peer)
    except (TypeError, ValueError):
        return {"error": "user"}
    text = re.sub(r"[\u0000-\u0008\u000b-\u001f\u007f]", "", str(text or "")).strip()
    if not text:
        return {"error": "empty"}
    if len(text) > CHAT_MAX_LEN:
        return {"error": "long", "max": CHAT_MAX_LEN}
    if peer == uid:
        return {"error": "self"}
    if not db().execute("SELECT 1 FROM users WHERE user_id=? AND (started=1 OR birth_confirmed=1)", (peer,)).fetchone():
        return {"error": "not_found"}
    if chat_blocked(uid, peer):
        return {"error": "blocked"}
    now = time.time()
    sent = [t for t in _CHAT_SENT.get(uid, []) if now - t < CHAT_RATE[1]]
    if len(sent) >= CHAT_RATE[0]:
        return {"error": "rate"}
    sent.append(now); _CHAT_SENT[uid] = sent
    c = db()
    with c:
        mid = c.execute("INSERT INTO web_chat_msgs(from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)",
                        (uid, peer, text, int(now))).lastrowid
    # Telegram bildirishnoma (suhbat bo'yicha 5 daqiqada bir marta, o'qilmagan bo'lsa)
    key = (uid, peer)
    if _EXCHANGE_LOOP_BOT is not None and now - _CHAT_NOTIFIED.get(key, 0) > CHAT_NOTIFY_GAP:
        _CHAT_NOTIFIED[key] = now
        kb = None
        if WEBAPP_URL.startswith("https://"):
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Javob berish",
                                                             web_app=WebAppInfo(f"{WEBAPP_URL}/app#chat={uid}"))]])
        try:
            await _EXCHANGE_LOOP_BOT.send_message(
                chat_id=peer, reply_markup=kb,
                text=f"💬 <b>Yangi xabar</b> — {person_name(uid)} (ID: <code>{uid}</code>)\n\n"
                     f"{html.escape(text[:300])}{'…' if len(text) > 300 else ''}")
        except TelegramError as e:
            logger.info("Chat bildirishnomasi yetkazilmadi (%s): %s", peer, e)
    return {"result": "sent", "msg": {"id": mid, "mine": True, "text": text, "at": tashkent_dt(int(now))}}


async def web_chat_block(uid, peer, on):
    try:
        peer = int(peer)
    except (TypeError, ValueError):
        return {"error": "user"}
    c = db()
    with c:
        if on:
            c.execute("INSERT OR IGNORE INTO web_chat_blocks(user_id, blocked_id) VALUES (?, ?)", (uid, peer))
        else:
            c.execute("DELETE FROM web_chat_blocks WHERE user_id=? AND blocked_id=?", (uid, peer))
    return {"result": "blocked" if on else "unblocked"}


async def web_pair_propose(uid, q):
    """💍 ID / @username orqali juftlik taklifi (web app). Faqat jufti yo'qlar, qarama-qarshi jins."""
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    tid = chat_resolve(q) if not isinstance(q, int) else q
    if not tid:
        return {"error": "not_found"}
    if tid == uid:
        return {"error": "self"}
    me, him = parent_role(uid), parent_role(tid)
    if me not in ("male", "female"):
        return {"error": "no_gender"}
    if him not in ("male", "female"):
        return {"error": "target_gender"}
    if me == him:
        return {"error": "same_gender"}
    if active_pair(uid):
        return {"error": "has_pair"}
    if active_pair(tid):
        return {"error": "target_pair"}
    if chat_blocked(uid, tid):
        return {"error": "blocked"}
    c = db()
    if c.execute("""SELECT 1 FROM pair_requests WHERE request_type='pair' AND requester_id=? AND target_id=?
                    AND status IN ('proposal','pending') AND created_at > ?""", (uid, tid, _iso_ago(RANDPAIR_TTL))).fetchone():
        return {"error": "already"}
    if _EXCHANGE_LOOP_BOT is None:
        return {"error": "bot"}
    now = datetime.now().isoformat(timespec="seconds")
    with c:
        rid = c.execute("""INSERT INTO pair_requests (request_type, requester_id, target_id, group_id, status, created_at, random)
                           VALUES ('pair', ?, ?, 0, 'proposal', ?, 2)""", (uid, tid, now)).lastrowid
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💞 Roziman", callback_data=f"rel:proposal:yes:{rid}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"rel:proposal:no:{rid}"),
    ]])
    try:
        await _EXCHANGE_LOOP_BOT.send_message(
            chat_id=tid, reply_markup=kb,
            text="💍 <b>Juftlik taklifi!</b>\n"
                 f"{person_name(uid)} sizga juft bo‘lishni taklif qildi.\n\n" + user_card_text(user_card(uid))
                 + "\n\nRozimisiz? Rozilikdan so‘ng juftlik bot egalari tasdig‘idan keyin tuziladi.")
    except TelegramError:
        with c:
            c.execute("UPDATE pair_requests SET status='failed' WHERE id=?", (rid,))
        return {"error": "undeliverable"}
    return {"result": "sent", "name": _plain_person(tid)}


async def web_avatar_save(uid, data):
    """Avatar sozlamalari (jins, kiyim/soch/teri ranglari, fon) — qisqa kalitlar, klient katalogidan."""
    if not avatar_enabled_for(uid):
        return {"error": "disabled"}
    if not isinstance(data, dict):
        return {"error": "avatar"}
    clean = {k: v for k, v in data.items()
             if k in AVATAR_SLOTS and isinstance(v, str) and re.fullmatch(r"[a-z0-9_]{1,20}", v)}
    with db() as c:
        c.execute("INSERT INTO user_avatar(user_id, data) VALUES (?, ?) "
                  "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data", (uid, json.dumps(clean)))
    return {"result": "saved", "avatar": clean}


def webapp_flags():
    d = {"all": 1, "owner": 1}
    for k, v in db().execute("SELECT key, value FROM webapp_config"):
        d[k] = v
    return d


def webapp_set(key, value):
    with db() as c:
        c.execute(
            "INSERT INTO webapp_config(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, int(value)))


def webapp_check_init_data(init_data, max_age=86400):
    """Telegram initData'ni bot token bilan tekshiradi. To'g'ri bo'lsa — user dict, aks holda None."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = urllib.parse.parse_qs(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        return None
    data = {k: v[0] for k, v in parsed.items()}
    recv_hash = data.pop("hash", None)
    if not recv_hash:
        return None
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, recv_hash):
        return None
    try:
        if abs(time.time() - int(data.get("auth_date", 0))) > max_age:
            return None
    except (ValueError, TypeError):
        return None
    try:
        user = json.loads(data.get("user", "{}"))
    except json.JSONDecodeError:
        return None
    return user if user.get("id") else None


async def webapp_payload(user_id):
    """Web app uchun foydalanuvchi ma'lumotlari (bot sikli ipida — DB xavfsiz)."""
    c = db()
    row = c.execute("SELECT first_name, username FROM users WHERE user_id=?", (user_id,)).fetchone()
    name = (row[0] if row else None) or str(user_id)
    username = row[1] if row else None
    money = wallet_balance(user_id)
    points, games, wins, losses, draws = get_stats(None, user_id, True)
    owners = tuple(CAREER_OWNER_IDS)
    marks = ",".join("?" * len(owners)) or "NULL"
    is_owner = user_id in CAREER_OWNER_IDS
    rank = None
    if not is_owner:
        rank = c.execute(
            f"SELECT COUNT(*)+1 FROM user_wallet WHERE money > ? AND user_id NOT IN ({marks})",
            (money, *owners),
        ).fetchone()[0]
    birja_val = sum(
        qty * (BIRJA_PRICES.get(a) or {"price": 0.0})["price"]
        for a, qty in c.execute("SELECT asset, qty FROM birja_holdings WHERE user_id=? AND qty>0", (user_id,))
    )
    top = c.execute(
        f"""SELECT w.user_id, w.money, u.first_name, u.username
            FROM user_wallet w LEFT JOIN users u ON u.user_id = w.user_id
            WHERE w.user_id NOT IN ({marks}) AND w.money > 0
            ORDER BY w.money DESC LIMIT 15""",
        owners,
    ).fetchall()
    # 🏦 Bank: faol kredit va omonat
    def _bank_name(bid):
        b = bank_get(bid)
        return b["name"] if b else "Bank"
    bank = {"loan": None, "deposit": None}
    lo = active_loan(user_id)
    if lo:
        bank["loan"] = {"amount": fmt_money(lo[1]), "days": lo[2], "due": fmt_money(lo[3]),
                        "due_at": tashkent_dt(lo[4]) if lo[4] else "—", "bank": _bank_name(lo[5])}
    dep = active_deposit(user_id)
    if dep:
        bank["deposit"] = {"amount": fmt_money(dep[1]), "days": dep[2], "payout": fmt_money(dep[3]),
                           "matures_at": tashkent_dt(dep[4]) if dep[4] else "—", "bank": _bank_name(dep[5])}

    # 📈 Birja: ushlab turilgan aktivlar
    birja_rows = []
    for asset, qty, cost in c.execute(
            "SELECT asset, qty, cost FROM birja_holdings WHERE user_id=? AND qty>0", (user_id,)):
        price = (BIRJA_PRICES.get(asset) or {"price": 0.0})["price"]
        value = qty * price
        birja_rows.append({
            "asset": asset, "qty": round(qty, 6), "price": round(price, 2),
            "value": round(value, 2), "value_fmt": fmt_money(round(value)),
            "profit": round(value - cost, 2),
        })

    # 📈 Birja bozori (narx, o'zgarish, ushlab turilgan miqdor)
    held = {a: (q, lb) for a, q, _c, lb in (
        (r[0], r[1], r[2], r[3]) for r in c.execute(
            "SELECT asset, qty, cost, last_buy FROM birja_holdings WHERE user_id=? AND qty>0", (user_id,)))}
    birja_market = []
    now_ts = int(time.time())
    for a, (nm, icon, _sym, _cg) in BIRJA_ASSETS.items():
        pinfo = BIRJA_PRICES.get(a) or {}
        price = pinfo.get("price")
        q, lb = held.get(a, (0, 0))
        birja_market.append({
            "asset": a, "name": nm, "icon": icon,
            "price": round(price, 2) if price else None,
            "change": round(pinfo.get("change", 0.0), 2),
            "qty": round(q, 8), "value_fmt": fmt_money(round(q * price)) if (q and price) else "0",
            "lock": max(0, BIRJA_HOLD - (now_ts - lb)) if q else 0,
        })

    # 👶 Farzandlar (boshqaruv uchun: ovqat/o'yinchoq ro'yxati, ta'lim to'lovi)
    _stage_uz = {"baby": "👶 Chaqaloq", "kinder": "🧒 Bog‘cha", "school": "🎒 Maktab",
                 "college": "🏫 Kollej", "uni": "🎓 Universitet", "work": "💼 Ishchi"}
    def _plain_name(pid):
        r = db().execute("SELECT first_name, username FROM users WHERE user_id=?", (pid,)).fetchone()
        return ((r[0] if r and r[0] else None) or (("@" + r[1]) if r and r[1] else None) or str(pid))[:24]
    kid_list = []
    for kid in kids_of(user_id):
        st = kid_stage(kid)
        owned = kid_gear(kid)
        def _items(kind):
            return [{"key": k, "name": v[5].get("uz", k), "price": v[3], "eff": v[4], "owned": k in owned}
                    for k, v in KID_ITEMS.items() if v[0] == kind and v[1] <= kid["age"] <= v[2]]
        fee_due = 0
        if not kid["working"] and st in KID_FEES and kid["fee_age"] < kid["age"]:
            fee_due = kid_fee(kid)
        inst = kid_inst(kid)
        kid_list.append({
            "id": kid["id"], "name": kid["child_name"] or "—", "age": kid["age"],
            "stage": _stage_uz.get(st, st), "stage_key": st, "gender": kid["gender"], "working": bool(kid["working"]),
            "hunger": round(kid["hunger"]), "happy": round(kid["happy"]),
            "growth": round(min(1.0, kid["meals"] / kid_meals_need(kid["age"])) * 100), "block": kid_block(kid) or "",
            "meals": kid["meals"], "meals_need": kid_meals_need(kid["age"]),
            "next_meal": int(kid_eat_check(kid, int(time.time())) or 0), "gear": _items("gear"),
            "outfit": kid_outfit(kid), "parents": [_plain_name(kid["parent1_id"]), _plain_name(kid["parent2_id"])],
            "inst": ({"id": inst["id"], "name": inst["name"], "fee": inst["fee"]} if inst else None),
            "salary": KID_SALARY.get(kid["edu"], 0) if kid["working"] else 0,
            "food": _items("food"), "toy": _items("toy"), "fee": fee_due,
        })

    # 🛍 Do'kon va 🏦 bank imkoniyatlari (web app interaktiv uchun)
    shop = [{"key": k, "name": nm, "price": pr} for k, (nm, pr) in SHOP_GIFTS.items()]
    has_partner = active_pair(user_id) is not None
    # Botdagi barcha ochiq banklar (ariza rejimidagilar ham — kredit ariza orqali beriladi)
    instant_banks = [{"id": b["id"], "name": b["name"], "apply": bool(b["apply_mode"]),
                      "loan_rate": round(b["loan_rate"] * 100, 1), "deposit_rate": round(b["deposit_rate"] * 100, 1)}
                     for b in banks_all(only_active=True)]
    bank_opts = {
        "banks": instant_banks,
        "loan_amounts": ([LOAN_FIRST] if not had_loan_before(user_id) else LOAN_AMOUNTS),
        "loan_days": list(LOAN_DAYS), "dep_amounts": DEPOSIT_AMOUNTS, "dep_days": list(DEPOSIT_DAYS),
        "can_loan": not (active_loan(user_id) or pending_app(user_id) or money < 0),
        "pending_app": bool(pending_app(user_id)),
        "can_deposit": not (active_deposit(user_id) or active_loan(user_id) or money < 0),
    }

    data = {
        "name": name, "username": username, "id": user_id,
        "money": money, "money_fmt": fmt_money(money),
        "points": points, "games": games, "wins": wins, "losses": losses, "draws": draws,
        "level": level_name(0, points), "rank": rank, "kids": len(kid_list),
        "loan": bool(lo), "birja": round(birja_val, 2),
        "bank": bank, "birja_list": birja_rows, "kids_list": kid_list,
        "shop": shop, "has_partner": has_partner, "bank_opts": bank_opts,
        "birja_market": birja_market, "birja_buy_fixed": BIRJA_BUY_FIXED,
        "birja_pcts": BIRJA_PCTS, "birja_min": BIRJA_MIN_ORDER,
        "crash_history": list(WEB_CRASH_HISTORY),
        "edu": edu_list(True), "edu_min_age": EDU_MIN_AGE, "edu_default_fee": KID_FEES,
        "edu_all": edu_list(False) if is_owner else [],
        "kami": kami_enabled_for(user_id),
        "kami_test": not webapp_flags().get("kami", 0),
        "kami_game": web_kami_view(user_id),
        "avatar3d": avatar_enabled_for(user_id),
        "avatar_test": not webapp_flags().get("avatar", 0),
        "avatar": avatar_get(user_id),
        "randpair": randpair_status(user_id),
        "chat_unread": chat_unread(user_id),
        "is_owner": is_owner,
        "top": [{
            "name": (t[2] or str(t[0])), "username": t[3],
            "money_fmt": fmt_money(t[1]), "me": t[0] == user_id,
        } for t in top],
    }
    if is_owner:
        total = c.execute("SELECT COALESCE(SUM(money),0) FROM user_wallet").fetchone()[0]
        users_count = bot_users_count(c)
        data["owner"] = {
            "users": stat_show("users", users_count),
            "groups": stat_show("groups", len(panel_group_ids(c))),
            "total_money": fmt_money(total),
            "active_games": len(GAMES),
            "in_games": fmt_money(money_in_games()),
        }
    return data


async def webapp_fetch(user_id):
    """Yoqilgan/o'chirilganlikni tekshirib, ma'lumotni qaytaradi (bot sikli ipida)."""
    flags = webapp_flags()
    is_owner = user_id in CAREER_OWNER_IDS
    if not (flags["all"] or (is_owner and flags["owner"])):
        return {"enabled": False, "owner": is_owner}
    return {"enabled": True, "owner": is_owner, "data": await webapp_payload(user_id)}


# ── 🎮 Web app o'yinlari (xavfsiz, server tomonda, haqiqiy hamyon) ──
WEB_FROG: dict[int, dict] = {}      # user_id -> {bet, mode, traps, step, done}
WEB_CRASH_HISTORY: list = []        # oxirgi crash nuqtalari (umumiy, yuqori panel uchun)
WEB_CRASH_GROWTH = 0.12
WEB_CRASH_MAX = 1000.0
WEB_BET_MAX = 10_000_000


def web_enabled_for(uid):
    flags = webapp_flags()
    return flags["all"] or (uid in CAREER_OWNER_IDS and flags["owner"])


# ── 🚀 UMUMIY Crash (Aviator): hamma uchun bitta raund, bir xil koeffitsiyent ──
# Bosqichlar: "bet" (WEB_ROUND_BET s tikish) → "fly" (koeffitsiyent o'sadi) → "crash" (WEB_ROUND_PAUSE s).
# Crash nuqtasi faqat serverda; klient faqat portlagandan keyin biladi. Tikish "fly"/"crash" paytida
# keyingi raundga navbatga qo'yiladi. Yechish SERVER soati bo'yicha.
WEB_ROUND_BET = 7.0
WEB_ROUND_PAUSE = 3.5
WEB_CRASH_BUST = 0.07          # darhol (1.00x) portlash ehtimoli
WEB_CRASH_RTP = 0.90           # P(crash > x) ≈ RTP / x — uy ustunligi ~10%
WEB_ROUND = {"id": 0, "phase": "bet", "t": time.monotonic(), "crash": 1.0, "bets": {}}
WEB_NEXT_BETS: dict[int, dict] = {}


def _web_crash_point():
    if random.random() < WEB_CRASH_BUST:
        return 1.00
    pt = WEB_CRASH_RTP / (1.0 - random.random())
    return round(min(max(pt, 1.01), WEB_CRASH_MAX), 2)


def _web_crash_mult(elapsed):
    return math.exp(WEB_CRASH_GROWTH * max(0.0, elapsed))


def _web_crash_record(pt):
    WEB_CRASH_HISTORY.insert(0, round(pt, 2))
    del WEB_CRASH_HISTORY[16:]


def _web_player_name(uid):
    row = db().execute("SELECT first_name, username FROM users WHERE user_id=?", (uid,)).fetchone()
    name = (row[0] if row else None) or (("@" + row[1]) if row and row[1] else None) or str(uid)
    return name[:18]


async def web_crash_round_worker(application):
    """Umumiy raundlarni cheksiz aylantiradi (post_init'da ishga tushadi)."""
    while True:
        try:
            WEB_ROUND.update(id=WEB_ROUND["id"] + 1, phase="bet", t=time.monotonic(),
                             crash=_web_crash_point(), bets=dict(WEB_NEXT_BETS))
            WEB_NEXT_BETS.clear()
            await asyncio.sleep(WEB_ROUND_BET)
            WEB_ROUND.update(phase="fly", t=time.monotonic())
            crash_t = math.log(WEB_ROUND["crash"]) / WEB_CRASH_GROWTH
            await asyncio.sleep(max(0.0, crash_t))
            WEB_ROUND.update(phase="crash", t=time.monotonic())
            _web_crash_record(WEB_ROUND["crash"])
            await asyncio.sleep(WEB_ROUND_PAUSE)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Web crash raundida xato")
            await asyncio.sleep(2)


def web_crash_refund_open():
    """Restartda: yechilmagan tikishlarni qaytaradi (raund to'xtab qoladi)."""
    for bets in (WEB_ROUND["bets"], WEB_NEXT_BETS):
        for uid, b in list(bets.items()):
            if b["cash"] is None:
                wallet_change(uid, b["bet"])
        bets.clear()


def _web_crash_players(me=None):
    out = []
    for uid, b in WEB_ROUND["bets"].items():
        out.append({"name": b["name"], "bet": b["bet"], "cash": b["cash"], "win": b["win"], "me": uid == me})
    out.sort(key=lambda x: -x["bet"])
    return out[:40]


async def web_crash_state(uid):
    r = WEB_ROUND
    el = time.monotonic() - r["t"]
    st = {"round": r["id"], "phase": r["phase"], "elapsed": round(el, 3), "growth": WEB_CRASH_GROWTH,
          "history": list(WEB_CRASH_HISTORY), "players": _web_crash_players(uid),
          "total": len(r["bets"]), "pot": sum(b["bet"] for b in r["bets"].values())}
    if r["phase"] == "bet":
        st["countdown"] = round(max(0.0, WEB_ROUND_BET - el), 2)
    elif r["phase"] == "fly":
        st["mult"] = round(min(_web_crash_mult(el), r["crash"] - 0.01) if r["crash"] > 1.0 else 1.0, 2)
    else:
        st["crash"] = round(r["crash"], 2)
    me = r["bets"].get(uid)
    if me:
        st["me"] = {"bet": me["bet"], "cash": me["cash"], "win": me["win"]}
    if uid in WEB_NEXT_BETS:
        st["queued"] = WEB_NEXT_BETS[uid]["bet"]
    st["balance"] = wallet_balance(uid)
    return st


async def web_crash_bet(uid, bet):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        bet = int(bet)
    except (TypeError, ValueError):
        return {"error": "bet"}
    if bet < CRASH_MIN_BET:
        return {"error": "min", "min": CRASH_MIN_BET}
    if bet > WEB_BET_MAX:
        return {"error": "max"}
    target = WEB_ROUND["bets"] if WEB_ROUND["phase"] == "bet" else WEB_NEXT_BETS
    if uid in target:
        return {"error": "bet_placed"}
    c = db()
    with c:
        if not _wallet_take(c, uid, bet):
            return {"error": "funds", "balance": wallet_balance(uid)}
    target[uid] = {"name": _web_player_name(uid), "bet": bet, "cash": None, "win": 0}
    return {"result": "placed" if target is WEB_ROUND["bets"] else "queued", "bet": bet,
            "balance": wallet_balance(uid)}


async def web_crash_cancel(uid):
    """Raund boshlanmasidan oldin tikishni bekor qilish (pul qaytadi)."""
    for target, ok in ((WEB_NEXT_BETS, True), (WEB_ROUND["bets"], WEB_ROUND["phase"] == "bet")):
        b = target.get(uid)
        if b and ok and b["cash"] is None:
            target.pop(uid)
            wallet_change(uid, b["bet"])
            return {"result": "cancelled", "balance": wallet_balance(uid)}
    return {"error": "no_game"}


async def web_crash_cashout(uid, _ignored=None):
    r = WEB_ROUND
    b = r["bets"].get(uid)
    if not b or b["cash"] is not None:
        return {"error": "no_game"}
    if r["phase"] != "fly":
        return {"error": "not_flying"}
    cur = _web_crash_mult(time.monotonic() - r["t"])
    if cur >= r["crash"]:
        return {"result": "lose", "balance": wallet_balance(uid)}
    mult = round(cur, 2)
    win = int(b["bet"] * mult)
    b.update(cash=mult, win=win)
    wallet_change(uid, win)
    return {"result": "win", "multiplier": mult, "win": win, "balance": wallet_balance(uid)}


# ── 🖼 Telegram profil rasmi (proksi: bot token URL'da ko'rinmasin) ──
_AVATAR_CACHE: dict[int, tuple] = {}


async def web_avatar_bytes(uid):
    hit = _AVATAR_CACHE.get(uid)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    data = b""
    try:
        photos = await _EXCHANGE_LOOP_BOT.get_user_profile_photos(uid, limit=1)
        if photos.photos:
            size = photos.photos[0][min(1, len(photos.photos[0]) - 1)]
            f = await _EXCHANGE_LOOP_BOT.get_file(size.file_id)
            data = bytes(await f.download_as_bytearray())
    except TelegramError:
        data = b""
    _AVATAR_CACHE[uid] = (time.time(), data)
    return data


WEB_FROG_EXTRA = 0.08     # har qatorda qo'shimcha (yashirin) tuzoq ehtimoli — web Baqa yutish imkonini kamaytiradi
_FROG_RNG = random.SystemRandom()


def _web_frog_traps(mode):
    """Har o'yinda tuzoqlar yangidan, kriptografik tasodif bilan joylashadi."""
    rows = []
    for _ in range(FROG_ROWS):
        n = FROG_MODES[mode] + (1 if _FROG_RNG.random() < WEB_FROG_EXTRA else 0)
        rows.append(set(_FROG_RNG.sample(range(FROG_COLS), min(n, FROG_COLS - 1))))
    return rows


async def web_frog_start(uid, bet, mode):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    if mode not in FROG_MODES:
        mode = "easy"
    try:
        bet = int(bet)
    except (TypeError, ValueError):
        return {"error": "bet"}
    if bet < FROG_MIN_BET:
        return {"error": "min", "min": FROG_MIN_BET}
    if bet > WEB_BET_MAX:
        return {"error": "max"}
    c = db()
    with c:
        if not _wallet_take(c, uid, bet):
            return {"error": "funds", "balance": wallet_balance(uid)}
    WEB_FROG[uid] = {"bet": bet, "mode": mode, "traps": _web_frog_traps(mode), "step": 0, "done": False}
    return {"started": True, "rows": FROG_ROWS, "cols": FROG_COLS, "mode": mode, "bet": bet,
            "next_mult": frog_mult(mode, 1), "balance": wallet_balance(uid)}


async def web_frog_step(uid, col):
    g = WEB_FROG.get(uid)
    if not g or g["done"]:
        return {"error": "no_game"}
    try:
        col = int(col)
    except (TypeError, ValueError):
        return {"error": "col"}
    r = g["step"]
    if not 0 <= col < FROG_COLS:
        return {"error": "col"}
    if col in g["traps"][r]:
        g["done"] = True
        WEB_FROG.pop(uid, None)
        return {"result": "lose", "row": r, "col": col, "traps": sorted(g["traps"][r]),
                "balance": wallet_balance(uid)}
    g["step"] += 1
    mult = frog_mult(g["mode"], g["step"])
    if g["step"] >= FROG_ROWS:
        g["done"] = True
        WEB_FROG.pop(uid, None)
        win = int(g["bet"] * mult)
        wallet_change(uid, win)
        return {"result": "win_full", "row": r, "col": col, "multiplier": mult,
                "win": win, "balance": wallet_balance(uid)}
    return {"result": "safe", "row": r, "col": col, "step": g["step"], "multiplier": mult,
            "next_mult": frog_mult(g["mode"], g["step"] + 1), "balance": wallet_balance(uid)}


async def web_frog_cashout(uid):
    g = WEB_FROG.get(uid)
    if not g or g["done"]:
        return {"error": "no_game"}
    if g["step"] <= 0:
        return {"error": "no_step"}
    g["done"] = True
    WEB_FROG.pop(uid, None)
    mult = frog_mult(g["mode"], g["step"])
    win = int(g["bet"] * mult)
    wallet_change(uid, win)
    return {"result": "cashed", "multiplier": mult, "win": win, "balance": wallet_balance(uid)}


# ── 🛩 Web app: Kamikaze (1xGames uslubi) ──
# 12 ustun × 5 qator dengiz. Har qadamda samolyot keyingi ustundan bitta katak tanlaydi; dushman kemasi
# o'sha ustunga bitta o'q uzadi (joyi o'yin boshida serverda yashirin tanlanadi). Tegsa — yutqazish.
KAMI_COLS = 12
KAMI_ROWS = 5
KAMI_RTP = 0.92
KAMI_MIN_BET = 10
WEB_KAMI: dict[int, dict] = {}
_KAMI_RNG = random.SystemRandom()


def kami_mult(step):
    if step <= 0:
        return 1.0
    return math.floor(KAMI_RTP * (KAMI_ROWS / (KAMI_ROWS - 1)) ** step * 100) / 100


def kami_win(bet, step):
    """Yutuq: suzuvchi nuqta xatosini (100*1.15=114.99…) yaxlitlab olib tashlaydi."""
    return int(round(bet * kami_mult(step), 2))


def kami_enabled_for(uid):
    """Test bosqichi: standart — faqat ownerlar; owner panel → Web App dan hamma uchun ochiladi."""
    if not web_enabled_for(uid):
        return False
    return bool(webapp_flags().get("kami", 0)) or uid in CAREER_OWNER_IDS


def web_kami_view(uid):
    """Ochiq o'yin holati (yopilgan/uzilgan web app'ni davom ettirish uchun). Dushman o'qlari faqat o'tilgan ustunlar uchun."""
    g = WEB_KAMI.get(uid)
    if not g:
        return None
    step = g["step"]
    return {"bet": g["bet"], "step": step, "cols": KAMI_COLS, "rows": KAMI_ROWS,
            "ladder": [kami_mult(i) for i in range(1, KAMI_COLS + 1)],
            "passed": [{"col": c, "row": r, "shot": g["shots"][c]} for c, r in enumerate(g.get("picks", [])[:step])],
            "multiplier": kami_mult(step) if step else 0, "win": kami_win(g["bet"], step) if step else 0}


async def web_kami_state(uid):
    v = web_kami_view(uid)
    return {"active": bool(v), "game": v, "balance": wallet_balance(uid)}


async def web_kami_start(uid, bet):
    if not kami_enabled_for(uid):
        return {"error": "disabled"}
    if uid in WEB_KAMI:      # oldingi o'yin ochiq qolgan (web app yopilgan/aloqa uzilgan) — bloklamasdan davom ettiramiz
        return {"resumed": True, "game": web_kami_view(uid), "balance": wallet_balance(uid)}
    try:
        bet = int(bet)
    except (TypeError, ValueError):
        return {"error": "bet"}
    if bet < KAMI_MIN_BET:
        return {"error": "min", "min": KAMI_MIN_BET}
    if bet > WEB_BET_MAX:
        return {"error": "max"}
    c = db()
    with c:
        if not _wallet_take(c, uid, bet):
            return {"error": "funds", "balance": wallet_balance(uid)}
    shots = [_KAMI_RNG.randrange(KAMI_ROWS) for _ in range(KAMI_COLS)]
    WEB_KAMI[uid] = {"bet": bet, "shots": shots, "step": 0, "picks": []}
    return {"started": True, "cols": KAMI_COLS, "rows": KAMI_ROWS, "bet": bet,
            "ladder": [kami_mult(i) for i in range(1, KAMI_COLS + 1)], "balance": wallet_balance(uid)}


async def web_kami_step(uid, row):
    g = WEB_KAMI.get(uid)
    if not g:
        return {"error": "no_game"}
    try:
        row = int(row)
    except (TypeError, ValueError):
        return {"error": "row"}
    if not 0 <= row < KAMI_ROWS:
        return {"error": "row"}
    col = g["step"]
    shot = g["shots"][col]
    if row == shot:
        WEB_KAMI.pop(uid, None)
        return {"result": "lose", "col": col, "row": row, "shot": shot, "balance": wallet_balance(uid)}
    g["step"] += 1
    g.setdefault("picks", []).append(row)
    mult = kami_mult(g["step"])
    if g["step"] >= KAMI_COLS:
        WEB_KAMI.pop(uid, None)
        win = kami_win(g["bet"], g["step"])
        wallet_change(uid, win)
        return {"result": "win_full", "col": col, "row": row, "shot": shot, "multiplier": mult,
                "win": win, "balance": wallet_balance(uid)}
    return {"result": "safe", "col": col, "row": row, "shot": shot, "step": g["step"], "multiplier": mult,
            "win": kami_win(g["bet"], g["step"]), "balance": wallet_balance(uid)}


async def web_kami_cashout(uid):
    g = WEB_KAMI.get(uid)
    if not g:
        return {"error": "no_game"}
    if g["step"] <= 0:
        return {"error": "no_step"}
    WEB_KAMI.pop(uid, None)
    mult = kami_mult(g["step"])
    win = kami_win(g["bet"], g["step"])
    wallet_change(uid, win)
    return {"result": "cashed", "multiplier": mult, "win": win, "balance": wallet_balance(uid)}


def web_kami_settle_open():
    """Restartda: o'rtadagi o'yinlar — o'tilgan qadamlar bo'yicha yutuq, qadam yo'q bo'lsa tikish qaytadi."""
    for uid, g in list(WEB_KAMI.items()):
        wallet_change(uid, kami_win(g["bet"], g["step"]) if g["step"] else g["bet"])
    WEB_KAMI.clear()


# ── 🛍 Web app: Do'kon (sovg'a sotib olib yuborish) ──

async def web_shop_buy(uid, gift_key, recipient):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    if gift_key not in SHOP_GIFTS:
        return {"error": "item"}
    name, price = SHOP_GIFTS[gift_key]
    rid = None
    if recipient == "partner":
        pair = active_pair(uid)
        if not pair:
            return {"error": "no_pair"}
        rid = pair[2] if pair[1] == uid else pair[1]
    else:
        recipient = str(recipient or "").strip()
        if recipient.startswith("@"):
            row = db().execute("SELECT user_id FROM users WHERE lower(username)=lower(?)", (recipient[1:],)).fetchone()
            rid = row[0] if row else None
        elif recipient.lstrip("-").isdigit():
            rid = int(recipient)
    if not rid:
        return {"error": "recipient"}
    if rid == uid:
        return {"error": "self"}
    owner = is_money_owner(uid)
    c = db()
    gift_id = None
    with c:
        if not owner and not _wallet_take(c, uid, price):
            return {"error": "funds", "balance": wallet_balance(uid)}
        cur = c.execute(
            "INSERT INTO gift_log(sender_id,recipient_id,gift_key,price,created_at) VALUES(?,?,?,?,?)",
            (uid, rid, gift_key, price, datetime.now().isoformat(timespec="seconds")))
        gift_id = cur.lastrowid
    try:
        await _EXCHANGE_LOOP_BOT.send_message(
            rid, f"🎁 {person_name(uid)} sizga {gift_label_html(gift_key, name)} sovg‘a qildi!")
    except TelegramError:
        with c:
            c.execute("DELETE FROM gift_log WHERE id=?", (gift_id,))
            if not owner:
                _wallet_add(c, uid, price)
        return {"error": "undeliverable", "balance": wallet_balance(uid)}
    return {"result": "sent", "gift": name, "to": person_name(rid), "balance": wallet_balance(uid)}


# ── 🏦 Web app: Bank (kredit / omonat — faqat instant banklar) ──

async def web_bank_loan(uid, bank_id, amount, days, purpose=None):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        bank = bank_get(int(bank_id))
        amount, days = int(amount), int(days)
    except (TypeError, ValueError):
        return {"error": "bad"}
    if not bank or not bank["active"]:
        return {"error": "bank"}
    if active_loan(uid):
        return {"error": "loan_has"}
    if pending_app(uid):
        return {"error": "apply_pending"}
    if wallet_balance(uid) < 0:
        return {"error": "debt"}
    allowed = LOAN_AMOUNTS if had_loan_before(uid) else [LOAN_FIRST]
    if amount not in allowed or days not in LOAN_DAYS:
        return {"error": "params"}
    due = loan_due(amount, days, bank["loan_rate"])
    if bank["apply_mode"]:
        # Ariza rejimi: botdagidek maqsad bilan ariza bank egasiga ketadi
        purpose = str(purpose or "").strip()[:500]
        if len(purpose) < 3:
            return {"error": "purpose"}
        row = db().execute("SELECT first_name FROM users WHERE user_id=?", (uid,)).fetchone()
        ok = await submit_loan_app(_EXCHANGE_LOOP_BOT, uid, (row[0] if row else None) or str(uid),
                                   bank, amount, days, due, purpose)
        return {"result": "applied", "bank": bank["name"]} if ok else {"error": "owner_unreachable"}
    now = int(time.time())
    c = db()
    with c:
        issue_loan(c, uid, bank["id"], amount, days, due, now)
    return {"result": "loan", "amount": amount, "days": days, "due": due, "balance": wallet_balance(uid)}


async def web_bank_repay(uid):
    loan = active_loan(uid)
    if not loan:
        return {"error": "no_loan"}
    loan_id, _, _, due, _, _ = loan
    now = int(time.time())
    c = db()
    with c:
        paid = _wallet_take(c, uid, due)
        if paid:
            c.execute("UPDATE bank_loans SET status='paid', closed_at=? WHERE id=? AND status='active'", (now, loan_id))
    if not paid:
        return {"error": "funds", "balance": wallet_balance(uid)}
    return {"result": "repaid", "due": due, "balance": wallet_balance(uid)}


async def web_bank_deposit(uid, bank_id, amount, days):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        bank = bank_get(int(bank_id))
        amount, days = int(amount), int(days)
    except (TypeError, ValueError):
        return {"error": "bad"}
    if not bank or not bank["active"]:
        return {"error": "bank"}
    if active_deposit(uid):
        return {"error": "dep_has"}
    if active_loan(uid) or wallet_balance(uid) < 0:
        return {"error": "dep_loan"}
    if amount not in DEPOSIT_AMOUNTS or days not in DEPOSIT_DAYS:
        return {"error": "params"}
    payout = deposit_payout(amount, days, bank["deposit_rate"])
    now = int(time.time())
    matures = now + days * DAY_SECONDS
    c = db()
    with c:
        taken = _wallet_take(c, uid, amount)
        if taken:
            c.execute(
                "INSERT INTO bank_deposits(user_id,amount,days,payout,created_at,matures_at,bank_id) VALUES(?,?,?,?,?,?,?)",
                (uid, amount, days, payout, now, matures, bank["id"]))
    if not taken:
        return {"error": "funds", "balance": wallet_balance(uid)}
    return {"result": "deposit", "amount": amount, "days": days, "payout": payout, "balance": wallet_balance(uid)}


# ── 📈 Web app: Birja (sotib olish / sotish) ──

async def web_birja_buy(uid, asset, usd):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    if asset not in BIRJA_ASSETS:
        return {"error": "asset"}
    price = birja_price(asset)
    if price is None:
        return {"error": "stale"}
    try:
        usd = int(usd)
    except (TypeError, ValueError):
        return {"error": "bad"}
    if usd < BIRJA_MIN_ORDER:
        return {"error": "min", "min": BIRJA_MIN_ORDER}
    if usd > BIRJA_MAX_ORDER:
        return {"error": "max", "max": BIRJA_MAX_ORDER}
    if usd > wallet_balance(uid):
        return {"error": "funds", "balance": wallet_balance(uid)}
    res = birja_buy(uid, asset, usd, price)
    if not res:
        return {"error": "funds", "balance": wallet_balance(uid)}
    qty, fee = res
    return {"result": "bought", "asset": asset, "qty": round(qty, 8), "usd": usd, "fee": fee,
            "balance": wallet_balance(uid)}


async def web_birja_sell(uid, asset, pct):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    if asset not in BIRJA_ASSETS:
        return {"error": "asset"}
    price = birja_price(asset)
    if price is None:
        return {"error": "stale"}
    try:
        pct = int(pct)
    except (TypeError, ValueError):
        return {"error": "bad"}
    if pct not in BIRJA_PCTS:
        return {"error": "pct"}
    qty_have, _, last_buy = birja_holding(uid, asset)
    if qty_have <= 0:
        return {"error": "nothing"}
    wait = BIRJA_HOLD - (int(time.time()) - last_buy)
    if wait > 0:
        return {"error": "hold", "min": max(1, math.ceil(wait / 60))}
    if qty_have * price * pct / 100 < BIRJA_MIN_ORDER and pct < 100:
        return {"error": "min", "min": BIRJA_MIN_ORDER}
    res = birja_sell(uid, asset, pct, price)
    if not res:
        return {"error": "nothing"}
    qty, usd, fee = res
    return {"result": "sold", "asset": asset, "qty": round(qty, 8), "usd": usd, "fee": fee,
            "balance": wallet_balance(uid)}


# ── 👶 Web app: Farzand boshqaruvi (ovqat / o'yinchoq / ta'lim to'lovi) ──

async def web_kid_action(uid, kid_id, act, item):
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        kid = kid_fresh(int(kid_id))
    except (TypeError, ValueError):
        return {"error": "kid"}
    if not kid or uid not in (kid["parent1_id"], kid["parent2_id"]):
        return {"error": "not_parent"}
    if kid["working"]:
        return {"error": "working"}
    c = db()
    if act in ("feed", "toy", "gear"):
        it = KID_ITEMS.get(item)
        kind = {"feed": "food", "toy": "toy", "gear": "gear"}[act]
        if not it or it[0] != kind or not it[1] <= kid["age"] <= it[2]:
            return {"error": "item"}
        price, eff = it[3], it[4]
        stat = "hunger" if kind == "food" else "happy"
        now = int(time.time())
        if kind == "gear":
            if item in kid_gear(kid):
                return {"error": "owned"}
            kid["gear"] = ",".join(sorted(kid_gear(kid) | {item}))
        else:
            if kind == "food":
                wait = kid_eat_check(kid, now)
                if wait:
                    return {"error": "too_soon", "wait": int(wait)}
            if kid[stat] >= 100:
                return {"error": "full"}
            if kind == "food":
                kid_eat(kid, now)
        kid[stat] = min(100.0, kid[stat] + eff)
        kid["alerts"] &= ~(KID_ALERT_HUNGRY if kind == "food" else KID_ALERT_SAD)
        with c:
            if not _wallet_take(c, uid, price):
                return {"error": "funds", "balance": wallet_balance(uid)}
            kid_save(c, kid)
        return {"result": "ok", "stat": stat, "value": round(kid[stat]), "balance": wallet_balance(uid),
                "meals": kid["meals"], "need": kid_meals_need(kid["age"]), "age": kid["age"]}
    if act == "fee":
        stage = kid_stage(kid)
        if stage not in KID_FEES or kid["fee_age"] >= kid["age"]:
            return {"error": "no_fee"}
        fee = kid_fee(kid)
        kid["fee_age"] = kid["age"]
        kid["alerts"] &= ~KID_ALERT_FEE
        with c:
            if not _wallet_take(c, uid, fee):
                return {"error": "funds", "balance": wallet_balance(uid)}
            kid_save(c, kid)
        return {"result": "fee", "fee": fee, "balance": wallet_balance(uid)}
    return {"error": "act"}


KID_OUTFIT_SLOTS = ("hat", "top", "bottom", "shoes", "acc", "emo")


def kid_outfit(kid):
    try:
        d = json.loads(kid.get("outfit") or "{}")
        return {k: v for k, v in d.items() if k in KID_OUTFIT_SLOTS and isinstance(v, str)}
    except (ValueError, TypeError):
        return {}


async def web_kid_outfit(uid, kid_id, outfit):
    """3D personaj kiyimlarini saqlaydi (faqat ota-ona). Qiymatlar — qisqa kalitlar (klient katalogi)."""
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        kid = kid_row(int(kid_id))
    except (TypeError, ValueError):
        return {"error": "kid"}
    if not kid or uid not in (kid["parent1_id"], kid["parent2_id"]):
        return {"error": "not_parent"}
    if not isinstance(outfit, dict):
        return {"error": "outfit"}
    clean = {k: v for k, v in outfit.items()
             if k in KID_OUTFIT_SLOTS and isinstance(v, str) and re.fullmatch(r"[a-z0-9_]{1,20}", v)}
    with db() as c:
        c.execute("UPDATE family_children SET outfit=? WHERE id=?", (json.dumps(clean), kid["id"]))
    return {"result": "saved", "outfit": clean}


async def web_edu_enroll(uid, kid_id, inst_id):
    """Ota/ona farzandni hozirgi bosqichiga mos muassasaga yozdiradi (to'lov keyin — 🎓 Ta'lim tugmasida)."""
    if not web_enabled_for(uid):
        return {"error": "disabled"}
    try:
        kid = kid_fresh(int(kid_id)); inst = edu_get(int(inst_id))
    except (TypeError, ValueError):
        return {"error": "kid"}
    if not kid or uid not in (kid["parent1_id"], kid["parent2_id"]):
        return {"error": "not_parent"}
    if kid["working"]:
        return {"error": "working"}
    if not inst or not inst["active"]:
        return {"error": "inst"}
    if inst["kind"] != kid_stage(kid):
        return {"error": "inst_stage"}
    kid["inst_id"] = inst["id"]
    with db() as c:
        kid_save(c, kid)
    return {"result": "enrolled", "inst": inst["name"], "fee": inst["fee"]}


async def web_edu_admin(uid, act, body):
    """Ownerlar: muassasa ochish / nomi va to'lovini o'zgartirish / yopish."""
    if uid not in CAREER_OWNER_IDS:
        return {"error": "owner_only"}
    c = db()
    if act == "add":
        kind = body.get("kind")
        name = str(body.get("name") or "").strip()[:40]
        try:
            fee = int(body.get("fee"))
        except (TypeError, ValueError):
            return {"error": "fee"}
        if kind not in EDU_KINDS:
            return {"error": "kind"}
        if len(name) < 2:
            return {"error": "name"}
        if not 0 <= fee <= EDU_FEE_MAX:
            return {"error": "fee"}
        with c:
            new_id = c.execute("INSERT INTO edu_institutions(kind, name, fee, active, owner_id, created_at) VALUES (?,?,?,?,?,?)",
                               (kind, name, fee, 1, uid, int(time.time()))).lastrowid
        return {"result": "added", "id": new_id, "edu_all": edu_list(False)}
    try:
        inst = edu_get(int(body.get("id")))
    except (TypeError, ValueError):
        inst = None
    if not inst:
        return {"error": "inst"}
    if act == "update":
        name = str(body.get("name") if body.get("name") is not None else inst["name"]).strip()[:40]
        try:
            fee = int(body.get("fee") if body.get("fee") is not None else inst["fee"])
        except (TypeError, ValueError):
            return {"error": "fee"}
        if len(name) < 2:
            return {"error": "name"}
        if not 0 <= fee <= EDU_FEE_MAX:
            return {"error": "fee"}
        with c:
            c.execute("UPDATE edu_institutions SET name=?, fee=? WHERE id=?", (name, fee, inst["id"]))
        return {"result": "updated", "edu_all": edu_list(False)}
    if act == "toggle":
        with c:
            c.execute("UPDATE edu_institutions SET active=? WHERE id=?", (0 if inst["active"] else 1, inst["id"]))
        return {"result": "toggled", "edu_all": edu_list(False)}
    return {"error": "act"}


# Kazino bannerlari (faqat shu ro'yxatdagi fayllar uzatiladi)
WEBAPP_ASSETS = {"crash.jpg": "image/jpeg", "hovuz.jpg": "image/jpeg", "kamikaze.jpg": "image/jpeg",
                 }
# 🧍 3D avatar: MakeHuman CC0 tana/kiyim/soch (skeletli) + CMU mocap harakatlar — av_*.glb (meshopt + WebP)
try:
    WEBAPP_ASSETS.update({n: "model/gltf-binary" for n in os.listdir(os.path.join(BASE_DIR, "webapp_assets"))
                          if n.startswith("av_") and n.endswith(".glb")})
except OSError:
    pass

WEBAPP_HTML = r"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Empire Stats</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;900&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#07060d; --card:#12101e; --line:#2a2440;
    --cyan:#22d3ee; --mag:#e879f9; --pur:#8b5cf6; --lime:#a3e635;
    --gold:#ffd24a; --gold2:#ffb020;
    --txt:#f3eede; --dim:#9a93b8;
  }
  *{box-sizing:border-box; -webkit-tap-highlight-color:transparent}
  body{margin:0; background:var(--bg); color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    background-image:radial-gradient(1200px 500px at 50% -10%, rgba(139,92,246,.2), transparent),
                     radial-gradient(900px 400px at 100% 0, rgba(255,210,74,.1), transparent),
                     radial-gradient(900px 400px at 0 10%, rgba(34,211,238,.1), transparent);
    min-height:100vh; padding:16px 16px 92px;}
  .hdr{display:flex; align-items:center; gap:14px; margin:6px 0 18px}
  .ava{width:58px;height:58px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-size:26px;font-weight:800;color:#07070d;
    background:linear-gradient(135deg,var(--gold),var(--mag));
    box-shadow:0 0 22px rgba(255,210,74,.45), 0 0 40px rgba(232,121,249,.3)}
  .hname{font-size:20px;font-weight:800;letter-spacing:.3px}
  .hsub{color:var(--dim);font-size:13px;margin-top:2px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .card{background:linear-gradient(180deg,var(--card),#0d0d16);border:1px solid var(--line);
    border-radius:18px;padding:16px;position:relative;overflow:hidden}
  .card::before{content:"";position:absolute;inset:0;border-radius:18px;padding:1px;
    background:linear-gradient(135deg,rgba(34,211,238,.5),transparent 40%,rgba(232,121,249,.4));
    -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
    -webkit-mask-composite:xor;mask-composite:exclude;opacity:.6;pointer-events:none}
  .lbl{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.6px}
  .val{font-size:22px;font-weight:800;margin-top:6px}
  .val.neon{color:var(--cyan);text-shadow:0 0 14px rgba(34,211,238,.6)}
  .val.mag{color:var(--mag);text-shadow:0 0 14px rgba(232,121,249,.6)}
  .val.lime{color:var(--lime);text-shadow:0 0 12px rgba(163,230,53,.5)}
  .full{grid-column:1/3}
  .row{display:flex;align-items:center;justify-content:space-between;padding:11px 4px;border-bottom:1px solid var(--line)}
  .row:last-child{border-bottom:none}
  .rk{width:26px;font-weight:800;color:var(--dim)}
  .rk.g1{color:#ffd54a;text-shadow:0 0 10px rgba(255,213,74,.6)}
  .rk.g2{color:#cfd8e3}.rk.g3{color:#e0a46a}
  .me{background:rgba(34,211,238,.08);border-radius:12px}
  .tabs{position:fixed;left:0;right:0;bottom:0;display:flex;gap:6px;padding:10px 12px;
    background:rgba(7,7,13,.9);backdrop-filter:blur(12px);border-top:1px solid var(--line)}
  .tab{flex:1;text-align:center;padding:10px 4px;border-radius:14px;font-size:13px;font-weight:700;
    color:var(--dim);border:1px solid transparent}
  .tab.on{color:var(--txt);border-color:var(--line);
    background:linear-gradient(135deg,rgba(34,211,238,.16),rgba(232,121,249,.16));
    box-shadow:0 0 18px rgba(139,92,246,.25)}
  .sec{display:none}.sec.on{display:block;animation:fade .25s ease}
  @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
  h2{font-size:15px;letter-spacing:.5px;margin:4px 0 12px;color:var(--dim);text-transform:uppercase}
  .chip{display:inline-flex;gap:6px;align-items:center;font-size:12px;color:var(--cyan);
    border:1px solid rgba(34,211,238,.4);border-radius:999px;padding:4px 10px;margin-top:8px}
  .center{text-align:center;color:var(--dim);padding:60px 20px}
  .big{font-size:40px;margin-bottom:12px}
  /* balans pill */
  .bal{margin-left:auto;text-align:right}
  .bal .n{font-size:18px;font-weight:800;color:var(--lime);text-shadow:0 0 12px rgba(163,230,53,.5)}
  .bal .l{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
  /* o'yin */
  .crashbox{height:250px;border-radius:22px;border:1px solid #2a1a4a;position:relative;overflow:hidden;
    background:radial-gradient(130% 110% at 20% 110%, #3a1d6e 0%, #1a0f38 45%, #0a0718 100%);
    display:flex;align-items:center;justify-content:center;box-shadow:inset 0 0 60px rgba(0,0,0,.6)}
  .crashbox.bust{background:radial-gradient(130% 110% at 20% 110%, #6e1d2a 0%, #2a0f16 45%, #0a0718 100%)}
  .mx{font-size:62px;font-weight:900;letter-spacing:1px;color:#fff;z-index:3;
    text-shadow:0 0 30px rgba(255,255,255,.5),0 2px 10px rgba(0,0,0,.6)}
  .mx.bust{color:#ff4d6a;text-shadow:0 0 30px rgba(255,77,106,.8)}
  .plane{position:absolute;font-size:34px;transition:none;bottom:14px;left:10px;z-index:3;filter:drop-shadow(0 0 8px rgba(255,80,100,.8))}
  .funmode{position:absolute;top:0;left:0;right:0;text-align:center;z-index:3;
    background:linear-gradient(90deg,var(--gold2),var(--gold),var(--gold2));color:#3a2600;
    font-weight:900;font-size:12px;letter-spacing:2px;padding:4px}
  .cstat{position:absolute;bottom:10px;left:0;right:0;text-align:center;z-index:3;font-size:13px;font-weight:700;color:#fff;opacity:.9}
  .betrow{display:flex;gap:8px;margin-top:14px;align-items:center}
  .ava{position:relative;overflow:hidden}
  .ava img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:50%}
  .cwait{position:absolute;inset:0;z-index:4;display:none;flex-direction:column;align-items:center;justify-content:center;gap:6px;
    background:radial-gradient(60% 60% at 50% 50%,rgba(10,7,24,.55),rgba(10,7,24,.15));pointer-events:none}
  .cwait.on{display:flex}
  .cw1{font-size:12px;letter-spacing:3px;text-transform:uppercase;color:#cbb8ff;font-weight:800}
  .cw2{font-size:54px;font-weight:900;color:#fff;text-shadow:0 0 26px rgba(232,121,249,.8)}
  .cw3{font-size:12px;color:var(--dim);font-weight:700}
  .cbar{width:62%;height:6px;border-radius:9px;background:rgba(255,255,255,.12);overflow:hidden}
  .cbar i{display:block;height:100%;width:100%;border-radius:9px;background:linear-gradient(90deg,var(--mag),var(--gold));
    box-shadow:0 0 12px rgba(255,210,74,.7)}
  .mx.fly{animation:mxp 1s ease-in-out infinite}
  @keyframes mxp{50%{transform:scale(1.06)}}
  .stepper button{width:40px}
  .bigbet.stop{color:#fff;background:linear-gradient(135deg,#f43f5e,#be123c);box-shadow:0 0 26px rgba(244,63,94,.45)}
  .bigbet.next{color:#07070d;background:linear-gradient(135deg,var(--cyan),var(--pur));box-shadow:0 0 22px rgba(34,211,238,.4)}
  .bigbet small{display:block;font-size:11px;font-weight:800;opacity:.85;margin-top:2px}
  .plist{margin-top:14px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(180deg,var(--card),#0d0d16);padding:12px 12px 6px}
  .phd{display:flex;justify-content:space-between;font-size:13px;color:var(--dim);font-weight:700;margin-bottom:8px}
  .phd b{color:var(--txt)}
  .pcol,.prow{display:grid;grid-template-columns:1fr 70px 56px 70px;gap:6px;align-items:center}
  .pcol{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.6px;padding:0 4px 6px;border-bottom:1px solid var(--line)}
  .pcol span:not(:first-child),.prow span:not(:first-child){text-align:right}
  .prow{padding:8px 4px;border-bottom:1px solid rgba(255,255,255,.04);font-size:13px;font-weight:700}
  .prow:last-child{border-bottom:none}
  .prow .pn{display:flex;align-items:center;gap:8px;min-width:0}
  .prow .pn i{flex:none;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-style:normal;font-size:11px;font-weight:900;color:#07070d}
  .prow .pn em{font-style:normal;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .prow.win{background:linear-gradient(90deg,rgba(163,230,53,.14),transparent);border-radius:10px}
  .prow.lost{opacity:.55}
  .prow.mine{outline:1px solid rgba(34,211,238,.5);border-radius:10px}
  .kf{color:var(--lime)} .kf.l{color:#ff4d6a} .kf.w{color:var(--dim)}
  .pempty{text-align:center;color:var(--dim);font-size:13px;padding:16px 0 12px}
  .stepper{display:flex;align-items:center;background:#0d0d16;border:1px solid var(--line);border-radius:14px;overflow:hidden}
  .stepper button{background:none;border:none;color:var(--gold);font-size:22px;font-weight:900;width:44px;height:48px;cursor:pointer}
  .quick{display:flex;gap:6px;margin-top:10px}
  .quick .q{flex:1;text-align:center;padding:9px;border-radius:10px;border:1px solid var(--line);font-weight:800;font-size:13px;color:var(--dim);cursor:pointer}
  .bigbet{width:100%;margin-top:12px;border:none;border-radius:16px;padding:18px;font-size:18px;font-weight:900;color:#06220d;cursor:pointer;
    background:linear-gradient(135deg,#34d399,#10b981);box-shadow:0 0 26px rgba(16,185,129,.45)}
  .bigbet.cash{color:#3a2600;background:linear-gradient(135deg,var(--gold),var(--gold2));box-shadow:0 0 26px rgba(255,180,32,.5)}
  .bigbet:disabled{opacity:.5}
  input.bet{flex:1;background:#0d0d16;border:1px solid var(--line);border-radius:14px;color:var(--txt);
    padding:13px;font-size:16px;font-weight:700;text-align:center;outline:none}
  .btn{border:none;border-radius:14px;padding:14px 18px;font-size:15px;font-weight:800;color:#07070d;cursor:pointer}
  .btn.go{background:linear-gradient(135deg,var(--cyan),var(--pur));box-shadow:0 0 20px rgba(34,211,238,.4)}
  .btn.cash{background:linear-gradient(135deg,var(--lime),#22d3ee);box-shadow:0 0 20px rgba(163,230,53,.4)}
  .btn.full{width:100%;margin-top:12px}
  .btn:disabled{opacity:.4;filter:grayscale(.5)}
  .seg{display:flex;gap:6px;margin-top:12px}
  .seg .s{flex:1;text-align:center;padding:9px;border-radius:12px;border:1px solid var(--line);
    font-size:13px;font-weight:700;color:var(--dim)}
  .seg .s.on{color:var(--txt);background:linear-gradient(135deg,rgba(34,211,238,.16),rgba(232,121,249,.16))}
  .note{text-align:center;margin-top:12px;font-size:15px;font-weight:700;min-height:22px}
  .pond{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}
  .pad{aspect-ratio:1;border-radius:14px;border:1px solid var(--line);background:#0d0d16;
    display:flex;align-items:center;justify-content:center;font-size:26px}
  .pad.active{border-color:var(--cyan);box-shadow:0 0 16px rgba(34,211,238,.35);cursor:pointer;
    background:linear-gradient(180deg,rgba(34,211,238,.1),#0d0d16)}
  .pad.safe{border-color:var(--lime);color:var(--lime)}
  .pad.bad{border-color:#ff6b6b;color:#ff6b6b}
  .pad.dim{opacity:.35}
  .frow{display:flex;gap:8px;margin-top:10px}
  select.sel{flex:1;background:#0d0d16;border:1px solid var(--line);border-radius:12px;color:var(--txt);
    padding:12px;font-size:15px;font-weight:700;outline:none;appearance:none;-webkit-appearance:none;
    background-image:linear-gradient(45deg,transparent 50%,var(--cyan) 50%),linear-gradient(135deg,var(--cyan) 50%,transparent 50%);
    background-position:calc(100% - 18px) 50%,calc(100% - 13px) 50%;background-size:5px 5px,5px 5px;background-repeat:no-repeat}
  #toast{position:fixed;left:50%;bottom:86px;transform:translateX(-50%) translateY(20px);opacity:0;
    background:#14142a;border:1px solid var(--line);color:var(--txt);padding:12px 18px;border-radius:14px;
    font-weight:700;font-size:14px;max-width:88%;text-align:center;transition:.25s;pointer-events:none;z-index:99;
    box-shadow:0 0 24px rgba(139,92,246,.4)}
  #toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
  /* oltin urg'u */
  h2{background:linear-gradient(90deg,var(--gold),var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
  .val.gold{color:var(--gold);text-shadow:0 0 14px rgba(255,210,74,.5)}
  /* crash tarix paneli */
  .hist{display:flex;gap:6px;overflow-x:auto;padding:4px 0 10px;-webkit-overflow-scrolling:touch}
  .hist::-webkit-scrollbar{display:none}
  .hc{flex:none;font-size:12px;font-weight:800;padding:4px 9px;border-radius:999px;border:1px solid var(--line)}
  .hc.lo{color:#7bdfff}.hc.mid{color:var(--mag)}.hc.hi{color:var(--gold)}
  #ccanvas{width:100%;height:100%;display:block}
  .mx{position:absolute;z-index:2}
  /* savdo tugmalari */
  .mkt{display:flex;align-items:center;gap:10px;padding:12px 6px;border-bottom:1px solid var(--line)}
  .mkt:last-child{border-bottom:none}
  .mkt .ic{font-size:22px;width:30px;text-align:center}
  .mkt .nm{font-weight:700}.mkt .pr{font-size:12px;color:var(--dim)}
  .up{color:var(--lime)}.down{color:#ff6b6b}
  .mkt .act{margin-left:auto;display:flex;gap:6px}
  .mini{border:none;border-radius:10px;padding:8px 12px;font-weight:800;font-size:13px;color:#07070d;cursor:pointer}
  .mini.buy{background:linear-gradient(135deg,var(--lime),var(--cyan))}
  .mini.sell{background:linear-gradient(135deg,var(--gold),#ff6b6b)}
  /* modal */
  .ov{position:fixed;inset:0;background:rgba(5,5,12,.72);backdrop-filter:blur(4px);z-index:50;
    display:flex;align-items:flex-end;justify-content:center;opacity:0;pointer-events:none;transition:.2s}
  .ov.show{opacity:1;pointer-events:auto}
  .sheet{width:100%;max-width:520px;background:linear-gradient(180deg,#15121f,#0c0b14);
    border:1px solid var(--line);border-radius:22px 22px 0 0;padding:18px 16px 24px;transform:translateY(30px);transition:.2s}
  .ov.show .sheet{transform:none}
  .opts{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
  .opt{flex:1 1 30%;text-align:center;padding:12px;border-radius:12px;border:1px solid var(--line);font-weight:800;cursor:pointer}
  .opt.on{background:linear-gradient(135deg,rgba(255,210,74,.2),rgba(34,211,238,.18));border-color:var(--gold)}
  /* farzand karta */
  .kid{border:1px solid var(--line);border-radius:16px;padding:14px;margin-top:12px;background:#0f0d18}
  .bars{display:flex;gap:10px;margin:8px 0}
  .bar{flex:1}.bar .t{font-size:11px;color:var(--dim)}
  .bar .track{height:7px;border-radius:5px;background:#201b33;overflow:hidden;margin-top:3px}
  .bar .fill{height:100%;border-radius:5px}
  .kbtns{display:flex;gap:8px;margin-top:10px}
  .kbtn{flex:1;text-align:center;padding:10px;border-radius:12px;border:1px solid var(--line);font-weight:700;font-size:13px;cursor:pointer}
  /* ═════════ 👑 QIROLLIK OLTIN MAVZUSI (Crash'dan tashqari hammasi) ═════════ */
  :root{
    --bg:#0a0705; --card:#17110a; --line:#4a3714;
    --cyan:#ffd77a; --mag:#f5c451; --pur:#b8862b; --lime:#ffe9a8;
    --gold:#ffd24a; --gold2:#d99a1e; --txt:#fbf1d6; --dim:#c2a96e;
    --g-metal:linear-gradient(135deg,#7a5410 0%,#f7d774 22%,#fff6c9 38%,#e2ad35 55%,#8c5e0e 78%,#f2cf6b 100%);
    --g-text:linear-gradient(180deg,#fff7d1 0%,#ffd86b 45%,#c98d18 70%,#ffe39a 100%);
    --g-border:linear-gradient(135deg,#fff1b8,#c48a1a 30%,#ffe08a 55%,#8a5b0c 80%,#ffd56a);
  }
  /* crash o'z neon ranglarini saqlaydi */
  #s-crash{--card:#12101e;--line:#2a2440;--cyan:#22d3ee;--mag:#e879f9;--pur:#8b5cf6;--lime:#a3e635;
    --gold:#ffd24a;--gold2:#ffb020;--txt:#f3eede;--dim:#9a93b8}
  body{background-color:var(--bg);
    background-image:
      radial-gradient(900px 420px at 50% -8%, rgba(255,200,80,.22), transparent 70%),
      radial-gradient(600px 380px at 110% 30%, rgba(160,40,40,.16), transparent 70%),
      radial-gradient(600px 380px at -10% 60%, rgba(120,70,10,.18), transparent 70%),
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='56'%3E%3Cpath d='M28 4l6 10-6 10-6-10zM28 32l6 10-6 10-6-10zM4 28l10-6 10 6-10 6zM32 28l10-6 10 6-10 6z' fill='none' stroke='%23d4a23a' stroke-opacity='.07'/%3E%3C/svg%3E");
    padding-bottom:110px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  .royal,h2,.hname{font-family:"Cinzel","Trajan Pro",Georgia,serif}
  /* sarlavha */
  .hdr{position:relative;padding:14px 14px;border-radius:22px;margin:4px 0 18px;
    background:linear-gradient(180deg,rgba(40,28,10,.85),rgba(18,12,6,.9));box-shadow:0 10px 30px rgba(0,0,0,.5),inset 0 1px 0 rgba(255,230,160,.25)}
  .hdr::before{content:"";position:absolute;inset:0;border-radius:22px;padding:1.5px;background:var(--g-border);
    -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
  .ava{width:62px;height:62px;color:#2a1a02;background:var(--g-metal);overflow:visible;
    box-shadow:0 0 0 3px #1a1206,0 0 0 5px #e6b84a,0 0 26px rgba(255,200,70,.55)}
  .ava img{border-radius:50%}
  .ava::after{content:"👑";position:absolute;top:-17px;left:50%;transform:translateX(-50%) rotate(-8deg);font-size:20px;
    filter:drop-shadow(0 2px 4px rgba(0,0,0,.6));animation:crown 3s ease-in-out infinite}
  @keyframes crown{50%{transform:translateX(-50%) rotate(8deg) translateY(-2px)}}
  .hname{font-size:19px;font-weight:700;letter-spacing:1px;background:var(--g-text);-webkit-background-clip:text;background-clip:text;color:transparent}
  .hsub{color:var(--dim)}
  .bal .n{background:var(--g-text);-webkit-background-clip:text;background-clip:text;color:transparent;text-shadow:none;
    filter:drop-shadow(0 0 8px rgba(255,200,70,.45));font-size:20px}
  .bal .l{color:var(--dim);letter-spacing:2px}
  /* sarlavhalar */
  h2{font-size:16px;letter-spacing:2.5px;text-align:center;margin:6px 0 14px;font-weight:700;
    background:var(--g-text);-webkit-background-clip:text;background-clip:text;color:transparent;position:relative}
  h2::before,h2::after{content:"";display:inline-block;width:42px;height:1px;vertical-align:middle;margin:0 10px;
    background:linear-gradient(90deg,transparent,#e2b04a)}
  h2::after{background:linear-gradient(90deg,#e2b04a,transparent)}
  /* kartalar: oltin hoshiya + yaltiroq nur */
  .sec:not(#s-crash) .card,.kid{background:linear-gradient(160deg,#21180b 0%,#120d07 60%,#1a1209 100%);border:none;
    box-shadow:0 8px 24px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,232,170,.18)}
  .sec:not(#s-crash) .card::before,.kid::before{background:var(--g-border);opacity:.9}
  .kid{position:relative;border-radius:16px}
  .kid::before{content:"";position:absolute;inset:0;border-radius:16px;padding:1px;
    -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
  .sec:not(#s-crash) .card::after{content:"";position:absolute;top:0;bottom:0;left:-60%;width:40%;pointer-events:none;
    background:linear-gradient(105deg,transparent,rgba(255,240,190,.10),transparent);transform:skewX(-18deg);animation:shine 6s ease-in-out infinite}
  .sec:not(#s-crash) .grid .card:nth-child(2n)::after{animation-delay:1.5s}
  .sec:not(#s-crash) .grid .card:nth-child(3n)::after{animation-delay:3s}
  @keyframes shine{0%,60%{left:-60%}100%{left:130%}}
  .lbl{color:var(--dim);letter-spacing:1.2px}
  .sec:not(#s-crash) .val,.val.neon,.val.mag,.val.lime,.val.gold{background:var(--g-text);-webkit-background-clip:text;background-clip:text;
    color:transparent;text-shadow:none;filter:drop-shadow(0 0 6px rgba(255,190,60,.35))}
  .chip{color:var(--gold);border-color:rgba(255,210,74,.45);background:rgba(255,210,74,.06)}
  /* reyting */
  .row{border-bottom-color:rgba(226,176,74,.16)}
  .rk{color:var(--dim);font-family:"Cinzel",Georgia,serif}
  .rk.g1,.rk.g2,.rk.g3{width:28px;height:28px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;color:#2a1a02;font-size:13px;text-shadow:none}
  .rk.g1{background:var(--g-metal);box-shadow:0 0 14px rgba(255,210,74,.7)}
  .rk.g2{background:linear-gradient(135deg,#8d969f,#f1f4f7,#9aa3ab)}
  .rk.g3{background:linear-gradient(135deg,#8a4d1c,#f0b07a,#9a5a26)}
  .me{background:rgba(255,210,74,.09)}
  /* tugmalar: metall oltin + yaltirash */
  .btn,.mini,.kbtn{position:relative;overflow:hidden;transition:transform .12s,filter .12s}
  .btn.go,.btn.cash,.mini.buy{color:#2b1b02;background:var(--g-metal);background-size:200% 200%;
    box-shadow:0 6px 18px rgba(200,140,30,.35),inset 0 1px 0 rgba(255,255,255,.6),inset 0 -2px 0 rgba(90,55,5,.5);
    text-shadow:0 1px 0 rgba(255,240,190,.6);animation:metal 5s ease-in-out infinite}
  .btn.cash{background:linear-gradient(135deg,#5b0f14,#b3242c 40%,#e0484f 55%,#7a1218);color:#ffe9b0;text-shadow:0 1px 1px rgba(0,0,0,.5);
    box-shadow:0 6px 18px rgba(160,30,40,.4),inset 0 0 0 1.5px #e6b84a}
  .mini.sell{color:#ffe9b0;background:linear-gradient(135deg,#5b0f14,#c0303a,#7a1218);box-shadow:inset 0 0 0 1px #e6b84a}
  @keyframes metal{50%{background-position:100% 100%}}
  .btn::after,.mini::after{content:"";position:absolute;top:0;bottom:0;left:-70%;width:45%;
    background:linear-gradient(105deg,transparent,rgba(255,255,255,.55),transparent);transform:skewX(-20deg);animation:shine 3.8s ease-in-out infinite}
  .btn:active,.mini:active,.kbtn:active,.opt:active{transform:scale(.96);filter:brightness(1.15)}
  .kbtn{border:1px solid #6b4f1c;background:linear-gradient(180deg,#2a1f0e,#160f07);color:var(--txt)}
  .kbtn:active{border-color:var(--gold)}
  /* tanlovlar */
  .sec:not(#s-crash) input.bet{background:#140e07;}
  select.sel,.sec:not(#s-crash) input.bet{border:1px solid #6b4f1c;color:var(--txt);box-shadow:inset 0 2px 6px rgba(0,0,0,.5)}
  select.sel{background-color:#140e07;background-image:linear-gradient(45deg,transparent 50%,var(--gold) 50%),linear-gradient(135deg,var(--gold) 50%,transparent 50%);
    background-position:calc(100% - 18px) 50%,calc(100% - 13px) 50%;background-size:5px 5px,5px 5px;background-repeat:no-repeat}
  select.sel:focus,.sec:not(#s-crash) input.bet:focus{border-color:var(--gold);box-shadow:0 0 0 2px rgba(255,210,74,.25)}
  .seg .s{border-color:#6b4f1c;background:#140e07}
  .seg .s.on{color:#2b1b02;background:var(--g-metal);border-color:#ffe08a;box-shadow:0 0 14px rgba(255,200,70,.4)}
  .opt{border-color:#6b4f1c;background:#140e07}
  .opt.on{background:var(--g-metal);color:#2b1b02;border-color:#ffe08a}
  .sheet{background:linear-gradient(180deg,#22180b,#0f0a05);border-color:#8a6420;box-shadow:0 -10px 40px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,230,160,.3)}
  #toast{background:linear-gradient(180deg,#2a1e0c,#140e07);border:1px solid #c79a3a;box-shadow:0 0 24px rgba(255,190,60,.35)}
  .bar .track{background:#2a1f0e}
  .up{color:#9be36b}.down{color:#ff7a6b}
  .mkt{border-bottom-color:rgba(226,176,74,.16)}
  .mkt .ic{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;
    background:radial-gradient(circle at 35% 30%,#3a2a10,#140e07);box-shadow:inset 0 0 0 1.5px #c9993a}
  /* baqa: oltin nilufarlar */
  .pad{border:1px solid #5a421a;background:radial-gradient(circle at 50% 40%,#1f170b,#100b06)}
  .pad.active{border-color:#ffd24a;background:radial-gradient(circle at 50% 40%,rgba(255,210,74,.22),#140e07);
    box-shadow:0 0 16px rgba(255,200,70,.45);animation:padglow 1.6s ease-in-out infinite}
  @keyframes padglow{50%{box-shadow:0 0 26px rgba(255,210,74,.75)}}
  .pad.safe{border-color:#ffe08a;color:#ffe08a;background:radial-gradient(circle,rgba(255,210,74,.3),#140e07)}
  .pad.bad{border-color:#e04b4b;background:radial-gradient(circle,rgba(224,75,75,.3),#140e07)}
  /* ───── 🎰 Kazino lobbisi ───── */
  .glob{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .gcard{position:relative;aspect-ratio:.68;border-radius:22px;overflow:hidden;cursor:pointer;isolation:isolate;
    box-shadow:0 12px 28px rgba(0,0,0,.55),inset 0 0 0 1.5px rgba(255,214,110,.55);transition:transform .15s}
  .gcard:active{transform:scale(.96)}
  .gimg{position:absolute;inset:0;background-size:cover;z-index:-2;animation:kb 9s ease-in-out infinite alternate}
  .g-crash .gimg{background-position:58% 50%;background-size:auto 108%}
  .g-hovuz .gimg{background-position:50% 100%}
  @keyframes kb{from{transform:scale(1.02)}to{transform:scale(1.1) translateY(-2%)}}
  .gcard::before{content:"";position:absolute;inset:0;z-index:-1;
    background:linear-gradient(180deg,rgba(6,4,14,.78) 0%,rgba(6,4,14,.25) 34%,rgba(0,0,0,0) 55%,rgba(0,0,0,.55) 100%)}
  .g-crash::before{background:linear-gradient(180deg,rgba(40,8,60,.85) 0%,rgba(40,8,60,.3) 34%,rgba(0,0,0,0) 55%,rgba(0,0,0,.6) 100%)}
  .gcard::after{content:"";position:absolute;top:0;bottom:0;left:-70%;width:45%;pointer-events:none;
    background:linear-gradient(105deg,transparent,rgba(255,240,200,.28),transparent);transform:skewX(-18deg);animation:shine 5s ease-in-out infinite}
  .g-hovuz::after{animation-delay:2.5s}
  .gtag{position:absolute;top:0;left:50%;transform:translateX(-50%);padding:5px 14px 6px;border-radius:0 0 12px 12px;
    background:rgba(10,8,20,.75);backdrop-filter:blur(4px);font-size:10.5px;font-weight:800;letter-spacing:.8px;color:#e9ddff;white-space:nowrap}
  .gtitle{position:absolute;top:30px;left:0;right:0;text-align:center;font-weight:900;font-size:27px;line-height:.98;color:#fff;
    letter-spacing:.5px;text-shadow:0 3px 0 rgba(0,0,0,.35),0 6px 18px rgba(0,0,0,.6);font-family:-apple-system,"Segoe UI",Roboto,sans-serif}
  .gfoot{position:absolute;left:10px;right:10px;bottom:10px;display:flex;align-items:center;justify-content:space-between}
  .glive{font-size:11px;font-weight:800;color:#fff;background:rgba(0,0,0,.5);padding:5px 9px;border-radius:999px;display:flex;align-items:center;gap:5px}
  .glive i{width:7px;height:7px;border-radius:50%;background:#3ef07a;box-shadow:0 0 8px #3ef07a;animation:blink 1.2s ease-in-out infinite}
  @keyframes blink{50%{opacity:.3}}
  .gplay{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;color:#2b1b02;
    background:var(--g-metal);box-shadow:0 4px 12px rgba(0,0,0,.5)}
  .gnote{text-align:center;color:var(--dim);font-size:12px;margin-top:14px}
  .gback{display:inline-flex;align-items:center;gap:4px;margin:0 0 10px;padding:7px 14px;border-radius:999px;font-weight:800;font-size:13px;
    color:#ffe08a;background:linear-gradient(180deg,#2a1e0c,#140e07);box-shadow:inset 0 0 0 1px #8a6420;cursor:pointer}
  .tab .ti .cz-ico{display:block;filter:drop-shadow(0 2px 3px rgba(0,0,0,.6))}
  .tab.on .ti .cz-ico{animation:czpulse 1.8s ease-in-out infinite}
  @keyframes czpulse{50%{filter:drop-shadow(0 0 8px rgba(255,220,120,.9))}}
  /* ───── 🛩 Kamikaze ───── */
  .kbox{position:relative;height:340px;border-radius:22px;overflow:hidden;
    box-shadow:0 12px 28px rgba(0,0,0,.55),inset 0 0 0 1.5px rgba(255,214,110,.5);background:#06203a}
  #kcanvas{width:100%;height:100%;display:block;touch-action:manipulation}
  .kmsg{position:absolute;left:50%;top:44%;transform:translate(-50%,-50%) scale(.6);opacity:0;pointer-events:none;text-align:center;
    font-weight:900;font-size:34px;color:#fff;text-shadow:0 4px 0 rgba(0,0,0,.35),0 0 24px rgba(255,200,70,.8);transition:all .3s cubic-bezier(.2,1.6,.4,1);white-space:nowrap}
  .kmsg.on{opacity:1;transform:translate(-50%,-50%) scale(1)}
  .kmsg small{display:block;font-size:16px;font-weight:800;color:#ffe08a;margin-top:4px}
  .kmsg.bad{color:#ff6b6b;text-shadow:0 4px 0 rgba(0,0,0,.35),0 0 24px rgba(255,60,60,.8)}
  .knote{text-align:center;color:var(--dim);font-size:13px;margin:10px 0 2px;min-height:18px}
  .knote b{color:var(--gold)}
  .kq{margin-top:10px}
  .gtest{position:absolute;top:9px;left:-36px;transform:rotate(-40deg);padding:2px 30px;border-radius:8px;
    background:#ff3b5c;color:#fff;font-weight:900;font-size:11px;letter-spacing:1px;box-shadow:0 4px 10px rgba(0,0,0,.4)}
  .g-kami .gimg{background-position:50% 60%}
  .g-kami::before{background:linear-gradient(180deg,rgba(4,10,30,.85) 0%,rgba(4,10,30,.3) 34%,rgba(0,0,0,0) 55%,rgba(0,0,0,.6) 100%)}
  /* ───── 🎵 ovoz tugmalari (o'yinlarda) ───── */
  #s-crash,#s-frog,#s-kami{position:relative}
  .sndbar{position:absolute;top:0;right:0;display:flex;gap:6px;z-index:6}
  .sndbar span{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;cursor:pointer;
    background:linear-gradient(180deg,#2a1e0c,#140e07);box-shadow:inset 0 0 0 1px #8a6420}
  .sndbar span.off{opacity:.45;filter:grayscale(1)}
  /* ───── 👶 Farzand kartalari: har bosqichga alohida dunyo ───── */
  .kidc{position:relative;overflow:hidden;border-radius:22px;padding:16px 14px 14px;margin-top:14px;isolation:isolate;
    box-shadow:0 12px 26px rgba(0,0,0,.5),inset 0 0 0 1.5px rgba(255,214,110,.45)}
  .kidc::before{content:"";position:absolute;inset:0;z-index:-2}
  .kidc.st-baby::before{background:radial-gradient(120% 90% at 20% 0%,#ffd6e8 0%,#c9b6ff 45%,#6a5acd 100%)}
  .kidc.st-kinder::before{background:linear-gradient(160deg,#ffe066 0%,#ff9f43 40%,#ee5a6f 100%)}
  .kidc.st-school::before{background:linear-gradient(170deg,#1f5f45 0%,#164433 60%,#0f2f24 100%)}
  .kidc.st-school::after{content:"";position:absolute;inset:0;z-index:-1;opacity:.18;
    background:repeating-linear-gradient(0deg,transparent 0 26px,rgba(255,255,255,.5) 26px 27px)}
  .kidc.st-college::before{background:linear-gradient(160deg,#0b3d91 0%,#08285e 60%,#061a3d 100%)}
  .kidc.st-college::after{content:"";position:absolute;inset:0;z-index:-1;opacity:.2;
    background-image:linear-gradient(rgba(120,200,255,.6) 1px,transparent 1px),linear-gradient(90deg,rgba(120,200,255,.6) 1px,transparent 1px);background-size:18px 18px}
  .kidc.st-uni::before{background:radial-gradient(120% 90% at 80% 0%,#3b2a6b 0%,#1d1440 55%,#0d0a20 100%)}
  .kidc.st-uni::after{content:"";position:absolute;left:0;right:0;top:0;height:4px;z-index:-1;background:var(--g-metal)}
  .kidc.st-work::before{background:linear-gradient(160deg,#1c1c22 0%,#2b2410 60%,#0f0d08 100%)}
  .kdeco{position:absolute;inset:0;z-index:-1;pointer-events:none}
  .kdeco i{position:absolute;font-style:normal;font-size:22px;opacity:.28;animation:kfloat 6s ease-in-out infinite;animation-delay:calc(var(--i)*-1.4s)}
  .kdeco i:nth-child(1){top:10%;right:8%}.kdeco i:nth-child(2){top:58%;right:16%;font-size:18px}
  .kdeco i:nth-child(3){top:32%;right:34%;font-size:15px}.kdeco i:nth-child(4){bottom:12%;left:46%;font-size:16px}
  @keyframes kfloat{50%{transform:translateY(-7px) rotate(8deg)}}
  .ktop{display:flex;align-items:center;gap:14px}
  .kava{position:relative;width:74px;height:74px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;
    background:radial-gradient(circle at 35% 30%,rgba(255,255,255,.55),rgba(255,255,255,.12));box-shadow:0 0 0 3px rgba(255,255,255,.35),0 8px 18px rgba(0,0,0,.35)}
  .kem{font-size:44px;line-height:1;animation:kbob 3.2s ease-in-out infinite}
  @keyframes kbob{50%{transform:translateY(-3px) scale(1.04)}}
  .kacc{position:absolute;right:-4px;bottom:-2px;font-size:24px;filter:drop-shadow(0 2px 3px rgba(0,0,0,.45))}
  .kname{font-size:21px;font-weight:900;color:#fff;text-shadow:0 2px 6px rgba(0,0,0,.45)}
  .kchips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
  .kchip{font-size:11.5px;font-weight:800;padding:4px 9px;border-radius:999px;background:rgba(0,0,0,.28);color:#fff}
  .kchip.st{background:rgba(255,255,255,.22)}
  .kidc .bars .t,.kgrow .t{color:rgba(255,255,255,.88)}
  .kgrow{margin-top:12px}.kgrow .t{display:flex;justify-content:space-between;font-size:11.5px;font-weight:700}
  .kgrow .track{height:8px;border-radius:6px;background:rgba(0,0,0,.3);overflow:hidden;margin-top:4px}
  .kgrow .fill{height:100%;border-radius:6px;background:var(--g-metal);box-shadow:0 0 10px rgba(255,210,74,.6)}
  .kidc .bar .track{background:rgba(0,0,0,.3)}
  .kblock{margin-top:8px;font-size:12px;font-weight:800;color:#fff;background:rgba(255,60,60,.35);padding:6px 10px;border-radius:10px}
  .kinst{margin-top:8px;font-size:12.5px;color:#fff;background:rgba(0,0,0,.25);padding:7px 10px;border-radius:10px}
  .kinst.dim{opacity:.8}
  .kwork{margin-top:12px;font-size:13px;color:#ffe9a8;background:rgba(0,0,0,.3);padding:8px 10px;border-radius:12px}
  .kidc .kbtns{flex-wrap:wrap}
  .kidc .kbtn{background:rgba(0,0,0,.32);border-color:rgba(255,255,255,.28);color:#fff;flex:1 1 30%}
  .kmeal{margin-top:6px;font-size:11.5px;font-weight:800;color:rgba(255,255,255,.85)}
  .kmeal.ready{color:#fff;display:inline-block;background:rgba(70,220,120,.35);padding:3px 9px;border-radius:999px;animation:padglow 1.6s ease-in-out infinite}
  .kidc .kbtn.wait{opacity:.7}
  .kgshop{margin-top:12px}.kgh{display:flex;justify-content:space-between;align-items:center;margin:0 4px 8px;font-size:14px}
  .kgh span{color:var(--dim);font-size:12px}
  .card.kown{opacity:.6}
  .kidc .kbtn.kfee{background:var(--g-metal);color:#2b1b02;border-color:#ffe08a;font-weight:900}
  /* 🏫 Ta'lim yo'li */
  .edupath{margin-top:20px}
  .egrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
  .etile{text-align:center;padding:12px 4px;border-radius:16px;background:linear-gradient(180deg,#1a140a,#0f0b06);
    box-shadow:inset 0 0 0 1px #4a3714;opacity:.55;filter:grayscale(.6)}
  .etile.open{opacity:1;filter:none;cursor:pointer;box-shadow:inset 0 0 0 1.5px #d9a63c,0 6px 16px rgba(0,0,0,.4);animation:padglow 2.4s ease-in-out infinite}
  .eic{font-size:28px}.enm{font-weight:900;font-size:12.5px;margin-top:4px}.esub{font-size:10.5px;color:var(--dim);margin-top:2px}
  /* owner: muassasalar */
  .egrp{margin:12px 0 6px;font-weight:800;font-size:13px;color:var(--gold)}
  .erow{display:flex;gap:6px;align-items:center;margin-bottom:6px}
  .erow.off{opacity:.5}
  .erow input{min-width:0;background:#140e07;border:1px solid #6b4f1c;border-radius:10px;color:var(--txt);padding:8px;font-weight:700;font-size:13px;outline:none}
  .erow .en{flex:1}.erow .ef{width:84px;text-align:right}
  .erow span{width:32px;height:32px;flex:none;display:flex;align-items:center;justify-content:center;border-radius:9px;cursor:pointer;
    background:linear-gradient(180deg,#2a1e0c,#140e07);box-shadow:inset 0 0 0 1px #8a6420}
  /* ───── 🧒 3D farzand studiyasi ───── */
  .kst{position:fixed;inset:0;z-index:80;background:rgba(5,4,2,.82);backdrop-filter:blur(6px);display:none;align-items:flex-end;justify-content:center}
  .kst.show{display:flex;animation:fade .25s ease}
  .kst-in{position:relative;width:100%;max-width:540px;height:94vh;border-radius:26px 26px 0 0;overflow:hidden;display:flex;flex-direction:column;
    box-shadow:0 -10px 40px rgba(0,0,0,.6),inset 0 0 0 1.5px rgba(255,214,110,.55);isolation:isolate}
  .kst-in::before{content:"";position:absolute;inset:0;z-index:-1}
  .kst-in.st-baby::before{background:radial-gradient(120% 70% at 50% 30%,#ffe0ef 0%,#c9b6ff 50%,#4c3c9a 100%)}
  .kst-in.st-kinder::before{background:radial-gradient(120% 70% at 50% 30%,#fff3b0 0%,#ffb347 50%,#c2410c 100%)}
  .kst-in.st-school::before{background:radial-gradient(120% 70% at 50% 30%,#4caf87 0%,#1f5f45 55%,#0b2a1e 100%)}
  .kst-in.st-college::before{background:radial-gradient(120% 70% at 50% 30%,#4f8be6 0%,#0b3d91 55%,#061a3d 100%)}
  .kst-in.st-uni::before{background:radial-gradient(120% 70% at 50% 30%,#7b61c9 0%,#2a1d5c 55%,#0d0a20 100%)}
  .kst-in.st-work::before{background:radial-gradient(120% 70% at 50% 30%,#8a7a4a 0%,#2b2410 55%,#0f0d08 100%)}
  .kst-hd{display:flex;justify-content:space-between;align-items:flex-start;padding:16px 16px 6px}
  .kst-name{font-size:24px;font-weight:900;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,.4)}
  .kst-sub{font-size:12.5px;color:rgba(255,255,255,.9);margin-top:3px;font-weight:700}
  .kst-x{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;color:#fff;cursor:pointer;background:rgba(0,0,0,.35)}
  .kst-stage{position:relative;flex:1;min-height:300px}
  #kstCv,#astCv{width:100%;height:100%;display:block;touch-action:none;cursor:grab}
  .kst-col{position:absolute;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:12px}
  .kst-col.l{left:10px}.kst-col.r{right:10px}
  .kslot{width:66px;height:66px;border-radius:18px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;
    background:rgba(0,0,0,.38);backdrop-filter:blur(4px);box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.35);transition:transform .15s}
  .kslot .ki{font-size:28px;line-height:1}.kslot .kn{font-size:8.5px;font-weight:800;color:#fff;margin-top:4px;text-align:center;line-height:1.05}
  .kslot.on{box-shadow:inset 0 0 0 2px #ffd24a,0 0 18px rgba(255,210,74,.7);transform:scale(1.06)}
  .kst-load{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800}
  .kst-rot{display:flex;align-items:center;justify-content:center;gap:18px;padding:6px 0 4px;color:#fff}
  .kst-rot span{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;cursor:pointer;background:rgba(0,0,0,.35);box-shadow:inset 0 0 0 1px rgba(255,255,255,.3)}
  .kst-rot b{min-width:110px;text-align:center;font-size:13px}
  .kst-pick{min-height:118px;padding:8px 12px 18px;background:linear-gradient(180deg,rgba(0,0,0,.25),rgba(0,0,0,.55))}
  .kst-hint{color:rgba(255,255,255,.85);font-size:12.5px;text-align:center;padding:26px 10px}
  .kst-pt{font-weight:900;font-size:13px;color:#ffe08a;margin:2px 4px 8px}
  .kst-opts{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;scrollbar-width:none}
  .kst-opts::-webkit-scrollbar{display:none}
  .kopt{flex:none;width:76px;padding:8px 4px;border-radius:14px;text-align:center;cursor:pointer;background:rgba(255,255,255,.1);box-shadow:inset 0 0 0 1px rgba(255,255,255,.2)}
  .kopt span{font-size:26px;display:block}.kopt small{display:block;font-size:10px;font-weight:700;color:#fff;margin-top:4px;line-height:1.1}
  .kopt.on{background:var(--g-metal);box-shadow:0 0 14px rgba(255,210,74,.6)}.kopt.on small{color:#2b1b02}
  .kst-in.st-av::before{background:radial-gradient(120% 70% at 50% 34%,#7a5a1c 0%,#2e220c 55%,#0d0904 100%)}
  .kst-in.st-av.bg-night::before{background:radial-gradient(120% 70% at 50% 34%,#2b4785 0%,#0d1733 55%,#03050c 100%)}
  .kst-in.st-av.bg-studio::before{background:radial-gradient(120% 70% at 50% 34%,#a8a8a8 0%,#4a4a4a 55%,#151515 100%)}
  .kst-in.st-av.bg-sunset::before{background:radial-gradient(120% 70% at 50% 34%,#f6a560 0%,#a4385a 55%,#2a0c22 100%)}
  .kst-in.st-av.bg-emerald::before{background:radial-gradient(120% 70% at 50% 34%,#24916a 0%,#0b3a2a 55%,#020d09 100%)}
  .asw{display:block;width:18px;height:18px;border-radius:50%;margin-top:3px;box-shadow:inset 0 0 0 2px rgba(255,255,255,.75),0 1px 4px rgba(0,0,0,.5)}
  .asw.big{width:30px;height:30px;margin:0 auto}
  .kslot .asw{position:absolute;right:5px;top:5px;width:14px;height:14px;margin:0}
  .kslot .kv{position:absolute;right:3px;top:2px;font-size:14px}
  .avbusy{position:absolute;left:50%;top:12px;transform:translateX(-50%);display:none;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;background:rgba(0,0,0,.45);font-size:16px}
  .kst-opts.emo{display:grid;grid-auto-flow:column;grid-template-rows:repeat(2,auto);grid-auto-columns:64px;gap:8px;overflow-x:auto}
  .kst-opts.emo .kopt{width:64px}
  .kst-in.st-av .kst-rot{gap:8px}.kst-in.st-av .kst-rot b{min-width:84px;font-size:12px}.kst-in.st-av .kst-rot span{width:38px;height:38px;font-size:19px}
  .kst-rot .ave{background:var(--g-metal);color:#2b1b02;box-shadow:0 0 16px rgba(255,210,74,.6)}
  .kst-rot span.on{box-shadow:inset 0 0 0 2px #ffd24a,0 0 14px rgba(255,210,74,.7)}
  .kst-in.st-av .kslot{position:relative}
  .avg{display:flex;gap:8px;justify-content:center;padding:2px 0 4px}
  .avg span{padding:7px 16px;border-radius:999px;font-size:13px;font-weight:800;color:#fff;cursor:pointer;background:rgba(0,0,0,.35);box-shadow:inset 0 0 0 1px rgba(255,255,255,.25)}
  .avg span.on{background:var(--g-metal);color:#2b1b02;box-shadow:0 0 14px rgba(255,210,74,.6)}
  .avtest{font-size:10px;padding:2px 7px;border-radius:8px;background:#ff4d6d;color:#fff;vertical-align:middle;letter-spacing:.06em}
  #astZ.on{background:var(--g-metal);color:#2b1b02}
  .rpair{margin-bottom:14px;background:linear-gradient(150deg,rgba(255,92,138,.16),rgba(255,210,74,.08))}
  .rpair .rph{display:flex;align-items:center;gap:12px}
  .rpair .rpi{width:48px;height:48px;flex:none;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:26px;background:var(--g-metal);box-shadow:0 0 16px rgba(255,210,74,.45)}
  .rpair .rpok,.rpair .rpw{margin-top:10px;padding:10px 12px;border-radius:12px;background:rgba(0,0,0,.25);line-height:1.45}
  .rpair .rpsep{margin:12px 0 6px;text-align:center;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim,#a99)}
  .rpair .rpid,.chs .chq{display:flex;gap:8px}.rpair .rpid .bet,.chs .chq .bet{flex:1;min-width:0}.rpair .rpid .btn,.chs .chq .btn{flex:none;padding:0 16px}
  .tab{position:relative}.tbadge{position:absolute;top:3px;right:calc(50% - 22px);min-width:17px;height:17px;padding:0 4px;border-radius:9px;background:#ff3b5c;color:#fff;font-size:10px;font-weight:800;line-height:17px;box-shadow:0 0 8px rgba(255,59,92,.7)}
  .chava{position:relative;flex:none;width:44px;height:44px;border-radius:50%;overflow:hidden;display:flex;align-items:center;justify-content:center;font-weight:800;color:#2b1b02;background:var(--g-metal)}
  .chava img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
  .chfound{display:flex;gap:12px;align-items:center;margin-top:12px}.chfound .chava{width:54px;height:54px}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.chbtns{display:flex;gap:8px;margin-top:12px}.chbtns .btn{flex:1}
  .chlist{display:flex;flex-direction:column;gap:8px}
  .chrow{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:16px;cursor:pointer;background:rgba(255,255,255,.04);box-shadow:inset 0 0 0 1px rgba(255,210,74,.14)}
  .chrow.un{box-shadow:inset 0 0 0 1px rgba(255,210,74,.55);background:rgba(255,210,74,.07)}
  .chr-m{flex:1;min-width:0}.chr-t{display:flex;justify-content:space-between;gap:8px}.chr-t .hsub{flex:none;font-size:10px}
  .chr-l{font-size:12.5px;opacity:.75;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
  .chbadge{flex:none;min-width:22px;height:22px;padding:0 6px;border-radius:11px;background:#ff3b5c;color:#fff;font-size:11px;font-weight:800;line-height:22px;text-align:center}
  .chv{position:fixed;inset:0;z-index:85;display:none;background:rgba(5,4,2,.6)}.chv.show{display:flex;justify-content:center}
  .chv-in{width:100%;max-width:560px;height:100%;display:flex;flex-direction:column;background:linear-gradient(180deg,#140f06,#07070d)}
  .chv-hd{display:flex;align-items:center;gap:10px;padding:12px 12px 10px;border-bottom:1px solid rgba(255,210,74,.2)}
  .chv-b{font-size:30px;line-height:1;padding:0 8px 4px 2px;cursor:pointer;color:#ffd24a}.chv-n{flex:1;min-width:0}.chv-n b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .chv-i{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;cursor:pointer;background:rgba(255,210,74,.12);box-shadow:inset 0 0 0 1px rgba(255,210,74,.35);color:#ffd24a}
  .chv-info{display:none;padding:0 12px 10px;border-bottom:1px solid rgba(255,210,74,.12)}.chv-info.on{display:block}
  .chv-msgs{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:6px}
  .msg{max-width:80%;align-self:flex-start;padding:8px 11px 5px;border-radius:16px 16px 16px 4px;background:rgba(255,255,255,.08);word-wrap:break-word;overflow-wrap:anywhere}
  .msg.me{align-self:flex-end;border-radius:16px 16px 4px 16px;background:linear-gradient(135deg,#c99a2e,#8a6416);color:#fff}
  .msg .mt{font-size:14.5px;line-height:1.38}.msg .mm{font-size:9.5px;opacity:.7;text-align:right;margin-top:3px}.msg .tick{margin-left:5px}
  .chempty{margin-top:30%}
  .chv-ft{display:flex;gap:8px;align-items:flex-end;padding:10px 12px calc(10px + env(safe-area-inset-bottom));border-top:1px solid rgba(255,210,74,.2)}
  .chv-ft textarea{flex:1;resize:none;min-height:44px;max-height:110px;padding:12px 14px;border-radius:22px;border:1px solid rgba(255,210,74,.35);background:rgba(0,0,0,.35);color:#fff;font:inherit;font-size:15px;outline:none}
  .chv-ft .btn{flex:none;width:48px;height:44px;padding:0;border-radius:50%;font-size:18px}
  .avcard{display:flex;align-items:center;gap:14px;margin-top:12px;cursor:pointer}
  .avcard .avi{width:56px;height:56px;flex:none;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:30px;background:var(--g-metal);box-shadow:0 0 18px rgba(255,210,74,.45)}
  .kpar{margin-top:8px;font-size:12px;font-weight:700;color:rgba(255,255,255,.92)}
  .k3d{position:absolute;top:12px;right:12px;z-index:2;font-size:11px;font-weight:900;color:#2b1b02;background:var(--g-metal);padding:4px 9px;border-radius:999px;
    box-shadow:0 4px 10px rgba(0,0,0,.35);animation:padglow 2s ease-in-out infinite}
  /* ───── pastki tugmalar: kattaroq, nomli, oltin ───── */
  .tabs{gap:4px;padding:8px 8px calc(10px + env(safe-area-inset-bottom));overflow-x:auto;scrollbar-width:none;
    background:linear-gradient(180deg,rgba(28,20,8,.96),rgba(10,7,4,.98));border-top:none;
    box-shadow:0 -8px 30px rgba(0,0,0,.6)}
  .tabs::-webkit-scrollbar{display:none}
  .tabs::before{content:"";position:absolute;left:0;right:0;top:0;height:1.5px;background:var(--g-border)}
  .tab{flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;gap:3px;padding:9px 2px 7px;border-radius:16px;
    color:var(--dim);border:1px solid transparent;transition:transform .18s,background .18s}
  .tab .ti{font-size:25px;line-height:1;filter:drop-shadow(0 2px 3px rgba(0,0,0,.6));transition:transform .18s}
  .tab .tl{font-size:9.5px;font-weight:800;letter-spacing:.3px;white-space:nowrap}
  .tab.on{color:#2b1b02;background:var(--g-metal);border-color:#ffe08a;transform:translateY(-4px);
    box-shadow:0 8px 20px rgba(200,140,30,.45),inset 0 1px 0 rgba(255,255,255,.6)}
  .tab.on .ti{transform:scale(1.12)}
  .tab:active .ti{transform:scale(.9)}
  /* tegilganda oltin uchqunlar */
  .spark{position:fixed;width:6px;height:6px;border-radius:50%;pointer-events:none;z-index:200;
    background:radial-gradient(circle,#fff8d6,#ffd24a 50%,rgba(255,180,30,0) 70%);animation:spark .6s ease-out forwards}
  @keyframes spark{to{transform:translate(var(--dx),var(--dy)) scale(.2);opacity:0}}
</style>
</head>
<body>
<div id="app"><div class="center"><div class="big">⏳</div>Yuklanmoqda…</div></div>
<script>
const tg = window.Telegram ? window.Telegram.WebApp : null;
const $ = (h)=>{const d=document.createElement('div');d.innerHTML=h;return d.firstElementChild;};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
let TAB='profil';
// 🎰 Kazino logotipi: oltin fishka + toj (SVG)
const CASINO_ICON='<svg class="cz-ico" viewBox="0 0 48 48" width="27" height="27" aria-hidden="true"><defs>'+
  '<linearGradient id="czg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff3c0"/><stop offset=".45" stop-color="#f2c048"/><stop offset="1" stop-color="#9a6510"/></linearGradient>'+
  '<radialGradient id="czr" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="#e2384c"/><stop offset="1" stop-color="#7a0d1d"/></radialGradient></defs>'+
  '<circle cx="24" cy="24" r="22" fill="url(#czg)"/>'+
  [0,45,90,135,180,225,270,315].map(a=>'<rect x="21" y="2.5" width="6" height="7" rx="1.5" fill="#7a0d1d" transform="rotate('+a+' 24 24)"/>').join('')+
  '<circle cx="24" cy="24" r="14.5" fill="url(#czr)" stroke="#ffe39a" stroke-width="1.6"/>'+
  '<path d="M15.5 29.5 L17 19.5 L21 24 L24 17 L27 24 L31 19.5 L32.5 29.5 Z" fill="url(#czg)" stroke="#5a3a05" stroke-width=".8" stroke-linejoin="round"/>'+
  '<rect x="15.5" y="29.5" width="17" height="2.6" rx="1" fill="url(#czg)"/></svg>';

function boot(){
  if(tg){ tg.ready(); tg.expand(); try{tg.setHeaderColor('#07070d');tg.setBackgroundColor('#07070d');}catch(e){} }
  fetch('/app/api/data',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({initData: tg?tg.initData:''})})
    .then(r=>r.json()).then(render).catch(()=>fail('Aloqa xatosi'));
}
function fail(m){document.getElementById('app').innerHTML=
  '<div class="center"><div class="big">📡</div>'+esc(m)+'</div>';}

function render(res){
  if(!res||!res.ok){return fail('Kirish tasdiqlanmadi. Botni Telegram orqali oching.');}
  if(!res.enabled){return fail('🌐 Web app hozircha o‘chirilgan.');}
  const d=res.data;
  const app=document.getElementById('app');
  const initial=(d.name||'?').trim().charAt(0).toUpperCase()||'🎮';
  app.innerHTML='';
  app.appendChild($(
    '<div class="hdr"><div class="ava">'+esc(initial)+'<img id="avimg" alt="" src="/app/avatar/'+esc(d.id)+'"></div>'+
    '<div><div class="hname">'+esc(d.name)+'</div>'+
    '<div class="hsub">'+(d.username?'@'+esc(d.username):'ID '+esc(d.id))+
    (d.is_owner?' · 👑 Owner':'')+'</div></div>'+
    '<div class="bal"><div class="n" id="bal">'+esc(d.money_fmt)+'$</div><div class="l">Hamyon</div></div></div>'));
  window.BAL=d.money;
  (function(){ const im=document.getElementById('avimg'); if(!im) return;
    const tu=tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user&&tg.initDataUnsafe.user.photo_url;
    im.onerror=()=>{ if(tu && im.src!==tu){ im.src=tu; } else { im.remove(); } }; })();

  // PROFIL
  const p=$('<div class="sec" id="s-profil"></div>');
  p.appendChild($('<div class="grid">'+
    card('💰 Hamyon', d.money_fmt+'$', 'neon','full')+
    card('🏆 Reyting', d.rank?('#'+d.rank):'—','mag')+
    card('⭐ Daraja', esc(d.level),'lime')+
    card('🎮 O‘yinlar', d.games,'')+
    card('✅ G‘alaba', d.wins,'lime')+
    card('📈 Ball', d.points,'neon')+
    card('👶 Farzandlar', d.kids,'mag')+
    '</div>'));
  const extra=[];
  if(d.birja>0) extra.push('<span class="chip">📈 Birja: '+esc(d.birja)+'$</span>');
  if(d.loan) extra.push('<span class="chip" style="color:#ff6b6b;border-color:rgba(255,107,107,.4)">🏦 Faol kredit</span>');
  if(extra.length) p.appendChild($('<div style="margin-top:12px">'+extra.join(' ')+'</div>'));
  if(d.avatar3d){
    const av=$('<div class="card full avcard" data-tap="1"><div class="avi">🧍</div><div><div class="lbl">3D avatarim'+(d.avatar_test?' <span class="avtest">TEST</span>':'')+'</div>'+
      '<div class="hsub">Realistik 3D model · kiyim, soch, teri rangi va fonni tanlang</div></div></div>');
    av.onclick=()=>openAvatarStudio(d); p.appendChild(av);
  }
  app.appendChild(p);

  // REYTING
  const r=$('<div class="sec" id="s-reyting"></div>');
  r.appendChild($('<h2>💎 Eng boylar TOP</h2>'));
  const list=$('<div class="card full"></div>');
  (d.top||[]).forEach((t,i)=>{
    const g=i===0?'g1':i===1?'g2':i===2?'g3':'';
    list.appendChild($('<div class="row '+(t.me?'me':'')+'">'+
      '<div style="display:flex;align-items:center;gap:10px"><span class="rk '+g+'">'+(i+1)+'</span>'+
      '<span>'+esc(t.name)+(t.me?' <span style="color:var(--cyan)">(siz)</span>':'')+'</span></div>'+
      '<b class="val neon" style="font-size:15px">'+esc(t.money_fmt)+'$</b></div>'));
  });
  if(!(d.top||[]).length) list.appendChild($('<div class="center">Hali ma’lumot yo‘q</div>'));
  r.appendChild(list);
  app.appendChild(r);

  // BANK
  const bk=$('<div class="sec" id="s-bank"></div>');
  bk.appendChild($('<h2>🏦 Bank</h2>'));
  if(d.bank && d.bank.loan){
    const l=d.bank.loan;
    bk.appendChild($('<div class="card full"><div class="lbl">💳 Faol kredit · '+esc(l.bank)+'</div>'+
      '<div class="val mag">'+esc(l.due)+'$</div>'+
      '<div class="hsub">Olingan: '+esc(l.amount)+'$ · '+esc(l.days)+' kun · muddat: '+esc(l.due_at)+'</div></div>'));
  }
  if(d.bank && d.bank.deposit){
    const s=d.bank.deposit;
    bk.appendChild($('<div class="card full" style="margin-top:12px"><div class="lbl">💰 Omonat · '+esc(s.bank)+'</div>'+
      '<div class="val lime">'+esc(s.payout)+'$</div>'+
      '<div class="hsub">Qo‘yilgan: '+esc(s.amount)+'$ · '+esc(s.days)+' kun · yechish: '+esc(s.matures_at)+'</div></div>'));
  }
  const bo=d.bank_opts||{};
  const bankSel=(bo.banks||[]).map(b=>'<option value="'+b.id+'" data-apply="'+(b.apply?1:0)+'">'+esc(b.name)+' · '+b.loan_rate+'%'+(b.apply?' · 📝 ariza':'')+'</option>').join('');
  if(bo.pending_app) bk.appendChild($('<div class="card full" style="margin-top:12px"><div class="center">📝 Kredit arizangiz bank egasida ko‘rib chiqilmoqda.</div></div>'));
  // Kredit to'lash
  if(d.bank && d.bank.loan){
    const rp=$('<button class="btn cash full" id="brepay">💳 Kreditni to‘lash ('+esc(d.bank.loan.due)+'$)</button>');
    rp.onclick=()=>{ rp.disabled=true; api('/app/api/bank/repay',{}).then(r=>{
      if(r.result==='repaid'){ setBal(r.balance); toast('✅ Kredit to‘landi'); refresh(); }
      else { toast(errText(r.error)); rp.disabled=false; } }); };
    bk.appendChild(rp);
  } else if(bo.can_loan && (bo.banks||[]).length){
    const amtO=(bo.loan_amounts||[]).map(a=>'<option value="'+a+'">'+fmtMoney(a)+'$</option>').join('');
    const dayO=(bo.loan_days||[]).map(x=>'<option value="'+x+'">'+x+' kun</option>').join('');
    const f=$('<div class="card full" style="margin-top:12px"><div class="lbl">💸 Kredit olish</div>'+
      '<div class="frow"><select class="sel" id="lbank">'+bankSel+'</select></div>'+
      '<div class="frow"><select class="sel" id="lamt">'+amtO+'</select><select class="sel" id="ldays">'+dayO+'</select></div>'+
      '<div class="frow" id="lpw" style="display:none"><input class="bet" id="lpurpose" placeholder="🎯 Kredit maqsadi (bank egasi ko‘radi)" style="text-align:left"></div>'+
      '<button class="btn go full" id="loanbtn">💸 Kredit olish</button></div>');
    const lb=app_q(f,'#lbank'), syncApply=()=>{ const ap=lb.selectedOptions[0]&&lb.selectedOptions[0].dataset.apply==='1';
      app_q(f,'#lpw').style.display=ap?'':'none'; app_q(f,'#loanbtn').textContent=ap?'📝 Ariza yuborish':'💸 Kredit olish'; };
    lb.onchange=syncApply; syncApply();
    app_q(f,'#loanbtn').onclick=()=>{ const b=app_q(f,'#loanbtn'); b.disabled=true;
      api('/app/api/bank/loan',{bank:lb.value,amount:app_q(f,'#lamt').value,days:app_q(f,'#ldays').value,purpose:app_q(f,'#lpurpose').value}).then(r=>{
        if(r.result==='loan'){ setBal(r.balance); toast('✅ Kredit olindi: +'+fmtMoney(r.amount)+'$'); refresh(); }
        else if(r.result==='applied'){ toast('📝 Ariza '+r.bank+' egasiga yuborildi'); refresh(); }
        else { toast(errText(r.error)); b.disabled=false; } }); };
    bk.appendChild(f);
  }
  // Omonat
  if(bo.can_deposit && (bo.banks||[]).length && !(d.bank&&d.bank.deposit)){
    const amtO=(bo.dep_amounts||[]).map(a=>'<option value="'+a+'">'+fmtMoney(a)+'$</option>').join('');
    const dayO=(bo.dep_days||[]).map(x=>'<option value="'+x+'">'+x+' kun</option>').join('');
    const bankSelD=(bo.banks||[]).map(b=>'<option value="'+b.id+'">'+esc(b.name)+' · '+b.deposit_rate+'%</option>').join('');
    const f=$('<div class="card full" style="margin-top:12px"><div class="lbl">💰 Omonat qo‘yish</div>'+
      '<div class="frow"><select class="sel" id="dbank">'+bankSelD+'</select></div>'+
      '<div class="frow"><select class="sel" id="damt">'+amtO+'</select><select class="sel" id="ddays">'+dayO+'</select></div>'+
      '<button class="btn go full" id="depbtn">💰 Omonat qo‘yish</button></div>');
    app_q(f,'#depbtn').onclick=()=>{ const b=app_q(f,'#depbtn'); b.disabled=true;
      api('/app/api/bank/deposit',{bank:app_q(f,'#dbank').value,amount:app_q(f,'#damt').value,days:app_q(f,'#ddays').value}).then(r=>{
        if(r.result==='deposit'){ setBal(r.balance); toast('✅ Omonat qo‘yildi'); refresh(); }
        else { toast(errText(r.error)); b.disabled=false; } }); };
    bk.appendChild(f);
  }
  if((!d.bank||(!d.bank.loan&&!d.bank.deposit)) && !((bo.banks||[]).length))
    bk.appendChild($('<div class="card full"><div class="center">Bank mavjud emas.</div></div>'));
  app.appendChild(bk);

  // BIRJA — savdo
  const bx=$('<div class="sec" id="s-birja"></div>');
  bx.appendChild($('<h2>📈 Birja — savdo</h2>'));
  const bl=$('<div class="card full"></div>');
  (d.birja_market||[]).forEach(it=>{
    const up=(it.change||0)>=0;
    const row=$('<div class="mkt"><div class="ic">'+esc(it.icon)+'</div>'+
      '<div><div class="nm">'+esc(it.asset)+'</div>'+
      '<div class="pr">'+(it.price?fmtMoney(it.price)+'$ <span class="'+(up?'up':'down')+'">'+(up?'▲':'▼')+Math.abs(it.change)+'%</span>':'—')+
      (it.qty>0?' · 💼 '+esc(it.value_fmt)+'$':'')+'</div></div>'+
      '<div class="act"></div></div>');
    const act=app_q(row,'.act');
    const buy=$('<button class="mini buy">Olish</button>');
    buy.onclick=()=>{ sheet('🟢 '+esc(it.name)+' — olish',(d.birja_buy_fixed||[]).map(a=>({label:fmtMoney(a)+'$',value:a})),
      (usd)=>api('/app/api/birja/buy',{asset:it.asset,usd:usd}).then(r=>{
        if(r.result==='bought'){ setBal(r.balance); toast('🟢 '+r.asset+' olindi'); refresh(); } else toast(errText(r.error,r.min)); })); };
    act.appendChild(buy);
    if(it.qty>0){
      const sell=$('<button class="mini sell">Sotish</button>');
      sell.onclick=()=>{ if(it.lock>0){ toast('⏳ '+Math.ceil(it.lock/60)+' daqiqadan keyin sotasiz'); return; }
        sheet('🔴 '+esc(it.name)+' — sotish',(d.birja_pcts||[]).map(p=>({label:p+'%',value:p})),
          (pct)=>api('/app/api/birja/sell',{asset:it.asset,pct:pct}).then(r=>{
            if(r.result==='sold'){ setBal(r.balance); toast('🔴 +'+fmtMoney(r.usd)+'$'); refresh(); } else toast(errText(r.error,r.min)); })); };
      act.appendChild(sell);
    }
    bl.appendChild(row);
  });
  if(!(d.birja_market||[]).length) bl.appendChild($('<div class="center">Narxlar yuklanmoqda…</div>'));
  bx.appendChild(bl);
  app.appendChild(bx);

  // FARZAND — har yosh bosqichiga alohida dizayn + ta'lim yo'li
  const fz=$('<div class="sec" id="s-farzand"></div>');
  // 💍 RANDOM JUFT: jufti yo'qlar uchun — yigitniki tasodifiy qizga, qizniki tasodifiy yigitga
  const rpBox=$('<div class="card full rpair"></div>'); fz.appendChild(rpBox);
  const RPERR={no_gender:'⚧ Avval botda jinsingizni tanlang (/start)',has_pair:'💞 Sizda allaqachon juft bor',
    waiting:'⏳ Oldingi taklifga javob kutilmoqda',none:'😔 Hozircha mos nomzod topilmadi, keyinroq urinib ko‘ring',
    disabled:'🌐 Web app o‘chirilgan',bot:'⚠️ Bot hozir band, qayta urining',no_request:'Taklif topilmadi'};
  let rpT=0;
  function drawRP(st){
    clearInterval(rpT); st=st||{};
    let h='<div class="rph"><span class="rpi">💍</span><div><div class="lbl">Random juft</div>'+
      '<div class="hsub">'+(st.gender==='male'?'👦 Siz — yigit · taklif tasodifiy qizga boradi':st.gender==='female'?'👧 Siz — qiz · taklif tasodifiy yigitga boradi':'Jins tanlanmagan')+'</div></div></div>';
    if(st.has_pair) h+='<div class="rpok">💞 Juftingiz: <b>'+esc(st.partner)+'</b></div>';
    else if(!st.gender) h+='<div class="hsub" style="margin-top:8px">Avval botda /start bosib jinsingizni tanlang.</div>';
    else if(st.pending) h+='<div class="rpw">⏳ <b>'+esc(st.pending.name)+'</b> javobini kutyapsiz<br><span class="hsub">Yuborildi: '+esc(st.pending.at)+'</span></div>'+
      '<button class="btn full" id="rpCancel" style="margin-top:10px">✖️ Taklifni bekor qilish</button>';
    else h+='<div class="hsub" style="margin-top:8px">Taklif bilan birga pulingiz, reytingingiz, darajangiz, kasbingiz va oilaviy tarixingiz ko‘rsatiladi. Rozi bo‘lsa — bot egalari tasdig‘idan keyin juft bo‘lasiz.</div>'+
      '<button class="btn go full" id="rpFind" style="margin-top:10px">💍 Random juft topish</button>';
    if(!st.has_pair && st.gender) h+='<div class="rpsep">yoki ID orqali</div><div class="rpid"><input class="bet" id="rpQ" placeholder="ID yoki @username" autocomplete="off" style="text-align:left">'+
      '<button class="btn" id="rpSend">💌 Taklif</button></div>';
    rpBox.innerHTML=h;
    const f=app_q(rpBox,'#rpFind'), cn=app_q(rpBox,'#rpCancel'), rs=app_q(rpBox,'#rpSend');
    if(rs) rs.onclick=()=>{ const v=app_q(rpBox,'#rpQ').value.trim(); if(!v){ toast('✍️ ID yoki @username yozing'); return; }
      pairPropose(v,rs).then(r=>{ if(r&&r.result==='sent') app_q(rpBox,'#rpQ').value=''; }); };
    if(f){ let cd=st.cooldown||0;
      const tick=()=>{ if(cd>0){ f.disabled=true; f.textContent='⏳ '+cd+' s dan keyin'; cd--; } else { f.disabled=false; f.textContent='💍 Random juft topish'; clearInterval(rpT); } };
      tick(); if(cd>0) rpT=setInterval(tick,1000);
      f.onclick=()=>{ f.disabled=true; f.textContent='🔎 Qidirilmoqda…';
        api('/app/api/randpair/find',{}).then(r=>{
          if(r.result==='sent'){ const t=r.target||{};
            toast('💌 Taklif '+(t.gender==='female'?'👧 ':'👦 ')+t.name+' ga yuborildi'); haptic('success'); d.randpair=r.status; drawRP(r.status); }
          else { toast(r.error==='cooldown'?('⏳ '+r.wait+' s kuting'):(RPERR[r.error]||'⚠️ Xatolik')); drawRP(r.status||st); }
        }).catch(()=>{ toast('⚠️ Aloqa xatosi'); drawRP(st); }); }; }
    if(cn) cn.onclick=()=>api('/app/api/randpair/cancel',{}).then(r=>{ if(r.result){ toast('✖️ Taklif bekor qilindi'); d.randpair=r.status; drawRP(r.status); } else toast(RPERR[r.error]||'⚠️ Xatolik'); });
  }
  drawRP(d.randpair);
  fz.appendChild($('<h2>👶 Farzandlar</h2>'));
  const KS={ // bosqich: [o'g'il emoji, qiz emoji, aksessuar, nomi, yosh oralig'i]
    baby:['👶','👶','🍼','Chaqaloq','0–2'], kinder:['👦','👧','🧸','Bog‘cha','3–6'], school:['🙋‍♂️','🙋‍♀️','🎒','Maktab','7–15'],
    college:['👨‍🔬','👩‍🔬','🔬','Kollej','16–18'], uni:['👨‍🎓','👩‍🎓','📜','Universitet','19–22'], work:['👨‍💼','👩‍💼','💼','Ishchi','23+'] };
  const KDECO={baby:['⭐','☁️','🌙','✨'],kinder:['🖍️','🎈','🧩','🌈'],school:['📐','✏️','📚','🔔'],college:['🧪','⚙️','📊','💡'],uni:['🎓','🏛️','📖','🌟'],work:['💰','📈','🏙️','💎']};
  const BLOCKMSG={hungry:'🍔 Och — o‘smayapti',sad:'😢 Xafa — o‘smayapti',fee:'🎓 Ta‘lim to‘lovi kutilmoqda',decide:'🧭 Yo‘l tanlash kerak (botda)'};
  (d.kids_list||[]).forEach(k=>{
    const st=KS[k.stage_key]?k.stage_key:'baby', S=KS[st], em=k.gender==='girl'?S[1]:S[0];
    const hc=k.hunger<30?'#ff6b6b':(k.hunger<60?'var(--gold)':'var(--lime)');
    const pc=k.happy<30?'#ff6b6b':(k.happy<60?'var(--gold)':'var(--lime)');
    const deco=KDECO[st].map((e,i)=>'<i style="--i:'+i+'">'+e+'</i>').join('');
    const instLine=(st in d.edu_default_fee)?(k.inst?'<div class="kinst">🏫 '+esc(k.inst.name)+' · <b>'+fmtMoney(k.inst.fee)+'$</b>/yil</div>'
      :'<div class="kinst dim">🏫 Muassasa tanlanmagan · standart '+fmtMoney(d.edu_default_fee[st])+'$/yil</div>'):'';
    const card=$('<div class="kidc st-'+st+'"><div class="kdeco">'+deco+'</div><div class="k3d">🧸 3D</div>'+
      '<div class="ktop"><div class="kava"><span class="kem">'+em+'</span><span class="kacc">'+S[2]+'</span></div>'+
      '<div class="kmeta"><div class="kname">'+esc(k.name)+'</div>'+
      '<div class="kchips"><span class="kchip">'+esc(k.age)+' yosh</span><span class="kchip st">'+S[3]+' · '+S[4]+'</span></div>'+
      ((k.parents||[]).length?'<div class="kpar">👨‍👩‍👧 '+esc(k.parents[0])+' ❤️ '+esc(k.parents[1])+'</div>':'')+'</div></div>'+
      (k.working?'<div class="kwork">💼 Ishlaydi · kuniga <b>'+fmtMoney(k.salary)+'$</b> (ota-onaga teng)</div>':
      '<div class="kgrow"><div class="t"><span>🌱 Keyingi yoshgacha: 🍽 '+k.meals+'/'+k.meals_need+' ovqat</span><b>'+k.growth+'%</b></div><div class="track"><div class="fill" style="width:'+k.growth+'%"></div></div>'+
        '<div class="kmeal'+(k.next_meal?'':' ready')+'">'+(k.next_meal?'⏳ Keyingi ovqat: '+hm(k.next_meal):'🍽 Ovqatlanish vaqti!')+'</div></div>'+
      (k.block?'<div class="kblock">'+BLOCKMSG[k.block]+'</div>':'')+
      '<div class="bars"><div class="bar"><div class="t">🍔 To‘qlik '+k.hunger+'%</div><div class="track"><div class="fill" style="width:'+k.hunger+'%;background:'+hc+'"></div></div></div>'+
      '<div class="bar"><div class="t">😊 Kayfiyat '+k.happy+'%</div><div class="track"><div class="fill" style="width:'+k.happy+'%;background:'+pc+'"></div></div></div></div>'+
      instLine)+
      '<div class="kbtns"></div></div>');
    const btns=app_q(card,'.kbtns');
    card.addEventListener('click',e=>{ if(e.target.closest('.kbtn')) return; openKidStudio(k); });
    if(!k.working){
      if((k.food||[]).length){ const fb=$('<div class="kbtn'+(k.next_meal?' wait':'')+'">'+(k.next_meal?'⏳ '+(k.next_meal>=3600?Math.ceil(k.next_meal/3600)+' soat':Math.ceil(k.next_meal/60)+' daq'):'🍔 Ovqat')+'</div>');
        fb.onclick=()=>k.next_meal?toast('⏳ '+esc(k.name)+' yaqinda ovqatlandi. Keyingi ovqat: '+hm(k.next_meal)+' (12 soatda 1 marta)'):sheet('🍔 '+esc(k.name)+' — ovqat',k.food.map(it=>({label:esc(it.name)+' · '+it.price+'$',value:it.key})),
          (item)=>api('/app/api/kid',{kid:k.id,act:'feed',item:item}).then(r=>{ if(r.result==='ok'){ setBal(r.balance); toast('✅ To‘qlik '+r.value+'% · 🍽 '+r.meals+'/'+r.need); refresh(); } else toast(kidErr(r.error,r.wait)); }));
        btns.appendChild(fb); }
      if((k.toy||[]).length){ const tb=$('<div class="kbtn">🧸 O‘yinchoq</div>');
        tb.onclick=()=>sheet('🧸 '+esc(k.name)+' — o‘yinchoq',k.toy.map(it=>({label:esc(it.name)+' · '+it.price+'$',value:it.key})),
          (item)=>api('/app/api/kid',{kid:k.id,act:'toy',item:item}).then(r=>{ if(r.result==='ok'){ setBal(r.balance); toast('✅ Kayfiyat '+r.value+'%'); refresh(); } else toast(kidErr(r.error)); }));
        btns.appendChild(tb); }
      if((k.gear||[]).length){ const gb=$('<div class="kbtn">🎒 Buyumlar</div>'); gb.onclick=()=>gearSheet(k); btns.appendChild(gb); }
      const insts=(d.edu||[]).filter(x=>x.kind===st);
      if(insts.length){ const ib=$('<div class="kbtn">🏫 Muassasa</div>');
        ib.onclick=()=>sheet('🏫 '+esc(k.name)+' uchun '+S[3].toLowerCase(),insts.map(x=>({label:(k.inst&&k.inst.id===x.id?'✅ ':'')+esc(x.name)+' · '+fmtMoney(x.fee)+'$/yil',value:x.id})),
          (iid)=>api('/app/api/edu/enroll',{kid:k.id,inst:iid}).then(r=>{ if(r.result==='enrolled'){ toast('✅ '+esc(r.inst)+' ga yozildi'); refresh(); } else toast(kidErr(r.error)); }));
        btns.appendChild(ib); }
      if(k.fee>0){ const feb=$('<div class="kbtn kfee">🎓 Ta‘lim '+fmtMoney(k.fee)+'$</div>');
        feb.onclick=()=>api('/app/api/kid',{kid:k.id,act:'fee'}).then(r=>{ if(r.result==='fee'){ setBal(r.balance); toast('✅ Ta‘lim to‘lovi qilindi'); refresh(); } else toast(kidErr(r.error)); });
        btns.appendChild(feb); }
    }
    fz.appendChild(card);
  });
  if(!(d.kids_list||[]).length) fz.appendChild($('<div class="card full"><div class="center">Farzandlar yo‘q.<br><span class="hsub">Botda /oila</span></div></div>'));
  // 🏫 Ta'lim yo'li: kategoriyalar farzand yoshi yetganda ochiladi
  const EDU_ORDER=[['kinder','🧸','Bog‘cha'],['school','🎒','Maktab'],['college','🔬','Kollej'],['uni','🎓','Institut']];
  const maxAge=Math.max(-1,...(d.kids_list||[]).map(k=>k.age));
  const path=$('<div class="edupath"><h2>🏫 Ta‘lim yo‘li</h2><div class="egrid"></div></div>');
  EDU_ORDER.forEach(([kind,ic,nm])=>{
    const need=d.edu_min_age[kind], open=maxAge>=need, list=(d.edu||[]).filter(x=>x.kind===kind);
    const t=$('<div class="etile'+(open?' open':'')+'"><div class="eic">'+(open?ic:'🔒')+'</div><div class="enm">'+nm+'</div>'+
      '<div class="esub">'+(open?(list.length?list.length+' ta muassasa':'Standart: '+fmtMoney(d.edu_default_fee[kind])+'$'):need+' yoshdan')+'</div></div>');
    if(open) t.onclick=()=>{ if(!list.length){ toast('Hozircha '+nm.toLowerCase()+' muassasasi ochilmagan — standart narx: '+fmtMoney(d.edu_default_fee[kind])+'$/yil'); return; }
      sheet(ic+' '+nm+' muassasalari',list.map(x=>({label:esc(x.name)+'<br><b>'+fmtMoney(x.fee)+'$</b>/yil',value:x.id})),()=>toast('Yozdirish: farzand kartasidagi 🏫 Muassasa tugmasi')); };
    app_q(path,'.egrid').appendChild(t);
  });
  if(maxAge>=0) fz.appendChild(path);
  app.appendChild(fz);

  // SHOP
  const sh=$('<div class="sec" id="s-shop"></div>');
  sh.appendChild($('<h2>🛍 Do‘kon — sovg‘a yuborish</h2>'));
  const toWrap=$('<div class="card full"><div class="lbl">Kimga</div>'+
    '<div class="seg" id="shto">'+(d.has_partner?'<div class="s on" data-t="partner">💞 Juftimga</div>':'')+
    '<div class="s'+(d.has_partner?'':' on')+'" data-t="other">👤 Boshqaga</div></div>'+
    '<div class="frow" id="shidwrap" style="'+(d.has_partner?'display:none':'')+'"><input class="bet" id="shid" placeholder="@username yoki ID"></div></div>');
  sh.appendChild(toWrap);
  let shMode=d.has_partner?'partner':'other';
  toWrap.querySelectorAll('#shto .s').forEach(s=>s.onclick=()=>{
    toWrap.querySelectorAll('#shto .s').forEach(x=>x.classList.remove('on')); s.classList.add('on'); shMode=s.dataset.t;
    app_q(toWrap,'#shidwrap').style.display=shMode==='other'?'':'none';
  });
  const gifts=$('<div class="grid" style="margin-top:12px"></div>');
  (d.shop||[]).forEach(g=>{
    const el=$('<div class="card" data-tap="1" style="text-align:center;cursor:pointer"><div style="font-size:30px">'+esc(g.name.split(" ")[0])+'</div>'+
      '<div style="margin-top:6px">'+esc(g.name.replace(/^\S+\s/,''))+'</div><div class="val mag" style="font-size:16px">'+g.price+'$</div></div>');
    el.onclick=()=>{
      const to = shMode==='partner' ? 'partner' : (app_q(toWrap,'#shid').value||'').trim();
      if(shMode==='other' && !to){ toast('Qabul qiluvchini kiriting'); return; }
      el.style.opacity=.5;
      api('/app/api/shop/buy',{gift:g.key,to:to}).then(r=>{
        el.style.opacity=1;
        if(r.result==='sent'){ setBal(r.balance); toast('✅ '+esc(g.name)+' → '+esc(r.to)); }
        else toast(errText(r.error)); });
    };
    gifts.appendChild(el);
  });
  sh.appendChild(gifts);
  // 👶 Farzand buyumlari — har davr uchun
  const gk=(d.kids_list||[]).filter(k=>!k.working && (k.gear||[]).length);
  if(gk.length){
    sh.appendChild($('<h2 style="margin-top:20px">👶 Farzand buyumlari</h2>'));
    gk.forEach(k=>{
      const box=$('<div class="kgshop"><div class="kgh"><b>'+esc(k.name)+'</b><span>'+esc(k.age)+' yosh · '+esc(k.stage)+'</span></div><div class="grid"></div></div>');
      k.gear.forEach(it=>{
        const ic=it.name.split(' ')[0], nm=it.name.replace(/^\S+\s/,'');
        const el=$('<div class="card'+(it.owned?' kown':'')+'" data-tap="1" style="text-align:center;cursor:pointer"><div style="font-size:30px">'+esc(ic)+'</div>'+
          '<div style="margin-top:6px;font-size:13px">'+esc(nm)+'</div>'+(it.owned?'<div class="hsub" style="margin-top:4px">✅ Bor</div>':'<div class="val mag" style="font-size:16px">'+fmtMoney(it.price)+'$</div><div class="hsub">😊 +'+it.eff+'</div>')+'</div>');
        el.onclick=()=>{ if(it.owned){ toast('✅ '+esc(k.name)+'da bu buyum bor'); return; }
          el.style.opacity=.5; api('/app/api/kid',{kid:k.id,act:'gear',item:it.key}).then(r=>{ el.style.opacity=1;
            if(r.result==='ok'){ setBal(r.balance); toast('✅ '+esc(nm)+' olindi'); refresh(); } else toast(kidErr(r.error)); }); };
        app_q(box,'.grid').appendChild(el);
      });
      sh.appendChild(box);
    });
  }
  app.appendChild(sh);

  // KAZINO — o'yinlar lobbisi
  const cz=$('<div class="sec" id="s-casino"></div>');
  cz.innerHTML=
    '<h2>🎰 Kazino</h2>'+
    '<div class="glob">'+
      '<div class="gcard g-crash" data-go="crash"><div class="gimg" style="background-image:url(/app/a/crash.jpg)"></div>'+
        '<div class="gtag">EMPIRE GAMES</div><div class="gtitle">ROYAL<br>CRASH</div>'+
        '<div class="gfoot"><span class="glive"><i></i>Jonli raund</span><span class="gplay">▶</span></div></div>'+
      '<div class="gcard g-hovuz" data-go="frog"><div class="gimg" style="background-image:url(/app/a/hovuz.jpg)"></div>'+
        '<div class="gtag">EMPIRE GAMES</div><div class="gtitle">HOVUZ</div>'+
        '<div class="gfoot"><span class="glive"><i></i>x4.08 gacha</span><span class="gplay">▶</span></div></div>'+
      (d.kami?'<div class="gcard g-kami" data-go="kami"><div class="gimg" style="background-image:url(/app/a/kamikaze.jpg?v=2)"></div>'+
        '<div class="gtag">EMPIRE GAMES</div><div class="gtitle">KAMI<br>KAZE</div>'+(d.kami_test?'<div class="gtest">🧪 TEST</div>':'')+
        '<div class="gfoot"><span class="glive"><i></i>x13 gacha</span><span class="gplay">▶</span></div></div>':'')+
    '</div>'+
    '<div class="gnote">🎮 Barcha o‘yinlar virtual pul bilan · hamyoningizdan</div>';
  cz.querySelectorAll('.gcard').forEach(c=>c.onclick=()=>setTab(c.dataset.go));
  app.appendChild(cz);

  // CRASH (Aviator — umumiy raund)
  const cr=$('<div class="sec" id="s-crash"></div>');
  cr.innerHTML=
    '<div class="gback" data-back="1">‹ Kazino</div>'+
    '<div class="hist" id="chist"></div>'+
    '<div class="crashbox" id="cbox"><canvas id="ccanvas"></canvas>'+
      '<div class="funmode">✦ RAUND #<span id="cround">—</span> · <span id="conline">0</span> o‘yinchi ✦</div>'+
      '<div class="mx" id="mx">1.00x</div>'+
      '<div class="cwait" id="cwait"><div class="cw1">Keyingi raund</div><div class="cw2" id="ccnt">0.0</div>'+
        '<div class="cbar"><i id="cbarf"></i></div><div class="cw3">Tikishni hozir qiling ⏳</div></div>'+
      '<div class="cstat" id="cnote">Hamma uchun bitta raund · qachon uchib ketishi sir 🎯</div></div>'+
    '<div class="betrow">'+
      '<div class="stepper"><button id="cminus">−</button><input class="bet" id="cbet" type="number" inputmode="numeric" value="50" style="border:none;width:74px;padding:13px 2px"><button id="cplus">+</button></div>'+
      '<button class="bigbet" id="cbtn" style="margin-top:0;flex:1">BET · 50$</button></div>'+
    '<div class="quick"><div class="q" data-v="half">½</div><div class="q" data-v="dbl">×2</div><div class="q" data-v="100">100</div><div class="q" data-v="500">500</div><div class="q" data-v="1000">1K</div><div class="q" data-v="max">MAX</div></div>'+
    '<div class="plist"><div class="phd"><span>👥 O‘yinchilar <b id="pcount">0</b></span><span>💰 Bank <b id="ppot">0</b>$</span></div>'+
      '<div class="pcol"><span>O‘yinchi</span><span>Tikish</span><span>Kf</span><span>Yutuq</span></div>'+
      '<div id="plist"></div></div>';
  app.appendChild(cr);
  window.CHIST=d.crash_history||[];

  // HOVUZ (avvalgi Baqa)
  const fr=$('<div class="sec" id="s-frog"></div>');
  fr.innerHTML=
    '<div class="gback" data-back="1">‹ Kazino</div>'+
    '<h2>🌊 Hovuz</h2>'+
    '<div class="seg" id="fmode">'+
      '<div class="s on" data-m="easy">🟢 Oson</div><div class="s" data-m="medium">🟡 O‘rta</div><div class="s" data-m="hard">🔴 Qiyin</div></div>'+
    '<div class="pond" id="pond"></div>'+
    '<div class="note" id="fnote">Rejim tanlab, tikib boshlang 🪷</div>'+
    '<div class="betrow"><input class="bet" id="fbet" type="number" inputmode="numeric" value="50"></div>'+
    '<button class="btn go full" id="fbtn">🐸 Tikish (50$)</button>'+
    '<button class="btn cash full" id="fcash" style="display:none">💰 Yechib olish</button>';
  app.appendChild(fr);

  // 💬 CHAT: ID / @username orqali topib suhbatlashish
  const ch=$('<div class="sec" id="s-chat"></div>');
  ch.innerHTML='<h2>💬 Chat</h2>'+
    '<div class="card full chs"><div class="lbl">🔎 Foydalanuvchini topish</div>'+
    '<div class="chq"><input class="bet" id="chQ" placeholder="ID yoki @username" autocomplete="off" style="text-align:left">'+
    '<button class="btn go" id="chGo">Topish</button></div><div id="chRes"></div></div>'+
    '<h2 style="margin-top:18px">🗨 Suhbatlar</h2><div id="chList" class="chlist"><div class="hsub">Yuklanmoqda…</div></div>';
  app.appendChild(ch);
  initChat(d);

  // KAMIKAZE (test: faqat ownerlar, keyin hamma uchun)
  if(d.kami){
    const km=$('<div class="sec" id="s-kami"></div>');
    km.innerHTML=
      '<div class="gback" data-back="1">‹ Kazino</div>'+
      '<h2>🛩 Kamikaze</h2>'+
      '<div class="kbox" id="kbox"><canvas id="kcanvas"></canvas><div class="kmsg" id="kmsg"></div></div>'+
      '<div class="knote" id="knote">Kataklardan birini tanlab, dushman o‘qidan qoching. Kemagacha yeting — x'+'<b id="kmax">13</b>!</div>'+
      '<div class="betrow"><div class="stepper"><button id="kminus">−</button><input class="bet" id="kbet" type="number" inputmode="numeric" value="50" style="border:none;width:74px;padding:13px 2px"><button id="kplus">+</button></div>'+
      '<button class="btn go" id="kbtn" style="flex:1">🛩 O‘YNASH · 50$</button></div>'+
      '<div class="quick kq"><div class="q" data-v="half">½</div><div class="q" data-v="dbl">×2</div><div class="q" data-v="100">100</div><div class="q" data-v="500">500</div><div class="q" data-v="1000">1K</div></div>';
    app.appendChild(km);
  }

  // OWNER
  if(d.is_owner && d.owner){
    const o=$('<div class="sec" id="s-owner"></div>');
    o.appendChild($('<h2>👑 Owner panel</h2>'));
    o.appendChild($('<div class="grid">'+
      card('👤 Foydalanuvchilar', d.owner.users,'neon')+
      card('🏘 Guruhlar', d.owner.groups,'mag')+
      card('💵 Jami pul', d.owner.total_money+'$','lime','full')+
      card('🎰 Faol o‘yinlar', d.owner.active_games,'')+
      card('🎲 O‘yinlarda', d.owner.in_games+'$','neon')+
      '</div>'));
    // 🏫 Ta'lim muassasalari (ownerlar: ochish, nomi/narxini o'zgartirish, yopish)
    const KN={kinder:'🧸 Bog‘cha',school:'🎒 Maktab',college:'🔬 Kollej',uni:'🎓 Institut'};
    const ed=$('<div class="card full oedu" style="margin-top:12px"><div class="lbl">🏫 Ta‘lim muassasalari</div>'+
      '<div class="frow"><select class="sel" id="ekind">'+Object.keys(KN).map(k=>'<option value="'+k+'">'+KN[k]+'</option>').join('')+'</select></div>'+
      '<div class="frow"><input class="bet" id="ename" maxlength="40" placeholder="Nomi (masalan: Prezident maktabi)" style="text-align:left"></div>'+
      '<div class="frow"><input class="bet" id="efee" type="number" inputmode="numeric" placeholder="Yillik to‘lov, $"></div>'+
      '<button class="btn go full" id="eadd">➕ Muassasa ochish</button><div class="elist" id="elist"></div></div>');
    function drawEdu(all){
      const box=app_q(ed,'#elist');
      if(!all.length){ box.innerHTML='<div class="hsub" style="margin-top:10px">Hali muassasa yo‘q — standart narxlar ishlaydi.</div>'; return; }
      box.innerHTML=Object.keys(KN).map(kind=>{ const rows=all.filter(x=>x.kind===kind); if(!rows.length) return '';
        return '<div class="egrp">'+KN[kind]+'</div>'+rows.map(x=>'<div class="erow'+(x.active?'':' off')+'" data-id="'+x.id+'">'+
          '<input class="en" value="'+esc(x.name)+'" maxlength="40"><input class="ef" type="number" inputmode="numeric" value="'+x.fee+'">'+
          '<span class="es" title="Saqlash">💾</span><span class="et" title="Yopish/ochish">'+(x.active?'🟢':'⛔')+'</span></div>').join(''); }).join('');
      box.querySelectorAll('.erow').forEach(r=>{ const id=+r.dataset.id;
        app_q(r,'.es').onclick=()=>api('/app/api/edu/update',{id:id,name:app_q(r,'.en').value,fee:app_q(r,'.ef').value}).then(res=>{
          if(res.result){ toast('✅ Saqlandi'); drawEdu(res.edu_all); } else toast(eduErr(res.error)); });
        app_q(r,'.et').onclick=()=>api('/app/api/edu/toggle',{id:id}).then(res=>{ if(res.result){ toast('✅ Holat o‘zgardi'); drawEdu(res.edu_all); } else toast(eduErr(res.error)); });
      });
    }
    app_q(ed,'#eadd').onclick=()=>api('/app/api/edu/add',{kind:app_q(ed,'#ekind').value,name:app_q(ed,'#ename').value,fee:app_q(ed,'#efee').value}).then(res=>{
      if(res.result==='added'){ toast('✅ Muassasa ochildi'); app_q(ed,'#ename').value=''; app_q(ed,'#efee').value=''; drawEdu(res.edu_all); }
      else toast(eduErr(res.error)); });
    drawEdu(d.edu_all||[]);
    o.appendChild(ed);
    app.appendChild(o);
  }

  // TABS
  const tabs=$('<div class="tabs"></div>');
  const defs=[['profil','👤','Profil'],['reyting','💎','TOP'],['shop','🛍','Do‘kon'],['bank','🏦','Bank'],['birja','📈','Birja'],['farzand','👶','Oila'],['chat','💬','Chat'],['casino',CASINO_ICON,'Kazino']];
  if(d.is_owner&&d.owner) defs.push(['owner','👑','Owner']);
  defs.forEach(([k,t,l])=>{
    const el=$('<div class="tab" data-k="'+k+'"><span class="ti">'+t+'</span><span class="tl">'+l+'</span></div>');
    el.onclick=()=>{setTab(k);};
    tabs.appendChild(el);
  });
  app.appendChild(tabs);
  app.querySelectorAll('.gback').forEach(b=>b.onclick=()=>setTab('casino'));
  setTab(defs.some(x=>x[0]===TAB)||TAB==='crash'||TAB==='frog'||(TAB==='kami'&&d.kami)?TAB:'profil');
  ['s-crash','s-frog','s-kami'].forEach(id=>{ const sc=document.getElementById(id); if(!sc) return;
    sc.insertAdjacentHTML('afterbegin','<div class="sndbar"><span data-snd="m">🎵</span><span data-snd="s">🔊</span></div>');
    sc.querySelectorAll('.sndbar span').forEach(b=>b.onclick=()=>SND.toggle(b.dataset.snd)); });
  SND.paintBars();
  window.D_KAMI_GAME=d.kami_game||null;
  initCrash(); initFrog(); initKami();
}
// tegilganda oltin uchqunlar (Crash'dan tashqari)
document.addEventListener('change',e=>{ if(e.target.matches&&e.target.matches('select.sel')&&typeof SND!=='undefined') SND.ui('select'); });
document.addEventListener('pointerdown',e=>{
  // ✨ ovoz: o'yinlardan tashqaridagi tugmalar (o'yinlarning o'z effektlari bor)
  const u=e.target.closest('.btn,.mini,.kbtn,.opt,.tab,.seg .s,.gcard,.gback,.card[data-tap],.chip,.ovx,.kslot,.kopt,.kst-rot span,.kidc,.avg span');
  if(u && typeof SND!=='undefined' && (!u.closest('#s-crash,#s-frog,#s-kami') || u.classList.contains('gback'))){
    SND.ui(u.classList.contains('tab')?'tab':(u.classList.contains('gcard')||u.hasAttribute('data-tap'))?'card':'sparkle'); }
  const t=e.target.closest('.btn,.mini,.kbtn,.opt,.tab,.pad.active,.seg .s');
  if(!t || t.closest('#s-crash')) return;
  for(let i=0;i<10;i++){ const sp=document.createElement('i'); sp.className='spark';
    const a=Math.random()*Math.PI*2, r=24+Math.random()*34;
    sp.style.left=(e.clientX-3)+'px'; sp.style.top=(e.clientY-3)+'px';
    sp.style.setProperty('--dx',Math.cos(a)*r+'px'); sp.style.setProperty('--dy',Math.sin(a)*r+'px');
    document.body.appendChild(sp); setTimeout(()=>sp.remove(),650); }
},{passive:true});
function setBal(v){ window.BAL=v; const b=document.getElementById('bal'); if(b) b.textContent=fmtMoney(v)+'$'; }
function fmtMoney(n){ return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g,' '); }
function app_q(el,sel){ return el.querySelector(sel); }
function toast(m){ if(typeof SND!=='undefined' && /^[✅🟢🎉🏆]/u.test(String(m))) SND.play('good'); let t=document.getElementById('toast'); if(!t){ t=document.createElement('div'); t.id='toast'; document.body.appendChild(t);}
  t.textContent=m; t.className='show'; clearTimeout(window._tt); window._tt=setTimeout(()=>t.className='',2200); }
function refresh(){ api('/app/api/data',{}).then(r=>{ if(r&&r.ok&&r.enabled) render(r); }); }
function sheet(title, opts, onPick){
  let ov=document.getElementById('ov'); if(!ov){ ov=document.createElement('div'); ov.id='ov'; ov.className='ov'; document.body.appendChild(ov); }
  ov.innerHTML='<div class="sheet"><div style="font-weight:800;font-size:16px;margin-bottom:4px">'+title+'</div>'+
    '<div class="opts">'+opts.map((o,i)=>'<div class="opt" data-i="'+i+'">'+o.label+'</div>').join('')+'</div>'+
    '<button class="btn full" id="ovx" style="background:#1c1830;color:var(--txt)">Yopish</button></div>';
  ov.className='ov show';
  const close=()=>{ ov.className='ov'; };
  ov.querySelector('#ovx').onclick=close;
  ov.onclick=(e)=>{ if(e.target===ov) close(); };
  ov.querySelectorAll('.opt').forEach(el=>el.onclick=()=>{ close(); onPick(opts[+el.dataset.i].value); });
}
function api(path,body){ // 20 s timeout: osilib qolgan so'rov tugmalarni "band" holatda qoldirmasin
  const ac=typeof AbortController!=='undefined'?new AbortController():null, t=ac?setTimeout(()=>ac.abort(),20000):0;
  return fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},signal:ac?ac.signal:undefined,
  body:JSON.stringify(Object.assign({initData:tg?tg.initData:''},body||{}))}).then(r=>r.json()).finally(()=>clearTimeout(t)); }
function haptic(t){ try{tg.HapticFeedback.notificationOccurred(t);}catch(e){} }

// ---- 🎵 Ovoz: har o'yinga alohida sokin fon musiqasi + effektlar (Web Audio sintez, fayl yo'q) ----
const SND=(function(){
  let ctx=null, master, musicBus, sfxBus, verb, cur=null, timer=0, nextT=0, step=0, want=null;
  const pref=(k,d)=>{ try{ const v=localStorage.getItem('snd_'+k); return v==null?d:v==='1'; }catch(e){ return d; } };
  const save=(k,v)=>{ try{ localStorage.setItem('snd_'+k,v?'1':'0'); }catch(e){} };
  let musicOn=pref('m',true), sfxOn=pref('s',true);
  function init(){
    if(ctx) return true;
    const AC=window.AudioContext||window.webkitAudioContext; if(!AC) return false;
    ctx=new AC(); master=ctx.createGain(); master.gain.value=0.9; master.connect(ctx.destination);
    const comp=ctx.createDynamicsCompressor(); comp.threshold.value=-18; comp.ratio.value=3; comp.connect(master);
    musicBus=ctx.createGain(); musicBus.gain.value=0; musicBus.connect(comp);
    sfxBus=ctx.createGain(); sfxBus.gain.value=sfxOn?0.55:0; sfxBus.connect(comp);
    // sun'iy reverb (shovqin impulsi)
    verb=ctx.createConvolver(); const len=ctx.sampleRate*2.6, ir=ctx.createBuffer(2,len,ctx.sampleRate);
    for(let c=0;c<2;c++){ const d=ir.getChannelData(c); for(let i=0;i<len;i++) d[i]=(Math.random()*2-1)*Math.pow(1-i/len,2.6); }
    verb.buffer=ir; const vg=ctx.createGain(); vg.gain.value=0.32; verb.connect(vg); vg.connect(comp);
    return true;
  }
  function unlock(){ if(!init()) return; const go=()=>{ if(want!==cur) setMusic(want); }; if(ctx.state==='suspended') ctx.resume().then(go); else go(); }
  ['pointerdown','touchstart','keydown'].forEach(ev=>document.addEventListener(ev,unlock,{passive:true}));
  document.addEventListener('visibilitychange',()=>{ if(!ctx) return; if(document.hidden) ctx.suspend(); else if(want) ctx.resume(); });
  const mtof=m=>440*Math.pow(2,(m-69)/12);
  // ---- asboblar ----
  function voice(type,freq,t,dur,vol,opt){ opt=opt||{};
    const o=ctx.createOscillator(), g=ctx.createGain(); o.type=type; o.frequency.setValueAtTime(freq,t);
    if(opt.detune) o.detune.value=opt.detune;
    if(opt.slide) o.frequency.exponentialRampToValueAtTime(opt.slide,t+dur);
    const a=opt.a||0.01, r=opt.r||dur;
    g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(vol,t+a); g.gain.exponentialRampToValueAtTime(0.0001,t+a+r);
    let out=g;
    if(opt.lp){ const f=ctx.createBiquadFilter(); f.type='lowpass'; f.frequency.value=opt.lp; f.Q.value=opt.q||0.7; g.connect(f); out=f; }
    o.connect(g); out.connect(opt.bus||musicBus); if(opt.wet) { const w=ctx.createGain(); w.gain.value=opt.wet; out.connect(w); w.connect(verb); }
    o.start(t); o.stop(t+a+r+0.05);
  }
  function noise(t,dur,vol,opt){ opt=opt||{};
    const len=Math.ceil(ctx.sampleRate*dur), b=ctx.createBuffer(1,len,ctx.sampleRate), d=b.getChannelData(0);
    for(let i=0;i<len;i++) d[i]=Math.random()*2-1;
    const s=ctx.createBufferSource(); s.buffer=b; const f=ctx.createBiquadFilter(); f.type=opt.type||'lowpass'; f.frequency.setValueAtTime(opt.f||1200,t);
    if(opt.fTo) f.frequency.exponentialRampToValueAtTime(opt.fTo,t+dur); f.Q.value=opt.q||0.8;
    const g=ctx.createGain(); g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(vol,t+(opt.a||0.005)); g.gain.exponentialRampToValueAtTime(0.0001,t+dur);
    s.connect(f); f.connect(g); g.connect(opt.bus||sfxBus); if(opt.wet){ const w=ctx.createGain(); w.gain.value=opt.wet; g.connect(w); w.connect(verb); }
    s.start(t); s.stop(t+dur+0.05);
  }
  function pad(notes,t,dur,vol,lp){ notes.forEach(n=>[-7,7].forEach(dt=>voice('sawtooth',mtof(n),t,dur,vol,{a:dur*0.35,r:dur*0.75,lp:lp||900,detune:dt,wet:0.7}))); }
  // ---- treklar (bar = 16 qadam) ----
  const TR={
    crash:{bpm:84, // sokin synthwave: Am-F-C-G
      tick(s,t,sp){ const ch=[[57,60,64],[53,57,60],[48,52,55],[55,59,62]][Math.floor(s/32)%4];
        if(s%32===0) pad(ch.map(n=>n-12),t,sp*32,0.035,800);
        if(s%32===0) voice('sine',mtof(ch[0]-24),t,sp*30,0.16,{a:0.05,r:sp*30});
        const arp=[0,1,2,1,0,2,1,2][(s>>1)%8]; if(s%2===0) voice('triangle',mtof(ch[arp]+12),t,sp*2,0.05,{a:0.005,r:sp*3,lp:2600,wet:0.5});
        if(s%8===0) voice('sine',110,t,0.25,0.14,{a:0.002,r:0.22,slide:42});
        if(s%4===2) noise(t,0.05,0.035,{type:'highpass',f:7000,bus:musicBus}); }},
    frog:{bpm:72, // hovuz: marimba pentatonika + suv tomchilari
      tick(s,t,sp){ const sc=[60,62,64,67,69,72,74,76], ch=[[48,55,64],[45,52,60],[41,48,57],[43,50,59]][Math.floor(s/32)%4];
        if(s%32===0) pad(ch,t,sp*32,0.032,750);
        if(s%2===0 && Math.random()<0.55){ const n=sc[Math.floor(Math.random()*sc.length)];
          voice('sine',mtof(n),t,0.5,0.15,{a:0.003,r:0.6,wet:0.6}); voice('sine',mtof(n)*4.0,t,0.12,0.035,{a:0.002,r:0.12}); }
        if(s%16===8 && Math.random()<0.6) voice('sine',900+Math.random()*700,t,0.12,0.04,{a:0.002,r:0.12,slide:2200+Math.random()*900,wet:0.8}); }},
    kami:{bpm:66, // kinematik dengiz: Dm, to'lqin shovqini, uzoq baraban
      tick(s,t,sp){ const ch=[[50,53,57],[46,50,53],[48,52,55],[45,49,52]][Math.floor(s/32)%4];
        if(s%32===0){ pad(ch.map(n=>n-12),t,sp*32,0.03,600); voice('sine',mtof(ch[0]-24),t,sp*31,0.15,{a:0.4,r:sp*30}); }
        if(s%16===0) noise(t,sp*14,0.05,{f:500,fTo:1400,a:sp*6,bus:musicBus,wet:0.4});      // to'lqin
        if(s%16===0||s%16===10) voice('sine',70,t,0.6,0.2,{a:0.004,r:0.6,slide:38,wet:0.5});   // baraban
        if(s%32===24) [0,7,12].forEach((d,i)=>voice('sine',mtof(ch[0]+12+d),t+i*sp*1.5,1.2,0.035,{a:0.003,r:1.4,wet:0.9})); }}
  };
  function loop(){
    if(!cur||!ctx) return; const tr=TR[cur], sp=60/tr.bpm/4;
    while(nextT<ctx.currentTime+0.25){ try{ tr.tick(step,nextT,sp); }catch(e){} nextT+=sp; step++; }
  }
  function setMusic(name){
    want=name; if(!ctx || ctx.state!=='running') return;
    const on=musicOn && name;
    musicBus.gain.cancelScheduledValues(ctx.currentTime);
    musicBus.gain.setTargetAtTime(0,ctx.currentTime,0.25);
    clearInterval(timer);
    if(!on){ cur=null; return; }
    setTimeout(()=>{ if(want!==name) return; cur=name; step=0; nextT=ctx.currentTime+0.1;
      musicBus.gain.setTargetAtTime(1.0,ctx.currentTime,0.8); timer=setInterval(loop,40); loop(); }, cur?450:0);
  }
  // ---- effektlar ----
  const FX={
    chip(t){ voice('square',1800,t,0.04,0.08,{bus:sfxBus,a:0.001,r:0.04,lp:4000}); voice('square',2400,t+0.035,0.04,0.06,{bus:sfxBus,a:0.001,r:0.05,lp:4000}); },
    tick(t){ voice('sine',1320,t,0.06,0.08,{bus:sfxBus,a:0.001,r:0.06}); },
    takeoff(t){ noise(t,1.2,0.12,{type:'bandpass',f:300,fTo:2400,a:0.3,q:1.2,wet:0.3}); voice('sawtooth',90,t,1.1,0.05,{bus:sfxBus,a:0.2,r:0.9,slide:220,lp:800}); },
    cash(t){ [0,4,7,12].forEach((d,i)=>{ voice('triangle',mtof(84+d),t+i*0.06,0.3,0.09,{bus:sfxBus,a:0.002,r:0.35,wet:0.5}); voice('sine',mtof(96+d),t+i*0.06,0.2,0.03,{bus:sfxBus,a:0.002,r:0.2}); }); },
    win(t){ [0,4,7,12,16,19,24].forEach((d,i)=>voice('triangle',mtof(72+d),t+i*0.07,0.4,0.08,{bus:sfxBus,a:0.002,r:0.5,wet:0.6})); },
    boom(t){ noise(t,1.1,0.5,{f:1800,fTo:80,a:0.003,wet:0.5}); voice('sine',90,t,0.8,0.5,{bus:sfxBus,a:0.003,r:0.8,slide:30}); },
    hop(t){ voice('sine',320,t,0.14,0.14,{bus:sfxBus,a:0.003,r:0.14,slide:760}); },
    plop(t){ voice('sine',600,t,0.12,0.12,{bus:sfxBus,a:0.002,r:0.12,slide:1500,wet:0.5}); noise(t,0.08,0.05,{type:'bandpass',f:1800,q:2}); },
    splash(t){ noise(t,0.7,0.35,{f:3500,fTo:300,a:0.004,wet:0.6}); voice('sine',260,t,0.4,0.15,{bus:sfxBus,a:0.003,r:0.4,slide:70}); },
    click(t){ voice('triangle',900,t,0.05,0.07,{bus:sfxBus,a:0.001,r:0.05}); },
    whoosh(t){ noise(t,0.45,0.13,{type:'bandpass',f:500,fTo:2600,a:0.15,q:1.4}); },
    cannon(t){ noise(t,0.45,0.35,{f:900,fTo:120,a:0.002,wet:0.6}); voice('sine',70,t,0.4,0.35,{bus:sfxBus,a:0.002,r:0.4,slide:35}); },
    explode(t){ FX.boom(t); noise(t+0.08,0.9,0.2,{type:'highpass',f:2500,fTo:600,a:0.01}); },
    bigboom(t){ FX.boom(t); FX.boom(t+0.18); noise(t,1.8,0.3,{f:600,fTo:60,a:0.01,wet:0.8}); setTimeout(()=>play('win'),500); },
    // ✨ interfeys: sehrli uchqunlar (premium his)
    sparkle(t){ const sc=[88,91,93,95,98,100,103,105], n=4+Math.floor(Math.random()*2), st=Math.floor(Math.random()*3);
      for(let i=0;i<n;i++){ const m=sc[Math.min(sc.length-1,st+i+Math.floor(Math.random()*2))], tt=t+i*(0.028+Math.random()*0.014), f=mtof(m);
        bell(f,tt,0.05-i*0.006,0.5); }
      noise(t,0.35,0.025,{type:'highpass',f:6500,fTo:11000,a:0.02,wet:0.6}); },
    tab(t){ const b=[84,86,88][Math.floor(Math.random()*3)]; bell(mtof(b),t,0.05,0.6); bell(mtof(b+7),t+0.05,0.04,0.7);
      noise(t,0.22,0.015,{type:'highpass',f:8000,a:0.01,wet:0.5}); },
    card(t){ noise(t,0.45,0.04,{type:'bandpass',f:1200,fTo:7000,a:0.12,q:2,wet:0.5});
      [76,83,88,95,100].forEach((m,i)=>bell(mtof(m),t+0.06+i*0.045,0.045,0.6)); },
    select(t){ bell(mtof(93+Math.floor(Math.random()*3)*2),t,0.035,0.35); },
    good(t){ [72,79,84,88,91,96].forEach((m,i)=>{ bell(mtof(m),t+i*0.055,0.055,0.9); });
      voice('sine',mtof(60),t,1.2,0.05,{bus:sfxBus,a:0.02,r:1.2,wet:0.8}); noise(t+0.1,0.8,0.02,{type:'highpass',f:7000,a:0.2,wet:0.8}); }
  };
  // qo'ng'iroq: asosiy ton + noharmonik qism (shisha/kristall tembri)
  function bell(f,t,vol,dur){ voice('sine',f,t,dur,vol,{bus:sfxBus,a:0.002,r:dur,wet:0.9});
    voice('sine',f*2.76,t,dur*0.45,vol*0.35,{bus:sfxBus,a:0.001,r:dur*0.45,wet:0.9});
    voice('triangle',f*5.4,t,dur*0.2,vol*0.12,{bus:sfxBus,a:0.001,r:dur*0.2}); }
  let lastUi=0;
  function ui(name){ const n=performance.now(); if(n-lastUi<70) return; lastUi=n; play(name); }
  function play(name){ if(!sfxOn || !init() || ctx.state!=='running' || !FX[name]) return; try{ FX[name](ctx.currentTime+0.01); }catch(e){} }
  function toggle(kind){
    if(kind==='m'){ musicOn=!musicOn; save('m',musicOn); setMusic(want); }
    else { sfxOn=!sfxOn; save('s',sfxOn); if(ctx) sfxBus.gain.setTargetAtTime(sfxOn?0.55:0,ctx.currentTime,0.05); }
    paintBars();
  }
  function paintBars(){ document.querySelectorAll('.sndbar').forEach(b=>{
    const m=b.querySelector('[data-snd="m"]'), s=b.querySelector('[data-snd="s"]');
    m.classList.toggle('off',!musicOn); s.classList.toggle('off',!sfxOn); s.textContent=sfxOn?'🔊':'🔇'; }); }
  return {music:setMusic, play, ui, toggle, paintBars};
})();

// ---- 🧒 3D farzand personaji (three.js, kerak bo'lganda yuklanadi) ----
const KID3D=(function(){
  const URL3='https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
  let loading=null;
  function load(){ if(window.THREE) return Promise.resolve(); if(loading) return loading;
    loading=new Promise((ok,bad)=>{ const s=document.createElement('script'); s.src=URL3; s.onload=ok; s.onerror=()=>{loading=null;bad();}; document.head.appendChild(s); });
    return loading; }
  // katalog: slot → variantlar (min/max yosh, g — jins)
  const CAT={
    hat:{n:'Bosh kiyim',ic:'🎩',o:[['none','Yo‘q','🚫'],['cap_red','Qizil kepka','🧢'],['cap_blue','Ko‘k kepka','🧢'],['beanie','Telpak','🧶'],['bear','Ayiqcha shapka','🐻',0,6],
      ['bow','Bant','🎀',0,99,'girl'],['crown','Oltin toj','👑'],['grad','Bitiruv shapkasi','🎓',19],['band','Gulchambar','🌸',0,99,'girl']]},
    top:{n:'Ustki kiyim',ic:'👕',o:[['onesie','Bodi','🍼',0,2],['tee_red','Qizil futbolka','👕'],['tee_blue','Ko‘k futbolka','👕'],['tee_yellow','Sariq futbolka','👕'],['hoodie','Xudi','🧥',3],
      ['dress_pink','Pushti ko‘ylak','👗',0,99,'girl'],['dress_purple','Binafsha ko‘ylak','👗',0,99,'girl'],['uniform','Maktab formasi','👔',7],['labcoat','Lab xalati','🥼',16],['suit','Kostyum','🤵',16]]},
    bottom:{n:'Shim / yubka',ic:'👖',o:[['diaper','Taglik','🧷',0,2],['shorts','Shorti','🩳'],['jeans','Jinsi','👖',3],['pants_dark','Klassik shim','👖',7],['skirt','Yubka','💃',3,99,'girl']]},
    shoes:{n:'Oyoq kiyim',ic:'👟',o:[['bare','Yalangoyoq','🦶'],['socks','Paypoq','🧦'],['sneakers','Krossovka','👟',2],['boots','Etik','🥾',3],['shoes_black','Tufli','👞',7],['sandals','Sandal','🩴',3]]},
    acc:{n:'Aksessuar',ic:'🕶',o:[['none','Yo‘q','🚫'],['pacifier','So‘rg‘ich','🍼',0,3],['glasses','Ko‘zoynak','👓',5],['backpack','Ryukzak','🎒',5],['scarf','Sharf','🧣'],['bowtie','Babochka','🎀',3]]},
    emo:{n:'Emotsiya',ic:'😊',o:[['happy','Xursand','😊'],['laugh','Kulgi','😆'],['love','Sevgi','😍'],['sleepy','Uyquchi','😴'],['surprised','Hayron','😮'],['cry','Yig‘loqi','😢'],['cool','Zo‘r','😎',5]]}
  };
  const DEF={hat:'none',top:'tee_blue',bottom:'shorts',shoes:'sneakers',acc:'none',emo:'happy'};
  function allowed(slot,age,gender){ return CAT[slot].o.filter(o=>{ const mn=o[3]||0, mx=o[4]==null?99:o[4]; return age>=mn && age<=mx && (!o[5]||o[5]===gender); }); }
  function fit(kid){ // yoshga mos kiyim (saqlangan bo'lsa — o'sha, bo'lmasa standart)
    const out={}, age=kid.age, g=kid.gender;
    for(const slot in CAT){ const ok=allowed(slot,age,g).map(o=>o[0]); let v=(kid.outfit||{})[slot];
      if(!ok.includes(v)){ v= slot==='top'? (age<=2?'onesie':(g==='girl'?'dress_pink':'tee_blue')) : slot==='bottom'? (age<=2?'diaper':(g==='girl'&&age>=3?'skirt':'shorts'))
        : slot==='shoes'? (age<2?'socks':'sneakers') : slot==='acc'? (age<=1?'pacifier':'none') : DEF[slot]; if(!ok.includes(v)) v=ok[0]; }
      out[slot]=v; }
    return out;
  }
  const COL={red:0xe53935,blue:0x1e88e5,yellow:0xfdd835,pink:0xf48fb1,purple:0x8e5bd6,white:0xf5f5f5,dark:0x263238,denim:0x3f6fb5,khaki:0xc8a46a,
    hoodie:0x43a047,skin:0xf2c7a5,hair_b:0x3e2723,hair_g:0x5d4037,gold:0xffc63a,black:0x1a1a1a,navy:0x1a237e,brown:0x8d6e63,green:0x2e7d32};
  // ---- sahna ----
  let R,S,CAM,root=null,raf=0,cvs=null,stageCol=0x2a1e0c,blinkT=0,eyes=[],t0=0,targetRot=0,curRot=0,emoState='happy',tears=[];
  function mat(c,o){ return new THREE.MeshStandardMaterial(Object.assign({color:c,roughness:.55,metalness:0},o||{})); }
  function sph(r,c,x,y,z,sx,sy,sz,o){ const m=new THREE.Mesh(new THREE.SphereGeometry(r,32,24),mat(c,o)); m.position.set(x,y,z); if(sx) m.scale.set(sx,sy,sz); m.castShadow=true; return m; }
  function cyl(rt,rb,h,c,x,y,z,o){ const m=new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,28),mat(c,o)); m.position.set(x,y,z); m.castShadow=true; return m; }
  function box(w,h,d,c,x,y,z,o){ const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat(c,o)); m.position.set(x,y,z); m.castShadow=true; return m; }
  function tor(r,tube,arc,c,x,y,z,o){ const m=new THREE.Mesh(new THREE.TorusGeometry(r,tube,12,40,arc||Math.PI*2),mat(c,o)); m.position.set(x,y,z); return m; }
  function init(canvas){
    cvs=canvas; R=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true}); R.setPixelRatio(Math.min(2,window.devicePixelRatio||1));
    R.shadowMap.enabled=true; R.outputEncoding=THREE.sRGBEncoding; R.toneMapping=THREE.ACESFilmicToneMapping; R.toneMappingExposure=1.1;
    S=new THREE.Scene(); CAM=new THREE.PerspectiveCamera(32,1,0.1,50);
    S.add(new THREE.HemisphereLight(0xfff4e0,0x3a2a14,0.75));
    const k=new THREE.DirectionalLight(0xffffff,1.15); k.position.set(2.5,4,3.5); k.castShadow=true; k.shadow.mapSize.set(1024,1024); S.add(k);
    const rim=new THREE.DirectionalLight(0xffd27a,0.7); rim.position.set(-3,2.5,-3); S.add(rim);
    const ground=new THREE.Mesh(new THREE.CircleGeometry(1.25,48),new THREE.MeshStandardMaterial({color:0xffffff,transparent:true,opacity:.18}));
    ground.rotation.x=-Math.PI/2; ground.receiveShadow=true; S.add(ground);
    const ring=new THREE.Mesh(new THREE.RingGeometry(1.18,1.28,64),new THREE.MeshBasicMaterial({color:0xffd24a,transparent:true,opacity:.55})); ring.rotation.x=-Math.PI/2; ring.position.y=.002; S.add(ring);
  }
  function lin(c){ const x=new THREE.Color(c); x.convertSRGBToLinear(); return x; }
  function build(kid,of){
    if(root){ S.remove(root); root.traverse(o=>{ if(o.geometry) o.geometry.dispose(); if(o.material) o.material.dispose(); }); }
    root=new THREE.Group(); eyes=[]; tears=[]; emoState=of.emo;
    const age=Math.max(0,Math.min(23,kid.age)), t=Math.min(1,age/20), girl=kid.gender==='girl';
    const legH=.18+.5*t, torsoH=.3+.32*t, torsoR=.2+.05*t, headR=.36-.08*t, armL=.24+.32*t, legR=.075+.025*t;
    const skin=COL.skin, hairC=girl?COL.hair_g:COL.hair_b;
    const top=of.top, bot=of.bottom;
    const topC= top.startsWith('tee_')?COL[top.slice(4)] : top==='hoodie'?COL.hoodie : top==='onesie'?0xffe082 : top.startsWith('dress_')?COL[top.slice(6)]
      : top==='uniform'?COL.white : top==='labcoat'?COL.white : top==='suit'?COL.navy : COL.blue;
    const botC= bot==='diaper'?COL.white : bot==='jeans'?COL.denim : bot==='pants_dark'?COL.dark : bot==='skirt'?(girl?COL.purple:COL.navy) : COL.khaki;
    const dress=top.startsWith('dress_'), onesie=top==='onesie';
    // ---- oyoqlar ----
    const hipY=legH+.06, footY=.05;
    [-1,1].forEach(sx=>{
      const x=sx*(torsoR*.48);
      const lower=(bot==='shorts'||bot==='skirt'||bot==='diaper'||dress||onesie)?skin:botC;
      root.add(cyl(legR,legR*.92,legH,lower,x,footY+legH/2+.02,0));
      if(bot==='shorts') root.add(cyl(legR*1.25,legR*1.2,legH*.42,botC,x,hipY-legH*.2,0));
      // poyabzal
      const sh=of.shoes;
      if(sh==='bare') root.add(sph(legR*1.1,skin,x,footY,.04,1,.55,1.5));
      else if(sh==='socks'){ root.add(sph(legR*1.15,0xffffff,x,footY,.04,1,.6,1.5)); root.add(cyl(legR*1.02,legR*1.02,.08,0xffffff,x,footY+.06,0)); }
      else { const c= sh==='sneakers'?0xf44336: sh==='boots'?COL.brown: sh==='shoes_black'?COL.black: 0xffb74d;
        root.add(box(legR*2.4,.08+(sh==='boots'?.04:0),legR*3.4,c,x,footY+(sh==='boots'?.02:0),.05));
        if(sh==='sneakers') root.add(box(legR*2.45,.025,legR*3.45,0xffffff,x,footY-.035,.05));
        if(sh==='boots') root.add(cyl(legR*1.15,legR*1.15,.16,c,x,footY+.12,0)); }
    });
    // ---- tana ----
    const tY=hipY+torsoH/2;
    if(bot==='diaper'||onesie){ root.add(sph(torsoR*1.02,onesie?topC:COL.white,0,hipY-.02,0,1,.6,1)); }
    else if(!dress) root.add(cyl(torsoR*.98,torsoR*.95,.12,botC,0,hipY,0));
    if(bot==='skirt'&&!dress) root.add(cyl(torsoR*1.0,torsoR*1.6,legH*.42,botC,0,hipY-legH*.15,0));
    const body=cyl(torsoR,torsoR*1.02,torsoH,topC,0,tY,0); root.add(body);
    root.add(sph(torsoR,topC,0,tY+torsoH/2,0,1,.45,1));            // yelka
    if(dress) root.add(cyl(torsoR*1.02,torsoR*1.9,legH*.6,topC,0,hipY-legH*.22,0));
    if(top==='uniform'){ root.add(box(.07,torsoH*.75,.02,0xc62828,0,tY,torsoR*.98)); root.add(cyl(torsoR*1.01,torsoR*1.03,torsoH*.55,COL.navy,0,tY-torsoH*.18,0)); }
    if(top==='suit'){ root.add(box(.12,torsoH*.85,.02,0xffffff,0,tY+.02,torsoR*.97)); root.add(box(.05,torsoH*.6,.025,0xc62828,0,tY+.02,torsoR*.99)); }
    if(top==='labcoat'){ root.add(cyl(torsoR*1.06,torsoR*1.25,torsoH*1.55,0xfafafa,0,tY-torsoH*.3,0,{transparent:true,opacity:.97}));
      root.add(box(.02,torsoH*1.3,.02,0xb0bec5,0,tY-torsoH*.2,torsoR*1.12)); }
    if(top==='hoodie'){ root.add(tor(torsoR*.62,.07,Math.PI*2,COL.hoodie,0,tY+torsoH/2+.02,-.08)); root.children[root.children.length-1].rotation.x=Math.PI/2.4;
      root.add(box(torsoR*.9,.1,.02,0x2e7d32,0,tY-torsoH*.18,torsoR*.99)); }
    // ---- qo'llar ----
    [-1,1].forEach(sx=>{
      const g=new THREE.Group(); g.position.set(sx*(torsoR+.05),tY+torsoH*.38,0); g.rotation.z=sx*.18;
      const longSleeve=['hoodie','uniform','labcoat','suit','onesie'].includes(top);
      const upper=cyl(.06+.015*t,.055+.015*t,armL*.5,topC,0,-armL*.25,0); g.add(upper);
      g.add(cyl(.055+.012*t,.05+.012*t,armL*.5,longSleeve?(top==='labcoat'?0xfafafa:topC):skin,0,-armL*.72,0));
      g.add(sph(.06+.012*t,skin,0,-armL*1.0,0));
      root.add(g);
    });
    // ---- bosh ----
    const hY=tY+torsoH/2+headR*.95;
    root.add(cyl(.06,.07,.1,skin,0,hY-headR*.95,0));
    const head=sph(headR,skin,0,hY,0); root.add(head);
    [-1,1].forEach(sx=>root.add(sph(headR*.2,skin,sx*headR*.97,hY,0,.6,1,1)));
    // soch
    const hair=new THREE.Mesh(new THREE.SphereGeometry(headR*1.05,32,24,0,Math.PI*2,0,Math.PI*(age<=1?.28:.52)),mat(hairC,{roughness:.8}));
    hair.position.set(0,hY+headR*.03,-headR*.04); hair.rotation.x=-.25; hair.castShadow=true; root.add(hair);
    if(girl&&age>=3){ [-1,1].forEach(sx=>root.add(sph(headR*.32,hairC,sx*headR*.95,hY-headR*.15,-headR*.35,.8,1.4,.8))); root.add(sph(headR*.9,hairC,0,hY-headR*.25,-headR*.45,1,1.1,.6)); }
    if(age<=1) root.add(tor(headR*.12,.018,Math.PI*1.4,hairC,0,hY+headR*1.02,0));
    // yuz: ko'zlar va og'iz — emotsiya bo'yicha
    const fz=headR*.92, ey=hY+headR*.12, ex=headR*.36, er=headR*(age<=2?.15:.12);
    const emo=of.emo;
    const eyeMat=mat(0x1a1a1a,{roughness:.2});
    if(emo==='happy'||emo==='surprised'||emo==='cry'||emo==='cool'){
      [-1,1].forEach(sx=>{ const g=new THREE.Group(); g.position.set(sx*ex,ey,fz);
        const s=emo==='surprised'?1.3:1; const e=new THREE.Mesh(new THREE.SphereGeometry(er*s,24,18),eyeMat); e.scale.z=.5; g.add(e);
        const hl=new THREE.Mesh(new THREE.SphereGeometry(er*.35*s,12,10),new THREE.MeshBasicMaterial({color:0xffffff})); hl.position.set(er*.3,er*.35,er*.35); g.add(hl);
        root.add(g); eyes.push(g); });
    } else if(emo==='laugh'||emo==='sleepy'){
      [-1,1].forEach(sx=>{ const a=tor(er*1.05,er*.28,Math.PI,0x1a1a1a,sx*ex,ey-(emo==='sleepy'?er*.4:0),fz); a.rotation.z=emo==='sleepy'?Math.PI:0; root.add(a); });
    } else if(emo==='love'){
      [-1,1].forEach(sx=>{ const g=new THREE.Group(); g.position.set(sx*ex,ey,fz+.01); const red=mat(0xe91e63,{roughness:.3,emissive:0x550022});
        g.add(sph(er*.62,0xe91e63,-er*.42,er*.25,0)); g.add(sph(er*.62,0xe91e63,er*.42,er*.25,0));
        const c=new THREE.Mesh(new THREE.ConeGeometry(er*1.0,er*1.3,24),red); c.rotation.z=Math.PI; c.position.y=-er*.4; g.add(c); g.scale.z=.5; root.add(g); });
    }
    if(emo==='cool'){ [-1,1].forEach(sx=>root.add(box(er*3.2,er*2.0,.02,0x111111,sx*ex,ey,fz+.04,{metalness:.6,roughness:.15}))); root.add(box(ex*.8,.025,.02,0x111111,0,ey+er*.4,fz+.04)); }
    if(emo==='cry'){ [-1,1].forEach(sx=>{ const d=sph(er*.45,0x64b5f6,sx*ex,ey-er*2.2,fz+.02,.8,1.3,.6,{transparent:true,opacity:.85,roughness:.05}); root.add(d); tears.push(d); }); }
    // og'iz
    const my=hY-headR*.32, mz=headR*.93;
    if(of.acc==='pacifier'){ root.add(cyl(headR*.16,headR*.16,.03,0x81d4fa,0,my,mz+.02)).rotation&&0; const p=root.children[root.children.length-1]; p.rotation.x=Math.PI/2;
      const r=tor(headR*.09,headR*.025,Math.PI*2,0xffffff,0,my,mz+.05); root.add(r); }
    else if(emo==='laugh'){ const m=new THREE.Mesh(new THREE.SphereGeometry(headR*.2,24,16,0,Math.PI*2,Math.PI/2,Math.PI/2),mat(0x8e2430)); m.position.set(0,my+headR*.06,mz); m.rotation.x=-.25; root.add(m); }
    else if(emo==='surprised'){ root.add(tor(headR*.09,headR*.035,Math.PI*2,0x8e2430,0,my,mz)); }
    else if(emo==='sleepy'){ root.add(box(headR*.18,headR*.03,.02,0x8e2430,0,my,mz)); }
    else { const sm=tor(headR*.17,headR*.03,Math.PI,0x8e2430,0,my+(emo==='cry'?-headR*.06:headR*.05),mz); sm.rotation.z=emo==='cry'?0:Math.PI; root.add(sm); }
    // yonoqlar
    [-1,1].forEach(sx=>root.add(sph(headR*.12,0xff8a80,sx*headR*.55,hY-headR*.18,headR*.8,1,.6,.4,{transparent:true,opacity:.7})));
    // ---- bosh kiyim ----
    const tY2=hY+headR*.7, h=of.hat;
    if(h.startsWith('cap_')){ const c=h==='cap_red'?COL.red:COL.blue;
      root.add(new THREE.Mesh(new THREE.SphereGeometry(headR*1.07,32,16,0,Math.PI*2,0,Math.PI*.42),mat(c))).position&&0; root.children[root.children.length-1].position.set(0,hY+headR*.05,0);
      const brim=cyl(headR*.62,headR*.62,.025,c,0,hY+headR*.42,headR*.7); brim.scale.z=.7; root.add(brim); }
    else if(h==='beanie'){ const b=new THREE.Mesh(new THREE.SphereGeometry(headR*1.08,32,16,0,Math.PI*2,0,Math.PI*.45),mat(0x7e57c2,{roughness:.9})); b.position.y=hY+headR*.02; root.add(b);
      root.add(cyl(headR*1.06,headR*1.06,headR*.22,0x5e35b1,0,hY+headR*.35,0)); root.add(sph(headR*.2,0xffffff,0,hY+headR*1.12,0,1,1,1,{roughness:1})); }
    else if(h==='bear'){ const b=new THREE.Mesh(new THREE.SphereGeometry(headR*1.08,32,16,0,Math.PI*2,0,Math.PI*.5),mat(COL.brown,{roughness:.95})); b.position.y=hY; root.add(b);
      [-1,1].forEach(sx=>{ root.add(sph(headR*.26,COL.brown,sx*headR*.7,hY+headR*.85,0,1,1,.6,{roughness:.95})); root.add(sph(headR*.14,0xd7a98c,sx*headR*.7,hY+headR*.85,headR*.12,1,1,.4)); }); }
    else if(h==='bow'){ [-1,1].forEach(sx=>{ const c=new THREE.Mesh(new THREE.ConeGeometry(headR*.22,headR*.4,16),mat(0xff4081)); c.rotation.z=sx*Math.PI/2; c.position.set(headR*.45+sx*headR*.2,hY+headR*.9,headR*.1); root.add(c); });
      root.add(sph(headR*.09,0xf50057,headR*.45,hY+headR*.9,headR*.1)); }
    else if(h==='band'){ for(let i=0;i<9;i++){ const a=-Math.PI*.9+i*(Math.PI*1.8/8); root.add(sph(headR*.11,[0xff80ab,0xfff176,0xb39ddb][i%3],Math.sin(a)*headR*.98,hY+headR*.62,Math.cos(a)*headR*.5)); } }
    else if(h==='crown'){ const g=mat(COL.gold,{metalness:1,roughness:.25,emissive:0x3a2a00}); const band=new THREE.Mesh(new THREE.CylinderGeometry(headR*.62,headR*.66,headR*.3,32,1,true),g); band.position.y=tY2+headR*.12; root.add(band);
      for(let i=0;i<6;i++){ const a=i/6*Math.PI*2; const c=new THREE.Mesh(new THREE.ConeGeometry(headR*.1,headR*.3,12),g); c.position.set(Math.cos(a)*headR*.62,tY2+headR*.42,Math.sin(a)*headR*.62); root.add(c);
        root.add(sph(headR*.05,[0xff1744,0x2979ff,0x00e676][i%3],Math.cos(a)*headR*.66,tY2+headR*.12,Math.sin(a)*headR*.66,1,1,1,{roughness:.1})); } }
    else if(h==='grad'){ root.add(cyl(headR*.62,headR*.66,headR*.28,COL.black,0,tY2+headR*.08,0)); root.add(box(headR*1.6,.04,headR*1.6,COL.black,0,tY2+headR*.24,0));
      root.add(cyl(.008,.008,headR*.6,COL.gold,headR*.65,tY2,headR*.3)); root.add(sph(.03,COL.gold,headR*.65,tY2-headR*.32,headR*.3)); }
    // ---- aksessuar ----
    const a=of.acc;
    if(a==='glasses'){ [-1,1].forEach(sx=>root.add(tor(er*1.7,.012,Math.PI*2,0x212121,sx*ex,ey,fz+.04))); root.add(box(ex*.5,.015,.015,0x212121,0,ey,fz+.04)); }
    if(a==='backpack'){ root.add(box(torsoR*1.3,torsoH*.8,torsoR*.7,0xff7043,0,tY,-torsoR-torsoR*.3)); [-1,1].forEach(sx=>root.add(box(.03,torsoH*.85,.03,0xbf360c,sx*torsoR*.5,tY,torsoR*.95))); }
    if(a==='scarf'){ const sc=tor(torsoR*.62,.06,Math.PI*2,0xd32f2f,0,tY+torsoH/2+.03,0); sc.rotation.x=Math.PI/2; root.add(sc); root.add(box(.1,torsoH*.5,.04,0xd32f2f,torsoR*.3,tY+torsoH*.1,torsoR*.95)); }
    if(a==='bowtie'){ [-1,1].forEach(sx=>{ const c=new THREE.Mesh(new THREE.ConeGeometry(.045,.09,12),mat(0xc62828)); c.rotation.z=sx*Math.PI/2; c.position.set(sx*.04,tY+torsoH/2-.03,torsoR*.98); root.add(c); }); }
    root.traverse(o=>{ if(o.material&&o.material.color&&!o.material._lin){ o.material.color.convertSRGBToLinear(); o.material._lin=1; } });
    S.add(root);
    // kamera: bo'yga moslab
    // kamera umumiy masshtabda: chaqaloq kichik, katta yoshdagi baland ko'rinadi (yoshga qarab o'sish seziladi)
    const H=hY+headR*(h==='none'?1.1:1.6), HC=0.42*H+0.58*2.05;
    CAM.position.set(0,HC*.52,HC*2.3+1.0); CAM.lookAt(0,HC*.46,0);
    root.rotation.y=curRot;
  }
  function frame(now){
    raf=requestAnimationFrame(frame);
    if(!root) return;
    const w=cvs.clientWidth,h=cvs.clientHeight; if(R.domElement.width!==Math.floor(w*R.getPixelRatio())||R.domElement.height!==Math.floor(h*R.getPixelRatio())){ R.setSize(w,h,false); CAM.aspect=w/h; CAM.updateProjectionMatrix(); }
    curRot+=(targetRot-curRot)*0.12; root.rotation.y=curRot;
    const t=(now-t0)/1000; root.position.y=Math.sin(t*2)*.012; root.scale.y=1+Math.sin(t*2)*.008;
    // ko'z qisish
    if(t>blinkT){ blinkT=t+2.5+Math.random()*2.5; }
    const b=Math.max(0,1-Math.abs(t-blinkT+.08)*14); eyes.forEach(e=>e.scale.y=1-0.9*b*(emoState==='surprised'?0.3:1));
    tears.forEach((d,i)=>{ d.position.y-=0.0025; if(d.userData.y0==null) d.userData.y0=d.position.y+.0025; if(d.position.y<d.userData.y0-.12) d.position.y=d.userData.y0; });
    R.render(S,CAM);
  }
  function height(age,g){ const T=[50,75,87,96,103,110,116,122,128,133,138,144,150,156,162,167,170,172,174,175,176];
    const v=T[Math.min(T.length-1,Math.max(0,age|0))]; return g==='girl'&&age>=12?v-6:v; }
  return {
    CAT, allowed, fit, height, load,
    async open(canvas,kid,outfit){ await load(); if(!R||cvs!==canvas){ if(R){ R.dispose(); } R=null; init(canvas); }
      t0=performance.now(); curRot=targetRot=0; build(kid,outfit); cancelAnimationFrame(raf); raf=requestAnimationFrame(frame); },
    rebuild(kid,outfit){ if(R) build(kid,outfit); },
    turn(d){ targetRot+=d; }, drag(d){ targetRot+=d; curRot+=d; },
    view(){ const a=((targetRot%(Math.PI*2))+Math.PI*2)%(Math.PI*2); const i=Math.round(a/(Math.PI/2))%4; return ['Old tomoni','O‘ng yon','Orqa tomoni','Chap yon'][i]; },
    close(){ cancelAnimationFrame(raf); raf=0; }
  };
})();

// ---- 🧒 Farzand 3D studiyasi (kartochka bosilganda) ----
function openKidStudio(k){
  let ov=document.getElementById('kst');
  if(!ov){ ov=document.createElement('div'); ov.id='kst'; ov.className='kst'; document.body.appendChild(ov); }
  const of=KID3D.fit(k), L=['hat','top','bottom'], Rr=['shoes','acc','emo'];
  const slotHtml=s=>{ const o=KID3D.CAT[s].o.find(x=>x[0]===of[s])||KID3D.CAT[s].o[0];
    return '<div class="kslot" data-s="'+s+'"><span class="ki">'+o[2]+'</span><span class="kn">'+KID3D.CAT[s].n+'</span></div>'; };
  ov.innerHTML='<div class="kst-in st-'+(k.stage_key||'baby')+'">'+
    '<div class="kst-hd"><div><div class="kst-name">'+esc(k.name)+'</div><div class="kst-sub">'+esc(k.age)+' yosh · 📏 ~'+KID3D.height(k.age,k.gender)+' sm · '+esc(k.stage)+
      ((k.parents||[]).length?' · 👨‍👩‍👧 '+esc(k.parents[0])+' ❤️ '+esc(k.parents[1]):'')+'</div></div><span class="kst-x" id="kstX">✕</span></div>'+
    '<div class="kst-stage" id="kstStage"><canvas id="kstCv"></canvas>'+
      '<div class="kst-col l">'+L.map(slotHtml).join('')+'</div><div class="kst-col r">'+Rr.map(slotHtml).join('')+'</div>'+
      '<div class="kst-load" id="kstLoad">⏳ 3D personaj yuklanmoqda…</div></div>'+
    '<div class="kst-rot"><span id="kstL">⟲</span><b id="kstV">Old tomoni</b><span id="kstR">⟳</span></div>'+
    '<div class="kst-pick" id="kstPick"><div class="kst-hint">👆 Kiyim tanlash uchun chekkadagi kataklarni bosing · personajni barmoq bilan aylantiring</div></div></div>';
  ov.className='kst show';
  const cv=document.getElementById('kstCv'), pick=document.getElementById('kstPick'), vlab=document.getElementById('kstV');
  let saveT=0, cur=null;
  const close=()=>{ ov.className='kst'; KID3D.close(); };
  document.getElementById('kstX').onclick=close;
  ov.onclick=e=>{ if(e.target===ov) close(); };
  const upd=()=>{ vlab.textContent=KID3D.view(); };
  document.getElementById('kstL').onclick=()=>{ KID3D.turn(-Math.PI/2); setTimeout(upd,10); };
  document.getElementById('kstR').onclick=()=>{ KID3D.turn(Math.PI/2); setTimeout(upd,10); };
  let dragX=null;
  cv.addEventListener('pointerdown',e=>{ dragX=e.clientX; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener('pointermove',e=>{ if(dragX==null) return; KID3D.drag((e.clientX-dragX)*0.012); dragX=e.clientX; upd(); });
  cv.addEventListener('pointerup',()=>{ dragX=null; });
  function showPick(s){
    cur=s; ov.querySelectorAll('.kslot').forEach(x=>x.classList.toggle('on',x.dataset.s===s));
    const opts=KID3D.allowed(s,k.age,k.gender);
    pick.innerHTML='<div class="kst-pt">'+KID3D.CAT[s].ic+' '+KID3D.CAT[s].n+'</div><div class="kst-opts">'+
      opts.map(o=>'<div class="kopt'+(of[s]===o[0]?' on':'')+'" data-v="'+o[0]+'"><span>'+o[2]+'</span><small>'+o[1]+'</small></div>').join('')+'</div>';
    pick.querySelectorAll('.kopt').forEach(el=>el.onclick=()=>{
      of[s]=el.dataset.v; pick.querySelectorAll('.kopt').forEach(x=>x.classList.toggle('on',x===el));
      const o=KID3D.CAT[s].o.find(x=>x[0]===of[s]); ov.querySelector('.kslot[data-s="'+s+'"] .ki').textContent=o[2];
      KID3D.rebuild(k,of); k.outfit=Object.assign({},of);
      clearTimeout(saveT); saveT=setTimeout(()=>api('/app/api/kid/outfit',{kid:k.id,outfit:of}).then(r=>{ if(!r||r.error) toast(kidErr(r&&r.error)); }),500);
    });
  }
  ov.querySelectorAll('.kslot').forEach(el=>el.onclick=()=>showPick(el.dataset.s));
  KID3D.open(cv,k,of).then(()=>{ document.getElementById('kstLoad').style.display='none'; })
    .catch(()=>{ document.getElementById('kstLoad').textContent='⚠️ 3D yuklanmadi. Internetni tekshiring.'; });
}

// ---- 🧍 Realistik 3D avatar: skeletli (MakeHuman cmu_mb), almashtiriladigan kiyimlar, mocap harakatlar — test: ownerlar ----
const AV3D=(function(){
  const EX='https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/';
  let ld=null;
  const sc=u=>new Promise((ok,bad)=>{ const s=document.createElement('script'); s.src=u; s.onload=ok; s.onerror=bad; document.head.appendChild(s); });
  function load(){ if(ld) return ld;
    ld=KID3D.load().then(()=>Promise.all([THREE.GLTFLoader?0:sc(EX+'loaders/GLTFLoader.js'),
      window.MeshoptDecoder?0:sc(EX+'libs/meshopt_decoder.js'), THREE.RoomEnvironment?0:sc(EX+'environments/RoomEnvironment.js')]))
      .catch(e=>{ ld=null; throw e; });
    return ld; }
  const MO=['male_casualsuit01','male_casualsuit02','male_casualsuit03','male_casualsuit04','male_casualsuit05','male_casualsuit06','male_elegantsuit01','male_worksuit01'];
  const FO=['female_casualsuit01','female_casualsuit02','female_elegantsuit01','female_sportsuit01'];
  const SH=['shoes01','shoes02','shoes03','shoes04','shoes05','shoes06'];
  const BIT={}; MO.concat(FO,SH).forEach((n,i)=>BIT[n]=i);       // tanani yashirish bitlari (build.py tartibi)
  const NM={male_casualsuit01:['Ko‘k ko‘ylak','👔'],male_casualsuit02:['Logo futbolka','👕'],male_casualsuit03:['Chiziqli ko‘ylak','👔'],
    male_casualsuit04:['Futbolka + jinsi','👕'],male_casualsuit05:['Kurtka + jinsi','🧥'],male_casualsuit06:['Oq futbolka','👕'],
    male_elegantsuit01:['Klassik kostyum','🤵'],male_worksuit01:['Kombinezon','👷'],female_casualsuit01:['Futbolka + jinsi','👚'],
    female_casualsuit02:['Futbolka + shorti','🩳'],female_elegantsuit01:['Ofis uslubi','👗'],female_sportsuit01:['Sport kostyum','🏃‍♀️'],
    shoes01:['Jigarrang tufli','👞'],shoes02:['Krossovka','👟'],shoes03:['Etik','🥾'],shoes04:['Qora tufli','👞'],shoes05:['Oq krossovka','👟'],shoes06:['Ko‘k krossovka','👟'],
    none:['Yo‘q','🚫'],fedora01:['Fedora','🎩'],fedora_cocked:['Qiyshiq fedora','🎩'],
    afro01:['Afro','🧑‍🦱'],bob01:['Bob','💇'],bob02:['Oq bob','💇‍♀️'],braid01:['O‘rim','👩'],long01:['Uzun','👱‍♀️'],ponytail01:['Dumcha','👧'],
    short01:['Qisqa 1','💇‍♂️'],short02:['Qisqa 2','💇‍♂️'],short03:['Qisqa 3','💇‍♂️'],short04:['Qisqa 4','💇‍♂️']};
  const HAIRS=['short01','short02','short03','short04','afro01','bob01','bob02','braid01','long01','ponytail01'];
  const it=k=>[k,NM[k][0],NM[k][1]];
  const CAT={
    outfit:{n:'Kiyim',ic:'👕',o:g=>(g==='f'?FO.concat(['male_casualsuit02','male_casualsuit04','male_casualsuit06','male_worksuit01']):MO).map(it)},
    shoes:{n:'Poyabzal',ic:'👟',o:()=>SH.map(it)},
    hat:{n:'Shlyapa',ic:'🎩',o:()=>['none','fedora01','fedora_cocked'].map(it)},
    hair:{n:'Soch',ic:'💇',o:g=>(g==='f'?['ponytail01','long01','bob01','bob02','braid01','afro01','short02','short04']:HAIRS).map(it)},
    hcol:{n:'Soch rangi',ic:'🎨',sw:1,o:()=>[['orig','Asl','#3b2a1e'],['black','Qora','#0f0d0c',25,.15,.07],['brown','Jigarrang','#4a2c17',24,.45,.2],
      ['chest','Kashtan','#6e3518',16,.6,.27],['blonde','Sariq','#d9b26a',40,.55,.58],['red','Malla','#a3401d',14,.68,.36],['gray','Oq-kul','#b9b9b9',30,.04,.66]]},
    skin:{n:'Teri rangi',ic:'🖐',sw:1,o:()=>[['orig','Asl','#e9c4a6'],['light','Oqish','#f3d6c4',[1.05,1.0,.98]],['wheat','Bug‘doy','#d3a47c',[.88,.7,.56]],
      ['tan','Qoramtir','#a8764f',[.76,.58,.45]],['dark','Qora','#5e3b27',[.48,.34,.27]]]},
    bg:{n:'Fon',ic:'🏛',sw:1,o:()=>[['gold','Oltin zal','radial-gradient(#7a5a1c,#1a1206)'],['night','Tungi shahar','radial-gradient(#26407a,#05070f)'],
      ['studio','Studiya','radial-gradient(#9a9a9a,#2a2a2a)'],['sunset','Shafaq','radial-gradient(#f2994a,#5b1d3a)'],['emerald','Zumrad','radial-gradient(#1f7a5a,#04150f)']]}
  };
  // PUBG lobbisidagidek harakatlar (CMU mocap → MakeHuman skeleti)
  const EMOTES=[['wave','👋','Salom'],['dance','💃','Raqs'],['salsa','🌶','Salsa'],['chicken','🐔','Tovuq raqsi'],['moonwalk','🌙','Moonwalk'],
    ['break','🤸','Breyk-dans'],['kazachok','🪗','Kazachok'],['party','🎉','Bayram'],['flex','💪','Kuch'],['happy','🥳','Xursand'],
    ['laugh','😂','Kulgi'],['cry','😭','Yig‘i'],['sad','😔','Xafa'],['boxing','🥊','Boks'],['kick','🦵','Zarba'],['backflip','🔄','Salto'],
    ['cartwheel','🤸‍♀️','G‘ildirak'],['jacks','⭐','Sakrash'],['bow','🙇','Ta‘zim'],['shrug','🤷','Bilmadim'],['taichi','🧘','Tay-chi']];
  const DEF={m:{outfit:'male_casualsuit04',shoes:'shoes02',hat:'none',hair:'short02'},f:{outfit:'female_casualsuit01',shoes:'shoes05',hat:'none',hair:'ponytail01'}};
  const opts=(s,g)=>CAT[s].o(g);
  const opt=(s,v,g)=>opts(s,g).find(x=>x[0]===v)||opts(s,g)[0];
  function fit(a){ a=a||{}; const g=a.g==='f'?'f':'m', o={g};
    for(const s in CAT){ const v=a[s], ok=opts(s,g).some(x=>x[0]===v); o[s]=ok?v:(DEF[g][s]||opts(s,g)[0][0]); } return o; }
  function hsl(r,g,b){ const mx=Math.max(r,g,b), mn=Math.min(r,g,b), l=(mx+mn)/2; let h=0,s=0;
    if(mx!==mn){ const d=mx-mn; s=l>.5?d/(2-mx-mn):d/(mx+mn); h=mx===r?(g-b)/d+(g<b?6:0):mx===g?(b-r)/d+2:(r-g)/d+4; h*=60; } return [h,s,l]; }
  function rgb(h,s,l){ const k=n=>(n+h/30)%12, a=s*Math.min(l,1-l), f=n=>l-a*Math.max(-1,Math.min(k(n)-3,9-k(n),1)); return [f(0),f(8),f(4)]; }
  const TEX=new Map();
  function recolor(mt,op){   // teksturani qayta bo'yash: ton/to'yinganlik almashadi, yorug'lik detali qoladi
    if(!mt.map) return;
    let t=TEX.get(mt);
    if(op[3]==null){ if(t){ mt.map=t.src; mt.needsUpdate=true; } return; }
    if(!t){ const img=mt.map.image, c=document.createElement('canvas'); c.width=img.width; c.height=img.height;
      const x=c.getContext('2d'); x.drawImage(img,0,0); const ct=new THREE.CanvasTexture(c); ct.flipY=mt.map.flipY; ct.encoding=THREE.sRGBEncoding;
      t={c,x,orig:x.getImageData(0,0,c.width,c.height),ct,src:mt.map,key:''}; TEX.set(mt,t); }
    if(t.key!==op[0]){ const o=t.orig.data, out=new ImageData(new Uint8ClampedArray(o),t.orig.width,t.orig.height), d=out.data;
      let sum=0,cnt=0; for(let i=0;i<o.length;i+=4){ if(o[i+3]<8) continue; sum+=hsl(o[i]/255,o[i+1]/255,o[i+2]/255)[2]; cnt++; }
      const mean=cnt?sum/cnt:.5;
      for(let i=0;i<o.length;i+=4){ if(o[i+3]<8) continue; const l=hsl(o[i]/255,o[i+1]/255,o[i+2]/255)[2];
        const c=rgb(op[3],op[4],Math.max(.02,Math.min(.97,op[5]+(l-mean)*.9))); d[i]=c[0]*255; d[i+1]=c[1]*255; d[i+2]=c[2]*255; }
      t.x.putImageData(out,0,0); t.ct.needsUpdate=true; t.key=op[0]; }
    mt.map=t.ct; mt.needsUpdate=true;
  }
  let R=null,S=null,CAM=null,cvs=null,raf=0,rot=0,tRot=0,zoom=0,tZoom=0,last=0,lw=0,lh=0,holder=null,cur=null,busy=null;
  const BASES={}, ITEMS={}, ANIMS={}, gl=()=>{ const L=new THREE.GLTFLoader(); L.setMeshoptDecoder(MeshoptDecoder); return L; };
  const get=u=>new Promise((ok,bad)=>gl().load(u,ok,undefined,bad));
  function fixMat(o){ const m=o.material, n=(m.name||'').toLowerCase(); o.castShadow=true; o.receiveShadow=true; o.frustumCulled=false;
    if(/eyebrow|eyelash/.test(n)||HAIRS.some(h=>n.indexOf(h)>=0)){ m.transparent=false; m.alphaTest=.5; m.side=THREE.DoubleSide; }
    else { m.transparent=false; m.alphaTest=0; }
    m.depthWrite=true; if(/body/.test(n)) m.roughness=.55; if(/low-poly|eye/.test(n)&&!/brow|lash/.test(n)) m.roughness=.08; m.needsUpdate=true; }
  function init(canvas){
    cvs=canvas; lw=lh=0; R=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});
    R.setPixelRatio(Math.min(2,window.devicePixelRatio||1)); R.outputEncoding=THREE.sRGBEncoding;
    R.toneMapping=THREE.ACESFilmicToneMapping; R.toneMappingExposure=1.05; R.physicallyCorrectLights=true;
    R.shadowMap.enabled=true; R.shadowMap.type=THREE.PCFSoftShadowMap;
    S=new THREE.Scene(); const pm=new THREE.PMREMGenerator(R); S.environment=pm.fromScene(new THREE.RoomEnvironment(),.04).texture; pm.dispose();
    const key=new THREE.DirectionalLight(0xfff1e0,2.3); key.position.set(2,4,3); key.castShadow=true; key.shadow.mapSize.set(2048,2048);
    Object.assign(key.shadow.camera,{left:-1.6,right:1.6,top:2.3,bottom:-.4}); key.shadow.bias=-.0005; key.shadow.radius=4; S.add(key);
    const rim=new THREE.DirectionalLight(0xffd59a,1.7); rim.position.set(-3,2.6,-3); S.add(rim);
    const fill=new THREE.DirectionalLight(0xbcd2ff,.6); fill.position.set(-3,1.5,2.5); S.add(fill);
    const gold=new THREE.MeshStandardMaterial({color:0xd4a33b,metalness:1,roughness:.28});
    const base=new THREE.Mesh(new THREE.CylinderGeometry(.9,.95,.08,72),new THREE.MeshStandardMaterial({color:0x17130d,metalness:.4,roughness:.35}));
    base.position.y=-.04; base.receiveShadow=true; S.add(base);
    const ring=new THREE.Mesh(new THREE.TorusGeometry(.93,.018,12,96),gold); ring.rotation.x=Math.PI/2; ring.position.y=-.002; S.add(ring);
    holder=new THREE.Group(); S.add(holder);
    CAM=new THREE.PerspectiveCamera(28,1,.05,50);
  }
  function size(){ const w=cvs.clientWidth||300, h=cvs.clientHeight||400; if(w===lw&&h===lh) return; lw=w; lh=h; R.setSize(w,h,false); CAM.aspect=w/h; CAM.updateProjectionMatrix(); }
  async function base(g){
    if(!BASES[g]) BASES[g]=get('/app/a/av_base_'+g+'.glb').then(x=>{ const root=x.scene, bones={}; let body=null;
      root.traverse(o=>{ if(o.isBone) bones[o.name]=o; if(o.isMesh){ fixMat(o); if(o.geometry.attributes._hide) body=o; } });
      return {g,root,bones,body,idx:body?body.geometry.index.array.slice():null,slots:{},mixer:new THREE.AnimationMixer(root),act:null,idle:null}; })
      .catch(e=>{ delete BASES[g]; throw e; });
    return BASES[g];
  }
  async function item(b,name){
    const k=b.g+'_'+name;
    if(!ITEMS[k]) ITEMS[k]=get('/app/a/av_'+k+'.glb').then(x=>{ const ms=[];
      x.scene.traverse(o=>{ if(o.isSkinnedMesh) ms.push(o); });
      return ms.map(m=>{ const sk=new THREE.Skeleton(m.skeleton.bones.map(bn=>b.bones[bn.name]),m.skeleton.boneInverses);
        const par=b.root.getObjectByName(m.parent.name)||b.root; const mesh=m; par.add(mesh); mesh.bind(sk,m.bindMatrix); fixMat(mesh); mesh.visible=false; return mesh; }); })
      .catch(e=>{ delete ITEMS[k]; throw e; });
    return ITEMS[k];
  }
  function hideBody(b,a){
    if(!b.body) return; const mask=(BIT[a.outfit]!=null?1<<BIT[a.outfit]:0)|(BIT[a.shoes]!=null?1<<BIT[a.shoes]:0);
    const h=b.body.geometry.attributes._hide.array, idx=b.idx, keep=[];
    for(let i=0;i<idx.length;i+=3){ const x=idx[i],y=idx[i+1],z=idx[i+2]; if((h[x]&mask)&&(h[y]&mask)&&(h[z]&mask)) continue; keep.push(x,y,z); }
    b.body.geometry.setIndex(keep);
  }
  async function anims(b){
    if(!ANIMS[b.g]) ANIMS[b.g]=get('/app/a/av_anims_'+b.g+'.glb').then(x=>x.animations).catch(e=>{ delete ANIMS[b.g]; throw e; });
    const list=await ANIMS[b.g];
    if(!b.idle){ const c=list.find(x=>x.name==='idle'); if(c){ b.idle=b.mixer.clipAction(c); b.idle.setLoop(THREE.LoopPingPong); b.idle.play(); }
      b.mixer.addEventListener('finished',e=>{ if(e.action!==b.idle&&b.idle){ b.idle.reset().play(); e.action.crossFadeTo(b.idle,.45,false); b.act=null; if(b.onEnd) b.onEnd(); } }); }
    return list;
  }
  async function apply(a){
    const b=await base(a.g);
    if(cur!==b){ if(cur) holder.remove(cur.root); holder.add(b.root); cur=b; }
    const want={outfit:a.outfit,shoes:a.shoes,hat:a.hat==='none'?null:a.hat,hair:a.hair};
    await Promise.all(Object.entries(want).map(async([s,n])=>{
      const ms=n?await item(b,n):[];
      if(b.slots[s]&&b.slots[s]!==ms) b.slots[s].forEach(m=>m.visible=false);
      ms.forEach(m=>m.visible=true); b.slots[s]=ms; }));
    hideBody(b,a);
    const hc=opt('hcol',a.hcol,a.g), tn=opt('skin',a.skin,a.g)[3]||[1,1,1];
    b.root.traverse(o=>{ if(!o.isMesh) return; const n=(o.material.name||'').toLowerCase();
      if(/eyebrow/.test(n)||HAIRS.some(h=>n.indexOf(h)>=0)) recolor(o.material,hc);
      else if(/body/.test(n)) o.material.color.setRGB(tn[0],tn[1],tn[2]); });
  }
  function frame(now){
    raf=requestAnimationFrame(frame); if(!R) return; size();
    const dt=Math.min(.05,(now-(last||now))/1000); last=now;
    rot+=(tRot-rot)*.12; zoom+=(tZoom-zoom)*.1; if(holder) holder.rotation.y=rot;
    if(cur) cur.mixer.update(dt);
    const y=1.0+zoom*.62, z=5.0-zoom*4.15, ly=.92+zoom*.7; CAM.position.set(0,y,z); CAM.lookAt(0,ly,0);
    R.render(S,CAM);
  }
  return {
    CAT, EMOTES, fit, opt, opts,
    async open(canvas,a){ await load(); if(R&&cvs!==canvas){ R.dispose(); R.forceContextLoss(); R=null; } if(!R) init(canvas);
      rot=tRot=0; last=0; await apply(a); cancelAnimationFrame(raf); raf=requestAnimationFrame(frame);
      anims(cur).catch(()=>{}); },
    set(a){ busy=(busy||Promise.resolve()).then(()=>apply(a)).then(()=>{ anims(cur).catch(()=>{}); }); return busy; },
    async emote(name,onEnd){ const b=cur; if(!b) return; const list=await anims(b); const c=list.find(x=>x.name===name); if(!c) return;
      const ac=b.mixer.clipAction(c); const from=b.act||b.idle; ac.reset(); ac.setLoop(THREE.LoopRepeat,c.duration<4?2:1); ac.clampWhenFinished=false;
      ac.play(); if(from&&from!==ac) from.crossFadeTo(ac,.35,false); b.act=ac; b.onEnd=onEnd; },
    turn(d){ tRot+=d; }, drag(d){ tRot+=d; rot+=d; }, zoom(){ tZoom=tZoom?0:1; return !!tZoom; },
    view(){ const a=((tRot%(Math.PI*2))+Math.PI*2)%(Math.PI*2); return ['Old tomoni','O‘ng yon','Orqa tomoni','Chap yon'][Math.round(a/(Math.PI/2))%4]; },
    close(){ cancelAnimationFrame(raf); raf=0; if(cur){ holder.remove(cur.root); cur.mixer.stopAllAction(); cur.idle=null; cur.act=null; }
      cur=null; if(R){ R.dispose(); R.forceContextLoss(); R=null; cvs=null; } tZoom=zoom=0; }
  };
})();

// ---- 🧍 Avatar studiyasi (Profil → 3D avatarim): kiyim almashtirish + harakatlar ----
function openAvatarStudio(d){
  let ov=document.getElementById('ast');
  if(!ov){ ov=document.createElement('div'); ov.id='ast'; document.body.appendChild(ov); }
  let a=AV3D.fit(d.avatar);
  const L=['outfit','shoes','hat'], Rr=['hair','hcol','skin'];
  const ico=s=>{ const o=AV3D.opt(s,a[s],a.g); return AV3D.CAT[s].sw?'<i class="asw" style="background:'+o[2]+'"></i>':'<span class="kv">'+o[2]+'</span>'; };
  const slotHtml=s=>'<div class="kslot" data-s="'+s+'"><span class="ki">'+AV3D.CAT[s].ic+'</span>'+ico(s)+'<span class="kn">'+AV3D.CAT[s].n+'</span></div>';
  ov.innerHTML='<div class="kst-in st-av bg-'+a.bg+'">'+
    '<div class="kst-hd"><div><div class="kst-name">🧍 '+esc(d.name)+(d.avatar_test?' <span class="avtest">TEST</span>':'')+'</div>'+
      '<div class="kst-sub">Realistik 3D avatar · ⭐ '+esc(d.level)+' · 💰 '+esc(d.money_fmt)+'$</div></div><span class="kst-x" id="astX">✕</span></div>'+
    '<div class="avg"><span data-g="m">👨 Erkak</span><span data-g="f">👩 Ayol</span></div>'+
    '<div class="kst-stage"><canvas id="astCv"></canvas>'+
      '<div class="kst-col l">'+L.map(slotHtml).join('')+'</div><div class="kst-col r">'+Rr.map(slotHtml).join('')+'</div>'+
      '<div class="kst-load" id="astLoad">⏳ 3D model yuklanmoqda…</div><div class="avbusy" id="astBusy">⏳</div></div>'+
    '<div class="kst-rot"><span id="astL">⟲</span><b id="astV">Old tomoni</b><span id="astR">⟳</span><span id="astZ">🔍</span><span id="astBg">🏛</span><span id="astE" class="ave">🕺</span></div>'+
    '<div class="kst-pick" id="astPick"><div class="kst-hint">🕺 — harakatlar (raqs, salto, salom…) · chekkadagi kataklar — kiyim, soch, teri · barmoq bilan aylantiring</div></div></div>';
  ov.className='kst show';
  const box=ov.querySelector('.kst-in'), cv=document.getElementById('astCv'), pick=document.getElementById('astPick'), vlab=document.getElementById('astV'),
    ldl=document.getElementById('astLoad'), bz=document.getElementById('astBusy');
  let saveT=0;
  const save=()=>{ d.avatar=Object.assign({},a); clearTimeout(saveT);
    saveT=setTimeout(()=>api('/app/api/avatar/save',{avatar:a}).then(r=>{ if(!r||r.error) toast('⚠️ Saqlanmadi'); }),600); };
  const refresh=()=>{ bz.style.display='flex'; return AV3D.set(a).then(()=>{ bz.style.display='none'; })
    .catch(()=>{ bz.style.display='none'; toast('⚠️ Model yuklanmadi'); }); };
  const close=()=>{ ov.className='kst'; AV3D.close(); };
  document.getElementById('astX').onclick=close;
  ov.onclick=e=>{ if(e.target===ov) close(); };
  const upd=()=>{ vlab.textContent=AV3D.view(); };
  document.getElementById('astL').onclick=()=>{ AV3D.turn(-Math.PI/2); setTimeout(upd,10); };
  document.getElementById('astR').onclick=()=>{ AV3D.turn(Math.PI/2); setTimeout(upd,10); };
  document.getElementById('astZ').onclick=e=>{ e.currentTarget.classList.toggle('on',AV3D.zoom()); };
  document.getElementById('astBg').onclick=()=>showPick('bg');
  document.getElementById('astE').onclick=()=>showEmotes();
  let dragX=null;
  cv.addEventListener('pointerdown',e=>{ dragX=e.clientX; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener('pointermove',e=>{ if(dragX==null) return; AV3D.drag((e.clientX-dragX)*.012); dragX=e.clientX; upd(); });
  cv.addEventListener('pointerup',()=>{ dragX=null; });
  const paintSlots=()=>{ ov.querySelectorAll('.kslot').forEach(el=>{ const s=el.dataset.s; el.outerHTML=slotHtml(s); });
    ov.querySelectorAll('.kslot').forEach(el=>el.onclick=()=>showPick(el.dataset.s)); };
  const paintG=()=>ov.querySelectorAll('.avg span').forEach(x=>x.classList.toggle('on',x.dataset.g===a.g));
  ov.querySelectorAll('.avg span').forEach(el=>el.onclick=()=>{ if(a.g===el.dataset.g) return;
    const keep={hcol:a.hcol,skin:a.skin,bg:a.bg}; a=AV3D.fit(Object.assign({g:el.dataset.g},keep)); paintG(); paintSlots(); pick.innerHTML='';
    ldl.style.display='flex'; ldl.textContent='⏳ 3D model yuklanmoqda…';
    AV3D.set(a).then(()=>{ ldl.style.display='none'; }).catch(()=>{ ldl.textContent='⚠️ Model yuklanmadi'; }); save(); });
  paintG();
  function showPick(s){
    ov.querySelectorAll('.kslot,.kst-rot span').forEach(x=>x.classList.remove('on'));
    const sl=ov.querySelector('.kslot[data-s="'+s+'"]'); if(sl) sl.classList.add('on');
    const cat=AV3D.CAT[s];
    pick.innerHTML='<div class="kst-pt">'+cat.ic+' '+cat.n+'</div><div class="kst-opts">'+
      AV3D.opts(s,a.g).map(o=>'<div class="kopt'+(a[s]===o[0]?' on':'')+'" data-v="'+o[0]+'">'+(cat.sw?'<span class="asw big" style="background:'+o[2]+'"></span>':'<span>'+o[2]+'</span>')+'<small>'+o[1]+'</small></div>').join('')+'</div>';
    pick.querySelectorAll('.kopt').forEach(el=>el.onclick=()=>{
      a[s]=el.dataset.v; pick.querySelectorAll('.kopt').forEach(x=>x.classList.toggle('on',x===el));
      if(s==='bg') box.className='kst-in st-av bg-'+a.bg; else { paintSlots(); ov.querySelector('.kslot[data-s="'+s+'"]').classList.add('on'); refresh(); }
      save();
    });
  }
  function showEmotes(){
    ov.querySelectorAll('.kslot,.kst-rot span').forEach(x=>x.classList.remove('on')); document.getElementById('astE').classList.add('on');
    pick.innerHTML='<div class="kst-pt">🕺 Harakatlar</div><div class="kst-opts emo">'+
      AV3D.EMOTES.map(e=>'<div class="kopt" data-v="'+e[0]+'"><span>'+e[1]+'</span><small>'+e[2]+'</small></div>').join('')+'</div>';
    pick.querySelectorAll('.kopt').forEach(el=>el.onclick=()=>{
      pick.querySelectorAll('.kopt').forEach(x=>x.classList.toggle('on',x===el));
      AV3D.emote(el.dataset.v,()=>el.classList.remove('on')).catch(()=>toast('⚠️ Harakat yuklanmadi'));
    });
  }
  ov.querySelectorAll('.kslot').forEach(el=>el.onclick=()=>showPick(el.dataset.s));
  AV3D.open(cv,a).then(()=>{ ldl.style.display='none'; })
    .catch(()=>{ ldl.textContent='⚠️ 3D yuklanmadi. Internetni tekshiring.'; });
}

// ---- 3D "Royal" samolyot — umumiy chizgich (Crash va Kamikaze) ----
function planeKit(ctx,dpr){
  //: qizil korpus + oltin bezaklar, toj belgisi (mesh + perspektiva + yoritish) ----
  const RED=[214,22,40], GOLD=[255,196,58], BLACK=[26,20,24], GLASS=[18,26,44];
  const P3=(function(){
    const F=[], W=[], N=12;
    // [x, radius, y-siljish, rang]
    const rings=[[1.8,0,0],[1.6,.17,0],[1.47,.4,0],[1.34,.43,0],[1.0,.42,.01],[.55,.4,.02],[.05,.36,.04],[-.5,.26,.07],[-1.0,.15,.12],[-1.32,.07,.16]];
    const segCol=[GOLD,GOLD,RED,RED,RED,RED,RED,RED,RED];
    const R=rings.map(r=>Array.from({length:N},(_,i)=>{ const a=i/N*Math.PI*2; return [r[0],Math.cos(a)*r[1]+r[2],Math.sin(a)*r[1]]; }));
    for(let k=0;k<R.length-1;k++) for(let i=0;i<N;i++){ const j=(i+1)%N;
      let c=segCol[k];
      if(k===2) c=GOLD;                                   // kapot oldidagi oltin halqa
      if(k>=3 && k<=6 && (i===3||i===8)) c=GOLD;          // yon tomondagi oltin chaqmoq chizig'i
      if(k>=4 && k<=6 && (i===5||i===6)) c=[150,14,28];   // pastki qorin — to'qroq
      F.push({v:[R[k][i],R[k+1][i],R[k+1][j],R[k][j]],c,sp:c===GOLD?2:1}); }
    F.push({v:R[R.length-1].slice().reverse(),c:BLACK});
    // kabina: qoramtir shisha + oltin ramka
    W.push({v:[[.62,.37,0],[.38,.58,-.17],[.0,.56,-.19],[-.24,.38,-.17],[-.24,.38,.17],[.0,.56,.19],[.38,.58,.17]],c:GLASS,sp:3,frame:1,bias:.04});
    // past joylashgan qanotlar: qizil + oltin old qirra + oltin uch
    for(const sg of [1,-1]){
      W.push({v:[[.5,-.2,.2*sg],[-.32,-.2,.2*sg],[-.44,-.1,1.6*sg],[-.12,-.1,1.6*sg]],c:RED,sp:4});
      W.push({v:[[.5,-.198,.2*sg],[.4,-.196,.2*sg],[-.1,-.108,1.42*sg],[-.04,-.11,1.42*sg]],c:GOLD,sp:2,bias:.02});
      W.push({v:[[-.04,-.11,1.42*sg],[-.41,-.11,1.42*sg],[-.45,-.1,1.64*sg],[-.12,-.1,1.64*sg]],c:GOLD,sp:2,bias:.02});
      // dum stabilizatori
      W.push({v:[[-.98,.06,.05*sg],[-1.32,.08,.05*sg],[-1.44,.11,.72*sg],[-1.2,.11,.72*sg]],c:RED,sp:4});
      W.push({v:[[-1.2,.11,.72*sg],[-1.44,.11,.72*sg],[-1.42,.11,.6*sg],[-1.18,.11,.6*sg]],c:GOLD,sp:2,bias:.02});
    }
    // vertikal dum: qora, oltin hoshiya, ikkala tomonda oltin toj
    const fin=[[-.82,.16,0],[-1.36,.18,0],[-1.5,.86,0],[-1.2,.86,0]];
    W.push({v:fin,c:BLACK,sp:1,edge:GOLD});
    const crown=(cx,cy,sz,z,n)=>({v:[[cx-sz,cy-sz*.55,z],[cx+sz,cy-sz*.55,z],[cx+sz*1.1,cy+sz*.6,z],[cx+sz*.5,cy+sz*.05,z],[cx,cy+sz*.75,z],[cx-sz*.5,cy+sz*.05,z],[cx-sz*1.1,cy+sz*.6,z]],
      c:GOLD,sp:2,n:[0,0,n],bias:.08});
    for(const sg of [1,-1]){
      W.push(crown(-1.24,.5,.13,.012*sg,sg));
      // korpus yonidagi qora panel + toj
      W.push({v:[[.6,-.12,.425*sg],[1.14,-.12,.43*sg],[1.14,.19,.425*sg],[.6,.19,.415*sg]],c:BLACK,sp:1,n:[0,0,sg],bias:.05,edge:GOLD});
      W.push(crown(.87,.04,.14,.44*sg,sg));
    }
    return {F,W};
  })();
  const LIGHT=(()=>{ const l=[-.35,.75,.55], n=Math.hypot(...l); return l.map(x=>x/n); })();
  function rot(v,roll,pitch,yaw,tilt){
    let [x,y,z]=v, c,s,t;
    c=Math.cos(roll); s=Math.sin(roll); t=y*c-z*s; z=y*s+z*c; y=t;          // x o'qi atrofida (krен)
    c=Math.cos(pitch); s=Math.sin(pitch); t=x*c-y*s; y=x*s+y*c; x=t;        // z o'qi atrofida (burun yuqoriga)
    c=Math.cos(yaw); s=Math.sin(yaw); t=x*c+z*s; z=-x*s+z*c; x=t;           // y o'qi atrofida
    c=Math.cos(tilt); s=Math.sin(tilt); t=y*c-z*s; z=y*s+z*c; y=t;          // kamera biroz yuqoridan
    return [x,y,z];
  }
  const rgb=(c,a)=>'rgba('+c[0]+','+c[1]+','+c[2]+','+(a==null?1:a)+')';
  function drawPlane(x,y,ang,s,roll){
    roll=roll||0; const now=performance.now();
    const pitch=-ang, yaw=0.5, tilt=0.32, D=6, R3=v=>rot(v,roll,pitch,yaw,tilt);
    const proj=p=>{ const f=D/(D-p[2]); return [x+p[0]*s*f, y-p[1]*s*f, p[2]]; };
    const polys=[];
    const add=(f,closed)=>{
      const vv=f.v.map(R3), pp=vv.map(proj);
      let n;
      if(f.n){ n=R3(f.n); if(n[2]<=0.02) return; }      // bir tomonlama bezak (toj/panel)
      else { const a=vv[0],b=vv[1],c=vv[2];
        n=[(b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]),(b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]),(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])]; }
      const nl=Math.hypot(...n)||1; n=n.map(q=>q/nl);
      if(closed){ let ar=0; for(let i=0;i<pp.length;i++){ const p1=pp[i],p2=pp[(i+1)%pp.length]; ar+=p1[0]*p2[1]-p2[0]*p1[1]; } if(ar>0) return; }
      let d=n[0]*LIGHT[0]+n[1]*LIGHT[1]+n[2]*LIGHT[2]; if(!closed) d=Math.abs(d);
      const lum=Math.max(f.c===GOLD?.62:0,(f.sp===4?.28+.6*Math.max(0,d):.3+.8*Math.max(0,d)));
      const spec=f.sp===4?Math.pow(Math.max(0,d),30)*60:f.sp===3?Math.pow(Math.max(0,d),4)*160:f.sp===2?Math.pow(Math.max(0,d),5)*110:f.sp?Math.pow(Math.max(0,d),18)*120:0;
      polys.push({pp,z:vv.reduce((m,v)=>m+v[2],0)/vv.length+(f.bias||0),col:f.c.map(q=>Math.min(255,Math.round(q*lum+spec))),f});
    };
    P3.F.forEach(f=>add(f,true)); P3.W.forEach(f=>add(f,false));
    polys.sort((a,b)=>a.z-b.z);
    // iliq oltin nur
    const gl=ctx.createRadialGradient(x,y,0,x,y,s*2.4); gl.addColorStop(0,'rgba(255,150,40,.32)'); gl.addColorStop(1,'rgba(255,120,40,0)');
    ctx.fillStyle=gl; ctx.beginPath(); ctx.arc(x,y,s*2.4,0,7); ctx.fill();
    // olovli iz (dumdan orqaga)
    const tail=proj(R3([-1.35,.1,0])), fk=Math.sin(now/45);
    for(const [len,w,c0] of [[2.6+.4*fk,.34,'rgba(255,90,20,'],[2.0+.3*fk,.2,'rgba(255,170,40,'],[1.3+.2*fk,.09,'rgba(255,245,190,']]){
      const back=proj(R3([-1.35-len,.1,0]));
      const g=ctx.createLinearGradient(back[0],back[1],tail[0],tail[1]); g.addColorStop(0,c0+'0)'); g.addColorStop(1,c0+'.9)');
      ctx.strokeStyle=g; ctx.lineCap='round'; ctx.lineWidth=s*w; ctx.beginPath(); ctx.moveTo(tail[0],tail[1]); ctx.lineTo(back[0],back[1]); ctx.stroke(); }
    for(const p of polys){
      ctx.beginPath(); ctx.moveTo(p.pp[0][0],p.pp[0][1]); for(let i=1;i<p.pp.length;i++) ctx.lineTo(p.pp[i][0],p.pp[i][1]); ctx.closePath();
      ctx.fillStyle=rgb(p.col); ctx.fill();
      if(p.f.frame||p.f.edge){ ctx.strokeStyle=rgb(GOLD); ctx.lineWidth=Math.max(1,s*.06); ctx.lineJoin='round'; ctx.stroke(); }
      else { ctx.strokeStyle=rgb(p.col,.9); ctx.lineWidth=.6; ctx.stroke(); }
      if(p.f.frame){ // shisha yaltirashi
        const a=p.pp[1],b=p.pp[2]; ctx.strokeStyle='rgba(200,230,255,.55)'; ctx.lineWidth=Math.max(1,s*.05);
        ctx.beginPath(); ctx.moveTo(a[0]+(b[0]-a[0])*.2,a[1]+(b[1]-a[1])*.2+s*.06); ctx.lineTo(a[0]+(b[0]-a[0])*.7,a[1]+(b[1]-a[1])*.7+s*.06); ctx.stroke(); }
    }
    // pervanel: oltin aylanish diski + 3 ta qora parrak (oltin uchli) + oltin konus
    const h=proj(R3([1.66,0,0])), pa=now/18, PR=1.0;
    const r1=proj(R3([1.66,PR,0])), r2=proj(R3([1.66,0,PR]));
    const ea=Math.hypot(r2[0]-h[0],r2[1]-h[1]), eb=Math.hypot(r1[0]-h[0],r1[1]-h[1]), et=Math.atan2(r1[1]-h[1],r1[0]-h[0])-Math.PI/2;
    ctx.save();
    const dg=ctx.createRadialGradient(h[0],h[1],0,h[0],h[1],Math.max(ea,eb));
    dg.addColorStop(0,'rgba(255,215,110,.05)'); dg.addColorStop(.75,'rgba(255,200,80,.22)'); dg.addColorStop(1,'rgba(255,220,120,.45)');
    ctx.fillStyle=dg; ctx.beginPath(); ctx.ellipse(h[0],h[1],Math.max(2,ea),Math.max(2,eb),et,0,7); ctx.fill();
    ctx.strokeStyle='rgba(255,215,120,.5)'; ctx.lineWidth=1;
    for(const k of [.55,.8]){ ctx.beginPath(); ctx.ellipse(h[0],h[1],Math.max(1,ea*k),Math.max(1,eb*k),et,0,7); ctx.stroke(); }
    for(let k=0;k<3;k++){ const a=pa+k*Math.PI*2/3;
      const mid=proj(R3([1.66,Math.cos(a)*PR*.78,Math.sin(a)*PR*.78])), tp=proj(R3([1.66,Math.cos(a)*PR,Math.sin(a)*PR]));
      ctx.lineCap='round'; ctx.strokeStyle='rgba(20,16,20,.8)'; ctx.lineWidth=s*.13;
      ctx.beginPath(); ctx.moveTo(h[0],h[1]); ctx.lineTo(mid[0],mid[1]); ctx.stroke();
      ctx.strokeStyle='rgba(255,200,70,.9)'; ctx.beginPath(); ctx.moveTo(mid[0],mid[1]); ctx.lineTo(tp[0],tp[1]); ctx.stroke(); }
    const tipP=proj(R3([2.0,0,0])), sg=ctx.createRadialGradient(h[0]-s*.06,h[1]-s*.08,0,h[0],h[1],s*.24);
    sg.addColorStop(0,'#fff6cf'); sg.addColorStop(.5,'#ffc93a'); sg.addColorStop(1,'#8a5a0c');
    ctx.fillStyle=sg; ctx.beginPath(); ctx.arc(h[0],h[1],s*.2,0,7); ctx.fill();
    ctx.beginPath(); ctx.moveTo(h[0]+(tipP[1]-h[1])*.45,h[1]-(tipP[0]-h[0])*.45); ctx.lineTo(tipP[0],tipP[1]); ctx.lineTo(h[0]-(tipP[1]-h[1])*.45,h[1]+(tipP[0]-h[0])*.45); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  return drawPlane;
}

// ---- CRASH (Aviator — bashorat qilib bo'lmaydi) ----
function histClass(v){ return v>=10?'hi':(v>=2?'mid':'lo'); }
function renderHist(el){ if(!el) return; el.innerHTML=(window.CHIST||[]).map(v=>'<span class="hc '+histClass(v)+'">'+v.toFixed(2)+'x</span>').join(''); }
function initCrash(){
  if(window.CR) window.CR.stop();
  const btn=document.getElementById('cbtn'), bet=document.getElementById('cbet'),
        mx=document.getElementById('mx'), box=document.getElementById('cbox'), cv=document.getElementById('ccanvas'),
        note=document.getElementById('cnote'), chist=document.getElementById('chist'),
        minus=document.getElementById('cminus'), plus=document.getElementById('cplus'), cr=document.getElementById('s-crash'),
        wait=document.getElementById('cwait'), cnt=document.getElementById('ccnt'), barf=document.getElementById('cbarf'),
        plist=document.getElementById('plist'), pcount=document.getElementById('pcount'), ppot=document.getElementById('ppot'),
        cround=document.getElementById('cround'), conline=document.getElementById('conline');
  if(!btn) return;
  renderHist(chist);
  const ctx=cv.getContext('2d'); const dpr=window.devicePixelRatio||1;
  // server holati (raund/bosqich/vaqt) — hamma uchun bir xil
  const S={round:0, phase:'bet', el:0, at:performance.now(), growth:0.12, crash:null, betDur:7, me:null, queued:null, players:[], total:0, pot:0};
  let alive=true, raf=0, timer=0, busy=false, crashAt=0, tip=[0,0,0], lastTip=null, roundSeen=0;
  const stars=Array.from({length:80},()=>({x:Math.random(),y:Math.random(),z:.25+Math.random()*.75,tw:Math.random()*6}));
  const puffs=[], sparks=[];
  function phaseEl(){ return S.el+(performance.now()-S.at)/1000; }
  function curMult(){ return S.phase==='fly'?Math.exp(S.growth*phaseEl()):1; }
  function size(){ const w=box.clientWidth,h=box.clientHeight; if(cv.width!==w*dpr||cv.height!==h*dpr){cv.width=w*dpr;cv.height=h*dpr;} }
  function betVal(){ return Math.max(0,parseInt(bet.value)||0); }
  function stepOf(v){ return v<100?10:v<1000?50:v<10000?500:5000; }
  function setBet(v){ bet.value=Math.max(10,Math.min(Math.round(v),1000000)); paintBtn(); }
  minus.onclick=()=>{ const v=betVal(); setBet(v-stepOf(v-1)); };
  plus.onclick=()=>{ const v=betVal(); setBet(v+stepOf(v)); };
  bet.oninput=paintBtn;
  cr.querySelectorAll('.quick .q').forEach(q=>q.onclick=()=>{ const v=q.dataset.v, b=betVal();
    if(v==='half') setBet(b/2); else if(v==='dbl') setBet(b*2); else if(v==='max') setBet(window.BAL||10); else setBet(+v); });

  // ---- tugma holatlari ----
  function myOpen(){ return S.me && S.me.cash==null; }
  function paintBtn(){
    const b=betVal(); btn.disabled=busy;
    if(S.phase==='bet' && S.me){ btn.className='bigbet stop'; btn.innerHTML='BEKOR QILISH<small>'+fmtMoney(S.me.bet)+'$ · raund boshlanmoqda</small>'; return; }
    if(S.phase==='fly' && myOpen()){ btn.className='bigbet cash'; btn.innerHTML='CASH OUT<small>'+fmtMoney(Math.floor(S.me.bet*curMult()))+'$</small>'; return; }
    if(S.queued){ btn.className='bigbet stop'; btn.innerHTML='BEKOR QILISH<small>'+fmtMoney(S.queued)+'$ · keyingi raundga</small>'; return; }
    if(S.phase==='bet'){ btn.className='bigbet'; btn.innerHTML='BET<small>'+fmtMoney(b)+'$</small>'; return; }
    btn.className='bigbet next'; btn.innerHTML='KEYINGI RAUNDGA<small>'+fmtMoney(b)+'$</small>';
  }
  btn.onclick=()=>{
    if(busy) return;
    let path, body={};
    if(S.phase==='fly' && myOpen()) path='/app/api/crash/cashout';
    else if((S.phase==='bet' && S.me) || S.queued) path='/app/api/crash/cancel';
    else { path='/app/api/crash/bet'; body={bet:betVal()}; }
    busy=true; paintBtn();
    api(path,body).then(r=>{
      busy=false;
      if(r.balance!=null) setBal(r.balance);
      if(!r.ok||r.error){ toast(errText(r.error,r.min)); }
      else if(r.result==='placed'){ S.me={bet:r.bet,cash:null,win:0}; haptic('success'); SND.play('chip'); toast('✅ Tikildi: '+fmtMoney(r.bet)+'$'); }
      else if(r.result==='queued'){ S.queued=r.bet; SND.play('chip'); toast('⏳ Keyingi raundga tikildi: '+fmtMoney(r.bet)+'$'); }
      else if(r.result==='cancelled'){ if(S.phase==='bet') S.me=null; S.queued=null; toast('↩️ Bekor qilindi, pul qaytdi'); }
      else if(r.result==='win'){ S.me&&(S.me.cash=r.multiplier,S.me.win=r.win); haptic('success'); SND.play('cash');
        note.textContent='✅ +'+fmtMoney(r.win)+'$ · '+r.multiplier.toFixed(2)+'x da yechdingiz'; }
      else if(r.result==='lose'){ haptic('error'); note.textContent='💥 Kech qoldingiz!'; }
      paintBtn(); poll(true);
    }).catch(()=>{ busy=false; paintBtn(); });
  };

  // ---- o'yinchilar ro'yxati ----
  const COLS=['#22d3ee','#e879f9','#ffd24a','#a3e635','#fb923c','#a78bfa','#f472b6'];
  function renderPlayers(){
    pcount.textContent=S.total; ppot.textContent=fmtMoney(S.pot); conline.textContent=S.total;
    if(!S.players.length){ plist._h=''; plist.innerHTML='<div class="pempty">Hali hech kim tikmadi — birinchi bo‘ling! 🚀</div>'; return; }
    const html=S.players.map(p=>{
      const ini=esc((p.name||'?').replace('@','').charAt(0).toUpperCase()), col=COLS[(p.name||'').length%COLS.length];
      let kf, w, cls='';
      if(p.cash!=null){ kf='<span class="kf">'+p.cash.toFixed(2)+'x</span>'; w='<span class="kf">+'+fmtMoney(p.win)+'$</span>'; cls='win'; }
      else if(S.phase==='crash'){ kf='<span class="kf l">💥</span>'; w='<span class="kf l">−'+fmtMoney(p.bet)+'$</span>'; cls='lost'; }
      else { kf='<span class="kf w">'+(S.phase==='fly'?'✈︎':'⏳')+'</span>'; w='<span class="kf w">—</span>'; }
      return '<div class="prow '+cls+(p.me?' mine':'')+'"><span class="pn"><i style="background:'+col+'">'+ini+'</i><em>'+esc(p.name)+(p.me?' (siz)':'')+'</em></span>'+
        '<span>'+fmtMoney(p.bet)+'$</span>'+kf+w+'</div>';
    }).join('');
    if(html!==plist._h){ plist._h=html; plist.innerHTML=html; }
  }

  // ---- serverdan holat (hamma uchun bir xil koeffitsiyent) ----
  let inflight=false;
  function poll(now){
    clearTimeout(timer);
    if(!alive) return;
    if(!inflight){ inflight=true; const t0=performance.now();
      api('/app/api/crash/state',{}).then(s=>{ inflight=false; if(!alive||!s||!s.ok) return;
        const lat=(performance.now()-t0)/2000, prev=S.phase, prevRound=S.round;
        S.growth=s.growth||S.growth; S.round=s.round; S.players=s.players||[]; S.total=s.total||0; S.pot=s.pot||0;
        S.me=s.me||null; S.queued=s.queued||null;
        if(s.history){ window.CHIST=s.history; }
        const est=s.elapsed+lat;
        if(s.phase!==prev || s.round!==prevRound || Math.abs(est-phaseEl())>0.12){ S.el=est; S.at=performance.now(); }
        S.phase=s.phase;
        if(s.phase==='bet') S.betDur=(s.countdown||0)+s.elapsed||7;
        if(s.phase==='crash' && (prev!=='crash' || s.round!==prevRound)){ S.crash=s.crash; onCrash(prev==='fly'); }
        if(s.phase==='fly' && prev!=='fly'){ puffs.length=0; lastTip=null; if(cr.classList.contains('on')) SND.play('takeoff'); note.textContent='🚀 Uchyapti… o‘z vaqtida yeching!'; }
        if(s.phase==='bet' && (prev!=='bet' || s.round!==prevRound)){ note.textContent='Hamma uchun bitta raund · qachon uchib ketishi sir 🎯'; }
        if(s.balance!=null && !busy) setBal(s.balance);
        cround.textContent=s.round; renderPlayers(); paintBtn();
      }).catch(()=>{ inflight=false; });
    }
    timer=setTimeout(poll, cr.classList.contains('on')?250:2000);
  }
  function onCrash(seen){
    crashAt=performance.now(); renderHist(chist); if(cr.classList.contains('on')) SND.play('boom');
    if(seen) for(let i=0;i<46;i++){ const a=Math.random()*Math.PI*2, v=(1+Math.random()*4)*dpr;
      sparks.push({x:tip[0],y:tip[1],vx:Math.cos(a)*v,vy:Math.sin(a)*v,life:1,c:i%3?'#ff4d6a':'#ffd24a'}); }
    if(S.me && S.me.cash==null){ haptic('error'); note.textContent='💥 Uchib ketdi! −'+fmtMoney(S.me.bet)+'$'; }
    else if(!S.me) note.textContent='💥 '+(S.crash||1).toFixed(2)+'x da uchib ketdi';
  }

  // ---- chizish ----
  function sunburst(W,H,now,speed){
    const ox=W*0.08,oy=H*1.05,R=Math.hypot(W,H)*1.4,rot=now/1000*speed,n=18;
    for(let i=0;i<n;i++){ const a=rot+i*(Math.PI*2/n), a2=a+Math.PI/n*0.62;
      ctx.beginPath(); ctx.moveTo(ox,oy); ctx.lineTo(ox+Math.cos(a)*R,oy+Math.sin(a)*R); ctx.lineTo(ox+Math.cos(a2)*R,oy+Math.sin(a2)*R); ctx.closePath();
      ctx.fillStyle=i%2?'rgba(150,110,235,.10)':'rgba(90,60,170,.08)'; ctx.fill(); }
  }
  let starOff=0, gridOff=0, lastNow=performance.now();
  function background(W,H,now,dt){
    const fly=S.phase==='fly', sp=fly?Math.min(0.08+0.06*Math.log(curMult()+1),0.5):0.015;
    starOff+=dt*sp; gridOff+=dt*(fly?60+40*Math.log(curMult()):6)*dpr;
    sunburst(W,H,now,fly?0.22:0.06);
    // parallaks yulduzlar (chapga oqadi — samolyot o'ngga uchayotgandek)
    for(const s of stars){ const x=((s.x-starOff*s.z)%1+1)%1*W, y=s.y*H*0.85, a=.25+.5*Math.abs(Math.sin(now/700+s.tw));
      ctx.fillStyle='rgba(255,255,255,'+(a*s.z).toFixed(3)+')';
      if(fly && s.z>.7){ ctx.fillRect(x,y,(6+18*s.z)*dpr*Math.min(sp*6,2),1.2*dpr); } else { ctx.beginPath(); ctx.arc(x,y,s.z*1.4*dpr,0,7); ctx.fill(); } }
    // pastki perspektiv to'r
    ctx.strokeStyle='rgba(139,92,246,.18)'; ctx.lineWidth=1*dpr;
    const gy=H-18*dpr, step=34*dpr;
    for(let x=-(gridOff%step);x<W;x+=step){ ctx.beginPath(); ctx.moveTo(x,gy); ctx.lineTo(x-14*dpr,H); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(0,gy); ctx.lineTo(W,gy); ctx.stroke();
  }
  const drawPlane=planeKit(ctx,dpr);   // 3D "Royal" samolyot (umumiy: Crash + Kamikaze)
  // 3D animatsiya: chayqalish (krен) + har 7 s da "bochka" aylanishi
  function flyRoll(t,now){
    let r=Math.sin(now/420)*0.42+Math.sin(now/170)*0.08;
    const cyc=t%7; if(t>2 && cyc>5 && cyc<6.1){ const u=(cyc-5)/1.1; r+=u*u*(3-2*u)*Math.PI*2; }
    return r;
  }
  // egri chiziq: uchi chapdan o'ngga siljiydi (8 s), keyin o'ngda chayqalib turadi
  function curve(W,H,t,now){
    const pl=14*dpr, pr=46*dpr, base=H-22*dpr, top=40*dpr, T=Math.max(t,8), m=Math.exp(S.growth*t), maxM=Math.max(1.9,m*1.14), N=60;
    const X=tau=>pl+(W-pl-pr)*(tau/T), Y=mm=>base-(base-top)*((mm-1)/(maxM-1));
    const line=new Path2D(); line.moveTo(X(0),Y(1));
    let x=X(0),y=Y(1),x0=x,y0=y;
    for(let i=1;i<=N;i++){ const tau=t*i/N; x0=x; y0=y; x=X(tau); y=Y(Math.exp(S.growth*tau)); line.lineTo(x,y); }
    // chalg'ituvchi chayqalish
    const wob=Math.min(1,t/1.5), wy=(Math.sin(now/260)*5+Math.sin(now/97)*2)*dpr*wob, wx=Math.sin(now/410)*4*dpr*wob;
    const tx=x+wx, ty=y+wy; line.lineTo(tx,ty);
    const fill=new Path2D(line); fill.lineTo(tx,base); fill.lineTo(X(0),base); fill.closePath();
    const g=ctx.createLinearGradient(0,top,0,base); g.addColorStop(0,'rgba(255,60,90,.5)'); g.addColorStop(1,'rgba(255,60,90,.03)');
    ctx.fillStyle=g; ctx.fill(fill);
    ctx.strokeStyle='#ff3b6b'; ctx.lineWidth=4*dpr; ctx.lineJoin='round'; ctx.shadowColor='#ff3b6b'; ctx.shadowBlur=14*dpr; ctx.stroke(line); ctx.shadowBlur=0;
    return [tx,ty,Math.atan2(y-y0,(x-x0)||1)+Math.sin(now/330)*0.14*wob];
  }
  function particles(dt){
    for(let i=puffs.length-1;i>=0;i--){ const p=puffs[i]; p.life-=dt*1.4; p.x-=dt*40*dpr; p.r+=dt*10*dpr;
      if(p.life<=0){ puffs.splice(i,1); continue; }
      ctx.fillStyle='rgba(255,'+Math.round(120+p.life*100)+',40,'+(p.life*.35).toFixed(3)+')'; ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,7); ctx.fill(); }
    for(let i=sparks.length-1;i>=0;i--){ const p=sparks[i]; p.life-=dt*1.1; p.x+=p.vx; p.y+=p.vy; p.vy+=0.05*dpr; p.vx*=.98;
      if(p.life<=0){ sparks.splice(i,1); continue; }
      ctx.globalAlpha=p.life; ctx.fillStyle=p.c; ctx.beginPath(); ctx.arc(p.x,p.y,2.2*dpr*p.life+0.5,0,7); ctx.fill(); ctx.globalAlpha=1; }
  }
  function frame(){
    if(!alive) return;
    raf=requestAnimationFrame(frame);
    if(!cr.classList.contains('on')) return;
    const now=performance.now(), dt=Math.min(0.05,(now-lastNow)/1000); lastNow=now;
    size(); const W=cv.width,H=cv.height; ctx.clearRect(0,0,W,H);
    background(W,H,now,dt);
    if(S.phase==='bet'){
      box.classList.remove('bust'); mx.classList.remove('bust','fly'); wait.classList.add('on');
      const cd=Math.max(0,S.betDur-phaseEl());
      const cdi=Math.ceil(cd); if(cdi<=3 && cdi>0 && cdi!==frame._cd){ frame._cd=cdi; SND.play('tick'); } if(cd<=0) frame._cd=0;
      cnt.textContent=cd.toFixed(1); barf.style.width=Math.min(100,cd/S.betDur*100)+'%'; mx.textContent='';
      // kutish: samolyot pastda tebranib turadi
      drawPlane(48*dpr+Math.sin(now/600)*3*dpr, H-46*dpr+Math.sin(now/300)*3*dpr, -0.22+Math.sin(now/500)*0.06, 17*dpr, Math.sin(now/700)*0.3);
    } else if(S.phase==='fly'){
      wait.classList.remove('on'); box.classList.remove('bust'); mx.classList.remove('bust'); mx.classList.add('fly');
      const t=phaseEl(), m=Math.exp(S.growth*t);
      mx.textContent=m.toFixed(2)+'x';
      tip=curve(W,H,t,now);
      if(!lastTip || Math.hypot(tip[0]-lastTip[0],tip[1]-lastTip[1])>5*dpr){ puffs.push({x:tip[0]-18*dpr,y:tip[1]+4*dpr,r:3*dpr,life:1}); lastTip=tip.slice(); }
      particles(dt);
      drawPlane(tip[0],tip[1],tip[2],22*dpr,flyRoll(t,now));
      if(myOpen()) btn.querySelector('small') && (btn.querySelector('small').textContent=fmtMoney(Math.floor(S.me.bet*m))+'$');
    } else {
      wait.classList.remove('on'); box.classList.add('bust'); mx.classList.remove('fly'); mx.classList.add('bust');
      mx.textContent=(S.crash||1).toFixed(2)+'x';
      particles(dt);
      // samolyot o'ng-yuqoriga uchib ketadi
      const k=(now-crashAt)/1000;
      if(k<1.2 && tip[0]) drawPlane(tip[0]+k*k*W*0.9, tip[1]-k*k*H*0.8, -0.6-k*0.8, 19*dpr*(1+k*.6), k*k*16);
    }
  }
  window.CR={stop(){ alive=false; cancelAnimationFrame(raf); clearTimeout(timer); }, poke(){ poll(true); }};
  paintBtn(); renderPlayers(); poll(true); raf=requestAnimationFrame(frame);
}

// ---- 💬 CHAT (ID orqali shaxsiy suhbat) ----
const CHERR={not_found:'🔎 Bunday foydalanuvchi topilmadi (botni ishlatgan bo‘lishi kerak)',self:'🙃 Bu sizning ID ingiz',
  blocked:'🚫 Bloklangan — xabar yuborib bo‘lmaydi',rate:'⏳ Juda tez yozyapsiz, biroz kuting',empty:'✍️ Xabar bo‘sh',
  long:'📏 Xabar juda uzun (1000 belgigacha)',disabled:'🌐 Web app o‘chirilgan',user:'⚠️ Foydalanuvchi xato'};
const PAIRERR={not_found:'🔎 Foydalanuvchi topilmadi',self:'🙃 O‘zingizga taklif yubora olmaysiz',no_gender:'⚧ Avval botda jinsingizni tanlang (/start)',
  target_gender:'⚧ U hali jinsini tanlamagan',same_gender:'🚫 Faqat qarama-qarshi jins bilan juft bo‘lish mumkin',
  has_pair:'💞 Sizda allaqachon juft bor',target_pair:'💞 Uning allaqachon jufti bor',blocked:'🚫 Bloklangan',
  already:'⏳ Bu odamga taklif allaqachon yuborilgan',undeliverable:'📭 Yetkazilmadi — u botni bloklagan',bot:'⚠️ Bot band, qayta urining',disabled:'🌐 Web app o‘chirilgan'};
function pairPropose(q,btn){
  if(btn) btn.disabled=true;
  return api('/app/api/pair/propose',{q:String(q)}).then(r=>{ if(btn) btn.disabled=false;
    if(r.result==='sent'){ toast('💌 Juftlik taklifi '+r.name+' ga yuborildi'); haptic('success'); }
    else toast(PAIRERR[r.error]||'⚠️ Xatolik'); return r; }).catch(()=>{ if(btn) btn.disabled=false; toast('⚠️ Aloqa xatosi'); });
}
function chAva(id,name){ const i=esc(((name||'?').trim().charAt(0)||'?').toUpperCase());
  return '<span class="chava">'+i+'<img alt="" src="/app/avatar/'+esc(id)+'" onerror="this.remove()"></span>'; }
function peerInfo(u){
  const G={male:'👦 Yigit',female:'👧 Qiz'};
  return '<div class="chips">'+(u.gender?'<span class="chip">'+G[u.gender]+'</span>':'')+(u.age!=null?'<span class="chip">🎂 '+esc(u.age)+'</span>':'')+
    '<span class="chip">💰 '+esc(u.money_fmt)+'$</span><span class="chip">🏆 '+(u.rank?'#'+esc(u.rank):'👑')+'</span>'+
    '<span class="chip">⭐ '+esc(u.level)+'</span>'+(u.profession?'<span class="chip">💼 '+esc(u.profession)+'</span>':'')+
    '<span class="chip">'+(u.has_pair?'💞 Jufti bor':'💍 Jufti yo‘q')+'</span>'+(u.divorces?'<span class="chip">💔 Ajrashgan: '+esc(u.divorces)+'</span>':'')+'</div>';
}
function initChat(d){
  const sec=document.getElementById('s-chat'); if(!sec) return;
  const q=document.getElementById('chQ'), go=document.getElementById('chGo'), res=document.getElementById('chRes'), list=document.getElementById('chList');
  if(window.CHL) clearInterval(window.CHL);
  const find=()=>{ const v=q.value.trim(); if(!v) return; go.disabled=true;
    api('/app/api/chat/find',{q:v}).then(r=>{ go.disabled=false;
      if(r.result!=='found'){ res.innerHTML='<div class="hsub" style="margin-top:10px">'+(CHERR[r.error]||'⚠️ Xatolik')+'</div>'; return; }
      const u=r.user, canPair=!u.has_pair&&!(d.randpair&&d.randpair.has_pair)&&u.gender&&d.randpair&&d.randpair.gender&&u.gender!==d.randpair.gender;
      res.innerHTML='<div class="chfound">'+chAva(u.id,u.name)+'<div class="chf-m"><b>'+esc(u.name)+'</b>'+(u.username?' <span class="hsub">@'+esc(u.username)+'</span>':'')+
        '<div class="hsub">ID '+esc(u.id)+'</div></div></div>'+peerInfo(u)+
        '<div class="chbtns"><button class="btn go" id="chW">💬 Yozish</button>'+(canPair?'<button class="btn" id="chP">💍 Juftlik taklifi</button>':'')+'</div>';
      document.getElementById('chW').onclick=()=>openChat(u.id,u.name,d);
      const pb=document.getElementById('chP'); if(pb) pb.onclick=()=>pairPropose(u.id,pb);
    }).catch(()=>{ go.disabled=false; toast('⚠️ Aloqa xatosi'); }); };
  go.onclick=find; q.onkeydown=e=>{ if(e.key==='Enter') find(); };
  const load=()=>{ if(!sec.classList.contains('on')&&list.dataset.ok) return;
    api('/app/api/chat/list',{}).then(r=>{ if(!r.chats) return; list.dataset.ok=1; setChatBadge(r.unread);
      list.innerHTML=r.chats.length?r.chats.map(c=>'<div class="chrow'+(c.unread?' un':'')+'" data-id="'+c.id+'" data-n="'+esc(c.name)+'">'+chAva(c.id,c.name)+
        '<div class="chr-m"><div class="chr-t"><b>'+esc(c.name)+'</b><span class="hsub">'+esc(c.at)+'</span></div>'+
        '<div class="chr-l">'+(c.mine?'Siz: ':'')+esc(c.last)+'</div></div>'+(c.unread?'<span class="chbadge">'+c.unread+'</span>':'')+'</div>').join('')
        :'<div class="card full"><div class="center">Hali suhbat yo‘q.<br><span class="hsub">Yuqoridan ID yoki @username orqali toping</span></div></div>';
      list.querySelectorAll('.chrow').forEach(el=>el.onclick=()=>openChat(+el.dataset.id,el.dataset.n,d));
    }).catch(()=>{}); };
  load(); window.CHL=setInterval(load,8000); window.CHLOAD=load;
  setChatBadge(d.chat_unread||0);
  const m=/chat=(\d+)/.exec(location.hash||''); if(m && !window.CHOPENED){ window.CHOPENED=1; setTimeout(()=>{ setTab('chat'); openChat(+m[1],'',d); },50); }
}
function setChatBadge(n){ const t=document.querySelector('.tab[data-k="chat"]'); if(!t) return;
  let b=t.querySelector('.tbadge'); if(n>0){ if(!b){ b=document.createElement('span'); b.className='tbadge'; t.appendChild(b); } b.textContent=n>99?'99+':n; } else if(b) b.remove(); }
function openChat(peer,name,d){
  let ov=document.getElementById('chv');
  if(!ov){ ov=document.createElement('div'); ov.id='chv'; document.body.appendChild(ov); }
  if(window.CHP) clearInterval(window.CHP);
  ov.className='chv show';
  ov.innerHTML='<div class="chv-in"><div class="chv-hd"><span class="chv-b" id="chvB">‹</span>'+chAva(peer,name)+
    '<div class="chv-n"><b id="chvN">'+esc(name||('ID '+peer))+'</b><div class="hsub" id="chvS">ID '+esc(peer)+'</div></div>'+
    '<span class="chv-i" id="chvP" title="Juftlik taklifi">💍</span><span class="chv-i" id="chvM" title="Ma’lumot">ⓘ</span></div>'+
    '<div class="chv-info" id="chvInfo"></div><div class="chv-msgs" id="chvL"><div class="hsub center">Yuklanmoqda…</div></div>'+
    '<div class="chv-ft"><textarea id="chvT" rows="1" maxlength="1000" placeholder="Xabar yozing…"></textarea><button class="btn go" id="chvS2">➤</button></div></div>';
  const L=document.getElementById('chvL'), T=document.getElementById('chvT'), S=document.getElementById('chvS2'), info=document.getElementById('chvInfo');
  let last=0, seen=0, peerData=null, first=true;
  const close=()=>{ ov.className='chv'; clearInterval(window.CHP); window.CHP=0; if(window.CHLOAD) window.CHLOAD(); };
  document.getElementById('chvB').onclick=close;
  const bubble=m=>'<div class="msg'+(m.mine?' me':'')+'" data-id="'+m.id+'"><div class="mt">'+esc(m.text).replace(/\n/g,'<br>')+'</div>'+
    '<div class="mm">'+esc(m.at)+(m.mine?'<span class="tick">✓</span>':'')+'</div></div>';
  function paintSeen(){ L.querySelectorAll('.msg.me').forEach(el=>{ const t=el.querySelector('.tick'); if(t) t.textContent=(+el.dataset.id<=seen)?'✓✓':'✓'; }); }
  function add(ms){ if(!ms.length) return; const near=L.scrollHeight-L.scrollTop-L.clientHeight<80;
    if(first){ L.innerHTML=''; } const em=L.querySelector('.chempty'); if(em) em.remove(); ms.forEach(m=>{ if(m.id>last){ L.insertAdjacentHTML('beforeend',bubble(m)); last=m.id; } });
    if(near||first) L.scrollTop=L.scrollHeight; }
  function drawInfo(){ if(!peerData) return; const u=peerData;
    document.getElementById('chvN').textContent=u.name; document.getElementById('chvS').textContent=(u.username?'@'+u.username+' · ':'')+'ID '+u.id;
    info.innerHTML=peerInfo(u)+'<div class="chbtns"><button class="btn" id="chvBl">'+(u.blocked_by_me?'✅ Blokdan chiqarish':'🚫 Bloklash')+'</button></div>';
    document.getElementById('chvBl').onclick=()=>api('/app/api/chat/block',{with:peer,on:!u.blocked_by_me}).then(r=>{
      if(r.result){ u.blocked_by_me=r.result==='blocked'; toast(u.blocked_by_me?'🚫 Bloklandi':'✅ Blokdan chiqarildi'); drawInfo(); } }); }
  document.getElementById('chvM').onclick=()=>{ info.classList.toggle('on'); };
  document.getElementById('chvP').onclick=e=>pairPropose(peer,e.currentTarget);
  function poll(){ api('/app/api/chat/history',{with:peer,after:last}).then(r=>{
      if(r.error){ L.innerHTML='<div class="hsub center">'+(CHERR[r.error]||'⚠️ Xatolik')+'</div>'; return; }
      if(r.peer){ peerData=r.peer; drawInfo(); }
      if(first&&!r.msgs.length) L.innerHTML='<div class="hsub center chempty">👋 Suhbatni boshlang</div>';
      add(r.msgs); first=false; seen=r.seen; paintSeen(); setChatBadge(r.unread);
    }).catch(()=>{}); }
  poll(); window.CHP=setInterval(()=>{ if(document.getElementById('chv').classList.contains('show')&&!document.hidden) poll(); },2500);
  const send=()=>{ const v=T.value.trim(); if(!v||S.disabled) return; S.disabled=true;
    api('/app/api/chat/send',{to:peer,text:v}).then(r=>{ S.disabled=false;
      if(r.result==='sent'){ T.value=''; T.style.height=''; if(first){ L.innerHTML=''; first=false; } add([r.msg]); paintSeen(); SND.ui&&SND.ui('select'); }
      else toast(CHERR[r.error]||'⚠️ Xatolik'); }).catch(()=>{ S.disabled=false; toast('⚠️ Aloqa xatosi'); }); };
  S.onclick=send;
  T.onkeydown=e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); send(); } };
  T.oninput=()=>{ T.style.height='auto'; T.style.height=Math.min(110,T.scrollHeight)+'px'; };
}

// ---- 🛩 KAMIKAZE ----
function initKami(){
  if(window.KM) window.KM.stop();
  const cv=document.getElementById('kcanvas'); if(!cv) return;
  const box=document.getElementById('kbox'), sec=document.getElementById('s-kami'),
        btn=document.getElementById('kbtn'), bet=document.getElementById('kbet'), note=document.getElementById('knote'),
        msg=document.getElementById('kmsg');
  const ctx=cv.getContext('2d'), dpr=Math.min(2,window.devicePixelRatio||1), drawPlane=planeKit(ctx,dpr);
  const COLS=12, ROWS=5;
  let ladder=Array.from({length:COLS},(_,i)=>Math.floor(0.92*Math.pow(1.25,i+1)*100)/100);
  document.getElementById('kmax').textContent=Math.floor(ladder[COLS-1]);
  // holat
  let playing=false, busy=false, step=0, lane=2, curBet=0, alive=true, raf=0, camX=0;
  let plane={x:0,y:0,fx:0,fy:0,t0:0,dur:0,dead:false,deadT:0,gone:false};
  let shots=[];                 // [{col,row,t0,hit}] — o'q uchishi
  let passed={};                // col -> {row, shot}
  const sparks=[], splashes=[], puffs=[];
  const waves=Array.from({length:46},(_,i)=>({x:Math.random(),y:Math.random(),l:.03+Math.random()*.06,p:Math.random()*6}));
  const smokeS=Array.from({length:3},(_,i)=>({x:.15+i*.32+Math.random()*.08,s:.6+Math.random()*.5}));
  function size(){ const w=box.clientWidth,h=box.clientHeight; if(cv.width!==w*dpr||cv.height!==h*dpr){cv.width=w*dpr;cv.height=h*dpr;} }
  function geo(){ const W=cv.width,H=cv.height, top=58*dpr, bot=H-12*dpr, T=Math.min((bot-top)/ROWS, W/5.6);
    return {W,H,T,top:top+((bot-top)-T*ROWS)/2, x0:T*1.1}; }
  function cellXY(col,row,g){ return [g.x0+(col+0.5)*g.T, g.top+(row+0.5)*g.T]; }  // dunyo koordinatasi; col=-1 — start
  function shipX(g){ return g.x0+(COLS+0.9)*g.T; }
  // ---- tugmalar ----
  function betVal(){ return Math.max(0,parseInt(bet.value)||0); }
  function stepOf(v){ return v<100?10:v<1000?50:v<10000?500:5000; }
  function setBet(v){ if(playing) return; bet.value=Math.max(10,Math.min(Math.round(v),1000000)); paint(); }
  document.getElementById('kminus').onclick=()=>{ const v=betVal(); setBet(v-stepOf(v-1)); };
  document.getElementById('kplus').onclick=()=>{ const v=betVal(); setBet(v+stepOf(v)); };
  bet.oninput=paint;
  sec.querySelectorAll('.kq .q').forEach(q=>q.onclick=()=>{ const v=q.dataset.v,b=betVal();
    if(v==='half') setBet(b/2); else if(v==='dbl') setBet(b*2); else setBet(+v); });
  function paint(){
    btn.disabled=busy || (playing && step===0);
    if(playing){ btn.className='btn cash'; btn.style.flex='1';
      btn.textContent=step?('💰 YECHIB OLISH · '+fmtMoney(Math.floor(curBet*ladder[step-1]))+'$'):'👆 Katak tanlang';
    } else { btn.className='btn go'; btn.style.flex='1'; btn.textContent='🛩 O‘YNASH · '+fmtMoney(betVal())+'$'; }
  }
  function flash(html,bad,ms){ msg.innerHTML=html; msg.className='kmsg on'+(bad?' bad':''); clearTimeout(msg._t);
    msg._t=setTimeout(()=>msg.className='kmsg'+(bad?' bad':''),ms||1300); }
  function reset(){ step=0; lane=2; passed={}; shots=[]; camX=0; const g=geo();
    const [x,y]=cellXY(-1,lane,g); Object.assign(plane,{x,y,fx:x,fy:y,t0:0,dur:0,dead:false,gone:false}); }
  // ochiq qolgan o'yinni davom ettirish (server holati bo'yicha)
  function resume(v){
    ladder=v.ladder||ladder; curBet=v.bet; playing=true; reset(); passed={};
    (v.passed||[]).forEach(p=>{ passed[p.col]={row:p.row,shot:p.shot}; lane=p.row; });
    step=v.step; const g=geo(), [x,y]=cellXY(step-1,lane,g); Object.assign(plane,{x,y,fx:x,fy:y,tx:null});
    note.innerHTML=step?('♻️ O‘yin davom etmoqda · hozir <b>x'+v.multiplier.toFixed(2)+'</b> · keyingisi <b>x'+ladder[step].toFixed(2)+'</b>')
      :('♻️ O‘yin davom etmoqda · <b>x'+ladder[0].toFixed(2)+'</b>');
    bet.value=v.bet; paint();
  }
  function resync(){ // aloqa uzilsa: server holatiga qaytamiz
    api('/app/api/kami/state',{}).then(r=>{ if(r.balance!=null) setBal(r.balance);
      if(r.active&&r.game) resume(r.game); else { playing=false; plane.tx=null; reset(); paint(); } }).catch(()=>{});
  }
  function moveTo(col,row){ const g=geo(); const [x,y]=cellXY(col,row,g);
    plane.fx=plane.x; plane.fy=plane.y; plane.tx=x; plane.ty=y; plane.t0=performance.now(); plane.dur=480; lane=row; }
  btn.onclick=()=>{
    if(busy) return;
    if(!playing){
      busy=true; paint();
      api('/app/api/kami/start',{bet:betVal()}).then(r=>{ busy=false;
        if(!r.ok||r.error){ toast(errText(r.error,r.min)); paint(); return; }
        if(r.resumed){ setBal(r.balance); resume(r.game); toast('♻️ Oldingi o‘yin davom ettirildi'); return; }
        setBal(r.balance); ladder=r.ladder||ladder; curBet=r.bet; playing=true; reset(); SND.play('chip');
        note.innerHTML='Keyingi ustundan katak tanlang · <b>x'+ladder[0].toFixed(2)+'</b>'; haptic('success'); paint();
      }).catch(()=>{ busy=false; paint(); resync(); });
      return;
    }
    if(!step) return;
    busy=true; paint();
    api('/app/api/kami/cashout',{}).then(r=>{ busy=false;
      if(r.result==='cashed'){ setBal(r.balance); playing=false; haptic('success'); SND.play('cash');
        flash('+'+fmtMoney(r.win)+'$<small>x'+r.multiplier.toFixed(2)+' da yechdingiz</small>');
        note.innerHTML='✅ Yutuq: <b>+'+fmtMoney(r.win)+'$</b>'; burst(plane.x,plane.y,'#ffd24a',40); }
      else { toast(errText(r.error)); resync(); } paint();
    }).catch(()=>{ busy=false; paint(); resync(); });
  };
  // katak tanlash
  cv.addEventListener('pointerdown',e=>{
    if(!playing||busy||plane.dead) return;
    const rc=cv.getBoundingClientRect(), px=(e.clientX-rc.left)*dpr+camX, py=(e.clientY-rc.top)*dpr, g=geo();
    const [cx]=cellXY(step,0,g);
    if(Math.abs(px-cx)>g.T*0.55) return;
    const row=Math.floor((py-g.top)/g.T); if(row<0||row>=ROWS) return;
    busy=true; paint(); moveTo(step,row); SND.play('click'); SND.play('whoosh');
    api('/app/api/kami/step',{row:row}).then(r=>{
      if(!r.ok||r.error){ busy=false; toast(errText(r.error)); paint(); resync(); return; }
      const col=r.col; shots.push({col,row:r.shot,t0:performance.now()+220,hit:r.result==='lose'}); setTimeout(()=>SND.play('cannon'),220);
      setTimeout(()=>{
        busy=false;
        if(r.result==='lose'){ playing=false; plane.dead=true; plane.deadT=performance.now(); passed[col]={row,shot:r.shot};
          haptic('error'); flash('💥 URILDINGIZ!<small>−'+fmtMoney(curBet)+'$</small>',true,1700);
          note.innerHTML='Dushman o‘qi tegdi. Yana urinib ko‘ring!'; setBal(r.balance); }
        else { passed[col]={row,shot:r.shot}; step=r.step||COLS; setBal(r.balance);
          if(r.result==='win_full'){ playing=false; plane.kamikaze=performance.now();
            flash('🎯 KAMIKAZE!<small>+'+fmtMoney(r.win)+'$ · x'+r.multiplier.toFixed(2)+'</small>',false,2400);
            note.innerHTML='🏆 Kemaga yetdingiz! <b>+'+fmtMoney(r.win)+'$</b>'; haptic('success'); }
          else { note.innerHTML='Zo‘r! Hozir: <b>x'+r.multiplier.toFixed(2)+'</b> · keyingisi <b>x'+ladder[step].toFixed(2)+'</b>'; haptic('success'); } }
        paint();
      },720);
    }).catch(()=>{ busy=false; paint(); resync(); });
  });
  function burst(x,y,c,n){ for(let i=0;i<n;i++){ const a=Math.random()*Math.PI*2,v=(1+Math.random()*4)*dpr;
    sparks.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v-1.5*dpr,life:1,c:Math.random()<.5?c:'#ffffff'}); } }
  // ---- chizish ----
  function sea(g,now){
    const {W,H}=g, gr=ctx.createLinearGradient(0,0,0,H);
    gr.addColorStop(0,'#07152e'); gr.addColorStop(.18,'#0c2a4f'); gr.addColorStop(1,'#04203a'); ctx.fillStyle=gr; ctx.fillRect(0,0,W,H);
    // ufq: yonayotgan kemalar va orollar (parallaks)
    const hy=46*dpr, par=camX*0.25;
    ctx.fillStyle='#0a1d33';
    for(let i=0;i<4;i++){ const x=((i*W*0.42-par)%(W*1.6)+W*1.6)%(W*1.6)-W*0.2;
      ctx.beginPath(); ctx.ellipse(x,hy,W*0.16,10*dpr,0,Math.PI,0); ctx.fill(); }
    for(const sm of smokeS){ const x=((sm.x*W*1.4-par)%(W*1.4)+W*1.4)%(W*1.4)-W*0.1;
      ctx.fillStyle='#1b2433'; ctx.fillRect(x-14*dpr*sm.s,hy-6*dpr,28*dpr*sm.s,6*dpr); ctx.fillRect(x-4*dpr*sm.s,hy-13*dpr*sm.s,7*dpr*sm.s,8*dpr*sm.s);
      const fl=.6+.4*Math.sin(now/90+sm.x*20);
      const fg=ctx.createRadialGradient(x,hy-8*dpr,0,x,hy-8*dpr,22*dpr*sm.s); fg.addColorStop(0,'rgba(255,170,60,'+(.75*fl)+')'); fg.addColorStop(1,'rgba(255,80,20,0)');
      ctx.fillStyle=fg; ctx.beginPath(); ctx.arc(x,hy-8*dpr,22*dpr*sm.s,0,7); ctx.fill();
      for(let k=0;k<5;k++){ const t=((now/2600+k/5)%1); ctx.fillStyle='rgba(70,70,80,'+(.35*(1-t))+')';
        ctx.beginPath(); ctx.arc(x+t*26*dpr,hy-14*dpr-t*36*dpr,(5+t*14)*dpr*sm.s,0,7); ctx.fill(); } }
    ctx.fillStyle='rgba(255,140,60,.10)'; ctx.fillRect(0,hy-2*dpr,W,4*dpr);
    // to'lqinlar
    ctx.strokeStyle='rgba(150,210,255,.16)'; ctx.lineWidth=1.4*dpr;
    ctx.beginPath();
    for(const w of waves){ const x=((w.x*W*1.3-camX*.8+now*0.012*dpr)%(W*1.3)+W*1.3)%(W*1.3)-W*.15, y=hy+8*dpr+w.y*(H-hy);
      ctx.moveTo(x,y); ctx.quadraticCurveTo(x+w.l*W*.5,y-3*dpr*Math.sin(now/400+w.p),x+w.l*W,y); }
    ctx.stroke();
  }
  function rr(x,y,w,h,r){ ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
  function board(g,now){
    const {T}=g, pad=T*0.09;
    for(let c=-1;c<COLS;c++){
      const x=g.x0+c*g.T; if(x-camX>g.W+T||x-camX<-T*2) continue;
      if(c===-1){ // start: aviatashuvchi palubasi
        ctx.fillStyle='#22324a'; rr(x+pad,g.top+pad,T-2*pad,T*ROWS-2*pad,10*dpr); ctx.fill();
        ctx.strokeStyle='rgba(255,214,110,.35)'; ctx.setLineDash([6*dpr,6*dpr]); ctx.beginPath(); ctx.moveTo(x+T/2,g.top+pad*2); ctx.lineTo(x+T/2,g.top+T*ROWS-pad*2); ctx.stroke(); ctx.setLineDash([]);
        continue; }
      const next=playing&&c===step&&!busy, done=c<step||passed[c];
      // koeffitsiyent yorlig'i
      ctx.font='800 '+(11*dpr)+'px -apple-system,Segoe UI,Roboto,sans-serif'; ctx.textAlign='center';
      ctx.fillStyle=next?'#ffd24a':done?'#7ee08a':'rgba(220,235,255,.55)';
      ctx.fillText('x'+ladder[c].toFixed(2),x+T/2,g.top-8*dpr);
      for(let r=0;r<ROWS;r++){
        const y=g.top+r*T, p=passed[c];
        let fill='rgba(120,190,255,.07)', stroke='rgba(150,210,255,.22)';
        if(next){ const pu=.5+.5*Math.sin(now/260); fill='rgba(255,210,74,'+(.10+.10*pu)+')'; stroke='rgba(255,214,110,'+(.55+.4*pu)+')'; }
        if(p && p.row===r){ fill='rgba(80,220,120,.22)'; stroke='rgba(120,240,150,.8)'; }
        if(p && p.shot===r){ fill='rgba(255,70,70,.22)'; stroke='rgba(255,110,110,.7)'; }
        ctx.fillStyle=fill; rr(x+pad,y+pad,T-2*pad,T-2*pad,9*dpr); ctx.fill();
        ctx.strokeStyle=stroke; ctx.lineWidth=(next?2:1.2)*dpr; ctx.stroke();
        if(p && p.shot===r){ ctx.font=(T*.38)+'px sans-serif'; ctx.textBaseline='middle'; ctx.fillText('💥',x+T/2,y+T/2+1); ctx.textBaseline='alphabetic'; }
      }
    }
  }
  function battleship(g,now){
    const x=shipX(g), cy=g.top+g.T*ROWS/2, L=g.T*1.25, Hh=g.T*ROWS*0.95;
    if(x-L-camX>g.W) return {x,cy};
    ctx.save(); ctx.translate(x,cy+Math.sin(now/700)*2*dpr);
    // korpus (yuqoridan ko'rinish, burni chapga)
    const hg=ctx.createLinearGradient(-L/2,0,L/2,0); hg.addColorStop(0,'#5d6a7c'); hg.addColorStop(.5,'#8794a6'); hg.addColorStop(1,'#4a5566');
    ctx.fillStyle=hg; ctx.beginPath(); ctx.moveTo(0,-Hh/2); ctx.quadraticCurveTo(L/2,-Hh/3,L/2,0); ctx.quadraticCurveTo(L/2,Hh/3,0,Hh/2);
    ctx.quadraticCurveTo(-L/2,Hh/3,-L/2,0); ctx.quadraticCurveTo(-L/2,-Hh/3,0,-Hh/2); ctx.fill();
    ctx.strokeStyle='rgba(255,255,255,.25)'; ctx.lineWidth=1.5*dpr; ctx.stroke();
    ctx.fillStyle='#3b4554'; rr(-L*.22,-Hh*.18,L*.44,Hh*.36,6*dpr); ctx.fill();
    // to'plar
    for(const ty of [-.32,-.12,.12,.32]){ ctx.fillStyle='#2b333f'; ctx.beginPath(); ctx.arc(-L*.08,ty*Hh,L*.13,0,7); ctx.fill();
      ctx.strokeStyle='#1d232c'; ctx.lineWidth=4*dpr; ctx.beginPath(); ctx.moveTo(-L*.08,ty*Hh); ctx.lineTo(-L*.42,ty*Hh); ctx.stroke(); }
    ctx.fillStyle='#ff3b5c'; ctx.beginPath(); ctx.arc(L*.15,0,4*dpr*(0.7+0.3*Math.sin(now/200)),0,7); ctx.fill();
    ctx.restore();
    return {x,cy};
  }
  let lastDraw=0;
  function frame(){
    if(!alive) return; raf=requestAnimationFrame(frame);
    if(!sec.classList.contains('on')||document.hidden) return;
    const now=performance.now();
    const calm=!playing&&!busy&&!plane.dead&&!plane.kamikaze&&plane.tx==null&&!shots.length&&!sparks.length&&!splashes.length&&!puffs.length;
    if(calm && now-lastDraw<66) return;           // kutish paytida ~15 fps — zaif telefonlarda qizib, qotib qolmasin
    lastDraw=now;
    size(); const g=geo();
    // kamera: keyingi ustun ekranning ~45% ida
    const target=Math.max(0, g.x0+(step+0.5)*g.T - g.W*0.45);
    camX+=(target-camX)*0.08;
    if(!playing && !plane.dead && !plane.kamikaze && step===0){ const [x,y]=cellXY(-1,lane,g); plane.x=x; plane.y=y; plane.tx=undefined; }
    else if(playing && !busy && !plane.dead && plane.tx==null){ const [x,y]=cellXY(step-1,lane,g); plane.x=x; plane.y=y; }  // o'lcham o'zgarsa/davom ettirilsa ham joyida
    ctx.clearRect(0,0,g.W,g.H); sea(g,now); ctx.save(); ctx.translate(-camX,0); board(g,now); const sh=battleship(g,now);
    // samolyot harakati
    let px=plane.x, py=plane.y, ang=0;
    if(plane.tx!=null){ const u=Math.min(1,(now-plane.t0)/plane.dur), e=u<.5?2*u*u:1-Math.pow(-2*u+2,2)/2;
      const gx=plane.tx, gy=plane.ty;
      px=plane.fx+(gx-plane.fx)*e; py=plane.fy+(gy-plane.fy)*e - Math.sin(Math.PI*u)*g.T*0.25;
      ang=Math.atan2(gy-plane.fy, (gx-plane.fx)||1)*0.6;
      if(u>=1){ plane.x=gx; plane.y=gy; plane.fx=gx; plane.fy=gy; plane.tx=null; }
    }
    // kemaga sho'ng'ish (to'liq g'alaba)
    if(plane.kamikaze){ const u=Math.min(1,(now-plane.kamikaze)/700);
      px=plane.x+(sh.x-plane.x)*u*u; py=plane.y+(sh.cy-plane.y)*u*u; ang=Math.atan2(sh.cy-plane.y,sh.x-plane.x);
      if(u>=1 && !plane.boom){ plane.boom=true; SND.play('bigboom'); burst(sh.x,sh.cy,'#ff8a3a',90); burst(sh.x,sh.cy,'#ffd24a',60); }
      if(u>=1) px=-9999; }
    // o'qlar
    for(const s of shots){ const u=(now-s.t0)/520; if(u<0) continue;
      const [tx,ty]=cellXY(s.col,s.row,g), sx=sh.x-g.T*0.5, sy=sh.cy+(s.row-2)*g.T*0.3;
      if(u<1){ const x=sx+(tx-sx)*u, y=sy+(ty-sy)*u - Math.sin(Math.PI*u)*g.T*1.2;
        ctx.fillStyle='#ffe08a'; ctx.shadowColor='#ff8a3a'; ctx.shadowBlur=14*dpr; ctx.beginPath(); ctx.arc(x,y,4*dpr,0,7); ctx.fill(); ctx.shadowBlur=0;
        if(u<0.12){ ctx.fillStyle='rgba(255,200,90,'+(1-u/0.12)+')'; ctx.beginPath(); ctx.arc(sx,sy,12*dpr,0,7); ctx.fill(); } }
      else if(!s.done){ s.done=true; splashes.push({x:tx,y:ty,t0:now}); SND.play(s.hit?'explode':'splash'); burst(tx,ty,s.hit?'#ff5a3a':'#9fe8ff',s.hit?70:26); } }
    for(let i=shots.length-1;i>=0;i--) if(shots[i].done) shots.splice(i,1);
    for(let i=splashes.length-1;i>=0;i--){ const sp=splashes[i], u=(now-sp.t0)/700; if(u>1){ splashes.splice(i,1); continue; }
      ctx.strokeStyle='rgba(200,240,255,'+(1-u)+')'; ctx.lineWidth=3*dpr*(1-u);
      ctx.beginPath(); ctx.arc(sp.x,sp.y,g.T*0.15+u*g.T*0.45,0,7); ctx.stroke(); }
    // tutun izi
    if(playing && Math.random()<0.5) puffs.push({x:px-18*dpr,y:py+2*dpr,r:3*dpr,life:1});
    for(let i=puffs.length-1;i>=0;i--){ const p=puffs[i]; p.life-=0.025; p.r+=0.25*dpr; p.x-=0.4*dpr; if(p.life<=0){ puffs.splice(i,1); continue; }
      ctx.fillStyle='rgba(255,'+Math.round(120+p.life*100)+',60,'+(p.life*.3)+')'; ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,7); ctx.fill(); }
    // samolyot
    if(!plane.dead){ drawPlane(px,py,ang,Math.min(15*dpr,g.T*0.24),Math.sin(now/380)*0.35); }
    else { const u=(now-plane.deadT)/900; if(u<1){ drawPlane(px+u*20*dpr,py+u*u*g.T,0.6+u*2,Math.min(15*dpr,g.T*0.24)*(1-u*.4),u*10); } }
    // uchqunlar
    for(let i=sparks.length-1;i>=0;i--){ const p=sparks[i]; p.life-=0.02; p.x+=p.vx; p.y+=p.vy; p.vy+=0.08*dpr; p.vx*=.98;
      if(p.life<=0){ sparks.splice(i,1); continue; }
      ctx.globalAlpha=p.life; ctx.fillStyle=p.c; ctx.beginPath(); ctx.arc(p.x,p.y,2.4*dpr*p.life+.5,0,7); ctx.fill(); ctx.globalAlpha=1; }
    ctx.restore();
    // tugma yozuvi kemaga yetgandan keyin qayta tayyor holat
    if(!playing && (plane.dead && now-plane.deadT>1800 || plane.kamikaze && now-plane.kamikaze>2600)){ plane.dead=false; plane.kamikaze=0; plane.boom=false; reset(); paint(); }
  }
  window.KM={stop(){ alive=false; cancelAnimationFrame(raf); },
    cell(r){ const g=geo(), [x,y]=cellXY(step,r,g); return [(x-camX)/dpr,y/dpr]; }};
  size(); reset(); paint(); raf=requestAnimationFrame(frame);
  if(window.D_KAMI_GAME){ resume(window.D_KAMI_GAME); window.D_KAMI_GAME=null; }
}

// ---- FROG (Baqa) ----
function initFrog(){
  const btn=document.getElementById('fbtn'), cash=document.getElementById('fcash'),
        bet=document.getElementById('fbet'), pond=document.getElementById('pond'),
        note=document.getElementById('fnote'), seg=document.getElementById('fmode');
  if(!btn) return;
  let mode='easy', rows=5, cols=4, step=0, playing=false;
  seg.querySelectorAll('.s').forEach(s=>s.onclick=()=>{ if(playing) return;
    seg.querySelectorAll('.s').forEach(x=>x.classList.remove('on')); s.classList.add('on'); mode=s.dataset.m; });
  bet.oninput=()=>{ if(!playing) btn.textContent='🐸 Tikish ('+(parseInt(bet.value)||0)+'$)'; };
  function grid(active){
    pond.innerHTML='';
    for(let r=rows-1;r>=0;r--) for(let c=0;c<cols;c++){
      const cell=document.createElement('div');
      cell.className='pad'+(r===active?' active':(r<active?' dim':''));
      cell.textContent=r===active?'🪷':(r<active?'✅':'🌿');
      if(r===active&&playing){ cell.onclick=()=>stepTo(c,cell); }
      pond.appendChild(cell);
    }
  }
  function start(){
    const b=parseInt(bet.value)||0; btn.disabled=true;
    api('/app/api/frog/start',{bet:b,mode:mode}).then(r=>{
      if(!r.ok||r.error){ note.textContent=errText(r.error,r.min); btn.disabled=false; return; }
      setBal(r.balance); rows=r.rows; cols=r.cols; step=0; playing=true; SND.play('chip');
      btn.style.display='none'; cash.style.display='block'; cash.disabled=true;
      note.textContent='🪷 Keyingi: '+r.next_mult+'x'; grid(0);
    }).catch(()=>{ btn.disabled=false; });
  }
  function stepTo(c,cell){
    pond.querySelectorAll('.pad').forEach(p=>p.onclick=null); SND.play('hop');
    api('/app/api/frog/step',{col:c}).then(r=>{
      if(r.result==='lose'){ cell.className='pad bad'; cell.textContent='🐸'; playing=false; SND.play('splash');
        note.textContent='🌊 Suvga tushdingiz! Yutqazdingiz.'; haptic('error'); endGame(); }
      else if(r.result==='win_full'){ cell.className='pad safe'; cell.textContent='✅'; setBal(r.balance); playing=false; SND.play('win');
        note.textContent='🏆 Yakun! +'+fmtMoney(r.win)+'$ ('+r.multiplier+'x)'; haptic('success'); endGame(); }
      else { cell.className='pad safe'; cell.textContent='✅'; step=r.step; cash.disabled=false; SND.play('plop');
        cash.textContent='💰 Yechib olish ('+r.multiplier+'x)';
        note.textContent='✅ '+r.multiplier+'x · keyingi: '+r.next_mult+'x'; haptic('success'); grid(step); }
    });
  }
  function doCash(){
    if(!playing||step<=0) return; cash.disabled=true;
    api('/app/api/frog/cashout',{}).then(r=>{
      if(r.result==='cashed'){ setBal(r.balance); playing=false; SND.play('cash'); note.textContent='✅ +'+fmtMoney(r.win)+'$ ('+r.multiplier+'x)'; haptic('success'); endGame(); }
    });
  }
  function endGame(){ setTimeout(()=>{ playing=false; btn.style.display='block'; btn.disabled=false; cash.style.display='none';
    btn.textContent='🐸 Tikish ('+(parseInt(bet.value)||0)+'$)'; pond.innerHTML=''; note.textContent='Rejim tanlab, tikib boshlang 🪷'; },1800); }
  btn.onclick=start; cash.onclick=doCash;
}
function errText(e,min){
  if(e==='min') return 'Minimal: '+min+'$';
  if(e==='funds') return '💸 Hamyonda pul yetarli emas';
  if(e==='disabled') return '🌐 Web app o‘chirilgan';
  if(e==='max') return 'Juda katta miqdor';
  if(e==='stale') return '⏳ Narx yangilanmoqda, qayta urining';
  if(e==='hold') return '⏳ Hali sotib bo‘lmaydi';
  if(e==='nothing') return 'Sizda bu aktiv yo‘q';
  if(e==='recipient') return 'Qabul qiluvchi topilmadi';
  if(e==='undeliverable') return 'Yetkazilmadi — u botni ochmagan. Pul qaytdi';
  if(e==='no_pair') return 'Juftingiz yo‘q';
  if(e==='self') return 'O‘zingizga yubora olmaysiz';
  if(e==='purpose') return '🎯 Kredit maqsadini yozing';
  if(e==='owner_unreachable') return 'Bank egasiga yetkazib bo‘lmadi';
  if(e==='apply_pending') return '📝 Arizangiz hali ko‘rib chiqilmoqda';
  if(e==='loan_has') return 'Sizda faol kredit bor';
  if(e==='bet_placed') return 'Bu raundga allaqachon tikkansiz';
  return 'Xato, qayta urining';
}
function hm(sec){ sec=Math.max(0,sec|0); const h=Math.floor(sec/3600), m=Math.floor(sec%3600/60); return (h?h+' soat ':'')+m+' daq'; }
function gearSheet(k){
  sheet('🎒 '+esc(k.name)+' uchun buyumlar',k.gear.map(it=>({label:esc(it.name)+'<br>'+(it.owned?'✅ bor':'<b>'+fmtMoney(it.price)+'$</b> · 😊 +'+it.eff),value:it.key})),
    (item)=>{ const it=k.gear.find(x=>x.key===item); if(it&&it.owned){ toast('✅ Bu buyum allaqachon bor'); return; }
      api('/app/api/kid',{kid:k.id,act:'gear',item:item}).then(r=>{ if(r.result==='ok'){ setBal(r.balance); toast('✅ '+esc(it?it.name:'Buyum')+' olindi · 😊 '+r.value+'%'); refresh(); } else toast(kidErr(r.error)); }); });
}
function eduErr(e){
  if(e==='name') return 'Nomi kamida 2 harf bo‘lsin';
  if(e==='fee') return 'To‘lov 0 – 1 000 000$ oralig‘ida bo‘lsin';
  if(e==='kind') return 'Turini tanlang';
  if(e==='owner_only') return 'Faqat bot egalari uchun';
  return errText(e);
}
function kidErr(e,wait){
  if(e==='too_soon') return '⏳ Yaqinda ovqatlandi. Keyingi ovqat: '+hm(wait||0)+' dan keyin';
  if(e==='owned') return '✅ Bu buyum allaqachon bor';
  if(e==='inst_stage') return 'Bu muassasa farzand yoshiga mos emas';
  if(e==='inst') return 'Muassasa topilmadi yoki yopilgan';
  if(e==='full') return 'To‘la — hozircha kerak emas';
  if(e==='no_fee') return 'Hozir to‘lov kerak emas';
  if(e==='working') return 'Bu farzand ishlaydi';
  if(e==='funds') return '💸 Pul yetarli emas';
  return errText(e);
}
function setTab(k){
  TAB=k;
  document.querySelectorAll('.sec').forEach(s=>s.classList.toggle('on',s.id==='s-'+k));
  const tk=(k==='crash'||k==='frog'||k==='kami')?'casino':k;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.k===tk));
  if(k==='crash' && window.CR) window.CR.poke();
  SND.music(k==='crash'||k==='frog'||k==='kami'?k:null);
  window.scrollTo(0,0);
}
function card(lbl,val,cls,full){
  return '<div class="card '+(full||'')+'"><div class="lbl">'+lbl+'</div>'+
    '<div class="val '+(cls||'')+'">'+esc(val)+'</div></div>';
}
boot();
</script>
</body>
</html>"""


def main():
    if not BOT_TOKEN or BOT_TOKEN == "BU_YERGA_BOT_TOKEN":
        print(
            "❌ BOT_TOKEN o‘rnatilmagan!\n"
            "   Linux/Mac:  export BOT_TOKEN='123:ABC...'\n"
            "   Windows:    set BOT_TOKEN=123:ABC...   (PowerShell: $env:BOT_TOKEN='123:ABC...')"
        )
        return

    init_db()
    init_economy()
    init_group_members()
    init_bank()
    init_birja()
    init_kids()
    init_edu()
    init_guard()
    init_guard2()
    init_grouphelp()
    init_exchange()
    init_panel_overrides()
    init_forcesub()
    init_webapp()
    init_rereg()
    init_bot_users()
    load_crash_config()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(Defaults(parse_mode=ParseMode.HTML))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    commands = [
        (["panel"], cmd_panel),
        (["taxrir"], cmd_taxrir),
        (["haqiqiy"], cmd_haqiqiy),
        (["tasdiq"], cmd_tasdiq),
        (["start"], cmd_start),
        (["juft"], cmd_juft),
        (["juftim"], cmd_juftim),
        (["juftliklar"], cmd_juftliklar),
        (["emps", "games", "oyin"], cmd_emps),
        (["stop"], cmd_stop),
        (["reyting", "rating"], cmd_reyting),
        (["aktiv", "active"], cmd_aktiv),
        (["profil", "profile"], cmd_profil),
        (["oila", "family"], cmd_oila),
        (["farzand", "kids"], cmd_farzand),
        (["far"], cmd_far),
        (["settings", "sozlamalar"], cmd_settings),
        (["warn", "unwarn", "warns", "mute", "tmute", "unmute", "ban", "tban", "unban", "kick"], cmd_mod),
        (["promote", "demote"], cmd_promote),
        (["addword", "delword", "words"], cmd_words),
        (["del", "delete", "ochir"], cmd_del),
        (["purge", "tozala"], cmd_purge),
        (["pin", "unpin"], cmd_pin),
        (["id"], cmd_id),
        (["info"], cmd_info),
        (["admins", "adminlar"], cmd_admins),
        (["lock", "unlock", "locks"], cmd_lock),
        (["title", "unvon"], cmd_title),
        (["setwelcome", "setwelc"], cmd_setwelcome),
        (["setrules"], cmd_setrules),
        (["badmute", "setbadmute"], cmd_badmute),
        (["filter", "filters", "delfilter"], cmd_filter),
        (["report"], cmd_report),
        (["setlog"], cmd_setlog),
        (["shop"], cmd_shop),
        (["pul"], cmd_pul),
        (["hisob"], cmd_hisob),
        (["hadya"], cmd_hadya),
        (["crash"], cmd_crash),
        (["scrash"], cmd_scrash),
        (["konkurs"], cmd_konkurs),
        (["missiyalar", "missions"], cmd_missiyalar),
        (["ariza"], cmd_ariza),
        (["qoidalar"], cmd_rules),
        (["rules"], cmd_grules),
        (["app", "ilova"], cmd_app),
        (["help", "yordam"], cmd_help),
        (["lang"], cmd_lang),
    ]
    # Buyruqlar / belgisidan tashqari . va ! bilan ham ishlaydi (Group Help uslubi): .admin .del .mute ...
    EXTRA_PREFIXES = [".", "!"]
    for names, handler in commands:
        if names in (["konkurs"], ["hadya"], ["crash"], ["scrash"]):
            # /konkurs guruhda ham, kanalda ham ishlashi uchun channel_post'larni ham qabul qilamiz
            app.add_handler(CommandHandler(
                names, handler,
                filters=filters.UpdateType.MESSAGES | filters.UpdateType.CHANNEL_POSTS,
            ))
        else:
            app.add_handler(CommandHandler(names, handler))
        # . va ! prefikslari (PrefixHandler komandani pastki registrsiz talab qiladi)
        app.add_handler(PrefixHandler(EXTRA_PREFIXES, names, handler))

    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    # Alohida guruh (-1): a'zolar ro'yxatini yig'adi, asosiy handlerlarni to'smaydi.
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, track_group_member), group=-1)
    # Guruh himoyasi eng birinchi ishlaydi: reklama/flood bo'lsa ApplicationHandlerStop bilan to'xtatadi.
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.UpdateType.MESSAGE, guard_messages), group=-2)
    app.add_handler(CallbackQueryHandler(cb_shop, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(cb_contest, pattern=r"^contest:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_hadya, pattern=r"^hadya:claim:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_panel, pattern=r"^panel:"))
    app.add_handler(CallbackQueryHandler(cb_memory, pattern=r"^m:"))
    app.add_handler(CallbackQueryHandler(cb_croc, pattern=r"^croc:show$"))
    app.add_handler(CallbackQueryHandler(cb_game, pattern=r"^g:(number|rsp|xo|memory|crash|croc|casino|frog|back|menu)$"))
    app.add_handler(CallbackQueryHandler(cb_frog, pattern=r"^fr:"))
    app.add_handler(CallbackQueryHandler(cb_bank, pattern=r"^bk:\d+:"))
    app.add_handler(CallbackQueryHandler(cb_bank_app, pattern=r"^bka:\d+:(yes|no)$"))
    app.add_handler(CallbackQueryHandler(cb_exchange, pattern=r"^ex:\d+:"))
    app.add_handler(CallbackQueryHandler(cb_birja, pattern=r"^bx:\d+:"))
    app.add_handler(CallbackQueryHandler(cb_kid, pattern=r"^kid:\d+:"))
    app.add_handler(CallbackQueryHandler(cb_captcha, pattern=r"^cap:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_settings, pattern=r"^gs:-?\d+:\w+$"))
    app.add_handler(CallbackQueryHandler(cb_admin, pattern=r"^ga:-?\d+:\d+(:\w+)?$"))
    app.add_handler(CallbackQueryHandler(cb_report, pattern=r"^rp:-?\d+:\d+:\d+:(del|mute|ban)$"))
    app.add_handler(CallbackQueryHandler(cb_mod_undo, pattern=r"^(undo:(mute|ban):\d+|bw:-?\d+:\d+)$"))
    app.add_handler(CallbackQueryHandler(cb_fsub_check, pattern=r"^fsub:check$"))
    app.add_handler(CallbackQueryHandler(cb_inline_game, pattern=r"^ix:(xo|rsp|crash|memory):\d+:(uz|eng|ru|kz)$"))
    app.add_handler(InlineQueryHandler(secret_inline))
    app.add_handler(CallbackQueryHandler(cb_career, pattern=r"^career:"))
    app.add_handler(
        CallbackQueryHandler(secret_callback, pattern=r"^secret:")
    )
    app.add_handler(CallbackQueryHandler(cb_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(cb_rsp_count, pattern=r"^rc:[235]$"))
    app.add_handler(CallbackQueryHandler(cb_rsp_join, pattern=r"^rj$"))
    app.add_handler(CallbackQueryHandler(cb_rsp_pick, pattern=r"^rp:(rock|scissors|paper)$"))
    app.add_handler(CallbackQueryHandler(cb_xo_join, pattern=r"^xj$"))
    app.add_handler(CallbackQueryHandler(cb_xo_move, pattern=r"^xm:[0-8]$"))
    # Boshqa barcha callback'larga ham javob beramiz (spinner qotib qolmasin)
    app.add_handler(CallbackQueryHandler(cb_relationship, pattern=r"^(rel:|family:)"))
    app.add_handler(CallbackQueryHandler(cb_crash, pattern=r"^cr:"))
    app.add_handler(CallbackQueryHandler(cb_noop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE & filters.UpdateType.MESSAGE, career_private_text))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS & filters.UpdateType.MESSAGE,
            on_text,
        )
    )

    app.add_error_handler(on_error)

    print("🤖 Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
