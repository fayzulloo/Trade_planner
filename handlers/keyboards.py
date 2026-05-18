"""
Barcha Telegram tugmalari (Reply va Inline keyboard).
BOT_STRUCTURE.md dagi tugmalar strukturasiga mos.
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ─────────────────────────────────────────────
# 📱 ASOSIY MENYU (Reply Keyboard)
# ─────────────────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    """Asosiy pastki menyu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Bugungi reja"),
                KeyboardButton(text="⚙️ Sozlamalar"),
            ],
            [
                KeyboardButton(text="📈 Statistika"),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )


# ─────────────────────────────────────────────
# 📊 BUGUNGI REJA
# ─────────────────────────────────────────────

def plan_kb(
    is_withdrawal_day: bool = False,
    withdrawal_confirmed: bool = False,
    webapp_url: str = "",
) -> InlineKeyboardMarkup:
    """
    Bugungi reja inline tugmalari.
    Yechish kuni va tasdiqlash holatiga qarab o'zgaradi.
    """
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(
        text="📝 Savdo kiriting",
        callback_data="trade_add",
    ))
    builder.row(InlineKeyboardButton(
        text="🔄 Yangilash",
        callback_data="plan_refresh",
    ))

    # Yechish kuni — tasdiqlanmagan
    if is_withdrawal_day and not withdrawal_confirmed:
        builder.row(
            InlineKeyboardButton(
                text="✅ Yechib yakunlash",
                callback_data="confirm_withdrawal",
            ),
            InlineKeyboardButton(
                text="❌ Yechimsiz yakunlash",
                callback_data="reject_withdrawal",
            ),
        )
    else:
        builder.row(InlineKeyboardButton(
            text="✅ Kunni yakunlash",
            callback_data="complete_day",
        ))

    return builder.as_markup()


def confirm_complete_kb() -> InlineKeyboardMarkup:
    """Kunni yakunlash tasdiqlash tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha", callback_data="confirm_complete"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel"),
    )
    return builder.as_markup()


# ─────────────────────────────────────────────
# 📝 SAVDO KIRITISH
# ─────────────────────────────────────────────

def direction_kb() -> InlineKeyboardMarkup:
    """BUY / SELL tanlash."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📈 BUY", callback_data="dir_BUY"),
        InlineKeyboardButton(text="📉 SELL", callback_data="dir_SELL"),
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="trade_cancel"))
    return builder.as_markup()


def cancel_trade_kb() -> InlineKeyboardMarkup:
    """Savdo kiritishda bekor qilish tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="trade_cancel"))
    return builder.as_markup()


# ─────────────────────────────────────────────
# 📸 MT5 SCREENSHOT
# ─────────────────────────────────────────────

def mt5_trades_list_kb(trades: list[dict]) -> InlineKeyboardMarkup:
    """
    MT5 dan topilgan savdolar ro'yxati.
    Har bir savdo uchun tahrirlash tugmasi.
    """
    builder = InlineKeyboardBuilder()

    for i, trade in enumerate(trades):
        sign = "+" if trade["pnl"] >= 0 else ""
        builder.row(InlineKeyboardButton(
            text=f"✏️ {i+1}. {trade['symbol']} {trade['direction']} {sign}{trade['pnl']:.2f}$",
            callback_data=f"mt5_edit_{i}",
        ))

    builder.row(InlineKeyboardButton(
        text="✅ Hammasini saqlash",
        callback_data="mt5_save_all",
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Bekor",
        callback_data="mt5_cancel",
    ))
    return builder.as_markup()


def mt5_edit_fields_kb(idx: int) -> InlineKeyboardMarkup:
    """MT5 savdoning maydonlarini tahrirlash tugmalari."""
    fields = [
        ("Symbol",       "symbol"),
        ("Direction",    "direction"),
        ("Entry",        "entry_price"),
        ("Exit",         "exit_price"),
        ("Lot",          "quantity"),
        ("PnL",          "pnl"),
        ("Kirish vaqti", "open_time"),
        ("Chiqish vaqti","close_time"),
    ]
    builder = InlineKeyboardBuilder()
    row_items = []
    for label, field in fields:
        row_items.append(InlineKeyboardButton(
            text=label,
            callback_data=f"mt5ef_{idx}_{field}",
        ))
        if len(row_items) == 2:
            builder.row(*row_items)
            row_items = []
    if row_items:
        builder.row(*row_items)

    builder.row(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data="mt5_back_to_list",
    ))
    return builder.as_markup()


def mt5_after_edit_kb(idx: int) -> InlineKeyboardMarkup:
    """MT5 maydon tahrirlangandan keyingi tugmalar."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Qabul qilindi!",
        callback_data=f"mt5_edit_{idx}",
    ))
    builder.row(InlineKeyboardButton(
        text="✏️ Yana tahrirlash",
        callback_data=f"mt5_edit_{idx}",
    ))
    builder.row(InlineKeyboardButton(
        text="🔙 Ro'yxatga qaytish",
        callback_data="mt5_back_to_list",
    ))
    return builder.as_markup()


# ─────────────────────────────────────────────
# ⚙️ SOZLAMALAR
# ─────────────────────────────────────────────

def settings_kb(s: dict) -> InlineKeyboardMarkup:
    """
    Sozlamalar menyusi.
    s — settings dict (joriy qiymatlar ko'rsatiladi).
    """
    def fmt_rate(r):
        return f"{float(r)*100:.0f}%" if r else "—"

    def fmt_val(v, suffix=""):
        return f"{v}{suffix}" if v else "—"

    builder = InlineKeyboardBuilder()
    rows = [
        (f"💰 Boshlang'ich balans: {fmt_val(s.get('starting_balance'), '$')}", "set_balance"),
        (f"📊 Kunlik foiz: {fmt_rate(s.get('daily_profit_rate'))}", "set_rate"),
        (f"➕ Qo'shimcha maqsad: {fmt_val(s.get('extra_target'), '$')}", "set_extra"),
        (f"💸 Yechish summasi: {fmt_val(s.get('withdrawal_amount'), '$')}", "set_withdrawal"),
        (f"📅 Yechish davri: har {fmt_val(s.get('withdrawal_every'))} kunda", "set_wevery"),
        (f"🗓 Kun soni: {fmt_val(s.get('total_days'))} kun", "set_days"),
        (f"📆 Boshlanish: {fmt_val(s.get('start_date'))}", "set_startdate"),
        (f"🌍 Timezone: {s.get('timezone', 'Asia/Tashkent')}", "set_timezone"),
        (f"⏰ Ertalabki eslatma: {fmt_val(s.get('reminder_time'))}", "set_reminder"),
        (f"🌙 Kechki eslatma: {fmt_val(s.get('evening_reminder_time'))}", "set_evening_reminder"),
        (f"🔄 Avtomatik yakunlash: {fmt_val(s.get('auto_complete_time'))}", "set_auto_complete"),
        (f"🏦 Broker: {fmt_val(s.get('broker_name'))}", "set_broker"),
        ("🗓 Dam olish kunlari", "set_rest_days"),
        ("💾 Saqlash va yopish", "settings_save"),
    ]
    for text, cb in rows:
        builder.row(InlineKeyboardButton(text=text, callback_data=cb))
    return builder.as_markup()


def cancel_settings_kb() -> InlineKeyboardMarkup:
    """Sozlamalarda bekor qilish tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="settings_open"))
    return builder.as_markup()


def timezone_kb() -> InlineKeyboardMarkup:
    """Timezone tanlash ro'yxati."""
    timezones = [
        "Asia/Tashkent", "Asia/Almaty", "Asia/Dubai",
        "Europe/Moscow", "Europe/Istanbul", "Asia/Baku",
        "Asia/Tbilisi", "Asia/Bishkek", "Asia/Dushanbe",
        "Asia/Ashgabat",
    ]
    builder = InlineKeyboardBuilder()
    for tz in timezones:
        builder.row(InlineKeyboardButton(
            text=tz,
            callback_data=f"tz_{tz}",
        ))
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="settings_open"))
    return builder.as_markup()


def rest_days_kb(current: str = "6,7") -> InlineKeyboardMarkup:
    """
    Dam olish kunlari toggle tugmalari.
    current — tanlangan kunlar ("6,7" formatida)
    1=Yakshanba, 2=Dushanba, 3=Seshanba, 4=Chorshanba,
    5=Payshanba, 6=Juma, 7=Shanba
    """
    selected = set()
    if current:
        selected = {int(x.strip()) for x in current.split(",") if x.strip().isdigit()}

    days = [
        (2, "Du"), (3, "Se"), (4, "Chor"),
        (5, "Pay"), (6, "Ju"), (7, "Shan"),
        (1, "Yak"),
    ]

    builder = InlineKeyboardBuilder()
    row_items = []
    for code, label in days:
        icon = "✅" if code in selected else "☑️"
        row_items.append(InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"rd_toggle_{code}",
        ))
        if len(row_items) == 3:
            builder.row(*row_items)
            row_items = []
    if row_items:
        builder.row(*row_items)

    builder.row(
        InlineKeyboardButton(text="💾 Saqlash", callback_data="rd_save"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="settings_open"),
    )
    return builder.as_markup()


def evening_reminder_kb() -> InlineKeyboardMarkup:
    """Kechki eslatma — o'chirish imkoni."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🚫 O'chirish",
        callback_data="clear_evening_reminder",
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="settings_open",
    ))
    return builder.as_markup()


def broker_kb() -> InlineKeyboardMarkup:
    """Broker nomi — o'chirish imkoni."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🚫 O'chirish",
        callback_data="clear_broker",
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="settings_open",
    ))
    return builder.as_markup()


# ─────────────────────────────────────────────
# 📈 STATISTIKA
# ─────────────────────────────────────────────

def stats_menu_kb(webapp_url: str = "") -> InlineKeyboardMarkup:
    """Statistika davr tanlash menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Kunlik",   callback_data="stats_daily"))
    builder.row(InlineKeyboardButton(text="📆 Haftalik", callback_data="stats_weekly"))
    builder.row(InlineKeyboardButton(text="🗓 Oylik",    callback_data="stats_monthly"))
    builder.row(InlineKeyboardButton(text="🔢 Muddatni tanlash", callback_data="stats_range"))
    builder.row(InlineKeyboardButton(text="🎯 Strategiya davri natijasi", callback_data="stats_strategy"))
    if webapp_url:
        builder.row(InlineKeyboardButton(
            text="📊 Batafsil statistika",
            web_app={"url": webapp_url},
        ))
    return builder.as_markup()


def stats_result_kb(chart_cb: str) -> InlineKeyboardMarkup:
    """Statistika natijasi ko'rsatilgandan keyingi tugmalar."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Grafik ko'rish", callback_data=chart_cb))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="stats_back"))
    return builder.as_markup()


def stats_cancel_kb() -> InlineKeyboardMarkup:
    """Statistika FSM da bekor qilish."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="stats_back"))
    return builder.as_markup()


# ─────────────────────────────────────────────
# 🏁 STRATEGIYA TUGASH
# ─────────────────────────────────────────────

def strategy_finished_kb() -> InlineKeyboardMarkup:
    """Strategiya tugagandan keyingi tugma."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔄 Yangi strategiya boshlash",
        callback_data="new_strategy",
    ))
    return builder.as_markup()


# ─────────────────────────────────────────────
# 📝 SAVDO SL/TP/RESULT
# ─────────────────────────────────────────────

def skip_kb() -> InlineKeyboardMarkup:
    """SL/TP kiritishda o'tkazib yuborish tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="skip_field"))
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="trade_cancel"))
    return builder.as_markup()


def trade_result_kb() -> InlineKeyboardMarkup:
    """Savdo natijasini tanlash tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 TP ishladi", callback_data="result_tp"),
        InlineKeyboardButton(text="🔴 SL ishladi", callback_data="result_sl"),
    )
    builder.row(InlineKeyboardButton(text="⚪ Qo'lda yopildi", callback_data="result_manual"))
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="trade_cancel"))
    return builder.as_markup()
