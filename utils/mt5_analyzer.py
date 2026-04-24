"""
MT5 yopilgan savdolar skrinshot tahlilchisi.
Faqat pytesseract va PIL ishlatiladi — tashqi API kerak emas.

MT5 format (oq fon, qora/qizil/ko'k matn):
  Qator 1: XAUUSDc, sell 1.00          2026.04.16 03:12:00
  Qator 2: 4 825.546 → 4 827.149                  -160.30
  Qator 3: #1031470841    Открытие2026.04.16 03:09:27
  Qator 4: S/L: —         Своп:                     0.00
  Qator 5: T/P: —         Комиссия:                 0.00
"""

import re
import io
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
from utils.logger import logger


# ============================================================
# REGEX PATTERNS
# ============================================================

# Savdo header: "XAUUSDc, sell 1.00" yoki "XAUUSD, buy 0.15"
# Oxiridagi vaqt ham shu qatorda bo'lishi mumkin
RE_HEADER = re.compile(
    r'\b([A-Z]{3,8}c?)\s*[,.]?\s*(buy|sell)\s+([\d.]+)',
    re.IGNORECASE
)

# Narxlar: "4 825.546 → 4 827.149"
# Arrow turli ko'rinishda kelishi mumkin: →, ->, —, -, >
RE_PRICES = re.compile(
    r'([\d][\d ]{0,6}\.[\d]{2,5})\s*(?:→|->|—|–|-+|>)\s*([\d][\d ]{0,6}\.[\d]{2,5})'
)

# Sana-vaqt: "2026.04.16 03:12:00" yoki "2026/04/16 03:12:00"
RE_DATETIME = re.compile(
    r'(\d{4}[./]\d{2}[./]\d{2}\s+\d{2}:\d{2}:\d{2})'
)

# Ticket raqami: "#1031470841"
RE_TICKET = re.compile(r'#\d{6,12}')

# S/L yoki T/P qatori — bu qatorlarni o'tkazib yuboramiz
RE_SKIP = re.compile(r'^\s*[ST][/\\][LP]', re.IGNORECASE)

# Своп, Комиссия qatorlari
RE_SKIP2 = re.compile(r'(своп|комисс|commission|swap)', re.IGNORECASE)


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def _to_float(s: str) -> float | None:
    """Bo'shliqli va vergülli raqamni float ga o'tkazish."""
    try:
        cleaned = re.sub(r'\s+', '', str(s)).replace(',', '.')
        return float(cleaned)
    except Exception:
        return None


def _calc_pnl_sign(direction: str, entry: float, exit_p: float) -> int:
    """
    PnL belgi hisoblash.
    SELL: exit < entry → +1 (foyda), exit > entry → -1 (zarar)
    BUY:  exit > entry → +1 (foyda), exit < entry → -1 (zarar)
    """
    if direction == "SELL":
        return 1 if exit_p < entry else -1
    else:  # BUY
        return 1 if exit_p > entry else -1


def _strip_symbol(raw: str) -> str:
    """XAUUSDc → XAUUSD, EURUSD → EURUSD."""
    s = raw.upper().strip()
    if s.endswith('C') and len(s) > 4:
        s = s[:-1]
    return s


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def _preprocess(image: Image.Image) -> list:
    """
    Turli preprocessing variantlari qaytaradi.
    MT5 oq fon, qora matn — inversiya kerak emas.
    """
    results = []
    w, h = image.size

    # Variant 1: 3x zoom, kontrast oshirish
    img = image.resize((w * 3, h * 3), Image.LANCZOS).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.filter(ImageFilter.SHARPEN)
    results.append(img)

    # Variant 2: 2x zoom, yumshoqroq
    img2 = image.resize((w * 2, h * 2), Image.LANCZOS).convert("L")
    img2 = ImageEnhance.Contrast(img2).enhance(2.0)
    results.append(img2)

    # Variant 3: 3x zoom, threshold
    img3 = image.resize((w * 3, h * 3), Image.LANCZOS).convert("L")
    import numpy as np
    arr = np.array(img3)
    arr = np.where(arr > 160, 255, 0).astype(np.uint8)
    results.append(Image.fromarray(arr))

    return results


# ============================================================
# OCR
# ============================================================

def _run_ocr(image: Image.Image) -> str:
    """
    Bir rasm uchun eng yaxshi OCR natijasini qaytaradi.
    Bir nechta PSM rejimini sinab, eng uzun natijani tanlaydi.
    """
    variants = _preprocess(image)
    psm_modes = ["--psm 6 --oem 3", "--psm 4 --oem 3", "--psm 12 --oem 3"]

    best = ""
    for img_v in variants:
        for psm in psm_modes:
            try:
                text = pytesseract.image_to_string(img_v, config=psm, lang="eng+rus")
                if len(text) > len(best):
                    best = text
            except Exception as e:
                logger.warning(f"OCR xatosi ({psm}): {e}")
    return best


# ============================================================
# PARSING
# ============================================================

def _clean_lines(raw_text: str) -> list[str]:
    """Matnni qatorlarga ajratadi, bo'sh va keraksizlarini o'chiradi."""
    lines = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if RE_SKIP.match(line):
            continue
        if RE_SKIP2.search(line):
            continue
        lines.append(line)
    return lines


def _split_blocks(lines: list[str]) -> list[list[str]]:
    """
    Qatorlarni savdo bloklariga ajratadi.
    Har bir blok header (symbol+direction) bilan boshlanadi.
    """
    blocks = []
    current = []

    for line in lines:
        if RE_HEADER.search(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


def _parse_block(lines: list[str]) -> dict | None:
    """
    Bitta savdo blokini tahlil qiladi.
    Qaytaradi: dict yoki None (agar muhim maydonlar topilmasa).
    """
    full_text = "\n".join(lines)

    # 1. Header: symbol, direction, quantity
    hm = RE_HEADER.search(full_text)
    if not hm:
        return None

    symbol = _strip_symbol(hm.group(1))
    direction = hm.group(2).upper()
    quantity = _to_float(hm.group(3))

    # 2. Narxlar: entry → exit
    pm = RE_PRICES.search(full_text)
    if not pm:
        logger.debug(f"Narxlar topilmadi: {full_text[:80]}")
        return None

    entry_price = _to_float(pm.group(1))
    exit_price = _to_float(pm.group(2))

    if not entry_price or not exit_price:
        return None

    # Narxlar bir xil bo'lsa yoki juda kichik bo'lsa — xato
    if abs(entry_price - exit_price) < 0.001:
        return None

    # 3. Vaqtlar
    # Header qatoridagi vaqt — yopilish vaqti (close_time)
    header_line = lines[0] if lines else ""
    header_times = RE_DATETIME.findall(header_line)
    close_time = header_times[0].strip() if header_times else None

    # "Открытие" bilan birikib kelgan ochilish vaqti
    open_time = None
    for line in lines:
        # "Открытие2026.04.16 03:09:27" → "2026.04.16 03:09:27"
        # OCR "Открытие" ni turli yo'l bilan o'qishi mumkin
        # Shuning uchun barcha datetime ni qidirib, close_time dan farqlisini olamiz
        dts = RE_DATETIME.findall(line)
        for dt in dts:
            dt = dt.strip()
            if dt != close_time:
                open_time = dt
                break
        if open_time:
            break

    # Agar open_time topilmasa — barcha vaqtlardan ikkinchisini olishga urinamiz
    if not open_time:
        all_times = RE_DATETIME.findall(full_text)
        all_times = [t.strip() for t in all_times]
        # Birinchisi close_time, ikkinchisi open_time
        for t in all_times:
            if t != close_time:
                open_time = t
                break

    # 4. PnL belgisini hisoblash (rangsiz, faqat narxlardan)
    sign = _calc_pnl_sign(direction, entry_price, exit_price)

    # 5. PnL qiymatini ham o'qishga urinamiz (ixtiyoriy)
    # Agar topilsa — sign bilan tasdiqlash
    pnl = None
    for line in reversed(lines):
        # Faqat raqamdan iborat qator: "160.30" yoki "757.20" yoki "-160.30"
        m = re.match(r'^-?\s*[\d][\d\s]*\.[\d]{2}\s*$', line)
        if m:
            val = _to_float(line)
            if val and abs(val) > 0.01:
                # Narxlardan farqlash
                if abs(val) not in (abs(entry_price), abs(exit_price)):
                    # Sign ni narxlardan hisoblab tasdiqlash
                    pnl = abs(val) * sign
                    break

    # PnL topilmasa None qoladi — foydalanuvchi o'zi kiritadi
    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
        "pnl": round(pnl, 2) if pnl is not None else None,
        "pnl_sign": sign,  # +1 yoki -1 — UI uchun
        "open_time": open_time,
        "close_time": close_time,
    }


# ============================================================
# ASOSIY FUNKSIYA
# ============================================================

async def analyze_mt5_screenshot(image_bytes: bytes) -> list | None:
    """
    MT5 yopilgan savdolar skrinshtini tahlil qiladi.
    Qaytaradi: list of trade dicts yoki None.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        raw_text = _run_ocr(image)

        if not raw_text.strip():
            logger.warning("OCR hech narsa o'qimadi")
            return None

        # Debug uchun dastlabki 400 belgini log qilamiz
        logger.warning(f"OCR raw (400 belgi):\n{raw_text[:400]}")

        lines = _clean_lines(raw_text)
        blocks = _split_blocks(lines)

        # Blok topilmasa — barcha qatorlarni bitta blok sifatida sinab ko'ramiz
        if not blocks and lines:
            blocks = [lines]

        trades = []
        for block in blocks:
            trade = _parse_block(block)
            if trade:
                trades.append(trade)

        if not trades:
            logger.warning("Savdo bloklari topilmadi")
            return None

        logger.info(f"Tahlil yakunlandi: {len(trades)} ta savdo")
        return trades

    except Exception as e:
        logger.error(f"MT5 analyzer xatosi: {e}", exc_info=True)
        return None
