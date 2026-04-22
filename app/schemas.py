from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ── Account ──────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str
    type: str
    institution: Optional[str] = None


class AccountOut(AccountCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Transaction ───────────────────────────────────────────────────────────────

class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    description: str
    merchant_clean: Optional[str]
    amount: float
    category: str
    subcategory: Optional[str]
    account_id: Optional[int]
    notes: Optional[str]
    is_transfer: bool
    is_excluded: bool


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    merchant_clean: Optional[str] = None
    notes: Optional[str] = None
    is_transfer: Optional[bool] = None
    is_excluded: Optional[bool] = None


# ── Import ────────────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    imported: int
    duplicates: int
    errors: int
    account_id: int


# ── Budget ────────────────────────────────────────────────────────────────────

class BudgetRuleCreate(BaseModel):
    category: str
    month_year: Optional[str] = None  # "YYYY-MM" or omit for global
    limit_amount: float
    alert_threshold: float = 0.8


class BudgetRuleOut(BudgetRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class BudgetStatus(BaseModel):
    category: str
    limit_amount: float
    actual_amount: float
    pct_used: float
    alert_threshold: float
    status: str  # "ok" | "warning" | "over"


# ── Net Worth ─────────────────────────────────────────────────────────────────

class SnapshotCreate(BaseModel):
    account_id: int
    balance: float
    snapshot_date: Optional[date] = None


class SnapshotOut(SnapshotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    snapshot_date: date


class NetWorthPoint(BaseModel):
    snapshot_date: date
    total: float


# ── Category Rule ─────────────────────────────────────────────────────────────

class CategoryRuleCreate(BaseModel):
    merchant_pattern: str
    category: str
    subcategory: Optional[str] = None
    is_regex: bool = False
    priority: int = 0


class CategoryRuleOut(CategoryRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Category ──────────────────────────────────────────────────────────────────

class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    parent_name: Optional[str]
    color: str
    icon: str


# ── Plaid ─────────────────────────────────────────────────────────────────────

class PlaidItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institution_name: Optional[str]
    institution_id: Optional[str]
    last_synced: Optional[str]


class PlaidSyncResult(BaseModel):
    institution_name: str
    imported: int
    duplicates: int
    accounts_synced: int


# ── AI ────────────────────────────────────────────────────────────────────────

class AIQueryRequest(BaseModel):
    question: str


class AIQueryResponse(BaseModel):
    answer: str
    data: Optional[dict] = None
    source: str  # "ollama" | "gemini"