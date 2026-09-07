# 💹 Equity Lab - SINGLE FILE EDITION

**All features in ONE file: `app.py` + `requirements.txt` + `README.md` = Full GitHub Repo**

### 🚀 Features in Single File

✅ **Live P&L** - Quantity × LTP = Current Value, Invested, P&L, Day Change  
✅ **SIP Tracker** - Parse SIP transactions, calculate XIRR (Extended IRR)  
✅ **Dividend Tracker** - Fetch dividends from NSE, total dividends received  
✅ **XIRR Calculation** - Newton-Raphson for irregular cashflows, annualized return  
✅ **P&L Alerts** - Auto alerts +10%, +20%, -5% etc  
✅ **Capital Gains** - STCG (<12m 15% tax), LTCG (≥12m 10% above ₹1L)  
✅ **Excel/CSV/PDF Upload** - Zerodha, Groww, Angel One holdings  
✅ **NSE/BSE** - Auto .NS/.BO, fast_info fix for Yahoo block  
✅ **Nifty 500** - Searchable dropdown  
✅ **PDF/Excel/WhatsApp/Hindi** - Broker reports  
✅ **Telegram Bot + 8 AM Scheduler** - GitHub Actions cron

### 📁 Only 3 Files

```
app.py - Everything (StockReportAgent + Parser + Tracker + SIP + Dividend + XIRR + Alerts + CG)
requirements.txt - Dependencies
README.md - This file
```

### 🔧 Local Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 📊 SIP File Format

CSV/Excel with columns:
```
Date, Ticker, Amount, Quantity, Price
15-01-2023, RELIANCE, 5000, 2, 2500
15-02-2023, RELIANCE, 5000, 2, 2450
```

App calculates:
- Total Invested, Total Qty, Avg Price, LTP, Current Value, P&L, P&L%, **XIRR%**

**XIRR Formula:**
```
NPV = Σ Amount / (1+r)^(days/365) = 0, solve for r via Newton-Raphson
Overall XIRR = Annualized return of all SIPs
```

### 💰 Dividend Tracker

- Fetches dividends via yfinance after Buy Date
- Calculates total dividends received per stock
- Dividend Yield on Invested

### 📈 Holdings File Format (for P&L)

Excel/CSV:
```
Instrument, Qty, Avg cost, Buy Date
RELIANCE, 10, 2500, 15-01-2023
TCS, 5, 3500, 10-10-2024
```

App auto-calculates:
- Invested = Qty × Avg
- Current = Qty × LTP (Live NSE)
- P&L = Current - Invested

### 🤖 GitHub Host (Free)

1. Push 3 files to GitHub
2. Go to share.streamlit.io → New App → Select repo → app.py → Deploy
3. Live at `https://your-app.streamlit.app`

### ⏰ Daily 8 AM Scheduler (Optional)

Create `.github/workflows/morning_reports.yml`:
```yaml
on:
  schedule:
    - cron: '30 2 * * 1-5'  # 8 AM IST
jobs:
  morning:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: python app.py  # Or scheduler logic
```

### 📦 Why Single File?

- Easy to host on GitHub (no import errors)
- Streamlit Cloud loves single file
- All classes in one place: StockReportAgent, PortfolioParser, LivePortfolioTracker, SIPTracker, DividendTracker, XIRR calculator
- Copy-paste app.py anywhere and it works

### ⚠️ Disclaimer

Not SEBI advice. Data from Yahoo Finance. XIRR, STCG/LTCG calculations approximate - consult CA.

### 🙏 Credits

Built for Indian investors - Zerodha, Groww, Angel One users
NSE/BSE, INR Cr/L, Hindi reports, WhatsApp share
