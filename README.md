# Trade Planner Bot

Forex trading jurnali va strategiya kuzatuvchi Telegram bot.
PostgreSQL ma'lumotlar bazasi bilan.

## Ishga tushirish (Railway)

1. GitHub ga push qiling
2. Railway da yangi loyiha yarating
3. PostgreSQL plugin qo'shing
4. Variables ga qo'shing:
   - `BOT_TOKEN` = telegram bot tokeningiz
   - `DATABASE_URL` = Railway avtomatik beradi

## Local ishga tushirish

```bash
pip install -r requirements.txt
cp .env.example .env
# .env ga BOT_TOKEN va DATABASE_URL kiriting
python main.py
```

## Loyiha strukturasi

```
trade_planner/
├── main.py                 # Asosiy fayl
├── config.py               # Config va validation
├── Procfile                # Railway uchun
├── runtime.txt             # Python versiyasi
├── requirements.txt
├── handlers/
│   ├── keyboards.py        # Barcha tugmalar
│   ├── start.py            # /start
│   ├── plan.py             # Bugungi reja
│   ├── trade.py            # Savdo kiritish
│   ├── settings.py         # Sozlamalar
│   └── stats.py            # Statistika
├── database/
│   ├── connection.py       # PostgreSQL pool
│   ├── models.py           # Jadvallar
│   └── queries.py          # Barcha SQL
├── scheduler/
│   ├── scheduler.py        # APScheduler
│   └── jobs.py             # Eslatma funksiyalari
├── middlewares/
│   ├── auth.py             # Foydalanuvchi tekshiruvi
│   └── throttle.py         # Spam himoya
└── utils/
    ├── logger.py           # Logging
    ├── calculator.py       # Strategiya hisoblash
    └── chart.py            # Grafik yaratish
```
