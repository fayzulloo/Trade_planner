import re
import io
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
from utils.logger import logger

import shutil
print("Tesseract path:", shutil.which("tesseract"))


# MT5 formatiga mos regex patternlar
# Misol: "XAUUSDc, sell 1.00"
RE_HEADER = re.compile(
    r'([A-Z]{3,10}(?:c|\.)?)\s*,?\s*(buy|sell|BUY|SELL)\s+([\d.]+)',
    re.IGNORECASE
)

# Narxlar: "4 825.546 → 4 827.149" yoki "4825.546 -> 4827.149"
RE_PRICES = re.compile(
    r'([\d\s]{1,10}[\d]\.[\d]{2,5})\s*(?:→|->|>)\s*([\d\s]{1,10}[\d]\.[\d]{2,5})'
)

# PnL: "-160.30" yoki "+160.30" yoki "160.30" (qizil/yashil rangda)
RE_PNL = re.compile(
    r'([+-]?\s*[\d\s]+\.[\d]{2})\s*$',
    re.MULTILINE
)

# Vaqt: "2026.04.16 03:12:00" yoki "2026.04.16 03:09:27"
RE_TIME = re.compile(
    r'(\d{4}[./]\d{2}[./]\d{2}\s+\d{2}:\d{2}:\d{2})'
)

# Savdo raqami: "#1031470841"
RE_TICKET = re.compile(r'#(\d{6,12})')


def _clean_number(s: str) -> float | None:
    """Bo'shliqli raqamni float ga o'tkazish: '4 825.546' → 4825.546"""
    try:
        cleaned = re.sub(r'\s+', '', str(s))
        return float(cleaned)
    except Exception:
        return None


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Rasmni OCR uchun tayyorlash"""
    # Kattalashtirish — aniqlik oshadi
    w, h = image.size
    scale = 2
    image = image.resize((w * scale, h * scale), Image.LANCZOS)

    # Grayscale
    image = image.convert("L")

    # Kontrast oshirish
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)

    # O'tkir qilish
    image = image.filter(ImageFilter.SHARPEN)

    return image


def _split_into_trade_blocks(lines: list) -> list:
    """
    Matnni alohida savdo bloklariga ajratish.
    Har bir blok header bilan boshlanadi (symbol, direction, quantity).
    """
    blocks = []
    current = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Yangi savdo boshlanishi — header qatori
        if RE_HEADER.search(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


def _parse_trade_block(lines: list) -> dict | None:
    """Bitta savdo blokini tahlil qilish"""
    text = "\n".join(lines)

    # 1. Header: symbol, direction, quantity
    header_match = RE_HEADER.search(text)
    if not header_match:
        return None

    symbol_raw = header_match.group(1).upper()
    # XAUUSDc → XAUUSD
    symbol = re.sub(r'C$', '', symbol_raw)
    direction = header_match.group(2).upper()
    quantity = _clean_number(header_match.group(3))

    # 2. Narxlar: entry → exit
    prices_match = RE_PRICES.search(text)
    entry_price = None
    exit_price = None
    if prices_match:
        entry_price = _clean_number(prices_match.group(1))
        exit_price = _clean_number(prices_match.group(2))

    # 3. Vaqtlar
    times = RE_TIME.findall(text)
    open_time = None
    close_time = None
    if len(times) >= 2:
        # Birinchi vaqt — ochilish (Открытие), ikkinchi — yopilish
        open_time = times[1].strip()
        close_time = times[0].strip()
    elif len(times) == 1:
        close_time = times[0].strip()

    # 4. PnL — oxirgi qatordagi katta raqam
    pnl = None
    # Har bir qatorni tekshiramiz — PnL odatda alohida qatorda
    for line in reversed(lines):
        line = line.strip()
        # Faqat raqam va belgilar: "-160.30" yoki "1 022.10"
        pnl_match = re.match(r'^([+-]?\s*[\d\s]+\.[\d]{2})\s*$', line)
        if pnl_match:
            val = _clean_number(pnl_match.group(1))
            if val is not None and abs(val) > 0.01:
                pnl = val
                break

    # Agar pnl topilmasa — butun matndan qidirish
    if pnl is None:
        # Qizil rang OCR da odatda minus belgisi bilan keladi
        all_numbers = re.findall(r'([+-][\s\d]+\.[\d]{2})', text)
        for n in reversed(all_numbers):
            val = _clean_number(n)
            if val is not None and abs(val) > 0.01:
                pnl = val
                break

    if symbol and direction and entry_price and exit_price:
        return {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "pnl": pnl,
            "open_time": open_time,
            "close_time": close_time,
        }

    return None


async def analyze_mt5_screenshot(image_bytes: bytes) -> list | None:
    """
    MT5 skrinshot rasmini OCR bilan tahlil qiladi.
    Qaytaradi: list of dicts yoki None
    """
    try:
        # Rasmni ochish
        image = Image.open(io.BytesIO(image_bytes))

        # Preprocessing
        processed = _preprocess_image(image)

        # OCR — MT5 qora fon, oq matn bo'lishi mumkin
        # psm 6: bir xil bloklangan matn
        configs = [
            "--psm 6 --oem 3",
            "--psm 4 --oem 3",
            "--psm 11 --oem 3",
        ]

        best_text = ""
        best_trade_count = 0

        for cfg in configs:
            try:
                text = pytesseract.image_to_string(processed, config=cfg, lang="eng")
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                blocks = _split_into_trade_blocks(lines)
                if len(blocks) > best_trade_count:
                    best_trade_count = len(blocks)
                    best_text = text
            except Exception as e:
                logger.warning(f"OCR config {cfg} xatosi: {e}")
                continue

        if not best_text:
            logger.error("OCR hech narsa o'qimadi")
            return None

        lines = [l.strip() for l in best_text.split("\n") if l.strip()]
        logger.debug(f"OCR natijasi:\n{best_text}")

        # Savdo bloklariga ajratish
        blocks = _split_into_trade_blocks(lines)

        if not blocks:
            # Blok topilmasa — butun matnni bitta blok sifatida
            blocks = [lines]

        trades = []
        for block in blocks:
            trade = _parse_trade_block(block)
            if trade:
                trades.append(trade)

        if not trades:
            logger.warning("Savdo ma'lumotlari topilmadi")
            return None

        logger.info(f"OCR tahlil: {len(trades)} ta savdo aniqlandi")
        return trades

    except Exception as e:
        logger.error(f"MT5 OCR xatosi: {e}")
        return None


def _safe_float(val) -> float | None:
    try:
        if val is None:
            return None
        s = str(val).replace(" ", "").replace(",", ".")
        return float(s)
    except Exception:
        return None
