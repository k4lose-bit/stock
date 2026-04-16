import pandas as pd
import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import re
from io import BytesIO

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    try:
        # 🌟 KRX에서 실시간으로 가져오되, 실패하면 내장 데이터를 씁니다.
        df = fdr.StockListing('KRX')
        if not df.empty:
            df = df.rename(columns={'Code': '종목코드', 'Name': '회사명', 'Sector': '섹터'})
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            return df[['종목코드', '회사명', '섹터']].dropna()
    except:
        pass
    # 기본 백업 데이터
    return pd.DataFrame([
        {'회사명': '삼성전자', '종목코드': '005930', '섹터': '반도체'},
        {'회사명': 'LG', '종목코드': '003550', '섹터': '지주사'},
        {'회사명': 'IREN', '종목코드': 'IREN', '섹터': '미국주식'}
    ])

def search_candidates(query, limit=15):
    df = get_stock_db()
    q = (query or "").strip().upper()
    if not q: return df.head(0)
    results = df[df["회사명"].str.upper().str.contains(q, na=False)].copy()
    if re.match(r'^[A-Z]+$', q):
        us_row = pd.DataFrame([{'회사명': q, '종목코드': q, '섹터': '미국 주식'}])
        results = pd.concat([us_row, results])
    return results.drop_duplicates(subset=['종목코드']).head(limit)

class DataFetcher:
    @st.cache_data(ttl=600)
    def get_stock_data(_self, code):
        try:
            symbol = f"{code}.KS" if (code.isdigit() and len(code) == 6) else code
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
            if df.empty and code.isdigit():
                df = yf.Ticker(f"{code}.KQ").history(period="3mo")
            if df is None or len(df) < 2: return None
            
            return {
                "current": float(df['Close'].iloc[-1]),
                "prev_close": float(df['Close'].iloc[-2]),
                "volume": float(df['Volume'].iloc[-1]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except: return None
