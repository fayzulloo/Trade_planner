"""
MT5 yopilgan savdolar skrinshot tahlilchisi.
Gemini API + Round-robin + Fallback (3 urinish).

Modellar tartibi (global round-robin):
  1. gemini-3-flash-preview
  2. gemini-2.5-flash-lite
  3. gemini-flash-latest
  4. gemini-3.1-flash-lite-preview
  5. gemini-2.5-flash

Har bir skrinshot navbatdagi modelga boradi.
Xato bo'lsa o'sha modeldan boshlab 3 ta model sinab ko'riladi.
"""

import base64
import json
import aiohttp
from utils.logger import logger

# ============================================================
# MODELLAR VA GLOBAL HOLAT
# ============================================================

GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3-flash-preview",
]

MAX_RETRIES = 3  # Xato bo'lganda nechta model sinab ko'riladi

# Global model indeksi — barcha foydalanuvchilar uchun bitta
_current_model_idx = 0


def _get_next_model() -> tuple[str, int]:
    """
    Navbatdagi modelni qaytaradi va indeksni oldinga siljitadi.
    Qaytaradi: (model_name, used_idx)
    """
    global _current_model_idx
    idx = _current_model_idx
    _current_model_idx = (_current_model_idx + 1) % len(GEMINI_MODELS)
    return GEMINI_MODELS[idx], idx


def _model_at(idx: int) -> str:
    return GEMINI_MODELS[idx % len(GEMINI_MODELS)]


# ============================================================
# PROMPT
# ============================================================

PROMPT = """Bu MT5 (MetaTrader 5) trading platformasining yopilgan savdolar ekrani.
Rasmda bir yoki bir nechta savdo bo'lishi mumkin.

Har bir savdo uchun quyidagi ma'lumotlarni o'qib, FAQAT JSON array formatida qaytaring:

[
  {
    "symbol": "juft nomi (XAUUSDc bo'lsa XAUUSD deb yoz, oxiridagi c ni olib tashla)",
    "direction": "BUY yoki SELL",
    "entry_price": kirish narxi raqam (bo'shliqsiz: 4825.546),
    "exit_price": chiqish narxi raqam (bo'shliqsiz: 4827.149),
    "quantity": lot miqdori raqam,
    "pnl_abs": PnL ning mutlaq qiymati (faqat musbat raqam: 160.30),
    "open_time": "ochilish vaqti: 2026.04.16 02:49:47",
    "close_time": "yopilish vaqti: 2026.04.16 03:12:00",
    "order_id": "savdo raqami # belgisiz: 1031470841",
    "swap": svop qiymati raqam (masalan: -2.07 yoki 0.00),
    "commission": komissiya qiymati raqam (masalan: 0.00)
  }
]

Muhim qoidalar:
- Faqat JSON array qaytaring, hech qanday izoh yoki markdown yozmang
- Narxlardagi bo'shliqlarni olib tashlang: 4 825.546 → 4825.546
- pnl_abs FAQAT musbat raqam: 160.30 (belgisiz)
- direction faqat BUY yoki SELL
- order_id dan # belgisini olib tashla
- swap va commission manfiy bo'lishi mumkin
- Biron maydon ko'rinmasa null yozing"""


# ============================================================
# PNL BELGISI HISOBLASH
# ============================================================

def _calc_pnl_sign(direction: str, entry: float, exit_p: float) -> int:
    """
    PnL belgisini narxlardan hisoblaydi.
    SELL: exit < entry → +1 (foyda)
    SELL: exit > entry → -1 (zarar)
    BUY:  exit > entry → +1 (foyda)
    BUY:  exit < entry → -1 (zarar)
    """
    if direction == "SELL":
        return 1 if exit_p < entry else -1
    else:  # BUY
        return 1 if exit_p > entry else -1


# ============================================================
# RESPONSE PARSING
# ============================================================

def _safe_float(val) -> float | None:
    try:
        if val is None:
            return None
        return float(str(val).replace(" ", "").replace(",", "."))
    except Exception:
        return None


def _parse_response(raw: str) -> list | None:
    """Gemini javobidan savdolar ro'yxatini ajratib oladi."""
    raw = raw.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not data:
            return None

        result = []
        for t in data:
            symbol = str(t.get("symbol") or "").upper().strip()
            if symbol.endswith("C") and len(symbol) > 4:
                symbol = symbol[:-1]

            direction = str(t.get("direction") or "").upper().strip()
            if direction not in ("BUY", "SELL"):
                logger.warning(f"Noto'g'ri direction: {direction}")
                continue

            entry = _safe_float(t.get("entry_price"))
            exit_p = _safe_float(t.get("exit_price"))

            if not symbol or not entry or not exit_p:
                logger.warning(f"Majburiy maydonlar yo'q: {t}")
                continue

            # PnL belgisini narxlardan hisoblaymiz
            pnl_sign = _calc_pnl_sign(direction, entry, exit_p)
            pnl_abs = _safe_float(t.get("pnl_abs"))
            pnl = round(abs(pnl_abs) * pnl_sign, 2) if pnl_abs is not None else None

            # order_id dan # belgisini tozalash
            order_id_raw = str(t.get("order_id") or "").strip()
            order_id = order_id_raw.lstrip("#").strip() or None

            result.append({
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry,
                "exit_price": exit_p,
                "quantity": _safe_float(t.get("quantity")),
                "pnl": pnl,
                "pnl_sign": pnl_sign,
                "open_time": str(t.get("open_time") or "").strip() or None,
                "close_time": str(t.get("close_time") or "").strip() or None,
                "order_id": order_id,
                "swap": _safe_float(t.get("swap")) or 0.0,
                "commission": _safe_float(t.get("commission")) or 0.0,
            })

        return result if result else None

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse xatosi: {e} | Raw: {raw[:200]}")
        return None


# ============================================================
# GEMINI API CALL
# ============================================================

async def _call_gemini(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    image_b64: str,
    mime_type: str
) -> tuple[list | None, str]:
    """
    Bitta modelga so'rov yuboradi.
    Qaytaradi: (trades | None, status)
    status: "ok" | "limit" | "not_found" | "forbidden" | "error"
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                {"text": PROMPT}
            ]
        }],
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0
        }
    }

    try:
        async with session.post(
            url, json=payload,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:

            if resp.status == 200:
                data = await resp.json()
                try:
                    raw = data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    logger.error(f"[{model}] Javob strukturasi noto'g'ri: {e}")
                    return None, "error"

                trades = _parse_response(raw)
                if trades:
                    logger.info(f"[{model}] ✅ {len(trades)} ta savdo aniqlandi")
                    return trades, "ok"
                else:
                    logger.warning(f"[{model}] Savdo topilmadi")
                    return None, "parse_error"

            elif resp.status == 429:
                logger.warning(f"[{model}] ⚠️ Limit tugadi")
                return None, "limit"

            elif resp.status == 404:
                logger.warning(f"[{model}] ❌ Model topilmadi")
                return None, "not_found"

            elif resp.status == 403:
                logger.warning(f"[{model}] 🚫 Ruxsat yo'q")
                return None, "forbidden"

            else:
                body = await resp.text()
                logger.error(f"[{model}] HTTP {resp.status}: {body[:150]}")
                return None, "error"

    except aiohttp.ClientConnectorError:
        logger.error(f"[{model}] Ulanish xatosi")
        return None, "error"
    except aiohttp.ServerTimeoutError:
        logger.error(f"[{model}] Timeout")
        return None, "error"
    except Exception as e:
        logger.error(f"[{model}] Kutilmagan xato: {e}")
        return None, "error"


# ============================================================
# ASOSIY FUNKSIYA
# ============================================================

async def analyze_mt5_screenshot(image_bytes: bytes) -> tuple[list | None, bool]:
    """
    MT5 skrinshot tahlili.
    Round-robin + fallback (max 3 urinish xato bo'lganda).

    Qaytaradi: (trades | None, need_wait)
      - trades: savdolar ro'yxati yoki None
      - need_wait: True bo'lsa foydalanuvchiga "kuting" xabari chiqadi
    """
    from config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY topilmadi!")
        return None, False

    # Rasm formatini aniqlash
    if image_bytes[:4] == b'\x89PNG':
        mime_type = "image/png"
    else:
        mime_type = "image/jpeg"

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    # Navbatdagi modelni olish (round-robin)
    start_model, start_idx = _get_next_model()
    logger.info(f"Boshlang'ich model: [{start_idx}] {start_model}")

    async with aiohttp.ClientSession() as session:
        # 1-urinish: navbatdagi model
        trades, status = await _call_gemini(
            session, GEMINI_API_KEY, start_model, image_b64, mime_type
        )

        if status == "ok":
            return trades, False

        # Xato bo'ldi — qolgan 2 ta model sinab ko'ramiz
        logger.warning(f"[{start_model}] xato ({status}), fallback boshlanmoqda...")

        for attempt in range(1, MAX_RETRIES):
            fallback_idx = (start_idx + attempt) % len(GEMINI_MODELS)
            fallback_model = GEMINI_MODELS[fallback_idx]

            logger.info(f"Fallback {attempt}/{MAX_RETRIES - 1}: [{fallback_idx}] {fallback_model}")

            trades, status = await _call_gemini(
                session, GEMINI_API_KEY, fallback_model, image_b64, mime_type
            )

            if status == "ok":
                return trades, False

            logger.warning(f"[{fallback_model}] xato ({status})")

    # Barcha 3 ta model muvaffaqiyatsiz
    logger.error("3 ta model ham muvaffaqiyatsiz tugadi")
    return None, True  # need_wait=True
