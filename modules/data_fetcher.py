import pandas as pd
import streamlit as st
import yfinance as yf
import re
import os

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    # 🌟 앱 배포 후에는 이 로컬 파일을 읽어오는 것이 가장 확실합니다.
    csv_path = "krx_stock_list.csv"
    if os.path.exists(csv_path):
        try:
            try:
                df = pd.read_csv(csv_path, encoding='utf-8', dtype=str)
            except:
                df = pd.read_csv(csv_path, encoding='cp949', dtype=str)
            
            # 컬럼명 전처리 (에러 방지 핵심)
            df.columns = [str(c).strip().replace(" ", "") for c in df.columns]
            
            col_map = {}
            for c in df.columns:
                if c in ['단축코드', '종목코드', '코드', 'CODE']: col_map[c] = '종목코드'
                elif c in ['한글종목약명', '종목명', '회사명', 'NAME']: col_map[c] = '회사명'
            
            df = df.rename(columns=col_map)
            df = df.loc[:, ~df.columns.duplicated()] # 중복 컬럼 제거
            
            if '종목코드' in df.columns and '회사명' in df.columns:
                # 🌟 str 속성 에러 방지를 위해 강제 형변환 후 처리
                df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                df['회사명'] = df['회사명'].astype(str).str.strip()
                return df[['종목코드', '회사명']].dropna()
        except Exception as e:
            st.error(f"데이터베이스 로드 중 오류: {e}")

    # 비상용 기본 데이터
    return pd.DataFrame([{'회사명': '삼성전자', '종목코드': '005930'}])

def search_candidates(query, limit=15):
    df = get_stock_db()
    q = str(query).strip().upper()
    if not q: return df.head(0)
    
    # 띄어쓰기 무시 검색
    q_no_space = q.replace(" ", "")
    df['search_name'] = df['회사명'].astype(str).str.replace(" ", "").str.upper()
    
    results = df[df["search_name"].str.contains(q_no_space, na=False)].copy()
    
    if re.match(r'^[A-Z]+$', q): # 영문 티커 처리
        us_row = pd.DataFrame([{'회사명': q, '종목코드': q}])
        results = pd.concat([us_row, results])
        
    return results.drop_duplicates(subset=['종목코드']).head(limit)

class DataFetcher:
    def get_stock_data(self, code):
        try:
            symbol = f"{code}.KS" if (str(code).isdigit() and len(str(code)) == 6) else code
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
            if df.empty and str(code).isdigit():
                df = yf.Ticker(f"{code}.KQ").history(period="3mo")
            if df.empty: return None
            
            return {
                "current": float(df['Close'].iloc[-1]),
                "prev_close": float(df['Close'].iloc[-2]),
                "volume": float(df['Volume'].iloc[-1]),
                "close_prices": df["Close"].tolist(),
                "volumes": df["Volume"].tolist(),
                "dates": df.index.strftime('%Y.%m.%d').tolist()
            }
        except: return None
