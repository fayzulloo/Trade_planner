# 📊 Trade Planner Bot

> Telegram orqali ishlatiladigan professional trading journal va rejalashtirish boti.
> Kunlik maqsadlarni kuzatish, savdolarni qayd etish va strategiya progressini tahlil qilish uchun mo'ljallangan.

---

## 🚀 Imkoniyatlar

- **Kunlik reja** — boshlang'ich balans va foiz asosida avtomatik maqsad hisoblash
- **Savdolarni qayd etish** — har bir treyid uchun PnL, swap, commission hisobi
- **Rollover tizimi** — bajarilmagan maqsad keyingi kunga avtomatik o'tkaziladi
- **Strategiya progressi** — N kunlik strategiya davomida balans o'sishini kuzatish
- **MT5 screenshot tahlili** — Google Gemini AI orqali savdo skrinshotini avtomatik tahlil qilish
- **Eslatmalar** — ertalabki va kechki eslatmalar, avtomatik kun yakunlash
- **WebApp dashboard** — balans grafigi, jurnal va statistika
- **Ko'p foydalanuvchi** — har bir foydalanuvchi o'z sozlamalari va ma'lumotlari bilan ishlaydi

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
| Google Gemini API | — | MT5 screenshot tahlili |
| Railway | — | Cloud deployment |

---

## 📁 Loyiha strukturasi

```
trade_planner/
├── main.py                    # Bot ishga tushirish nuqtasi
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
│   ├── start.py               # /start, onboarding
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
│   ├── chart.py               # Grafik generatsiya
│   ├── logger.py              # Logging sozlamalari
│   └── mt5_analyzer.py        # Gemini AI tahlil
│
└── webapp/
    ├── __init__.py
    ├── app.py                 # FastAPI routes, static files
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
```

### 5. Ishga tushirish

```bash
# Bot
python main.py

# WebApp (alohida terminal)
python webapp_server.py
```

---

## 🗄️ Ma'lumotlar bazasi

### Jadvallar

```
users          — Telegram foydalanuvchilar
settings       — Har bir user sozlamalari (1:1)
trades         — Savdo yozuvlari (1:N)
daily_journal  — Kunlik jurnal (1:N, UNIQUE user+date)
```

### Asosiy formulalar

```
net_pnl       = pnl + swap + commission
total_target  = target_profit + extra_target + carry_over_amount
end_balance   = start_balance + net_pnl - withdrawal
is_rolled_over = net_pnl < total_target
```

---

## 📅 Scheduler vazifalari

| Vazifa | Vaqt | Tavsif |
|---|---|---|
| `job_create_daily_journals` | 00:01 UTC | Barcha userlar uchun yangi kun jurnal yaratish |
| `job_morning_reminder` | Har daqiqa* | Ertalabki reja eslatmasi |
| `job_evening_reminder` | Har daqiqa* | Kechki progress eslatmasi |
| `job_auto_complete` | Har daqiqa* | Avtomatik kun yakunlash |

*Har daqiqa ishlaydi, ichida foydalanuvchi timezone va sozlangan vaqt tekshiriladi.

---

## 🌐 Railway Deploy

### Servislar

Loyiha Railway da **2 ta alohida servis** sifatida deploy qilinadi:

```
Trade_planner     → worker: python main.py      (bot)
webapp-service    → web: python webapp_server.py (dashboard)
Postgres          → ma'lumotlar bazasi
```

### Environment variables (Trade_planner)

```
BOT_TOKEN
DATABASE_URL
GEMINI_API_KEY
WEBAPP_URL
```

### Environment variables (webapp-service)

```
DATABASE_URL
PORT  (Railway avtomatik beradi)
```

---

## 🔄 Rollover tizimi

Maqsadga erishilmagan kunlar keyingi kunga avtomatik o'tkaziladi:

```
1-kun: Maqsad 500$, bajarildi 300$ → carry_over = 200$
2-kun: Maqsad 550$ + 200$ = 750$
```

Scheduler ketma-ketligi:
```
23:30 → auto_complete (kun yakunlandi, is_rolled_over = TRUE)
00:01 → create_journal (oldingi kundan carry_over hisoblanadi)
```

---

## 📊 WebApp Dashboard

Dashboard quyidagi ma'lumotlarni ko'rsatadi:

- **Overview** — haqiqiy vs rejalangan balans, progress, natijalar, sozlamalar
- **Jurnal** — kunlik jurnal jadvali (holat, PnL, maqsad)
- **Grafik** — balans o'sishi va kunlik PnL bar chart

WebApp Telegram WebApp API orqali ishlaydi va faqat bot ichidan ochiladi.

---

## 🤖 Bot buyruqlari

| Buyruq | Tavsif |
|---|---|
| `/start` | Botni ishga tushirish, onboarding |

Asosiy boshqaruv reply klaviatura orqali amalga oshiriladi:

```
📊 Bugungi reja     ⚙️ Sozlamalar
           📈 Statistika 
```

---

## 🔒 Xavfsizlik

- **AuthMiddleware** — har so'rovda foydalanuvchi DB dan tekshiriladi
- **ThrottleMiddleware** — spam himoyasi (1 soniyada 1 so'rov)
- **Environment variables** — barcha maxfiy kalitlar `.env` da
- **ON DELETE CASCADE** — foydalanuvchi o'chirilsa barcha ma'lumotlar tozalanadi

---

---

> **Muallif:** @fayzulloo
> **Versiya:** 1.2.0
> **Stack:** Python 3.11.8 · aiogram 3.7 · PostgreSQL · Railway
