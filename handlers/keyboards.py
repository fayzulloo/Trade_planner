from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
import os

WEBAPP_URL = os.getenv("WEBAPP_URL", "")


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Bugungi reja"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="📈 Statistika")],
        ],
        resize_keyboard=True,
        persistent=True
    )


def plan_inline(is_withdrawal_day: bool = False, withdrawal_confirmed: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📝 Savdo kiriting", callback_data="trade_add")],
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="plan_refresh")],
    ]
    if is_withdrawal_day and not withdrawal_confirmed:
        buttons.append([InlineKeyboardButton(text="💸 Yechishni tasdiqlash", callback_data="confirm_withdrawal")])
    if not is_withdrawal_day or withdrawal_confirmed:
        buttons.append([InlineKeyboardButton(text="✅ Kunni yakunlash", callback_data="complete_day")])
    if WEBAPP_URL:
        buttons.append([InlineKeyboardButton(
            text="📊 Batafsil statistika",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel")
        ]
    ])


def stats_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Kunlik", callback_data="stats_daily")],
        [InlineKeyboardButton(text="📆 Haftalik", callback_data="stats_weekly")],
        [InlineKeyboardButton(text="🗓 Oylik", callback_data="stats_monthly")],
        [InlineKeyboardButton(text="🔢 Muddatni tanlash", callback_data="stats_range")],
        [InlineKeyboardButton(text="🎯 Strategiya davri natijasi", callback_data="stats_strategy")],
    ])


def stats_chart_inline(period: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Grafik ko'rish", callback_data=f"chart_{period}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="stats_back")],
    ])


def back_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel")]
    ])
