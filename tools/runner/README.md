# METRO DASH 3D resurslari

Natija (`games/metro_dash/`):
- `md_world.glb` (~350 KB) — poyezdlar (subway/city/konteyner/tramvay), rels, binolar, osmono'par binolar, bezaklar;
  har model alohida nomlangan tugun (`train-electric-subway-a`, `building-a`, ...), JS `MDASH.Assets.clone(nom)` bilan oladi.
- `md_char_<m|f><a..f>.glb` (~96 KB) — 12 personaj, faqat kerakli animatsiyalar: idle, sprint, jump, fall, crouch, die, emote-yes.

Manba — **Kenney** (kenney.nl), litsenziya **CC0 1.0** (public domain, atribusiya shart emas, lekin o'yinda ko'rsatilgan):
- Train Kit — https://kenney.nl/assets/train-kit
- City Kit (Commercial) 2.1 — https://kenney.nl/assets/city-kit-commercial
- Mini Characters — https://kenney.nl/assets/mini-characters

O'yin nomi, mexanikasi, interfeysi, tovushlari (Web Audio sintez) va graffiti/teksturalar (canvas protsedura) original —
hech qanday tijoriy o'yin (Subway Surfers va b.) fayllari, logotiplari yoki nomlari ishlatilmagan.

Qayta yig'ish: zip'larni bitta papkaga oching (`kenney_train-kit/`, `kenney_city-kit-commercial_2.1/`, `kenney_mini-characters/`), keyin
```
node build.mjs <papka> ../../games/metro_dash
```
`build.mjs` global `gltf-transform` CLI ichidagi modullardan foydalanadi (`/opt/node22/lib/node_modules/@gltf-transform/cli`):
dedup/prune/weld/join, WebP teksturalar, quantize + meshopt.
