import streamlit as st
import pandas as pd
import hashlib
import time
import urllib.parse
from deep_translator import GoogleTranslator
import yfinance as yf
import requests
import xml.etree.ElementTree as ET

from modules.data_fetcher import DataFetcher, get_stock_db, search_candidates
from modules.analyzer import StockAnalyzer

st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.markdown('<meta name="format-detection" content="telephone=no">', unsafe_allow_html=True)

# 한국 국룰 색상 강제 적용 스타일
st.markdown("""
    <style>
    div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
    .stTable td { text-align: center !important; font-size: 0.9rem; }
    .big-font { font-size:1.8rem !important; font-weight: bold; }
    .red-text { color: #f44336; font-weight: bold; }
    .blue-text { color: #2196f3; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return float(yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1])
    except: return 1420.0

@st.cache_data(ttl=3600)
def get_company_news(company_name):
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(company_name+' 주식')}&hl=ko&gl=KR&ceid=KR:ko"
        root = ET.fromstring(requests.get(url).text)
        return [{"title": i.find('title').text, "link": i.find('link').text} for i in root.findall('.//item')[:5]]
    except: return []

def render_report(fetcher, analyzer, exc_rate, item, key_suffix=""):
    data = fetcher.get_stock_data(item['code'])
    if not data:
        st.error("⚠️ 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return

    an = analyzer.analyze(item['code'], item['name'], item['sector'], data)
    news = get_company_news(item['name'])
    
    st.subheader(f"📈 {item['name']} ({item['code']}) 리포트")
    
    curr, prev = data['current'], data['prev_close']
    diff = curr - prev
    chg = (diff / prev) * 100
    color_class = "red-text" if diff > 0 else ("blue-text" if diff < 0 else "")
    
    c1, c2, c3, c4 = st.columns(4)
    p_unit = "원" if curr > 1000 else "$"
    c1.markdown(f"현재가  \n<span class='big-font'>{curr:,.2f if p_unit=='$' else int(curr):,}{p_unit}</span>  \n<span class='{color_class}'>{diff:+,.2f if p_unit=='$' else int(diff):,}{p_unit}</span>", unsafe_allow_html=True)
    c2.markdown(f"등락률  \n<span class='big-font {color_class}'>{chg:+.2f}%</span>", unsafe_allow_html=True)
    c3.markdown(f"RSI  \n<span class='big-font'>{an['rsi']:.1f}</span>", unsafe_allow_html=True)
    c4.markdown(f"거래량  \n<span class='big-font'>{int(data['volume']):,}</span>", unsafe_allow_html=True)

    if len(data['dates']) >= 6:
        st.write("#### 🕒 최근 5거래일 추이")
        rows = []
        for i in range(-2, -7, -1):
            p, po = data['close_prices'][i], data['close_prices'][i-1]
            df, dc = p-po, ((p-po)/po)*100
            clr = "red" if df > 0 else ("blue" if df < 0 else "black")
            rows.append([data['dates'][i][5:], f"{p:,.0f}원" if p > 1000 else f"${p:.2f}", 
                         f"<span style='color:{clr}'>{df:+,.0f}원</span>" if p > 1000 else f"<span style='color:{clr}'>${df:+.2f}</span>",
                         f"<span style='color:{clr}'>{dc:+.2f}%</span>", f"{int(data['volumes'][i]):,}"])
        st.write(pd.DataFrame(rows, columns=["날짜", "종가", "변동", "등락률", "거래량"]).to_html(escape=False, index=False), unsafe_allow_html=True)

    st.divider()
    st.subheader("💡 분석 의견")
    st.markdown(f"### {an['recommendation_color']} {an['recommendation']}")
    for d in an['details']: st.success(d)
    
    st.divider()
    judal_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(item['name'])}+투자분석"
    st.info(f"💡 [주달(Judal) 테마 확인]({judal_url})")
    for n in news: st.markdown(f"🔗 [{n['title']}]({n['link']})")

    if not any(s["code"] == item['code'] for s in st.session_state.custom_stocks):
        if st.button("➕ 관심종목 추가", key=f"add_{item['code']}_{key_suffix}", use_container_width=True):
            st.session_state.custom_stocks.append(item); st.rerun()

# --- App 실행 ---
if "custom_stocks" not in st.session_state: st.session_state.custom_stocks = []
if "search_history" not in st.session_state: st.session_state.search_history = []
if "active_item" not in st.session_state: st.session_state.active_item = None
if "port_code" not in st.session_state: st.session_state.port_code = None

# 로그인
if "pw_ok" not in st.session_state: st.session_state.pw_ok = False
if not st.session_state.pw_ok:
    pw = st.text_input("Password", type="password")
    if st.button("Log In"):
        if hashlib.sha256(pw.encode()).hexdigest() == CORRECT_PASSWORD_HASH:
            st.session_state.pw_ok = True; st.rerun()
        else: st.error("❌ 틀렸습니다.")
else:
    fetcher, analyzer, exc_rate = DataFetcher(), StockAnalyzer(), get_exchange_rate()
    t1, t2 = st.tabs(["🔍 종목 분석", "⭐ 관심종목"])

    with t1:
        st.markdown("### 🕒 최근 검색")
        if st.session_state.search_history:
            cols = st.columns(5)
            for i, h in enumerate(st.session_state.search_history):
                if cols[i%5].button(h['name'], key=f"h_{i}", use_container_width=True):
                    st.session_state.active_item = h; st.rerun()
        
        # 🌟 자동완성 검색창 구현
        query = st.text_input("종목명 입력 (예: 삼성, LG, IREN)", placeholder="검색어를 입력하면 아래에 후보가 나타납니다.")
        if query:
            cands = search_candidates(query)
            if not cands.empty:
                # 검색 결과 리스트에서 선택
                options = [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()]
                pick = st.selectbox("정확한 종목을 골라주세요:", options)
                if st.button("📊 분석 시작", type="primary", use_container_width=True):
                    code = pick.split("(")[1].replace(")", "")
                    name = pick.split(" (")[0]
                    item = {"code": code, "name": name, "sector": "기타"}
                    st.session_state.active_item = item
                    # 히스토리 업데이트
                    st.session_state.search_history = [i for i in st.session_state.search_history if i['code'] != code]
                    st.session_state.search_history.insert(0, item)
                    st.session_state.search_history = st.session_state.search_history[:10]
                    st.rerun()

        if st.session_state.active_item:
            st.divider(); render_report(fetcher, analyzer, exc_rate, st.session_state.active_item, "tab1")

    with t2:
        if not st.session_state.custom_stocks: st.info("관심종목을 추가하세요.")
        else:
            if st.button("🗑️ 전체 삭제"): st.session_state.custom_stocks = []; st.rerun()
            for i, s in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([5, 3, 2])
                c1.write(f"**{s['name']}** ({s['code']})")
                lbl = "🔼 닫기" if st.session_state.port_code == s['code'] else "📊 분석"
                if c2.button(lbl, key=f"p_an_{i}", use_container_width=True):
                    st.session_state.port_code = None if st.session_state.port_code == s['code'] else s['code']; st.rerun()
                if c3.button("❌", key=f"p_del_{i}", use_container_width=True):
                    st.session_state.custom_stocks.pop(i); st.rerun()
                if st.session_state.port_code == s['code']:
                    render_report(fetcher, analyzer, exc_rate, s, f"tab2_{i}")
                    st.divider()
