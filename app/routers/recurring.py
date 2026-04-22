"""
Recurring transactions + cashflow forecast router.

Endpoints:
  POST /api/recurring/detect          — scan transactions, populate recurring table
  GET  /api/recurring                 — list all recurring items
  PATCH /api/recurring/{id}           — confirm / dismiss / edit
  DELETE /api/recurring/{id}          — remove a recurring item
  GET  /api/recurring/forecast        — cashflow projection
  GET  /api/recurring/upcoming        — next N bills due soon
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RecurringTransaction
from app.services.recurring_detector import detect_recurring
from app.services.forecaster import build_forecast

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RecurringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_clean: str
    category: str
    amount: float
    is_income: bool
    frequency: str
    typical_day: Optional[int]
    status: str
    last_seen_date: Optional[date]
    next_expected_date: Optional[date]
    occurrences: int
    notes: Optional[str]


class RecurringUpdate(BaseModel):
    status: Optional[str] = None          # "confirmed" | "dismissed"
    category: Optional[str] = None
    amount: Optional[float] = None
    frequency: Optional[str] = None
    notes: Optional[str] = None
    next_expected_date: Optional[date] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/detect")
def run_detection(db: Session = Depends(get_db)):
    """
    Scan all transactions for recurring patterns.
    Safe to call repeatedly — upserts only.
    """
    detected = detect_recurring(db)
    return {
        "detected": len(detected),
        "message": f"Found {len(detected)} recurring patterns",
    }


@router.get("", response_model=list[RecurringOut])
def list_recurring(
    status: Optional[str] = None,
    include_dismissed: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(RecurringTransaction)
    if not include_dismissed:
        q = q.filter(RecurringTransaction.status != "dismissed")
    if status:
        q = q.filter(RecurringTransaction.status == status)
    return q.order_by(RecurringTransaction.is_income.asc(), RecurringTransaction.amount.desc()).all()


@router.patch("/{rec_id}", response_model=RecurringOut)
def update_recurring(rec_id: int, update: RecurringUpdate, db: Session = Depends(get_db)):
    rec = db.query(RecurringTransaction).filter(RecurringTransaction.id == rec_id).first()
    if not rec:
        raise HTTPException(404, "Recurring item not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(rec, field, value)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/{rec_id}", status_code=204)
def delete_recurring(rec_id: int, db: Session = Depends(get_db)):
    rec = db.query(RecurringTransaction).filter(RecurringTransaction.id == rec_id).first()
    if not rec:
        raise HTTPException(404, "Recurring item not found")
    db.delete(rec)
    db.commit()


@router.get("/forecast")
def get_forecast(
    days: int = 90,
    include_detected: bool = True,
    db: Session = Depends(get_db),
):
    """
    Project recurring transactions forward N days.
    Returns daily running balance + event list + monthly summary.
    """
    return build_forecast(db, days_forward=days, include_detected=include_detected)


@router.get("/upcoming")
def get_upcoming(limit: int = 10, db: Session = Depends(get_db)):
    """Quick list of soonest upcoming bills."""
    forecast = build_forecast(db, days_forward=60, include_detected=True)
    bills = [e for e in forecast["events"] if not e["is_income"]]
    return {"upcoming": bills[:limit]}