import pandas as pd
import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import re
import os
from io import StringIO

EMBEDDED_MINI_CSV = """
회사명,종목코드,섹터
삼성전자,005930,기타
SK하이닉스,000660,기타
NAVER,035420,AI
네이버,035420,AI
카카오,035720,AI
휴림로봇,090710,로봇
IREN,IREN,미국 주식
BTQ,BTQ,미국 주식
""".strip()

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    # 1. 시도: FinanceDataReader (Streamlit 클라우드에서 KRX 차단될 수 있음)
    try:
        df = fdr.StockListing('KRX')
        if not df.empty and 'Code' in df.columns and 'Name' in df.columns:
            df = df.rename(columns={'Code': '종목코드', 'Name': '회사명', 'Sector': '섹터'})
            if '섹터' not in df.columns:
                df['섹터'] = '기타'
            df['섹터'] = df['섹터'].fillna('기타')
            df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
            return df[['종목코드', '회사명', '섹터']].dropna().reset_index(drop=True)
    except Exception as e:
        pass

    # 2. 시도: 클라우드 차단 시 깃허브에 있는 krx_stock_list.csv 자동 사용
    try:
        if os.path.exists("krx_stock_list.csv"):
            df = pd.read_csv("krx_stock_list.csv")
            col_map = {}
            lower_cols = {c.lower(): c for c in df.columns}
            for cand in ["회사명", "name", "corp_name", "company", "companyname"]:
                if cand.lower() in lower_cols: col_map[lower_cols[cand.lower()]] = "회사명"; break
            for cand in ["종목코드", "code", "symbol", "ticker"]:
                if cand.lower() in lower_cols: col_map[lower_cols[cand.lower()]] = "종목코드"; break
            for cand in ["섹터", "sector", "업종", "industry"]:
                if cand.lower() in lower_cols: col_map[lower_cols[cand.lower()]] = "섹터"; break
            
            df = df.rename(columns=col_map)
            if '섹터' not in df.columns: df['섹터'] = '기타'
            df['종목코드'] = df['종목코드'].astype(str).str.extract(r"(\d+)")[0].fillna(df["종목코드"].astype(str)).str.zfill(6)
            return df[['종목코드', '회사명', '섹터']].dropna().reset_index(drop=True)
    except Exception as e:
        pass

    # 3. 최후의 보루: 내장 미니 데이터
    df = pd.read_csv(StringIO(EMBEDDED_MINI_CSV))
    df['종목코드'] = df['종목코드'].astype(str)
    return df

def search_candidates(query, limit=20):
    df = get_stock_db()
    q = (query or "").strip().upper()
    if not q: return df.head(0)

    # 영문(미국 티커) 입력 시 검색 결과에 바로 띄워줌
    if re.match(r'^[A-Z]+$', q):
        us_row = pd.DataFrame([{'회사명': q, '종목코드': q, '섹터': '미국 주식'}])
        name_norm = df["회사명"].astype(str).str.replace(" ", "", regex=False).str.upper()
        exact = df[name_norm == q]
        part = df[name_norm.str.contains(q, na=False)]
        return pd.concat([us_row, exact, part]).head(limit)

    name_norm = df["회사명"].astype(str).str.replace(" ", "", regex=False).str.upper()
    exact = df[name_norm == q]
    if not exact.empty: return exact.head(limit)
    return df[name_norm.str.contains(q, na=False)].head(limit)

class DataFetcher:
    def __init__(self):
        pass

    @st.cache_data(ttl=600)
    def get_stock_data_live(_self, code):
        try:
            # 종목코드가 숫자 6자리인 경우 한국 주식 (yfinance 포맷 변환)
            if code.isdigit() and len(code) == 6:
                stock = yf.Ticker(code + ".KS") # 코스피 먼저 시도
                df = stock.history(period="3mo")
                if df.empty:
                    stock = yf.Ticker(code + ".KQ") # 없으면 코스닥 시도
                    df = stock.history(period="3mo")
            else:
                # 그 외 영문 코드는 미국 주식으로 인식 (예: IREN, BTQ)
                stock = yf.Ticker(code)
                df = stock.history(period="3mo")

            if df is None or df.empty or len(df) < 35:
                return None

            return {
                "current": float(df.iloc[-1]["Close"]),
                "open": float(df.iloc[-1]["Open"]),
                "prev_close": float(df.iloc[-2]["Close"]),
                "volume": float(df.iloc[-1]["Volume"]),
                "close_prices": df["Close"].astype(float).tolist(),
                "volumes": df["Volume"].astype(float).tolist(),
            }
        except Exception: 
            return None

    def get_stock_data(self, code):
        offline_map = st.session_state.get("offline_price_data", {})
        if isinstance(offline_map, dict) and code in offline_map:
            return offline_map[code]
        return self.get_stock_data_live(code)
