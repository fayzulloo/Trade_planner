import re
import io
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
from utils.logger import logger
import numpy as np


# ===== REGEX PATTERNS =====

# "XAUUSDc, sell 1.00" — symbol vergul/boʻshliq bilan ajratilgan
RE_HEADER = re.compile(
    r'([A-Z]{3,10}[cC]?)\s*[,.]?\s*(buy|sell)\s+([\d.]+)',
    re.IGNORECASE
)

# Narxlar: "4 825.546 → 4 827.149" yoki "4825.546 -> 4827.149"
# Bo'shliqli raqamlar ham: "4 825.546"
RE_PRICES = re.compile(
    r'([\d][\d\s]{0,8}\.[\d]{2,5})\s*(?:→|->|»|>|—>)\s*([\d][\d\s]{0,8}\.[\d]{2,5})'
)

# Vaqt: "2026.04.16 03:12:00"
RE_TIME = re.compile(
    r'(\d{4}[./]\d{2}[./]\d{2}\s+\d{2}:\d{2}:\d{2})'
)

# Savdo raqami: "#1031470841"
RE_TICKET = re.compile(r'#(\d{7,12})')

# PnL — manfiy yoki musbat raqam, 2 kasr
# "-160.30" yoki "-1 022.10" yoki "160.30"
RE_PNL_LINE = re.compile(
    r'^-?\s*[\d][\d\s]*\.[\d]{2}\s*$'
)


def _clean_number(s: str) -> float | None:
    try:
        cleaned = re.sub(r'\s+', '', str(s)).replace(',', '.')
        return float(cleaned)
    except Exception:
        return None


def _preprocess_variants(image: Image.Image) -> list:
    """
    Turli preprocessing variantlari — hammasi sinab ko'riladi.
    OCR uchun eng ko'p ma'lumot beradigan variant tanlanadi.
    """
    variants = []
    w, h = image.size

    # 1. Kattalashtirish + inversiya (qoʻyuq fon uchun)
    img1 = image.resize((w * 3, h * 3), Image.LANCZOS).convert("L")
    arr = np.array(img1)
    if arr.mean() < 128:
        img1 = ImageOps.invert(img1)
    enhancer = ImageEnhance.Contrast(img1)
    img1 = enhancer.enhance(3.0)
    img1 = img1.filter(ImageFilter.SHARPEN)
    img1 = img1.filter(ImageFilter.SHARPEN)
    variants.append(img1)

    # 2. Oddiy grayscale, kattalashtirish
    img2 = image.resize((w * 2, h * 2), Image.LANCZOS).convert("L")
    enhancer2 = ImageEnhance.Contrast(img2)
    img2 = enhancer2.enhance(2.0)
    variants.append(img2)

    # 3. Threshold — ikki qiymatli rasm
    img3 = image.resize((w * 3, h * 3), Image.LANCZOS).convert("L")
    arr3 = np.array(img3)
    if arr3.mean() < 128:
        img3 = ImageOps.invert(img3)
    # Manual threshold
    threshold = 140
    arr3 = np.array(img3)
    arr3 = np.where(arr3 > threshold, 255, 0).astype(np.uint8)
    img3 = Image.fromarray(arr3)
    variants.append(img3)

    return variants


def _split_into_trade_blocks(lines: list) -> list:
    blocks = []
    current = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
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
    text = "\n".join(lines)

    # 1. Header
    header_match = RE_HEADER.search(text)
    if not header_match:
        return None

    symbol_raw = header_match.group(1).upper()
    symbol = re.sub(r'C$', '', symbol_raw)
    direction = header_match.group(2).upper()
    quantity = _clean_number(header_match.group(3))

    # 2. Narxlar
    prices_match = RE_PRICES.search(text)
    entry_price = None
    exit_price = None
    if prices_match:
        entry_price = _clean_number(prices_match.group(1))
        exit_price = _clean_number(prices_match.group(2))

    # Agar narxlar topilmasa — raqamli qatorlardan topishga urinamiz
    if not entry_price or not exit_price:
        # 4 xonali raqamlar (oltin narxi 4000+ bo'ladi)
        big_numbers = re.findall(r'(\d[\d\s]{2,8}\.\d{2,5})', text)
        big_nums = [_clean_number(n) for n in big_numbers if _clean_number(n) and _clean_number(n) > 100]
        if len(big_nums) >= 2:
            entry_price = big_nums[0]
            exit_price = big_nums[1]

    # 3. Vaqtlar
    times = RE_TIME.findall(text)
    open_time = None
    close_time = None
    if len(times) >= 2:
        close_time = times[0].strip()
        open_time = times[1].strip()
    elif len(times) == 1:
        close_time = times[0].strip()

    # 4. PnL
    pnl = None
    # Avval ticket raqamidan keyingi qatorlarga qara
    ticket_match = RE_TICKET.search(text)
    after_ticket = text
    if ticket_match:
        after_ticket = text[ticket_match.end():]

    # Oxirgi qatorlarda PnL qidirish
    all_lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in reversed(all_lines):
        # PnL: "-160.30" yoki "-1 022.10"
        m = re.match(r'^-?\s*\d[\d\s]*\.\d{2}\s*$', line)
        if m:
            val = _clean_number(line)
            if val is not None and abs(val) > 0.01:
                # Narxlardan farqlash — narxlar entry/exit bilan bir xil bo'lmasin
                if entry_price and abs(val) == entry_price:
                    continue
                if exit_price and abs(val) == exit_price:
                    continue
                # S/L yoki T/P emas
                pnl = -abs(val) if direction == "SELL" and val > 0 else val
                # Aslida foyda/zarar belgisi rasmda rangi bilan ko'rsatiladi
                # OCR belgini tushirmaydi — keyinroq foydalanuvchi tuzatadi
                pnl = val
                break

    # Agar pnl topilmasa
    if pnl is None:
        signed = re.findall(r'([+-]\s*\d[\d\s]*\.\d{2})', text)
        for s in reversed(signed):
            val = _clean_number(s)
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
    try:
        image = Image.open(io.BytesIO(image_bytes))
        variants = _preprocess_variants(image)

        psm_configs = [
            "--psm 6 --oem 3",
            "--psm 4 --oem 3",
            "--psm 12 --oem 3",
        ]

        best_trades = []
        best_text = ""

        for img_variant in variants:
            for cfg in psm_configs:
                try:
                    text = pytesseract.image_to_string(
                        img_variant, config=cfg, lang="eng"
                    )
                    if not text.strip():
                        continue

                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    blocks = _split_into_trade_blocks(lines)

                    # Blok topilmasa — butun matn bitta blok
                    if not blocks and lines:
                        blocks = [lines]

                    trades = []
                    for block in blocks:
                        trade = _parse_trade_block(block)
                        if trade:
                            trades.append(trade)

                    if len(trades) > len(best_trades):
                        best_trades = trades
                        best_text = text

                except Exception as e:
                    logger.warning(f"OCR variant xatosi ({cfg}): {e}")
                    continue

        # OCR natijasini log ga yozamiz — debug uchun
        if best_text:
            # Faqat birinchi 500 belgini logga yozamiz
            logger.warning(f"OCR raw text (500 belgi):\n{best_text[:500]}")
        else:
            logger.warning("OCR hech narsa o'qimadi — rasm sifatini tekshiring")
            return None

        if not best_trades:
            logger.warning(f"Savdo ma'lumotlari topilmadi. OCR matni:\n{best_text[:300]}")
            return None

        logger.info(f"OCR muvaffaqiyat: {len(best_trades)} ta savdo")
        return best_trades

    except Exception as e:
        logger.error(f"MT5 OCR xatosi: {e}")
        return None
