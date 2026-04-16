import pandas as pd
import streamlit as st
import yfinance as yf
import re
import os

def get_stock_db():
    # 🌟 핵심 수정: 웹에서 업로드한 데이터가 있으면 무조건 0순위로 읽어옵니다! (이전 코드에서 누락된 부분)
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
                # 🌟 '와이제이링크보통주' 대신 '와이제이링크'를 우선적으로 가져오도록 세팅
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
        {'회사명': 'LG', '종목코드': '003550', '섹터': '지주사'},
        {'회사명': '휴림로봇', '종목코드': '090710', '섹터': '로봇'},
        {'회사명': 'LK삼양', '종목코드': '225190', '섹터': '기계'},
        {'회사명': '와이제이링크', '종목코드': '209640', '섹터': '기타'},
        {'회사명': 'IREN', '종목코드': 'IREN', '섹터': '미국주식'},
        {'회사명': 'BTQ', '종목코드': 'BTQ', '섹터': '미국주식'}
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
                "open": float(df['Open'].iloc[-1]),
                "prev_close": float(df['Close'].iloc[-2]),
                "volume": float(df['Volume'].iloc[-1]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except: return None
