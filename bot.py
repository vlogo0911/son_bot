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
from datetime import date, datetime
import os
import random
import sqlite3
import re
import secrets
import time
from html import escape

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputFile,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TelegramError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    InlineQueryHandler,
    MessageHandler,
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
        "SELECT child_name,gender FROM family_children WHERE pair_id=? ORDER BY id",
        (pair[0],),
    ).fetchall()
    names = [f"👶 {escape(n)} — {escape(child_gender_label(user.id, g))}" for n, g in child_rows]
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
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(family_text(user.id, "child"), url=family_url(context, "child"))
    ]])
    await msg.reply_text("\n".join(lines), reply_markup=kb)


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
        rows.append([InlineKeyboardButton("🎰 Crash sozlamalari", callback_data="panel:crash")])
        rows.append([InlineKeyboardButton("✨ Premium emoji", callback_data="panel:pemoji")])

    return InlineKeyboardMarkup(rows or [[
        InlineKeyboardButton("🔄 Panelni yangilash", callback_data="panel:home")
    ]])


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
    users_count = c.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]
    group_ids = panel_group_ids(c)
    total_games = c.execute(
        "SELECT COALESCE(SUM(games), 0) FROM chat_stats"
    ).fetchone()[0]

    text = (
        "🛠 <b>BOT EGASI PANELI</b>\n\n"
        "Kerakli bo'limni tugma orqali tanlang.\n\n"
        f"👤 Foydalanuvchilar: <b>{users_count}</b>\n"
        f"🏘 Guruhlar: <b>{len(group_ids)}</b>\n"
        f"🎮 Faol o'yinlar: <b>{len(GAMES)}</b>"
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

    await query.answer()

    if query.data == "panel:pemoji" or query.data.startswith("panel:pemoji:"):
        await pemoji_callback(query, context)
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
    users_count = c.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

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
            f"👤 Foydalanuvchilar: <b>{users_count}</b>\n"
            f"🏘 Qayd etilgan guruhlar: <b>{len(group_ids)}</b>\n"
            f"🎮 Faol o'yinlar: <b>{len(GAMES)}</b>\n"
            f"📈 Jami o'yin ishtiroklari: <b>{total_games}</b>\n\n"
            "ℹ️ Ishtiroklar chat statistikasi asosida hisoblanadi."
        )

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
            f"👤 Foydalanuvchilar: <b>{users_count}</b>\n"
            f"🏘 Guruhlar: <b>{len(group_ids)}</b>\n"
            f"🎮 Faol o'yinlar: <b>{len(GAMES)}</b>"
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
            "SELECT child_name,gender FROM family_children WHERE pair_id=? ORDER BY id",
            (pair[0],),
        ).fetchall()
        child_lines = [
            f"👶 {escape(child_name)} — {escape(child_gender_label(user.id, child_gender))}"
            for child_name, child_gender in child_rows
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


async def create_rel_request(application, request_type, requester_id,
                             target_id=None, group_id=None):
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
               (request_type, requester_id, target_id, group_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (request_type, requester_id, target_id, group_id, initial_status, now),
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
                     f"{person_name(requester_id)} siz bilan ajrashishni so‘radi. "
                     "Rozilik bildirasizmi?",
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
        await q.answer("Rozilik qabul qilindi.")
        await q.edit_message_text("✅ Rozilik berildi. Farzand kutishsiz yetkaziladi." if immediate_delivery else "✅ Rozilik berildi. Farzand 48 soat ichida yetkaziladi.")
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
        if answer == "no":
            with c:
                c.execute("UPDATE pair_requests SET status='rejected' WHERE id=?", (rid,))
            await q.answer("Taklif rad etildi.")
            await q.edit_message_text("❌ Taklif rad etildi.")
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
            with c:
                c.execute(
                    "UPDATE pairs SET status='ended', ended_at=? WHERE id=? AND status='active'",
                    (now, pair[0]),
                )
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


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if chat and msg:
        await msg.reply_text(t(chat.id, "help"))


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
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🐾 Hayvonlar", callback_data="m:cat:animals"),
                InlineKeyboardButton("🍕 Taomlar", callback_data="m:cat:food"),
            ],
            [
                InlineKeyboardButton("😀 Yuzlar", callback_data="m:cat:faces"),
            ],
        ])
        await edit(
            context.bot, chat_id, msg.message_id,
            memory_t(chat_id, "choose"), kb
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
    if not q or not q.message:
        return

    chat_id = q.message.chat.id
    game = GAMES.get(chat_id)

    if not game or game.get("type") != "memory":
        await _cb_memory_locked(update, context)
        return

    lock = game.setdefault("_callback_lock", asyncio.Lock())
    async with lock:
        await _cb_memory_locked(update, context)


async def _cb_memory_locked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat.id
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

        game["state"] = "play"
        game["board"] = memory_make_board(game["size"], game.get("category", "animals"))
        game["revealed"] = set()
        game["locked"] = set()
        game["scores"] = {uid: 0 for uid in game["names"]}
        game["turn"] = list(game["names"])[0]
        game["first"] = None
        game["second"] = None
        game["busy"] = False

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


# ───────────────────────────── 🎯 Son topish ─────────────────────────────

HEAT = [(3, "heat_hot"), (10, "heat_warm"), (25, "heat_cool"), (10**9, "heat_cold")]


# ───────────────────────────── 📢 "bot" — guruh a'zolarini chaqirish ─────────────────────────────
# Bot egasi yoki bot paneli admini guruhda "bot" deb yozsa, bot guruh a'zolarini
# 5 tadan belgilab chiqadi. "bot kelish" — har bir a'zo "@username kelish" ko'rinishida
# chaqiriladi. "stop" — jarayonni to'xtatadi.
# Telegram botga guruh a'zolarining to'liq ro'yxatini bermaydi, shuning uchun bot
# guruhda yozgan / qo'shilgan a'zolarni group_members jadvalida o'zi yig'ib boradi.

TAG_WORDS = {"bot", "бот"}
TAG_STOP_WORDS = {"stop", "стоп", "bot stop", "бот стоп"}
TAG_TEXT_MAX = 200      # "bot ..." dan keyingi matnning eng katta uzunligi
TAG_BATCH = 5           # bitta xabardagi belgilar soni
TAG_DELAY = 3.0         # xabarlar orasidagi pauza (guruh flood-limitidan saqlaydi)
TAG_TASKS: dict[int, asyncio.Task] = {}

TAG_TEXT = {
    "uz": {
        "head": "📢 <b>Diqqat!</b>",
        "busy": "⏳ A'zolar hozir chaqirilyapti. To'xtatish: <b>stop</b>",
        "empty": "🤷 Bot hali bu guruh a'zolarini bilmaydi. A'zolar guruhda yozganda ular ro'yxatga qo'shiladi.",
        "done": "✅ <b>{n}</b> ta a'zo chaqirildi.",
        "stopped": "🛑 Chaqirish to'xtatildi ({n} ta a'zo chaqirildi).",
    },
    "eng": {
        "head": "📢 <b>Attention!</b>",
        "busy": "⏳ Members are being tagged right now. To stop: <b>stop</b>",
        "empty": "🤷 The bot doesn't know this group's members yet. Members are added when they write in the group.",
        "done": "✅ <b>{n}</b> members tagged.",
        "stopped": "🛑 Tagging stopped ({n} members tagged).",
    },
    "ru": {
        "head": "📢 <b>Внимание!</b>",
        "busy": "⏳ Участники уже упоминаются. Остановить: <b>стоп</b>",
        "empty": "🤷 Бот пока не знает участников этой группы. Они добавляются, когда пишут в группе.",
        "done": "✅ Упомянуто участников: <b>{n}</b>.",
        "stopped": "🛑 Упоминание остановлено (упомянуто: {n}).",
    },
    "kz": {
        "head": "📢 <b>Назар аударыңыз!</b>",
        "busy": "⏳ Мүшелер қазір белгіленуде. Тоқтату: <b>стоп</b>",
        "empty": "🤷 Бот бұл топтың мүшелерін әлі білмейді. Олар топта жазғанда тізімге қосылады.",
        "done": "✅ <b>{n}</b> мүше белгіленді.",
        "stopped": "🛑 Белгілеу тоқтатылды ({n} мүше белгіленді).",
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
        # Birinchi ishga tushishda guruhda o'ynagan a'zolarni ro'yxatga olamiz.
        c.execute("""
            INSERT OR IGNORE INTO group_members(chat_id, user_id, last_seen)
            SELECT chat_id, user_id, ? FROM chat_stats WHERE chat_id < 0
        """, (datetime.utcnow().isoformat(),))


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
        for new in msg.new_chat_members or ():
            member_seen(chat.id, new)
        if msg.left_chat_member:
            member_left(chat.id, msg.left_chat_member.id)
    except sqlite3.Error:
        logger.exception("group_members yangilanmadi")


async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot admin bo'lgan guruhlarda kirish/chiqishlarni kuzatadi."""
    event = update.chat_member
    if not event or event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    member = event.new_chat_member
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
                await asyncio.sleep(TAG_DELAY)
    except asyncio.CancelledError:
        await bot.send_message(chat_id, tag_t(chat_id, "stopped", n=tagged))
        raise
    await bot.send_message(chat_id, tag_t(chat_id, "done", n=tagged))


async def maybe_tag_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'bot [matn]' / 'stop' buyrug'i bo'lsa — bajaradi va True qaytaradi."""
    msg = update.effective_message
    user = update.effective_user
    raw = msg.text.strip()
    text = raw.lower()
    first, _, rest = raw.partition(" ")
    is_start = first.lower() in TAG_WORDS
    if not is_start and text not in TAG_STOP_WORDS:
        return False
    if not is_panel_admin(user.id):
        return False

    chat_id = msg.chat_id
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
    sets = {
        None: [
            ("emps", "🎮 O‘yin tanlash"), ("stop", "🛑 O‘yinni to‘xtatish"),
            ("reyting", "🏆 Reyting"), ("profil", "👤 Profil"), ("scrash", "🛑 Crashni to‘xtatish"),
            ("qoidalar", "📚 Qoidalar"), ("lang", "🌐 Til"), ("help", "❓ Yordam"),
        ],
        "en": [
            ("emps", "🎮 Choose a game"), ("stop", "🛑 Stop the game"),
            ("reyting", "🏆 Leaderboard"), ("profil", "👤 Profile"), ("scrash", "🛑 Stop Crash"),
            ("qoidalar", "📚 Rules"), ("lang", "🌐 Language"), ("help", "❓ Help"),
        ],
        "ru": [
            ("emps", "🎮 Выбрать игру"), ("stop", "🛑 Остановить игру"),
            ("reyting", "🏆 Рейтинг"), ("profil", "👤 Профиль"), ("scrash", "🛑 Остановить Crash"),
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



async def post_shutdown(application: Application):
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
            reply_markup=career_profession_kb(chat.id),
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

    raw = msg.text.strip()
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
    "uz": {"xo": "Do‘stingiz bilan XO o‘ynang", "rsp": "Ikki kishilik tosh-qaychi-qog‘oz", "crash": "Pul tikib roketni kuzating"},
    "eng": {"xo": "Play XO with a friend", "rsp": "Rock-paper-scissors for two", "crash": "Bet and watch the rocket"},
    "ru": {"xo": "Сыграйте в XO с другом", "rsp": "Камень-ножницы-бумага на двоих", "crash": "Сделайте ставку и следите за ракетой"},
    "kz": {"xo": "Досыңызбен XO ойнаңыз", "rsp": "Екі адамға тас-қайшы-қағаз", "crash": "Ақша салып, зымыранды бақылаңыз"},
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

    def article(kind, title, text, join_label):
        return InlineQueryResultArticle(
            id=f"game-{kind}",
            title=title,
            description=desc[kind],
            input_message_content=InputTextMessageContent(text, parse_mode=ParseMode.HTML),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                join_label, callback_data=f"ix:{kind}:{user.id}:{lang}",
            )]]),
        )

    results = [
        article("xo", texts["btn_xo"], texts["xo_lobby"].format(owner=name), texts["btn_join"]),
        article(
            "rsp", texts["btn_rsp"],
            texts["rsp_lobby"].format(current=1, count=2, players=f"🙋 {name}\n⬜ …"),
            texts["btn_join"],
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
       InlineKeyboardButton({"uz":"👤 Boshqaga","eng":"👤 Someone else","ru":"👤 Другому","kz":"👤 Басқаға"}.get(lang,"👤 Boshqaga"), callback_data="shop:other")]
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
        (["tasdiq"], cmd_tasdiq),
        (["start"], cmd_start),
        (["juft"], cmd_juft),
        (["juftim"], cmd_juftim),
        (["juftliklar"], cmd_juftliklar),
        (["emps", "games", "oyin"], cmd_emps),
        (["stop"], cmd_stop),
        (["reyting", "rating"], cmd_reyting),
        (["profil", "profile"], cmd_profil),
        (["oila", "family"], cmd_oila),
        (["shop"], cmd_shop),
        (["pul"], cmd_pul),
        (["hisob"], cmd_hisob),
        (["hadya"], cmd_hadya),
        (["crash"], cmd_crash),
        (["scrash"], cmd_scrash),
        (["konkurs"], cmd_konkurs),
        (["missiyalar", "missions"], cmd_missiyalar),
        (["ariza"], cmd_ariza),
        (["qoidalar", "rules"], cmd_rules),
        (["help"], cmd_help),
        (["lang"], cmd_lang),
    ]
    for names, handler in commands:
        if names in (["konkurs"], ["hadya"], ["crash"], ["scrash"]):
            # /konkurs guruhda ham, kanalda ham ishlashi uchun channel_post'larni ham qabul qilamiz
            app.add_handler(CommandHandler(
                names, handler,
                filters=filters.UpdateType.MESSAGES | filters.UpdateType.CHANNEL_POSTS,
            ))
        else:
            app.add_handler(CommandHandler(names, handler))

    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    # Alohida guruh (-1): a'zolar ro'yxatini yig'adi, asosiy handlerlarni to'smaydi.
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, track_group_member), group=-1)
    app.add_handler(CallbackQueryHandler(cb_shop, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(cb_contest, pattern=r"^contest:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_hadya, pattern=r"^hadya:claim:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_panel, pattern=r"^panel:"))
    app.add_handler(CallbackQueryHandler(cb_memory, pattern=r"^m:"))
    app.add_handler(CallbackQueryHandler(cb_croc, pattern=r"^croc:show$"))
    app.add_handler(CallbackQueryHandler(cb_game, pattern=r"^g:(number|rsp|xo|memory|crash|croc|casino|back|menu)$"))
    app.add_handler(CallbackQueryHandler(cb_inline_game, pattern=r"^ix:(xo|rsp|crash):\d+:(uz|eng|ru|kz)$"))
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
