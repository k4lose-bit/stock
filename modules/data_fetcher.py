import pandas as pd
import streamlit as st
import yfinance as yf
import re
import os

# 🌟 서학개미(해외주식) 전용 스마트 한글-티커 사전
US_STOCK_DICT = {
    "애플": "AAPL", "테슬라": "TSLA", "엔비디아": "NVDA", "마이크로소프트": "MSFT",
    "구글": "GOOGL", "알파벳": "GOOGL", "아마존": "AMZN", "메타": "META", "페이스북": "META",
    "넷플릭스": "NFLX", "에이엠디": "AMD", "인텔": "INTC", "티에스엠씨": "TSM",
    "팔란티어": "PLTR", "아이온큐": "IONQ", "쿠팡": "CPNG", "노키아": "NOK",
    "아이렌": "IREN", "비티큐": "BTQ", "코인베이스": "COIN", "마이크로스트레티지": "MSTR",
    "에이에스엠엘": "ASML", "브로드컴": "AVGO", "퀄컴": "QCOM", "일라이릴리": "LLY",
    "티큐": "TQQQ", "속슬": "SOXL", "슈드": "SCHD", "스파이": "SPY", "큐큐큐": "QQQ"
}

def get_stock_db():
    if "uploaded_db" in st.session_state and st.session_state.uploaded_db is not None:
        return st.session_state.uploaded_db
        
    csv_path = "krx_stock_list.csv"
    if os.path.exists(csv_path):
        try:
            try:
                df = pd.read_csv(csv_path, encoding='utf-8', dtype=str)
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, encoding='cp949', dtype=str)
            
            df.columns = df.columns.str.replace(" ", "")
            col_map = {}
            for c in df.columns:
                if c in ['단축코드', '종목코드', '코드', 'CODE']: col_map[c] = '종목코드'
                elif c in ['한글종목약명', '종목명', '회사명', 'NAME']: col_map[c] = '회사명'
                elif c in ['시장구분', '업종명', '섹터', 'SECTOR']: col_map[c] = '섹터'
                
            if '회사명' not in col_map.values():
                for c in df.columns:
                    if c == '한글종목명': col_map[c] = '회사명'

            df = df.rename(columns=col_map)
            df = df.loc[:, ~df.columns.duplicated()]
            
            if '종목코드' in df.columns and '회사명' in df.columns:
                df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                df['회사명'] = df['회사명'].astype(str).str.strip()
                if '섹터' not in df.columns: df['섹터'] = '기타'
                return df[['종목코드', '회사명', '섹터']].dropna()
        except Exception as e:
            print(f"CSV 로드 에러: {e}")

    return pd.DataFrame([
        {'회사명': '삼성전자', '종목코드': '005930', '섹터': '반도체'},
        {'회사명': 'SK하이닉스', '종목코드': '000660', '섹터': '반도체'},
        {'회사명': 'LG', '종목코드': '003550', '섹터': '지주사'}
    ])

def search_candidates(query, limit=15):
    df = get_stock_db()
    q = (query or "").strip().upper()
    if not q: return df.head(0)
    
    q_no_space = q.replace(" ", "")
    df['검색용회사명'] = df['회사명'].str.replace(" ", "").str.upper()
    
    results = df[df["검색용회사명"].str.contains(q_no_space, na=False)].copy()
    results = results.drop(columns=['검색용회사명'])
    
    if re.match(r'^[A-Z]+$', q):
        us_row = pd.DataFrame([{'회사명': q, '종목코드': q, '섹터': '해외주식'}])
        results = pd.concat([us_row, results])
        
    for kr_name, ticker in US_STOCK_DICT.items():
        if q_no_space in kr_name:
            us_row = pd.DataFrame([{'회사명': kr_name, '종목코드': ticker, '섹터': '해외주식'}])
            results = pd.concat([us_row, results])
            
    return results.drop_duplicates(subset=['종목코드']).head(limit)

class DataFetcher:
    # 🌟 기존 10분(600초) 지연 캐시를 30초로 단축하여 실시간 체감 속도를 높임
    @st.cache_data(ttl=30)
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
                "open": float(df['Open'].iloc[-1]),
                "prev_close": float(df['Close'].iloc[-2]),
                "volume": float(df['Volume'].iloc[-1]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except: return None
