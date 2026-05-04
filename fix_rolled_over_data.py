"""
=============================================================
BIR MARTALIK BAZA TUZATISH SKRIPTI
=============================================================

MUAMMO:
    _apply_rollover() xatosi tufayli ba'zi jurnallar
    is_rolled_over=TRUE bo'lib qolgan, holbuki ular
    haqiqiy ish kunlari. get_all_journals() ularni
    filtrlaydi — statistika va balans nolga tushadi.

QOIDALAR:
    Jurnal is_rolled_over=TRUE bo'lishi FAQAT quyidagi
    holatda to'g'ri:
        — Kun maqsad bajarmagan VA
        — Shu KUN uchun KEYINGI kunda alohida jurnal
          yaratilgan (ya'ni bu kun rollover sababli takror)

    Boshqa barcha is_rolled_over=TRUE yozuvlar xato —
    FALSE ga o'tkazilishi kerak.

XAVFSIZLIK:
    — Avval DRY RUN (faqat ko'rsatadi, o'zgartirmaydi)
    — Tasdiqlangandan so'ng APPLY mode

ISHLATISH:
    python fix_rolled_over_data.py            # DRY RUN
    python fix_rolled_over_data.py --apply    # Bazaga yozadi
=============================================================
"""

import asyncio
import sys
import os
from datetime import date

# .env faylni yuklash
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    print("❌ DATABASE_URL topilmadi! .env faylni tekshiring.")
    sys.exit(1)


async def run(apply: bool):
    import asyncpg

    print(f"\n{'='*60}")
    mode_label = 'APPLY MODE' if apply else "DRY RUN — hech narsa o'zgarmaydi"
    print(f"  {mode_label}")
    print(f"{'='*60}\n")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # 1. Barcha is_rolled_over=TRUE yozuvlarni olish
        wrong_candidates = await conn.fetch("""
            SELECT
                dj.id,
                dj.user_id,
                dj.day_number,
                dj.date,
                dj.is_completed,
                dj.actual_pnl,
                dj.net_pnl,
                dj.carry_over_amount,
                dj.target_profit,
                dj.extra_target
            FROM daily_journal dj
            WHERE dj.is_rolled_over = TRUE
            ORDER BY dj.user_id, dj.date
        """)

        if not wrong_candidates:
            print("✅ Bazada is_rolled_over=TRUE yozuv topilmadi. Tuzatish kerak emas.\n")
            return

        print(f"🔍 Tekshirilayotgan is_rolled_over=TRUE yozuvlar soni: {len(wrong_candidates)}\n")

        to_fix = []      # FALSE ga o'tkazilishi kerak
        to_keep = []     # TRUE bo'lishi to'g'ri

        for row in wrong_candidates:
            user_id    = row["user_id"]
            day_number = row["day_number"]
            row_date   = row["date"]

            # Bu kun uchun keyingi kunda alohida jurnal bormi?
            # Ya'ni shu day_number bilan boshqa (keyingi) sana bormi?
            duplicate = await conn.fetchrow("""
                SELECT id, date FROM daily_journal
                WHERE user_id = $1
                  AND day_number = $2
                  AND date > $3
                LIMIT 1
            """, user_id, day_number, row_date)

            net = float(row["net_pnl"] or row["actual_pnl"] or 0)
            total_target = (
                float(row["target_profit"] or 0)
                + float(row["extra_target"] or 0)
                + float(row["carry_over_amount"] or 0)
            )

            # To'g'ri rollover: maqsad bajarilmagan VA keyingi jurnal mavjud
            real_rollover = (net < total_target) and (duplicate is not None)

            if real_rollover:
                to_keep.append(row)
            else:
                to_fix.append(row)

        # ── Natijalarni chiqarish ──────────────────────────────
        print(f"{'─'*60}")
        print(f"  ✅ To'g'ri rollover (o'zgartirilmaydi): {len(to_keep)} ta")
        print(f"  ⚠️  Xato rollover  (FALSE ga o'tadi):   {len(to_fix)} ta")
        print(f"{'─'*60}\n")

        if to_keep:
            print("📌 Saqlanadigan (haqiqiy rollover) yozuvlar:")
            for r in to_keep:
                print(f"   user={r['user_id']} | day={r['day_number']} | "
                      f"date={r['date']} | net={r['net_pnl'] or r['actual_pnl']}")

        if to_fix:
            print(f"\n🔧 Tuzatiladigan yozuvlar (is_rolled_over: TRUE → FALSE):")
            for r in to_fix:
                print(f"   user={r['user_id']} | day={r['day_number']} | "
                      f"date={r['date']} | completed={r['is_completed']} | "
                      f"net={r['net_pnl'] or r['actual_pnl']}")

        # ── Apply ─────────────────────────────────────────────
        if apply and to_fix:
            fix_ids = [r["id"] for r in to_fix]
            updated = await conn.execute("""
                UPDATE daily_journal
                SET is_rolled_over = FALSE
                WHERE id = ANY($1::int[])
            """, fix_ids)
            print(f"\n✅ {len(fix_ids)} ta yozuv tuzatildi: is_rolled_over = FALSE")
        elif not apply and to_fix:
            print(f"\n💡 Haqiqiy tuzatish uchun: python fix_rolled_over_data.py --apply")

        # ── Tekshiruv statistikasi ─────────────────────────────
        print(f"\n{'─'*60}")
        total_journals = await conn.fetchval("SELECT COUNT(*) FROM daily_journal")
        still_wrong   = await conn.fetchval(
            "SELECT COUNT(*) FROM daily_journal WHERE is_rolled_over = TRUE"
        )
        print(f"  Jami jurnal yozuvlar:        {total_journals}")
        print(f"  Hali is_rolled_over=TRUE:    {still_wrong}")
        print(f"{'─'*60}\n")

        if apply:
            print("🎉 Migration muvaffaqiyatli yakunlandi!")
            print("   Endi botni qayta ishga tushiring va statistikani tekshiring.\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    apply_mode = "--apply" in sys.argv
    asyncio.run(run(apply=apply_mode))
