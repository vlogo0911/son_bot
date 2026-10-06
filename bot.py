import os
import random
import sqlite3
import logging
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "BU_YERGA_BOT_TOKEN")
DB_FILE = "game.db"

MIN_NUMBER = 1
MAX_NUMBER = 100

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DEFAULT_LANG = "uz"

LANGS = {
    "uz": {
        "lang_title": "🌐 Tilni tanlang:",
        "lang_set": "🌐 Guruh tili o‘zbekchaga o‘rnatildi.",
        "lang_private": "🌐 Til tanlandi: O‘zbekcha.",
        "use_group": "Bu buyruqni guruh ichida ishlating.",
        "choose_game": "🎮 O‘YIN TANLANG:",
        "number_game": "🎯 Son topish",
        "rsp_game": "✊ Tosh-Qaychi-Qog‘oz",
        "number_started": "🎯 Son topish boshlandi!\n1 dan 100 gacha sonni toping!",
        "number_exists": "🎯 Hozir guruhda son topish o‘yini ketmoqda!",
        "correct": "🎉 {name} sonni topdi: {number}!\n🏆 +10 ball",
        "higher": "📈 Kattaroq!",
        "lower": "📉 Kichikroq!",
        "rsp_count": "✊ Tosh-Qaychi-Qog‘oz\n\nNechta odam o‘ynaydi?",
        "rsp_exists": "⚠️ Hozir guruhda RSP o‘yini ketmoqda.",
        "rsp_wait": "✊ RSP boshlandi!\n\n{count} ta o‘yinchi kerak.\nPastdagi tugmani bosib o‘yinga qo‘shiling.",
        "rsp_joined": "{name} o‘yinga qo‘shildi! ({current}/{count})",
        "rsp_already": "Siz allaqachon o‘yinga qo‘shilgansiz.",
        "rsp_full": "O‘yinchilar to‘ldi!",
        "rsp_choose": "✊ Siz o‘yinga kirdingiz!\n\nTanlang:",
        "rsp_wait_choices": "⏳ {current}/{count} o‘yinchi tanlov qildi.\nG‘olib barcha tanlovdan keyin aniqlanadi.",
        "rsp_already_choice": "Siz tanlovingizni allaqachon berdingiz.",
        "rsp_result": "🏁 RSP NATIJASI\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 G‘olib: {names}\n💰 Har biriga +10 ball",
        "rsp_draw": "🤝 Durang!",
        "rsp_no_winner": "🤝 G‘olib yo‘q — uchala tanlov ham chiqdi.",
        "rsp_all_same": "🤝 Hamma bir xil tanladi. Durang!",
        "rating_title": "🏆 TOP 10 REYTING",
        "rating_row": "{i}. {name} — {points} ball | {wins} g‘alaba",
        "rating_empty": "Hali reyting mavjud emas.",
        "profile": "👤 Profil\n\n"
                   "📝 O‘yinlar: {games}\n"
                   "🏆 G‘alabalar: {wins}\n"
                   "❌ Mag‘lubiyatlar: {losses}\n"
                   "💰 Ball: {points}\n"
                   "📊 G‘alaba foizi: {winrate}%",
        "rules": "📚 QOIDALAR\n\n"
                 "🎯 Son topish:\n"
                 "Bot 1–100 oralig‘ida son o‘ylaydi. Guruhdagilar son yuboradi. "
                 "Bot kattaroq yoki kichikroq deb yo‘l ko‘rsatadi. "
                 "To‘g‘ri topgan odam +10 ball oladi.\n\n"
                 "✊ RSP:\n"
                 "2, 3 yoki 5 kishi o‘ynaydi. "
                 "Barcha o‘yinchilar tanlov qilmaguncha natija chiqmaydi. "
                 "G‘oliblar +10 ball oladi.\n\n"
                 "📊 /reyting — guruh reytingi\n"
                 "👤 /profil — profilingiz\n"
                 "🌐 /lang — guruh tilini tanlash",
        "help": "🤖 BUYRUQLAR\n\n"
               "/emps — o‘yin tanlash\n"
               "/reyting — reyting\n"
               "/profil — profil\n"
               "/qoidalar — qoidalar\n"
               "/lang — til tanlash\n"
               "/help — yordam",
        "private_start": "🤖 Bot ishlayapti!\n\nO‘yinni guruhda /emps buyrug‘i orqali boshlang.",
        "rsp_rock": "✊ Tosh",
        "rsp_scissors": "✂️ Qaychi",
        "rsp_paper": "📄 Qog‘oz",
    },

    "eng": {
        "lang_title": "🌐 Choose a language:",
        "lang_set": "🌐 Group language has been set to English.",
        "lang_private": "🌐 Language selected: English.",
        "use_group": "Use this command inside a group.",
        "choose_game": "🎮 CHOOSE A GAME:",
        "number_game": "🎯 Guess the Number",
        "rsp_game": "✊ Rock-Paper-Scissors",
        "number_started": "🎯 Guess the Number started!\nGuess a number from 1 to 100!",
        "number_exists": "🎯 A number game is already running in this group!",
        "correct": "🎉 {name} guessed the number: {number}!\n🏆 +10 points",
        "higher": "📈 Higher!",
        "lower": "📉 Lower!",
        "rsp_count": "✊ Rock-Paper-Scissors\n\nHow many players?",
        "rsp_exists": "⚠️ A RPS game is already running in this group.",
        "rsp_wait": "✊ RPS started!\n\n{count} players needed.\nPress the button below to join.",
        "rsp_joined": "{name} joined! ({current}/{count})",
        "rsp_already": "You have already joined.",
        "rsp_full": "Players are full!",
        "rsp_choose": "✊ You joined the game!\n\nChoose:",
        "rsp_wait_choices": "⏳ {current}/{count} players have chosen.\nThe winner will be announced after everyone chooses.",
        "rsp_already_choice": "You have already made your choice.",
        "rsp_result": "🏁 RPS RESULT\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 Winner: {names}\n💰 +10 points each",
        "rsp_draw": "🤝 Draw!",
        "rsp_no_winner": "🤝 No winner — all three choices appeared.",
        "rsp_all_same": "🤝 Everyone chose the same. Draw!",
        "rating_title": "🏆 TOP 10 RATING",
        "rating_row": "{i}. {name} — {points} points | {wins} wins",
        "rating_empty": "No rating yet.",
        "profile": "👤 Profile\n\n"
                   "📝 Games: {games}\n"
                   "🏆 Wins: {wins}\n"
                   "❌ Losses: {losses}\n"
                   "💰 Points: {points}\n"
                   "📊 Win rate: {winrate}%",
        "rules": "📚 RULES\n\n"
                 "🎯 Guess the Number:\n"
                 "The bot chooses a number from 1–100. Players send guesses. "
                 "The bot gives higher/lower hints. The first correct player gets +10 points.\n\n"
                 "✊ RPS:\n"
                 "2, 3 or 5 players can play. The result is shown only after everyone chooses. "
                 "Winners get +10 points.\n\n"
                 "📊 /reyting — group rating\n"
                 "👤 /profil — your profile\n"
                 "🌐 /lang — choose group language",
        "help": "🤖 COMMANDS\n\n"
               "/emps — choose a game\n"
               "/reyting — rating\n"
               "/profil — profile\n"
               "/qoidalar — rules\n"
               "/lang — choose language\n"
               "/help — help",
        "private_start": "🤖 Bot is working!\n\nStart a game in a group with /emps.",
        "rsp_rock": "✊ Rock",
        "rsp_scissors": "✂️ Scissors",
        "rsp_paper": "📄 Paper",
    },

    "ru": {
        "lang_title": "🌐 Выберите язык:",
        "lang_set": "🌐 Язык группы установлен: русский.",
        "lang_private": "🌐 Выбран язык: русский.",
        "use_group": "Используйте эту команду в группе.",
        "choose_game": "🎮 ВЫБЕРИТЕ ИГРУ:",
        "number_game": "🎯 Угадай число",
        "rsp_game": "✊ Камень-Ножницы-Бумага",
        "number_started": "🎯 Игра началась!\nУгадайте число от 1 до 100!",
        "number_exists": "🎯 В группе уже идёт игра в угадывание числа!",
        "correct": "🎉 {name} угадал число: {number}!\n🏆 +10 очков",
        "higher": "📈 Больше!",
        "lower": "📉 Меньше!",
        "rsp_count": "✊ Камень-Ножницы-Бумага\n\nСколько игроков?",
        "rsp_exists": "⚠️ Игра КНБ уже идёт.",
        "rsp_wait": "✊ КНБ началась!\n\nНужно игроков: {count}.\nНажмите кнопку ниже, чтобы присоединиться.",
        "rsp_joined": "{name} присоединился! ({current}/{count})",
        "rsp_already": "Вы уже присоединились.",
        "rsp_full": "Все места заняты!",
        "rsp_choose": "✊ Вы присоединились!\n\nВыберите:",
        "rsp_wait_choices": "⏳ Выбор сделали {current}/{count} игроков.\nРезультат будет после выбора всех.",
        "rsp_already_choice": "Вы уже сделали выбор.",
        "rsp_result": "🏁 РЕЗУЛЬТАТ КНБ\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 Победитель: {names}\n💰 Каждому +10 очков",
        "rsp_draw": "🤝 Ничья!",
        "rsp_no_winner": "🤝 Победителя нет — появились все три варианта.",
        "rsp_all_same": "🤝 Все выбрали одинаково. Ничья!",
        "rating_title": "🏆 ТОП 10 РЕЙТИНГА",
        "rating_row": "{i}. {name} — {points} очков | {wins} побед",
        "rating_empty": "Рейтинг пока пуст.",
        "profile": "👤 Профиль\n\n"
                   "📝 Игр: {games}\n"
                   "🏆 Побед: {wins}\n"
                   "❌ Поражений: {losses}\n"
                   "💰 Очков: {points}\n"
                   "📊 Процент побед: {winrate}%",
        "rules": "📚 ПРАВИЛА\n\n"
                 "🎯 Угадай число:\n"
                 "Бот выбирает число от 1 до 100. Игроки отправляют варианты. "
                 "Бот подсказывает больше/меньше. Угадавший получает +10 очков.\n\n"
                 "✊ КНБ:\n"
                 "Играют 2, 3 или 5 человек. Результат появляется после выбора всех игроков. "
                 "Победители получают +10 очков.\n\n"
                 "📊 /reyting — рейтинг группы\n"
                 "👤 /profil — профиль\n"
                 "🌐 /lang — выбор языка",
        "help": "🤖 КОМАНДЫ\n\n"
               "/emps — выбрать игру\n"
               "/reyting — рейтинг\n"
               "/profil — профиль\n"
               "/qoidalar — правила\n"
               "/lang — выбрать язык\n"
               "/help — помощь",
        "private_start": "🤖 Бот работает!\n\nЗапустите игру в группе командой /emps.",
        "rsp_rock": "✊ Камень",
        "rsp_scissors": "✂️ Ножницы",
        "rsp_paper": "📄 Бумага",
    },

    "kz": {
        "lang_title": "🌐 Тілді таңдаңыз:",
        "lang_set": "🌐 Топтың тілі қазақша болып орнатылды.",
        "lang_private": "🌐 Таңдалған тіл: қазақша.",
        "use_group": "Бұл команданы топ ішінде қолданыңыз.",
        "choose_game": "🎮 ОЙЫНДЫ ТАҢДАҢЫЗ:",
        "number_game": "🎯 Сан тап",
        "rsp_game": "✊ Тас-Қайшы-Қағаз",
        "number_started": "🎯 Сан табу ойыны басталды!\n1 мен 100 арасындағы санды табыңыз!",
        "number_exists": "🎯 Топта сан табу ойыны жүріп жатыр!",
        "correct": "🎉 {name} санды тапты: {number}!\n🏆 +10 ұпай",
        "higher": "📈 Үлкенірек!",
        "lower": "📉 Кішірек!",
        "rsp_count": "✊ Тас-Қайшы-Қағаз\n\nҚанша ойыншы ойнайды?",
        "rsp_exists": "⚠️ Топта RPS ойыны жүріп жатыр.",
        "rsp_wait": "✊ RPS басталды!\n\n{count} ойыншы керек.\nТөмендегі батырманы басып қосылыңыз.",
        "rsp_joined": "{name} ойынға қосылды! ({current}/{count})",
        "rsp_already": "Сіз ойынға әлдеқашан қосылдыңыз.",
        "rsp_full": "Ойыншылар саны толды!",
        "rsp_choose": "✊ Сіз ойынға қосылдыңыз!\n\nТаңдаңыз:",
        "rsp_wait_choices": "⏳ {current}/{count} ойыншы таңдау жасады.\nБарлығы таңдағаннан кейін нәтиже шығады.",
        "rsp_already_choice": "Сіз таңдауыңызды жасап қойдыңыз.",
        "rsp_result": "🏁 RPS НӘТИЖЕСІ\n\n{players}\n\n{result}",
        "rsp_winner": "🏆 Жеңімпаз: {names}\n💰 Әрқайсысына +10 ұпай",
        "rsp_draw": "🤝 Тең ойын!",
        "rsp_no_winner": "🤝 Жеңімпаз жоқ — үш таңдау да шықты.",
        "rsp_all_same": "🤝 Барлығы бірдей таңдады. Тең ойын!",
        "rating_title": "🏆 ТОП 10 РЕЙТИНГ",
        "rating_row": "{i}. {name} — {points} ұпай | {wins} жеңіс",
        "rating_empty": "Рейтинг әлі жоқ.",
        "profile": "👤 Профиль\n\n"
                   "📝 Ойындар: {games}\n"
                   "🏆 Жеңістер: {wins}\n"
                   "❌ Жеңілістер: {losses}\n"
                   "💰 Ұпай: {points}\n"
                   "📊 Жеңіс пайызы: {winrate}%",
        "rules": "📚 ЕРЕЖЕЛЕР\n\n"
                 "🎯 Сан тап:\n"
                 "Бот 1–100 арасынан сан таңдайды. Ойыншылар сан жібереді. "
                 "Бот үлкен/кіші екенін көрсетеді. Дұрыс тапқан ойыншы +10 ұпай алады.\n\n"
                 "✊ RPS:\n"
                 "2, 3 немесе 5 адам ойнайды. Барлығы таңдағанша нәтиже көрсетілмейді. "
                 "Жеңімпаздар +10 ұпай алады.\n\n"
                 "📊 /reyting — топ рейтингі\n"
                 "👤 /profil — профиль\n"
                 "🌐 /lang — тіл таңдау",
        "help": "🤖 БҰЙРЫҚТАР\n\n"
               "/emps — ойын таңдау\n"
               "/reyting — рейтинг\n"
               "/profil — профиль\n"
               "/qoidalar — ережелер\n"
               "/lang — тіл таңдау\n"
               "/help — көмек",
        "private_start": "🤖 Бот жұмыс істеп тұр!\n\nТопта /emps арқылы ойынды бастаңыз.",
        "rsp_rock": "✊ Тас",
        "rsp_scissors": "✂️ Қайшы",
        "rsp_paper": "📄 Қағаз",
    },
}


def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            points INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            chat_id INTEGER PRIMARY KEY,
            number INTEGER,
            attempts INTEGER DEFAULT 0,
            active INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_languages (
            chat_id INTEGER PRIMARY KEY,
            language TEXT NOT NULL DEFAULT 'uz'
        )
    """)

    conn.commit()
    conn.close()


def get_group_lang(chat_id):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT language FROM group_languages WHERE chat_id = ?",
        (chat_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row and row[0] in LANGS:
        return row[0]

    return DEFAULT_LANG


def set_group_lang(chat_id, language):
    if language not in LANGS:
        language = DEFAULT_LANG

    conn = db()
    conn.execute("""
        INSERT INTO group_languages(chat_id, language)
        VALUES (?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET language = excluded.language
    """, (chat_id, language))
    conn.commit()
    conn.close()


def t(chat_id, key, **kwargs):
    language = get_group_lang(chat_id)
    text = LANGS[language].get(key, LANGS[DEFAULT_LANG].get(key, key))
    return text.format(**kwargs)


def save_user(user):
    conn = db()
    conn.execute("""
        INSERT INTO users(user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (
        user.id,
        user.username,
        user.first_name,
    ))
    conn.commit()
    conn.close()


def add_points(user_id, points):
    conn = db()
    conn.execute(
        "UPDATE users SET points = points + ? WHERE user_id = ?",
        (points, user_id),
    )
    conn.commit()
    conn.close()


def add_game_stats(user_id, win=False):
    conn = db()

    if win:
        conn.execute("""
            UPDATE users
            SET games = games + 1,
                wins = wins + 1
            WHERE user_id = ?
        """, (user_id,))
    else:
        conn.execute("""
            UPDATE users
            SET games = games + 1
            WHERE user_id = ?
        """, (user_id,))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT points, games, wins
        FROM users
        WHERE user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_game(chat_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT number, attempts, active
        FROM games
        WHERE chat_id = ?
    """, (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row


def create_game(chat_id):
    number = random.randint(MIN_NUMBER, MAX_NUMBER)

    conn = db()
    conn.execute("""
        INSERT INTO games(chat_id, number, attempts, active)
        VALUES (?, ?, 0, 1)
        ON CONFLICT(chat_id) DO UPDATE SET
            number = excluded.number,
            attempts = 0,
            active = 1
    """, (chat_id, number))
    conn.commit()
    conn.close()


def update_attempts(chat_id):
    conn = db()
    conn.execute("""
        UPDATE games
        SET attempts = attempts + 1
        WHERE chat_id = ?
    """, (chat_id,))
    conn.commit()
    conn.close()


def finish_game(chat_id):
    conn = db()
    conn.execute(
        "UPDATE games SET active = 0 WHERE chat_id = ?",
        (chat_id,),
    )
    conn.commit()
    conn.close()


def display_name(user):
    if user.username:
        return "@" + user.username
    return user.first_name or "Noma'lum"


rsp_games = {}

RSP_CHOICES = {
    "rock": "rsp_rock",
    "scissors": "rsp_scissors",
    "paper": "rsp_paper",
}

RSP_BEATS = {
    "rock": "scissors",
    "scissors": "paper",
    "paper": "rock",
}


def emps_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Son topish", callback_data="emps_number"),
        ],
        [
            InlineKeyboardButton("✊ RSP", callback_data="emps_rsp"),
        ],
    ])


async def emps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "Bu buyruqni guruh ichida ishlating."
        )
        return

    await update.message.reply_text(
        t(update.effective_chat.id, "choose_game"),
        reply_markup=emps_keyboard(),
    )


def rsp_count_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 2", callback_data="rsp_count_2"),
            InlineKeyboardButton("👥 3", callback_data="rsp_count_3"),
            InlineKeyboardButton("👥 5", callback_data="rsp_count_5"),
        ]
    ])


async def start_rsp_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id

    await query.answer()

    if chat_id in rsp_games:
        await query.message.reply_text(
            t(chat_id, "rsp_exists")
        )
        return

    await query.message.reply_text(
        t(chat_id, "rsp_count"),
        reply_markup=rsp_count_keyboard(),
    )


async def create_rsp(update: Update, count):
    query = update.callback_query
    chat_id = query.message.chat.id

    await query.answer()

    if chat_id in rsp_games:
        await query.message.reply_text(
            t(chat_id, "rsp_exists")
        )
        return

    rsp_games[chat_id] = {
        "count": count,
        "players": {},
        "choices": {},
    }

    lang = get_group_lang(chat_id)

    join_labels = {
        "uz": "✊ Qo‘shilish",
        "eng": "✊ Join",
        "ru": "✊ Присоединиться",
        "kz": "✊ Қосылу",
    }

    await query.message.reply_text(
        t(chat_id, "rsp_wait", count=count),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    join_labels.get(lang, "✊ Qo‘shilish"),
                    callback_data="rsp_join"
                )
            ]
        ]),
    )


def rsp_choice_keyboard(chat_id):
    lang = get_group_lang(chat_id)

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✊ " + LANGS[lang]["rsp_rock"].split(" ", 1)[-1],
                callback_data="rsp_choice_rock",
            ),
            InlineKeyboardButton(
                "✂️ " + LANGS[lang]["rsp_scissors"].split(" ", 1)[-1],
                callback_data="rsp_choice_scissors",
            ),
            InlineKeyboardButton(
                "📄 " + LANGS[lang]["rsp_paper"].split(" ", 1)[-1],
                callback_data="rsp_choice_paper",
            ),
        ]
    ])


async def rsp_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    user = query.from_user

    await query.answer()

    game = rsp_games.get(chat_id)

    if not game:
        await query.message.reply_text(
            t(chat_id, "rsp_full")
        )
        return

    if user.id in game["players"]:
        await query.answer(
            t(chat_id, "rsp_already"),
            show_alert=True,
        )
        return

    if len(game["players"]) >= game["count"]:
        await query.answer(
            t(chat_id, "rsp_full"),
            show_alert=True,
        )
        return

    save_user(user)

    game["players"][user.id] = display_name(user)

    current = len(game["players"])

    await query.message.reply_text(
        t(
            chat_id,
            "rsp_joined",
            name=escape(display_name(user)),
            current=current,
            count=game["count"],
        )
    )

    if current == game["count"]:
        await query.message.reply_text(
            t(chat_id, "rsp_choose"),
            reply_markup=rsp_choice_keyboard(chat_id),
        )


async def rsp_choice(update: Update, choice):
    query = update.callback_query
    chat_id = query.message.chat.id
    user = query.from_user

    game = rsp_games.get(chat_id)

    if not game:
        await query.answer()
        return

    if user.id not in game["players"]:
        await query.answer(
            t(chat_id, "rsp_already"),
            show_alert=True,
        )
        return

    if user.id in game["choices"]:
        await query.answer(
            t(chat_id, "rsp_already_choice"),
            show_alert=True,
        )
        return

    game["choices"][user.id] = choice

    await query.answer("✅")

    current = len(game["choices"])
    count = game["count"]

    status_text = t(
        chat_id,
        "rsp_wait_choices",
        current=current,
        count=count,
    )

    status_message_id = game.get("status_message_id")

    if status_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text=status_text,
            )
        except Exception:
            pass

    if current >= count:
        await finish_rsp(query, chat_id)


async def finish_rsp(query, chat_id):
    game = rsp_games.get(chat_id)

    if not game:
        return

    choices = game["choices"]

    players_lines = []

    for user_id, choice in choices.items():
        name = escape(game["players"][user_id])
        lang = get_group_lang(chat_id)
        choice_text = LANGS[lang][RSP_CHOICES[choice]]
        players_lines.append(f"{name} — {choice_text}")

    choice_values = set(choices.values())

    winners = []

    if len(choice_values) == 1:
        result = t(chat_id, "rsp_all_same")

    elif len(choice_values) == 3:
        result = t(chat_id, "rsp_no_winner")

    else:
        winner_choice = None

        for a in choice_values:
            for b in choice_values:
                if a != b and RSP_BEATS[a] == b:
                    winner_choice = a
                    break
            if winner_choice:
                break

        for user_id, choice in choices.items():
            if choice == winner_choice:
                winners.append(user_id)

        if winners:
            winner_names = ", ".join(
                escape(game["players"][uid])
                for uid in winners
            )

            result = t(
                chat_id,
                "rsp_winner",
                names=winner_names,
            )

            for uid in winners:
                add_points(uid, 10)

            for uid in choices:
                add_game_stats(uid, uid in winners)
        else:
            result = t(chat_id, "rsp_draw")

    if len(choice_values) <= 1:
        for uid in choices:
            add_game_stats(uid, False)

    players_text = "\n".join(players_lines)

    await query.message.reply_text(
        t(
            chat_id,
            "rsp_result",
            players=players_text,
            result=result,
        )
    )

    del rsp_games[chat_id]


async def reyting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT username, first_name, points, wins
        FROM users
        ORDER BY points DESC, wins DESC
        LIMIT 10
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            t(chat_id, "rating_empty")
        )
        return

    text = t(chat_id, "rating_title") + "\n\n"

    for i, row in enumerate(rows, 1):
        username, first_name, points, wins = row
        name = "@" + username if username else (first_name or "User")

        text += t(
            chat_id,
            "rating_row",
            i=i,
            name=escape(name),
            points=points,
            wins=wins,
        ) + "\n"

    await update.message.reply_text(text)


async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    save_user(user)

    row = get_user(user.id)

    if not row:
        return

    points, games, wins = row
    losses = max(0, games - wins)
    winrate = round((wins / games) * 100, 1) if games else 0

    await update.message.reply_text(
        t(
            chat_id,
            "profile",
            games=games,
            wins=wins,
            losses=losses,
            points=points,
            winrate=winrate,
        )
    )


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        t(update.effective_chat.id, "rules")
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        t(update.effective_chat.id, "help")
    )


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await update.message.reply_text(
            "🌐 /lang buyrug‘ini guruh ichida ishlating."
        )
        return

    me = await context.bot.get_me()
    username = me.username

    chat_id = chat.id

    buttons = [
        [
            InlineKeyboardButton(
                "🇺🇿 O‘zbekcha",
                url=f"https://t.me/{username}?start=lang_{chat_id}_uz",
            )
        ],
        [
            InlineKeyboardButton(
                "🇬🇧 English",
                url=f"https://t.me/{username}?start=lang_{chat_id}_eng",
            )
        ],
        [
            InlineKeyboardButton(
                "🇷🇺 Русский",
                url=f"https://t.me/{username}?start=lang_{chat_id}_ru",
            )
        ],
        [
            InlineKeyboardButton(
                "🇰🇿 Қазақша",
                url=f"https://t.me/{username}?start=lang_{chat_id}_kz",
            )
        ],
    ]

    await update.message.reply_text(
        t(chat_id, "lang_title"),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not context.args:
        await update.message.reply_text(
            t(chat.id, "private_start")
        )
        return

    payload = context.args[0]

    if not payload.startswith("lang_"):
        await update.message.reply_text(
            t(chat.id, "private_start")
        )
        return

    try:
        data = payload[len("lang_"):]
        group_id_str, language = data.rsplit("_", 1)
        group_id = int(group_id_str)

        if language not in LANGS:
            await update.message.reply_text(
                "❌ Noma’lum til."
            )
            return

        set_group_lang(group_id, language)

        await update.message.reply_text(
            LANGS[language]["lang_private"]
        )

        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=LANGS[language]["lang_set"],
            )
        except Exception as e:
            logger.warning("Group language message error: %s", e)

    except Exception as e:
        logger.warning("Language payload error: %s", e)
        await update.message.reply_text(
            t(chat.id, "private_start")
        )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "emps_number":
        chat_id = query.message.chat.id

        await query.answer()

        if get_game(chat_id) and get_game(chat_id)[2] == 1:
            await query.message.reply_text(
                t(chat_id, "number_exists")
            )
            return

        create_game(chat_id)

        await query.message.reply_text(
            t(chat_id, "number_started")
        )

    elif data == "emps_rsp":
        await start_rsp_selection(update, context)

    elif data.startswith("rsp_count_"):
        count = int(data.split("_")[-1])
        await create_rsp(update, count)

    elif data == "rsp_join":
        await rsp_join(update, context)

    elif data.startswith("rsp_choice_"):
        choice = data.replace("rsp_choice_", "")
        await rsp_choice(update, choice)


async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message or not message.text:
        return

    if message.chat.type == "private":
        return

    try:
        guess = int(message.text.strip())
    except ValueError:
        return

    if guess < MIN_NUMBER or guess > MAX_NUMBER:
        return

    chat_id = message.chat.id
    game = get_game(chat_id)

    if not game or game[2] != 1:
        return

    user = message.from_user
    save_user(user)

    number = game[0]

    update_attempts(chat_id)

    if guess == number:
        finish_game(chat_id)

        add_points(user.id, 10)
        add_game_stats(user.id, True)

        await message.reply_text(
            t(
                chat_id,
                "correct",
                name=escape(display_name(user)),
                number=number,
            )
        )

    elif guess < number:
        await message.reply_text(
            t(chat_id, "higher")
        )

    else:
        await message.reply_text(
            t(chat_id, "lower")
        )


def main():
    if BOT_TOKEN == "BU_YERGA_BOT_TOKEN":
        print("BOT_TOKEN o‘rnatilmagan!")
        return

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("emps", emps)
    )

    application.add_handler(
        CommandHandler("lang", lang_command)
    )

    application.add_handler(
        CommandHandler("reyting", reyting)
    )

    application.add_handler(
        CommandHandler("profil", profil)
    )

    application.add_handler(
        CommandHandler("qoidalar", rules)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CallbackQueryHandler(callbacks)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_number,
        )
    )

    print("Bot ishga tushdi...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
