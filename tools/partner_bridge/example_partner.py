"""Hamkor bot uchun namuna: 💎 olmos ↔ 🪙 EMP ko'prigi (son_bot bilan). Faqat stdlib.

O'z bazangizga moslang: diamonds_add / diamonds_take / txid_seen / txid_mark funksiyalari.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request

SECRET = os.environ["EXCHANGE_SECRET"].encode()           # son_bot bilan bir xil kalit
SONBOT_URL = os.environ["EXCHANGE_PARTNER_URL"].rstrip("/")  # son_bot manzili, masalan https://sonbot-production.up.railway.app
RATE = 10.0          # 1 olmos = 10 EMP (son_bot ownerlari qo'ygan kurs bilan bir xil bo'lsin)
FEE_PCT = 5.0


def sign(body: bytes) -> str:
    return hmac.new(SECRET, body, hashlib.sha256).hexdigest()


# ── Kiruvchi: son_bot → bizda 💎 ──
def handle_credit_asset(raw: bytes, signature: str):
    """HTTP handler ichidan chaqiring: (status_code, javob_dict)."""
    if not hmac.compare_digest(signature or "", sign(raw)):
        return 401, {"ok": False, "error": "bad_signature"}
    try:
        d = json.loads(raw)
        txid, uid, asset, amount, ts = str(d["txid"]), int(d["user_id"]), d["asset"], int(d["amount"]), int(d["ts"])
    except (ValueError, KeyError, TypeError):
        return 400, {"ok": False, "error": "bad_json"}
    if abs(time.time() - ts) > 300:
        return 401, {"ok": False, "error": "stale"}
    if asset != "diamond" or amount <= 0:
        return 409, {"ok": False, "error": "asset"}
    if txid_seen(txid):
        return 200, {"ok": True, "duplicate": True}
    diamonds_add(uid, amount)      # bitta tranzaksiyada: txid_mark + kredit
    txid_mark(txid)
    return 200, {"ok": True}


# ── Chiquvchi: bizdagi 💎 → son_bot'da 🪙 EMP ──
def send_to_emp(uid: int, diamonds: int):
    emp = int(diamonds * RATE * (1 - FEE_PCT / 100))
    if emp < 1 or not diamonds_take(uid, diamonds):
        return "too_small_or_funds"
    txid = f"dm-{uid}-{secrets.token_hex(8)}"
    body = json.dumps({"txid": txid, "user_id": uid, "asset": "emp", "amount": emp, "ts": int(time.time())}).encode()
    req = urllib.request.Request(SONBOT_URL + "/exchange/credit_asset", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Signature": sign(body)})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200 and json.loads(r.read() or b"{}").get("ok"):
                return "done"
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403, 404, 409):
            diamonds_add(uid, diamonds)        # aniq rad → qaytarish
            return "refunded"
    except Exception:  # noqa: BLE001 — tarmoq/timeout: noaniq
        pass
    # noaniq: txid va summani saqlab, keyin AYNAN SHU body'ni qayta yuboring (ts yangilanadi, imzo qayta hisoblanadi)
    return "pending"


# ── Quyidagilarni o'z bazangizga ulang ──
def diamonds_add(uid, n): raise NotImplementedError
def diamonds_take(uid, n): raise NotImplementedError     # yetarli bo'lsa yechib True
def txid_seen(txid): raise NotImplementedError
def txid_mark(txid): raise NotImplementedError
