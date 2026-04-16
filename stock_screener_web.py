import streamlit as st
import pandas as pd
import hashlib
import time
import urllib.parse
from datetime import datetime
from deep_translator import GoogleTranslator
import yfinance as yf
import requests
import xml.etree.ElementTree as ET

from modules.data_fetcher import DataFetcher, get_stock_db, search_candidates
from modules.analyzer import StockAnalyzer

# 🌟 최상단 설정
st.set_page_config(page_title="Stock Screener Pro", layout="wide")

# 모바일 취소선 방지 및 PC/모바일 통합 스타일
st.markdown("""
    <meta name="format-detection" content="telephone=no">
    <style>
    div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
    .stTable td { text-align: center !important; }
    .big-font { font-size:1.8rem !important; font-weight: bold; }
    .red-text { color: #f44336; font-weight: bold; }
    .blue-text { color: #2196f3; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("USDKRW=X").history(period="1d")
        return float(rate['Close'].iloc[-1])
    except: return 1420.0

@st.cache_data(ttl=3600)
def get_company_news(company_name):
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(company_name+' 주식')}&hl=ko&gl=KR&ceid=KR:ko"
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.text)
        return [{"title": i.find('title').text, "link": i.find('link').text} for i in root.findall('.//item')[:5]]
    except: return []

def render_report(fetcher, analyzer, exc_rate, item, key_suffix=""):
    data = fetcher.get_stock_data(item['code'])
    if not data:
        st.error("⚠️ 데이터를 불러오지 못했습니다. 종목 코드나 네트워크를 확인해주세요.")
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
    
    # 숫자 안전 포맷팅
    curr_txt = f"{curr:,.2f}" if p_unit == "$" else f"{int(curr):,}"
    diff_txt = f"{diff:+,.2f}" if p_unit == "$" else f"{int(diff):+,}"
    conv_txt = f"{int(curr * exc_rate):,}"
    
    c1.markdown(f"현재가  \n<span class='big-font'>{curr_txt}{p_unit}</span>  \n<span class='{color_class}'>{diff_txt}{p_unit}</span>", unsafe_allow_html=True)
    c1.caption(f"약 {conv_txt}원")
    
    c2.markdown(f"등락률  \n<span class='big-font {color_class}'>{chg:+.2f}%</span>", unsafe_allow_html=True)
    
    # 🌟 RSI 에러 방지 처리
    rsi_val = an.get('rsi')
    rsi_txt = f"{rsi_val:.1f}" if rsi_val is not None else "-"
    c3.markdown(f"RSI  \n<span class='big-font'>{rsi_txt}</span>", unsafe_allow_html=True)
    
    c4.markdown(f"거래량  \n<span class='big-font'>{int(data['volume']):,}</span>", unsafe_allow_html=True)

    if len(data['dates']) >= 6:
        st.write("#### 🕒 최근 5거래일 추이")
        rows = []
        for i in range(-2, -7, -1):
            p, po = data['close_prices'][i], data['close_prices'][i-1]
            df_val, dc = p-po, ((p-po)/po)*100
            clr = "red" if df_val > 0 else ("blue" if df_val < 0 else "black")
            p_f = f"{p:,.2f}$" if p < 1000 else f"{int(p):,}원"
            df_f = f"{df_val:+,.2f}$" if p < 1000 else f"{int(df_val):+,}원"
            rows.append([data['dates'][i][5:], p_f, f"<span style='color:{clr}'>{df_f}</span>", f"<span style='color:{clr}'>{dc:+.2f}%</span>", f"{int(data['volumes'][i]):,}"])
        st.write(pd.DataFrame(rows, columns=["날짜", "종가", "변동", "등락률", "거래량"]).to_html(escape=False, index=False), unsafe_allow_html=True)

    st.divider()
    st.subheader("💡 분석 의견")
    st.markdown(f"### {an['recommendation_color']} {an['recommendation']}")
    for d in an['details']: st.success(d)
    
    st.divider()
    judal_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(item['name'])}+투자분석"
    st.info(f"💡 [주달(Judal) 테마 확인]({judal_url})")
    for n in news: st.markdown(f"🔗 [{n['title']}]({n['link']})")

    if not any(s["code"] == item['code'] for s in st.session_state.get("custom_stocks", [])):
        if st.button("➕ 관심종목 추가", key=f"add_{item['code']}_{key_suffix}", use_container_width=True):
            if "custom_stocks" not in st.session_state: st.session_state.custom_stocks = []
            st.session_state.custom_stocks.append(item); st.rerun()

# --- 메인 실행 로직 ---
if "pw_ok" not in st.session_state: st.session_state.pw_ok = False
if "custom_stocks" not in st.session_state: st.session_state.custom_stocks = []
if "search_history" not in st.session_state: st.session_state.search_history = []
if "active_item" not in st.session_state: st.session_state.active_item = None
if "port_code" not in st.session_state: st.session_state.port_code = None

if not st.session_state.pw_ok:
    st.title("🚀 Stock Screener Pro")
    st.write("---")
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.subheader("🔒 로그인")
        pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
        if st.button("들어가기", use_container_width=True, type="primary"):
            if hashlib.sha256(pw.encode()).hexdigest() == CORRECT_PASSWORD_HASH:
                st.session_state.pw_ok = True; st.rerun()
            else: st.error("비밀번호가 틀렸습니다.")
else:
    fetcher, analyzer, exc_rate = DataFetcher(), StockAnalyzer(), get_exchange_rate()
    
    if datetime.now().day == 13:
        st.info("📅 오늘은 매월 13일, 종목 리스트 업데이트 권장일입니다.")

    tab1, tab2, tab3 = st.tabs(["🔍 종목 분석", "⭐ 관심종목", "⚙️ 관리"])

    with tab1:
        st.markdown("### 🕒 최근 검색")
        if st.session_state.search_history:
            cols = st.columns(5)
            for i, h in enumerate(st.session_state.search_history):
                if cols[i%5].button(h['name'], key=f"h_{i}", use_container_width=True):
                    st.session_state.active_item = h; st.rerun()
        
        st.divider()
        query = st.text_input("종목명 입력 (삼성, LG, IREN...)", placeholder="검색어를 입력하면 후보가 나타납니다.")
        if query:
            cands = search_candidates(query)
            if not cands.empty:
                pick = st.selectbox("정확한 종목 선택", [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()])
                if st.button("📊 즉시 분석", type="primary", use_container_width=True):
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

    with tab2:
        if not st.session_state.custom_stocks: st.info("관심종목을 추가해 보세요.")
        else:
            if st.button("🗑️ 리스트 전체 삭제"): st.session_state.custom_stocks = []; st.rerun()
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

    with tab3:
        st.subheader("📥 데이터베이스 관리")
        db_df = get_stock_db()
        csv_data = db_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 현재 종목 리스트(CSV) 다운로드", data=csv_data, file_name=f"stock_list_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        st.write("---")
        if st.button("🚪 로그아웃"):
            st.session_state.pw_ok = False; st.rerun()
