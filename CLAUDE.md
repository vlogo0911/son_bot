# son_bot (@empire_statsbot)

- Asosiy fayl: `bot.py` (Railway `Procfile`: `web: python bot.py` — web app/almashuv HTTP serveri public domen orqali ishlashi uchun `web` jarayon). Barcha o'zgarishlar shu faylda qilinadi.
  Foydalanuvchi yuklagan `probot.zip` ichidagi `bot.py` shu repodagi bilan bir xil; zip'dagi
  `*.backup*` / `*.before_*` fayllar faqat eski zaxira nusxalar.
- Railway shu repodan avtomatik deploy qiladi (GitHub commit statuslarida ko'rinadi).
  Agar main commitida status/deployment paydo bo'lmasa — Railway webhook'i ishlamagan: Railway'da "Deploy latest commit" yoki yangi push.
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
  ownerga `vip_list`; owner panel → 👑 VIP (`vipAdmin`, `/app/api/vip/grant` — `web_vip_grant`, 0 kun = olib qo'yish, berilganda bot xabari).
  VIP o'yin: 🕹 STRIKE 2D (`STRIKE` modul, WEBAPP_HTML ichida) — eski Nokia telefonlaridagi kontr-terror o'yinlari uslubidagi original
  o'yin (nom va grafika o'zimizniki): monoxrom LCD 168×120 canvas (pixelated), 3×5 piksel shrift, urug'li protsedura xarita
  (`genMap(level)`, flood-fill bilan ulanish), dushmanlar patrul/hujum (LOS), hitscan o'q + nishonga olish yordami, bosqichlar
  (dushmanlar 3+2·L, HP +35). Boshqaruv — telefon klaviaturasi `#csv` (2/4/6/8, 1/3/7/9 diagonal, 5 o'q, 0 o'qlash, * pauza, # chiqish)
  va klaviatura (WASD/strelka, Space, R). Ovoz — square beep (`SFX`). Rekord `/app/api/vip/score` → `vip_scores` (`web_vip_score`:
  faqat VIP, score ≤ level·4000, 8 s da bir).
