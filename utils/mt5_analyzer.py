"""
MT5 screenshot tahlili — Google Gemini API orqali.
Rasm yuborilganda savdolarni avtomatik aniqlaydi.
"""

import json
import logging
import base64
from typing import Optional
import aiohttp

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-lite:generateContent"
)

# Gemini ga yuboriladigan prompt
MT5_PROMPT = """
Bu MetaTrader 5 (MT5) savdo tarixining screenshoti.
Rasmdan BARCHA yopiq savdolarni topib, FAQAT JSON formatda qaytar.
Boshqa hech narsa yozma, faqat JSON.

Format:
{
  "trades": [
    {
      "symbol": "XAUUSD",
      "direction": "BUY",
      "entry_price": 2345.67,
      "exit_price": 2356.78,
      "quantity": 0.1,
      "pnl": 111.10,
      "swap": -1.20,
      "commission": -0.50,
      "open_time": "2024.01.15 10:30",
      "close_time": "2024.01.15 14:45",
      "order_id": "12345678",
      "sl_price": 2330.00,
      "tp_price": 2360.00,
      "result": "tp"
    }
  ]
}

Qoidalar:
- direction faqat "BUY" yoki "SELL"
- pnl, swap, commission raqam (manfiy bo'lishi mumkin)
- sl_price: skrinshotda S/L narxi ko'rsatilgan bo'lsa yoz, yo'q bo'lsa null
- tp_price: skrinshotda T/P narxi ko'rsatilgan bo'lsa yoz, yo'q bo'lsa null
- result: savdo qanday yopilgani — "tp" (take profit ishladi), "sl" (stop loss ishladi), "manual" (qo'lda yopildi)
  * Rasmda aniq ko'rinmasa — pnl musbat bo'lsa "tp", manfiy bo'lsa "sl", noaniq bo'lsa "manual" deb bel
- Topilmagan maydonlar uchun null yoz
- Faqat YOPIQ savdolar (open pozitsiyalar emas)
- Agar savdo topilmasa: {"trades": []}
"""


async def analyze_mt5_screenshot(image_bytes: bytes) -> Optional[list[dict]]:
    """
    MT5 screenshot rasmini Gemini API orqali tahlil qiladi.

    Parametrlar:
        image_bytes — rasm baytlari (JPEG yoki PNG)

    Qaytaradi:
        Savdolar ro'yxati [{"symbol": ..., "pnl": ..., ...}]
        None — xato yoki GEMINI_API_KEY yo'q bo'lsa
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY topilmadi, MT5 tahlil o'chirilgan.")
        return None

    try:
        # Rasmni base64 ga o'girish
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": MT5_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Gemini API xato [{resp.status}]: {error_text[:200]}")
                    return None

                data = await resp.json()

        # Javobni olish
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not text:
            logger.error("Gemini bo'sh javob qaytardi.")
            return None

        # JSON tozalash (ba'zan ```json ... ``` ichida keladi)
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        result = json.loads(text)
        trades = result.get("trades", [])

        # Validatsiya
        validated = []
        for t in trades:
            if not t.get("symbol") or not t.get("direction"):
                continue
            if t.get("direction") not in ("BUY", "SELL"):
                continue
            validated.append({
                "symbol":      str(t.get("symbol", "")).upper(),
                "direction":   t.get("direction"),
                "entry_price": float(t.get("entry_price") or 0),
                "exit_price":  float(t.get("exit_price") or 0),
                "quantity":    float(t.get("quantity") or 0),
                "pnl":         float(t.get("pnl") or 0),
                "swap":        float(t.get("swap") or 0),
                "commission":  float(t.get("commission") or 0),
                "open_time":   t.get("open_time"),
                "close_time":  t.get("close_time"),
                "order_id":    str(t.get("order_id")) if t.get("order_id") else None,
                "sl_price":    float(t["sl_price"]) if t.get("sl_price") else None,
                "tp_price":    float(t["tp_price"]) if t.get("tp_price") else None,
                "result":      t.get("result") if t.get("result") in ("tp", "sl", "manual") else None,
            })

        logger.info(f"Gemini {len(validated)} ta savdo aniqladi.")
        return validated

    except json.JSONDecodeError as e:
        logger.error(f"Gemini JSON parse xato: {e}")
        return None
    except Exception as e:
        logger.error(f"analyze_mt5_screenshot xato: {e}")
        return None
