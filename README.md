# 📊 Trade Planner Bot

> Telegram orqali ishlatiladigan professional trading journal va rejalashtirish boti.
> Kunlik maqsadlarni kuzatish, savdolarni qayd etish va strategiya progressini tahlil qilish uchun mo'ljallangan.

---

## 🚀 Imkoniyatlar

### 📊 Strategiya rejimi
- **Kunlik reja** — rejalangan balans asosida avtomatik maqsad hisoblash
- **Rollover tizimi** — bajarilmagan maqsad keyingi kunga avtomatik o'tkaziladi
- **Strategiya progressi** — N kunlik strategiya davomida balans o'sishini kuzatish
- **Yechish tizimi** — har N kunda yechish, tasdiqlash/rad etish imkoni

### 📝 Jurnal rejimi
- **Maqsadsiz jurnal** — faqat savdolarni qayd etish
- **Kunlik PnL** — har kungi foyda/zarar hisobi
- Strategiya davri va rollover yo'q

### 🔄 Umumiy
- **Savdolarni qayd etish** — PnL, swap, commission, SL/TP, result hisobi
- **MT5 screenshot tahlili** — Google Gemini AI orqali avtomatik tahlil
- **Ikki jurnal** — asosiy (doim saqlanadi) va strategiya (yangi strategiyada tozalanadi)
- **Eslatmalar** — ertalabki va kechki eslatmalar, avtomatik kun yakunlash
- **WebApp dashboard** — balans grafigi, jurnal va statistika (barcha tarix)
- **Ko'p foydalanuvchi** — har bir foydalanuvchi o'z sozlamalari bilan

---

## 🛠 Texnologiyalar

| Texnologiya | Versiya | Maqsad |
|---|---|---|
| Python | 3.11.8 | Asosiy til |
| aiogram | 3.7.0 | Telegram Bot API |
| PostgreSQL | — | Ma'lumotlar bazasi |
| asyncpg | 0.27.0 | Asinxron DB ulanish |
| APScheduler | 3.10.4 | Avtomatik vazifalar |
| FastAPI | 0.111.0 | WebApp backend |
| Uvicorn | 0.29.0 | ASGI server |
| aiohttp | 3.9.5 | HTTP client |
| Google Gemini API | — | MT5 screenshot tahlili |
| Railway | — | Cloud deployment |

---

## 📁 Loyiha strukturasi

```
trade_planner/
├── main.py                    # Bot ishga tushirish nuqtasi (webhook/polling)
├── webapp_server.py           # WebApp FastAPI server
├── config.py                  # Environment variables
├── requirements.txt
├── Procfile                   # Railway process konfiguratsiyasi
├── runtime.txt                # Python versiyasi
│
├── database/
│   ├── __init__.py
│   ├── connection.py          # PostgreSQL connection pool
│   ├── models.py              # CREATE TABLE, migration
│   └── queries.py             # Barcha CRUD operatsiyalar
│
├── handlers/
│   ├── __init__.py
│   ├── keyboards.py           # Inline va reply klaviaturalar
│   ├── start.py               # /start, rejim tanlash
│   ├── plan.py                # Bugungi reja, kun yakunlash
│   ├── trade.py               # Savdo qo'shish, MT5 tahlil
│   ├── settings.py            # Sozlamalar boshqaruvi
│   └── stats.py               # Statistika va grafiklar
│
├── scheduler/
│   ├── __init__.py
│   ├── scheduler.py           # APScheduler sozlamalari
│   └── jobs.py                # Avtomatik vazifalar (jobs)
│
├── middlewares/
│   ├── __init__.py
│   ├── auth.py                # Foydalanuvchi autentifikatsiyasi
│   └── throttle.py            # Spam himoyasi
│
├── utils/
│   ├── __init__.py
│   ├── calculator.py          # Trading hisob-kitoblari
│   ├── chart.py               # Grafik generatsiya (matplotlib)
│   ├── logger.py              # Logging sozlamalari
│   └── mt5_analyzer.py        # Gemini AI tahlil
│
└── webapp/
    ├── __init__.py
    ├── app.py                 # FastAPI routes
    ├── index.html             # Dashboard UI
    └── static/
        ├── css/style.css
        └── js/app.js
```

---

## ⚙️ O'rnatish

### 1. Repository ni clone qilish

```bash
git clone https://github.com/username/trade_planner.git
cd trade_planner
```

### 2. Virtual muhit yaratish

```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
```

### 3. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 4. `.env` fayl yaratish

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://user:password@host:5432/dbname
GEMINI_API_KEY=your_gemini_api_key
WEBAPP_URL=https://your-webapp.up.railway.app
BOT_WEBHOOK_URL=https://your-bot.up.railway.app  # webhook uchun
```

### 5. Ishga tushirish

```bash
# Bot (polling rejimi)
python main.py

# WebApp (alohida terminal)
python webapp_server.py
```

---

## 🗄️ Ma'lumotlar bazasi

### Jadvallar

```
users            — Telegram foydalanuvchilar
settings         — Har bir user sozlamalari (1:1)
trades           — Asosiy jurnal: barcha savdolar (hech qachon o'chirmaydi)
strategy_trades  — Strategiya jurnali: trade_id reference (yangi strategiyada tozalanadi)
daily_journal    — Kunlik jurnal (1:N, UNIQUE user+date)
```

### Ikki jurnal arxitekturasi

```
Savdo kiritilganda:
  → trades        (asosiy, doim saqlanadi)
  → strategy_trades (strategiya, yangi strategiyada tozalanadi)

Bot ichida:
  → strategy_trades dan o'qiydi (joriy strategiya)

WebApp da:
  → trades dan o'qiydi (barcha tarix)

Yangi strategiya boshlananda:
  → strategy_trades tozalanadi
  → trades o'zgarmaydi ✅
```

### Asosiy formulalar

```
net_pnl          = pnl + swap + commission
total_target     = target_profit + extra_target + carry_over_amount
end_balance      = start_balance + net_pnl - withdrawal
is_rolled_over   = net_pnl < total_target

# Rejalangan balans (har kun uchun)
balance = starting_balance
for day in range(1, N+1):
    balance = balance + balance * rate + extra_target
    if day % withdrawal_every == 0:
        balance -= withdrawal_amount
```

### Rejimlar

| Rejim | target_profit | Rollover | Strategiya davri |
|---|---|---|---|
| `strategy` | rejalangan balans * rate | ✅ | ✅ |
| `journal` | 0 | ❌ | ❌ |

---

## 📅 Scheduler vazifalari

| Vazifa | Vaqt | Tavsif |
|---|---|---|
| `job_create_daily_journals` | 00:01 UTC | Barcha userlar uchun yangi kun jurnal yaratish |
| `job_morning_reminder` | Har daqiqa | Ertalabki reja eslatmasi |
| `job_evening_reminder` | Har daqiqa | Kechki progress eslatmasi |
| `job_auto_complete` | Har daqiqa | Avtomatik kun yakunlash |

### Muhim ketma-ketlik

```
23:30 UZT → auto_complete (kun yakunlanadi, is_rolled_over belgilanadi)
00:01 UZT → create_journal (yangi kun yaratiladi, carry_over hisoblanadi)
```

⚠️ `auto_complete_time` sozlamada `23:30` dan oldin bo'lishi kerak.

---

## 🔄 Rollover tizimi

Maqsadga erishilmagan kunlar keyingi kunga avtomatik o'tkaziladi:

```
1-kun: Maqsad 500$, bajarildi 300$ → carry_over = 200$
2-kun: Maqsad 550$ + 200$ = 750$
```

---

## 💸 Yechish tizimi

Yechish kuni `plan_kb` da 2 ta tugma chiqadi:

```
✅ Yechib yakunlash    → withdrawal_confirmed=TRUE → balansdan ayiriladi
❌ Yechimsiz yakunlash → withdrawal_confirmed=FALSE → ayirilmaydi
```

Avtomatik yakunlashda (`job_auto_complete`) yechish **bo'lmaydi** — faqat qo'lda tasdiqlanganda.

---

## 🏁 Strategiya tugash

Strategiya tugaganda:
1. Bot xabar yuboradi (natijalar bilan)
2. `finish_strategy` — `end_date` saqlanadi, `is_active=FALSE`
3. `strategy_trades` tozalanadi
4. User yangi rejim tanlaydi: 📊 Strategiya yoki 📝 Jurnal

---

## 🌐 Railway Deploy

### Servislar

```
Trade_planner     → web: python main.py       (bot + webhook)
webapp-service    → web: python webapp_server.py (dashboard)
Postgres          → ma'lumotlar bazasi
```

### Environment variables (Trade_planner)

```
BOT_TOKEN
DATABASE_URL
GEMINI_API_KEY
WEBAPP_URL
BOT_WEBHOOK_URL    # Railway domain: https://tradeplanner-production.up.railway.app
PORT               # Railway avtomatik beradi
```

### Environment variables (webapp-service)

```
DATABASE_URL
PORT
```

### Webhook vs Polling

```
BOT_WEBHOOK_URL mavjud → Webhook rejimi (RAM tejaydi)
BOT_WEBHOOK_URL bo'sh  → Polling rejimi
```

---

## 📊 WebApp Dashboard

Dashboard **asosiy jurnal** (barcha tarix) dan o'qiydi:

- **Overview** — haqiqiy balans, rejalangan balans, progress, natijalar
- **Jurnal** — kunlik jurnal jadvali, kun ustiga bosib savdolar ko'rish
- **Grafik** — balans o'sishi (rejalangan to'liq chiziq + haqiqiy)

WebApp Telegram WebApp API orqali ishlaydi.

---

## 🤖 Bot buyruqlari

| Buyruq | Tavsif |
|---|---|
| `/start` | Botni ishga tushirish, rejim tanlash |

Asosiy boshqaruv reply klaviatura orqali:

```
📊 Bugungi reja      ⚙️ Sozlamalar
        📈 Statistika
```

---

## 🔒 Xavfsizlik

- **AuthMiddleware** — har so'rovda foydalanuvchi DB dan tekshiriladi
- **ThrottleMiddleware** — spam himoyasi (1 soniyada 1 so'rov)
- **Environment variables** — barcha maxfiy kalitlar `.env` da
- **ON DELETE CASCADE** — foydalanuvchi o'chirilsa barcha ma'lumotlar tozalanadi
- **Webhook** — Telegram signature tekshiruvi

---

## 📝 Litsenziya

MIT License

---

> **Muallif:** @fayzulloo
> **Versiya:** 2.0.0
> **Stack:** Python 3.11 · aiogram 3.7 · PostgreSQL · Railway · Gemini AI
