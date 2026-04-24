"""
Plaid router — handles Link flow and transaction sync.

Endpoints:
  GET  /api/plaid/status            — are keys configured?
  POST /api/plaid/link-token        — create Link token for frontend
  POST /api/plaid/exchange-token    — exchange public_token → store access_token
  POST /api/plaid/sync/{item_id}    — pull latest transactions for one institution
  POST /api/plaid/sync-all          — sync all connected institutions
  GET  /api/plaid/items             — list connected institutions
  DELETE /api/plaid/items/{item_id} — disconnect an institution
"""
import asyncio
import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, NetWorthSnapshot, PlaidAccount, PlaidItem, Transaction
from app.schemas import PlaidItemOut, PlaidSyncResult
from app.services import plaid_client as pc
from app.services.categorizer import categorize_transactions

router = APIRouter(prefix="/api/plaid", tags=["plaid"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_hash(txn_date: date, description: str, amount: float, account_id: int) -> str:
    raw = f"{txn_date}|{description.strip().lower()}|{amount:.2f}|{account_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _map_account_type(plaid_type: str, plaid_subtype: Optional[str]) -> str:
    t = plaid_type.lower()
    s = (plaid_subtype or "").lower()
    if t == "credit":
        return "credit"
    if t == "investment" or t == "brokerage":
        return "investment"
    if "saving" in s:
        return "savings"
    return "checking"

# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
def plaid_status():
    return {
        "configured": pc.is_configured(),
        "env": pc.PLAID_ENV,
        "message": "Ready" if pc.is_configured() else "Set PLAID_CLIENT_ID and PLAID_SECRET in .env",
    }


@router.post("/link-token")
def create_link_token():
    if not pc.is_configured():
        raise HTTPException(503, "Plaid credentials not configured — add PLAID_CLIENT_ID and PLAID_SECRET to .env")
    try:
        token = pc.create_link_token()
        return {"link_token": token}
    except Exception as e:
        raise HTTPException(502, f"Plaid error: {e}")

@router.post("/exchange-token", response_model=PlaidSyncResult)
async def exchange_token(
    body: dict,
    db: Session = Depends(get_db),
):
    """
    Called after user completes Plaid Link.
    body: { public_token, institution_name, institution_id }
    """
    public_token = body.get("public_token")
    institution_name = body.get("institution_name", "Unknown Bank")
    institution_id = body.get("institution_id", "")

    if not public_token:
        raise HTTPException(400, "public_token required")

    try:
        exchanged = pc.exchange_public_token(public_token)
    except Exception as e:
        raise HTTPException(502, f"Plaid token exchange failed: {e}")

    access_token = exchanged["access_token"]
    item_id = exchanged["item_id"]

    # Store the item
    existing = db.query(PlaidItem).filter(PlaidItem.item_id == item_id).first()
    if existing:
        existing.access_token = access_token
        existing.institution_name = institution_name
        item = existing
    else:
        item = PlaidItem(
            item_id=item_id,
            access_token=access_token,
            institution_id=institution_id,
            institution_name=institution_name,
        )
        db.add(item)
        db.flush()

    # Sync accounts + 30 days of transactions immediately
    result = await _sync_item(item, db, days_back=30)
    db.commit()
    return result


@router.post("/sync/{item_id}", response_model=PlaidSyncResult)
async def sync_item(item_id: str, days_back: int = 90, db: Session = Depends(get_db)):
    item = db.query(PlaidItem).filter(PlaidItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    result = await _sync_item(item, db, days_back=days_back)
    db.commit()
    return result

@router.post("/sync-all")
async def sync_all(days_back: int = 7, db: Session = Depends(get_db)):
    items = db.query(PlaidItem).all()
    if not items:
        return {"synced": 0, "results": []}
    results = []
    for item in items:
        try:
            r = await _sync_item(item, db, days_back=days_back)
            results.append(r)
        except Exception as e:
            results.append({"institution_name": item.institution_name, "error": str(e)})
    db.commit()
    return {"synced": len(items), "results": results}


@router.get("/items", response_model=list[PlaidItemOut])
def list_items(db: Session = Depends(get_db)):
    items = db.query(PlaidItem).all()
    out = []
    for item in items:
        out.append(PlaidItemOut(
            id=item.id,
            institution_name=item.institution_name,
            institution_id=item.institution_id,
            last_synced=item.last_synced.isoformat() if item.last_synced else None,
        ))
    return out


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(PlaidItem).filter(PlaidItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    db.query(PlaidAccount).filter(PlaidAccount.plaid_item_id == item.id).delete()
    db.delete(item)
    db.commit()

# ── core sync logic ───────────────────────────────────────────────────────────

async def _sync_item(item: PlaidItem, db: Session, days_back: int = 90) -> PlaidSyncResult:
    # ── 1. Sync accounts ──────────────────────────────────────────────────────
    plaid_accounts_raw = pc.get_accounts(item.access_token)
    account_id_map: dict[str, int] = {}

    for pa in plaid_accounts_raw:
        existing_pa = db.query(PlaidAccount).filter(
            PlaidAccount.plaid_account_id == pa["plaid_account_id"]
        ).first()

        if existing_pa:
            local_acct = db.query(Account).filter(Account.id == existing_pa.account_id).first()
        else:
            acct_name = f"{item.institution_name} — {pa['name']}"
            existing_acct = db.query(Account).filter(Account.name == acct_name).first()
            if existing_acct:
                local_acct = existing_acct
            else:
                local_acct = Account(
                    name=acct_name,
                    type=_map_account_type(pa["type"], pa["subtype"]),
                    institution=item.institution_name,
                )
                db.add(local_acct)
                db.flush()

            link = PlaidAccount(
                plaid_item_id=item.id,
                account_id=local_acct.id,
                plaid_account_id=pa["plaid_account_id"],
                mask=pa.get("mask"),
                subtype=pa.get("subtype"),
            )
            db.add(link)
            db.flush()

        account_id_map[pa["plaid_account_id"]] = local_acct.id

        balance = pa.get("balance_current")
        if balance is not None:
            today = date.today()
            existing_snap = db.query(NetWorthSnapshot).filter(
                NetWorthSnapshot.account_id == local_acct.id,
                NetWorthSnapshot.snapshot_date == today,
            ).first()
            if existing_snap:
                existing_snap.balance = balance
            else:
                snap = NetWorthSnapshot(
                    account_id=local_acct.id,
                    balance=balance,
                    snapshot_date=date.today(),
                )
                db.add(snap)

    # ── 2. Sync transactions (with retry for PRODUCT_NOT_READY) ──────────────
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    raw_txns = []
    for attempt in range(5):
        try:
            raw_txns = pc.get_transactions(item.access_token, start_date=start_date, end_date=end_date)
            break
        except Exception as e:
            if "PRODUCT_NOT_READY" in str(e) and attempt < 4:
                wait = (attempt + 1) * 3  # 3s, 6s, 9s, 12s
                await asyncio.sleep(wait)
                continue
            raise

    # ── 3. Import transactions ────────────────────────────────────────────────
    imported = 0
    duplicates = 0
    new_ids = []

    for t in raw_txns:
        if t["pending"]:
            continue

        local_account_id = account_id_map.get(t["plaid_account_id"])
        if not local_account_id:
            continue

        import_hash = _make_hash(t["date"], t["description"], t["amount"], local_account_id)

        if db.query(Transaction).filter(Transaction.import_hash == import_hash).first():
            duplicates += 1
            continue

        merchant = t.get("merchant_name") or t["description"]
        # Detect transfers via Plaid's category hint
        plaid_cats = t.get("plaid_category") or []
        is_transfer = any(
            c.lower() in ("transfer", "payment", "deposit", "internal account transfer")
            for c in plaid_cats
        )

        txn = Transaction(
            import_hash=import_hash,
            date=t["date"],
            description=t["description"],
            merchant_clean=merchant,
            amount=t["amount"],
            category="Transfer" if is_transfer else "Uncategorized",
            account_id=local_account_id,
            is_transfer=is_transfer,
            is_excluded=False,
        )
        db.add(txn)
        db.flush()
        new_ids.append(txn.id)
        imported += 1

    # ── 4. AI categorization ──────────────────────────────────────────────────
    if new_ids:
        await categorize_transactions(new_ids, db)

    item.last_synced = datetime.now(timezone.utc)

    return PlaidSyncResult(
        institution_name=item.institution_name or "Unknown",
        imported=imported,
        duplicates=duplicates,
        accounts_synced=len(plaid_accounts_raw),
    )