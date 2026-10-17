# son_bot (@empire_statsbot)

- Asosiy fayl: `bot.py` (Railway `Procfile`: `worker: python bot.py`). Barcha o'zgarishlar shu faylda qilinadi.
  Foydalanuvchi yuklagan `probot.zip` ichidagi `bot.py` shu repodagi bilan bir xil; zip'dagi
  `*.backup*` / `*.before_*` fayllar faqat eski zaxira nusxalar.
- Railway shu repodan avtomatik deploy qiladi (GitHub commit statuslarida ko'rinadi).
- Bot `BOT_TOKEN` env'dan o'qiydi; baza `RAILWAY_VOLUME_MOUNT_PATH/game.db` (volume bo'lmasa repo ichidagi `game.db`).
- Tillar: `uz`, `eng`, `ru`, `kz` (`LANGS`, `CRASH_TEXT`, ...).
- `/emps` menyusi: `menu_kb()`; pul tikiladigan o'yinlar `🎰 Casino` bo'limida (`casino_kb()`) —
  yangi casino o'yinlari shu yerga qo'shiladi.
- 🐸 Qurbaqa (`cb_frog`, `fr:` callback'lar): Casino'da va inline'da. 5×4 nilufar barglari, rejim (oson/o'rta/qiyin =
  qatorda 1/2/3 xavf, har o'yin tasodifiy), depozit hamyondan. O'yinlar `FROG_GAMES` da xabar bo'yicha saqlanadi
  (GAMES'ni band qilmaydi); restartda `post_shutdown` yutuq/depozitni qaytaradi.
- Inline rejim (`@empire_statsbot` shaxsiy yozishmada): yashirin xabar + XO / RSP / Juftini top / Qurbaqa / Crash.
  Inline o'yinlar `GAMES` ichida `"i:<inline_message_id>"` kaliti bilan saqlanadi (`game_key`, `msg_target`).
- Guruhda bot egasi (`CAREER_OWNER_IDS`) yoki u ruxsat bergan a'zo (`can_tag`) "bot" deb yozsa — har bir a'zo alohida xabarda belgilanadi
  (`maybe_tag_all`); "bot kelish" → har biri "@username kelish"; "stop" to'xtatadi; "tez 0.7" — guruh uchun xabarlar oralig'i (0.7–1.5 s, `tag_speed` jadvali). A'zolar `group_members` jadvalida yig'iladi
  (`track_group_member`, `on_chat_member`), chunki Telegram API to'liq ro'yxatni bermaydi.
  Bot egasi xabarga reply qilib "ruxsat" / "xayr" yozsa — tag huquqi beriladi / olinadi (`tag_permissions`, guruh bo'yicha).
- `/aktiv` (faqat guruh adminlari va bot egalari): guruhdagi eng faol 15 a'zo (xabarlar soni + eng ko'p yozgan so'zi). Hisob `count_activity` orqali
  `member_activity` / `member_words` jadvallarida, funksiya qo'shilgan paytdan boshlab yig'iladi.
- Owner panel → 💰 Pul statistikasi (`panel:money`, `panel_money_text`): faqat bot egalari; jami pul, egalarda /
  foydalanuvchilarda, o'yinlarda tikilgan (`money_in_games`), o'rtacha, eng boy 10.
- /profil → 🏦 Banklar / 📈 Birja / 👶 Farzandlarim — URL tugmalar (`?start=bank|birja|kids`, `cmd_start`),
  bo'lim shaxsiy chatda ochiladi.
- 🏦 Banklar (`cb_bank`, `bk:<uid>:...`): Gold Invest. Kredit kuniga 13%, 1–7 kun, birinchisi 1 000$, keyingilari
  1 000–50 000$; muddatda hamyondan avtomatik yechiladi (balans minusga tushishi mumkin). Omonat 5 000–30 000$, 3–10 kun,
  kuniga 5%, muddatida avtomatik to'lanadi. `bank_worker` (har 30 s). Faol kredit bo'lsa `/pul` va omonat bloklanadi.
- /profil → 📈 Birja (`cb_birja`, `bx:<uid>:...`): BTC/ETH/TON/SOL/BNB/GOLD(PAXG), narxlar Binance `data-api.binance.vision`
  (zaxira CoinGecko), `birja_worker` har 60 s. Komissiya 0.5%, sotib olgandan keyin 10 daqiqa sotib bo'lmaydi, narx 5 daqiqadan
  eski bo'lsa savdo to'xtaydi. Grafik — Binance klines + Pillow.
- 👶 Farzandlar (`cb_kid`, `kid:<uid>:...`, `/farzand`, /oila va do'kondagi tugma): 1 kun = 1 yosh (faqat to'q, xursand va
  ta'lim to'lovi qilingan bo'lsa). Bosqichlar 0–2 / bog'cha 3–6 / maktab 7–15 / kollej 16–18 / universitet 19–22 / ish.
  16 va 19 yoshda yo'l tanlanadi; ishlayotgan farzand kuniga 100/200/400$ maosh (ota-onaga teng). Ovqat/o'yinchoqlar `KID_ITEMS`,
  to'lovlar `KID_FEES`, maosh `KID_SALARY`; holat `family_children` ustunlarida, `kid_worker` har 60 s.
