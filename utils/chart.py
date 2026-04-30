import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime, date
from utils.logger import logger

CHARTS_DIR = "charts"
os.makedirs(CHARTS_DIR, exist_ok=True)


def _setup_style():
    plt.rcParams.update({
        "figure.facecolor": "#1a1a2e",
        "axes.facecolor": "#16213e",
        "axes.edgecolor": "#444",
        "axes.labelcolor": "#ccc",
        "xtick.color": "#aaa",
        "ytick.color": "#aaa",
        "grid.color": "#333",
        "grid.linestyle": "--",
        "grid.alpha": 0.5,
        "text.color": "#eee",
        "font.family": "DejaVu Sans",
    })


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def _format_date(d) -> str:
    """Sanani qisqa ko'rinishga o'tkazadi"""
    try:
        if isinstance(d, str):
            if "-" in d:
                d = datetime.strptime(d, "%Y-%m-%d").date()
            else:
                d = datetime.strptime(d, "%d.%m.%Y").date()
        return d.strftime("%d.%m")
    except Exception:
        return str(d)


def _save_chart(fig, prefix: str) -> str | None:
    try:
        plt.tight_layout()
        path = os.path.join(CHARTS_DIR, f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png")
        plt.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path
    except Exception as e:
        logger.error(f"Grafik saqlashda xato: {e}")
        plt.close("all")
        return None


def generate_pnl_chart(journals: list, title: str = "PnL") -> str | None:
    """Ustunli PnL grafigi — bo'sh bo'lsa ham ishlaydi"""
    try:
        _setup_style()

        if not journals:
            journals = [{"date": date.today().isoformat(), "actual_pnl": 0,
                         "target_profit": 0, "extra_target": 0}]

        dates = [_format_date(j.get("date", "")) for j in journals]
        pnls = [_safe_float(j.get("actual_pnl")) for j in journals]
        targets = [
            _safe_float(j.get("target_profit")) + _safe_float(j.get("extra_target"))
            for j in journals
        ]

        fig, ax = plt.subplots(figsize=(10, 5))
        x = list(range(len(dates)))
        bar_colors = ["#4ade80" if p >= 0 else "#f87171" for p in pnls]

        # Rollover kunlar to'q sariq rang
        final_colors = []
        for i, (p, j) in enumerate(zip(pnls, journals)):
            if j.get("is_rolled_over"):
                final_colors.append("#f59e0b")  # to'q sariq — rollover
            elif p >= 0:
                final_colors.append("#4ade80")  # yashil — foyda
            else:
                final_colors.append("#f87171")  # qizil — zarar
        bars = ax.bar(x, pnls, color=final_colors, alpha=0.85, zorder=3, width=0.6)
        ax.plot(x, targets, color="#fbbf24", linewidth=2, linestyle="--",
                marker="o", markersize=4, label="Maqsad", zorder=4)
        ax.axhline(y=0, color="#666", linewidth=0.8)

        ax.set_xticks(x)
        ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("USD", fontsize=10)
        ax.set_title(title, fontsize=13, pad=12, color="#fff")
        ax.grid(True, axis="y", zorder=0)

        green_patch = mpatches.Patch(color="#4ade80", label="Foyda")
        red_patch = mpatches.Patch(color="#f87171", label="Zarar")
        rollover_patch = mpatches.Patch(color="#f59e0b", label="Rollover")
        target_line = plt.Line2D([0], [0], color="#fbbf24", linestyle="--",
                                  linewidth=2, label="Maqsad")
        ax.legend(handles=[green_patch, red_patch, rollover_patch, target_line],
                  facecolor="#1a1a2e", edgecolor="#444", labelcolor="#ccc", fontsize=9)

        for bar, pnl in zip(bars, pnls):
            if pnl != 0:
                y_pos = bar.get_height() + (0.2 if pnl >= 0 else -0.5)
                ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                        f"{'+' if pnl > 0 else ''}{pnl:.1f}",
                        ha="center", va="bottom", fontsize=7.5, color="#eee")

        return _save_chart(fig, "pnl")

    except Exception as e:
        logger.error(f"PnL grafik xatosi: {e}")
        plt.close("all")
        return None


def generate_balance_chart(journals: list, settings: dict,
                            title: str = "Balans o'sishi") -> str | None:
    """Chiziqli balans grafigi — bo'sh bo'lsa ham ishlaydi"""
    try:
        _setup_style()
        from utils.calculator import calculate_balance_progression
        progression = calculate_balance_progression(settings)

        if not progression:
            logger.warning("Progressiya bo'sh — grafik yaratilmadi")
            return None

        prog_dates = [_format_date(d["date"]) for d in progression]
        expected_balances = [d["final_balance"] for d in progression]

        # Haqiqiy balanslar — faqat yakunlangan kunlar
        actual_balances = []
        actual_indices = []
        for i, j in enumerate(journals):
            eb = j.get("end_balance")
            if eb is not None:
                try:
                    actual_balances.append(float(eb))
                    actual_indices.append(i)
                except Exception:
                    pass

        fig, ax = plt.subplots(figsize=(10, 5))

        # Rejalangan chiziq
        ax.plot(range(len(prog_dates)), expected_balances,
                color="#60a5fa", linewidth=2, linestyle="--",
                marker="o", markersize=4, label="Rejalangan balans", zorder=3)
        ax.fill_between(range(len(prog_dates)), expected_balances,
                        alpha=0.08, color="#60a5fa")

        # Haqiqiy chiziq (bo'lsa)
        if actual_balances:
            ax.plot(actual_indices, actual_balances,
                    color="#4ade80", linewidth=2.5,
                    marker="o", markersize=5, label="Haqiqiy balans", zorder=4)

        # X o'qi — ko'p kun bo'lsa kamroq label
        n = len(prog_dates)
        if n <= 15:
            step = 1
        elif n <= 30:
            step = 2
        elif n <= 60:
            step = 5
        else:
            step = 10

        tick_positions = list(range(0, n, step))
        tick_labels = [prog_dates[i] for i in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=8)

        ax.set_ylabel("USD", fontsize=10)
        ax.set_title(title, fontsize=13, pad=12, color="#fff")
        ax.grid(True, zorder=0)
        ax.legend(facecolor="#1a1a2e", edgecolor="#444", labelcolor="#ccc", fontsize=9)

        return _save_chart(fig, "balance")

    except Exception as e:
        logger.error(f"Balans grafik xatosi: {e}")
        plt.close("all")
        return None
