from datetime import date, datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)  # checking/savings/credit/investment
    institution = Column(String)
    created_at = Column(DateTime, default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    import_hash = Column(String, unique=True, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    description = Column(String, nullable=False)
    merchant_clean = Column(String)
    amount = Column(Float, nullable=False)
    category = Column(String, default="Uncategorized", index=True)
    subcategory = Column(String)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    notes = Column(Text)
    is_transfer = Column(Boolean, default=False)
    is_excluded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())


class BudgetRule(Base):
    __tablename__ = "budget_rules"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False, index=True)
    month_year = Column(String)  # "YYYY-MM" or NULL for all months
    limit_amount = Column(Float, nullable=False)
    alert_threshold = Column(Float, default=0.8)

    __table_args__ = (
        UniqueConstraint("category", "month_year", name="uq_budget_category_month"),
    )


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(Date, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    balance = Column(Float, nullable=False)
    created_at = Column(DateTime, default=func.now())


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True, index=True)
    merchant_pattern = Column(String, nullable=False)
    category = Column(String, nullable=False)
    subcategory = Column(String)
    is_regex = Column(Boolean, default=False)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    parent_name = Column(String, ForeignKey("categories.name"))
    color = Column(String, default="#9ca3af")
    icon = Column(String, default="tag")


class PlaidItem(Base):
    """One row per connected institution (bank login)."""
    __tablename__ = "plaid_items"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String, nullable=False, unique=True)      # Plaid item_id
    access_token = Column(String, nullable=False)              # never expose to frontend
    institution_id = Column(String)
    institution_name = Column(String)
    last_synced = Column(DateTime)
    created_at = Column(DateTime, default=func.now())


class PlaidAccount(Base):
    """One row per account within a PlaidItem."""
    __tablename__ = "plaid_accounts"

    id = Column(Integer, primary_key=True, index=True)
    plaid_item_id = Column(Integer, ForeignKey("plaid_items.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    plaid_account_id = Column(String, nullable=False, unique=True)  # Plaid's account_id
    mask = Column(String)       # last 4 digits
    subtype = Column(String)    # checking / savings / credit card / etc.
