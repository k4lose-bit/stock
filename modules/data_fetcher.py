import pandas as pd
import streamlit as st
import yfinance as yf
import re
import os

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    # 1. 깃허브/스트림릿 저장소에 올라가 있는 CSV 파일 우선 읽기
    csv_path = "krx_stock_list.csv"
    if os.path.exists(csv_path):
        try:
            # KRX 인코딩 문제(cp949 vs utf-8) 자동 해결
            try:
                df = pd.read_csv(csv_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, encoding='cp949')
            
            # KRX 다운로드 포맷에 맞춘 컬럼명 자동 매핑
            rename_dict = {}
            for col in df.columns:
                if col in ['단축코드', '종목코드', 'Code']: rename_dict[col] = '종목코드'
                elif col in ['한글 종목명', '종목명', '회사명', 'Name']: rename_dict[col] = '회사명'
                elif col in ['시장구분', '업종명', '섹터', 'Sector']: rename_dict[col] = '섹터'
            
            df = df.rename(columns=rename_dict)
            
            # 'DataFrame' object has no attribute 'str' 오류 방지 (중복 컬럼 제거)
            df = df.loc[:, ~df.columns.duplicated()]
            
            if '종목코드' in df.columns and '회사명' in df.columns:
                df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                if '섹터' not in df.columns: df['섹터'] = '기타'
                return df[['종목코드', '회사명', '섹터']].dropna()
        except Exception as e:
            print(f"CSV 로드 에러: {e}")

    # 2. 파일이 없거나 깨졌을 때를 대비한 비상용 기본 데이터
    return pd.DataFrame([
        {'회사명': '삼성전자', '종목코드': '005930', '섹터': '반도체'},
        {'회사명': 'SK하이닉스', '종목코드': '000660', '섹터': '반도체'},
        {'회사명': 'LG', '종목코드': '003550', '섹터': '지주사'},
        {'회사명': '휴림로봇', '종목코드': '090710', '섹터': '로봇'},
        {'회사명': 'LK삼양', '종목코드': '225190', '섹터': '기계'},
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
                "open": float(df['Open'].iloc[-1]),
                "prev_close": float(df['Close'].iloc[-2]),
                "volume": float(df['Volume'].iloc[-1]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except: return None
