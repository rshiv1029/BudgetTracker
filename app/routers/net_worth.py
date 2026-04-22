from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, NetWorthSnapshot
from app.schemas import AccountCreate, AccountOut, NetWorthPoint, SnapshotCreate, SnapshotOut
from app.services.insights import net_worth_history

router = APIRouter(prefix="/api/net-worth", tags=["net-worth"])


# ── Accounts ──────────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(Account).all()


@router.post("/accounts", response_model=AccountOut)
def create_account(account: AccountCreate, db: Session = Depends(get_db)):
    obj = Account(**account.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── Snapshots ─────────────────────────────────────────────────────────────────

@router.post("/snapshot", response_model=SnapshotOut)
def add_snapshot(snap: SnapshotCreate, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == snap.account_id).first()
    if not account:
        raise HTTPException(404, "Account not found")
    obj = NetWorthSnapshot(
        account_id=snap.account_id,
        balance=snap.balance,
        snapshot_date=snap.snapshot_date or date.today(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/history", response_model=list[NetWorthPoint])
def get_history(db: Session = Depends(get_db)):
    rows = net_worth_history(db)
    return [NetWorthPoint(snapshot_date=r["date"], total=r["total"]) for r in rows]


@router.get("/latest")
def get_latest_balances(db: Session = Depends(get_db)):
    """Return the most recent balance per account."""
    accounts = db.query(Account).all()
    result = []
    for acct in accounts:
        snap = (
            db.query(NetWorthSnapshot)
            .filter(NetWorthSnapshot.account_id == acct.id)
            .order_by(NetWorthSnapshot.snapshot_date.desc())
            .first()
        )
        result.append({
            "account_id": acct.id,
            "account_name": acct.name,
            "type": acct.type,
            "institution": acct.institution,
            "balance": snap.balance if snap else None,
            "as_of": str(snap.snapshot_date) if snap else None,
        })
    total = sum(
        r["balance"] for r in result
        if r["balance"] is not None and r["balance"] > 0  # exclude credit (negative)
    )
    return {"accounts": result, "total_net_worth": round(total, 2)}

