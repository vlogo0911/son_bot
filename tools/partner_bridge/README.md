# 💎 Hamkor bot olmosi ↔ 🪙 EMP — ko'prik protokoli

Mavjud $ ko'prigi (`POST /exchange/credit`) bilan bir xil kalit (`EXCHANGE_SECRET`) va imzo, lekin **alohida yo'l**:
`POST /exchange/credit_asset`. Eski kod yangi maydonni e'tiborsiz qoldirib, olmos o'rniga $ qo'shib yubormasligi uchun
yo'l alohida.

## So'rov

```
POST <qabul qiluvchi bot>/exchange/credit_asset
Content-Type: application/json
X-Signature: hex(HMAC-SHA256(EXCHANGE_SECRET, <aynan yuborilgan body baytlari>))

{"txid": "sw-123-ab12cd34", "user_id": 123456789, "asset": "diamond", "amount": 9, "ts": 1760000000}
```

- `amount` — **qabul qiluvchi valyutasida**, butun son. son_bot hamkorga `asset: "diamond"` yuboradi; hamkor son_bot'ga
  `asset: "emp"` yuboradi.
- `ts` — Unix vaqti. ±300 soniyadan eski bo'lsa so'rov rad etiladi.
- `txid` — o'tkazmaning noyob ID'si. Bir xil `txid` qayta kelsa, qayta kreditlamang: `200 {"ok": true, "duplicate": true}` qaytaring.

## Javob

| Holat | Kod | Body | Yuboruvchi nima qiladi |
|---|---|---|---|
| Kreditlandi | 200 | `{"ok": true}` | yakunlaydi |
| Rad (limit, valyuta yopiq, user yo'q, asset noto'g'ri) | 409 | `{"ok": false, "error": "..."}` | **to'liq qaytaradi** |
| Imzo xato / eskirgan | 401 | `{"ok": false, "error": "bad_signature" \| "stale"}` | qaytaradi |
| Vaqtincha xato / timeout | 5xx | — | pul ushlab turiladi, keyin qayta urinadi (txid o'sha) |

son_bot qaytaradigan xato kodlari: `disabled`, `asset`, `bad_amount`, `user`, `emp_closed`, `limit`, `db`.

## Kurs

son_bot ownerlari web app → Owner → "💎 Hamkor olmosi ↔ 🪙 EMP" bo'limida quyidagilarni belgilaydi:
- kurs: 1 💎 = N EMP;
- komissiya, %;
- kunlik chiqish va kirish limitlari (EMP hisobida).

**EMP → 💎** (son_bot hisoblaydi): `olmos = floor((EMP − ceil(EMP·komissiya/100)) / kurs)`.

**💎 → EMP** (hamkor hisoblaydi): `EMP = floor(olmos · kurs · (1 − komissiya/100))`. Kurs va komissiyani ikkala tomon bir xil
qo'yishi kerak. son_bot kirishni kunlik limit bilan cheklaydi.

## Hamkor tomonda kerak bo'ladiganlar

1. `POST /exchange/credit_asset` — `asset == "diamond"` bo'lsa, foydalanuvchiga olmos qo'shish (txid bo'yicha idempotent).
2. "EMP ga almashtirish" tugmasi:
   - olmosni yechish;
   - son_bot'ga `asset: "emp"` bilan so'rov yuborish;
   - 409 yoki 401 kelsa olmosni qaytarish, 5xx yoki timeout bo'lsa keyin shu txid bilan qayta urinish.

Namuna (Python, stdlib) — `example_partner.py`.
