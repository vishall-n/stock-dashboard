"""
data_service.py
Handles all stock data fetching, cleaning, and metric calculations.
Uses yfinance to pull real NSE/BSE stock data.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# ── Company Registry ─────────────────────────────────────────────────────────
COMPANIES = {
    "RELIANCE": {"name": "Reliance Industries",   "sector": "Energy"},
    "TCS":      {"name": "Tata Consultancy Svc",  "sector": "IT"},
    "INFY":     {"name": "Infosys",               "sector": "IT"},
    "HDFCBANK": {"name": "HDFC Bank",             "sector": "Banking"},
    "WIPRO":    {"name": "Wipro",                 "sector": "IT"},
    "ICICIBANK":{"name": "ICICI Bank",            "sector": "Banking"},
    "SBIN":     {"name": "State Bank of India",   "sector": "Banking"},
    "BAJFINANCE":{"name": "Bajaj Finance",        "sector": "Finance"},
    "HINDUNILVR":{"name": "Hindustan Unilever",   "sector": "FMCG"},
    "ADANIENT": {"name": "Adani Enterprises",     "sector": "Conglomerate"},
}

def _nse_ticker(symbol: str) -> str:
    """Append .NS suffix for NSE listing."""
    symbol = symbol.upper().strip()
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS"


def fetch_raw(symbol: str, period: str = "1y") -> pd.DataFrame:
    """
    Download OHLCV data from Yahoo Finance for an NSE symbol.
    Returns a clean DataFrame sorted by date ascending.
    """
    ticker = _nse_ticker(symbol)
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)

    if df.empty:
        raise ValueError(f"No data found for symbol '{symbol}'. "
                         "Check that it is a valid NSE ticker.")

    # Flatten multi-index columns that yfinance sometimes returns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.reset_index()
    df.rename(columns={"Date": "date", "Open": "open", "High": "high",
                        "Low": "low", "Close": "close", "Volume": "volume"},
              inplace=True)

    # ── Data Cleaning ─────────────────────────────────────────────────────
    df["date"] = pd.to_datetime(df["date"])
    df.dropna(subset=["close"], inplace=True)          # drop rows with no close
    df.ffill(inplace=True)           # forward-fill remaining NaN
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich the DataFrame with calculated financial metrics.

    Added columns
    ─────────────
    daily_return      : (close - open) / open
    ma_7              : 7-day rolling average of close
    ma_30             : 30-day rolling average of close
    volatility_score  : 14-day rolling std of daily returns (annualised ×√252)
                        — our custom metric
    """
    df = df.copy()

    # Core metrics
    df["daily_return"] = (df["close"] - df["open"]) / df["open"]
    df["ma_7"]  = df["close"].rolling(window=7,  min_periods=1).mean()
    df["ma_30"] = df["close"].rolling(window=30, min_periods=1).mean()

    # Custom metric: Volatility Score (annualised 14-day rolling σ of returns)
    df["volatility_score"] = (
        df["daily_return"].rolling(window=14, min_periods=1).std() * np.sqrt(252)
    )

    # Round for readability
    num_cols = ["open", "high", "low", "close",
                "daily_return", "ma_7", "ma_30", "volatility_score"]
    df[num_cols] = df[num_cols].round(4)

    return df


@lru_cache(maxsize=64)
def _cached_fetch(symbol: str) -> pd.DataFrame:
    """
    LRU-cached wrapper so repeated API calls within a session reuse data.
    Cache is keyed by symbol; call _cached_fetch.cache_clear() to refresh.
    """
    df = fetch_raw(symbol, period="1y")
    return add_metrics(df)


def get_recent_data(symbol: str, days: int = 30) -> list[dict]:
    """Return the last `days` trading days for `symbol` as a list of dicts."""
    df = _cached_fetch(symbol)
    recent = df.tail(days).copy()
    recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
    # Replace NaN / Infinity with None so JSON serialization doesn't fail
    recent = recent.replace([float('inf'), float('-inf')], None)
    recent = recent.where(recent.notna(), other=None)
    return recent.to_dict(orient="records")


def get_summary(symbol: str) -> dict:
    """
    52-week high, low, average close, latest price,
    and current volatility score.
    """
    df = _cached_fetch(symbol)
    week52 = df.tail(252)  # approx 1 trading year

    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest
    change_pct = ((latest["close"] - prev["close"]) / prev["close"]) * 100

    return {
        "symbol":             symbol.upper(),
        "name":               COMPANIES.get(symbol.upper(), {}).get("name", symbol),
        "latest_close":       round(float(latest["close"]), 2),
        "change_pct":         round(float(change_pct), 2),
        "week52_high":        round(float(week52["high"].max()), 2),
        "week52_low":         round(float(week52["low"].min()), 2),
        "avg_close":          round(float(week52["close"].mean()), 2),
        "avg_volume":         int(week52["volume"].mean()),
        "volatility_score":   round(float(latest["volatility_score"]), 4),
        "as_of":              latest["date"].strftime("%Y-%m-%d"),
    }


def compare_stocks(symbol1: str, symbol2: str, days: int = 90) -> dict:
    """
    Compare two stocks over the last `days` trading days.
    Returns normalised close (base-100), returns, and correlation.
    """
    df1 = _cached_fetch(symbol1).tail(days).copy()
    df2 = _cached_fetch(symbol2).tail(days).copy()

    # Align on common dates
    df1.set_index("date", inplace=True)
    df2.set_index("date", inplace=True)
    combined = df1[["close", "daily_return"]].join(
        df2[["close", "daily_return"]], how="inner",
        lsuffix=f"_{symbol1.upper()}", rsuffix=f"_{symbol2.upper()}"
    )

    # Normalise to 100 at start
    for sym in [symbol1.upper(), symbol2.upper()]:
        col = f"close_{sym}"
        combined[f"norm_{sym}"] = (combined[col] / combined[col].iloc[0]) * 100

    correlation = combined[
        [f"daily_return_{symbol1.upper()}", f"daily_return_{symbol2.upper()}"]
    ].corr().iloc[0, 1]

    combined = combined.reset_index()
    combined["date"] = combined["date"].dt.strftime("%Y-%m-%d")

    return {
        "symbol1": symbol1.upper(),
        "symbol2": symbol2.upper(),
        "correlation": round(float(correlation), 4),
        "data": combined[[
            "date",
            f"norm_{symbol1.upper()}",
            f"norm_{symbol2.upper()}",
        ]].to_dict(orient="records"),
    }


def get_top_movers(n: int = 5) -> dict:
    """
    Returns top N gainers and losers based on yesterday's daily_return.
    """
    results = []
    for symbol in COMPANIES:
        try:
            df = _cached_fetch(symbol)
            last = df.iloc[-1]
            results.append({
                "symbol":      symbol,
                "name":        COMPANIES[symbol]["name"],
                "close":       round(float(last["close"]), 2),
                "daily_return":round(float(last["daily_return"]) * 100, 2),
            })
        except Exception as e:
            logger.warning(f"Skipping {symbol}: {e}")

    results.sort(key=lambda x: x["daily_return"], reverse=True)
    return {
        "gainers": results[:n],
        "losers":  results[-n:][::-1],
    }
