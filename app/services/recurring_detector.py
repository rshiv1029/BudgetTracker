"""
Recurring transaction detector.

Algorithm:
1. Group all non-excluded, non-transfer transactions by merchant_clean
2. For each merchant, look for amount clusters (within 5% tolerance)
3. If a cluster appears in >= 2 distinct calendar months, flag as recurring
4. Determine frequency by analyzing gaps between occurrence dates
5. Upsert into recurring_transactions table
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Transaction


# ── helpers ───────────────────────────────────────────────────────────────────

def _amount_key(amount: float, tolerance: float = 0.05) -> int:
    """Round amount to nearest 5% bucket for fuzzy matching."""
    return round(amount / max(abs(amount) * tolerance, 0.01))


def _detect_frequency(gaps_days: list[int]) -> tuple[str, Optional[int]]:
    """
    Given a list of day-gaps between occurrences, return (frequency, typical_day).
    typical_day = median day-of-month for monthly, or median gap for weekly.
    """
    if not gaps_days:
        return "irregular", None

    median_gap = statistics.median(gaps_days)

    if 25 <= median_gap <= 35:
        return "monthly", int(median_gap)
    elif 12 <= median_gap <= 18:
        return "biweekly", int(median_gap)
    elif 6 <= median_gap <= 9:
        return "weekly", int(median_gap)
    elif 340 <= median_gap <= 390:
        return "annual", int(median_gap)
    else:
        return "irregular", int(median_gap)


def _next_expected(last_date: date, frequency: str, typical_day: Optional[int]) -> date:
    """Estimate next occurrence date."""
    if frequency == "monthly" and typical_day:
        d = last_date + timedelta(days=typical_day)
        return d
    elif frequency == "biweekly" and typical_day:
        return last_date + timedelta(days=typical_day)
    elif frequency == "weekly" and typical_day:
        return last_date + timedelta(days=typical_day)
    elif frequency == "annual" and typical_day:
        return last_date + timedelta(days=typical_day)
    else:
        return last_date + timedelta(days=30)


# ── main detector ─────────────────────────────────────────────────────────────

def detect_recurring(db: Session) -> list[dict]:
    """
    Scan all transactions and return list of detected recurring patterns.
    Also upserts results into the recurring_transactions table.
    """
    # Lazy import to avoid circular at module level
    from app.models import RecurringTransaction  # noqa

    # Pull all non-excluded, non-transfer transactions
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.is_excluded == False,  # noqa: E712
            Transaction.is_transfer == False,   # noqa: E712
            Transaction.merchant_clean != None,  # noqa: E711
        )
        .order_by(Transaction.date.asc())
        .all()
    )

    # Group: merchant → list of (date, abs_amount, is_income)
    merchant_groups: dict[str, list[tuple[date, float, bool]]] = defaultdict(list)
    for t in txns:
        if not t.merchant_clean:
            continue
        merchant_groups[t.merchant_clean].append(
            (t.date, abs(t.amount), t.amount > 0)
        )

    detected = []

    for merchant, occurrences_raw in merchant_groups.items():
        if len(occurrences_raw) < 2:
            continue

        # Cluster by amount (within 5% of median)
        amounts = [amt for _, amt, _ in occurrences_raw]
        median_amt = statistics.median(amounts)
        tolerance = max(median_amt * 0.05, 1.0)  # at least $1 wiggle room

        # Filter to transactions within the amount cluster
        cluster = [
            (d, amt, is_inc)
            for d, amt, is_inc in occurrences_raw
            if abs(amt - median_amt) <= tolerance
        ]

        if len(cluster) < 2:
            continue

        # Must span at least 2 distinct calendar months
        months_seen = {(d.year, d.month) for d, _, _ in cluster}
        if len(months_seen) < 2:
            continue

        # Sort by date
        cluster.sort(key=lambda x: x[0])

        dates = [d for d, _, _ in cluster]
        gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]

        frequency, typical_day = _detect_frequency(gaps)

        # Skip truly irregular patterns with wildly varying gaps
        if frequency == "irregular" and len(gaps) > 1:
            gap_stdev = statistics.stdev(gaps) if len(gaps) > 1 else 0
            if gap_stdev > 20:
                continue

        last_date = dates[-1]
        next_date = _next_expected(last_date, frequency, typical_day)
        is_income = sum(1 for _, _, inc in cluster if inc) > len(cluster) / 2
        avg_amount = statistics.mean(amt for _, amt, _ in cluster)

        pattern = {
            "merchant_clean": merchant,
            "category": occurrences_raw[0][2] and "Income" or "Uncategorized",
            "amount": round(avg_amount, 2),
            "is_income": is_income,
            "frequency": frequency,
            "typical_day": typical_day,
            "last_seen_date": last_date,
            "next_expected_date": next_date,
            "occurrences": len(cluster),
        }
        detected.append(pattern)

        # Upsert into DB
        existing = (
            db.query(RecurringTransaction)
            .filter(RecurringTransaction.merchant_clean == merchant)
            .first()
        )
        if existing:
            # Only update if not manually dismissed/confirmed
            if existing.status == "detected":
                existing.amount = pattern["amount"]
                existing.frequency = frequency
                existing.typical_day = typical_day
                existing.last_seen_date = last_date
                existing.next_expected_date = next_date
                existing.occurrences = len(cluster)
                existing.is_income = is_income
        else:
            # Look up category from most recent transaction for this merchant
            recent_txn = (
                db.query(Transaction)
                .filter(Transaction.merchant_clean == merchant)
                .order_by(Transaction.date.desc())
                .first()
            )
            rec = RecurringTransaction(
                merchant_clean=merchant,
                category=recent_txn.category if recent_txn else "Uncategorized",
                amount=pattern["amount"],
                is_income=is_income,
                frequency=frequency,
                typical_day=typical_day,
                last_seen_date=last_date,
                next_expected_date=next_date,
                occurrences=len(cluster),
                status="detected",
            )
            db.add(rec)

    db.commit()
    return detected