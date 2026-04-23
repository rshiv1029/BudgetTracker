from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.transfer_detector import detect_and_flag_transfers
from app.models import Category, CategoryRule, Transaction
from app.schemas import (
    CategoryOut, CategoryRuleCreate, CategoryRuleOut,
    ImportResult, TransactionOut, TransactionUpdate,
)
from app.services import csv_importer
from app.services.categorizer import categorize_transactions

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    limit: int = 200,
    offset: int = 0,
    category: Optional[str] = None,
    account_id: Optional[int] = None,
    month_year: Optional[str] = None,  # "YYYY-MM"
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)
    if category:
        q = q.filter(Transaction.category == category)
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if month_year:
        year, month = month_year[:4], month_year[5:7]
        from sqlalchemy import func
        q = q.filter(
            func.strftime("%Y", Transaction.date) == year,
            func.strftime("%m", Transaction.date) == month,
        )
    if search:
        q = q.filter(Transaction.description.ilike(f"%{search}%"))
    q = q.filter(Transaction.is_excluded == False)  # noqa: E712
    q = q.order_by(Transaction.date.desc())
    return q.offset(offset).limit(limit).all()


@router.patch("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, update: TransactionUpdate, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    return txn


@router.post("/import", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(...),
    account_name: str = Form(...),
    account_type: str = Form("checking"),
    institution: str = Form(""),
    bank_profile: str = Form("sofi"),
    run_ai: bool = Form(True),
    db: Session = Depends(get_db),
):
    content = await file.read()
    result = csv_importer.import_csv(
        file_bytes=content,
        account_name=account_name,
        account_type=account_type,
        institution=institution,
        bank_profile=bank_profile,
        db=db,
    )

    if run_ai and result["imported"] > 0:
        # Get IDs of newly imported transactions that are Uncategorized
        from app.models import Transaction as T
        new_txns = (
            db.query(T)
            .filter(T.account_id == result["account_id"], T.category == "Uncategorized")
            .order_by(T.id.desc())
            .limit(result["imported"] + 10)
            .all()
        )
        ids = [t.id for t in new_txns]
        if ids:
            await categorize_transactions(ids, db)

    return ImportResult(**result)


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()


# ── Category Rules ────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[CategoryRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(CategoryRule).order_by(CategoryRule.priority.desc()).all()


@router.post("/rules", response_model=CategoryRuleOut)
def create_rule(rule: CategoryRuleCreate, db: Session = Depends(get_db)):
    obj = CategoryRule(**rule.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    obj = db.query(CategoryRule).filter(CategoryRule.id == rule_id).first()
    if not obj:
        raise HTTPException(404, "Rule not found")
    db.delete(obj)
    db.commit()

# ── Internal Transfer Detection ─────────────────────────────────────────────
@router.post("/detect-transfers")
def detect_transfers(db: Session = Depends(get_db)):
    flagged = detect_and_flag_transfers(db)
    return {"flagged": flagged, "message": f"Flagged {flagged} transactions as transfers"}

@router.get("/debug-transfers")
def debug_transfers(db: Session = Depends(get_db)):
    from app.models import Transaction
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.is_excluded == False,
            Transaction.is_transfer == False,
        )
        .order_by(Transaction.date.asc())
        .all()
    )
    return [
        {
            "id": t.id,
            "date": str(t.date),
            "description": t.description,
            "amount": t.amount,
            "account_id": t.account_id,
        }
        for t in txns
    ]