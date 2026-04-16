import pandas as pd
import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import re
import os
from io import StringIO

# 기본 데이터베이스 (수집 실패 시 보조용)
EMBEDDED_MINI_CSV = """
회사명,종목코드,섹터
삼성전자,005930,반도체
SK하이닉스,000660,반도체
IREN,IREN,미국주식
BTQ,BTQ,미국주식
LG,003550,지주사
""".strip()

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    try:
        df = fdr.StockListing('KRX')
        if not df.empty:
            df = df.rename(columns={'Code': '종목코드', 'Name': '회사명', 'Sector': '섹터'})
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            return df[['종목코드', '회사명', '섹터']].dropna()
    except: pass
    return pd.read_csv(StringIO(EMBEDDED_MINI_CSV))

def search_candidates(query, limit=10):
    df = get_stock_db()
    q = (query or "").strip().upper()
    if not q: return df.head(0)
    
    # 영문 티커 우선 검색 (미국주식 대응)
    if re.match(r'^[A-Z]+$', q):
        us_row = pd.DataFrame([{'회사명': q, '종목코드': q, '섹터': '미국 주식'}])
        part = df[df["회사명"].str.upper().str.contains(q, na=False)]
        return pd.concat([us_row, part]).head(limit)
        
    return df[df["회사명"].str.contains(q, na=False)].head(limit)

class DataFetcher:
    @st.cache_data(ttl=600)
    def get_stock_data(_self, code):
        try:
            # 🌟 코드 형식에 따른 자동 심볼 보정 (LG -> 003550.KS 등)
            symbol = code
            if code.isdigit() and len(code) == 6:
                symbol = f"{code}.KS" # 우선 코스피 시도
            
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
            
            # 코스피 실패 시 코스닥 시도
            if df.empty and code.isdigit():
                symbol = f"{code}.KQ"
                stock = yf.Ticker(symbol)
                df = stock.history(period="3mo")

            if df.empty or len(df) < 5: return None

            return {
                "current": float(df.iloc[-1]["Close"]),
                "prev_close": float(df.iloc[-2]["Close"]),
                "volume": float(df.iloc[-1]["Volume"]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except Exception as e:
            print(f"Data Fetch Error: {e}")
            return None
