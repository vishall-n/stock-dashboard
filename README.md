# 📈 Stock Data Intelligence Dashboard

A mini financial data platform for NSE-listed Indian stocks.  
Built with **FastAPI**, **yfinance**, **Pandas**, and a vanilla-JS **Chart.js** frontend.

---

## 🗂️ Project Structure

```
stock_dashboard/
├── main.py            # FastAPI application & all REST endpoints
├── data_service.py    # Data fetching, cleaning & metric calculations
├── requirements.txt
├── README.md
└── static/
    └── index.html     # Interactive dashboard (no build step needed)
```

---

## ⚙️ Setup & Run

### 1 · Clone & install dependencies

```bash
git clone <your-repo-url>
cd stock_dashboard
pip install -r requirements.txt
```

### 2 · Start the server

```bash
uvicorn main:app --reload --port 8000
```

### 3 · Open the dashboard

Visit **http://localhost:8000** in your browser.  
Interactive API docs are at **http://localhost:8000/docs** (Swagger UI).

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/companies` | List all tracked companies |
| `GET` | `/data/{symbol}?days=30` | Last N days of OHLCV + computed metrics |
| `GET` | `/summary/{symbol}` | 52-week high/low, avg close, latest price |
| `GET` | `/compare?symbol1=INFY&symbol2=TCS&days=90` | Normalised comparison + correlation |
| `GET` | `/movers?n=5` | Top N gainers and losers for the latest day |

### Example requests

```bash
# List companies
curl http://localhost:8000/companies

# 30 days of data for Infosys
curl http://localhost:8000/data/INFY?days=30

# 52-week summary for TCS
curl http://localhost:8000/summary/TCS

# Compare Infosys vs TCS over 90 days
curl "http://localhost:8000/compare?symbol1=INFY&symbol2=TCS&days=90"
```

---

## 📊 Calculated Metrics

| Metric | Formula / Description |
|--------|-----------------------|
| `daily_return` | `(close − open) / open` |
| `ma_7` | 7-day rolling average of close |
| `ma_30` | 30-day rolling average of close |
| `volatility_score` ⭐ | 14-day rolling **annualised σ** of daily returns (`std × √252`) — custom metric indicating how "risky" the stock is on recent data |

---

## 🧩 Design Decisions

### Data source
`yfinance` is used to pull real OHLCV data from Yahoo Finance for NSE-listed tickers (`<SYMBOL>.NS`).

### Caching
Results are cached per symbol using Python's `functools.lru_cache` to avoid redundant network calls within a single server session.

### Custom metric — Volatility Score
Most dashboards show only static 52-week volatility. This project adds a **rolling 14-day annualised volatility** computed fresh on every data pull. It helps identify stocks that have recently become more or less stable — useful for short-term risk assessment.

### Correlation in /compare
The `/compare` endpoint normalises both stocks to a base of 100 so percentage moves are directly comparable, and also reports the **Pearson correlation of daily returns** — which shows whether the two stocks tend to move together.

---

## 🚀 Deployment (optional)

### Render (free tier)
1. Push the repo to GitHub.
2. Create a new **Web Service** on [Render](https://render.com).
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## ✅ Evaluation Checklist

| Category | Done |
|----------|------|
| Python & Pandas data handling | ✅ |
| Data cleaning (missing values, date parsing) | ✅ |
| Daily return, 7-day MA, 52-week high/low | ✅ |
| Custom metric (Volatility Score) | ✅ |
| REST API — /companies | ✅ |
| REST API — /data/{symbol} | ✅ |
| REST API — /summary/{symbol} | ✅ |
| REST API — /compare (bonus) | ✅ |
| Swagger / interactive API docs | ✅ |
| Frontend dashboard with Chart.js | ✅ |
| Top Gainers / Losers panel | ✅ |
| Stock comparison chart | ✅ |
| README with setup & explanations | ✅ |

---

*Built as part of the Jarnox Software Engineering Internship Assignment.*
