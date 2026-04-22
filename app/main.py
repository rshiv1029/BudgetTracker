import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from app.database import init_db
from app.routers import transactions, budgets, net_worth, ai, plaid, recurring

app = FastAPI(title="Finance App", version="1.0.0")

# Register routers
app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(net_worth.router)
app.include_router(ai.router)
app.include_router(plaid.router)
app.include_router(recurring.router)

# Static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def startup():
    os.makedirs("data", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    init_db()


@app.get("/")
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/health")
def health():
    return {"status": "ok"}