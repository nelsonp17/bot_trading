from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import sys

from app.config import BOT_TRADING_FILE

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import get_db_manager

app = FastAPI(title="Trading Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/api/status")
def get_status():
    if not os.path.exists(BOT_TRADING_FILE):
        return {
            "status": "stopped",
            "symbol": "N/A",
            "network": "N/A",
            "timeframe": "N/A",
            "budget": 0
        }

    try:
        with open(BOT_TRADING_FILE, 'r') as f:
            status_data = json.load(f)
        return status_data
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/trades")
def get_trades(limit: int = 50):
    db = get_db_manager()
    trades = db.get_last_trades(limit=limit)
    return trades


@app.get("/api/predictions")
def get_predictions(limit: int = 50):
    db = get_db_manager()
    predictions = db.get_last_predictions(limit=limit)
    return predictions


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
