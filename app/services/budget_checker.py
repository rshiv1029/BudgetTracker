"""
Budget checker — compares actual spending vs budget limits.
"""
from datetime import date
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import BudgetRule, Transaction
from app.schemas import BudgetStatus


def get_budget_status(month_year: Optional[str], db: Session) -> list[BudgetStatus]:
    """
    Returns budget status for all rules applicable to the given month_year (YYYY-MM).
    If month_year is None, uses current month.
    """
    if month_year is None:
        today = date.today()
        month_year = today.strftime("%Y-%m")

    year, month = int(month_year[:4]), int(month_year[5:7])

    # Gather applicable rules: global rules + month-specific rules
    rules: list[BudgetRule] = db.query(BudgetRule).filter(
        (BudgetRule.month_year == None) | (BudgetRule.month_year == month_year)  # noqa: E711
    ).all()

    if not rules:
        return []

    # Merge: month-specific overrides global for same category
    rule_map: dict[str, BudgetRule] = {}
    for r in rules:
        if r.month_year is None:
            if r.category not in rule_map:
                rule_map[r.category] = r
        else:
            rule_map[r.category] = r  # specific wins

    # Sum actuals for the month (expenses are negative amounts, flip sign)
    actuals: dict[str, float] = {}
    rows = (
        db.query(Transaction.category, func.sum(Transaction.amount))
        .filter(
            func.strftime("%Y", Transaction.date) == str(year),
            func.strftime("%m", Transaction.date) == f"{month:02d}",
            Transaction.is_excluded == False,  # noqa: E712
            Transaction.is_transfer == False,  # noqa: E712
        )
        .group_by(Transaction.category)
        .all()
    )
    for category, total in rows:
        actuals[category] = abs(total) if total < 0 else 0.0  # only count expenses

    statuses = []
    for category, rule in rule_map.items():
        actual = actuals.get(category, 0.0)
        pct = actual / rule.limit_amount if rule.limit_amount > 0 else 0.0
        if pct >= 1.0:
            status = "over"
        elif pct >= rule.alert_threshold:
            status = "warning"
        else:
            status = "ok"
        statuses.append(BudgetStatus(
            category=category,
            limit_amount=rule.limit_amount,
            actual_amount=round(actual, 2),
            pct_used=round(pct, 4),
            alert_threshold=rule.alert_threshold,
            status=status,
        ))

    return sorted(statuses, key=lambda s: s.pct_used, reverse=True)