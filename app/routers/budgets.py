from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BudgetRule
from app.schemas import BudgetRuleCreate, BudgetRuleOut, BudgetStatus
from app.services.budget_checker import get_budget_status

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetRuleOut])
def list_budgets(db: Session = Depends(get_db)):
    return db.query(BudgetRule).all()


@router.post("", response_model=BudgetRuleOut)
def create_budget(rule: BudgetRuleCreate, db: Session = Depends(get_db)):
    existing = db.query(BudgetRule).filter(
        BudgetRule.category == rule.category,
        BudgetRule.month_year == rule.month_year,
    ).first()
    if existing:
        raise HTTPException(409, f"Budget rule already exists for {rule.category} / {rule.month_year}")
    obj = BudgetRule(**rule.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{budget_id}", response_model=BudgetRuleOut)
def update_budget(budget_id: int, rule: BudgetRuleCreate, db: Session = Depends(get_db)):
    obj = db.query(BudgetRule).filter(BudgetRule.id == budget_id).first()
    if not obj:
        raise HTTPException(404, "Budget not found")
    for field, value in rule.model_dump().items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    obj = db.query(BudgetRule).filter(BudgetRule.id == budget_id).first()
    if not obj:
        raise HTTPException(404, "Budget not found")
    db.delete(obj)
    db.commit()


@router.get("/status", response_model=list[BudgetStatus])
def budget_status(month_year: Optional[str] = None, db: Session = Depends(get_db)):
    return get_budget_status(month_year, db)
