import pandas as pd
import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import re

@st.cache_data(ttl=60 * 60 * 24)
def get_stock_db():
    try:
        # 한국 거래소(KRX) 전체 종목 자동 수집
        df = fdr.StockListing('KRX')
        df = df.rename(columns={'Code': '종목코드', 'Name': '회사명', 'Sector': '섹터'})
        df['섹터'] = df['섹터'].fillna('기타')
        df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
        return df[['종목코드', '회사명', '섹터']].dropna().reset_index(drop=True)
    except Exception as e:
        print(f"[ERROR] KRX DB Load Failed: {e}")
        return pd.DataFrame(columns=['종목코드', '회사명', '섹터'])

def search_candidates(query, limit=20):
    df = get_stock_db()
    q = (query or "").strip().upper()
    if not q: return df.head(0)

    # 영문(미국 티커) 입력 시 자동으로 검색 결과에 추가 (예: IREN, BTQ, TSLA 등)
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
            if code.isdigit() and len(code) == 6:
                # 한국 주식 (KOSPI 우선, 없으면 KOSDAQ)
                stock = yf.Ticker(code + ".KS")
                df = stock.history(period="3mo")
                if df.empty:
                    stock = yf.Ticker(code + ".KQ")
                    df = stock.history(period="3mo")
            else:
                # 미국 주식
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
