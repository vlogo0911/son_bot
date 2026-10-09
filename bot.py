"""
🎮 O'yinlar boti  —  Son topish · Tosh-Qaychi-Qog'oz · XO

Talab: python-telegram-bot >= 22   (pip install -r requirements.txt)
Ishga tushirish:  BOT_TOKEN muhit o'zgaruvchisini o'rnating va `python bot.py`
"""

import html
import asyncio
import logging
from datetime import date, datetime
import os
import random
import sqlite3
import re
import secrets
from html import escape

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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

# Kasb almashtirish so'rovlarini qabul qiladigan ownerlar
CAREER_OWNER_IDS = {6913838682, 1150777456}

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
LANG_CACHE: dict[int, str] = {}


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


def db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_FILE)
    return _conn


def init_db():
    c = db()
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
    key = (user.username, user.first_name)
    if _SEEN.get(user.id) == key:
        return
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

                # Ownerlar cheksiz pulga ega, balansiga qo'shmaymiz
                if user_id not in {6913838682, 1150777456}:
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


async def edit(bot, chat_id, message_id, text, kb=None):
    """Xabarni xavfsiz tahrirlaydi ("not modified" xatosini e'tiborsiz qoldiradi)."""
    try:
        await bot.edit_message_text(
            text, chat_id=chat_id, message_id=message_id, reply_markup=kb
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
    if GAMES.get(chat_id) is game:
        del GAMES[chat_id]
    timer = game.get("timer")
    if timer and not timer.done():
        timer.cancel()
    game["timer"] = None


async def close_game_message(bot, chat_id, game, text):
    """O'yin xabarini yakuniy matn bilan almashtiradi (yoki yangi xabar yuboradi)."""
    if game.get("msg_id") and game["type"] != "number":
        try:
            await bot.edit_message_text(
                text, chat_id=chat_id, message_id=game["msg_id"], reply_markup=None
            )
            return
        except TelegramError:
            pass
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

    del GAMES[chat_id]
    game["timer"] = None

    if game["type"] == "number":
        text = t(chat_id, "number_timeout", number=game["number"])
    else:
        text = t(chat_id, "timeout")
    await close_game_message(app.bot, chat_id, game, text)


def active(q, kind):
    """Tugma bosilgan xabar hozirgi o'yinga tegishlimi? (eski xabarlardan himoya)"""
    game = GAMES.get(q.message.chat.id)
    if game and game["type"] == kind and game.get("msg_id") == q.message.message_id:
        return game
    return None


# ───────────────────────────── Menyu va umumiy buyruqlar ─────────────────────────────


def menu_kb(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(chat_id, "btn_number"), callback_data="g:number")],
        [InlineKeyboardButton(t(chat_id, "btn_rsp"), callback_data="g:rsp")],
        [InlineKeyboardButton(t(chat_id, "btn_xo"), callback_data="g:xo")],
        [InlineKeyboardButton(memory_t(chat_id, "btn"), callback_data="g:memory")],
    ])


def again_row(chat_id):
    return [InlineKeyboardButton(t(chat_id, "btn_again"), callback_data="g:menu")]


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



def panel_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Foydalanuvchilar", callback_data="panel:users"),
            InlineKeyboardButton("🏘 Guruhlar", callback_data="panel:groups"),
        ],
        [
            InlineKeyboardButton("🎮 Faol o'yinlar", callback_data="panel:active"),
            InlineKeyboardButton("📊 Umumiy statistika", callback_data="panel:stats"),
        ],
        [
            InlineKeyboardButton("🏆 O'yin turlari statistikasi", callback_data="panel:games"),
        ],
    ])


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

    if user.id not in CAREER_OWNER_IDS:
        await msg.reply_text("⛔ Bu buyruq faqat bot egalari uchun.")
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

    await msg.reply_text(text, reply_markup=panel_keyboard())



async def cb_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    if query.from_user.id not in CAREER_OWNER_IDS:
        await query.answer(
            "⛔ Bu bo'lim faqat bot egalari uchun.",
            show_alert=True,
        )
        return

    await query.answer()

    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else "home"

    try:
        page = max(0, int(parts[2])) if len(parts) > 2 else 0
    except ValueError:
        page = 0

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
            reply_markup=panel_keyboard(),
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
    await close_game_message(context.bot, chat.id, game, t(chat.id, "stopped"))


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

    if user.id in {6913838682, 1150777456}:
        money = "∞"

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
        age_display = f"{age} {age_units.get(lang, age_units["uz"])}"
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

    await msg.reply_text(
        t(
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


async def cmd_menyu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user
    if not chat or not msg or not user:
        return
    if chat.type != ChatType.PRIVATE:
        await msg.reply_text("📩 Menyuni bot bilan shaxsiy chatda oching: /menyu")
        return

    save_user(user)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Juftlashish arizasi", callback_data="rel:menu:pair")],
        [InlineKeyboardButton("💼 Ishdan bo‘shash arizasi", callback_data="rel:menu:quit")],
        [InlineKeyboardButton("💔 Juft bilan ajrashish arizasi", callback_data="rel:menu:divorce")],
    ])
    await msg.reply_text("📋 <b>Arizalar menyusi</b>\nKerakli bo‘limni tanlang:", reply_markup=kb)


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
                   decided_by=?, decided_at=? WHERE id=? AND status='pending'""",
                (uid, now, rid),
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


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not msg.text or not user or user.is_bot:
        return

    chat_id = msg.chat_id
    game = GAMES.get(chat_id)
    if not game or game["type"] != "number":
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
    chat_id = q.message.chat.id
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
    chat_id = q.message.chat.id
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
    chat_id = q.message.chat.id
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
    chat_id = q.message.chat.id
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
    chat_id = q.message.chat.id
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


# ───────────────────────────── Boshqa callback'lar ─────────────────────────────


async def cb_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


# ───────────────────────────── Xatolar va ishga tushirish ─────────────────────────────


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Kutilmagan xato", exc_info=context.error)


async def post_init(application: Application):
    sets = {
        None: [
            ("emps", "🎮 O‘yin tanlash"), ("stop", "🛑 O‘yinni to‘xtatish"),
            ("reyting", "🏆 Reyting"), ("profil", "👤 Profil"),
            ("qoidalar", "📚 Qoidalar"), ("lang", "🌐 Til"), ("help", "❓ Yordam"),
        ],
        "en": [
            ("emps", "🎮 Choose a game"), ("stop", "🛑 Stop the game"),
            ("reyting", "🏆 Leaderboard"), ("profil", "👤 Profile"),
            ("qoidalar", "📚 Rules"), ("lang", "🌐 Language"), ("help", "❓ Help"),
        ],
        "ru": [
            ("emps", "🎮 Выбрать игру"), ("stop", "🛑 Остановить игру"),
            ("reyting", "🏆 Рейтинг"), ("profil", "👤 Профиль"),
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
        timer = game.get("timer")
        if timer and not timer.done():
            timer.cancel()
    if _conn is not None:
        _conn.close()


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
    if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
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
            ],
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



def main():
    if not BOT_TOKEN or BOT_TOKEN == "BU_YERGA_BOT_TOKEN":
        print(
            "❌ BOT_TOKEN o‘rnatilmagan!\n"
            "   Linux/Mac:  export BOT_TOKEN='123:ABC...'\n"
            "   Windows:    set BOT_TOKEN=123:ABC...   (PowerShell: $env:BOT_TOKEN='123:ABC...')"
        )
        return

    init_db()

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
        (["start"], cmd_start),
        (["menyu"], cmd_menyu),
        (["juft"], cmd_juft),
        (["juftim"], cmd_juftim),
        (["juftliklar"], cmd_juftliklar),
        (["emps", "games", "oyin"], cmd_emps),
        (["stop"], cmd_stop),
        (["reyting", "rating"], cmd_reyting),
        (["profil", "profile"], cmd_profil),
        (["missiyalar", "missions"], cmd_missiyalar),
        (["ariza"], cmd_ariza),
        (["qoidalar", "rules"], cmd_rules),
        (["help"], cmd_help),
        (["lang"], cmd_lang),
    ]
    for names, handler in commands:
        app.add_handler(CommandHandler(names, handler))

    app.add_handler(CallbackQueryHandler(cb_panel, pattern=r"^panel:"))
    app.add_handler(CallbackQueryHandler(cb_memory, pattern=r"^m:"))
    app.add_handler(CallbackQueryHandler(cb_game, pattern=r"^g:(number|rsp|xo|memory|menu)$"))
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
    app.add_handler(CallbackQueryHandler(cb_relationship, pattern=r"^rel:"))
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
