"""
Plaid API client.

Environment variables (set in .env):
  PLAID_CLIENT_ID   — from dashboard.plaid.com → Team Settings → Keys
  PLAID_SECRET      — Sandbox secret (testing) or Development secret (real banks)
  PLAID_ENV         — "sandbox" or "development" (default: sandbox)

Sandbox lets you test with fake credentials instantly.
Switch to development (+ real secret) to connect real banks.
"""
import os
from datetime import date, timedelta, datetime
from typing import Optional

import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.products import Products

PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "")
PLAID_SECRET = os.getenv("PLAID_SECRET", "")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox").lower()

_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Sandbox,   # v39+ removed Development; use Sandbox for testing
    "production": plaid.Environment.Production,
}


def _client() -> plaid_api.PlaidApi:
    config = plaid.Configuration(
        host=_ENV_MAP.get(PLAID_ENV, plaid.Environment.Sandbox),
        api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
    )
    return plaid_api.PlaidApi(plaid.ApiClient(config))


def is_configured() -> bool:
    return bool(PLAID_CLIENT_ID and PLAID_SECRET)


def create_link_token(user_id: str = "local-user") -> str:
    """Create a Plaid Link token to initialise the frontend Link modal."""
    client = _client()
    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Finance App",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    resp = client.link_token_create(req)
    return resp["link_token"]


def exchange_public_token(public_token: str) -> dict:
    """Exchange the short-lived public_token from Link for a permanent access_token."""
    client = _client()
    req = ItemPublicTokenExchangeRequest(public_token=public_token)
    resp = client.item_public_token_exchange(req)
    return {"access_token": resp["access_token"], "item_id": resp["item_id"]}

def get_accounts(access_token: str) -> list[dict]:
    client = _client()
    req = AccountsGetRequest(access_token=access_token)
    resp = client.accounts_get(req)
    accounts = []
    for a in resp["accounts"]:
        accounts.append({
            "plaid_account_id": a["account_id"],
            "name": a["name"],
            "official_name": a.get("official_name"),
            "type": str(a["type"]),
            "subtype": str(a["subtype"]) if a.get("subtype") else None,
            "mask": a.get("mask"),
            "balance_current": a["balances"].get("current"),
            "balance_available": a["balances"].get("available"),
        })
    return accounts

def get_transactions(
    access_token: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    max_count: int = 500,
) -> list[dict]:
    """Fetch up to max_count transactions, paging if needed."""
    client = _client()
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    all_txns = []
    offset = 0

    while True:
        req = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(count=min(500, max_count), offset=offset),
        )
        resp = client.transactions_get(req)
        batch = resp["transactions"]
        all_txns.extend(batch)
        if len(all_txns) >= resp["total_transactions"] or not batch or len(all_txns) >= max_count:
            break
        offset += len(batch)

    result = []
    for t in all_txns:
        result.append({
            "plaid_transaction_id": t["transaction_id"],
            "plaid_account_id": t["account_id"],
            "date": t["date"],
            "description": t["name"],
            "merchant_name": t.get("merchant_name"),
            # Plaid amounts: positive = money leaving account (expense), negative = credit
            # We store as: negative = expense, positive = income — so flip sign
            "amount": -float(t["amount"]),
            "plaid_category": t.get("category", []),
            "pending": t.get("pending", False),
        })
    return result