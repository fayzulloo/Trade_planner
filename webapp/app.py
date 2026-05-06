"""
WebApp FastAPI routes.
Telegram WebApp orqali ochiladi.
"""

import logging
from datetime import date
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database.queries import (
    get_settings,
    get_journal_range,
    get_stats,
    get_strategy_summary,
)
from database.connection import get_pool
from utils.calculator import (
    get_current_date,
    parse_start_date,
    calc_planned_balance,
    format_money,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Trade Planner WebApp")

# webapp_server.py dan import uchun router
router = app.router

# Static fayllar
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


async def _get_user_id_from_telegram(telegram_id: int) -> int | None:
    """
    Telegram ID dan ichki user_id ni oladi.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1", telegram_id
            )
            return row["id"] if row else None
    except Exception as e:
        logger.error(f"_get_user_id_from_telegram xato: {e}")
        return None


@app.get("/", response_class=HTMLResponse)
async def index():
    """WebApp asosiy sahifasi."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>Trade Planner WebApp</h1>", status_code=200)


@app.get("/api/overview")
async def get_overview(telegram_id: int):
    """
    Overview tab ma'lumotlari.
    Haqiqiy va rejalangan balans, progress, sozlamalar.
    """
    user_id = await _get_user_id_from_telegram(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    try:
        settings = await get_settings(user_id)
        if not settings:
            raise HTTPException(status_code=404, detail="Sozlamalar topilmadi")

        today = get_current_date(settings["timezone"])
        start_date = parse_start_date(settings.get("start_date") or "")

        # Joriy balans (oxirgi yakunlangan kun)
        current_balance = float(settings["starting_balance"] or 0)
        if start_date:
            journals = await get_journal_range(user_id, start_date, today)
            completed = [j for j in journals if j["is_completed"]]
            if completed:
                current_balance = float(completed[-1]["end_balance"] or current_balance)

        # Strategiya statistikasi
        summary = None
        if start_date:
            stats = await get_stats(user_id, start_date, today)
            summary = {
                "total_days":      int(stats.get("completed_days") or 0),
                "planned_days":    settings.get("total_days") or 0,
                "total_pnl":       float(stats.get("total_net_pnl") or 0),
                "win_days":        int(stats.get("win_days") or 0),
                "loss_days":       int(stats.get("loss_days") or 0),
            }

        # Rejalangan balans
        planned = calc_planned_balance(
            float(settings.get("starting_balance") or 0),
            float(settings.get("daily_profit_rate") or 0.1),
            summary["total_days"] if summary else 0,
            float(settings.get("extra_target") or 0),
        ) if summary else float(settings.get("starting_balance") or 0)

        return JSONResponse({
            "settings": {
                "starting_balance":  float(settings.get("starting_balance") or 0),
                "daily_profit_rate": float(settings.get("daily_profit_rate") or 0),
                "start_date":        settings.get("start_date"),
                "total_days":        settings.get("total_days"),
                "broker_name":       settings.get("broker_name"),
            },
            "current_balance": current_balance,
            "planned_balance": planned,
            "summary":         summary,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_overview xato [telegram_id={telegram_id}]: {e}")
        raise HTTPException(status_code=500, detail="Server xatosi")


@app.get("/api/journal")
async def get_journal(telegram_id: int, limit: int = 30):
    """
    Statistika tab — kunlik jurnal jadvali.
    """
    user_id = await _get_user_id_from_telegram(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    try:
        settings = await get_settings(user_id)
        if not settings or not settings.get("start_date"):
            return JSONResponse({"journal": []})

        start_date = parse_start_date(settings["start_date"])
        today = get_current_date(settings["timezone"])
        journals = await get_journal_range(user_id, start_date, today)

        result = []
        for j in journals[-limit:]:
            total_target = (
                float(j["target_profit"]) +
                float(j["extra_target"]) +
                float(j["carry_over_amount"])
            )
            result.append({
                "day_number":   j["day_number"],
                "date":         j["date"].strftime("%d.%m.%Y"),
                "start_balance": float(j["start_balance"]),
                "end_balance":  float(j["end_balance"] or 0),
                "target":       total_target,
                "net_pnl":      float(j["net_pnl"] or 0),
                "is_completed": j["is_completed"],
                "is_rolled_over": j["is_rolled_over"],
                "withdrawal":   float(j["withdrawal_amount"] or 0),
            })

        return JSONResponse({"journal": result})
    except Exception as e:
        logger.error(f"get_journal xato [telegram_id={telegram_id}]: {e}")
        raise HTTPException(status_code=500, detail="Server xatosi")


@app.get("/api/chart_data")
async def get_chart_data(telegram_id: int):
    """
    Grafik tab — balans va PnL ma'lumotlari.
    """
    user_id = await _get_user_id_from_telegram(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    try:
        settings = await get_settings(user_id)
        if not settings or not settings.get("start_date"):
            return JSONResponse({"dates": [], "actual": [], "planned": [], "pnl": []})

        start_date = parse_start_date(settings["start_date"])
        today = get_current_date(settings["timezone"])
        journals = await get_journal_range(user_id, start_date, today)

        dates = []
        actual_balances = []
        planned_balances = []
        pnl_values = []

        start_bal = float(settings.get("starting_balance") or 0)
        rate = float(settings.get("daily_profit_rate") or 0.1)
        extra = float(settings.get("extra_target") or 0)

        for i, j in enumerate(journals, 1):
            dates.append(j["date"].strftime("%d.%m"))
            actual_balances.append(float(j["end_balance"] or j["start_balance"]))
            planned_balances.append(calc_planned_balance(start_bal, rate, i, extra))
            pnl_values.append(float(j["net_pnl"] or 0))

        return JSONResponse({
            "dates":   dates,
            "actual":  actual_balances,
            "planned": planned_balances,
            "pnl":     pnl_values,
        })
    except Exception as e:
        logger.error(f"get_chart_data xato [telegram_id={telegram_id}]: {e}")
        raise HTTPException(status_code=500, detail="Server xatosi")
