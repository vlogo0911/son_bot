# son_bot (@empire_statsbot)

- Asosiy fayl: `bot.py` (Railway `Procfile`: `web: python bot.py` — web app/almashuv HTTP serveri public domen orqali ishlashi uchun `web` jarayon). Barcha o'zgarishlar shu faylda qilinadi.
  Foydalanuvchi yuklagan `probot.zip` ichidagi `bot.py` shu repodagi bilan bir xil; zip'dagi
  `*.backup*` / `*.before_*` fayllar faqat eski zaxira nusxalar.
- Railway shu repodan avtomatik deploy qiladi (GitHub commit statuslarida ko'rinadi).
  Agar main commitida status/deployment paydo bo'lmasa — Railway webhook'i ishlamagan: Railway'da "Deploy latest commit" yoki yangi push.
  Railway "New builds are temporarily paused" bo'lsa — push ham deploy qilmaydi, pauza tugagach "Deploy latest commit" bosiladi.
  Deploy tekshiruvi: `https://api.github.com/repos/vlogo0911/son_bot/deployments` (radiant-heart / exquisite-ambition production) va commit statuslari.
- Qo'shni bot: `vlogo0911/mafia-bot` (aiogram, Postgres+Redis) — son_bot Railway loyihasida alohida servis bo'ladi, o'z reposi va CLAUDE.md'si bor.
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
  Web app bo'limlari: Profil / Reyting (TOP-15) / Bank (faol kredit+omonat) / Birja (aktivlar+foyda) / Farzandlar / 🚀 Crash / 🐸 Baqa / Owner.
  `webapp_payload` da `bank`, `birja_list`, `kids_list` ham bor.
  Web o'yinlari (haqiqiy hamyon, server tomonda xavfsiz): `_web_api` dispatcher `POST /app/api/{crash,frog}/{start,step,cashout}`.
  🚀 Crash — Aviator uslubi: `web_crash_start` betni `_wallet_take` bilan yechadi, yashirin `_web_crash_point()` (RTP ~0.97, ~3% darhol
  portlash) tanlaydi; klient `exp(WEB_CRASH_GROWTH·t)` bilan animatsiya qiladi; `web_crash_cashout(uid, mult)` — mult<crash bo'lsa
  `bet·mult` yutuq, aks holda yutqazish. 🐸 Baqa — `web_frog_start` (rejim easy/medium/hard → qatordagi tuzoqlar soni, `frog_mult`
  bilan bir xil RTP), `web_frog_step(col)` qadam/tuzoq, `web_frog_cashout`. Holat `WEB_CRASH`/`WEB_FROG` (bot siklida, bitta o'yin
  har foydalanuvchi). Faqat web app yoqilgan bo'lsa (`web_enabled_for`).
  🛍 Do'kon (interaktiv): `web_shop_buy(uid, gift, to)` — sovg'a sotib olib (narx `_wallet_take`), juftga yoki @username/ID ga
  yuboradi (`_EXCHANGE_LOOP_BOT.send_message`), yetkazilmasa pul qaytadi. 🏦 Bank (interaktiv, faqat instant banklar):
  `web_bank_loan`/`web_bank_repay`/`web_bank_deposit` — botdagi bir xil qoidalar (birinchi kredit 1000, `LOAN_AMOUNTS`/`LOAN_DAYS`,
  `DEPOSIT_AMOUNTS`/`DEPOSIT_DAYS`, `loan_due`/`deposit_payout`, faol kredit/omonat tekshiruvi). Payloadda `shop`, `has_partner`,
  `bank_opts` (banklar, summalar, kunlar, can_loan/can_deposit). Endpointlar: `/app/api/{shop/buy,bank/loan,bank/repay,bank/deposit}`.
  🚀 Crash YANGILANDI — bashorat qilib bo'lmaydi: crash nuqtasi klientga umuman berilmaydi (`web_crash_start` javobida yo'q).
  Klient jonli animatsiya (canvas Aviator egri chizig'i + samolyot) qiladi va `/app/api/crash/state` (`web_crash_state`) ni ~350ms
  da so'rab turadi; portlash va yechish SERVER soati bo'yicha hal qilinadi (`web_crash_cashout` klient koeffitsiyentiga ishonmaydi).
  Oxirgi natijalar `WEB_CRASH_HISTORY` (yuqori panel). 📈 Birja savdosi (`web_birja_buy`/`web_birja_sell` — `birja_buy`/`birja_sell`,
  `BIRJA_HOLD`/stale/min tekshiruvlari), 👶 Farzand boshqaruvi (`web_kid_action` — ovqat/o'yinchoq/ta'lim, `KID_ITEMS`/`KID_FEES`,
  `kid_fresh`/`kid_save`). Payloadda `birja_market`, `crash_history`, `kids_list` ichida food/toy/fee. Endpointlar yana:
  `/app/api/{crash/state,birja/buy,birja/sell,kid}`. UI: neon+oltin uslub, modal sheet, toast. Owner toggle'lari hamma o'yin/amalga amal qiladi.
- 🚀 Web Crash endi UMUMIY raund (hamma uchun bir vaqtda bir xil koeffitsiyent): `WEB_ROUND` (id/phase bet→fly→crash/t/crash/bets),
  `WEB_NEXT_BETS` (fly/crash paytidagi tikishlar keyingi raundga), `web_crash_round_worker` (post_init task, `WEB_ROUND_BET` 7 s
  tikish, `WEB_ROUND_PAUSE`). Uy ustunligi: `WEB_CRASH_BUST` 7% darhol portlash + `WEB_CRASH_RTP` 0.90. API: `crash/bet`
  (`web_crash_bet`, `/crash/start` ham shunga), `crash/cancel`, `crash/cashout` (faqat fly, server soati), `crash/state`
  (players/total/pot/me/queued; crash nuqta faqat crash fazasida). Restartda `web_crash_refund_open` ochiq tikishlarni qaytaradi.
  Klient: `initCrash` → `window.CR` (stop/poke, qayta renderda eski sikl to'xtaydi), samolyot chapdan o'ngga (8 s) chayqalib uchadi,
  parallaks yulduzlar + sunburst, ± stepper va ½/×2/MAX, tagida o'yinchilar ro'yxati (tikish/kf/yutuq).
- Web bank: payloadda botdagi BARCHA ochiq banklar (`apply` flag); ariza rejimidagi bankka web'dan maqsad bilan ariza
  (`submit_loan_app` — bot bilan umumiy). Profil rasmi: `GET /app/avatar/<uid>` (`web_avatar_bytes`, 1 soat kesh; token oshkor bo'lmaydi),
  xato bo'lsa `photo_url` → bosh harf.
- Panel foydalanuvchilar soni: `bot_users_count` (botni haqiqatan ishlatganlar, `users.started`/`mark_started`); `seen_users_count` — guruhda ko'rilganlar.
  Qayta ro'yxat: `rereg_config`/`rereg_users`, owner panel `panel:rereg`, profil tugmasi `career:rereg`.
- 👑 Web app qirollik oltin mavzusi: WEBAPP_HTML `<style>` oxiridagi "QIROLLIK OLTIN MAVZUSI" bloki (`--g-metal`/`--g-text`/`--g-border`,
  Cinzel shrifti, yaltiroq kartalar/tugmalar, `.spark` uchqunlar — `pointerdown` listener). `#s-crash` eski neon o'zgaruvchilarini qayta
  belgilaydi — Crash dizayni o'zgarmaydi. Pastki tablar kattaroq, ikon + nom (`.ti`/`.tl`).
- Crash samolyoti 3D ("Royal" — foydalanuvchi rasmi asosida: qizil korpus, oltin kapot halqasi/konus/chiziq, qora dum va yon panelda oltin toj, oltin ramkali kabina, 3 parrakli pervanel + oltin disk, olovli iz): `P3` mesh (fuselaj halqalari + qanot/dum yuzalari, `n` — bir tomonlama bezaklar), `rot()` krен/pitch/yaw/tilt, perspektiva, flat shading,
  aylanuvchi parrak; `flyRoll` — chayqalish + har 7 s da bochka aylanishi; portlashda aylanib uchib ketadi.
- Web Baqa: tuzoqlar `_web_frog_traps` (SystemRandom, har o'yinda yangi), `WEB_FROG_EXTRA` (8%) — qatorga yashirin qo'shimcha tuzoq.
- 🎰 Web app Kazino: pastki qatorda Crash/Baqa o'rniga bitta "Kazino" tab (`CASINO_ICON` — SVG oltin fishka+toj). `#s-casino` lobbisi:
  ikkita banner (`.gcard`, 1win uslubi: "EMPIRE GAMES" yorlig'i, katta sarlavha, Ken Burns + yaltirash) → `setTab('crash'|'frog')`;
  o'yin bo'limlarida "‹ Kazino" (`.gback`). `setTab` crash/frog uchun Kazino tabini yoritadi. Baqa web'da endi "🌊 Hovuz" (backend o'zgarmagan).
  Banner rasmlari repo'dagi `webapp_assets/` (crash.jpg — foydalanuvchi samolyot rasmi, hovuz.jpg — three.js 3D render: tojli qurbaqa),
  `GET /app/a/<nom>` → `_ExchangeHandler._asset`, faqat `WEBAPP_ASSETS` ro'yxatidagi fayllar (1 kun kesh).
- 🛩 Web Kamikaze (1xGames uslubi, Kazino'da): 12 ustun × 5 qator dengiz, har qadamda keyingi ustundan katak tanlanadi, dushman kemasi
  shu ustunga bitta o'q uzadi (joylari `web_kami_start` da SystemRandom bilan yashirin, `WEB_KAMI`). Koeffitsiyent `kami_mult` =
  0.92·(5/4)^qadam (x1.15 → x13.38), yutuq `kami_win` (float yaxlitlash). API `/app/api/kami/{start,step,cashout}`; restartda
  `web_kami_settle_open` (post_shutdown). Ko'rinish: `kami_enabled_for` — standart faqat ownerlar (test), owner panel → 🌐 Web App →
  "🛩 Kamikaze: hamma uchun ochish" (`webapp_config.kami`, `panel:webapp_kami`). Payloadda `kami`, `kami_test`. Klient `initKami`
  (`window.KM`), 3D samolyot `planeKit(ctx,dpr)` — Crash bilan umumiy.
  Ochiq qolgan o'yin bloklamaydi: `web_kami_view` (qadam, `picks`, o'tilgan o'qlar), `/app/api/kami/state` (`web_kami_state`),
  `kami/start` ochiq o'yin bo'lsa `resumed` qaytaradi, payload `kami_game` → klient `resume()`; xato/uzilishda `resync()`.
  Klient: dpr ≤ 2, kutishda ~15 fps, to'lqinlar bitta path; `api()` da 20 s timeout (AbortController). Banner `webapp_assets/kamikaze.jpg` — foydalanuvchi bergan kema rasmi fonida uning biplan rasmi (OpenCV GrabCut bilan kesilgan, tungi rangga moslangan, olov/tutun/iz qo'shilgan) kemaga sho'ng'iyapti.
- 🎵 Web o'yinlar ovozi (`SND`, WEBAPP_HTML ichida, Web Audio sintez — fayl yo'q): har o'yinga alohida sokin fon musiqasi
  (`TR.crash` synthwave 84 BPM, `TR.frog` marimba pentatonika + suv tomchilari 72 BPM, `TR.kami` dengiz/kinematik 66 BPM), lookahead
  scheduler (40 ms), reverb (generatsiya qilingan IR), kompressor. `setTab` → `SND.music(crash|frog|kami|null)` (crossfade).
  Effektlar `SND.play(nom)`: chip/tick/takeoff/cash/boom (Crash), hop/plop/splash/cash/win (Hovuz), click/whoosh/cannon/splash/
  explode/bigboom/cash (Kamikaze). Brauzer siyosati: birinchi tegishda `AudioContext` ochiladi. 🎵/🔊 tugmalar (`.sndbar`) har o'yin
  bo'limida, tanlov `localStorage` (`snd_m`, `snd_s`).
- ✨ Interfeys ovozlari (premium "sehrli uchqun"): `SND.ui(nom)` (70 ms throttle) — `tab` (pastki tablar, shisha qo'ng'iroq),
  `sparkle` (tugmalar: kristall arpedjio + yuqori chastotali shimmer, notalar tasodifiy), `card` (Kazino bannerlari, do'kon sovg'alari
  `data-tap`), `select` (select.sel change), `good` (toast ✅/🟢/🎉/🏆 bilan boshlansa). Umumiy `pointerdown` listener, o'yin
  bo'limlari ichida faqat `.gback` (o'yinlarning o'z effektlari bor). `bell()` — noharmonik qismli qo'ng'iroq tembri.
- 👶 Farzand so'rovlari ownerlarga: rozilik+to'lovdan keyin (48 soat kutish boshlanganda) `notify_owners_child_request` → ownerlarga
  xabar + "⚡ Hozir yetkazish" (`family:far:<rid>`, cb_relationship). `/far` (faqat ownerlar, `cmd_far`) — barcha `approved`
  so'rovlarni darhol yetkazishga qo'yadi (`child_deliver_now` → `due_at=now`, `family_delivery_worker` 3 s ichida yetkazadi);
  rozilik kutayotgan (`pending`) lar soni ham ko'rsatiladi.
- 🏫 Ta'lim muassasalari: `edu_institutions` (kind kinder/school/college/uni, name, fee, active; `init_edu`, init_kids ichida ham).
  Farzand `family_children.inst_id`; `kid_fee(kid)` — mos va faol muassasa narxi, aks holda `KID_FEES` (bot va web to'lovlari shu
  bilan). Web: `/app/api/edu/enroll` (ota-ona, faqat joriy bosqich turidagi muassasa), ownerlar `/app/api/edu/{add,update,toggle}`
  (`web_edu_admin`). Payloadda `edu`, `edu_min_age` (3/7/16/19), `edu_default_fee`, owner uchun `edu_all`; `kids_list` da
  stage_key/gender/growth/block/inst/salary.
- Web Farzandlar: har bosqichga alohida karta dizayni (`.kidc.st-baby|kinder|school|college|uni|work`, emoji jins bo'yicha `KS`,
  suzuvchi bezaklar `KDECO`), o'sish progressi, "🏫 Muassasa" tanlash; "🏫 Ta'lim yo'li" — kategoriyalar eng katta farzand yoshi
  yetganda ochiladi (🔒 N yoshdan). Owner tabida "🏫 Ta'lim muassasalari": ochish, nomi/narxini saqlash (💾), yopish/ochish.
- 🍽 Farzand o'sishi endi OVQAT bo'yicha (vaqt bo'yicha emas): 12 soatda 1 marta ovqat (`KID_MEAL_GAP`, `kid_eat_check`/`kid_eat`,
  ustunlar `meals`, `last_meal`); `kid_meals_need(age)` = 7 + yosh//3 ta ovqatdan keyin +1 yosh (kid_tick, blok bo'lmasa).
  Erta ovqat → `too_soon` (bot alert / web `error: too_soon, wait`). Migratsiya: eski `growth` → `meals`.
- 🎒 Farzand buyumlari (`KID_ITEMS` tur "gear", har davr uchun: beshik/belanchak/aravacha, bog'cha formasi/samokat, maktab
  formasi/ryukzak/darslik, lab xalati, talaba kostyumi/planshet/yotoqxona...): har farzandga bir marta (`family_children.gear`),
  sotib olinganda kayfiyat +eff, shu davrda kayfiyat har buyum uchun 15% sekin tushadi (maks 60%). Bot: farzand menyusida
  "🎒 Buyumlar" (`kid:...:g:<id>`); web: kartada "🎒 Buyumlar" + Do'kon'da "👶 Farzand buyumlari" (`/app/api/kid` act=gear).
- 🧒 Farzand 3D personaji (web): kartochka bosilganda `openKidStudio(k)` — to'liq ekranli studiya; `KID3D` (three.js r128 cdnjs'dan
  kerak bo'lganda yuklanadi) protsedura personaj: proporsiyalar yoshga qarab (bosh/tana/oyoq, `height()` sm), kamera umumiy
  masshtabda (o'sish ko'rinadi), nafas/ko'z qisish, ko'z yoshi animatsiyasi. Chapda 3 katak (bosh kiyim/ustki/shim-yubka), o'ngda 3
  (oyoq kiyim/aksessuar/emotsiya) — `KID3D.CAT` katalog (yosh/jins bo'yicha `allowed`, `fit` standartlar; chaqaloq: bodi, taglik,
  so'rg'ich, emotsiyalar). Aylantirish: barmoq bilan surish + ⟲/⟳ (Old/O'ng yon/Orqa/Chap yon). Kiyimlar `family_children.outfit`
  (JSON) — `/app/api/kid/outfit` (`web_kid_outfit`, faqat ota-ona, qiymatlar `[a-z0-9_]` bilan tozalanadi). Payloadda `outfit`,
  `parents` (ota-ona ismlari kartada).
- 🧍 Realistik 3D avatar (web, test — standart faqat ownerlar): Profil → "3D avatarim" (`openAvatarStudio(d)`, `#ast`, `.kst` uslublari).
  Skeletli MakeHuman (CC0, MPFB2 orqali, `cmu_mb` rig) modellar: `webapp_assets/av_base_<m|f>.glb` (tana + ko'z/qosh/kiprik/tish;
  `_HIDE` bit atributi — kiyim/poyabzal ostidagi tana uchburchaklari yashiriladi, bitlar tartibi JS `BIT` = build.py),
  har buyum alohida `av_<g>_<nom>.glb` (12 kiyim, 6 poyabzal, 2 shlyapa, 10 soch) — kerak bo'lganda yuklanib, tana skeletiga
  nom bo'yicha qayta bog'lanadi (`item()`), `av_anims_<g>.glb` — CMU mocap'dan 22 harakat (idle ping-pong + 21 emote: raqs,
  salsa, moonwalk, breyk, salto, boks...). `AV3D`: three r128 + jsdelivr GLTFLoader/meshopt/RoomEnvironment, AnimationMixer,
  crossfade; soch rangi — tekstura `recolor`, teri — `material.color`. Slotlar `AVATAR_SLOTS` (g/outfit/shoes/hat/hair/hcol/skin/bg),
  `user_avatar` jadvali, `/app/api/avatar/save` (`web_avatar_save`), payload `avatar3d`/`avatar_test`/`avatar`. `avatar_enabled_for` =
  webapp_config "avatar" yoki owner; owner panel → 🌐 Web App → "🧍 3D avatar: hamma uchun ochish" (`panel:webapp_avatar`).
  Qayta yig'ish: `tools/avatar/` (README).
- 💍 Random juft (web app → Oila tabi yuqorisida `.rpair` karta, `drawRP`): faqat jufti yo'q va jinsi tanlangan (`user_gender`)
  foydalanuvchilar; yigitniki tasodifiy qizga, qizniki tasodifiy yigitga (bir jinsli juftlashmaydi). `web_randpair` →
  `randpair_candidate` (qarama-qarshi jins, `started`/`birth_confirmed`, faol juftligi yo'q, ochiq taklif yo'q, 7 kun ichida rad
  etmagan; `ORDER BY RANDOM()`), `pair_requests` ga `random=1`, `status='proposal'` (ustun `init_webapp` migratsiyasida).
  Nomzodga bot xabari: `user_card`/`user_card_text` (jins, yosh, pul, reyting, daraja/ball/o'yinlar, kasb, oldin ajrashganmi —
  `pairs.status='ended'` soni, farzandlar) + mavjud `rel:proposal:yes|no` tugmalari → rozilikdan keyin odatdagidek bot egalari
  tasdig'i. Random taklifga javob (rad/rozi) yuboruvchiga xabar qilinadi. Cheklovlar: bitta ochiq taklif, `RANDPAIR_COOLDOWN` 60 s,
  `RANDPAIR_TTL` 24 soat (eskiradi), yetkazilmasa (bloklagan) `failed` + boshqa nomzod (`RANDPAIR_TRIES`). API
  `/app/api/randpair/{find,cancel}`, payload `randpair` (`randpair_status`: gender/has_pair/partner/pending/cooldown).
- 💬 Web Chat (pastki tab "Chat", `#s-chat`, `initChat`/`openChat` — to'liq ekranli `#chv`): ID yoki @username orqali topish
  (`chat_resolve` — faqat botni ishlatganlar), profil chiplari (`chat_peer`: jins, yosh, pul, reyting, daraja, kasb, jufti bormi,
  ajrashgan), shaxsiy suhbat. Jadvallar `web_chat_msgs` (from/to/text/created_at/read) va `web_chat_blocks` (`init_webapp`).
  API `/app/api/chat/{find,list,history,send,block}`: history `after` bilan ~2.5 s polling, o'qilganlar `read=1`, yuboruvchiga
  `seen` (✓✓); `send` — 1000 belgi, `CHAT_RATE` 10 s da 8 ta, blok bo'lsa ikkala tomon yoza olmaydi; qabul qiluvchiga Telegram
  bildirishnoma (suhbat bo'yicha `CHAT_NOTIFY_GAP` 5 daqiqada bir) + "💬 Javob berish" WebApp tugmasi (`/app#chat=<uid>` →
  avtomatik ochiladi). Tab badge — o'qilmaganlar (`chat_unread`, payload `chat_unread`), ro'yxat 8 s da yangilanadi.
- 💍 ID orqali juftlik taklifi (web): Oila → Random juft kartasida "ID yoki @username" + 💌 Taklif, Chat'da topilgan profil va
  suhbat sarlavhasidagi 💍 (`pairPropose` → `/app/api/pair/propose`, `web_pair_propose`): faqat jufti yo'qlar, ikkalasining jinsi
  tanlangan va qarama-qarshi, blok yo'q, takror (24 soat) yo'q; `pair_requests.random=2`, nomzodga `user_card_text` + `rel:proposal`
  tugmalari → rozilik → bot egalari tasdig'i; javob yuboruvchiga xabar qilinadi.
- 💬 Chat media: `web_chat_msgs.kind` (text/image/sticker) + `media` (migratsiya `init_webapp`). 📷 Rasm: klient `chatShrink`
  (≤1280 px JPEG) → `chat/send` kind=image, data=dataURL (+ ixtiyoriy izoh ≤300); server `_chat_save_image` (Pillow verify,
  thumbnail `CHAT_IMG_SIDE`, RGB JPEG q82 — EXIF/GPS yo'qoladi) → `CHAT_MEDIA_DIR` (volume/`chat_media`), nom 128-bit token;
  `GET /app/chatimg/<32hex>.jpg` (`_chatimg`). Limit `CHAT_IMG_DAILY` 40/kun, `_web_api` body > 4 MB → 413. 🎭 Stiker: faqat
  `CHAT_STICKERS` ro'yxatidagi emoji (payload `chat_stickers`), katta animatsiyali (`.msg.stk`). `chat_msg_json`, `chat_preview`
  (ro'yxat/bildirishnomada "📷 Rasm"/"… Stiker"), rasmni bosish → `chatViewer`.
- Web do'kon javobida `to` — oddiy ism (`_plain_person`), HTML havola emas (toast'da `&lt;a…` chiqmasin).
- 🎭 Telegram stikerlari (web chat): foydalanuvchi botga shaxsiy chatda stiker yuborsa (`on_private_sticker`, `filters.Sticker.ALL`)
  `tg_sticker_set_fetch` → `get_sticker_set` (1 kun kesh) → `tg_sticker_sets` (id/name/title/data JSON: u/f/t/e) +
  `tg_sticker_files` (file_unique_id → file_id, fmt webp/tgs/webm/thumb) + `chat_sticker_packs` (user_id, set_id; `user_id=0` —
  hamma uchun, ownerga "🌍 Hamma uchun qo'shish" tugmasi `stk:g|u:<id>` → `cb_sticker_pack`). Maks `TG_STICKER_PACKS_MAX` 30.
  Fayllar `GET /app/tgs/<file_unique_id>` (`_tgsticker` → `tg_sticker_bytes`: bot `get_file`, volume `tg_stickers/` kesh, TGS gunzip
  → Lottie JSON, kontent turi `_sniff_image`). API `/app/api/chat/stickers` (+`/remove`), `chat/send` kind=`tg` (text=file_unique_id,
  media=fmt; eskiz yuborilmaydi). Klient: stiker panelida tablar (😊 emoji / to'plamlar eskizi / ➕ yo'riqnoma), `tgStickerHtml`
  (webp img, webm video, tgs → `lottieLoad` cdnjs lottie-web 5.12.2 light, `tgLottieIn`, yopilganda destroy).
- 🪙 EMP Coin (Empire premium valyutasi; test rejimdan chiqdi — standart hamma uchun: `webapp_flags` default emp=1, `init_webapp` da
  bir martalik `emp_launch` belgisi bilan emp=1; `emp_enabled_for` = webapp_config "emp" yoki owner,
  owner panel → 🌐 Web App → "🪙 EMP Coin: hamma uchun ochish" `panel:webapp_emp`). Jadvallar: `emp_wallet`, `emp_packs`
  (emp/stars/bonus/active; bo'sh bo'lsa `EMP_DEFAULT_PACKS`), `emp_payments` (charge_id UNIQUE — takroriy to'lov bir marta).
  ⭐ Telegram Stars: `/app/api/emp/invoice` → `create_invoice_link(currency="XTR", payload="emp:uid:pack:stars:total")` → klient
  `tg.openInvoice` → `on_pre_checkout` (`PreCheckoutQueryHandler`, `_emp_check_payload`: user, XTR, joriy narx/miqdor mos) →
  `on_successful_payment` (`filters.SUCCESSFUL_PAYMENT`): payload'dagi shart bo'yicha EMP beriladi; mos kelmasa ownerlarga ogohlantirish.
  Narxlarni ownerlar web app Owner tabida boshqaradi (`/app/api/emp/{add,update,toggle,delete}`, `web_emp_admin`, ⭐ 1–10 000).
  Klient: Profil'da `.empc` karta, `openEmpShop` (`#empv`, coin rasmi `webapp_assets/emp_coin*.jpg` — "STATS ECONOMY"),
  to'lovdan keyin `/app/api/emp/state` polling. Payload `emp` (balance/test/packs/history; owner uchun `admin` statistikasi).
- 💎 Hamkor olmosi ↔ 🪙 EMP: alohida yo'l `POST /exchange/credit_asset` ({txid,user_id,asset,amount,ts}, o'sha HMAC/`EXCHANGE_SECRET`;
  amount — qabul qiluvchi valyutasida; eski `/exchange/credit` ($) o'zgarmagan). `exchange_txns.asset` (usd|emp), sozlama
  `exchange_asset_config` (enabled, rate = 1 💎 necha EMP, fee_pct, limit_out/limit_in — kunlik, EMP). EMP→💎: `web_emp_swap`
  (`/app/api/emp/swap`, `swap_quote`: olmos = floor((EMP−ceil(EMP·fee%))/rate), EMP yechiladi → `_swap_finalize_out` hamkorga
  asset=diamond; 4xx → EMP qaytadi, noaniq → pending + `exchange_retry_worker`). 💎→EMP: `exchange_apply_incoming_asset` (asset=emp,
  idempotent txid, `emp_enabled_for`, limit_in). Ownerlar web app Owner → EMP bo'limida kurs/komissiya/limit/yoqish
  (`/app/api/emp/swapcfg`, `web_emp_swapcfg`), statistika `swap_stats`. Payload `emp.swap` (`swap_payload`). Hamkor uchun protokol va
  namuna: `tools/partner_bridge/`.
- 👛 O'tkazmalar: web app sarlavha kartasida EMP balansi (`#hdrEmp`, `emp_face_s.png`) va 👛 tugma (`#wBtn` → `openTransfers`, `#trv`):
  $ yoki 🪙 EMP ni ID/@username ga (`chat_resolve`), `/app/api/transfer` → `web_transfer` (kredit bo'lsa $ yo'q, EMP test rejimida
  ikkala tomonda `emp_enabled_for`, `TRANSFER_RATE` 60 s da 10 ta, qabul qiluvchiga bot xabari). Tarix `transfers` jadvali
  (from/to/cur usd|emp/amount/src web|pul|coin|coins; `transfer_log`, payload `transfers` → `transfers_payload`). Guruhda reply
  `/coin N` (`cmd_coin`, `emp_move`) — "X → Yga N EMP Coin o'tkazdi"; ownerlar `/coins N` (`cmd_coins`, o'ziga yoki reply'dagi
  odamga; boshqalar uchun jim). Bot /profil'da "🪙 EMP Coin" qatori (`emp_enabled_for` bo'lsa).
- 🪙 3D tanga: `webapp_assets/emp_face.webp` (fon olib tashlangan, perspektiva tekislangan tanga yuzi — ichki halqa ellipsi bo'yicha
  remap) + `coin3d(px, 'sway'|'spin')` (CSS preserve-3d: ikki yuz, qalinlik qatlamlari `<i>`, `c3shine` yaltirash, `c3g` nur).
  Profil EMP kartasi va EMP do'koni sarlavhasida.
- 🧭 Ro'yxat mantiqi (jins → tug'ilgan sana → kasb): `cb_career` — `_cb_career` o'rami, callback faqat bir marta `answer` qilinadi
  (aks holda alertlar ishlamaydi). Jins, tasdiqlangan sana va kasb bir marta tanlanadi (eski tugmalar bilan o'zgartirib bo'lmaydi;
  kasb almashtirish faqat /ariza, ishdan bo'shash — owner tasdig'i). Yosh `CAREER_MIN_AGE`/`CAREER_MAX_AGE` (6–100).
  `registration_next_step(bot, uid)` — keyingi bo'sh qadamni yuboradi (jins tanlangandan va ishdan bo'shash tasdiqlangandan keyin);
  `request_result_text(kind, approved)` — tasdiq/rad xabarlari; `profession_name` noma'lum id uchun "—". ID argumentlari ≤16 raqam.
- 💼 Web app Moliya: pastki qatorda Bank/Birja o'rniga bitta "Moliya" tab. `#s-moliya` lobbisi — Kazino uslubidagi ikki banner
  (`.glob.wide` — to'liq kenglik, `.gcard.g-bank`/`.g-birja`, rasmlar `webapp_assets/moliya_bank.jpg`/`moliya_birja.jpg` —
  foydalanuvchi bergan rasm (1536×510, 3:1, `?v=2`); sarlavha rasm ichida, HTML overlay/chip yashirilgan) → `setTab('bank'|'birja')`; bo'limlarda
  "‹ Moliya" (`.gback[data-back=moliya]`), `setTab` bank/birja uchun Moliya tabini yoritadi.
- 📰 NEWS (online gazeta): pastki qatorda "📰 News" tab (Profil'dan keyin; o'qilmaganlar `.tbadge` — `setNewsBadge`, `news_unread`/
  `news_seen` jadvali; `setTab('news')` → `newsSeen` → `/app/api/news/seen`) → `#s-news` (`newsPage`): "EMPIRE NEWS" mastheadi, bosh maqola (`.nlead`) va yangiliklar
  (`.nrow`) — chapda rasm, o'ngda maqola; pastda "📢 E'lonlar" (`.nad`), har post tagida havolalar (`.nlink` → `newsOpenLink`,
  t.me → `openTelegramLink`). Bosilganda `openArticle` (`#nwv`). Jadval `news_posts` (kind news|ad,
  title ≤120, body ≤5000, img token, links JSON ≤6 — `_news_links`: faqat https/http/tg, @kanal → t.me, pinned, active).
  Rasm `_chat_save_image(data, NEWS_MEDIA_DIR, 1600)` → `GET /app/newsimg/<32hex>.jpg`. Ownerlar: `/app/api/news/{add,update,
  delete,pin,toggle}` (`web_news_admin`), payload `news` (ownerlarga yashirinlari ham).
- 👑 Web owner panel guruhlari (`.oseg` → `.ogrp`, tanlov `window.OGRP`): 📊 Statistika / 📰 Yangiliklar (`newsAdmin` — yozish,
  rasm, havolalar, ✏️📌👁🗑) / 🪙 EMP / 🏫 Ta'lim / ⚙️ Sozlamalar (`ownerFlags` → `/app/api/owner/flag`, `web_owner_flag`:
  `OWNER_FLAG_KEYS` all/emp/kami/avatar — bot panelidagi bilan bir xil `webapp_config`).
- 📝 Arizalar web app'da (Profil → EMP kartasi tagida `.reqc` `#reqc`, `drawReqCard`/`openRequest` — pastdan chiquvchi `#rqv`):
  💼 Ishdan bo'shash / 💔 Ajrashish (shartlar `divorce_terms_text` → `_plain`, farzand bo'lsa vasiy tanlovi) / 👶 Farzand ko'rish
  (jins, `CHILD_NAMES` dan yoki o'z ismi 2–40, narx `next_child_cost`). `POST /app/api/request` → `web_request` (`create_rel_request`
  `types.SimpleNamespace(bot=_EXCHANGE_LOOP_BOT)` bilan; farzand — `child_requests` status=pending + `child_request_message` →
  juftga `family:consent` tugmalari, yetkazilmasa `cancelled`/`undeliverable`). Payload `requests` (`requests_payload`).
  Juft roziligi va owner tasdig'i botda o'zgarmagan. Botdagi eski kirishlar (`rel:menu:quit|divorce`, `rel:divgo:*`, `?start=child`)
  endi `REQ_WEB_TEXT` + `webapp_open_kb` (shaxsiy chatda WebApp `/app#req` → Profil'dagi kartaga scroll; guruhda bot havolasi).
- 👨‍👩‍👧 Yangi juftlik tuzilganda (`rel:owner` pair tasdig'i va /tasdiq) `pair_merge_kids(c, new_pair, a, b)` → (qayta, o'gay):
  ajrashgan ota-ona qayta juftlashsa — umumiy farzandlari yangi juftlikka, `custody_id`/`alimony_payer`/`step_id` = 0 (aliment to'xtaydi);
  boshqa odam bilan juftlashsa — vasiylikdagi (`custody_id`=x) farzandlar yangi juftlikka, yangi jufti o'gay ota/ona
  (`family_children.step_id`): `kids_of`, profil sanoqlari, ruxsatlar (`kid_is_parent`), bildirishnomalar va web `kids_list.step` da
  ko'rinadi; aliment (ikkinchi o'z ota-onadan) davom etadi, maosh faqat o'z ota-onaga. Ajrashishda (`divorce_settle`) o'gay farzandlar
  vasiy ota-onasida qoladi (`step_id`=0), vasiylik tanloviga faqat o'z farzandlar (`divorce_kids`: `step_id=0`). `notify_kids_merged` xabari. Web ajrashish oynasi botdagidek: "👨 Otada / 👩 Onada qolsin — ism" (`.rqopts.col`).
- 📝 Kiruvchi so'rovlar web'da (Telegram xabari yetmasa ham qotib qolmaydi): `requests_payload` → `divorce.incoming` (partner_consent,
  target=uid) va `child.incoming` (status pending, partner=uid) + `child.mine`; plitkada "💌 So'rov keldi" (`.rqt.hot`), Profil tabida
  badge. Javob `POST /app/api/request/answer` → `web_request_answer`: botdagi `cb_relationship` (`rel:divorce:*` / `family:consent:*`)
  `_WebCallback` soxta query bilan chaqiriladi — mantiq bir xil. O'zimniki: `/app/api/request/cancel` (`web_request_cancel`) va
  `/app/api/request/remind` (`web_request_remind`, `REQ_REMIND_GAP` 10 daq). Ajrashish xabari `send_divorce_consent` (yetkazilmasa
  `REL_SEND_FAILED` → web javobida `undelivered`).
- 🎮 Web app Games: pastki qatorda "Kazino" o'rniga "🎮 Games" tab (`games`) → `#s-games` (`gamesPage`): kategoriyalar 🎰 Kazino
  (`setTab('casino')`, lobbi tepasida "‹ Games") va 👑 VIP (`#s-vip`, `vipPage`). `setTab` casino/vip/crash/frog/kami uchun Games tabini
  yoritadi. VIP: `vip_users` (until, ownerlar beradi), `is_vip` (ownerlar doim VIP), payload `vip` (`vip_payload`: vip/until/best/top),
  ownerga `vip_list`; bo'lim test — `vip_enabled_for` (webapp_config "vip" yoki owner; web Owner → ⚙️ Sozlamalar → "VIP o'yinlar —
  hamma uchun", `OWNER_FLAG_KEYS`), yopiq bo'lsa Games'da VIP kartasi va `#s-vip` chiqmaydi, rekord qabul qilinmaydi; owner panel → 👑 VIP (`vipAdmin`, `/app/api/vip/grant` — `web_vip_grant`, 0 kun = olib qo'yish, berilganda bot xabari).
  VIP o'yin: 🕹 STRIKE 2D (`STRIKE` modul, WEBAPP_HTML ichida) — eski Nokia telefonlaridagi kontr-terror o'yinlari uslubidagi original
  o'yin (nom va grafika o'zimizniki): monoxrom LCD 168×120 canvas (pixelated), 3×5 piksel shrift, urug'li protsedura xarita
  (`genMap(level)`, flood-fill bilan ulanish), dushmanlar patrul/hujum (LOS), hitscan o'q + nishonga olish yordami, bosqichlar
  (dushmanlar 3+2·L, HP +35). v2: qurollar `GUNS` (USP ∞ / AK avtomat / AWP 4 zarar, `*` almashtirish), dushman turlari `ET`
  (T oddiy, H zirhli 4 HP, S snayper — nishonga olishda nuqtali lazer), narsalar `pk` (M aptechka +35, B o'q qutisi, A/S qurol; o'ljadan
  tushadi), har 3-raund C4 (`BOMB_T` 60 s, ustida turib `DEFUSE` 2.5 s; portlasa o'yin tugaydi), ekrandan tashqari nishonga strelka,
  silkinish + Telegram haptic. Boshqaruv — telefon klaviaturasi `#csv` (2/4/6/8, 1/3/7/9 diagonal, 5 o'q, * qurol, 0 o'qlash, # pauza,
  ✕ chiqish) va klaviatura (WASD/strelka, Space, Q, R, P, Esc). Ovoz — square beep (`SFX`). Rekord `/app/api/vip/score` → `vip_scores` (`web_vip_score`:
  faqat VIP, score ≤ level·7000, 8 s da bir).
- 🎯 CLASSIC STRIKE (3D FPS, VIP → owners-only, original assetlar): alohida katalog `games/classic_strike/` — `cs_core.js` (`CS3D.U`,
  `CS3D.Save` localStorage `classic_strike_v1` — sozlamalar/statistika/ochilishlar, `CS3D.Audio` Web Audio sintez), `cs_world.js`
  (`CS3D.MapSystem.GameMap`: Desert Base / Urban Strike / Warehouse, 28×28 katak, A*, 3D ray/LOS, to'qnashuv), `cs_combat.js`
  (`WeaponSystem` 7 qurol + effektlar + viewmodel, `EnemyAI.Bot` patrol/investigate/chase/attack/cover/reload/retreat, easy/normal/hard),
  `cs_ui.js` (menyu, HUD, mobil tugmalar), `cs_game.js` (Engine, Input — multi-touch joystick/qarash/tugmalar + WASD/sichqoncha,
  Player, Match, `RoundManager` tdm/dm/bomb/survival, `CS3D.launch({onResult,onExit})`), `cs_style.css` (faqat `.cs3d` ichida).
  Server: `GET /app/games/classic_strike/<fayl>` (`CS_GAME_FILES` oq ro'yxati, `_game_file`); WEBAPP_HTML `CSTRIKE` loader
  (three r128 `KID3D.load` + CSS + 5 skript, `?v=` = `cs_game_version()` xeshi, `__CS_VER__`). VIP sahifada `#vipCS` karta (STRIKE 2D
  ham qoldi). Natija `vip/score` game=`cstrike` (`cstrike_check`: kills/heads/wave/rounds/win bo'yicha yuqori chegara), payload
  `vip.cs_best`/`cs_top`.
- 🏁 NEON RUSH (3D arkada jangovar poyga, Blur uslubidagi ORIGINAL o'yin; VIP → owners-only test): `games/neon_rush/` — `nr_core.js`
  (`NR3D.U`, `NR3D.Save` localStorage `neon_rush_v1`, `NR3D.Audio` sintez: dvigatel, power-up effektlari, synthwave), `nr_world.js`
  (`NR3D.World.Track`: 3 trassa Neon Harbor / Sunset Canyon / Downtown Rush — yopiq CatmullRom spline, `at(d,lat)`, `locate(x,z,hint)`
  (iterativ, xato < 5 sm), `curvAhead`, `pads` (power-up joylari); yo'l/to'siq/neon lenta, instanced binolar/qoyalar, Points chiroqlar),
  `nr_race.js` (`CARS` viper/hornet/bulldog/phantom — `mergeBoxes` bilan ~3 draw call/mashina, arkada fizika + drift, ikki doirali
  to'qnashuv, `aiInput` (poyga chizig'i, egrilik bo'yicha tezlik, rubber-band, `aiUse`), `PU` 8 ta: seeker/volt/blast/mine/shield/
  nitro/repair/storm, teskari yo'nalish/tiqilishda `reset()`), `nr_game.js` (Engine avtomatik sifat, Input tugmalar/giroskop/klaviatura,
  UI menyu/HUD/minikarta/natija, `NR3D.launch({playerName,onResult,onExit})`), `nr_style.css` (`.nr3d`). Server: umumiy `GAME_DIRS`
  (`/app/games/<o'yin>/<fayl>`, `_game_file(game,name)`), `cs_game_version(game)`, `__NR_VER__`. Web: `game3d(...)` yuklovchi,
  `NRUSH`, VIP'da `#vipNR` karta + TOP. Natija `vip/score` game=`nrush` (`nrush_check`: place/cars/fans/hits bo'yicha chegara), payload
  `vip.nr_best`/`nr_top` (level = o'rin).
- 🎯 CLASSIC STRIKE grafikasi yangilandi: 256px protsedura teksturalar (`canvasTex(base, kind)` brick/block/tile/concrete/crate/cont/metal),
  `boxM` — UV metr bo'yicha (cho'zilmaydi), gradient osmon + quyosh, tuman = ufq rangi, devor tagida AO lentalari (instanced), devor
  qirralari, arena tashqarisida siluetlar, ombor tomi/chiroqlari, mashina kabinasi/g'ildiraklari, botlarda jilet/ryukzak/etik + oyoq
  soyasi. Engine: zaif qurilmada (`deviceMemory<=3` yoki `hardwareConcurrency<=4`) auto → low; medium/high'da antialias.
- 🚗 NEON RUSH realistik mashinalar: `games/neon_rush/car_hi.glb` (~34k uchburchak, yaqin) + `car_lo.glb` (~9k, uzoq LOD, teksturasiz) —
  "Car Concept" (Eric Chadwick / Khronos glTF-Sample-Assets, **CC BY 4.0**; asli Unity Fan CC0), Khronos logotiplari/salon olib tashlangan,
  `tools/cars/build.mjs` (gltf-transform: prune/join/simplify/webp/quantize/meshopt) + `tools/cars/README.md`. Atribusiya o'yin ichida
  (HOW TO PLAY → `.nr-cred`). Klient: `NR3D.Models.load(assets, ver)` (jsdelivr three@0.128 GLTFLoader + meshopt_decoder; xato bo'lsa
  protsedura mashinalarga qaytadi), `prepModel` (frustumCulled=false — kvantlangan geometriya, tekstura LinearEncoding, rang/shina/disk
  sozlamalari), `modelFor`: o'yinchi — hi, botlar — `THREE.LOD` (hi <14 m, lo), past sifat — `loLambert`; bo'yoq har mashinaga klon
  (`paintMats`, `ACCENT`, `SHAPE` masshtab), `envFor` — trassa osmoni + neon panellardan PMREM (scene.environment, poyga tugaganda
  render target tozalanadi). Web: `NRUSH` launch `assets:'/app/games/neon_rush/'`, `ver`; GLB'lar `NR_GAME_FILES` da (`model/gltf-binary`).
  Tormoz endi orqaga yurgizmaydi (start sanog'ida mashina orqaga ketib qolardi).
- 🚇 METRO DASH (3D cheksiz runner, ORIGINAL o'yin; VIP → owners-only test): `games/metro_dash/` — `md_core.js` (`MDASH.U`, `MDASH.Save`
  localStorage `metro_dash_v1` — tangalar/personajlar/taxtalar, `MDASH.Audio` sintez + hip-hop chiptune), `md_world.js` (`MDASH.Assets`
  — `md_world.glb` nomlangan tugunlar + `md_char_<m|f><a-f>.glb` animatsiyali personajlar, `World`: 3 yo'lak `LANES` ±1.5, shpallar
  instanced, graffiti devorlar (canvas), binolar, generator `generate` — trains/rampTrain/barriers/mixed/moving/wall2/coins naqshlari,
  har doim o'tib bo'ladigan yo'l; `groundAt` — poyezd tomi `ROOF` 1.57 / rampa), `md_game.js` (Engine avto-sifat, `Game.step` 1/120
  qadam: sakrash/sirpanish/yo'lak, old tomondan urilish → crash, yondan → qoqilish + 🚨 dron (`CHASE_T` 8 s ichida 2-qoqilish = ushlanish),
  power-up `PU` magnet/jet/boots/x2, 🛹 uchar taxta (ikki marta bosish, 1 urilishdan qutqaradi), `MDASH.launch({assets, ver, onResult, onExit})`),
  `md_style.css` (`.mdash`). Modellar Kenney **CC0** (Train Kit, City Kit Commercial, Mini Characters), qayta yig'ish `tools/runner/`.
  Natija `vip/score` game=`mdash` (`mdash_check`: dist ≤ 17·t+20, score ≤ 2·dist+5, coins ≤ 2·dist+50; level = masofa).
- 🐍 NEON SNAKE (`games/neon_snake/`, `window.NSNK`, 2D canvas, three yuklanmaydi — `game3d(..., no3d=true)`): Classic/Portal/Labirint,
  kombo x1–x10, oltin olma, power-up'lar; `nsnake_check`: score ≤ (foods·10 + golds·50)·maxMult, maxMult ≤ 10.
  🧱 BLOCK STORM (`games/block_storm/`, `window.BSTORM`, 2D canvas; "Tetris" nomi/brendi ishlatilmaydi): 7-bag, SRS kick, hold, ghost,
  T-spin, B2B, kombo, Marafon/Sprint 40/Zen; `bstorm_check`: lines·10 ≤ pieces·4, score ≤ (lines·1800 + pieces·60)·maxLevel (≤30),
  `VIP_GAME_MAX["bstorm"]`. Tekshiruvlar `VIP_CHECKS` lug'atida; payload `vip.md_*/ns_*/bs_*` (best/top).
- 🤖 Loyiha agentlari `.claude/agents/`: architect, debugger (opus, effort max), game-dev, qa-tester, reviewer, asset-builder (opus, high),
  deploy-watcher (sonnet). Agentlar commit/push qilmaydi — bosh sessiya qiladi.
- 🧪 Web testerlar (haqiqiy odamlar jamoasi): web Owner panel → 🧪 Testerlar (`testerAdmin`, `/app/api/testers/{add,remove}` →
  `web_tester_admin`, faqat ownerlar, ID/@username `chat_resolve`, maks `WEB_TESTERS_MAX` 200, qo'shilganda bot xabari). Jadval
  `web_testers` (`init_webapp`), kesh `_TESTERS` (`web_testers()`), `is_tester`, `can_test(uid)` = owner yoki tester. Test rejimidagi
  gate'lar `can_test` bilan: `web_enabled_for`/`webapp_fetch` ("faqat ownerlar" rejimi), `vip_enabled_for`, `is_vip`, `kami_enabled_for`,
  `avatar_enabled_for`, `emp_enabled_for`. Owner huquqlari (panel, flaglar, VIP berish) testerlarga berilmaydi. Payload `testers` (owner),
  `is_tester`.
- 🏆 TOP (web app pastki tab "TOP", `#s-reyting`, `topsRender`/`TOPC`): kategoriyalar 💎 Boylar (`rich`), 🏦 Kreditchilar (`loan_max`/
  `loan_sum` — `bank_loans`), 🎰 Qimorvozlar (`gamble_all`/`gamble_crash|frog|kami`), 💞 Juftliklar (faol `pairs`, birga kunlar + farzand),
  💔 Ajrashganlar (`pairs.status='ended'`), 👶 Farzandlilar (`family_children` parent1/2), 🎁 Sovg'alar (`gifts_sent` — sender, `gifts_held` —
  hozirgi egasi `gift_log.recipient_id`). Podium (1–3) + ro'yxat (TOP 15) + "Sizning o'rningiz". Server `tops_payload(uid)` (payload `tops`),
  Ko'rinish kategoriya bo'yicha (`_top_access`): ochiq bo'limlar (boylik, kredit, juftlik, ajrim, farzand, sovg'a, Crash/Hovuz, bot
  o'yinlari) — hammaga; test rejimidagi o'yinlar (Kamikaze — `kami` flag, VIP o'yinlar — `vip` flag) reytingi faqat `can_test`
  foydalanuvchilarga, "TEST" belgisi bilan (payload `tops._test`); flag yoqilsa avtomatik hammaga ochiladi. `gamble_all` ga Kamikaze
  faqat `kami` ochiq bo'lsa kiradi. Alohida "tops" flag yo'q.
  ro'yxatlar `_top_lists` 60 s kesh (`TOP_CACHE_TTL`), manbalar `_top_sources` (boylik/kredit/qimor reytingiga ownerlar kirmaydi).
  Qimor statistikasi `gamble_stats` (user_id, game, plays, wagered, won, best_win, best_mult) — `gamble_note` web Crash/Hovuz/Kamikaze
  tikish, yutuq, bekor qilish/qaytarishda (deploy'dan keyin yig'ila boshlagan).
  Botdagi Crash (`crash_charge`/`crash_refund`/cashout → `bot_crash`) va Qurbaqa ("go" tikish, `frog_settle` → `bot_frog`) ham
  `GAMBLE_GAMES` da. VIP o'yin reytinglari (`TOP_VIP`, manba `vip_scores`): 🏁 Poygachilar (nrush, a=o'rin), 🎯 Merganlar (cstrike frag /
  strike 2D raund), 🧱 Blokchilar (bstorm), 🚇 Yuguruvchilar (mdash, a=masofa), 🐍 Ilonchilar (nsnake).
- 🐍 NEON SNAKE: ekrandagi D-pad standart yoniq (`defaults().dpad=true`, saqlash `v: 2`; eski v1 saqlanganlar ham yoqiladi),
  sozlamalardan o'chirsa saqlanadi.
- 📅 Kredit endi OYLIK foiz bilan: `LOAN_TERM_DAYS` 30, `LOAN_DAYS=(30,)`, `loan_due(amount, days, rate)` = amount + amount·rate·days/30
  (banklar `loan_rate` — oylik), `loan_daily(due)`. Yangi kredit `bank_loans.plan='monthly'` (+ `paid`, `next_at` ustunlari, migratsiya
  `init_bank`): `bank_settle_due` har kuni round(due·n/30) gacha yechadi (balans minusga tushishi mumkin, `n_inst` xabari), 30-kunda
  status `paid`. `active_loan()[3]` = QOLGAN qarz (due − paid) — to'lash/ko'rsatish shu bilan. Eski 1–7 kunlik kreditlar `plan='once'` —
  eski qoidada (`due_at` da birdan). Web payload `bank.loan`: monthly/daily/paid/total.
- 🧹 Kredit amnistiyasi (web Owner → ⚙️ Sozlamalar, `amnestyCard`, ikki bosqichli tasdiq): `/app/api/owner/amnesty` → `web_amnesty`
  (faqat ownerlar, `confirm` shart): faol kreditlarning qolgan qarzi hamyondan yechiladi, status `forgiven`; so'ng `money<0` → 0;
  ta'sirlanganlarga bot xabari, `log_money_event`. Ko'rinish `amnesty_preview` (payload `amnesty`).
- ⚖️ Ajrimchilar: web Owner → ⚖️ Ajrimchilar (`judgeAdmin`, `/app/api/judges/{add,remove}` → `web_judge_admin`, jadval `judges`,
  `is_judge`/`judges()` kesh). `notify_pair_owners` — `JUDGE_KINDS` (pair, divorce) arizalari ownerlar + ajrimchilarga; `rel:owner`
  callback ajrimchiga faqat shu turlarda ruxsat (ishdan bo'shash va boshqa owner amallari — yo'q).
- 🍱 Farzandlar uchun premium to'yimli ovqatlar — 📦 TO'PLAM orqali: `KID_PREMIUM` (12 taom/shirinlik: yosh oralig'i, kayfiyat bonusi,
  nomi, tavsif; 3-maydon — eski donalik narx, ishlatilmaydi). To'plam umumiy narxi `kid_pack_price()` (webapp_config `kid_pack_price`,
  standart `KID_PACK_DEFAULT` 1 EMP, 0–100 000) — web Owner → 🪙 EMP → "🍱 Farzand ovqatlari to'plami" (`/app/api/owner/kidpack` →
  `web_kid_pack_price`, faqat ownerlar). Sotib olish `/app/api/kid/pack` → `web_kid_pack_buy` (`emp_enabled_for`, EMP atomik) — har taomdan
  +1 ota-onaning zaxirasiga (`kid_food_stock` jadvali, user_id+item). Berish: farzand kartasida "🍱 Premium" (`premiumSheet`: to'plam
  tugmasi, kartalarda ×zaxira, yoshga mos bo'lmasa 🔒), `/app/api/kid` act=`premium` → zaxiradan 1 ta (`no_stock`), to'qlik = 100,
  kayfiyat +bonus; 12 soatlik qoida saqlanadi (vaqti kelgan bo'lsa `kid_eat`); to'q va xursand bo'lsa `full`. Payload `kid_pack`, `kid_premium`.
- 🎙 Ovozli xonalar (Telegram uslubi; web app → Chat tepasida `#vcCard` — ro'yxat `#vcRooms` + "➕ Xona yaratish"; test —
  `voice_enabled_for`: webapp_config "voice" yoki `can_test`; Owner → ⚙️ Sozlamalar → "Ovozli xona — hamma uchun"). `VOICE_ROOMS`
  (xotirada): doimiy `VOICE_MAIN` "🎙 Umumiy xona" + foydalanuvchi xonalari (nomi 2–40, bittadan ko'p emas, jami `VOICE_ROOMS_MAX` 20,
  bo'sh qolsa `VOICE_EMPTY_TTL` 120 s da yopiladi). Bitta odam bitta xonada (`VOICE_WHERE`), xonada maks `VOICE_MAX` 10 (mesh).
  Xona egasi (yoki bot egasi, `_voice_admin`): a'zoni 🔇 majburiy jim qilish (`forced`, klientda trek o'chadi, mic tugmasi bloklanadi),
  🚪 chiqarish (`VOICE_KICK_BAN` 120 s qayta kira olmaydi), 🗑 xonani yopish (umumiy xonani yopib bo'lmaydi). API
  `/app/api/voice/{rooms,create,join,leave,poll,signal,state,kick,mute,close}` → `web_voice`; signal faqat shu xonadagilarga,
  ≤ `VOICE_SIGNAL_MAX`; `VOICE_STALE` 15 s poll bo'lmasa chiqariladi; restartda xonalar bo'shaydi. WebRTC mesh, ICE: Google STUN +
  ixtiyoriy TURN env `VOICE_TURN_URL`/`VOICE_TURN_USER`/`VOICE_TURN_PASS`. Klient `VOICE` (`list/refresh/create/open/close`, `#vcv`):
  yangi kirgan (seq katta) offer yuboradi, ~700 ms polling, AnalyserNode bilan gapirayotgan (yashil halqa), 👑 egasi belgisi, admin a'zo
  kartasini bosib boshqaradi. Payload `voice` (rooms/count/max), `voice_test`.
- 🎬 Media (YouTube; test — `media_enabled_for`: webapp_config "media" yoki `can_test`; Owner → ⚙️ "Media (YouTube) — hamma uchun"): Games →
  🎬 MEDIA (`.gcc.media`) → `#s-media` (`mediaPage`, `MEDIA` modul, "‹ Games"). Video FAQAT rasmiy IFrame pleyerda (`ytApi`/`ytMake`,
  youtube-nocookie, playsinline) — yuklab olinmaydi/saqlanmaydi; embed taqiqlangan (101/150) → "↗ YouTube'da ochish" (`tg.openLink`).
  API `/app/api/media/{home,search,cat,resolve,fav,watched,history}` → `web_media`. Qidiruv/kategoriyalar — YouTube Data API v3,
  kalit env `YOUTUBE_API_KEY` (faqat serverda; bo'lmasa `search:false` — faqat havola). Havola — oEmbed (kalitsiz, `MEDIA_URL_RE`).
  Kvota: kesh `_MEDIA_CACHE` (qidiruv 6 s, kategoriya 3 s), `MEDIA_DAILY_SEARCH` 90/kun (UTC), foydalanuvchi `MEDIA_USER_RATE` 12/10 daq
  (ownerlarga yo'q); `MEDIA_CATS` trend/music/funny/sport — mostPopular (1 birlik, UZ), yo'q bo'lsa qidiruv; kino (long)/multfilm — qidiruv.
  Jadvallar `media_favs` (200) / `media_history` (60). 👥 Birga ko'rish: ovozli xona `room["media"]` (vid/playing/pos/at/by/v),
  `voice/media` op set|play|pause|seek|stop (`voice_media_act`; boshqaradi xona egasi/bot egasi, qo'ygan odam yoki hech kim qo'ymagan
  bo'lsa har kim), holat poll/join javobida `voice_media_view` (pozitsiya server soati bo'yicha). Klient VOICE ichida `mdSync`/`mdApply`
  (drift >3 s → seek, boshqaruvchi pleyeridagi pauza/play `mdState` orqali hammaga), xonada 🎬 tugma (`mdPicker`), Media pleyerida
  "👥 Xonada birga". 📚 Kalitsiz rejim: ownerlar to'ldiradigan ro'yxatlar `media_lists` (cat, vid UNIQUE, `MEDIA_LIB_MAX` 300/kategoriya):
  Media sahifasida owner uchun `#mdAdm` (bir nechta havola, `media_lib_add` — oEmbed, takror/embed taqiqlangan o'tkaziladi, ≤30),
  kartalarda 🗑 (`media/del`), pleyerda "📌 Kategoriya ro'yxatiga" (`media/add`). `cat`/`search` — avval `media_lib` (qidiruv LIKE
  nom/kanal bo'yicha), kalit bo'lsa `_media_api` natijalari qo'shiladi (API xatosida ro'yxat + `warn`). z-index: `.ov` 96 (sheet'lar ovozli xona ustida), `#vcv` 92, `#mpv` 91, toast 99.
- 💎↔🪙 Empire Mafia bilan kurs: 3 💎 = 1 EMP, komissiyasiz — `init_webapp` da bir martalik `swap_3d1e` belgisi bilan `exchange_asset_config.rate=1/3, fee=0`
  (keyin owner panelda o'zgartirilsa o'sha qoladi). `swap_quote` floor + 1e-6 (float xatosi), payload `swap.rate_txt` ("3 💎 = 1 EMP").
  Hamkor (empire-bot) tomonda `DIAMONDS_PER_EMP`/`EMP_FEE_PCT` bir xil bo'lishi kerak.
- 🪙→💎 Botdagi almashuv menyusida (`exchange_menu_view`, `cb_exchange` `ex:<uid>:e|eg:<n>`) EMP→olmos tugmalari (`EMP_SWAP_AMOUNTS`) —
  `web_emp_swap` orqali; `swap_ready()` va `emp_enabled_for` bo'lsa chiqadi. `init_webapp` da bir martalik `swap_on1` — almashuv yoqiladi.
  Hamkor manzili `EXCHANGE_PARTNER_URL` dan faqat sxema+domen olinadi; rad etilsa xabarda sabab (`exch_fail_reason`, HTTP kodi).
- 🚫 Botdan foydalanishni cheklash: shaxsiy chatda `/ban ID|@username [sabab]`, `/unban ID`, `/ban` (ro'yxat) — faqat `CAREER_OWNER_IDS`
  (`cmd_mod` shaxsiy chatda `cmd_botban` ga yo'naltiradi; guruhdagi `/ban` — oddiy moderatsiya). Jadval `bot_bans`, kesh `BOT_BANS`
  (`init_botban`), `is_bot_banned` (ownerlar hech qachon). `botban_guard` — `TypeHandler` group=-100: cheklanganning har qanday
  update'i to'xtatiladi (callback alert, shaxsiyda 10 daqiqada bir ogohlantirish). Web app: `webapp_check_init_data` None qaytaradi.
- 💞 Juftlik ↔ Empire Mafia parasi: `para_sync_bg(op,a,b)` → `POST {EXCHANGE_PARTNER_URL}/exchange/para` ({op: pair|unpair, a, b, ts}, o'sha HMAC)
  `rel:owner` va /tasdiq'da juftlik/ajrashish tasdiqlanganda. Kiruvchi `/exchange/para` → `para_apply_incoming`: pair — ikkalasida faol
  juftlik yo'q, ikkalasi botni ishlatgan, jinslar qarama-qarshi bo'lsa juftlik (pair_merge_kids); unpair — shu juftlik bo'lsa ajrashish
  (`divorce_settle(c, pair, 0)` — vasiylik standart qoida, `divorce_notify`). Bir martalik `para_sync_v1` (`para_sync_initial`) — mavjud juftliklar Empire'ga.
- 👑 VIP ↔ Empire Mafia: `web_vip_grant` (berish/uzaytirish/olish) → `vip_sync_bg(uid, until)` → `POST {EXCHANGE_PARTNER_URL}/exchange/vip`
  ({user_id, until (0 = yo'q), ts}, o'sha HMAC). Kiruvchi `/exchange/vip` (`_vip_in` → `vip_apply_incoming`): faqat `src=="buy"`
  (Empire'da YANGI xarid) qabul qilinadi — muddat `max(joriy, kelgan)` gacha uzaytiriladi; `src` yo'q / boshqa yoki until ≤ hozir →
  200 `{"result":"ignored"}` (hamkor qayta urinmaydi). Kiruvchi so'rov bu yerdagi VIP'ni hech qachon olmaydi/qisqartirmaydi; qayta push QILINMAYDI. Ownerlar `is_vip` orqali doim VIP — push yo'q. Bir martalik `vip_sync_v1`
  (`vip_sync_initial`) — faol VIP'lar Empire'ga.
- 🚀 Test rejimdan chiqarildi (`init_webapp` bir martalik `tests_open_v1`, `webapp_flags` standartlari): Kamikaze, VIP o'yinlar, ovozli xona, EMP — hamma uchun. 🧍 3D avatar va 🎬 Media (`media_test_v1`) test rejimida qoladi (owner panelda yoqiladi).
- 👑 VIP: `/vips` (ownerlar, `cmd_vips`) va web Owner → 👑 VIP ro'yxati — olgan sana, tugash, qolgan vaqt, kim bergan (`vip_list`: since/left/by). Web app'da VIP sotib olish `/app/api/vip/buy` → `web_vip_buy`: `VIP_EMP_PRICE` 11 EMP → `VIP_BUY_DAYS` 30 kun (faol bo'lsa uzaytiriladi, EMP atomik, `vip_sync_bg` → Empire); VIP sahifasi tepasida `.vipbuy` karta.
- 🌐 VIP o'yinlar MULTIPLAYER: server `web_mp` (`/app/api/mp/{list,create,quick,join,leave,start,end,sync}`, faqat VIP) — xotirada `MP_ROOMS`
  (5 belgili kod, host, `MP_GAMES` maks o'yinchilar, seed/round, `private`), `MP_WHERE`; o'yinchi holati (`state` ≤ `MP_STATE_MAX`) va
  hodisalar navbati (`ev`, `eseq`, `after` bilan), `MP_STALE` 12 s → chiqariladi, host chiqsa egalik o'tadi. Server faqat uzatadi.
  Klient `games/mp/mp.js` (`MPNET.lobby` — tez o'yin / xona yaratish / yopiq xona / kod bilan / ochiq xonalar; `Session` ~110 ms sync,
  `send/emit/on('sync'|'event')`, `isHost`, `start`) + `games/mp/kit.js` (`AKIT`: three renderer, joystik, menyu, sfx, label) + `mp.css`.
  Web: `MPKIT` yuklovchi, `mpGame(...)`. Yangi VIP o'yinlar (solo + online): 🛡 TANK ARENA (`games/tank_arena/ta.js`, `TANKA`, 8 kishi DM,
  15 frag/4 daq; o'q egasi emas — qurbon zararni hisoblaydi, `die` hodisasi), 💥 BUMPER ARENA (`games/bumper_arena/ba.js`, `BUMPA`, 6 kishi,
  torayuvchi maydon, 3 jon, `out` hodisasi), 🚢 DENGIZ JANGI (`games/sea_battle/sb.js`, `SEAB`, 4·3·3·2·2·2·1·1·1·1, AI oson/ov/ehtimollik,
  online `ready/fire/res`), ⚪ SHASHKA (`games/checkers/ck.js`, `CHECK`, rus qoidalari, alpha-beta 2/4/6, online `mv` yo'li tekshiriladi).
  Rekordlar `tank_check/bumper_check/sea_check/checkers_check` (faqat solo), payload `vip.<o'yin>_best/_top`.
  NEON RUSH online: menyu "🌐 ONLINE" (`GP.online/startNet`), `Race({net})` — boshqa o'yinchilar `c.remote` (`netStep`, `netState`), power-up
  `use` hodisasi, trassa = xona `mode`, pauza yo'q. CLASSIC STRIKE online: `RoundManager.online` (DM 25 frag, botlarsiz), boshqa o'yinchilar
  bot modeli (`netBot`, `CS3D.netHandlers`), zarar `hit` → qurbon `die`, o'q izi `sh`; xarita = xona `mode`.
- 🏪 EMPIRE MARKET (web app → Games → `.gcc.mkt` → `#s-market`, `marketPage`/`MARKET`, "‹ Games"; Fragment uslubi; test — `market_enabled_for`:
  webapp_config "market" (standart 0) yoki `can_test`; Owner → ⚙️ "Market — hamma uchun", `OWNER_FLAG_KEYS`). Tablar ⭐ Premium / 🎁 Gifts /
  🌟 Stars / 💎 NFT / 🧾 Buyurtmalarim. Avtomatik (botning ⭐ balansidan): Premium 3/6/12 oy (`MARKET_PREMIUM` 1000/1500/2500 ⭐ →
  `gift_premium_subscription`), Gifts (`get_available_gifts` 10 daq kesh `_MARKET_GIFTS`, eskizlar `tg_sticker_files` → `/app/tgs/`, `send_gift`);
  sotishdan oldin `get_my_star_balance` (30 s kesh) ≥ tannarx, aks holda "Vaqtincha mavjud emas". Qo'lda (Bot API yetkaza olmaydi): Stars paketlari
  (`MARKET_STARS_PACKS`) va NFT (`market_nft`, ownerlar qo'shadi; rasm `_chat_save_image` → `/app/newsimg/` yoki https havola) — to'langach
  navbat + ownerlarga bot xabari, web Owner → 🏪 Market'da "✅ Yetkazildi" / "↩️ Qaytarish". Narx = tannarx × (1+ustama%) yuqoriga
  (`market_price`); `market_config` (markup, premium/gift/stars/nft yoqish, `emp_per_star` — 0 bo'lsa EMP bilan to'lash yo'q). Buyurtma
  `market_orders` (status pending→paid→delivered | refunded | failed; `charge_id` UNIQUE, EMP to'lovda `emp:<id>`); qabul qiluvchi o'zi yoki
  `chat_resolve`. To'lov: `create_invoice_link` payload `mk:<order>:<uid>:<stars>` → `on_pre_checkout` (`market_check_payload`: egasi, pending,
  1 soat TTL, narx, NFT sotilmagan) → `on_successful_payment` (`market_on_payment`: takror update e'tiborsiz, yopilgan buyurtmaga 2-to'lov
  avtomatik `refund_star_payment`) → `market_fulfil`; avto yetkazish xatosi → `market_refund` (⭐ refund yoki EMP qaytadi). API
  `/app/api/market/{catalog,order,state}` + ownerlar `{config,nft_add,nft_update,nft_toggle,nft_delete,deliver,refund,balance}` → `web_market`.
  Payload `market` (`market_payload`; ownerga `admin`: cfg, balans, navbat, NFT, statistika). Kod bloki `# ── 🏪 EMPIRE MARKET` … `/EMPIRE MARKET`.
  🎞 Rasmiy animatsiyalar: klient `MKA` (IntersectionObserver — faqat ko'rinayotganlar, bir vaqtda ≤ `MK_ANIM_MAX` 8, `lottieLoad`,
  bo'lim/tab almashganda `MKA.clear`, eskiz/emoji — joy egasi; xarid oynasida `data-pri` katta). Gifts — to'liq `gift.sticker`
  (tgs/webm) `/app/tgs/`. Premium — `market_premium_stickers`: `MARKET_PREMIUM_STICKER_SETS` (PremiumGifts → GiftsPremium →
  AnimatedEmojies ⭐/🎁) `get_sticker_set`, oy moslik `_premium_pick`, kesh `market_cache` 1 kun (topilmasa 1 soatda qayta; ⭐ emoji).
  NFT — owner `t.me/nft/<Name-N>` yoki slug (`nft_slug_norm`, `^[a-z0-9]+-[0-9]{1,7}$`; `market_nft.slug/meta`) → proksi
  `GET /app/nft/<slug>.{tgs,webp,json}` (`nft_asset`: faqat nft.fragment.com, redirect yo'q, 2 MB, volume `nft_cache/`, 1 kun kesh;
  .tgs → ochilgan Lottie (to'liq karta: model+fon+naqsh), .json → nom/#raqam/Model·Backdrop·Symbol + fon ranglari `_nft_bg`
  (webp'dan); `original_details` olinmaydi). Fragment rarity % bermaydi. Havolasiz NFT — eski rasm yuklash.
  🤖 NFT AVTOMATIK (Telethon userbot, `telethon==1.45.0`, kerak bo'lganda import): umumiy qatlam `ub_*` (keyingi per-user userbotlar
  uchun ham): `ub_tl` (TL klasslari), `ub_make_client`, `ub_connect(session, expect_id)`, `ub_err`, `ub_session_encrypt/decrypt`
  (Fernet `f1:`, kalit env `USERBOT_SESSION_KEY`; kalit bo'lmasa login/saqlash rad — `ub_key`, owner'ga ogohlantirish). Faqat
  `NFT_USERBOT_ID` (1150777456): owner web Owner → 🏪 Market → 🤖 Userbot: telefon → kod → 2FA (`ub_send_code/ub_code/ub_password`,
  10 urinish/10 daq), `get_me().id` boshqa bo'lsa `log_out` + rad. Sessiya `nft_userbot` (shifrlangan; env `NFT_USERBOT_SESSION` ustun),
  payload/logga chiqmaydi. Env: `TG_API_ID`, `TG_API_HASH`, `USERBOT_SESSION_KEY`. Resale: `nft_collections` (follow / `rs_all`),
  `nft_rs_sync` (getStarGifts + getResaleStarGifts stars_only, ko'rinmagan narxlanganlar getUniqueStarGift; `nft_rs_worker` ~10 daq,
  "🔄 Sync" fonda) → `nft_resale` (slug kichik harf — `/app/nft/` proksi, `tg_slug`, cost, approved_cost, price, enabled, available,
  sold, reserved). Narxsiz listing sotilmaydi; `rs_price` = narx + joriy tannarxni tasdiqlash, `rs_bulk` (cost×(1+%) — narxsiz/qayta
  tasdiq/hammasi); Telegram narxi > approved → `reapprove`. Buyurtma item `r<id>` (`nft_rs_id`): invoysdan oldin `nft_rs_precheck`
  (hali sotuvda, narx, userbot ⭐ balansi, qabul qiluvchi — ID keshda yoki @username, ID mos bo'lishi shart → `no_username`),
  `nft_rs_reserve` (CAS). To'lov → `nft_rs_fulfil`: paid→`buying` (atomik) + `_NFT_BUY_LOCK` → qayta tekshiruv → getPaymentForm
  (narx ≤ approved) → sendStarsForm (InputInvoiceStarGiftResale) → delivered/sold; xato → reserved=0 + `market_refund` + ownerlarga
  xabar; tarmoq uzilishi (noaniq) → `failed`, qaytarilmaydi, owner navbatda hal qiladi. Jurnal `nft_resale_log`. Userbot ulanmagan bo'lsa
  resale "Sotuvda yo'q" (offline), qo'lda NFT'lar ishlayveradi. Payload: `nft` ichida `rs`/`state`; ownerga `admin.ub`, `admin.rs`.
- 🔐 Umumiy userbot login (NFT owner + UTag): `ub_login(store, uid, act, body, expect_id, device)` — act send_code/resend/code/password/cancel;
  `ub_norm_phone` (bo'shliq/nuqta/chiziqcha/qavs, unicode raqamlar, `00<cc>`→`+<cc>`, E.164 8–15 raqam; mamlakat kodisiz → `phone_local`,
  +998 hech qachon taxmin qilinmaydi; `UB_PHONE_HINT`), `ub_norm_code` (5–6 raqam, bo'shliq/chiziqcha), `ub_err_info` → (kod, flood soniyasi):
  phone_invalid/phone_banned/phone_unoccupied/flood/api_id_invalid/send_code_unavailable/email_setup/code/code_expired/password;
  `ub_sent_info` (delivery app/sms/call/flash_call/missed_call/email/fragment_sms/firebase + len + next) → UI ko'rsatma (`UBDLV`/`ubDeliveryHint`),
  `next` bo'lsa "qayta yuborish" (`auth.resendCode`, act `resend`/`ub_resend`); `ub_call_migrate` — PhoneMigrate/NetworkMigrate'da DC almashtirib 1 marta qayta;
  `ub_log_err` — logga faqat klass + RPC xabari. JS xatolari `UBERR`/`ubErr`. NFT login (`nft_ub_login`) shu helper ustida.
- 🏷 UTag (o'z akkauntidan guruhda hammani belgilash; kod bloki `# ── 🏷 UTAG` … `/UTAG`): ulanish FAQAT web app'da (`#s-utag`, `/app#utag`,
  Profil'dagi `.utc` karta; rozilik checkbox + ogohlantirish) — `/app/api/utag/{state,send_code,resend,code,password,cancel,logout,speed,buy}` →
  `web_utag` (`ub_login`, expect_id = o'zi, `UTAG_LOGIN_RATE`), sessiya `utag_accounts` da shifrlangan. Obuna `UTAG_PRICE_DIAMONDS` 10 💎 /
  `UTAG_DAYS` 30 kun (`utag_subs`, faol bo'lsa uzayadi): `utag_buy` → Empire `POST /exchange/debit_asset` {txid,user_id,asset:"diamond",amount,reason:"utag",ts}
  (X-Signature HMAC); `utag_record` (atomik, bir marta) yiqilsa `/exchange/refund_asset` {txid,orig_txid,...}; tarmoq/5xx → pending, `utag_worker`
  (30 s) o'sha txid bilan qayta (`utag_payments`, `UTAG_PAY_MAX_RETRY` → stuck + owner log). Tinglovchi: `utag_ensure_client` (Telethon updates=True,
  `NewMessage(outgoing=True)`, maks `UTAG_MAX_CLIENTS` 300) → `utag_on_message`: guruhda `.tag <matn>` (buyruq o'chadi, `utag_strip_command` — entitylar
  UTF-16 bo'yicha siljiydi, premium/custom emoji saqlanadi; `utag_build` + `InputMessageEntityMentionName`), a'zolar bot/deleted/o'zi'siz ≤600 (`UTAG_MAX_MEMBERS`),
  guruhda `UTAG_GROUP_COOLDOWN` 60 s, oraliq `utag_speed` 0.3–1.5 (`utag_settings`, standart 0.7), FloodWait ≤60 s kutadi, uzunroq → to'xtab bot xabari;
  `.stop`, obuna tugashi (`utag_tick`), uzish yurishni to'xtatadi. Bot: `utag_card`/`cb_utag` (`ut:<uid>:m|p|buy|ok|card`), `?start=utag`. Payload `utag`.
- 📋 Shaxsiy chat pastki menyusi: `/start` va `/emps` (shaxsiyda) doimiy `private_menu_kb()` (ReplyKeyboard, `PRIVATE_MENU`): Profil/Oila/Farzandlarim/
  Banklar/Birja/Almashuv/Do'kon/Reyting/Missiyalar/O'yinlar (guruh o'yinlari ro'yxati + guruhga qo'shish)/🏷 UTag/Ilova/Guruhga qo'shish/Til/Yordam →
  `on_private_menu` (`filters.Text(PRIVATE_MENU_MAP)`, career_private_text'dan oldin) mavjud handlerlarga yo'naltiradi. Guruhlar o'zgarmagan.
- 🎵 Musiqa (/play; kod bloki `# ── 🎵 MUSIQA` … `/MUSIQA`): ALOHIDA musiqa yordamchi akkaunti (Telethon userbot) — ownerlar web app → Owner →
  🎵 Musiqa'da ulaydi (`musicAdmin`, `/app/api/music/{state,send_code,resend,code,password,cancel,logout,reconnect}` → `web_music`, umumiy
  `ub_login`, istalgan akkaunt; sessiya `music_userbot` da shifrlangan). Ijro: py-tgcalls 3 (`music_ensure` → `PyTgCalls(client)`,
  StreamEnded → `music_on_end`, ChatUpdate kicked/left/closed → `music_clear`). Guruhda `/play nomi|havola` yoki audio/ovozli xabarga reply:
  manba `_music_fetch_sync` (yt-dlp: ytsearch1 → zaxira scsearch1; havola faqat `MUSIC_URL_HOSTS` youtube/soundcloud; YouTube havolasi
  yiqilsa oEmbed sarlavhasi bilan SoundCloud — `_music_targets`), Telegram audio `music_from_tg` (≤20 MB); fayllar `MUSIC_DIR`
  (`_music_pick_dir`: env `MUSIC_DIR` yoki /tmp/empire_music va volume'dan bo'sh joyi ko'progi — baza volume'i to'lmasin; eski volume keshi
  `music_cleanup_videos` da o'chadi; `music_cache_trim` 800 MB va diskda ≥2×`VIDEO_DISK_RESERVE` (150 MB) bo'sh; `music_disk_ok`/`music_disk_text` — aniq MB). `music_join`: yordamchi guruhda bo'lmasa — public → JoinChannel, yopiq → bot
  `create_chat_invite_link(member_limit=1)` → ImportChatInvite (join-request → `approve_chat_join_request`). Ovozli chat yo'q/huquq yo'q →
  bot yordamchiga `can_manage_video_chats` beradi va qayta uriniladi. Navbat `MUSIC_Q` (xotirada, `MUSIC_QUEUE_MAX` 25), trek ≤
  `MUSIC_MAX_DURATION` (env, 1800 s), /play `MUSIC_USER_RATE` 30 s da 3 ta. Boshqaruv `/skip /next /pause /resume /end /mstop /queue /navbat`
  (`cmd_music_ctl`) va tugmalar `mu:pause|resume|skip|end|q` (`cb_music`) — so'ragan odam, guruh adminlari, bot egalari.
  Server: ffmpeg+ffprobe (`nixpacks.toml` / `railpack.json`), `deno` (yt-dlp YouTube JS), ixtiyoriy env `YTDLP_COOKIES` (cookies.txt matni —
  datacenter IP'da YouTube "bot emasligini tasdiqlang" deydi; cookies'siz SoundCloud ishlaydi).
- 🎬 Video (/vplay, `/video`; o'sha 🎵 MUSIQA bloki va yordamchi akkaunt): FAQAT guruh adminlari / bot egalari. Video faylga reply (`_video_of`:
  video/video_note/animation/document video/*) → `music_video_from_tg`: yordamchi guruhga qo'shiladi va Telethon `download_media` bilan yuklaydi
  (Bot API 20 MB cheklovisiz, `VIDEO_FILE_MAX_MB` 1024, foiz progress, `music_disk_ok` — bo'sh joy). `/vplay nomi|havola` → `_music_fetch_sync(q, video=True)`
  (faqat YouTube ≤`VIDEO_QUALITY` p, mp4 merge; SoundCloud zaxirasi yo'q → cookies kerak bo'lishi mumkin). Trek `video: True`, fayllar `V_*` —
  keshlanmaydi: `music_discard` (o'tkazish/tugash/to'xtatishda o'chadi), ishga tushganda `music_cleanup_videos`. Bir vaqtda `VIDEO_MAX_CHATS` 2
  guruhda (`music_video_busy`), uzunlik `VIDEO_MAX_DURATION` 3 soat. Video trek tugashi VIDEO StreamEnded bo'yicha (audio — AUDIO), qayta
  boshlangandan 2 s ichidagi tugash e'tiborsiz. Pozitsiya `music_pos` (off/at/pos_p, server soati); ⏪/⏩ `MUSIC_SEEK` 30 s va 🎚 sifat
  (`VIDEO_QUALITIES` 360/480/720, `q["vq"]`) — `music_start_track(offset)` ffmpeg `-ss` bilan qayta boshlaydi (tugmalar `mu:back|fwd|vq`).
  Umumiy navbat `music_enqueue` (🎵/🎬 aralash).
- 🏷 UTag `.tags [matn]` (`UTAG_CMD_RE` tags|tag|stop): `.tag` bilan bir xil, lekin har bir mention yoniga `UTAG_PHRASES` (18 ta hazil gap)
  dan biri qo'shiladi — `utag_phrase_seq` (aralashtirilgan bloklar, ketma-ket takrorlanmaydi), `utag_build(..., tail)`, `utag_run(phrases=True)`.
  Web app UTag bo'limida "📖 Qisqa yo'riqnoma" (`.utguide`), bot kartasida `UTAG_HELP` ham `.tags` ni aytadi.
- 🎵/🎬 Xabarlar tozaligi: `_music_del(chat, *mids, delay)`; trek boshlanganda uning "➕ Navbatga qo'shildi" xabari (`track["qmsg"]`) o'chadi,
  `music_leave` (navbat tugashi, /end, ovozli chat yopilishi) "🎵 Hozir…" xabarini va navbatdagilar xabarlarini o'chiradi; "✅ Navbat tugadi" 15 s dan keyin o'chadi.
