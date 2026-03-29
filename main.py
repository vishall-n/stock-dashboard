"""
main.py
FastAPI backend for the Stock Data Intelligence Dashboard.

Run with:
    uvicorn main:app --reload --port 8000

Interactive docs:
    http://localhost:8000/docs    (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import data_service as ds
import os

import json
import math
from starlette.responses import Response

def clean_json(data):
    """Recursively replace NaN/Inf with None so JSON serialization never fails."""
    if isinstance(data, list):
        return [clean_json(i) for i in data]
    if isinstance(data, dict):
        return {k: clean_json(v) for k, v in data.items()}
    if isinstance(data, float) and (math.isnan(data) or math.isinf(data)):
        return None
    return data

# ── App Setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="📈 Stock Data Intelligence Dashboard",
    description=(
        "A mini financial data platform providing NSE stock data, "
        "computed metrics, 52-week summaries, and stock comparisons."
    ),
    version="1.0.0",
    contact={"name": "Jarnox Internship Assignment"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    """Serve the frontend dashboard."""
    index = os.path.join(static_dir, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Stock API is running. Visit /docs for API reference."}


@app.get(
    "/companies",
    summary="List all available companies",
    tags=["Companies"],
    response_description="A list of companies with their ticker symbols and sectors.",
)
def get_companies():
    """
    Returns every company available in the platform with its:
    - **symbol** – NSE ticker
    - **name** – full company name
    - **sector** – business sector
    """
    return [
        {"symbol": sym, **meta}
        for sym, meta in ds.COMPANIES.items()
    ]


@app.get(
    "/data/{symbol}",
    summary="Last 30 days of OHLCV + calculated metrics",
    tags=["Stock Data"],
)
def get_stock_data(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365,
                      description="Number of trading days to return (1–365)"),
):
    try:
        data = ds.get_recent_data(symbol.upper(), days=days)
        payload = clean_json({"symbol": symbol.upper(), "days": days, "records": len(data), "data": data})
        return Response(content=json.dumps(payload), media_type="application/json")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data fetch error: {e}")


@app.get(
    "/summary/{symbol}",
    summary="52-week high, low, avg close, and more",
    tags=["Stock Data"],
)
def get_summary(symbol: str):
    """
    Returns a summary for a stock including:
    - 52-week high and low
    - Average closing price
    - Latest price and day change %
    - Volatility score (custom metric)
    """
    try:
        return ds.get_summary(symbol.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary error: {e}")


@app.get(
    "/compare",
    summary="Compare two stocks' performance",
    tags=["Comparison"],
)
def compare_stocks(
    symbol1: str = Query(..., description="First NSE ticker, e.g. INFY"),
    symbol2: str = Query(..., description="Second NSE ticker, e.g. TCS"),
    days: int   = Query(default=90, ge=7, le=365,
                        description="Lookback period in trading days"),
):
    """
    Compares two stocks over `days` trading days using:
    - **Normalised close** (rebased to 100 at the start of the period)
    - **Return correlation** between the two stocks

    Example: `/compare?symbol1=INFY&symbol2=TCS&days=90`
    """
    try:
        return ds.compare_stocks(symbol1.upper(), symbol2.upper(), days=days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison error: {e}")


@app.get(
    "/movers",
    summary="Top gainers and losers for the latest trading day",
    tags=["Market Overview"],
)
def get_movers(n: int = Query(default=5, ge=1, le=10)):
    """
    Scans all tracked companies and returns the top N gainers and losers
    ranked by daily return percentage.
    """
    try:
        return ds.get_top_movers(n=n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
