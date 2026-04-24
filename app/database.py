from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

DATABASE_URL = get_settings().database_url

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    _seed_categories()


def _seed_categories():
    from app.models import Category
    db = SessionLocal()
    try:
        if db.query(Category).count() > 0:
            return
        defaults = [
            ("Food & Drink", None, "#f97316", "utensils"),
            ("Groceries", "Food & Drink", "#fb923c", "shopping-basket"),
            ("Restaurants", "Food & Drink", "#f97316", "fork-knife"),
            ("Coffee", "Food & Drink", "#92400e", "coffee"),
            ("Transportation", None, "#3b82f6", "car"),
            ("Gas", "Transportation", "#60a5fa", "fuel"),
            ("Parking", "Transportation", "#93c5fd", "parking"),
            ("Rideshare", "Transportation", "#2563eb", "taxi"),
            ("Public Transit", "Transportation", "#1d4ed8", "bus"),
            ("Shopping", None, "#8b5cf6", "shopping-bag"),
            ("Clothing", "Shopping", "#a78bfa", "shirt"),
            ("Electronics", "Shopping", "#7c3aed", "monitor"),
            ("Amazon", "Shopping", "#6d28d9", "package"),
            ("Entertainment", None, "#ec4899", "tv"),
            ("Streaming", "Entertainment", "#f472b6", "play"),
            ("Movies", "Entertainment", "#db2777", "film"),
            ("Games", "Entertainment", "#be185d", "gamepad"),
            ("Health & Fitness", None, "#10b981", "heart"),
            ("Gym", "Health & Fitness", "#34d399", "dumbbell"),
            ("Pharmacy", "Health & Fitness", "#059669", "pill"),
            ("Doctor", "Health & Fitness", "#047857", "stethoscope"),
            ("Bills & Utilities", None, "#f59e0b", "zap"),
            ("Rent", "Bills & Utilities", "#fbbf24", "home"),
            ("Electric", "Bills & Utilities", "#fcd34d", "zap"),
            ("Internet", "Bills & Utilities", "#fde68a", "wifi"),
            ("Phone", "Bills & Utilities", "#f59e0b", "smartphone"),
            ("Insurance", "Bills & Utilities", "#d97706", "shield"),
            ("Travel", None, "#06b6d4", "plane"),
            ("Hotels", "Travel", "#22d3ee", "bed"),
            ("Flights", "Travel", "#0891b2", "plane"),
            ("Income", None, "#22c55e", "dollar-sign"),
            ("Paycheck", "Income", "#4ade80", "briefcase"),
            ("Freelance", "Income", "#86efac", "laptop"),
            ("Transfer", None, "#94a3b8", "arrow-right-left"),
            ("Savings", None, "#64748b", "piggy-bank"),
            ("Investments", None, "#475569", "trending-up"),
            ("Uncategorized", None, "#9ca3af", "question"),
        ]
        for name, parent, color, icon in defaults:
            db.add(Category(name=name, parent_name=parent, color=color, icon=icon))
        db.commit()
    finally:
        db.close()