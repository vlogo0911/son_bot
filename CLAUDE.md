# son_bot (@empire_statsbot)

- Asosiy fayl: `bot.py` (Railway `Procfile`: `worker: python bot.py`). Barcha o'zgarishlar shu faylda qilinadi.
  Foydalanuvchi yuklagan `probot.zip` ichidagi `bot.py` shu repodagi bilan bir xil; zip'dagi
  `*.backup*` / `*.before_*` fayllar faqat eski zaxira nusxalar.
- Railway shu repodan avtomatik deploy qiladi (GitHub commit statuslarida ko'rinadi).
- Bot `BOT_TOKEN` env'dan o'qiydi; baza `RAILWAY_VOLUME_MOUNT_PATH/game.db` (volume bo'lmasa repo ichidagi `game.db`).
- Tillar: `uz`, `eng`, `ru`, `kz` (`LANGS`, `CRASH_TEXT`, ...).
- `/emps` menyusi: `menu_kb()`; pul tikiladigan o'yinlar `🎰 Casino` bo'limida (`casino_kb()`) —
  yangi casino o'yinlari shu yerga qo'shiladi.
- Inline rejim (`@empire_statsbot` shaxsiy yozishmada): yashirin xabar + XO / RSP / Crash.
  Inline o'yinlar `GAMES` ichida `"i:<inline_message_id>"` kaliti bilan saqlanadi (`game_key`, `msg_target`).
- Guruhda bot egasi (`CAREER_OWNER_IDS`) yoki u ruxsat bergan a'zo (`can_tag`) "bot" deb yozsa — har bir a'zo alohida xabarda belgilanadi
  (`maybe_tag_all`); "bot kelish" → har biri "@username kelish"; "stop" to'xtatadi; "tez 0.7" — guruh uchun xabarlar oralig'i (0.7–1.5 s, `tag_speed` jadvali). A'zolar `group_members` jadvalida yig'iladi
  (`track_group_member`, `on_chat_member`), chunki Telegram API to'liq ro'yxatni bermaydi.
  Bot egasi xabarga reply qilib "ruxsat" / "xayr" yozsa — tag huquqi beriladi / olinadi (`tag_permissions`, guruh bo'yicha).
- `/aktiv` (faqat guruh adminlari va bot egalari): guruhdagi eng faol 15 a'zo (xabarlar soni + eng ko'p yozgan so'zi). Hisob `count_activity` orqali
  `member_activity` / `member_words` jadvallarida, funksiya qo'shilgan paytdan boshlab yig'iladi.
