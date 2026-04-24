"""
Detects internal transfers by matching transaction pairs:
same absolute amount, opposite sign, within 3 days, different accounts.
"""
from datetime import timedelta
from sqlalchemy.orm import Session
from app.models import Transaction


def detect_and_flag_transfers(db: Session) -> int:
    """
    Scans all non-excluded transactions and flags matched pairs as is_transfer=True.
    Returns count of transactions flagged.
    """
    # Pull all unflagged, non-excluded transactions ordered by date
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.is_excluded == False,
            Transaction.is_transfer == False,
        )
        .order_by(Transaction.date.asc())
        .all()
    )

    flagged = 0
    used_ids = set()

    for i, t1 in enumerate(txns):
        if t1.id in used_ids:
            continue

        for t2 in txns[i + 1:]:
            if t2.id in used_ids:
                continue

            # Must be within 3 days
            if (t2.date - t1.date).days > 3:
                break

            # Must be opposite signs and same absolute amount (within $0.01)
            if abs(abs(t1.amount) - abs(t2.amount)) > 0.01:
                continue
            if (t1.amount > 0) == (t2.amount > 0):
                continue

            # Must be different accounts (or same account for credit card payments)
            if t1.account_id == t2.account_id:
                continue
            # Flag both as transfers
            t1.is_transfer = True
            t2.is_transfer = True
            t1.category = "Transfer"
            t2.category = "Transfer"
            used_ids.add(t1.id)
            used_ids.add(t2.id)
            flagged += 2
            break

    db.commit()
    return flagged