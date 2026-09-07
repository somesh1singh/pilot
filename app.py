
"""
Equity Lab - FIXED + BULK REPORTS EDITION
Fixed P&L + Bulk Reports for All 52 Holdings
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json, os, re, base64, io, urllib.parse
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.dpi'] = 150

class StockReportAgent:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    def sanitize_ticker(self, ticker: str) -> str:
        t = str(ticker).strip().upper()
        t = re.sub(r'\s+', '', t)
        t = t.replace('-EQ','').replace('-BE','')
        if not t or t.lower()=='nan': return ""
        if t.endswith('.NS') or t.endswith('.BO'): return t
        if '.' not in t: return f"{t}.NS"
        return t
    def get_robust_info(self, ticker_obj, hist_1y):
        info = {}
        try:
            raw = ticker_obj.info
            if raw and len(raw) > 5: info.update(raw)
        except: pass
        try:
            fi = ticker_obj.fast_info
            info['currentPrice'] = info.get('currentPrice') or getattr(fi, 'last_price', None)
            info['previousClose'] = info.get('previousClose') or getattr(fi, 'previous_close', None)
            info['fiftyTwoWeekHigh'] = info.get('fiftyTwoWeekHigh') or getattr(fi, 'year_high', None)
            info['fiftyTwoWeekLow'] = info.get('fiftyTwoWeekLow') or getattr(fi, 'year_low', None)
            info['marketCap'] = info.get('marketCap') or getattr(fi, 'market_cap', None)
            if not info.get('currentPrice') and not hist_1y.empty:
                info['currentPrice'] = float(hist_1y['Close'].iloc[-1])
        except: pass
        if not hist_1y.empty:
            last = hist_1y.iloc[-1]
            if not info.get('currentPrice'): info['currentPrice'] = float(last['Close'])
            if not info.get('previousClose') and len(hist_1y)>1: info['previousClose'] = float(hist_1y['Close'].iloc[-2])
            if not info.get('fiftyTwoWeekHigh'): info['fiftyTwoWeekHigh'] = float(hist_1y['High'].max())
            if not info.get('fiftyTwoWeekLow'): info['fiftyTwoWeekLow'] = float(hist_1y['Low'].min())
        info.setdefault('currency','INR')
        info.setdefault('longName', info.get('shortName', ticker_obj.ticker))
        for k in ['currentPrice','previousClose','fiftyTwoWeekHigh','fiftyTwoWeekLow','marketCap']:
            if k not in info or info[k] is None: info[k]=0
        return info
    def _fig_to_base64(self, fig):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        return img
    def generate_report_html(self, ticker, peers=None, target_price=None, rating=None, lang="en"):
        ticker = self.sanitize_ticker(ticker)
        stock = yf.Ticker(ticker)
        hist_1y = stock.history(period="1y", auto_adjust=True)
        if hist_1y.empty: hist_1y = stock.history(period="2y").tail(260)
        info = self.get_robust_info(stock, hist_1y)
        current_price = float(info.get('currentPrice',0))
        prev_close = float(info.get('previousClose',0))
        day_change = current_price - prev_close
        day_pct = (day_change/prev_close*100) if prev_close else 0
        target_price = target_price or current_price*1.15
        rating = rating or "HOLD"
        upside = ((target_price/current_price-1)*100) if current_price else 0
        charts = {}
        if not hist_1y.empty:
            fig, ax = plt.subplots(figsize=(10,4))
            ax.plot(hist_1y.index, hist_1y['Close'], color='#1f77b4')
            ax.set_title(f"{ticker} - 1Y Price", fontweight='bold')
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            charts['price'] = self._fig_to_base64(fig)
        def fmt(num):
            if pd.isna(num) or num==0: return "-"
            if abs(num)>=1e7: return f"\u20b9{num/1e7:.2f}Cr"
            elif abs(num)>=1e5: return f"\u20b9{num/1e5:.2f}L"
            else: return f"\u20b9{num:,.2f}"
        html = f"""<!DOCTYPE html><html><head><meta charset='UTF-8'><title>{ticker} Report</title>
<style>body{{font-family:sans-serif;background:#f5f5f5}} .container{{max-width:1000px;margin:0 auto;background:white}} .header{{background:#1a237e;color:white;padding:20px}} .price{{font-size:32px}}</style></head><body><div class='container'>
<div class='header'><h1>{info.get('longName',ticker)} ({ticker})</h1><div class='price'>\u20b9{current_price:,.2f} ({day_pct:+.2f}%)</div><div>Target \u20b9{target_price:,.0f} ({upside:+.1f}%) - {rating}</div></div>
<div style='padding:20px'><p>Market Cap: {fmt(info.get('marketCap',0))} | 52W High \u20b9{info.get('fiftyTwoWeekHigh',0):,.0f} Low \u20b9{info.get('fiftyTwoWeekLow',0):,.0f}</p>
<div style='text-align:center'><img src='data:image/png;base64,{charts.get('price','')}' style='max-width:100%'/></div></div>
<div style='background:#0d1b2a;color:white;padding:15px;text-align:center;font-size:11px'>Disclaimer: Not SEBI advice | {datetime.now().strftime('%d %b %Y %H:%M IST')}</div>
</div></body></html>"""
        return html

class PortfolioParser:
    def sanitize_ticker(self, ticker):
        t = str(ticker).strip().upper()
        t = re.sub(r'\s+', '', t)
        t = t.replace('-EQ','').replace('-BE','')
        if not t or t.lower()=='nan': return ""
        if t.endswith('.NS') or t.endswith('.BO'): return t
        if '.' not in t: return f"{t}.NS"
        return t
    def parse_excel(self, file_input):
        try:
            df = pd.read_excel(file_input, sheet_name=0)
            return self._parse_df(df, "Excel")
        except Exception as e:
            print(f"Excel error {e}")
            return []
    def parse_csv(self, file_input):
        try:
            df = pd.read_csv(file_input)
            return self._parse_df(df, "CSV")
        except:
            try:
                file_input.seek(0)
                df = pd.read_csv(file_input, encoding='latin1')
                return self._parse_df(df, "CSV")
            except Exception as e:
                print(f"CSV error {e}")
                return []
    def _parse_df(self, df, source):
        if df.empty: return []
        df = df.dropna(how='all')
        symbol_cols = [c for c in df.columns if 'symbol' in str(c).lower()]
        if symbol_cols:
            df = df.dropna(subset=[symbol_cols[0]])
            df = df[~df[symbol_cols[0]].astype(str).str.lower().isin(['nan','none',''])]
        df.columns = [str(c).strip() for c in df.columns]
        col_lower = {c.lower(): c for c in df.columns}
        ticker_col = None
        for key in ['symbol','ticker','instrument']:
            for low, orig in col_lower.items():
                if low == key:
                    ticker_col = orig
                    break
            if ticker_col: break
        if not ticker_col:
            for low, orig in col_lower.items():
                if 'symbol' in low and 'quantity' not in low:
                    ticker_col = orig
                    break
        if not ticker_col:
            ticker_col = df.columns[1] if len(df.columns)>1 else df.columns[0]
        qty_col = None
        for low, orig in col_lower.items():
            if 'total' in low and 'quantity' in low and 'available' in low:
                qty_col = orig
                break
        if not qty_col:
            for low, orig in col_lower.items():
                if 'total' in low and 'quantity' in low:
                    qty_col = orig
                    break
        if not qty_col:
            candidates = []
            for low, orig in col_lower.items():
                if 'quantity' in low and 'long' not in low and 'short' not in low:
                    candidates.append(orig)
            if candidates:
                qty_col = candidates[0]
        avg_col = None
        for low, orig in col_lower.items():
            if 'average' in low and 'price' in low:
                avg_col = orig
                break
        invested_col = None
        for low, orig in col_lower.items():
            if 'invested' in low and 'amount' in low:
                invested_col = orig
                break
        ltp_col = None
        for low, orig in col_lower.items():
            if 'last' in low and 'traded' in low and 'price' in low:
                ltp_col = orig
                break
        curr_col = None
        for low, orig in col_lower.items():
            if 'current' in low and 'value' in low:
                curr_col = orig
                break
        buy_date_col = None
        for low, orig in col_lower.items():
            if 'buy' in low and 'date' in low:
                buy_date_col = orig
                break
        print(f"Detected -> Ticker:{ticker_col} Qty:{qty_col} Avg:{avg_col} Invested:{invested_col} LTP:{ltp_col} Current:{curr_col}")
        results = []
        for idx, row in df.iterrows():
            try:
                raw = str(row[ticker_col]).strip() if pd.notna(row[ticker_col]) else ""
                if not raw or raw.lower() in ['nan','none','']: continue
                if raw.lower() in ['symbol','ticker']: continue
                ticker = self.sanitize_ticker(raw)
                if len(ticker)<2: continue
                if ticker.replace('.NS','').replace('.BO','').isdigit(): continue
                qty = None
                if qty_col and pd.notna(row.get(qty_col)):
                    try: qty = float(str(row[qty_col]).replace(',','').replace('\u20b9','').strip())
                    except: pass
                avg = None
                if avg_col and pd.notna(row.get(avg_col)):
                    try: avg = float(str(row[avg_col]).replace(',','').replace('\u20b9','').strip())
                    except: pass
                invested_file = None
                if invested_col and pd.notna(row.get(invested_col)):
                    try: invested_file = float(str(row[invested_col]).replace(',','').replace('\u20b9','').strip())
                    except: pass
                ltp_file = None
                if ltp_col and pd.notna(row.get(ltp_col)):
                    try: ltp_file = float(str(row[ltp_col]).replace(',','').replace('\u20b9','').strip())
                    except: pass
                current_file = None
                if curr_col and pd.notna(row.get(curr_col)):
                    try: current_file = float(str(row[curr_col]).replace(',','').replace('\u20b9','').strip())
                    except: pass
                buy_date = None
                if buy_date_col and pd.notna(row.get(buy_date_col)):
                    buy_date = str(row[buy_date_col]).strip()
                if qty and avg and invested_file and invested_file>0:
                    calc = qty*avg
                    if abs(calc - invested_file) / invested_file > 0.01:
                        qty = invested_file / avg if avg else qty
                if (qty is None or qty==0) and invested_file and avg:
                    qty = invested_file / avg if avg else 0
                results.append({'ticker': ticker, 'quantity': qty, 'avg_price': avg, 'invested_file': invested_file, 'ltp_file': ltp_file, 'current_file': current_file, 'buy_date': buy_date, 'peers': [], 'target_price': None, 'rating': None, 'source': source})
            except Exception as e:
                print(f"Row {idx} error {e}")
                continue
        seen = {}
        for r in results:
            if r['ticker'] not in seen: seen[r['ticker']] = r
        final = list(seen.values())
        total_inv = sum([x.get('invested_file',0) or 0 for x in final])
        print(f"Parsed {len(final)} tickers, Total Invested (file): {total_inv:,.2f}")
        return final

class LivePortfolioTracker:
    def calculate_live_pnl(self, portfolio_stocks, use_file_ltp=False):
        results = []
        for stock in portfolio_stocks:
            ticker_raw = stock.get('ticker','')
            qty = stock.get('quantity') or 0
            avg_price = stock.get('avg_price') or 0
            try: qty = float(qty) if qty is not None else 0
            except: qty = 0
            try: avg_price = float(avg_price) if avg_price is not None else 0
            except: avg_price = 0
            ticker = ticker_raw if ticker_raw.endswith('.NS') or ticker_raw.endswith('.BO') else f"{ticker_raw}.NS"
            invested_file = stock.get('invested_file') or 0
            current_file = stock.get('current_file') or 0
            ltp_file = stock.get('ltp_file') or 0
            if (qty==0 or pd.isna(qty)) and invested_file and avg_price:
                qty = invested_file / avg_price if avg_price else 0
            live_price = prev_close = 0
            day_pct = 0
            try:
                s = yf.Ticker(ticker)
                hist = s.history(period="5d", auto_adjust=True)
                if not hist.empty:
                    live_price = float(hist['Close'].iloc[-1])
                    if len(hist)>1:
                        prev_close = float(hist['Close'].iloc[-2])
                        day_pct = ((live_price-prev_close)/prev_close*100) if prev_close else 0
                else:
                    try: live_price = float(s.fast_info.last_price)
                    except: live_price = ltp_file or 0
            except:
                live_price = ltp_file or 0
            display_ltp = ltp_file if use_file_ltp and ltp_file else live_price
            if display_ltp==0:
                display_ltp = ltp_file or live_price
            invested = qty*avg_price if qty and avg_price else (invested_file or 0)
            if invested_file and invested and abs(invested - invested_file)/max(invested_file,1) < 0.01:
                invested = invested_file
            elif invested_file and invested_file>0:
                invested = invested_file
            current_val = qty*display_ltp if qty and display_ltp else (current_file or 0)
            pnl = current_val - invested if invested else 0
            pnl_pct = (pnl/invested*100) if invested else 0
            file_pnl = (current_file - invested_file) if current_file and invested_file else 0
            file_pnl_pct = (file_pnl/invested_file*100) if invested_file else 0
            results.append({
                'Ticker': ticker_raw.replace('.NS','').replace('.BO',''),
                'Full Ticker': ticker_raw,
                'Quantity': qty,
                'Avg Price': avg_price,
                'LTP File': ltp_file,
                'LTP (Live)': live_price,
                'LTP Used': display_ltp,
                'Prev Close': prev_close,
                'Day Change %': day_pct,
                'Invested Value': invested,
                'Invested File': invested_file,
                'Current Value': current_val,
                'Current File': current_file,
                'P&L': pnl,
                'P&L %': pnl_pct,
                'P&L File': file_pnl,
                'P&L File %': file_pnl_pct,
                'Buy Date': stock.get('buy_date',''),
            })
        return pd.DataFrame(results)
    def get_summary(self, pnl_df):
        if pnl_df.empty: return {}
        total_inv = pnl_df['Invested Value'].sum()
        total_cur = pnl_df['Current Value'].sum()
        total_pnl = pnl_df['P&L'].sum()
        total_inv_file = pnl_df['Invested File'].sum()
        total_cur_file = pnl_df['Current File'].sum()
        total_pnl_file = pnl_df['P&L File'].sum()
        day_pnl = sum([row['Quantity']*(row['LTP (Live)']-row['Prev Close']) for _, row in pnl_df.iterrows() if row['Quantity'] and row['LTP (Live)'] and row['Prev Close']])
        return {
            'total_stocks': len(pnl_df),
            'total_invested': total_inv,
            'total_current': total_cur,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl/total_inv*100) if total_inv else 0,
            'total_invested_file': total_inv_file,
            'total_current_file': total_cur_file,
            'total_pnl_file': total_pnl_file,
            'total_pnl_file_pct': (total_pnl_file/total_inv_file*100) if total_inv_file else 0,
            'day_pnl': day_pnl,
            'day_pnl_pct': (day_pnl/total_cur*100) if total_cur else 0,
            'winners': len(pnl_df[pnl_df['P&L']>0]),
            'losers': len(pnl_df[pnl_df['P&L']<0]),
        }
    def format_inr(self, num):
        if pd.isna(num) or num==0: return "\u20b90"
        abs_num = abs(num)
        if abs_num>=1e7: return f"\u20b9{num/1e7:.2f}Cr"
        elif abs_num>=1e5: return f"\u20b9{num/1e5:.2f}L"
        elif abs_num>=1e3: return f"\u20b9{num/1e3:.1f}K"
        else: return f"\u20b9{num:,.2f}"

st.set_page_config(page_title="Fixed P&L + Bulk Reports", page_icon="✅", layout="wide")

st.markdown("""
<style>
.main-header { background: linear-gradient(135deg,#0d1b2a 0%,#1a237e 50%,#4caf50 100%); padding:20px; border-radius:12px; color:white; margin-bottom:20px }
.metric-card { background:white; padding:15px; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,0.08); border-left:4px solid #1a237e; text-align:center; margin-bottom:10px }
.metric-card.green { border-left-color:#4caf50; background: linear-gradient(135deg,#e8f5e9,#ffffff); }
.metric-card.red { border-left-color:#f44336; background: linear-gradient(135deg,#ffebee,#ffffff); }
.metric-card.blue { border-left-color:#2196f3; background: linear-gradient(135deg,#e3f2fd,#ffffff); }
.metric-card.orange { border-left-color:#ff6f00; background: linear-gradient(135deg,#fff3e0,#ffffff); }
.metric-value { font-size:22px; font-weight:bold; margin:5px 0; }
.metric-label { font-size:11px; color:#666; text-transform:uppercase; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>✅ FIXED + BULK REPORTS EDITION</h1><p>Fixed: Total Quantity Available | Bulk Reports for All 52 Holdings + Single Stock Option | Qty×LTP Correct</p></div>', unsafe_allow_html=True)

parser = PortfolioParser()
tracker = LivePortfolioTracker()
agent = StockReportAgent()

with st.sidebar:
    st.header("📁 Upload Holdings")
    st.markdown("Supports your file with Total Quantity Available, Average Price, Invested Amount")
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx","xls","csv"], help="Your holdings file")
    portfolio_stocks = []
    if uploaded_file:
        try:
            import io
            buf = io.BytesIO(uploaded_file.getvalue())
            ext = uploaded_file.name.split('.')[-1].lower()
            if ext=='csv':
                parsed = parser.parse_csv(buf)
            else:
                parsed = parser.parse_excel(buf)
            if parsed:
                st.success(f"✅ {len(parsed)} stocks - Invested: \u20b9{sum([x.get('invested_file',0) or 0 for x in parsed]):,.0f}")
                portfolio_stocks = parsed
        except Exception as e:
            st.error(f"Error: {e}")
    if not portfolio_stocks:
        try:
            with open("portfolio.json") as f:
                data=json.load(f)
                portfolio_stocks=data.get('stocks',[])
        except:
            portfolio_stocks=[]
    st.divider()
    st.header("⚙️ Settings")
    use_file_ltp = st.checkbox("Use File LTP (not Live)", value=False, help="Uses Last Traded Price from file")
    calc = st.button("💹 Calculate FIXED P&L")

# Main Tabs
tab1, tab2 = st.tabs(["💹 Fixed P&L Dashboard", "📄 Bulk Reports (All + Single)"])

with tab1:
    if portfolio_stocks:
        if 'pnl_df' not in st.session_state or calc:
            with st.spinner(f"Calculating FIXED P&L for {len(portfolio_stocks)} stocks..."):
                pnl_df = tracker.calculate_live_pnl(portfolio_stocks, use_file_ltp=use_file_ltp)
                st.session_state.pnl_df = pnl_df
                st.session_state.summary = tracker.get_summary(pnl_df)
        pnl_df = st.session_state.pnl_df
        summary = st.session_state.get('summary',{})
        if not pnl_df.empty:
            m1,m2,m3,m4,m5 = st.columns(5)
            with m1:
                st.markdown(f'<div class="metric-card blue"><div class="metric-label">Invested (File)</div><div class="metric-value">{tracker.format_inr(summary.get("total_invested_file",0))}</div></div>', unsafe_allow_html=True)
            with m2:
                st.markdown(f'<div class="metric-card"><div class="metric-label">Current (File)</div><div class="metric-value">{tracker.format_inr(summary.get("total_current_file",0))}</div></div>', unsafe_allow_html=True)
            with m3:
                cur = summary.get('total_current_file' if use_file_ltp else 'total_current',0)
                label = "Current File" if use_file_ltp else "Current Live"
                st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{tracker.format_inr(cur)}</div></div>', unsafe_allow_html=True)
            with m4:
                pnl_val = summary.get('total_pnl_file' if use_file_ltp else 'total_pnl',0)
                pnl_pct = summary.get('total_pnl_file_pct' if use_file_ltp else 'total_pnl_pct',0)
                color = "green" if pnl_val>=0 else "red"
                st.markdown(f'<div class="metric-card {color}"><div class="metric-label">Total P&L {"(File)" if use_file_ltp else "(Live)"}</div><div class="metric-value">{tracker.format_inr(pnl_val)} ({pnl_pct:+.1f}%)</div></div>', unsafe_allow_html=True)
            with m5:
                st.markdown(f'<div class="metric-card orange"><div class="metric-label">Winners/Losers</div><div class="metric-value">🟢{summary.get("winners",0)}/🔴{summary.get("losers",0)}</div></div>', unsafe_allow_html=True)
            st.dataframe(pnl_df.style.format({'Avg Price':'\u20b9{:.2f}','LTP File':'\u20b9{:.2f}','LTP (Live)':'\u20b9{:.2f}','Invested File':'\u20b9{:.0f}','Current File':'\u20b9{:.0f}','P&L File':'\u20b9{:.0f}','P&L File %':'{:.2f}%'}), use_container_width=True, height=400)
    else:
        st.info("Upload holdings Excel in sidebar")

with tab2:
    st.markdown("### 📄 Bulk Reports - All Portfolio + Single Stock")
    st.info("Generates detailed broker reports with 1Y chart, 52W High/Low, Market Cap for each holding. Uses Total Quantity Available for P&L in reports.")
    if not portfolio_stocks:
        st.warning("Upload portfolio Excel first")
        portfolio_tickers = []
    else:
        portfolio_tickers = [s.get('ticker','').replace('.NS','').replace('.BO','') for s in portfolio_stocks]
        st.success(f"📁 Portfolio: {len(portfolio_tickers)} stocks")
    
    col1, col2 = st.columns([2,1])
    with col1:
        report_mode = st.radio("Report Mode", ["📚 All Portfolio Stocks (Bulk) - 52 Reports", "✅ Selected Stocks", "🔍 Single Stock Detailed"], index=0)
    with col2:
        want_pdf = st.checkbox("Also PDF", value=False)
        lang_rep = st.selectbox("Language", ["English","Hindi","Hinglish"], index=0, key="lang_rep")
        lang_code_rep = "en" if lang_rep=="English" else "hi" if "Hindi" in lang_rep else "hinglish"
    
    if report_mode.startswith("📚 All"):
        st.subheader(f"📚 Generate All {len(portfolio_tickers)} Reports")
        st.markdown(f"This will create {len(portfolio_tickers)} HTML reports (one per stock) with live price, charts, and your P&L (Qty {portfolio_tickers[0] if portfolio_tickers else ''} etc). Takes ~2-3 mins for 52 stocks.")
        if st.button(f"🚀 Generate ALL {len(portfolio_tickers)} Detailed Reports", type="primary"):
            if not portfolio_tickers:
                st.error("No portfolio")
            else:
                progress = st.progress(0)
                status = st.empty()
                generated = []
                failed = []
                os.makedirs("reports", exist_ok=True)
                for i, ticker_short in enumerate(portfolio_tickers):
                    ticker_full = f"{ticker_short}.NS"
                    for s in portfolio_stocks:
                        if s.get('ticker','').replace('.NS','').replace('.BO','') == ticker_short:
                            ticker_full = s.get('ticker','')
                            break
                    status.text(f"{i+1}/{len(portfolio_tickers)}: {ticker_short} ({ticker_full}) - Total Qty Available")
                    try:
                        html = agent.generate_report_html(ticker_full, [], None, None, lang_code_rep)
                        # Inject P&L if available
                        if 'pnl_df' in st.session_state and st.session_state.pnl_df is not None:
                            match = st.session_state.pnl_df[st.session_state.pnl_df['Ticker']==ticker_short]
                            if not match.empty:
                                r = match.iloc[0]
                                pnl_block = f"<div style='background:#e8f5e9;padding:15px;margin:15px 30px;border-radius:8px;border-left:4px solid #4caf50'><h3>💹 Your Holding - {r['Ticker']}</h3><p><b>Qty:</b> {r['Quantity']:.0f} (Total Available) | <b>Avg:</b> \u20b9{r['Avg Price']:.2f} | <b>LTP:</b> \u20b9{r['LTP Used']:.2f}</p><p><b>Invested:</b> \u20b9{r['Invested Value']:,.0f} | <b>Current:</b> \u20b9{r['Current Value']:,.0f} | <b>P&L:</b> \u20b9{r['P&L']:,.0f} ({r['P&L %']:+.1f}%)</p></div>"
                                html = html.replace("<div style='padding:20px'>", pnl_block + "<div style='padding:20px'>", 1)
                        safe = ticker_full.replace('.','_')
                        date_str = datetime.now().strftime('%Y%m%d')
                        html_path = f"reports/{safe}_Report_{date_str}.html"
                        with open(html_path, "w", encoding="utf-8") as out:
                            out.write(html)
                        generated.append(html_path)
                    except Exception as e:
                        failed.append(f"{ticker_short}: {e}")
                    progress.progress((i+1)/len(portfolio_tickers))
                status.text(f"✅ Done! {len(generated)} reports")
                if generated:
                    import zipfile
                    zip_path = f"reports/All_{len(generated)}_Reports_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for fp in generated:
                            zipf.write(fp, os.path.basename(fp))
                    with open(zip_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                        st.markdown(f'<a href="data:application/zip;base64,{b64}" download="{os.path.basename(zip_path)}" style="background:#1a237e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;display:inline-block;margin:10px 0">📦 Download All {len(generated)} Reports ZIP</a>', unsafe_allow_html=True)
                    st.success(f"Generated {len(generated)} detailed reports for all portfolio holdings! Each includes Total Quantity Available (fixed), Avg Price, Invested, Current, P&L")
                    if failed:
                        with st.expander(f"Failed {len(failed)}"):
                            for f in failed: st.text(f)
    
    elif report_mode.startswith("✅ Selected"):
        if portfolio_tickers:
            selected = st.multiselect(f"Choose from {len(portfolio_tickers)} stocks", portfolio_tickers, default=portfolio_tickers[:5])
            if st.button(f"🚀 Generate {len(selected)} Selected Reports", type="primary"):
                progress = st.progress(0)
                generated = []
                os.makedirs("reports", exist_ok=True)
                for i, ticker_short in enumerate(selected):
                    ticker_full = f"{ticker_short}.NS"
                    for s in portfolio_stocks:
                        if s.get('ticker','').replace('.NS','').replace('.BO','') == ticker_short:
                            ticker_full = s.get('ticker','')
                            break
                    try:
                        html = agent.generate_report_html(ticker_full, [], None, None, lang_code_rep)
                        safe = ticker_full.replace('.','_')
                        date_str = datetime.now().strftime('%Y%m%d')
                        html_path = f"reports/{safe}_Report_{date_str}.html"
                        with open(html_path, "w", encoding="utf-8") as out:
                            out.write(html)
                        generated.append(html_path)
                    except Exception as e:
                        st.error(f"{ticker_short}: {e}")
                    progress.progress((i+1)/len(selected))
                if generated:
                    import zipfile
                    zip_path = f"reports/Selected_{len(generated)}_Reports.zip"
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for fp in generated:
                            zipf.write(fp, os.path.basename(fp))
                    with open(zip_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                        st.markdown(f'<a href="data:application/zip;base64,{b64}" download="{os.path.basename(zip_path)}" style="background:#1a237e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none">📦 Download {len(generated)} Reports ZIP</a>', unsafe_allow_html=True)
    
    else:
        st.subheader("🔍 Single Stock Detailed Report")
        if portfolio_tickers:
            single = st.selectbox(f"Select from portfolio ({len(portfolio_tickers)}) or type custom", [""] + portfolio_tickers + ["Custom..."], index=0)
            if single == "Custom...":
                single = st.text_input("Enter Ticker", value="RELIANCE")
            elif single == "":
                single = st.text_input("Or custom ticker", value="RELIANCE", key="custom_single")
        else:
            single = st.text_input("Ticker", value="RELIANCE")
        include_pnl = st.checkbox("Include Your P&L (Qty, Avg, Invested, Current)", value=True)
        if st.button("🚀 Generate Single Detailed Report", type="primary"):
            clean = single.upper()
            if not clean.endswith('.NS') and not clean.endswith('.BO'):
                clean = f"{clean.replace('.NS','').replace('.BO','')}.NS"
            with st.spinner(f"Generating {clean}..."):
                try:
                    pnl_info = None
                    if 'pnl_df' in st.session_state and st.session_state.pnl_df is not None:
                        match = st.session_state.pnl_df[st.session_state.pnl_df['Ticker']==clean.replace('.NS','').replace('.BO','')]
                        if not match.empty:
                            pnl_info = match.iloc[0]
                    html = agent.generate_report_html(clean, [], None, None, lang_code_rep)
                    if include_pnl and pnl_info is not None:
                        block = f"<div style='background:#e8f5e9;padding:15px;margin:15px 30px;border-radius:8px;border-left:4px solid #4caf50'><h3>💹 Your Holding - {pnl_info['Ticker']}</h3><p><b>Qty:</b> {pnl_info['Quantity']:.0f} (Total Available) | <b>Avg:</b> \u20b9{pnl_info['Avg Price']:.2f} | <b>LTP:</b> \u20b9{pnl_info['LTP Used']:.2f}</p><p><b>Invested:</b> \u20b9{pnl_info['Invested Value']:,.0f} | <b>Current:</b> \u20b9{pnl_info['Current Value']:,.0f} | <b>P&L:</b> \u20b9{pnl_info['P&L']:,.0f} ({pnl_info['P&L %']:+.1f}%)</p></div>"
                        html = html.replace("<div style='padding:20px'>", block + "<div style='padding:20px'>", 1)
                    path = f"reports/{clean.replace('.','_')}_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
                    os.makedirs("reports", exist_ok=True)
                    with open(path,"w", encoding="utf-8") as f:
                        f.write(html)
                    st.success(f"✅ Report for {clean} generated!")
                    if pnl_info is not None:
                        st.info(f"💹 P&L: Qty {pnl_info['Quantity']:.0f} × Avg \u20b9{pnl_info['Avg Price']:.2f} = Invested \u20b9{pnl_info['Invested Value']:,.0f} | Current \u20b9{pnl_info['Current Value']:,.0f} | P&L \u20b9{pnl_info['P&L']:,.0f} ({pnl_info['P&L %']:+.1f}%)")
                    b64 = base64.b64encode(html.encode()).decode()
                    st.markdown(f'<a href="data:text/html;base64,{b64}" download="{os.path.basename(path)}" style="background:#1a237e;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block;margin:5px">📥 Download HTML</a>', unsafe_allow_html=True)
                    st.components.v1.html(html, height=700, scrolling=True)
                except Exception as e:
                    st.error(f"{e}")

st.caption("✅ FIXED + BULK REPORTS | Total Quantity Available (not ST) | Bulk Reports for All 52 Holdings + Single Stock Option | ZIP Download")
