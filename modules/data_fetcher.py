import pandas as pd
import requests
import time
from io import StringIO
import streamlit as st

EMBEDDED_MINI_CSV = """
회사명,종목코드,섹터
삼성전자,005930,기타
SK하이닉스,000660,기타
NAVER,035420,AI
네이버,035420,AI
카카오,035720,AI
셀트리온,068270,의약품
삼성바이오로직스,207940,의약품
현대차,005380,기타
기아,000270,기타
휴림로봇,090710,로봇
""".strip()

@st.cache_data(ttl=60 * 60 * 24)
def load_stock_db_from_repo(filepath="krx_stock_list.csv"):
try: return pd.read_csv(filepath)
except Exception: return None

def normalize_stock_db(df):
df = df.copy()
col_map = {}
lower_cols = {c.lower(): c for c in df.columns}
for cand in ["회사명", "name", "corp_name", "company", "companyname"]:
if cand.lower() in lower_cols: col_map[lower_cols[cand.lower()]] = "회사명"; break
for cand in ["종목코드", "code", "symbol", "ticker", "stock_code"]:
if cand.lower() in lower_cols: col_map[lower_cols[cand.lower()]] = "종목코드"; break
for cand in ["섹터", "sector", "업종", "industry"]:
if cand.lower() in lower_cols: col_map[lower_cols[cand.lower()]] = "섹터"; break
df = df.rename(columns=col_map)
if "섹터" not in df.columns: df["섹터"] = "기타"
df["회사명"] = df["회사명"].astype(str).str.strip()
df["종목코드"] = df["종목코드"].astype(str).str.extract(r"(\d+)")[0].fillna(df["종목코드"].astype(str)).str.zfill(6)
df["섹터"] = df["섹터"].astype(str).fillna("기타")
return df.dropna(subset=["회사명", "종목코드"]).drop_duplicates(subset=["종목코드"]).reset_index(drop=True)

def get_stock_db():
if "uploaded_stock_db" in st.session_state and isinstance(st.session_state.uploaded_stock_db, pd.DataFrame):
try: return normalize_stock_db(st.session_state.uploaded_stock_db)
except Exception: pass
repo_df = load_stock_db_from_repo("krx_stock_list.csv")
if repo_df is not None and not repo_df.empty:
try: return normalize_stock_db(repo_df)
except Exception: pass
return normalize_stock_db(pd.read_csv(StringIO(EMBEDDED_MINI_CSV)))

def search_candidates(query, limit=20):
df = get_stock_db()
q = (query or "").strip()
if not q: return df.head(0)
q2 = q.replace(" ", "").upper()
name_norm = df["회사명"].astype(str).str.replace(" ", "", regex=False).str.upper()
exact = df[name_norm == q2]
if not exact.empty: return exact.head(limit)
return df[name_norm.str.contains(q2, na=False)].head(limit)

def safe_get(url, params=None, headers=None, timeout=10, retries=2, sleep=0.3):
last_exc = None
for _ in range(retries + 1):
try:
r = requests.get(url, params=params, headers=headers, timeout=timeout)
r.raise_for_status()
return r
except Exception as e:
last_exc = e
time.sleep(sleep)
raise last_exc

def parse_ohlcv_csv(file):
try:
df = pd.read_csv(file)
cols = {c.lower(): c for c in df.columns}
def pick(*names):
for n in names:
if n in cols: return cols[n]
return None
c_date = pick("date", "날짜")
c_open = pick("open", "시가")
c_close = pick("close", "종가")
c_vol = pick("volume", "거래량")
if c_close is None or c_vol is None: return None
if c_date is not None:
df[c_date] = pd.to_datetime(df[c_date], errors="coerce")
df = df.dropna(subset=[c_date]).sort_values(c_date)
closes = df[c_close].astype(float).tolist()
vols = df[c_vol].astype(float).tolist()
if len(closes) < 35: return None
current = float(closes[-1])
prev_close = float(closes[-2])
volume = float(vols[-1])
openp = float(df[c_open].astype(float).iloc[-1]) if c_open is not None else prev_close
return {
"current": current, "open": openp, "prev_close": prev_close, "volume": volume,
"close_prices": closes, "volumes": vols
}
except Exception: return None

class DataFetcher:
def init(self):
self.headers = {
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
"Referer": "https://finance.naver.com/",
}

@st.cache_data(ttl=600)
def get_stock_data_live(_self, code):
    all_data = []
    try:
        for page in range(1, 4):
            url = "[https://finance.naver.com/item/sise_day.naver](https://finance.naver.com/item/sise_day.naver)"
            r = safe_get(url, params={"code": code, "page": page}, headers=_self.headers, timeout=12, retries=1)
            df_list = pd.read_html(r.text)
            if not df_list: break
            df = df_list[0].dropna()
            if df.empty: break
            all_data.append(df)
            time.sleep(0.1)
        if not all_data: return None
        combined = pd.concat(all_data, ignore_index=True).sort_values("날짜").reset_index(drop=True)
        if len(combined) < 35: return None
        return {
            "current": float(combined.iloc[-1]["종가"]),
            "open": float(combined.iloc[-1]["시가"]),
            "prev_close": float(combined.iloc[-2]["종가"]),
            "volume": float(combined.iloc[-1]["거래량"]),
            "close_prices": combined["종가"].astype(float).tolist(),
            "volumes": combined["거래량"].astype(float).tolist(),
        }
    except Exception: return None

def get_stock_data(self, code):
    offline_map = st.session_state.get("offline_price_data", {})
    if isinstance(offline_map, dict) and code in offline_map:
        return offline_map[code]
    return self.get_stock_data_live(code)
