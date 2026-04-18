import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
from config import CHARTS_DIR
from utils.logger import logger


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


def generate_pnl_chart(journals: list, title: str = "PnL") -> str:
    """Ustunli PnL grafigi"""
    try:
        _setup_style()
        dates = [j["date"] for j in journals]
        pnls = [j.get("actual_pnl", 0) for j in journals]
        targets = [j.get("profit_target", 0) + j.get("extra_target", 0) for j in journals]

        fig, ax = plt.subplots(figsize=(10, 5))
        x = range(len(dates))
        bar_colors = ["#4ade80" if p >= 0 else "#f87171" for p in pnls]

        bars = ax.bar(x, pnls, color=bar_colors, alpha=0.85, zorder=3, width=0.6)
        ax.plot(x, targets, color="#fbbf24", linewidth=2, linestyle="--",
                marker="o", markersize=4, label="Maqsad", zorder=4)

        ax.axhline(y=0, color="#666", linewidth=0.8)
        ax.set_xticks(list(x))
        ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("USD", fontsize=10)
        ax.set_title(title, fontsize=13, pad=12, color="#fff")
        ax.grid(True, axis="y", zorder=0)

        green_patch = mpatches.Patch(color="#4ade80", label="Foyda")
        red_patch = mpatches.Patch(color="#f87171", label="Zarar")
        target_line = plt.Line2D([0], [0], color="#fbbf24", linestyle="--", linewidth=2, label="Maqsad")
        ax.legend(handles=[green_patch, red_patch, target_line],
                  facecolor="#1a1a2e", edgecolor="#444", labelcolor="#ccc", fontsize=9)

        for bar, pnl in zip(bars, pnls):
            if pnl != 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + (0.2 if pnl >= 0 else -0.5),
                        f"{'+' if pnl > 0 else ''}{pnl:.1f}",
                        ha="center", va="bottom", fontsize=7.5, color="#eee")

        plt.tight_layout()
        path = os.path.join(CHARTS_DIR, f"pnl_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        plt.savefig(path, dpi=130, bbox_inches="tight")
        plt.close()
        return path
    except Exception as e:
        logger.error(f"PnL grafik xatosi: {e}")
        return None


def generate_balance_chart(journals: list, settings: dict, title: str = "Balans o'sishi") -> str:
    """Chiziqli balans grafigi"""
    try:
        _setup_style()
        from utils.calculator import calculate_balance_progression
        progression = calculate_balance_progression(settings)

        prog_dates = [d["date"] for d in progression]
        expected_balances = [d["final_balance"] for d in progression]

        actual_dates = [j["date"] for j in journals if j.get("end_balance")]
        actual_balances = [j["end_balance"] for j in journals if j.get("end_balance")]

        fig, ax = plt.subplots(figsize=(10, 5))

        ax.plot(range(len(prog_dates)), expected_balances,
                color="#60a5fa", linewidth=2, linestyle="--",
                marker="o", markersize=4, label="Rejalangan balans", zorder=3)

        if actual_balances:
            ax.plot(range(len(actual_balances)), actual_balances,
                    color="#4ade80", linewidth=2.5,
                    marker="o", markersize=5, label="Haqiqiy balans", zorder=4)

        ax.fill_between(range(len(prog_dates)), expected_balances,
                        alpha=0.08, color="#60a5fa")

        ax.set_xticks(range(len(prog_dates)))
        ax.set_xticklabels(prog_dates, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("USD", fontsize=10)
        ax.set_title(title, fontsize=13, pad=12, color="#fff")
        ax.grid(True, zorder=0)
        ax.legend(facecolor="#1a1a2e", edgecolor="#444", labelcolor="#ccc", fontsize=9)

        plt.tight_layout()
        path = os.path.join(CHARTS_DIR, f"balance_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        plt.savefig(path, dpi=130, bbox_inches="tight")
        plt.close()
        return path
    except Exception as e:
        logger.error(f"Balans grafik xatosi: {e}")
        return None
