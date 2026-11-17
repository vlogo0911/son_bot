"""Owner-only SQLite backup and staged restore for Son Bot."""
import asyncio
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

_PENDING_SUFFIX = ".restore_pending"
_MAX_DB_BYTES = 45 * 1024 * 1024

def apply_pending_restore(db_file):
    """Run before init_db and before opening any SQLite connection."""
    pending = Path(str(db_file) + _PENDING_SUFFIX)
    if not pending.exists():
        return
    target = Path(db_file)
    with sqlite3.connect(str(pending)) as src:
        if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Restore pending DB integrity check failed")
    if target.exists():
        backup = target.with_name(target.name + ".before_restore_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
        with sqlite3.connect(str(target)) as src, sqlite3.connect(str(backup)) as dst:
            src.backup(dst)
    os.replace(str(pending), str(target))
    print("SQLite restore applied before bot startup")

def register(app, db_file, owners):
    db_file = str(db_file)
    owners = set(owners)
    def allowed(update):
        return bool(update.effective_user and update.effective_user.id in owners
                    and update.effective_chat and update.effective_chat.type == "private")

    async def menu(update, context):
        if not allowed(update):
            return
        await update.effective_message.reply_text(
            "🗄 Son Bot — baza boshqaruvi\n"
            "DB saqlash: bazaning to‘liq nusxasini Telegramga yuboradi.\n"
            "DB ga yuklash: bazani keyingi restartda tiklashga tayyorlaydi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 DB saqlash", callback_data="dbtransfer:save")],
                [InlineKeyboardButton("📤 DB ga yuklash", callback_data="dbtransfer:load")]
            ]))

    async def callback(update, context):
        q = update.callback_query
        if not allowed(update):
            await q.answer("Ruxsat yo‘q", show_alert=True)
            return
        await q.answer()
        if q.data == "dbtransfer:save":
            await q.message.reply_text("Baza nusxasi tayyorlanmoqda...")
            def make_backup():
                fd, path = tempfile.mkstemp(suffix=".db")
                os.close(fd)
                try:
                    with sqlite3.connect(db_file, timeout=30) as src, sqlite3.connect(path) as dst:
                        src.backup(dst)
                    return path
                except Exception:
                    os.unlink(path)
                    raise
            path = await asyncio.to_thread(make_backup)
            try:
                with open(path, "rb") as file:
                    await q.message.reply_document(
                        document=file,
                        filename="son_bot_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + ".db",
                        caption="Son Bot SQLite backup. Maxfiy saqlang; boshqa odamlarga yubormang.",
                        read_timeout=120, write_timeout=120)
            finally:
                os.unlink(path)
        elif q.data == "dbtransfer:load":
            context.user_data["dbtransfer_wait"] = True
            await q.message.reply_text("Yangi .db faylni shu shaxsiy chatga hujjat sifatida yuboring. "
                                       "Fayl tekshiriladi va keyin alohida tasdiq so‘raladi.")
        elif q.data == "dbtransfer:confirm":
            path = context.user_data.pop("dbtransfer_candidate", None)
            if not path or not os.path.exists(path):
                await q.message.reply_text("Fayl topilmadi. /data dan qayta boshlang.")
                return
            os.replace(path, db_file + _PENDING_SUFFIX)
            await q.message.reply_text(
                "✅ Baza tiklashga tayyor. Endi Railway'da bot servisiga RESTART bering. "
                "Yangi baza bot ishga tushishidan OLDIN tiklanadi. "
                "Eski serverni avval to‘xtating! Backup nusxasini saqlang.")
        elif q.data == "dbtransfer:cancel":
            path = context.user_data.pop("dbtransfer_candidate", None)
            if path and os.path.exists(path):
                os.unlink(path)
            context.user_data.pop("dbtransfer_wait", None)
            await q.message.reply_text("Bekor qilindi.")

    async def document(update, context):
        if not allowed(update) or not context.user_data.pop("dbtransfer_wait", False):
            return
        doc = update.effective_message.document
        if not doc or not doc.file_name or not doc.file_name.lower().endswith(".db"):
            await update.effective_message.reply_text("Faqat .db fayl yuboring. /data dan qayta boshlang.")
            return
        if doc.file_size and doc.file_size > _MAX_DB_BYTES:
            await update.effective_message.reply_text("Fayl 45 MB dan katta. Boshqa usul kerak.")
            return
        fd, path = tempfile.mkstemp(suffix=".db", dir=str(Path(db_file).parent))
        os.close(fd)
        try:
            tg_file = await doc.get_file()
            await tg_file.download_to_drive(custom_path=path)
            if os.path.getsize(path) > _MAX_DB_BYTES:
                raise ValueError("Fayl juda katta")
            def verify():
                with sqlite3.connect(path) as incoming:
                    if incoming.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite integrity_check muvaffaqiyatsiz")
                    tables = {x[0] for x in incoming.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                with sqlite3.connect(db_file) as current:
                    existing = {x[0] for x in current.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                overlap = (tables & existing) - {"sqlite_sequence"}
                if len(overlap) < 3:
                    raise ValueError("Bu Son Bot bazasiga o‘xshamaydi: umumiy jadvallar kam")
                return len(tables), len(overlap)
            tables, overlap = await asyncio.to_thread(verify)
            old = context.user_data.pop("dbtransfer_candidate", None)
            if old and os.path.exists(old):
                os.unlink(old)
            context.user_data["dbtransfer_candidate"] = path
            await update.effective_message.reply_text(
                f"Tekshirildi: {tables} ta jadval, {overlap} tasi hozirgi baza bilan mos.\n"
                "DIQQAT: Tasdiqlasangiz, restart paytida hozirgi baza almashtiriladi. "
                "Yangi serverga ko‘chirishda eski serverni avval to‘xtating.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data="dbtransfer:confirm"),
                    InlineKeyboardButton("❌ Bekor qilish", callback_data="dbtransfer:cancel")
                ]]))
        except Exception as exc:
            if os.path.exists(path):
                os.unlink(path)
            await update.effective_message.reply_text(f"DB qabul qilinmadi: {str(exc)[:250]}")

    app.add_handler(CommandHandler("data", menu), group=-10)
    app.add_handler(CallbackQueryHandler(callback, pattern=r"^dbtransfer:(save|load|confirm|cancel)$"), group=-10)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Document.ALL, document), group=-10)
