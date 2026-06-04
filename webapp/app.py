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

        # Rejalangan balans — bugungi kun raqami asosida
        from utils.calculator import get_day_number, is_strategy_finished
        today_day_number = 0
        if start_date:
            today_day_number = get_day_number(
                start_date, today,
                settings.get("rest_days") or "",
                int(settings.get("total_days") or 0),
            ) or 0

        planned = calc_planned_balance(
            float(settings.get("starting_balance") or 0),
            float(settings.get("daily_profit_rate") or 0.1),
            today_day_number,
            float(settings.get("extra_target") or 0),
        ) if today_day_number > 0 else float(settings.get("starting_balance") or 0)

        mode = settings.get("mode", "strategy")

        return JSONResponse({
            "mode":            mode,
            "settings": {
                "starting_balance":  float(settings.get("starting_balance") or 0),
                "daily_profit_rate": float(settings.get("daily_profit_rate") or 0),
                "start_date":        settings.get("start_date"),
                "total_days":        settings.get("total_days"),
                "broker_name":       settings.get("broker_name"),
            },
            "current_balance": current_balance,
            # Journal rejimida rejalangan balans yo'q
            "planned_balance": planned if mode == "strategy" else None,
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
        if not settings:
            return JSONResponse({"journal": [], "mode": "strategy"})

        mode = settings.get("mode", "strategy")
        today = get_current_date(settings.get("timezone", "Asia/Tashkent"))

        # Journal rejimida start_date yo'q — barcha kunlarni qaytarish
        if mode == "journal":
            pool = await get_pool()
            async with pool.acquire() as conn:
                journals = await conn.fetch("""
                    SELECT * FROM daily_journal
                    WHERE user_id = $1
                    ORDER BY date DESC
                    LIMIT $2;
                """, user_id, limit)
        else:
            if not settings.get("start_date"):
                return JSONResponse({"journal": [], "mode": mode})
            start_date = parse_start_date(settings["start_date"])
            journals = await get_journal_range(user_id, start_date, today)
            journals = journals[-limit:]

        result = []
        for j in journals:
            total_target = (
                float(j["target_profit"] or 0) +
                float(j["extra_target"] or 0) +
                float(j["carry_over_amount"] or 0)
            )
            result.append({
                "day_number":     j["day_number"],
                "date":           j["date"].strftime("%d.%m.%Y"),
                "start_balance":  float(j["start_balance"] or 0),
                "end_balance":    float(j["end_balance"] or 0),
                "target":         total_target,
                "net_pnl":        float(j["net_pnl"] or 0),
                "is_completed":   j["is_completed"],
                "is_rolled_over": j["is_rolled_over"],
                "withdrawal":     float(j["withdrawal_amount"] or 0),
            })

        return JSONResponse({"journal": result, "mode": mode})
    except Exception as e:
        logger.error(f"get_journal xato [telegram_id={telegram_id}]: {e}")
        raise HTTPException(status_code=500, detail="Server xatosi")


@app.get("/api/day_detail")
async def get_day_detail(telegram_id: int, day_number: int):
    """
    Kun detail sahifasi — journal + savdolar ro'yxati.
    """
    user_id = await _get_user_id_from_telegram(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Journal
            journal = await conn.fetchrow("""
                SELECT * FROM daily_journal
                WHERE user_id = $1 AND day_number = $2;
            """, user_id, day_number)

            if not journal:
                raise HTTPException(status_code=404, detail="Jurnal topilmadi")

            # Savdolar
            trades = await conn.fetch("""
                SELECT * FROM trades
                WHERE user_id = $1 AND day_number = $2
                ORDER BY created_at ASC;
            """, user_id, day_number)

        total_target = (
            float(journal["target_profit"]) +
            float(journal["extra_target"]) +
            float(journal["carry_over_amount"])
        )

        trades_list = []
        for t in trades:
            net = float(t["pnl"]) + float(t["swap"] or 0) + float(t["commission"] or 0)
            # TP/SL aniqlash: exit_price ga qarab
            if float(t["pnl"]) > 0:
                result = "tp"
            elif float(t["pnl"]) < 0:
                result = "sl"
            else:
                result = "be"  # breakeven

            trades_list.append({
                "id":           t["id"],
                "symbol":       t["symbol"],
                "direction":    t["direction"],
                "entry_price":  float(t["entry_price"]),
                "exit_price":   float(t["exit_price"]),
                "quantity":     float(t["quantity"]),
                "pnl":          float(t["pnl"]),
                "swap":         float(t["swap"] or 0),
                "commission":   float(t["commission"] or 0),
                "net_pnl":      round(net, 2),
                "open_time":    t["open_time"] or "",
                "close_time":   t["close_time"] or "",
                "order_id":     t["order_id"] or "",
                "broker":       t["broker"] or "",
                "sl_price":     float(t["sl_price"]) if t["sl_price"] else None,
                "tp_price":     float(t["tp_price"]) if t["tp_price"] else None,
                "result":       t["result"] or "manual",
            })

        return JSONResponse({
            "journal": {
                "day_number":      journal["day_number"],
                "date":            journal["date"].strftime("%d.%m.%Y"),
                "start_balance":   float(journal["start_balance"]),
                "end_balance":     float(journal["end_balance"] or 0),
                "target_profit":   float(journal["target_profit"]),
                "extra_target":    float(journal["extra_target"]),
                "carry_over":      float(journal["carry_over_amount"]),
                "total_target":    total_target,
                "net_pnl":         float(journal["net_pnl"] or 0),
                "actual_pnl":      float(journal["actual_pnl"] or 0),
                "withdrawal":      float(journal["withdrawal_amount"] or 0),
                "is_completed":    journal["is_completed"],
                "is_rolled_over":  journal["is_rolled_over"],
            },
            "trades": trades_list,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_day_detail xato [telegram_id={telegram_id}]: {e}")
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
        if not settings:
            return JSONResponse({"actual_dates": [], "actual": [], "pnl": [], "planned_dates": [], "planned": []})

        mode             = settings.get("mode", "strategy")
        start_bal        = float(settings.get("starting_balance") or 0)
        rate             = float(settings.get("daily_profit_rate") or 0)
        extra            = float(settings.get("extra_target") or 0)
        total_days       = int(settings.get("total_days") or 0)
        rest_days        = settings.get("rest_days") or ""
        withdrawal_amt   = float(settings.get("withdrawal_amount") or 0)
        withdrawal_every = int(settings.get("withdrawal_every") or 0)
        today            = get_current_date(settings.get("timezone", "Asia/Tashkent"))

        # Journal rejimida start_date yo'q — faqat haqiqiy balans chiziq
        if mode == "journal":
            pool = await get_pool()
            async with pool.acquire() as conn:
                journals = await conn.fetch("""
                    SELECT date, end_balance, start_balance, net_pnl
                    FROM daily_journal
                    WHERE user_id = $1 AND is_completed = TRUE
                    ORDER BY date ASC;
                """, user_id)

            actual_dates    = [j["date"].strftime("%d.%m") for j in journals]
            actual_balances = [round(float(j["end_balance"] or j["start_balance"] or 0), 2) for j in journals]
            pnl_values      = [round(float(j["net_pnl"] or 0), 2) for j in journals]

            return JSONResponse({
                "actual_dates":  actual_dates,
                "actual":        actual_balances,
                "pnl":           pnl_values,
                "planned_dates": [],
                "planned":       [],
            })

        # Strategy rejimi
        if not settings.get("start_date"):
            return JSONResponse({"actual_dates": [], "actual": [], "pnl": [], "planned_dates": [], "planned": []})

        start_date = parse_start_date(settings["start_date"])
        journals   = await get_journal_range(user_id, start_date, today)

        # Rejalangan chiziq
        from datetime import timedelta
        from utils.calculator import is_rest_day as _is_rest_day

        planned_dates    = [start_date.strftime("%d.%m")]
        planned_balances = [start_bal]
        current   = start_date
        day_count = 0
        while day_count < total_days:
            if not _is_rest_day(current, rest_days):
                day_count += 1
                planned_dates.append(current.strftime("%d.%m"))
                planned_balances.append(round(calc_planned_balance(
                    start_bal, rate, day_count, extra, withdrawal_amt, withdrawal_every
                ), 2))
            current += timedelta(days=1)
            if (current - start_date).days > total_days * 3:
                break

        if not journals:
            return JSONResponse({
                "actual_dates":  [],
                "actual":        [],
                "pnl":           [],
                "planned_dates": planned_dates,
                "planned":       planned_balances,
            })

        actual_dates    = [j["date"].strftime("%d.%m") for j in journals]
        actual_balances = [round(float(j["end_balance"] or j["start_balance"] or 0), 2) for j in journals]
        pnl_values      = [round(float(j["net_pnl"] or 0), 2) for j in journals]

        return JSONResponse({
            "actual_dates":  actual_dates,
            "actual":        actual_balances,
            "pnl":           pnl_values,
            "planned_dates": planned_dates,
            "planned":       planned_balances,
        })
    except Exception as e:
        logger.error(f"get_chart_data xato [telegram_id={telegram_id}]: {e}")
        raise HTTPException(status_code=500, detail="Server xatosi")


@app.get("/api/stats")
async def get_trade_stats(telegram_id: int):
    """
    Jurnal tab uchun savdo statistikasi.
    Wins/Losses/BE breakdown, gross/swap/commission/net.
    """
    user_id = await _get_user_id_from_telegram(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT pnl, swap, commission, result
                FROM trades
                WHERE user_id = $1
                ORDER BY id;
            """, user_id)

        if not rows:
            return JSONResponse({})

        wins = [r for r in rows if (r['pnl'] or 0) > 0]
        losses = [r for r in rows if (r['pnl'] or 0) < 0]
        bes = [r for r in rows if (r['pnl'] or 0) == 0]

        def agg(group):
            gross = sum(float(r['pnl'] or 0) for r in group)
            swap  = sum(float(r['swap'] or 0) for r in group)
            comm  = sum(float(r['commission'] or 0) for r in group)
            net   = gross + swap + comm
            total_net_all = sum(float(r['pnl'] or 0) + float(r['swap'] or 0) + float(r['commission'] or 0) for r in rows)
            pct   = round((net / abs(total_net_all) * 100), 2) if total_net_all else 0
            return gross, swap, comm, net, pct

        wg, ws, wc, wn, wp = agg(wins)
        bg, bs_, bc, bn, bp = agg(bes)
        lg, ls, lc, ln, lp  = agg(losses)
        tg, ts, tc, tn, tp  = agg(rows)

        gross_win  = abs(wg)
        gross_loss = abs(lg)
        pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

        return JSONResponse({
            "total_trades":   len(rows),
            "wins":           len(wins),
            "losses":         len(losses),
            "break_even":     len(bes),
            "biggest_win":    max((float(r['pnl'] or 0) for r in wins), default=0),
            "biggest_loss":   min((float(r['pnl'] or 0) for r in losses), default=0),
            "profit_factor":  pf,
            "wins_gross":     round(wg, 2), "wins_swap":    round(ws, 2),
            "wins_commission":round(wc, 2), "wins_net":     round(wn, 2),
            "wins_pct":       wp,           "wins_rr":      0,
            "be_gross":       round(bg, 2), "be_swap":      round(bs_, 2),
            "be_commission":  round(bc, 2), "be_net":       round(bn, 2),
            "be_pct":         bp,           "be_rr":        0,
            "loss_gross":     round(lg, 2), "loss_swap":    round(ls, 2),
            "loss_commission":round(lc, 2), "loss_net":     round(ln, 2),
            "loss_pct":       lp,           "loss_rr":      0,
            "total_gross":    round(tg, 2), "total_swap":   round(ts, 2),
            "total_commission":round(tc,2), "total_net":    round(tn, 2),
            "total_pct":      tp,           "total_rr":     0,
        })
    except Exception as e:
        logger.error(f"get_trade_stats xato [telegram_id={telegram_id}]: {e}")
        raise HTTPException(status_code=500, detail="Server xatosi")



async def get_progression(telegram_id: int):
    """
    Barcha kunlar progression ma'lumotlarini qaytaradi.
    Grafik uchun ishlatiladi.
    """
    user_id = await _get_user_id_from_telegram(telegram_id)
    if not user_id:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    try:
        settings = await get_settings(user_id)
        if not settings or not settings.get("start_date"):
            return JSONResponse({"progression": []})

        start_bal        = float(settings.get("starting_balance") or 0)
        rate             = float(settings.get("daily_profit_rate") or 0.1)
        extra            = float(settings.get("extra_target") or 0)
        total_days       = int(settings.get("total_days") or 0)
        rest_days        = settings.get("rest_days") or ""
        withdrawal_amt   = float(settings.get("withdrawal_amount") or 0)
        withdrawal_every = int(settings.get("withdrawal_every") or 0)
        start_date       = parse_start_date(settings["start_date"])

        if not start_date or not total_days:
            return JSONResponse({"progression": []})

        journals    = await get_journal_range(user_id, start_date, start_date.replace(year=start_date.year + 1))
        journal_map = {j["day_number"]: j for j in journals}

        from datetime import timedelta
        from utils.calculator import is_rest_day as _is_rest_day

        progression = []
        current   = start_date
        day_count = 0

        while day_count < total_days:
            if not _is_rest_day(current, rest_days):
                day_count += 1
                j = journal_map.get(day_count)

                final_balance = round(calc_planned_balance(
                    start_bal, rate, day_count, extra, withdrawal_amt, withdrawal_every
                ), 2)
                prev_balance = round(calc_planned_balance(
                    start_bal, rate, day_count - 1, extra, withdrawal_amt, withdrawal_every
                ), 2)

                progression.append({
                    "day":            day_count,
                    "date":           current.strftime("%Y-%m-%d"),
                    "start_balance":  float(j["start_balance"]) if j else prev_balance,
                    "final_balance":  final_balance,
                    "actual_pnl":     float(j["net_pnl"]) if j and j["is_completed"] else None,
                    "is_completed":   bool(j["is_completed"]) if j else False,
                    "is_rolled_over": bool(j["is_rolled_over"]) if j and j["is_completed"] else False,
                    "target_profit":  float(j["target_profit"]) if j else 0,
                    "extra_target":   float(j["extra_target"]) if j else extra,
                    "carry_over":     float(j["carry_over_amount"]) if j else 0,
                })

            current += timedelta(days=1)
            if (current - start_date).days > total_days * 3:
                break

        return JSONResponse({"progression": progression})
    except Exception as e:
        logger.error(f"get_progression xato [telegram_id={telegram_id}]: {e}")
        raise HTTPException(status_code=500, detail="Server xatosi")
