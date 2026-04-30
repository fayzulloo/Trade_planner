# Trade Planner Bot

Forex trading jurnali va strategiya kuzatuvchi Telegram bot + WebApp.

## Xususiyatlar

- 📊 Kunlik reja, haqiqiy balans, rollover
- 📝 Savdo kiritish (qo'lda + MT5 skrinshot AI tahlil)
- 📈 Statistika va interaktiv grafiklar (WebApp)
- ⚙️ To'liq sozlamalar: foiz, yechish, dam olish kunlari, broker
- 🔔 Ertalabki/kechki eslatmalar, avtomatik yakunlash

## Railway da deploy

### 1. Bot service
```
BOT_TOKEN=...
DATABASE_URL=...
GEMINI_API_KEY=...
WEBAPP_URL=https://your-webapp.railway.app
```
`Procfile`:
```
worker: python main.py
```

### 2. WebApp service (alohida Railway service)
```
DATABASE_URL=...  (bir xil PostgreSQL)
BOT_TOKEN=...
PORT=8000  (Railway avtomatik beradi)
```
`Procfile`:
```
web: python webapp_server.py
```

## Loyiha strukturasi

```
trade_planner/
├── main.py
├── config.py
├── webapp_server.py
├── Dockerfile
├── handlers/
│   ├── keyboards.py
│   ├── start.py
│   ├── plan.py
│   ├── trade.py
│   ├── settings.py
│   └── stats.py
├── database/
│   ├── connection.py
│   ├── models.py
│   └── queries.py
├── scheduler/
│   ├── scheduler.py
│   └── jobs.py
├── middlewares/
│   ├── auth.py
│   └── throttle.py
├── utils/
│   ├── logger.py
│   ├── calculator.py
│   ├── chart.py
│   └── mt5_analyzer.py
└── webapp/
    ├── app.py
    ├── index.html
    └── static/
        ├── css/style.css
        └── js/app.js
```
