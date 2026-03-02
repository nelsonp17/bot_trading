from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import sys

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
