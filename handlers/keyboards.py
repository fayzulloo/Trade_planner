from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


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
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_{action}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel")
        ]
    ])


def settings_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Boshlang'ich balans", callback_data="set_balance")],
        [InlineKeyboardButton(text="📊 Kunlik % (hozir: 20%)", callback_data="set_rate")],
        [InlineKeyboardButton(text="➕ Qo'shimcha maqsad ($)", callback_data="set_extra")],
        [InlineKeyboardButton(text="💸 Yechish summasi", callback_data="set_withdrawal")],
        [InlineKeyboardButton(text="📅 Yechish davri (har necha kunda)", callback_data="set_wevery")],
        [InlineKeyboardButton(text="🗓 Kun soni", callback_data="set_days")],
        [InlineKeyboardButton(text="📆 Boshlanish sanasi", callback_data="set_startdate")],
        [InlineKeyboardButton(text="🌍 Timezone", callback_data="set_timezone")],
        [InlineKeyboardButton(text="⏰ Eslatma vaqti", callback_data="set_reminder")],
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
