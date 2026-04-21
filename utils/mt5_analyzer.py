import base64
import json
import aiohttp
from config import ANTHROPIC_API_KEY
from utils.logger import logger


async def analyze_mt5_screenshot(image_bytes: bytes) -> list | None:
    """
    MT5 skrinshot rasmini Claude API ga yuborib barcha savdo ma'lumotlarini oladi.
    Qaytaradi: list of dicts yoki None
    Har bir dict: {symbol, direction, entry_price, exit_price, quantity, pnl, open_time, close_time}
    """
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY topilmadi!")
        return None

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    prompt = """Bu MT5 (MetaTrader 5) trading platformasining yopilgan savdolar ekrani.
Rasmda bir yoki bir nechta savdo bo'lishi mumkin.

Har bir savdo uchun quyidagi ma'lumotlarni o'qib, faqat JSON array formatida qaytaring:

[
  {
    "symbol": "juft nomi (masalan XAUUSD, EURUSD)",
    "direction": "BUY yoki SELL",
    "entry_price": kirish narxi (raqam),
    "exit_price": chiqish narxi (raqam),
    "quantity": lot miqdori (raqam),
    "pnl": foyda yoki zarar USD da (musbat yoki manfiy raqam),
    "open_time": "ochilish vaqti (masalan 2026.04.16 02:49:47)",
    "close_time": "yopilish vaqti (masalan 2026.04.16 03:12:00)"
  }
]

Muhim qoidalar:
- Faqat JSON array qaytaring, boshqa hech narsa yozmang
- Har bir savdoni alohida object sifatida kiritng
- Agar biron maydon ko'rinmasa null yozing
- PnL manfiy bo'lsa minus bilan: -160.30
- direction faqat BUY yoki SELL
- symbol dagi 'c' harfini olib tashlang (XAUUSDc → XAUUSD)
- Narxlardagi bo'shliqlarni olib tashlang (4 825.546 → 4825.546)"""

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1500,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Anthropic API xato {response.status}: {text}")
                    return None

                data = await response.json()
                content = data.get("content", [])
                if not content:
                    return None

                raw = content[0].get("text", "").strip()
                raw = raw.replace("```json", "").replace("```", "").strip()

                trades_raw = json.loads(raw)
                if not isinstance(trades_raw, list):
                    trades_raw = [trades_raw]

                result = []
                for t in trades_raw:
                    direction = str(t.get("direction", "")).upper()
                    if direction not in ("BUY", "SELL"):
                        direction = None

                    symbol = str(t.get("symbol") or "").upper()
                    symbol = symbol.replace("C", "") if symbol.endswith("C") else symbol

                    trade = {
                        "symbol": symbol or None,
                        "direction": direction,
                        "entry_price": _safe_float(t.get("entry_price")),
                        "exit_price": _safe_float(t.get("exit_price")),
                        "quantity": _safe_float(t.get("quantity")),
                        "pnl": _safe_float(t.get("pnl")),
                        "open_time": str(t.get("open_time") or "") or None,
                        "close_time": str(t.get("close_time") or "") or None,
                    }
                    result.append(trade)

                logger.info(f"MT5 tahlil: {len(result)} ta savdo aniqlandi")
                return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse xatosi: {e}")
        return None
    except Exception as e:
        logger.error(f"MT5 tahlil xatosi: {e}")
        return None


def _safe_float(val) -> float | None:
    try:
        if val is None:
            return None
        s = str(val).replace(" ", "").replace(",", ".")
        return float(s)
    except Exception:
        return None
