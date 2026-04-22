"""
Natural language query router
Two-stage (1) extract intent JSON, (2) execute pre-written query functions.
"""

import json
import re
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AIQueryRequest, AIQueryResponse
from app.services import ai_client
from app.services.insights import (
    category_breakdown, monthly_income_vs_expenses,
    monthly_spending_by_category, top_merchants
)

router = APIRouter(prefix="/api/ai", tags=["ai"])

INTENT_PROMPT_TEMPLATE = """Extract structured intent from this personal finance question.

Question: {question}

Today's date: {today}

Return a JSON object with these fields (use null for unknown/not-applicable):
{{
  "operation": "spending_by_category" | "income_vs_expenses" | "top_merchants" | "category_breakdown" | "freeform",
  "category": "<category name or null>",
  "month_year": "<YYYY-MM or null>",
  "months_back": <integer 1-12 or null>,
  "limit": <integer or null>
}}

Respond with only the JSON object, no explanation."""

def _build_context_for_gemini(question: str, db: Session) -> str:
    """Build a prompt with real data context for Gemini freeform queries."""
    today = date.today()
    month_year = today.strftime("%Y-%m")
    breakdown = category_breakdown(month_year, db)
    breakdown_text = "\n".join(f"  {r['category']}: ${r['total']:.2f}" for r in breakdown[:10])
    income_data = monthly_income_vs_expenses(3, db)
    income_text = "\n".join(
        f"  {r['month']}: income=${r['income']:.2f}, expenses=${r['expenses']:.2f}, net=${r['net']:.2f}"
        for r in income_data
    )
    return f"""You are a personal finance assistant. Answer the question using the data below.

TODAY: {today}

THIS MONTH SPENDING BY CATEGORY:
{breakdown_text}

LAST 3 MONTHS INCOME VS EXPENSES:
{income_text}

QUESTION: {question}

Answer concisely in 1-3 sentences."""

@router.post("/query", response_model=AIQueryResponse)
async def ai_query(req: AIQueryRequest, db: Session = Depends(get_db)):
    today = date.today().isoformat()
    intent_prompt = INTENT_PROMPT_TEMPLATE.format(question=req.question, today=today)

    intent_text, source = await ai_client.complete(intent_prompt)

    # Strip markdown fences
    intent_text = re.sub(r"```(?:json)?", "", intent_text).strip()

    try:
        intent = json.loads(intent_text)
    except Exception:
        # Fallback: send directly to Gemini with context
        context_prompt = _build_context_for_gemini(req.question, db)
        answer, source = await ai_client.complete(context_prompt)
        return AIQueryResponse(answer=answer.strip(), source=source)

    operation = intent.get("operation", "freeform")
    category = intent.get("category")
    month_year = intent.get("month_year")
    months_back = intent.get("months_back") or 3
    limit = intent.get("limit") or 10

    data = None
    answer = ""

    if operation == "spending_by_category":
        rows = monthly_spending_by_category(months_back, db)
        if category:
            rows = [r for r in rows if r["category"].lower() == category.lower()]
        data = {"rows": rows}
        if rows:
            total = sum(r["total"] for r in rows)
            answer = f"Over the last {months_back} months, you spent ${total:.2f}" + (f" on {category}" if category else " across all categories") + "."
        else:
            answer = "No spending data found for that period."

    elif operation == "income_vs_expenses":
        rows = monthly_income_vs_expenses(months_back, db)
        data = {"rows": rows}
        if rows:
            avg_net = sum(r["net"] for r in rows) / len(rows)
            answer = f"Over the last {months_back} months, your average monthly net was ${avg_net:+.2f}."
        else:
            answer = "No income/expense data found."

    elif operation == "top_merchants":
        rows = top_merchants(month_year, limit, db)
        data = {"rows": rows}
        if rows:
            top = rows[0]
            answer = f"Your top merchant is {top['merchant']} (${top['total']:.2f})."
        else:
            answer = "No merchant data found."

    elif operation == "category_breakdown":
        rows = category_breakdown(month_year, db)
        data = {"rows": rows}
        if rows:
            top = rows[0]
            answer = f"Your biggest spending category is {top['category']} (${top['total']:.2f})."
        else:
            answer = "No category data found."

    else:
        # Freeform — use context + AI
        context_prompt = _build_context_for_gemini(req.question, db)
        answer, source = await ai_client.complete(context_prompt)
        answer = answer.strip()

    return AIQueryResponse(answer=answer, data=data, source=source)

@router.get("/insights")
def get_insights(months: int = 3, db: Session = Depends(get_db)):
    """Quick aggregated insights for the dashboard."""
    today = date.today()
    month_year = today.strftime("%Y-%m")
    return {
        "category_breakdown": category_breakdown(month_year, db),
        "income_vs_expenses": monthly_income_vs_expenses(months, db),
        "top_merchants": top_merchants(month_year, 5, db),
    }