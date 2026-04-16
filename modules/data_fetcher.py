import pandas as pd
import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import re

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    try:
        # 한국 거래소 전체 리스트 확보
        df = fdr.StockListing('KRX')
        if not df.empty:
            df = df.rename(columns={'Code': '종목코드', 'Name': '회사명', 'Sector': '섹터'})
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            return df[['종목코드', '회사명', '섹터']].dropna()
    except: pass
    # 최소한의 백업 데이터
    return pd.DataFrame([
        {'회사명': '삼성전자', '종목코드': '005930', '섹터': '반도체'},
        {'회사명': 'LG', '종목코드': '003550', '섹터': '지주사'},
        {'회사명': 'IREN', '종목코드': 'IREN', '섹터': '미국주식'},
        {'회사명': 'BTQ', '종목코드': 'BTQ', '섹터': '미국주식'}
    ])

def search_candidates(query, limit=15):
    df = get_stock_db()
    q = (query or "").strip().upper()
    if not q: return df.head(0)
    
    # 🌟 유사 검색 로직: 이름에 포함만 되어도 다 찾아냄
    results = df[df["회사명"].str.upper().str.contains(q, na=False)].copy()
    
    # 영문 티커(IREN 등) 대응
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
                symbol = f"{code}.KQ"
                df = yf.Ticker(symbol).history(period="3mo")

            if df is None or len(df) < 2: return None

            # 🌟 데이터 누락 방어: 안전하게 데이터 꺼내기
            return {
                "current": float(df['Close'].iloc[-1]),
                "prev_close": float(df['Close'].iloc[-2]),
                "volume": float(df['Volume'].iloc[-1]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except: return None
