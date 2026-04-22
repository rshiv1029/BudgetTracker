"""
Cashflow forecaster.

Takes confirmed (or detected) recurring transactions and projects them
forward over the next N days, producing:
  - A daily running balance projection
  - A list of upcoming bill events
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import RecurringTransaction


FREQ_DAYS = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "annual": 365,
    "irregular": 30,  # treat as monthly for forecasting
}


def _occurrences_in_window(
    next_date: date,
    frequency: str,
    typical_day: Optional[int],
    window_start: date,
    window_end: date,
) -> list[date]:
    """
    Enumerate all projected occurrence dates for a recurring item
    that fall within [window_start, window_end].
    """
    step = typical_day or FREQ_DAYS.get(frequency, 30)
    step = max(step, 7)  # sanity floor

    dates = []
    current = next_date

    # Wind back if next_date is in the past (catch up)
    while current < window_start:
        current = current + timedelta(days=step)

    # Forward until window end
    while current <= window_end:
        if current >= window_start:
            dates.append(current)
        current = current + timedelta(days=step)

    return dates


def build_forecast(
    db: Session,
    days_forward: int = 90,
    include_detected: bool = True,
) -> dict:
    """
    Returns:
      {
        "events": [ { date, merchant, amount, is_income, category } ],
        "daily": [ { date, projected_income, projected_expenses, running_balance } ],
        "monthly_summary": [ { month, income, expenses, net } ],
        "upcoming_bills": [ ... next 10 upcoming expenses ],
      }
    """
    today = date.today()
    window_end = today + timedelta(days=days_forward)

    # Fetch recurring items
    statuses = ["confirmed"]
    if include_detected:
        statuses.append("detected")

    recurrings = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.status.in_(statuses),
        )
        .all()
    )

    # Build event list
    events: list[dict] = []

    for rec in recurrings:
        if not rec.next_expected_date:
            continue

        occurrence_dates = _occurrences_in_window(
            next_date=rec.next_expected_date,
            frequency=rec.frequency or "monthly",
            typical_day=rec.typical_day,
            window_start=today,
            window_end=window_end,
        )

        for occ_date in occurrence_dates:
            events.append({
                "date": str(occ_date),
                "merchant": rec.merchant_clean,
                "amount": rec.amount,
                "is_income": rec.is_income,
                "category": rec.category,
                "frequency": rec.frequency,
                "recurring_id": rec.id,
            })

    # Sort events chronologically
    events.sort(key=lambda e: e["date"])

    # Build daily running balance
    # Seed with $0 (relative — user can see +/- flow)
    daily_map: dict[str, dict] = {}
    current = today
    while current <= window_end:
        daily_map[str(current)] = {
            "date": str(current),
            "projected_income": 0.0,
            "projected_expenses": 0.0,
        }
        current += timedelta(days=1)

    for ev in events:
        day = daily_map.get(ev["date"])
        if not day:
            continue
        if ev["is_income"]:
            day["projected_income"] += ev["amount"]
        else:
            day["projected_expenses"] += ev["amount"]

    # Compute running balance
    running = 0.0
    daily_list = []
    for d in sorted(daily_map.keys()):
        day = daily_map[d]
        running += day["projected_income"] - day["projected_expenses"]
        daily_list.append({
            "date": d,
            "projected_income": round(day["projected_income"], 2),
            "projected_expenses": round(day["projected_expenses"], 2),
            "running_balance": round(running, 2),
        })

    # Monthly summary
    monthly: dict[str, dict] = {}
    for ev in events:
        month = ev["date"][:7]  # "YYYY-MM"
        if month not in monthly:
            monthly[month] = {"month": month, "income": 0.0, "expenses": 0.0}
        if ev["is_income"]:
            monthly[month]["income"] += ev["amount"]
        else:
            monthly[month]["expenses"] += ev["amount"]

    monthly_summary = []
    for m in sorted(monthly.keys()):
        row = monthly[m]
        monthly_summary.append({
            "month": row["month"],
            "income": round(row["income"], 2),
            "expenses": round(row["expenses"], 2),
            "net": round(row["income"] - row["expenses"], 2),
        })

    # Upcoming bills (next 10 expenses)
    upcoming_bills = [e for e in events if not e["is_income"]][:10]

    return {
        "events": events,
        "daily": daily_list,
        "monthly_summary": monthly_summary,
        "upcoming_bills": upcoming_bills,
        "generated_at": str(today),
        "days_forward": days_forward,
    }