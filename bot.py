"""
🎮 O'yinlar boti  —  Son topish · Tosh-Qaychi-Qog'oz · XO

Talab: python-telegram-bot >= 22   (pip install -r requirements.txt)
Ishga tushirish:  BOT_TOKEN muhit o'zgaruvchisini o'rnating va `python bot.py`
"""

import asyncio
import logging
import os
import random
import sqlite3
from html import escape

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
    MessageHandler,
    filters,
)

# ───────────────────────────── Sozlamalar ─────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "game.db")

DEFAULT_LANG = "uz"

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
            "🎖 Daraja: {level}\n"
            "💰 Ball: <b>{points}</b>\n"
            "🎮 O‘yinlar: {games}\n"
            "🏆 G‘alabalar: {wins}\n"
            "💔 Mag‘lubiyatlar: {losses}\n"
            "🤝 Duranglar: {draws}\n"
            "📊 G‘alaba foizi: <b>{winrate}%</b>\n"
            "{bar}{rank}"
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
            "🎖 Level: {level}\n"
            "💰 Points: <b>{points}</b>\n"
            "🎮 Games: {games}\n"
            "🏆 Wins: {wins}\n"
            "💔 Losses: {losses}\n"
            "🤝 Draws: {draws}\n"
            "📊 Win rate: <b>{winrate}%</b>\n"
            "{bar}{rank}"
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
            "🎖 Уровень: {level}\n"
            "💰 Очки: <b>{points}</b>\n"
            "🎮 Игр: {games}\n"
            "🏆 Побед: {wins}\n"
            "💔 Поражений: {losses}\n"
            "🤝 Ничьих: {draws}\n"
            "📊 Процент побед: <b>{winrate}%</b>\n"
            "{bar}{rank}"
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
            "🎖 Деңгей: {level}\n"
            "💰 Ұпай: <b>{points}</b>\n"
            "🎮 Ойындар: {games}\n"
            "🏆 Жеңістер: {wins}\n"
            "💔 Жеңілістер: {losses}\n"
            "🤝 Тең ойындар: {draws}\n"
            "📊 Жеңіс пайызы: <b>{winrate}%</b>\n"
            "{bar}{rank}"
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
    migrate_legacy(c)

    for chat_id, language in c.execute("SELECT chat_id, language FROM group_languages"):
        if language in LANGS:
            LANG_CACHE[chat_id] = language


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
    """O'yin natijasini yozadi: games +1, g'alaba/mag'lubiyat/durang +1, ball."""
    col = OUTCOME_COL[outcome]
    c = db()
    with c:
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
    ])


def again_row(chat_id):
    return [InlineKeyboardButton(t(chat_id, "btn_again"), callback_data="g:menu")]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    if chat.type == ChatType.PRIVATE:
        username = context.bot.username
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                t(chat.id, "btn_add_group"),
                url=f"https://t.me/{username}?startgroup=true",
            )
        ]])
    else:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(t(chat.id, "btn_games"), callback_data="g:menu")
        ]])

    await msg.reply_text(t(chat.id, "start_text"), reply_markup=kb)


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
    private = chat.type == ChatType.PRIVATE
    points, games, wins, losses, draws = get_stats(chat.id, user.id, private)
    winrate = round(wins / games * 100, 1) if games else 0

    rank = ""
    if not private and games:
        rank = t(chat.id, "profile_rank", rank=get_rank(chat.id, points, wins))

    await msg.reply_text(
        t(
            chat.id,
            "profile",
            name=uname(user),
            level=level_name(chat.id, points),
            points=points,
            games=games,
            wins=wins,
            losses=losses,
            draws=draws,
            winrate=winrate,
            bar=bar(winrate),
            rank=rank,
        )
    )


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
        (["start"], cmd_start),
        (["emps", "games", "oyin"], cmd_emps),
        (["stop"], cmd_stop),
        (["reyting", "rating"], cmd_reyting),
        (["profil", "profile"], cmd_profil),
        (["qoidalar", "rules"], cmd_rules),
        (["help"], cmd_help),
        (["lang"], cmd_lang),
    ]
    for names, handler in commands:
        app.add_handler(CommandHandler(names, handler))

    app.add_handler(CallbackQueryHandler(cb_game, pattern=r"^g:(number|rsp|xo|menu)$"))
    app.add_handler(CallbackQueryHandler(cb_lang, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(cb_rsp_count, pattern=r"^rc:[235]$"))
    app.add_handler(CallbackQueryHandler(cb_rsp_join, pattern=r"^rj$"))
    app.add_handler(CallbackQueryHandler(cb_rsp_pick, pattern=r"^rp:(rock|scissors|paper)$"))
    app.add_handler(CallbackQueryHandler(cb_xo_join, pattern=r"^xj$"))
    app.add_handler(CallbackQueryHandler(cb_xo_move, pattern=r"^xm:[0-8]$"))
    # Boshqa barcha callback'larga ham javob beramiz (spinner qotib qolmasin)
    app.add_handler(CallbackQueryHandler(cb_noop))

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
