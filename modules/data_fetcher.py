import pandas as pd
import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import re
import os

@st.cache_data(ttl=60 * 60 * 24)
def _fetch_fdr_krx():
    try:
        df = fdr.StockListing('KRX')
        if not df.empty:
            df = df.rename(columns={'Code': '종목코드', 'Name': '회사명', 'Sector': '섹터'})
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            return df[['종목코드', '회사명', '섹터']].dropna()
    except:
        pass
    return pd.DataFrame()

def get_stock_db():
    # 🌟 1. 세션 스테이트에 사용자가 탭에서 업로드한 파일이 있으면 무조건 1순위로 사용!
    if "uploaded_db" in st.session_state and st.session_state.uploaded_db is not None:
        return st.session_state.uploaded_db
        
    # 2. 앱 폴더(로컬/깃허브)에 저장된 파일이 있으면 2순위로 사용
    try:
        csv_path = "krx_stock_list.csv"
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
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

    # 3. 실시간 서버 데이터 수집 시도 (스트림릿 클라우드에서 차단될 확률 높음)
    fdr_df = _fetch_fdr_krx()
    if not fdr_df.empty:
        return fdr_df

    # 4. 전부 다 실패했을 때의 비상용 최후 보루
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
