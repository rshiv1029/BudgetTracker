"""
SQL aggregation queries for charts and insights.
"""
from datetime import date
from typing import Optional
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models import NetWorthSnapshot, Transaction


def monthly_spending_by_category(months: int, db: Session) -> list[dict]:
    """Returns monthly spending per category for the last N months."""
    rows = db.execute(text("""
        SELECT
            strftime('%Y-%m', date) AS month,
            category,
            ABS(SUM(amount)) AS total
        FROM transactions
        WHERE amount < 0
          AND is_excluded = 0
          AND is_transfer = 0
          AND date >= date('now', :offset)
        GROUP BY month, category
        ORDER BY month ASC, total DESC
    """), {"offset": f"-{months} months"}).fetchall()
    return [{"month": r[0], "category": r[1], "total": round(r[2], 2)} for r in rows]


def monthly_income_vs_expenses(months: int, db: Session) -> list[dict]:
    rows = db.execute(text("""
        SELECT
            strftime('%Y-%m', date) AS month,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income,
            ABS(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END)) AS expenses
        FROM transactions
        WHERE is_excluded = 0
          AND is_transfer = 0
          AND date >= date('now', :offset)
        GROUP BY month
        ORDER BY month ASC
    """), {"offset": f"-{months} months"}).fetchall()
    return [
        {"month": r[0], "income": round(r[1], 2), "expenses": round(r[2], 2), "net": round(r[1] - r[2], 2)}
        for r in rows
    ]


def top_merchants(month_year: Optional[str], limit: int, db: Session) -> list[dict]:
    params: dict = {"limit": limit}
    date_filter = ""
    if month_year:
        year, month = month_year[:4], month_year[5:7]
        date_filter = "AND strftime('%Y', date) = :year AND strftime('%m', date) = :month"
        params["year"] = year
        params["month"] = month
    rows = db.execute(text(f"""
        SELECT merchant_clean, category, ABS(SUM(amount)) AS total, COUNT(*) AS txn_count
        FROM transactions
        WHERE amount < 0 AND is_excluded = 0 AND is_transfer = 0
        {date_filter}
        GROUP BY merchant_clean, category
        ORDER BY total DESC
        LIMIT :limit
    """), params).fetchall()
    return [{"merchant": r[0], "category": r[1], "total": round(r[2], 2), "count": r[3]} for r in rows]

def net_worth_history(db: Session) -> list[dict]:
    rows = db.execute(text("""
        SELECT snapshot_date, SUM(balance) AS total
        FROM net_worth_snapshots
        GROUP BY snapshot_date
        ORDER BY snapshot_date ASC
    """)).fetchall()
    return [{"date": str(r[0]), "total": round(r[1], 2)} for r in rows]


def category_breakdown(month_year: Optional[str], db: Session) -> list[dict]:
    params: dict = {}
    date_filter = ""
    if month_year:
        year, month = month_year[:4], month_year[5:7]
        date_filter = "AND strftime('%Y', date) = :year AND strftime('%m', date) = :month"
        params["year"] = year
        params["month"] = month
    rows = db.execute(text(f"""
        SELECT category, ABS(SUM(amount)) AS total
        FROM transactions
        WHERE amount < 0 AND is_excluded = 0 AND is_transfer = 0
        {date_filter}
        GROUP BY category
        ORDER BY total DESC
    """), params).fetchall()
    return [{"category": r[0], "total": round(r[1], 2)} for r in rows]