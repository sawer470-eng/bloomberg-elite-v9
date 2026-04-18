import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import time

@st.cache_data(ttl=3600)
def fetch_ticker_data(ticker, fallback_google_ticker=None):
    """
    Robust data fetching:
    1. Try yfinance.
    2. If fails, try scraping Google Finance.
    """
    try:
        # Step 1: yfinance
        asset = yf.Ticker(ticker)
        hist = asset.history(period="1mo")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            
            # SCALING FIX: Yahoo Bond Yields (e.g. ^TNX) are returned as Yield * 10
            if any(x in ticker for x in ['^TNX', '^IRX', '^TYX', '^FVX']):
                price = price / 10.0
            
            last_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else last_close
            
            # Recalculate if scaled
            if any(x in ticker for x in ['^TNX', '^IRX', '^TYX', '^FVX']):
                last_val = last_close / 10.0
                prev_val = prev_close / 10.0
            else:
                last_val = last_close
                prev_val = prev_close

            change = last_val - prev_val
            pct_change = (change / prev_val) * 100 if prev_val != 0 else 0
            
            return {
                "price": last_val,
                "change": change,
                "pct_change": pct_change,
                "history": hist['Close'] / (10.0 if any(x in ticker for x in ['^TNX', '^IRX', '^TYX', '^FVX']) else 1.0),
                "source": "Yahoo"
            }
    except Exception as e:
        pass
    
    # Step 2: Google Finance Fallback
    if fallback_google_ticker:
        try:
            url = f"https://www.google.com/finance/quote/{fallback_google_ticker}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Multiple possible selectors for Google Finance (ver. 2024 update)
            price_el = soup.select_one('.YMlKec.fxKbKc') or soup.select_one('.pclqee')
            change_el = soup.select_one('.P6L18e') or soup.select_one('.Jw7X9b')
            
            if price_el:
                price_str = price_el.text.replace('$', '').replace(',', '').replace('+', '').strip()
                price = float(price_str)
                
                pct_val = 0.0
                if change_el:
                    text = change_el.text
                    if '(' in text and '%' in text:
                        # Extract percentage from "+1.23 (1.23%)"
                        parts = text.split('(')
                        if len(parts) > 1:
                            pct_str = parts[1].split('%')[0].replace('+', '').replace('-', '').strip()
                            pct_val = float(pct_str)
                            if '-' in text or '▼' in text:
                                pct_val = -pct_val
                
                return {
                    "price": price,
                    "change": (price * pct_val / 100),
                    "pct_change": pct_val,
                    "history": pd.Series([price] * 20), # Fallback history
                    "source": "Google (Fallback)"
                }
        except:
            pass
            
    # Final Fallback to prevent UI crashes with NoneType
    return {
        "price": 0.0,
        "change": 0.0,
        "pct_change": 0.0,
        "history": pd.Series([0.0] * 5),
        "source": "N/A (Failed)",
        "is_failed": True
    }

@st.cache_data(ttl=3600)
def fetch_macro_yields():
    tickers = {
        "10Y Yield": ("^TNX", "TNX:INDEXCBOE"),
        "2Y Yield": ("^IRX", "IRX:INDEXCBOE"),
        "30Y Yield": ("^TYX", "TYX:INDEXCBOE")
    }
    
    results = {}
    for name, (yf_tkr, go_tkr) in tickers.items():
        data = fetch_ticker_data(yf_tkr, go_tkr)
        results[name] = data
    return results

def get_ticker_tape_data():
    symbols = {
        "S&P 500": ("^GSPC", "SPY:NYSE"),
        "NASDAQ": ("^NDX", "QQQ:NASDAQ"),
        "GOLD": ("GC=F", "GOLD:COMEX"),
        "CRUDE": ("CL=F", "CL.1:COMEX"),
        "BTC": ("BTC-USD", "BTC-USD")
    }
    
    items = []
    for name, (yf_tkr, go_tkr) in symbols.items():
        data = fetch_ticker_data(yf_tkr, fallback_google_ticker=go_tkr)
        if data and not data.get('is_failed'):
            color = "#66ff00" if data['pct_change'] >= 0 else "#ff0033"
            arrow = "▲" if data['pct_change'] >= 0 else "▼"
            items.append(f"<span style='color:#c5c6c7'>{name}</span> <span style='color:{color}'>{data['price']:,.2f} {arrow} {abs(data['pct_change']):.2f}%</span>")
        else:
            items.append(f"<span style='color:#c5c6c7'>{name}</span> <span style='color:#8b949e'>N/A</span>")
            
    return " &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; ".join(items)
