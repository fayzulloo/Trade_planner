"""
Trade Planner WebApp — Telegram Mini App backend
FastAPI bilan yozilgan, PostgreSQL dan ma'lumot oladi.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import hmac
import hashlib
import json
import os
from urllib.parse import unquote, parse_qs
from database.connection import get_pool
from database.queries import (
    get_user_id, get_settings, get_all_journals,
    get_journal_range, get_trades_range
)
from utils.calculator import (
    get_strategy_summary, calculate_balance_progression,
    parse_rest_days, get_real_balance as calc_real_balance
)
from utils.logger import logger
from datetime import date, timedelta

app = FastAPI(title="Trade Planner WebApp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


@app.on_event("startup")
async def startup():
    """Ishga tushganda PostgreSQL pool yaratadi"""
    from database.connection import init_pool
    await init_pool()
    logger.info("WebApp: PostgreSQL pool tayyor.")


@app.on_event("shutdown")
async def shutdown():
    from database.connection import close_pool
    await close_pool()
    logger.info("WebApp: PostgreSQL pool yopildi.")


def verify_telegram_data(init_data: str) -> dict | None:
    """Telegram WebApp init_data ni tekshiradi"""
    try:
        parsed = parse_qs(init_data)
        hash_val = parsed.get("hash", [""])[0]

        data_check = "\n".join(
            f"{k}={v[0]}"
            for k, v in sorted(parsed.items())
            if k != "hash"
        )

        secret = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        expected = hmac.new(
            secret,
            data_check.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, hash_val):
            return None

        user_data = json.loads(unquote(parsed.get("user", ["{}"])[0]))
        return user_data
    except Exception as e:
        logger.error(f"Telegram verify xato: {e}")
        return None


async def get_user_from_request(request: Request) -> int | None:
    """Request dan telegram_id ni oladi"""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        # Development mode — query param
        telegram_id = request.query_params.get("telegram_id")
        if telegram_id:
            return int(telegram_id)
        return None

    user_data = verify_telegram_data(init_data)
    if not user_data:
        return None
    return user_data.get("id")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/summary")
async def api_summary(request: Request):
    telegram_id = await get_user_from_request(request)
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = await get_user_id(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    settings = await get_settings(user_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    journals = await get_all_journals(user_id)
    summary = get_strategy_summary(settings, journals)
    real_balance = await get_real_balance_db(user_id, float(settings["starting_balance"] or 0))

    return {
        "summary": summary,
        "real_balance": real_balance,
        "settings": {
            "starting_balance": float(settings["starting_balance"] or 0),
            "daily_profit_rate": float(settings["daily_profit_rate"] or 0.20),
            "total_days": int(settings["total_days"] or 0),
            "start_date": settings["start_date"],
            "broker_name": settings["broker_name"],
        }
    }


@app.get("/api/journals")
async def api_journals(request: Request, period: str = "strategy"):
    telegram_id = await get_user_from_request(request)
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = await get_user_id(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    today = date.today()
    if period == "daily":
        journals = await get_journal_range(user_id, today.isoformat(), today.isoformat())
    elif period == "weekly":
        journals = await get_journal_range(user_id, (today - timedelta(days=6)).isoformat(), today.isoformat())
    elif period == "monthly":
        journals = await get_journal_range(user_id, today.replace(day=1).isoformat(), today.isoformat())
    else:
        journals = await get_all_journals(user_id)

    return {"journals": [_serialize_journal(j) for j in journals]}


@app.get("/api/progression")
async def api_progression(request: Request):
    telegram_id = await get_user_from_request(request)
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = await get_user_id(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    settings = await get_settings(user_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    journals = await get_all_journals(user_id)
    progression = calculate_balance_progression(settings, journals)

    journal_map = {j["day_number"]: j for j in journals}
    result = []
    for d in progression:
        j = journal_map.get(d["day"])
        result.append({
            **d,
            "actual_pnl": float(j["actual_pnl"]) if j else None,
            "is_completed": bool(j["is_completed"]) if j else False,
            "is_rolled_over": bool(d.get("is_rolled_over")),
        })

    return {"progression": result}


async def get_real_balance_db(user_id: int, starting: float) -> float:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COALESCE(SUM(pnl + COALESCE(swap,0) + COALESCE(commission,0)), 0) AS total
            FROM trades t
            JOIN daily_journal dj ON t.user_id = dj.user_id AND t.day_number = dj.day_number
            WHERE t.user_id = $1 AND dj.is_completed = TRUE
        """, user_id)
    return round(starting + float(row["total"] if row else 0), 2)


def _serialize_journal(j: dict) -> dict:
    return {
        "day_number": j.get("day_number"),
        "date": str(j.get("date", "")),
        "start_balance": float(j.get("start_balance") or 0),
        "target_profit": float(j.get("target_profit") or 0),
        "extra_target": float(j.get("extra_target") or 0),
        "carry_over_amount": float(j.get("carry_over_amount") or 0),
        "actual_pnl": float(j.get("actual_pnl") or 0),
        "is_completed": bool(j.get("is_completed")),
        "is_rolled_over": bool(j.get("is_rolled_over")),
        "is_withdrawal_day": bool(j.get("is_withdrawal_day")),
        "withdrawal_confirmed": bool(j.get("withdrawal_confirmed")),
    }
