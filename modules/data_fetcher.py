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
            # 🌟 dtype=str 로 읽어서 종목코드 앞의 '0'이 날아가는 현상 방지
            try:
                df = pd.read_csv(csv_path, encoding='utf-8', dtype=str)
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, encoding='cp949', dtype=str)
            
            rename_dict = {}
            for col in df.columns:
                if col in ['단축코드', '종목코드', 'Code']: rename_dict[col] = '종목코드'
                elif col in ['한글 종목명', '종목명', '회사명', 'Name']: rename_dict[col] = '회사명'
                elif col in ['시장구분', '업종명', '섹터', 'Sector']: rename_dict[col] = '섹터'
            
            df = df.rename(columns=rename_dict)
            df = df.loc[:, ~df.columns.duplicated()]
            
            if '종목코드' in df.columns and '회사명' in df.columns:
                df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                # 회사명 앞뒤 공백 제거 및 텍스트화
                df['회사명'] = df['회사명'].astype(str).str.strip() 
                if '섹터' not in df.columns: df['섹터'] = '기타'
                return df[['종목코드', '회사명', '섹터']].dropna()
        except Exception as e:
            print(f"CSV 로드 에러: {e}")

    # 2. 비상용 기본 데이터
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
    
    # 🌟 띄어쓰기 무시 검색: 'HD현대'나 'HD 현대' 모두 검색되도록 강력하게 수정
    q_no_space = q.replace(" ", "")
    df['검색용회사명'] = df['회사명'].str.replace(" ", "").str.upper()
    
    results = df[df["검색용회사명"].str.contains(q_no_space, na=False)].copy()
    results = results.drop(columns=['검색용회사명']) # 임시 컬럼 삭제
    
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
