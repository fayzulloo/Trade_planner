"""
Statistika grafiklarini yaratish.
matplotlib orqali PNG rasm sifatida qaytaradi.
"""

import io
import logging
from datetime import date
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # GUI bo'lmagan muhit uchun
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch

logger = logging.getLogger(__name__)

# Rang palitasi
COLORS = {
    "green":      "#2ecc71",
    "red":        "#e74c3c",
    "blue":       "#3498db",
    "planned":    "#95a5a6",
    "background": "#1a1a2e",
    "surface":    "#16213e",
    "text":       "#eaeaea",
    "grid":       "#2d2d4e",
}


def _apply_dark_style(ax, fig) -> None:
    """
    Dark tema stilini qo'llaydi.
    """
    fig.patch.set_facecolor(COLORS["background"])
    ax.set_facecolor(COLORS["surface"])
    ax.tick_params(colors=COLORS["text"], labelsize=9)
    ax.xaxis.label.set_color(COLORS["text"])
    ax.yaxis.label.set_color(COLORS["text"])
    ax.title.set_color(COLORS["text"])
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.spines["top"].set_color(COLORS["grid"])
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["right"].set_color(COLORS["grid"])
    ax.grid(True, color=COLORS["grid"], linestyle="--", linewidth=0.5, alpha=0.7)


def create_balance_chart(
    dates: list[date],
    actual_balances: list[float],
    planned_balances: list[float],
    title: str = "Balans o'sishi",
) -> Optional[bytes]:
    """
    Haqiqiy va rejalangan balans grafigini yaratadi.

    Parametrlar:
        dates             — sanalar ro'yxati
        actual_balances   — haqiqiy balanslar
        planned_balances  — rejalangan balanslar
        title             — grafik sarlavhasi

    Qaytaradi: PNG rasm bytes yoki None (xato bo'lsa)
    """
    try:
        fig, ax = plt.subplots(figsize=(10, 5))
        _apply_dark_style(ax, fig)

        # Rejalangan chiziq
        ax.plot(
            dates, planned_balances,
            color=COLORS["planned"],
            linewidth=1.5,
            linestyle="--",
            label="Rejalangan",
            alpha=0.8,
        )

        # Haqiqiy balans chiziq
        ax.plot(
            dates, actual_balances,
            color=COLORS["blue"],
            linewidth=2,
            label="Haqiqiy",
            marker="o",
            markersize=4,
        )

        # Maydon to'ldirish
        ax.fill_between(
            dates, actual_balances, planned_balances,
            where=[a >= p for a, p in zip(actual_balances, planned_balances)],
            alpha=0.15, color=COLORS["green"], label="Ustunlik",
        )
        ax.fill_between(
            dates, actual_balances, planned_balances,
            where=[a < p for a, p in zip(actual_balances, planned_balances)],
            alpha=0.15, color=COLORS["red"], label="Qoloqlik",
        )

        # X o'qi formati
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 8)))
        plt.xticks(rotation=45)

        # Y o'qi — dollar belgisi
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )

        ax.set_title(title, fontsize=13, pad=12, fontweight="bold")
        ax.set_xlabel("Sana", fontsize=10)
        ax.set_ylabel("Balans ($)", fontsize=10)
        ax.legend(
            facecolor=COLORS["surface"],
            edgecolor=COLORS["grid"],
            labelcolor=COLORS["text"],
            fontsize=9,
        )

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        logger.error(f"create_balance_chart xato: {e}")
        return None


def create_pnl_chart(
    dates: list[date],
    pnl_values: list[float],
    targets: list[float],
    title: str = "Kunlik PnL",
) -> Optional[bytes]:
    """
    Kunlik PnL bar chart yaratadi.
    Maqsadga erishilgan kunlar — yashil, erishilmagan — qizil.

    Parametrlar:
        dates      — sanalar ro'yxati
        pnl_values — kunlik net PnL lar
        targets    — kunlik maqsadlar
        title      — grafik sarlavhasi

    Qaytaradi: PNG rasm bytes yoki None
    """
    try:
        fig, ax = plt.subplots(figsize=(10, 5))
        _apply_dark_style(ax, fig)

        # Har kun uchun rang belgilash
        bar_colors = [
            COLORS["green"] if pnl >= target else COLORS["red"]
            for pnl, target in zip(pnl_values, targets)
        ]

        # Bar chart
        x_pos = range(len(dates))
        bars = ax.bar(x_pos, pnl_values, color=bar_colors, alpha=0.85, width=0.6)

        # Maqsad chizig'i
        ax.plot(
            x_pos, targets,
            color=COLORS["planned"],
            linewidth=1.5,
            linestyle="--",
            label="Maqsad",
            marker="x",
            markersize=5,
        )

        # Nol chizig'i
        ax.axhline(y=0, color=COLORS["text"], linewidth=0.8, alpha=0.5)

        # X o'qi — sanalar
        ax.set_xticks(list(x_pos))
        ax.set_xticklabels(
            [d.strftime("%d.%m") for d in dates],
            rotation=45,
            fontsize=8,
        )

        # Y o'qi
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )

        ax.set_title(title, fontsize=13, pad=12, fontweight="bold")
        ax.set_ylabel("PnL ($)", fontsize=10)
        ax.legend(
            facecolor=COLORS["surface"],
            edgecolor=COLORS["grid"],
            labelcolor=COLORS["text"],
            fontsize=9,
        )

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        logger.error(f"create_pnl_chart xato: {e}")
        return None
