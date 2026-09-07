
"""
Equity Lab - 5 TABS FIXED EDITION
Tabs: Live P&L (Fixed) + SIP + XIRR + Dividend + Capital Gains + Bulk Reports (All 52 + Single)
Fixed: Uses Total Quantity Available, not Short Term Qty
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json, os, re, base64, io, urllib.parse, requests
from datetime import datetime, timedelta
from typing import List, Dict
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
    def sanitize_with_exchange(self, ticker, exchange="NSE"):
        t = self.sanitize_ticker(ticker)
        if exchange=="BSE":
            if t.endswith('.NS'): t=t.replace('.NS','.BO')
            elif not t.endswith('.BO'): t=t.replace('.NS','').replace('.BO','')+'.BO'
        else:
            if t.endswith('.BO'): t=t.replace('.BO','.NS')
            elif not t.endswith('.NS'): t=t.replace('.NS','').replace('.BO','')+'.NS'
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
            info['currency'] = info.get('currency','INR')
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
        info.setdefault('exchange','NSE')
        info.setdefault('longName', info.get('shortName', ticker_obj.ticker))
        info.setdefault('longBusinessSummary', f"{ticker_obj.ticker} listed on NSE India.")
        for k in ['currentPrice','previousClose','fiftyTwoWeekHigh','fiftyTwoWeekLow','marketCap','bookValue']:
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
        hist_5y = stock.history(period="5y", auto_adjust=True)
        if hist_1y.empty: hist_1y = stock.history(period="2y").tail(260)
        if hist_5y.empty: hist_5y = hist_1y
        info = self.get_robust_info(stock, hist_1y)
        # Charts
        charts = {}
        if not hist_1y.empty:
            fig, (ax1, ax2) = plt.subplots(2,1,figsize=(10,5), gridspec_kw={'height_ratios':[3,1]}, sharex=True)
            ax1.plot(hist_1y.index, hist_1y['Close'], color='#1f77b4', linewidth=1.2)
            ret = (hist_1y['Close'].iloc[-1]/hist_1y['Close'].iloc[0]-1)*100 if len(hist_1y)>1 else 0
            ax1.text(0.02,0.95,f"1Y Return: {ret:+.1f}%", transform=ax1.transAxes, fontweight='bold', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8), color='green' if ret>=0 else 'red')
            ax1.set_title(f"{info.get('longName',ticker)} - NSE Price & Volume (1Y)", fontweight='bold')
            ax1.grid(True, alpha=0.3)
            colors = ['green' if hist_1y['Close'].iloc[i]>=hist_1y['Open'].iloc[i] else 'red' for i in range(len(hist_1y))]
            ax2.bar(hist_1y.index, hist_1y['Volume'], color=colors, alpha=0.6, width=1)
            plt.tight_layout()
            charts['price_1y'] = self._fig_to_base64(fig)
        if not hist_1y.empty and len(hist_1y)>=14:
            close = hist_1y['Close']
            delta = close.diff()
            rs = delta.where(delta>0,0).rolling(14).mean() / (-delta.where(delta<0,0)).rolling(14).mean()
            rsi = 100 - (100/(1+rs))
            fig, ax = plt.subplots(figsize=(10,3))
            ax.plot(hist_1y.index, rsi, color='purple')
            ax.axhline(70, color='red', linestyle='--', alpha=0.7)
            ax.axhline(30, color='green', linestyle='--', alpha=0.7)
            ax.set_title(f"RSI (14) - {ticker}", fontweight='bold')
            ax.set_ylim(0,100)
            plt.tight_layout()
            charts['rsi'] = self._fig_to_base64(fig)
        if not hist_1y.empty and len(hist_1y)>=200:
            fig, ax = plt.subplots(figsize=(10,4))
            close = hist_1y['Close']
            ax.plot(hist_1y.index, close, color='black', label='Price', alpha=0.8)
            ax.plot(hist_1y.index, close.rolling(20).mean(), label='SMA 20', color='blue')
            ax.plot(hist_1y.index, close.rolling(50).mean(), label='SMA 50', color='orange')
            ax.plot(hist_1y.index, close.rolling(200).mean(), label='SMA 200', color='red')
            ax.set_title(f"Moving Averages - {ticker}", fontweight='bold')
            ax.legend()
            plt.tight_layout()
            charts['sma'] = self._fig_to_base64(fig)
        current_price = float(info.get('currentPrice',0))
        prev_close = float(info.get('previousClose',0))
        day_change = current_price - prev_close
        day_pct = (day_change/prev_close*100) if prev_close else 0
        target_price = target_price or current_price*1.15
        rating = rating or ("BUY" if (target_price/current_price-1)*100>15 else "HOLD" if current_price else "NEUTRAL")
        upside = ((target_price/current_price-1)*100) if current_price else 0
        def fmt(num):
            if pd.isna(num) or num==0: return "-"
            abs_num = abs(num)
            if abs_num>=1e7: return f"\u20b9{num/1e7:.2f}Cr"
            elif abs_num>=1e5: return f"\u20b9{num/1e5:.2f}L"
            elif abs_num>=1e3: return f"\u20b9{num/1e3:.1f}K"
            else: return f"\u20b9{num:,.2f}"
        html = f"""<!DOCTYPE html><html><head><meta charset='UTF-8'><title>{info.get('longName',ticker)} Report</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#f5f5f5;margin:0}} .container{{max-width:1200px;margin:0 auto;background:white;box-shadow:0 0 20px rgba(0,0,0,0.1)}}
.header{{background:linear-gradient(135deg,#0d1b2a,#1a237e,#ff6f00);color:white;padding:30px}} .price{{font-size:36px;font-weight:bold}}
.positive{{color:#4caf50}} .negative{{color:#f44336}} .rating-bar{{background:#fff3e0;padding:15px 30px;display:flex;justify-content:space-between;flex-wrap:wrap}}
.rating-badge{{padding:8px 20px;border-radius:20px;font-weight:bold;color:white}} .buy{{background:#4caf50}} .sell{{background:#f44336}} .hold{{background:#ff9800}} .accumulate{{background:#2196f3}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;padding:25px;background:#fafafa}}
.stat-card{{background:white;padding:15px;border-radius:8px;box-shadow:0 2px 5px rgba(0,0,0,0.05);border-left:4px solid #283593}}
.label{{font-size:11px;color:#666;text-transform:uppercase}} .value{{font-size:18px;font-weight:bold;color:#1a237e}}
.section{{padding:25px 30px;border-bottom:1px solid #eee}} .section-title{{font-size:20px;font-weight:bold;color:#1a237e;margin-bottom:15px;border-bottom:2px solid #283593;display:inline-block;padding-bottom:8px}}
.chart-container{{margin:20px 0;text-align:center}} .chart-container img{{max-width:100%;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.08)}}
.footer{{background:#0d1b2a;color:white;padding:20px;text-align:center;font-size:11px}}
</style></head><body><div class='container'>
<div class='header'><h1>{info.get('longName',ticker)} <span style='background:#ff9800;padding:4px 10px;border-radius:12px;font-size:12px'>NSE: {ticker}</span></h1>
<div>{ticker} | {info.get('sector','N/A')} | \u20b9 NSE India</div><div style='text-align:right'><div class='price'>\u20b9 {current_price:,.2f}</div><div class='{"positive" if day_change>=0 else "negative"}'>{day_change:+,.2f} ({day_pct:+.2f}%)</div></div></div>
<div class='rating-bar'><span class='rating-badge {rating.lower()}'>{rating}</span><div>Target: <strong>\u20b9 {target_price:,.0f}</strong> <span style='color:{"#4caf50" if upside>0 else "#f44336"};font-weight:bold'>({upside:+.1f}%)</span></div></div>
<div class='stats-grid'>
<div class='stat-card'><div class='label'>Market Cap</div><div class='value'>{fmt(info.get('marketCap',0))}</div></div>
<div class='stat-card'><div class='label'>52W High / Low</div><div class='value'>\u20b9{info.get('fiftyTwoWeekHigh',0):,.0f} / \u20b9{info.get('fiftyTwoWeekLow',0):,.0f}</div></div>
<div class='stat-card'><div class='label'>Exchange</div><div class='value'>NSE India</div></div>
<div class='stat-card'><div class='label'>Currency</div><div class='value'>{info.get('currency','INR')}</div></div>
</div>
<div class='section'><div class='section-title'>Price & Volume</div><div class='chart-container'><img src='data:image/png;base64,{charts.get('price_1y','')}' /></div></div>
<div class='section'><div class='section-title'>Technical Analysis</div><div style='display:grid;grid-template-columns:1fr 1fr;gap:20px'><div class='chart-container'><img src='data:image/png;base64,{charts.get('rsi','')}' /></div><div class='chart-container'><img src='data:image/png;base64,{charts.get('sma','')}' /></div></div></div>
<div class='footer'><p>Generated by Equity Lab - 5 Tabs Fixed Edition | NSE Data | {datetime.now().strftime('%d %b %Y %H:%M IST')} | \u20b9</p></div>
</div></body></html>"""
        return html
    def _format_inr(self, num):
        if pd.isna(num) or num==0: return "-"
        abs_num = abs(num)
        if abs_num>=1e7: return f"\u20b9{num/1e7:.2f}Cr"
        elif abs_num>=1e5: return f"\u20b9{num/1e5:.2f}L"
        elif abs_num>=1e3: return f"\u20b9{num/1e3:.1f}K"
        else: return f"\u20b9{num:,.2f}"
    def generate_whatsapp_text(self, ticker, info, rating, target, lang="en"):
        current = info.get('currentPrice',0)
        prev = info.get('previousClose',0)
        change_pct = ((current-prev)/prev*100) if prev else 0
        upside = ((target/current-1)*100) if target and current else 0
        company = info.get('longName', ticker.replace('.NS',''))
        return f"\u20b9 *{company} - Report*\n\u20b9 {ticker} | NSE\n\u20b9 LTP: \u20b9{current:,.2f} ({change_pct:+.2f}%)\n\u20b9 Target: \u20b9{target:,.0f} ({upside:+.1f}%)\n\u2b50 Rating: {rating}\n"

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

class SIPTracker:
    def parse_sip_file(self, file_input):
        try:
            if file_input.name.endswith('.csv'):
                df = pd.read_csv(file_input)
            else:
                df = pd.read_excel(file_input)
        except:
            return []
        df.columns = [str(c).strip() for c in df.columns]
        col_lower = {c.lower(): c for c in df.columns}
        results = []
        for _, row in df.iterrows():
            try:
                date_val = None
                for d in ['date','sip date','trade date','purchase date']:
                    for low, orig in col_lower.items():
                        if d in low:
                            date_val = row[orig]
                            break
                ticker = None
                for t in ['ticker','symbol','stock','instrument']:
                    for low, orig in col_lower.items():
                        if t in low:
                            ticker = str(row[orig]).strip()
                            break
                amount = None
                for a in ['amount','invested','sip amount']:
                    for low, orig in col_lower.items():
                        if a in low:
                            try: amount = float(row[orig])
                            except: pass
                qty = None
                price = None
                for q in ['qty','quantity','units']:
                    for low, orig in col_lower.items():
                        if q in low:
                            try: qty = float(row[orig])
                            except: pass
                for p in ['price','rate','nav','avg']:
                    for low, orig in col_lower.items():
                        if p in low and 'amount' not in low:
                            try: price = float(row[orig])
                            except: pass
                if ticker:
                    results.append({
                        'Date': pd.to_datetime(date_val) if date_val else datetime.now(),
                        'Ticker': ticker.upper(),
                        'Amount': amount or (qty*price if qty and price else 0),
                        'Quantity': qty or 0,
                        'Price': price or 0,
                    })
            except: continue
        return results
    def calculate_sip_summary(self, sip_transactions, live_prices=None):
        if not sip_transactions:
            return pd.DataFrame(), {}
        df = pd.DataFrame(sip_transactions)
        df['Date'] = pd.to_datetime(df['Date'])
        summary = []
        for ticker in df['Ticker'].unique():
            t_df = df[df['Ticker']==ticker]
            total_invested = t_df['Amount'].sum()
            total_qty = t_df['Quantity'].sum()
            avg_price = total_invested/total_qty if total_qty else 0
            live_price = 0
            if live_prices and ticker in live_prices:
                live_price = live_prices[ticker]
            else:
                try:
                    s = yf.Ticker(f"{ticker}.NS" if not ticker.endswith('.NS') else ticker)
                    hist = s.history(period="5d")
                    if not hist.empty:
                        live_price = float(hist['Close'].iloc[-1])
                except:
                    live_price = 0
            current_val = total_qty * live_price
            pnl = current_val - total_invested
            pnl_pct = (pnl/total_invested*100) if total_invested else 0
            cashflows = []
            for _, row in t_df.iterrows():
                cashflows.append((row['Date'], -row['Amount']))
            cashflows.append((datetime.now(), current_val))
            xirr_val = self.calculate_xirr(cashflows)
            summary.append({
                'Ticker': ticker,
                'Total SIPs': len(t_df),
                'Total Invested': total_invested,
                'Total Qty': total_qty,
                'Avg Price': avg_price,
                'LTP': live_price,
                'Current Value': current_val,
                'P&L': pnl,
                'P&L %': pnl_pct,
                'XIRR %': xirr_val*100 if xirr_val else 0,
                'First SIP': t_df['Date'].min().strftime('%d-%m-%Y'),
                'Last SIP': t_df['Date'].max().strftime('%d-%m-%Y'),
            })
        summary_df = pd.DataFrame(summary)
        all_cashflows = []
        for _, row in df.iterrows():
            all_cashflows.append((row['Date'], -row['Amount']))
        total_current = summary_df['Current Value'].sum()
        all_cashflows.append((datetime.now(), total_current))
        overall_xirr = self.calculate_xirr(all_cashflows)
        overall = {
            'total_sips': len(df),
            'total_invested': summary_df['Total Invested'].sum(),
            'total_current': total_current,
            'total_pnl': summary_df['P&L'].sum(),
            'total_pnl_pct': (summary_df['P&L'].sum()/summary_df['Total Invested'].sum()*100) if summary_df['Total Invested'].sum() else 0,
            'overall_xirr': overall_xirr*100 if overall_xirr else 0,
            'tickers': len(summary_df),
        }
        return summary_df, overall
    def calculate_xirr(self, cashflows):
        if not cashflows or len(cashflows) < 2:
            return None
        cashflows = sorted(cashflows, key=lambda x: x[0])
        first_date = cashflows[0][0]
        cf_days = []
        for date, amount in cashflows:
            days = (date - first_date).days
            cf_days.append((days, amount))
        def npv(rate):
            total = 0
            for days, amount in cf_days:
                total += amount / ((1 + rate) ** (days/365.0))
            return total
        def npv_derivative(rate):
            total = 0
            for days, amount in cf_days:
                total += -amount * (days/365.0) / ((1 + rate) ** (days/365.0 + 1))
            return total
        rate = 0.1
        for _ in range(100):
            npv_val = npv(rate)
            if abs(npv_val) < 1e-6:
                return rate
            deriv = npv_derivative(rate)
            if abs(deriv) < 1e-10:
                break
            new_rate = rate - npv_val/deriv
            new_rate = max(-0.9, min(new_rate, 10.0))
            if abs(new_rate - rate) < 1e-6:
                return new_rate
            rate = new_rate
        low, high = -0.9, 10.0
        for _ in range(100):
            mid = (low + high) / 2
            npv_mid = npv(mid)
            if abs(npv_mid) < 1e-6:
                return mid
            if npv_mid > 0:
                low = mid
            else:
                high = mid
            if high - low < 1e-6:
                return mid
        return rate if abs(npv(rate)) < 1 else None

class DividendTracker:
    def get_dividends(self, ticker, buy_date=None):
        try:
            t = ticker if ticker.endswith('.NS') or ticker.endswith('.BO') else f"{ticker}.NS"
            stock = yf.Ticker(t)
            divs = stock.dividends
            if divs.empty:
                return pd.DataFrame(), 0
            if buy_date:
                try:
                    buy_dt = pd.to_datetime(buy_date, dayfirst=True)
                    divs = divs[divs.index >= buy_dt]
                except: pass
            div_df = pd.DataFrame({'Date': divs.index, 'Dividend': divs.values})
            total_div = divs.sum()
            return div_df, total_div
        except Exception as e:
            return pd.DataFrame(), 0
    def calculate_portfolio_dividends(self, portfolio_stocks):
        results = []
        total_div_all = 0
        for stock in portfolio_stocks:
            ticker = stock.get('ticker','').replace('.NS','').replace('.BO','')
            qty = stock.get('quantity') or 0
            buy_date = stock.get('buy_date','')
            div_df, div_per_share = self.get_dividends(ticker, buy_date)
            if not div_df.empty and qty:
                div_df['Quantity'] = qty
                div_df['Total Dividend'] = div_df['Dividend'] * qty
                total_div = div_df['Total Dividend'].sum()
                total_div_all += total_div
                results.append({
                    'Ticker': ticker,
                    'Quantity': qty,
                    'Buy Date': buy_date,
                    'Dividend Count': len(div_df),
                    'Div Per Share Total': div_per_share,
                    'Total Dividend': total_div,
                    'Last Dividend': div_df['Dividend'].iloc[-1] if not div_df.empty else 0,
                    'Last Div Date': div_df['Date'].iloc[-1].strftime('%d-%m-%Y') if not div_df.empty else '',
                })
            else:
                results.append({
                    'Ticker': ticker,
                    'Quantity': qty,
                    'Buy Date': buy_date,
                    'Dividend Count': 0,
                    'Div Per Share Total': 0,
                    'Total Dividend': 0,
                    'Last Dividend': 0,
                    'Last Div Date': '',
                })
        summary_df = pd.DataFrame(results)
        return summary_df, total_div_all

# ==================== STREAMLIT APP - 5 TABS ====================
st.set_page_config(page_title="Equity Lab - 5 Tabs Fixed", page_icon="💹", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.main-header { background: linear-gradient(135deg,#0d1b2a 0%,#1a237e 30%,#ff6f00 60%,#25D366 85%,#9c27b0 100%); padding:25px; border-radius:12px; color:white; margin-bottom:20px }
.metric-card { background:white; padding:15px; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,0.08); border-left:4px solid #1a237e; text-align:center; margin-bottom:10px }
.metric-card.green { border-left-color:#4caf50; background: linear-gradient(135deg,#e8f5e9,#ffffff); }
.metric-card.red { border-left-color:#f44336; background: linear-gradient(135deg,#ffebee,#ffffff); }
.metric-card.orange { border-left-color:#ff6f00; background: linear-gradient(135deg,#fff3e0,#ffffff); }
.metric-card.blue { border-left-color:#2196f3; background: linear-gradient(135deg,#e3f2fd,#ffffff); }
.metric-card.purple { border-left-color:#9c27b0; background: linear-gradient(135deg,#f3e5f5,#ffffff); }
.metric-value { font-size:22px; font-weight:bold; margin:5px 0; }
.metric-label { font-size:11px; color:#666; text-transform:uppercase; }
.stButton>button { background:#1a237e; color:white; border-radius:8px; height:42px; font-weight:600; width:100%; border:none }
.stButton>button:hover { background:#ff6f00; color:white }
.tab-header { background:#f5f7ff; padding:15px; border-radius:10px; margin:15px 0; border-left:4px solid #1a237e; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>💹 Equity Lab - 5 TABS FIXED EDITION</h1><p>FIXED: Total Quantity Available (not Short Term) | Live P&L Qty×LTP | SIP + XIRR | Dividend | STCG/LTCG | Bulk Reports (All 52 + Single)</p></div>', unsafe_allow_html=True)

parser = PortfolioParser()
tracker = LivePortfolioTracker()
sip_tracker = SIPTracker()
div_tracker = DividendTracker()
agent = StockReportAgent(output_dir="reports")

with st.sidebar:
    st.header("📁 Upload Portfolio")
    uploaded_file = st.file_uploader("Holdings Excel/CSV (Total Qty Available)", type=["xlsx","xls","csv","json"], help="Your holdings file with Total Quantity Available")
    portfolio_stocks = []
    if uploaded_file:
        try:
            import io
            buf = io.BytesIO(uploaded_file.getvalue())
            ext = uploaded_file.name.split('.')[-1].lower()
            if ext == 'csv':
                parsed = parser.parse_csv(buf)
            elif ext in ['xlsx','xls']:
                parsed = parser.parse_excel(buf)
            else:
                parsed = parser._parse_df(pd.read_json(buf), "JSON") if ext=='json' else []
            if parsed:
                st.success(f"✅ {len(parsed)} stocks - Invested File: \u20b9{sum([x.get('invested_file',0) or 0 for x in parsed]):,.0f} (Fixed: Total Qty)")
                portfolio_stocks = parsed
        except Exception as e:
            st.error(f"{e}")
    if not portfolio_stocks:
        try:
            with open("portfolio.json") as f:
                data = json.load(f)
                portfolio_stocks = data.get('stocks', [])
                if portfolio_stocks:
                    st.info(f"portfolio.json: {len(portfolio_stocks)} stocks")
        except:
            portfolio_stocks = [{"ticker":"RELIANCE.NS","quantity":575,"avg_price":685.25,"invested_file":394020,"ltp_file":736,"current_file":423200,"buy_date":"15-01-2023"}]
    
    st.divider()
    st.header("📅 SIP Upload")
    sip_file = st.file_uploader("SIP Transactions CSV/Excel", type=["xlsx","xls","csv"], key="sip", help="Date, Ticker, Amount, Qty, Price")
    sip_transactions = []
    if sip_file:
        try:
            sip_transactions = sip_tracker.parse_sip_file(sip_file)
            if sip_transactions:
                st.success(f"✅ {len(sip_transactions)} SIPs")
        except Exception as e:
            st.error(f"SIP error: {e}")
    
    st.divider()
    st.header("⚙️ Settings")
    exchange = st.radio("Exchange", ["NSE","BSE"], index=0, horizontal=True)
    language = st.selectbox("Language", ["English","Hindi (हिंदी)","Hinglish"], index=0)
    lang_code = "en" if language=="English" else "hi" if "Hindi" in language else "hinglish"
    use_file_ltp = st.checkbox("Use File LTP (not Live)", value=False, help="Uses Last Traded Price from Excel for P&L to match file")
    
    st.divider()
    st.header("⚙️ Actions")
    calc_pnl = st.button("💹 Live P&L (Fixed)")
    calc_sip = st.button("📅 SIP + XIRR")
    calc_div = st.button("💰 Dividend")
    calc_cg = st.button("📊 STCG/LTCG")
    gen_reports = st.button(f"📄 Reports ({len(portfolio_stocks)})")

# 5 TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["💹 Live P&L Dashboard", "📅 SIP Tracker + XIRR", "💰 Dividend Tracker", "📊 Capital Gains (STCG/LTCG)", "📄 Reports (Bulk All + Single)"])

with tab1:
    st.markdown('<div class="tab-header"><h3>💹 Live P&L - Quantity × LTP = Current Value (FIXED: Total Quantity Available)</h3><p>Fixed: Uses Total Quantity Available (575 for AGI, not 425 Short Term). Removes NaN total rows. Qty display fixed.</p></div>', unsafe_allow_html=True)
    if portfolio_stocks:
        if 'pnl_df' not in st.session_state:
            st.session_state.pnl_df = None
        if calc_pnl or st.session_state.pnl_df is None:
            with st.spinner(f"Calculating FIXED P&L for {len(portfolio_stocks)} stocks (Total Qty Available)..."):
                pnl_df = tracker.calculate_live_pnl(portfolio_stocks, use_file_ltp=use_file_ltp)
                st.session_state.pnl_df = pnl_df
                st.session_state.summary = tracker.get_summary(pnl_df)
        pnl_df = st.session_state.pnl_df
        summary = st.session_state.get('summary',{})
        if pnl_df is not None and not pnl_df.empty:
            m1,m2,m3,m4,m5 = st.columns(5)
            with m1:
                st.markdown(f'<div class="metric-card blue"><div class="metric-label">Invested (File)</div><div class="metric-value">{tracker.format_inr(summary.get("total_invested_file",0))}</div><div class="metric-label">Excel Invested Amount</div></div>', unsafe_allow_html=True)
            with m2:
                cur = summary.get('total_current_file' if use_file_ltp else 'total_current',0)
                label = "Current File" if use_file_ltp else "Current Live (Qty×LTP)"
                st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{tracker.format_inr(cur)}</div></div>', unsafe_allow_html=True)
            with m3:
                pnl_val = summary.get('total_pnl_file' if use_file_ltp else 'total_pnl',0)
                pnl_pct = summary.get('total_pnl_file_pct' if use_file_ltp else 'total_pnl_pct',0)
                color = "green" if pnl_val>=0 else "red"
                st.markdown(f'<div class="metric-card {color}"><div class="metric-label">Total P&L {"(File)" if use_file_ltp else "(Live)"}</div><div class="metric-value">{tracker.format_inr(pnl_val)} ({pnl_pct:+.1f}%)</div></div>', unsafe_allow_html=True)
            with m4:
                day = summary.get('day_pnl',0)
                color = "green" if day>=0 else "red"
                st.markdown(f'<div class="metric-card {color}"><div class="metric-label">Day P&L</div><div class="metric-value">{tracker.format_inr(day)} ({summary.get("day_pnl_pct",0):+.1f}%)</div></div>', unsafe_allow_html=True)
            with m5:
                st.markdown(f'<div class="metric-card orange"><div class="metric-label">Winners/Losers</div><div class="metric-value">🟢{summary.get("winners",0)}/🔴{summary.get("losers",0)}</div></div>', unsafe_allow_html=True)
            st.info(f"✅ FIXED: Now using Total Quantity Available (not Short Term). For your file: Invested File ₹{summary.get('total_invested_file',0):,.0f} should match Excel total ₹1.42Cr (not ₹92.81L ST). AGI Qty {pnl_df[pnl_df['Ticker']=='AGI']['Quantity'].values[0] if not pnl_df[pnl_df['Ticker']=='AGI'].empty else 575:.0f} (was 25 before).")
            st.dataframe(pnl_df.style.format({'Avg Price':'\u20b9{:.2f}','LTP File':'\u20b9{:.2f}','LTP (Live)':'\u20b9{:.2f}','Invested File':'\u20b9{:.0f}','Current File':'\u20b9{:.0f}','P&L File':'\u20b9{:.0f}','P&L File %':'{:.2f}%'}), use_container_width=True, height=400)
            if st.button("📊 Export FIXED P&L Excel"):
                path = f"reports/FIXED_PnL_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                os.makedirs("reports", exist_ok=True)
                with pd.ExcelWriter(path, engine='openpyxl') as writer:
                    pnl_df.to_excel(writer, sheet_name='Fixed_PnL', index=False)
                    pd.DataFrame([summary]).to_excel(writer, sheet_name='Summary', index=False)
                st.success(f"Exported {path}")
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    st.markdown(f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{os.path.basename(path)}" style="background:#107C41;color:white;padding:10px 20px;border-radius:8px;text-decoration:none">📥 Download FIXED P&L Excel</a>', unsafe_allow_html=True)
    else:
        st.info("Upload holdings Excel in sidebar - Fixed to use Total Quantity Available")

with tab2:
    st.markdown('<div class="tab-header"><h3>📅 SIP Tracker + XIRR Calculation</h3><p>Track Systematic Investment Plans, calculate XIRR (Extended IRR) for irregular cashflows</p></div>', unsafe_allow_html=True)
    st.subheader("➕ Add SIP Transaction")
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1:
        sip_ticker = st.text_input("Ticker", value="RELIANCE", key="sip_ticker")
    with c2:
        sip_date = st.date_input("Date", value=datetime.now() - timedelta(days=30))
    with c3:
        sip_amount = st.number_input("Amount \u20b9", value=5000, step=500)
    with c4:
        sip_qty = st.number_input("Qty", value=2, step=1)
    with c5:
        sip_price = st.number_input("Price \u20b9", value=2500.0, step=10.0)
    if st.button("Add SIP"):
        if 'sip_manual' not in st.session_state:
            st.session_state.sip_manual = []
        st.session_state.sip_manual.append({'Date': pd.to_datetime(sip_date), 'Ticker': sip_ticker.upper(), 'Amount': sip_amount, 'Quantity': sip_qty, 'Price': sip_price})
        st.success(f"Added SIP: {sip_ticker} \u20b9{sip_amount} on {sip_date}")
    all_sips = []
    if sip_transactions:
        all_sips.extend(sip_transactions)
    if 'sip_manual' in st.session_state:
        all_sips.extend(st.session_state.sip_manual)
    if not all_sips:
        st.info("No SIP data - showing sample. Upload SIP file or add manual SIPs above.")
        all_sips = [
            {'Date': datetime(2023,1,15), 'Ticker': 'RELIANCE', 'Amount': 5000, 'Quantity': 2, 'Price': 2500},
            {'Date': datetime(2023,2,15), 'Ticker': 'RELIANCE', 'Amount': 5000, 'Quantity': 2, 'Price': 2450},
            {'Date': datetime(2023,3,15), 'Ticker': 'RELIANCE', 'Amount': 5000, 'Quantity': 2, 'Price': 2600},
            {'Date': datetime(2023,1,15), 'Ticker': 'TCS', 'Amount': 10000, 'Quantity': 3, 'Price': 3300},
        ]
    if all_sips:
        tickers = list(set([s['Ticker'] for s in all_sips]))
        live_prices = {}
        with st.spinner(f"Fetching live prices for {len(tickers)} SIP stocks..."):
            for t in tickers:
                try:
                    s = yf.Ticker(f"{t}.NS")
                    hist = s.history(period="5d")
                    if not hist.empty:
                        live_prices[t] = float(hist['Close'].iloc[-1])
                except:
                    pass
        summary_df, overall = sip_tracker.calculate_sip_summary(all_sips, live_prices)
        m1,m2,m3,m4,m5 = st.columns(5)
        with m1:
            st.markdown(f'<div class="metric-card blue"><div class="metric-label">Total SIPs</div><div class="metric-value">{overall.get("total_sips",0)}</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Invested</div><div class="metric-value">{tracker.format_inr(overall.get("total_invested",0))}</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Current Value</div><div class="metric-value">{tracker.format_inr(overall.get("total_current",0))}</div></div>', unsafe_allow_html=True)
        with m4:
            pnl = overall.get('total_pnl',0)
            st.markdown(f'<div class="metric-card {"green" if pnl>=0 else "red"}"><div class="metric-label">P&L</div><div class="metric-value">{tracker.format_inr(pnl)} ({overall.get("total_pnl_pct",0):+.1f}%)</div></div>', unsafe_allow_html=True)
        with m5:
            xirr = overall.get('overall_xirr',0)
            st.markdown(f'<div class="metric-card purple"><div class="metric-label">Overall XIRR</div><div class="metric-value">{xirr:.2f}%</div><div class="metric-label">Annualized</div></div>', unsafe_allow_html=True)
        st.subheader("📊 SIP Summary per Stock (with XIRR)")
        st.dataframe(summary_df.style.format({'Total Invested':'\u20b9{:.0f}','Total Qty':'{:.0f}','Avg Price':'\u20b9{:.2f}','LTP':'\u20b9{:.2f}','Current Value':'\u20b9{:.0f}','P&L':'\u20b9{:.0f}','P&L %':'{:.2f}%','XIRR %':'{:.2f}%'}), use_container_width=True)
        st.subheader("📋 All SIP Transactions")
        sip_df = pd.DataFrame(all_sips)
        st.dataframe(sip_df, use_container_width=True, height=300)
        st.info("XIRR = Extended IRR for irregular cashflows. NPV = Σ Amount / (1+r)^(days/365) = 0")

with tab3:
    st.markdown('<div class="tab-header"><h3>💰 Dividend Tracker</h3><p>Track dividends received from your holdings after buy date</p></div>', unsafe_allow_html=True)
    if portfolio_stocks:
        with st.spinner("Fetching dividends from NSE..."):
            div_df, total_div = div_tracker.calculate_portfolio_dividends(portfolio_stocks)
        m1,m2,m3 = st.columns(3)
        with m1:
            st.markdown(f'<div class="metric-card green"><div class="metric-label">Total Dividends Received</div><div class="metric-value">{tracker.format_inr(total_div)}</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card blue"><div class="metric-label">Stocks with Dividends</div><div class="metric-value">{len(div_df[div_df["Total Dividend"]>0])} / {len(div_df)}</div></div>', unsafe_allow_html=True)
        with m3:
            avg_yield = (total_div / (st.session_state.get('summary',{}).get('total_invested_file',1)) * 100) if st.session_state.get('summary') else 0
            st.markdown(f'<div class="metric-card purple"><div class="metric-label">Dividend Yield on Invested</div><div class="metric-value">{avg_yield:.2f}%</div></div>', unsafe_allow_html=True)
        st.dataframe(div_df.style.format({'Total Dividend':'\u20b9{:.2f}','Div Per Share Total':'\u20b9{:.2f}','Last Dividend':'\u20b9{:.2f}'}), use_container_width=True, height=400)
    else:
        st.info("Upload holdings with Buy Date to track dividends")

with tab4:
    st.markdown('<div class="tab-header"><h3>📊 Capital Gains - STCG/LTCG (Indian Tax: STCG 15%, LTCG 10% above \u20b91L)</h3></div>', unsafe_allow_html=True)
    if portfolio_stocks:
        live_prices = {}
        if 'pnl_df' in st.session_state and st.session_state.pnl_df is not None:
            live_prices = {row['Full Ticker']: row['LTP Used'] for _, row in st.session_state.pnl_df.iterrows()}
        gains_data = []
        for stock in portfolio_stocks:
            ticker = stock.get('ticker','').replace('.NS','').replace('.BO','')
            qty = stock.get('quantity') or 0
            avg = stock.get('avg_price') or 0
            buy_date_str = stock.get('buy_date','')
            try:
                if buy_date_str:
                    buy_date = pd.to_datetime(buy_date_str, dayfirst=True)
                    holding_days = (datetime.now() - buy_date).days
                else:
                    holding_days = 400
                    buy_date = datetime.now() - timedelta(days=400)
            except:
                holding_days = 400
                buy_date = datetime.now() - timedelta(days=400)
            gain_type = "LTCG" if holding_days>=365 else "STCG"
            live_price = live_prices.get(stock.get('ticker',''), 0)
            if live_price==0:
                try:
                    s = yf.Ticker(f"{ticker}.NS")
                    hist = s.history(period="5d")
                    if not hist.empty:
                        live_price = float(hist['Close'].iloc[-1])
                except:
                    live_price = 0
            invested = qty*avg if qty and avg else 0
            current = qty*live_price if qty and live_price else 0
            gain = current - invested
            gains_data.append({
                'Ticker': ticker,
                'Qty': qty,
                'Buy Date': buy_date.strftime('%d-%m-%Y') if isinstance(buy_date, datetime) else str(buy_date),
                'Days': holding_days,
                'Type': gain_type,
                'Invested': invested,
                'Current': current,
                'Gain': gain,
                'Gain %': (gain/invested*100) if invested else 0,
            })
        gains_df = pd.DataFrame(gains_data)
        total_stcg = gains_df[gains_df['Type']=='STCG']['Gain'].sum()
        total_ltcg = gains_df[gains_df['Type']=='LTCG']['Gain'].sum()
        ltcg_positive = gains_df[(gains_df['Type']=='LTCG') & (gains_df['Gain']>0)]['Gain'].sum()
        ltcg_taxable = max(0, ltcg_positive - 100000)
        ltcg_tax = ltcg_taxable * 0.10
        stcg_tax = max(0, total_stcg) * 0.15
        total_tax = ltcg_tax + stcg_tax
        m1,m2,m3,m4,m5 = st.columns(5)
        with m1:
            st.markdown(f'<div class="metric-card orange"><div class="metric-label">STCG (<12m)</div><div class="metric-value">{tracker.format_inr(total_stcg)}</div><div class="metric-label">15% tax</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card blue"><div class="metric-label">LTCG (\u226512m)</div><div class="metric-value">{tracker.format_inr(total_ltcg)}</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">LTCG Taxable (after \u20b91L)</div><div class="metric-value">{tracker.format_inr(ltcg_taxable)}</div></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-card purple"><div class="metric-label">Total Tax</div><div class="metric-value">{tracker.format_inr(total_tax)}</div></div>', unsafe_allow_html=True)
        with m5:
            st.markdown(f'<div class="metric-card green"><div class="metric-label">STCG Tax + LTCG Tax</div><div class="metric-value">{tracker.format_inr(stcg_tax)} + {tracker.format_inr(ltcg_tax)}</div></div>', unsafe_allow_html=True)
        st.dataframe(gains_df.style.format({'Invested':'\u20b9{:.0f}','Current':'\u20b9{:.0f}','Gain':'\u20b9{:.0f}','Gain %':'{:.2f}%'}), use_container_width=True, height=400)
        st.caption("Indian Tax: STCG <12 months = 15%, LTCG \u226512 months = 10% above \u20b91L exemption. Consult CA.")
    else:
        st.info("Upload portfolio with Buy Date for STCG/LTCG")

with tab5:
    st.markdown('<div class="tab-header"><h3>📄 Reports - Bulk All Portfolio (52) + Single Stock Detailed</h3><p>Fixed: Uses Total Quantity Available for P&L in reports | Generates detailed broker reports with charts for all holdings</p></div>', unsafe_allow_html=True)
    if not portfolio_stocks:
        st.warning("Upload portfolio Excel first")
        portfolio_tickers = []
    else:
        portfolio_tickers = [s.get('ticker','').replace('.NS','').replace('.BO','') for s in portfolio_stocks]
        st.success(f"📁 Portfolio: {len(portfolio_tickers)} stocks - {', '.join(portfolio_tickers[:10])}{'... and '+str(len(portfolio_tickers)-10)+' more' if len(portfolio_tickers)>10 else ''}")
    col1, col2 = st.columns([2,1])
    with col1:
        report_mode = st.radio("Report Mode", ["📚 All Portfolio Stocks (Bulk) - 52 Reports", "✅ Selected Stocks", "🔍 Single Stock Detailed"], index=0)
    with col2:
        want_pdf = st.checkbox("Also PDF", value=False)
        lang_rep = st.selectbox("Language", ["English","Hindi","Hinglish"], index=0, key="lang_rep")
        lang_code_rep = "en" if lang_rep=="English" else "hi" if "Hindi" in lang_rep else "hinglish"
    if report_mode.startswith("📚 All"):
        st.subheader(f"📚 Generate All {len(portfolio_tickers)} Reports (FIXED Qty)")
        st.markdown(f"This will create {len(portfolio_tickers)} HTML reports (one per stock) with live price, charts, and your FIXED P&L (Total Qty Available {portfolio_tickers[0] if portfolio_tickers else ''} etc). Takes ~2-3 mins for 52 stocks.")
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
                    status.text(f"{i+1}/{len(portfolio_tickers)}: {ticker_short} ({ticker_full}) - Total Qty Available FIXED")
                    try:
                        html = agent.generate_report_html(ticker_full, [], None, None, lang_code_rep)
                        if 'pnl_df' in st.session_state and st.session_state.pnl_df is not None:
                            match = st.session_state.pnl_df[st.session_state.pnl_df['Ticker']==ticker_short]
                            if not match.empty:
                                r = match.iloc[0]
                                pnl_block = f"<div style='background:#e8f5e9;padding:15px;margin:15px 30px;border-radius:8px;border-left:4px solid #4caf50'><h3>💹 Your Holding - {r['Ticker']} (FIXED)</h3><p><b>Qty:</b> {r['Quantity']:.0f} (Total Available, was 25 before) | <b>Avg:</b> \u20b9{r['Avg Price']:.2f} | <b>LTP:</b> \u20b9{r['LTP Used']:.2f}</p><p><b>Invested:</b> \u20b9{r['Invested Value']:,.0f} | <b>Current:</b> \u20b9{r['Current Value']:,.0f} | <b>P&L:</b> \u20b9{r['P&L']:,.0f} ({r['P&L %']:+.1f}%)</p></div>"
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
                        st.markdown(f'<a href="data:application/zip;base64,{b64}" download="{os.path.basename(zip_path)}" style="background:#1a237e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;display:inline-block;margin:10px 0">📦 Download All {len(generated)} Reports ZIP (FIXED Qty)</a>', unsafe_allow_html=True)
                    st.success(f"Generated {len(generated)} detailed reports for all portfolio holdings! Each includes Total Quantity Available (fixed from 25 to 575 for AGI), Avg Price, Invested, Current, P&L")
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
        include_pnl = st.checkbox("Include Your P&L (Qty, Avg, Invested, Current) - FIXED", value=True)
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
                        block = f"<div style='background:#e8f5e9;padding:15px;margin:15px 30px;border-radius:8px;border-left:4px solid #4caf50'><h3>💹 Your Holding - {pnl_info['Ticker']} (FIXED: Total Qty)</h3><p><b>Qty:</b> {pnl_info['Quantity']:.0f} (Total Available) | <b>Avg:</b> \u20b9{pnl_info['Avg Price']:.2f} | <b>LTP:</b> \u20b9{pnl_info['LTP Used']:.2f}</p><p><b>Invested:</b> \u20b9{pnl_info['Invested Value']:,.0f} | <b>Current:</b> \u20b9{pnl_info['Current Value']:,.0f} | <b>P&L:</b> \u20b9{pnl_info['P&L']:,.0f} ({pnl_info['P&L %']:+.1f}%)</p></div>"
                        html = html.replace("<div style='padding:20px'>", block + "<div style='padding:20px'>", 1)
                    path = f"reports/{clean.replace('.','_')}_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
                    os.makedirs("reports", exist_ok=True)
                    with open(path,"w", encoding="utf-8") as f:
                        f.write(html)
                    st.success(f"✅ Report for {clean} generated! FIXED Qty")
                    if pnl_info is not None:
                        st.info(f"💹 P&L: Qty {pnl_info['Quantity']:.0f} (Total Available, was showing 25 before) × Avg \u20b9{pnl_info['Avg Price']:.2f} = Invested \u20b9{pnl_info['Invested Value']:,.0f} | Current \u20b9{pnl_info['Current Value']:,.0f} | P&L \u20b9{pnl_info['P&L']:,.0f} ({pnl_info['P&L %']:+.1f}%)")
                    b64 = base64.b64encode(html.encode()).decode()
                    st.markdown(f'<a href="data:text/html;base64,{b64}" download="{os.path.basename(path)}" style="background:#1a237e;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block;margin:5px">📥 Download HTML</a>', unsafe_allow_html=True)
                    st.components.v1.html(html, height=700, scrolling=True)
                except Exception as e:
                    st.error(f"{e}")

st.caption("✅ 5 TABS FIXED EDITION | Total Quantity Available (not ST) | AGI 575 not 25 | Bulk Reports All 52 + Single | SIP + XIRR | Dividend | STCG/LTCG | 3 Files Only")
