import pandas as pd
import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import re
import os

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    # 1. 사용자가 다운로드/업로드한 로컬 CSV 파일이 있으면 최우선으로 읽음
    try:
        csv_path = "krx_stock_list.csv"  # 다운로드 후 앱 폴더에 이 이름으로 넣으면 됨
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            # 호환성을 위해 컬럼명 강제 매핑
            col_map = {}
            for c in df.columns:
                if "코드" in c or "code" in c.lower(): col_map[c] = "종목코드"
                elif "명" in c or "name" in c.lower(): col_map[c] = "회사명"
                elif "섹터" in c or "업종" in c: col_map[c] = "섹터"
            df = df.rename(columns=col_map)
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            if '섹터' not in df.columns: df['섹터'] = '기타'
            return df[['종목코드', '회사명', '섹터']].dropna()
    except: pass

    # 2. 로컬 파일이 없으면 한국거래소(KRX) 실시간 수집 시도
    try:
        df = fdr.StockListing('KRX')
        if not df.empty:
            df = df.rename(columns={'Code': '종목코드', 'Name': '회사명', 'Sector': '섹터'})
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            return df[['종목코드', '회사명', '섹터']].dropna()
    except: pass

    # 3. 전부 실패했을 때를 대비한 최후의 비상용 데이터 (IREN, BTQ 등 핵심 종목 포함)
    return pd.DataFrame([
        {'회사명': '삼성전자', '종목코드': '005930', '섹터': '반도체'},
        {'회사명': 'SK하이닉스', '종목코드': '000660', '섹터': '반도체'},
        {'회사명': 'LG', '종목코드': '003550', '섹터': '지주사'},
        {'회사명': '휴림로봇', '종목코드': '090710', '섹터': '로봇'},
        {'회사명': 'IREN', '종목코드': 'IREN', '섹터': '미국주식'},
        {'회사명': 'BTQ', '종목코드': 'BTQ', '섹터': '미국주식'}
    ])

def search_candidates(query, limit=15):
    df = get_stock_db()
    q = (query or "").strip().upper()
    if not q: return df.head(0)
    
    # 회사명에 검색어가 '포함'만 되어도 모두 검색 (자동완성 기능)
    results = df[df["회사명"].str.upper().str.contains(q, na=False)].copy()
    
    # 영문 티커 바로 검색 지원
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
            
            return {
                "current": float(df['Close'].iloc[-1]),
                "prev_close": float(df['Close'].iloc[-2]),
                "volume": float(df['Volume'].iloc[-1]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except: return None
