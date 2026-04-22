"""
CSV importer with bank profile support.
Currently pre-built: SoFi
"""
import hashlib
import io
from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Account, Transaction


# ── Bank Profiles ─────────────────────────────────────────────────────────────

BANK_PROFILES = {
    "sofi": {
        "date_col": "Date",
        "description_col": "Description",
        "amount_col": "Amount",
        "date_format": "%Y-%m-%d",
        # Positive amount = credit/income, negative = expense
        "amount_sign": 1,
        # Optional: filter rows by column value
        "filter_col": "Status",
        "filter_value": "cleared",
        # Optional columns (None if not present)
        "category_col": "Category",
    },
    "generic": {
        "date_col": "Date",
        "description_col": "Description",
        "amount_col": "Amount",
        "date_format": "%Y-%m-%d",
        "amount_sign": 1,
        "filter_col": None,
        "filter_value": None,
        "category_col": None,
    },
}


def _make_hash(row_date: date, description: str, amount: float, account_id: int) -> str:
    raw = f"{row_date}|{description.strip().lower()}|{amount:.2f}|{account_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _clean_merchant(description: str) -> str:
    """Basic merchant name cleanup — strip trailing digits/codes."""
    import re
    name = re.sub(r"\s+\d{4,}.*$", "", description)
    name = re.sub(r"\s{2,}", " ", name)
    return name.strip().title()

def import_csv(
    file_bytes: bytes,
    account_name: str,
    account_type: str,
    institution: str,
    bank_profile: str,
    db: Session,
) -> dict:
    profile = BANK_PROFILES.get(bank_profile.lower(), BANK_PROFILES["generic"])

    # Get or create account
    account = db.query(Account).filter(Account.name == account_name).first()
    if not account:
        account = Account(name=account_name, type=account_type, institution=institution)
        db.add(account)
        db.flush()  # get the id

    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        return {"imported": 0, "duplicates": 0, "errors": 1, "account_id": account.id, "error_msg": str(e)}

    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Filter rows
    if profile["filter_col"] and profile["filter_col"] in df.columns:
        df = df[df[profile["filter_col"]].str.lower() == profile["filter_value"].lower()]

    imported = 0
    duplicates = 0
    errors = 0

    for _, row in df.iterrows():
        try:
            raw_date = str(row[profile["date_col"]]).strip()
            parsed_date = pd.to_datetime(raw_date, format=profile["date_format"]).date()

            raw_amount = float(str(row[profile["amount_col"]]).replace(",", "").replace("$", ""))
            amount = raw_amount * profile["amount_sign"]

            description = str(row[profile["description_col"]]).strip()
            merchant_clean = _clean_merchant(description)

            import_hash = _make_hash(parsed_date, description, amount, account.id)

            # Dedup check
            existing = db.query(Transaction).filter(Transaction.import_hash == import_hash).first()
            if existing:
                duplicates += 1
                continue

            # Category hint from CSV (will be overridden by AI later)
            csv_category: Optional[str] = None
            if profile["category_col"] and profile["category_col"] in df.columns:
                csv_category = str(row[profile["category_col"]]).strip() or None

            txn = Transaction(
                import_hash=import_hash,
                date=parsed_date,
                description=description,
                merchant_clean=merchant_clean,
                amount=amount,
                category=csv_category or "Uncategorized",
                account_id=account.id,
                is_transfer=False,
                is_excluded=False,
            )
            db.add(txn)
            imported += 1
        except Exception:
            errors += 1
            continue

    db.commit()
    return {"imported": imported, "duplicates": duplicates, "errors": errors, "account_id": account.id}
