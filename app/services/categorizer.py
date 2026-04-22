"""
Batch AI categorization for imported transactions.
"""
import json
import re
from typing import Optional
from sqlalchemy.orm import Session

from app.models import Category, CategoryRule, Transaction
from app.services import ai_client


def _build_category_list(db: Session) -> list[str]:
    return [c.name for c in db.query(Category).all()]


def _match_category_rules(description: str, db: Session) -> Optional[tuple[str, Optional[str]]]:
    """Try to match description against manual category_rules. Returns (category, subcategory) or None."""
    rules = (
        db.query(CategoryRule)
        .order_by(CategoryRule.priority.desc())
        .all()
    )
    desc_lower = description.lower()
    for rule in rules:
        try:
            if rule.is_regex:
                if re.search(rule.merchant_pattern, description, re.IGNORECASE):
                    return rule.category, rule.subcategory
            else:
                if rule.merchant_pattern.lower() in desc_lower:
                    return rule.category, rule.subcategory
        except re.error:
            continue
    return None


def _build_prompt(transactions: list[dict], categories: list[str]) -> str:
    categories_str = "\n".join(f"- {c}" for c in categories)
    txn_lines = "\n".join(
        f'{i+1}. description="{t["description"]}" amount={t["amount"]:.2f}'
        for i, t in enumerate(transactions)
    )
    return f"""You are a personal finance categorizer. Assign each transaction to exactly one category from the list below.

VALID CATEGORIES:
{categories_str}

TRANSACTIONS:
{txn_lines}

Respond with a JSON array only — no explanation, no markdown. The array must have one object per transaction with fields "index" (1-based) and "category". Example:
[{{"index": 1, "category": "Groceries"}}, {{"index": 2, "category": "Income"}}]"""


def _parse_ai_response(response: str, count: int) -> dict[int, str]:
    """Parse AI JSON array into index->category map."""
    # Strip markdown code fences if present
    response = re.sub(r"```(?:json)?", "", response).strip()
    try:
        items = json.loads(response)
        return {item["index"]: item["category"] for item in items if "index" in item and "category" in item}
    except Exception:
        return {}

async def categorize_transactions(transaction_ids: list[int], db: Session) -> int:
    """Run AI categorization on a list of transaction IDs. Returns count updated."""
    categories = _build_category_list(db)
    category_set = set(categories)
    transactions = db.query(Transaction).filter(Transaction.id.in_(transaction_ids)).all()

    # First pass: apply category_rules
    remaining = []
    for txn in transactions:
        match = _match_category_rules(txn.description, db)
        if match:
            txn.category, txn.subcategory = match
        else:
            remaining.append(txn)

    # Second pass: AI in batches of 25
    batch_size = 25
    updated = len(transactions) - len(remaining)

    for i in range(0, len(remaining), batch_size):
        batch = remaining[i : i + batch_size]
        txn_dicts = [{"description": t.description, "amount": t.amount} for t in batch]
        prompt = _build_prompt(txn_dicts, categories)

        try:
            response_text, _ = await ai_client.complete(prompt)
            index_map = _parse_ai_response(response_text, len(batch))
        except Exception:
            index_map = {}

        for j, txn in enumerate(batch):
            ai_category = index_map.get(j + 1)
            if ai_category and ai_category in category_set:
                txn.category = ai_category
            else:
                txn.category = "Uncategorized"
            updated += 1

    db.commit()
    return updated