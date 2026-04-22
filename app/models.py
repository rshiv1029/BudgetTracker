from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Text, Integer, func, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class PlaidItem(Base):
    __tablename__ = "plaid_items"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id = Column(String)
    institution_name = Column(String)
    access_token = Column(String, unique=True)
    item_id = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_synced = Column(DateTime, nullable=True)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plaid_item_id = Column(String)
    plaid_account_id = Column(String, unique=True)
    name = Column(String)
    official_name = Column(String, nullable=True)
    type = Column(String)       # depository, credit, investment, loan
    subtype = Column(String, nullable=True)
    current_balance = Column(Float, default=0.0)
    available_balance = Column(Float, nullable=True)
    currency = Column(String, default="USD")
    institution_name = Column(String, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plaid_transaction_id = Column(String, unique=True, nullable=True)
    account_id = Column(String)
    name = Column(String)
    merchant_name = Column(String, nullable=True)
    amount = Column(Float)          # positive = debit (money out), negative = credit (money in)
    date = Column(String)           # YYYY-MM-DD
    category = Column(String, nullable=True)
    category_detailed = Column(String, nullable=True)
    pending = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def create_tables():
    Base.metadata.create_all(bind=engine)


class RecurringTransaction(Base):
    """
    A detected recurring bill or subscription.
    One row per unique merchant+amount pattern.
    """
    __tablename__ = "recurring_transactions"

    id = Column(Integer, primary_key=True, index=True)

    merchant_clean = Column(String, nullable=False, unique=True)
    category = Column(String, default="Uncategorized")

    amount = Column(Float, nullable=False)
    is_income = Column(Boolean, default=False)

    # "monthly" | "weekly" | "biweekly" | "annual" | "irregular"
    frequency = Column(String, default="monthly")

    typical_day = Column(Integer)

    # "detected" | "confirmed" | "dismissed"
    status = Column(String, default="detected")

    last_seen_date = Column(Date)
    next_expected_date = Column(Date)
    occurrences = Column(Integer, default=0)
    notes = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())