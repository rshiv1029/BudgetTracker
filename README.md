# Configuration Setup Guide

## The Issue
Your `models.py` was importing from `app.config` which didn't exist:
```python
from app.config import get_settings
```

## The Solution
Create the `app/config.py` file with proper environment variable loading.

## Files to Update

### 1. Create `app/config.py`
Place this file in your `app/` directory. It defines a `Settings` class that loads environment variables from your `.env` file using Pydantic.

**Key features:**
- Loads Plaid API credentials from `.env`
- Loads AI configuration (Ollama vs Gemini)
- Optional database URL override (defaults to the hardcoded path in `database.py`)
- Uses `@lru_cache()` for performance

### 2. Replace `app/models.py`
The new `models.py`:
- ✅ Uses `Base` from `app.database` (not creating its own)
- ✅ Fixes the `RecurringTransaction` model with proper imports
- ✅ Uses String IDs with UUID defaults (consistent with your existing code)
- ✅ Adds all missing models (Category, BudgetRule, NetWorthSnapshot, CategoryRule)
- ✅ Removes the broken `from app.config import get_settings`

### 3. Update `.env` file
Use the provided `.env` file - it already has your Plaid credentials.

## Installation

Install the required dependency:
```bash
pip install pydantic-settings
```

## Architecture

```
app/
├── __init__.py
├── config.py          ← NEW: loads environment variables
├── database.py        ← existing: defines Base and engine
├── models.py          ← UPDATED: uses Base from database.py
├── main.py            ← existing
├── schemas.py         ← existing
└── routers/
    └── ...
```

## How It Works

1. **`.env` file** contains your configuration variables
2. **`config.py`** reads `.env` and exposes settings via `get_settings()`
3. **`main.py`** imports from `app.database` (which works fine)
4. **`models.py`** imports `Base` from `app.database` (not from config)

The old `models.py` tried to do too much:
- Creating its own engine
- Creating its own SessionLocal
- Trying to import from non-existent `config.py`

The new approach is cleaner:
- One source of truth: `app/database.py`
- Config is separate in `app/config.py`
- Models just define tables in `app/models.py`

## No Breaking Changes

Your existing code in `main.py` and routers doesn't need to change. The `init_db()` function already handles everything:

```python
# In main.py (unchanged)
from app.database import init_db
init_db()  # Creates tables and seeds categories
```

## Testing

To verify everything works:

```python
from app.config import get_settings

settings = get_settings()
print(settings.plaid_client_id)  # Should print from .env
print(settings.ollama_model)     # Should print "llama3.2"
```