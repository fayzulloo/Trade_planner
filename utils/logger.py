"""
Logging konfiguratsiyasi.
Barcha modullarda shu logger ishlatiladi.
"""

import logging
import sys
from config import LOG_LEVEL


def setup_logger() -> None:
    """
    Asosiy logger ni sozlaydi.
    main.py da bir marta chaqiriladi.
    """
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Shovqinli kutubxonalarni sokinlashtirish
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
