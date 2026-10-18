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
- `/aktiv` (faqat guruh adminlari va bot egalari): guruhdagi eng faol 15 a'zo (mention bilan, xabarlar soni + eng ko'p yozgan so'zi). Hisob `count_activity` orqali
  `member_activity` / `member_words` jadvallarida, funksiya qo'shilgan paytdan boshlab yig'iladi.
- Owner panel → 💰 Pul statistikasi (`panel:money`, `panel_money_text`): faqat bot egalari; jami pul, egalarda /
  foydalanuvchilarda, o'yinlarda tikilgan (`money_in_games`), o'rtacha, eng boy 10.
- Owner panel → 👶 Farzand o'chirish (`panel:kiddel*`, `panel_kid_callback`, `panel_kid_handle_text`): faqat bot egalari;
  ID/@username → farzandlar ro'yxati → tasdiqlab o'chirish.
- /profil → 🏦 Banklar / 📈 Birja / 👶 Farzandlarim — URL tugmalar (`?start=bank|birja|kids`, `cmd_start`),
  bo'lim shaxsiy chatda ochiladi.
- 🏦 Banklar (`cb_bank`, `bk:<uid>:<amal>:<bank_id>...`): ko'p bankli — `banks` jadvali (nomi, egasi, `loan_rate`,
  `deposit_rate`, `apply_mode`, `active`); 1-bank Gold Invest (`MAIN_BANK_ID`) — doim ochiq, yopib bo'lmaydi, faqat sozlanadi. Owner panel → 🏦 Banklar boshqaruvi (`panel:banks`, `panel:bank_*`,
  `panel_bank_callback`/`panel_bank_text`): qo'shish, foiz ±1%, ariza rejimi, egasi, yopish. Ariza rejimida foydalanuvchidan
  maqsad so'raladi (`bank_purpose_text`) → `bank_loan_apps`; bank egasiga to'liq ma'lumot (`applicant_info`) + ✅/❌ (`cb_bank_app`, `bka:`).
  Standart foizlar: kredit kuniga 13%, 1–7 kun, birinchisi 1 000$, keyingilari
  1 000–50 000$; muddatda hamyondan avtomatik yechiladi (balans minusga tushishi mumkin). Omonat 5 000–30 000$, 3–10 kun,
  kuniga 5%, muddatida avtomatik to'lanadi. `bank_worker` (har 30 s). Faol kredit bo'lsa `/pul` va omonat bloklanadi.
- /profil → 📈 Birja (`cb_birja`, `bx:<uid>:...`): BTC/ETH/TON/SOL/BNB/GOLD(PAXG), narxlar Binance `data-api.binance.vision`
  (zaxira CoinGecko), `birja_worker` har 60 s. Komissiya 0.5%, sotib olgandan keyin 10 daqiqa sotib bo'lmaydi, narx 5 daqiqadan
  eski bo'lsa savdo to'xtaydi. Grafik — Binance klines + Pillow.
- 👶 Farzandlar (`cb_kid`, `kid:<uid>:...`, `/farzand`, /oila va do'kondagi tugma): 1 kun = 1 yosh (faqat to'q, xursand va
  ta'lim to'lovi qilingan bo'lsa). Bosqichlar 0–2 / bog'cha 3–6 / maktab 7–15 / kollej 16–18 / universitet 19–22 / ish.
  16 va 19 yoshda yo'l tanlanadi; ishlayotgan farzand kuniga 100/200/400$ maosh (ota-onaga teng). Ovqat/o'yinchoqlar `KID_ITEMS`,
  to'lovlar `KID_FEES`, maosh `KID_SALARY`; holat `family_children` ustunlarida, `kid_worker` har 60 s.
- 💔 Ajrashish: "Ajrashish" bosilganda avval oqibatlar (`divorce_terms_text`) va farzand bo'lsa vasiylik tanlovi
  (`rel:divgo:<custody_id>`, `pair_requests.custody_id`); juftga shu shartlar yuboriladi. Tasdiqlanganda (`rel:owner` va
  /tasdiq) `divorce_settle`: ikkala hamyon puli teng bo'linadi, sovg'alar qiymati bo'yicha teng taqsimlanadi, farzandlarga
  `custody_id` / `alimony_payer`. Aliment: farzand ishga kirguncha kuniga `ALIMONY_PER_CHILD` (75$) har bir farzand uchun,
  `kid_tick` → `kid_apply_money` (balans minusga tushishi mumkin).
- 🛡 Guruh himoyasi (Group Help uslubida, kulgili matnlar `MOD_TEXT`): `/settings` (`cb_settings`, `gs:<chat>:<kalit>`,
  `group_settings` jadvali; standart faqat salomlashish yoqiq), captcha (`cb_captcha`, emoji tanlash, 120 s), anti-reklama va
  anti-flood (`guard_messages`, handler group -2, `ApplicationHandlerStop`), `/warn /unwarn /warns /mute /unmute /ban /unban /kick`
  (`cmd_mod`, `group_warns`; limitdan keyin 1 kun mute yoki ban). Bot guruhda admin bo'lishi kerak.
  /settings → "Shu yerda" (`gs:<chat>:home`) yoki "Shaxsiy chatda" (`?start=gs_<|chat|>`); bo'limlar: Himoya / Salomlashish
  (o'z matni `welcome_text`, {name} {group}) / Ogohlantirishlar / Adminlar. 👮 Admin paneli (`cb_admin`, `ga:<chat>:<uid>`,
  `?start=ga_<|chat|>_<uid>`): huquqlarni ✅/❌, adminlikdan olish; `/promote [unvon]`, `/demote`; Telegram'da admin qilinsa
  `announce_new_admin` panel tugmasini chiqaradi. Bot faqat o'zi tayinlagan adminlarni o'zgartira oladi.
- 🛡 2-bosqich: 🚫 taqiqlangan so'zlar (`group_badwords`, `/addword /delword /words`, settings → So'zlar), 🔒 cheklovlar
  (`locks` bitmaskasi: stiker/GIF/ovozli/dumaloq video/forward). Taqiqlangan so'z ishlatilsa (Empire Security uslubi):
  xabar o'chadi + a'zo jim qilinadi (muddat guruh bo'yicha sozlanadi: `group_settings.badword_mute`, default 30 daq, `/badmute 1h`),
  `tashkent_dt` bilan muddat ko'rsatiladi va «✅ Bekor qilish» tugmasi chiqadi.
  Umumiy «Bekor qilish»: `/mute /tmute /ban /tban` va warn-dan kelib chiqqan jazo xabari tagida ham `undo_kb(chat,act,uid)`
  (`undo:<mute|ban>:<uid>`, eski `bw:<chat>:<uid>` ham qabul qilinadi) → `cb_mod_undo`; tugmani faqat `admin_can_restrict`
  (a'zolarni cheklash huquqiga ega admin/owner) bosa oladi, xabar o'chmaydi (auto-delete yo'q). 🌙 tungi rejim (`night_*` ustunlari, `night_worker` har 60 s,
  Toshkent vaqti; `set_chat_permissions` bilan yopadi, oldingi ruxsatlar `night_saved` da), 📣 `/report` va "@admin" (adminlarga
  shaxsiy xabar + 🗑/🔇/🚀 tugmalar `cb_report`), 📋 log kanal (`/setlog @kanal|off`, `mod_log`).
- 💱 Botlar aro pul almashuvi (`cb_exchange`, `ex:<uid>:...`; owner panel → 💱 Pul almashuvi, `panel:exch*`): hamkor bot bilan
  HMAC-imzolangan HTTP ko'prik. Env: `EXCHANGE_SECRET`, `EXCHANGE_PARTNER_URL`, `EXCHANGE_PARTNER_NAME`, `PORT`. Kiruvchi server
  (`exchange_start_server`, stdlib http.server, alohida ip → `asyncio.run_coroutine_threadsafe`): `POST /exchange/credit`
  (idempotent, `exchange_txns.txid`). Chiquvchi (`exchange_send` → `exchange_finalize_out`): $ 1:1 (komissiya `fee_pct`),
  xatoda to'liq qaytadi, noaniqda pending + `exchange_retry_worker`. Kunlik limit, faol kredit bo'lsa bloklanadi.
  Sozlamalar `exchange_config` (enabled/fee_pct/daily_limit). son_bot Railway'da public domen + PORT bilan ishlashi kerak.
- Owner panel → 🔢 Ko'rsatkichlarni tahrirlash (`panel:stats_edit`, `panel:stat_*`, `panel_stats_callback`/`panel_stats_text`,
  `panel_overrides` jadvali): foydalanuvchilar/guruhlar/faol o'yinlar/jami ishtiroklar sonini qo'lda belgilash (faqat panel
  ko'rinishi, `stat_show`), "🔄 Avto" haqiqiy songa qaytaradi. Faqat bot egalari.
  `/taxrir` — tahrirlash menyusini ochadi (`cmd_taxrir`); `/haqiqiy` — asl (override'siz) statistikani ko'rsatadi (`cmd_haqiqiy`).
- 📢 Majburiy obuna (`forcesub` jadvali, bitta yozuv `id=1`): owner panel → 📢 Majburiy obuna (`panel:fsub*`,
  `panel_fsub_callback`/`panel_fsub_text`, `panel_fsub_view`): kanal `@username` orqali ulanadi (`get_chat` bilan tekshiriladi;
  bot kanalda admin bo'lishi shart — `get_chat_member` orqali tekshiriladi), yoqish/o'chirish, almashtirish, uzish. Faqat bot egalari.
  Gate: `fsub_is_member` (owner bypass, ijobiy natija `_FSUB_CACHE`'da 5 min, API xatoda fail-open → bloklamaydi) +
  `fsub_block_cb`(callback)/`fsub_block_msg`(matn); o'yin kirish nuqtalarida: `cb_game`, `cb_inline_game`, `cb_rsp_join`,
  `cb_xo_join`, crash join (`crash_action`), memory `m:join`, qurbaqa join (`_frog_action`), `on_text` (son topish) va `croc_on_text`.
  "✅ Tekshirish" tugmasi (`fsub:check`, `cb_fsub_check`) keshni tozalab qayta tekshiradi. Matnlar 4 tilda `FSUB_TEXT`/`fsub_t`.
- 🛡 Group Help buyruqlari (`init_grouphelp`, `GH_TEXT`/`gh_t`, `gh_admin_guard` admin+guruh tekshiruvi): barcha moderatsiya buyruqlari
  endi Telegram "/" menyusida — `post_init` da `set_my_commands(scope=BotCommandScopeAllGroupChats())`. Jazo `cmd_mod` da
  (`/warn /unwarn /warns /mute /tmute /unmute /ban /tban /unban /kick`; muddat `parse_dur`: 10m/2h/1d). Qo'shimcha: `/del`,
  `/purge` (reply→joriy, `delete_messages` 100talab), `/pin /unpin`, `/id`, `/info`, `/admins`, `/lock /unlock /locks`
  (`LOCK_ALIASES`→`locks` bitmaskasi, "all"), `/title` (`set_chat_administrator_custom_title`, 16 belgi), `/setwelcome`
  (`welcome_text`), `/setrules`+`/rules` (`group_settings.rules`; `/rules`=`cmd_grules`, qoida bo'lmasa o'yin qoidasiga tushadi,
  `/qoidalar`=o'yin qoidasi), filtrlar `/filter /filters /delfilter` (`group_filters` jadvali, `FILTERS_CACHE`, `on_text` da
  `gh_filter_match` so'z-chegarasi bilan). `rules` ustuni `GUARD_DEFAULTS` ga qo'shilgan. `/help` guruhda admin buyruqlar ro'yxatini ham chiqaradi.
  Barcha buyruqlar `/` dan tashqari `.` va `!` prefikslari bilan ham ishlaydi (Group Help uslubi): `main()` da har bir buyruq
  `CommandHandler` + `PrefixHandler([".","!"], ...)` bilan ro'yxatdan o'tadi; buyruq nomini ajratish `lstrip("/.!")`.
- 🌐 Web App (Telegram Mini App, to'q + neon uslub): botning mavjud HTTP serveridan uzatiladi (`exchange_start_server` endi PORT bo'lsa
  ishga tushadi; almashuv yo'llari EXCHANGE_SECRET bo'lsa). `_ExchangeHandler`: `GET /app` → `WEBAPP_HTML`, `POST /app/api/data` →
  `webapp_fetch` (DB bot sikliga marshal qilinadi). Auth: `webapp_check_init_data` — Telegram `initData` ni bot token bilan HMAC
  (`secret=HMAC("WebAppData", token)`), `auth_date` yangiligi tekshiriladi. `webapp_payload`: profil, hamyon, reyting (TOP 15),
  daraja, farzand, birja, kredit; owner uchun qo'shimcha statistika. URL: `WEBAPP_URL` yoki `RAILWAY_PUBLIC_DOMAIN`. Kirish: `/app`
  (`cmd_app`, shaxsiy chatda `WebAppInfo` tugma) + `post_init` da `set_chat_menu_button(MenuButtonWebApp)`. Yoqish/o'chirish:
  `webapp_config` jadvali (`all`, `owner` flaglari, default 1), owner panel → 🌐 Web App (`panel:webapp*`, `panel_webapp_view/callback`):
  hamma uchun va ownerlar uchun alohida yoqish/o'chirish. Faqat bot egalari.
