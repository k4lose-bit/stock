import streamlit as st
import pandas as pd
import hashlib
import time
import yfinance as yf
import urllib.parse
import requests
import xml.etree.ElementTree as ET
from deep_translator import GoogleTranslator

from modules.data_fetcher import DataFetcher, get_stock_db, search_candidates
from modules.analyzer import StockAnalyzer

# 최상단 설정 및 모바일 최적화 CSS
st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.markdown("""
    <meta name="format-detection" content="telephone=no">
    <style>
        a[href^="tel"] { color: inherit !important; text-decoration: none !important; }
        div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
        /* 테이블 텍스트 중앙 정렬 및 가독성 */
        .stTable td { text-align: center !important; }
    </style>
""", unsafe_allow_html=True)

CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("USDKRW=X").history(period="1d")
        return float(rate['Close'].iloc[-1])
    except: return 1400.0

@st.cache_data(ttl=3600)
def get_company_news(company_name, limit=5):
    try:
        search_query = urllib.parse.quote(f"{company_name} 주식 when:7d")
        url = f"https://news.google.com/rss/search?q={search_query}&hl=ko&gl=KR&ceid=KR:ko"
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.text)
        return [{"title": i.find('title').text, "link": i.find('link').text} for i in root.findall('.//item')[:limit]]
    except: return []

@st.cache_data(ttl=3600*24)
def get_company_profile(code):
    try:
        ticker = (code + ".KS") if (code.isdigit() and len(code) == 6) else code
        stock = yf.Ticker(ticker)
        info = stock.info
        if code.isdigit() and 'longBusinessSummary' not in info:
            info = yf.Ticker(code + ".KQ").info
            
        trans = GoogleTranslator(source='auto', target='ko')
        sum_raw = info.get("longBusinessSummary", "개요 없음")
        return {
            "sector": trans.translate(info.get("sector", "알 수 없음")),
            "industry": trans.translate(info.get("industry", "알 수 없음")),
            "summary": trans.translate(sum_raw) if len(sum_raw) > 5 else sum_raw,
            "website": info.get("website", ""), "marketCap": info.get("marketCap", 0),
            "pe": info.get("trailingPE", 0), "eps": info.get("trailingEps", 0),
            "div_yield": info.get("dividendYield", 0), "high52": info.get("fiftyTwoWeekHigh", 0),
            "low52": info.get("fiftyTwoWeekLow", 0)
        }
    except: return None

def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.warning("🔒 비밀번호를 입력해 주세요.")
        pw = st.text_input("Password", type="password")
        if st.button("Log In", type="primary"):
            if hashlib.sha256(pw.encode()).hexdigest() == CORRECT_PASSWORD_HASH:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("❌ 틀렸습니다.")
        return False
    return True

def add_to_history(item):
    if "search_history" not in st.session_state: st.session_state.search_history = []
    st.session_state.search_history = [i for i in st.session_state.search_history if i["code"] != item["code"]]
    st.session_state.search_history.insert(0, item)
    st.session_state.search_history = st.session_state.search_history[:10]

def render_report(fetcher, analyzer, exc_rate, item, key_suffix=""):
    with st.spinner(f"{item['name']} 분석 중..."):
        data = fetcher.get_stock_data(item['code'])
        if not data: 
            st.error("데이터 수집 불가")
            return
        an = analyzer.analyze(item['code'], item['name'], item['sector'], data)
        prof = get_company_profile(item['code'])
        news_list = get_company_news(item['name'])
        
        st.header(f"📈 {item['name']} 상세 분석")
        
        curr = an['current']
        prev_close = data['prev_close']
        diff = curr - prev_close
        chg = an['change']
        
        # 🌟 색상 국룰 적용 (상승 빨강, 하락 파랑)
        main_color = "#f44336" if diff > 0 else ("#2196f3" if diff < 0 else "#666")
        
        c1, c2, c3, c4 = st.columns(4)
        
        # 1. 현재가 (HTML 강제 색상 주입)
        p_str = f"{int(curr):,}원" if curr > 1000 else f"${curr:.2f}"
        d_str = f"{int(diff):+,}원" if curr > 1000 else f"${diff:+.2f}"
        c1.markdown(f"**현재가** \n<span style='font-size:1.8rem; font-weight:bold;'>{p_str}</span>  \n<span style='color:{main_color}; font-weight:bold;'>{d_str}</span>", unsafe_allow_html=True)
        c1.caption(f"약 {int(curr * exc_rate):,}원")
        
        # 2. 등락률
        c2.markdown(f"**등락률** \n<span style='font-size:1.8rem; font-weight:bold; color:{main_color};'>{chg:+.2f}%</span>", unsafe_allow_html=True)
        
        # 3. RSI
        c3.markdown(f"**RSI** \n<span style='font-size:1.8rem; font-weight:bold;'>{an['rsi']:.1f}</span>", unsafe_allow_html=True)
        
        # 4. 거래량
        c4.markdown(f"**거래량** \n<span style='font-size:1.8rem; font-weight:bold;'>{int(an['volume']):,}</span>", unsafe_allow_html=True)
        
        if len(data['dates']) >= 10:
            st.write("#### 🕒 최근 5거래일 추이 (전일 대비)")
            
            # 테이블용 데이터 생성 (HTML 색상 태그 포함)
            hist_rows = []
            for i in range(-2, -7, -1):
                p_past, p_old = data['close_prices'][i], data['close_prices'][i-1]
                v_df = p_past - p_old
                v_chg = ((p_past - p_old) / p_old) * 100
                v_color = "red" if v_df > 0 else ("blue" if v_df < 0 else "black")
                
                hist_rows.append([
                    data['dates'][i][5:],
                    f"{int(p_past):,}원" if curr > 1000 else f"${p_past:.2f}",
                    f"<span style='color:{v_color}; font-weight:bold;'>{int(v_df):+,}원</span>" if curr > 1000 else f"<span style='color:{v_color}; font-weight:bold;'>${v_df:+.2f}</span>",
                    f"<span style='color:{v_color}; font-weight:bold;'>{v_chg:+.2f}%</span>",
                    f"{int(data['volumes'][i]):,}"
                ])
            
            df_hist = pd.DataFrame(hist_rows, columns=["날짜", "종가", "변동", "등락률", "거래량"])
            # HTML로 변환하여 출력 (색상 유지)
            st.write(df_hist.to_html(escape=False, index=False, justify='center'), unsafe_allow_html=True)

        st.divider()
        if prof:
            st.subheader("🏢 기업 정보")
            st.write(f"**섹터:** {prof['sector']} | **산업:** {prof['industry']}")
            f1, f2, f3, f4, f5 = st.columns(5)
            mc = prof['marketCap']
            f1.metric("시가총액", f"{mc//100000000:,}억" if item['code'].isdigit() else f"${mc//1000000:,}M")
            f2.metric("PER", f"{prof['pe']:.1f}" if prof['pe'] else "-")
            f3.metric("EPS", f"{prof['eps']:.1f}" if prof['eps'] else "-")
            f4.metric("배당률", f"{prof['div_yield']*100:.1f}%" if prof['div_yield'] else "-")
            h, l = prof['high52'], prof['low52']
            f5.write("**52주 고/저**")
            f5.write(f"{l:,.0f} ~ {h:,.0f}" if h else "-")
            st.info(prof['summary'])

        st.divider()
        st.subheader("💡 분석 의견")
        st.markdown(f"### {an['recommendation_color']} {an['recommendation']}")
        for d in an['details']: st.success(d)
        
        st.divider()
        st.subheader(f"📰 '{item['name']}' 주요 뉴스 및 분석")
        judal_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(item['name'])}+투자분석"
        st.info(f"💡 [주달(Judal)에서 '{item['name']}' 테마 확인하기]({judal_url})")
        if news_list:
            for news in news_list: st.markdown(f"🔗 [{news['title']}]({news['link']})")
        
        st.divider()
        if not any(s["code"] == item['code'] for s in st.session_state.custom_stocks):
            if st.button("➕ 관심종목 추가", use_container_width=True, type="primary", key=f"add_{item['code']}_{key_suffix}"):
                st.session_state.custom_stocks.append(item)
                st.rerun()

# --- App Logic ---
if "custom_stocks" not in st.session_state: st.session_state.custom_stocks = []
if "search_history" not in st.session_state: st.session_state.search_history = []
if "active_item" not in st.session_state: st.session_state.active_item = None
if "port_active_code" not in st.session_state: st.session_state.port_active_code = None

if check_password():
    fetcher, analyzer, exc_rate = DataFetcher(), StockAnalyzer(), get_exchange_rate()
    
    tab1, tab2 = st.tabs(["🔍 종목 분석", "⭐ 관심종목 리스트"])

    with tab1:
        st.markdown("### 🕒 최근 검색")
        if st.session_state.search_history:
            cols = st.columns(5)
            for i, h in enumerate(st.session_state.search_history):
                if cols[i%5].button(h['name'], key=f"h_{i}", use_container_width=True):
                    st.session_state.active_item = h; st.rerun()
        
        query = st.text_input("종목 검색 (삼성전자, IREN, BTQ...)", key="main_search")
        if query:
            cands = search_candidates(query, limit=5)
            if not cands.empty:
                pick = st.selectbox("정확한 종목 선택", [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()])
                if st.button("📊 즉시 분석", type="primary"):
                    code_raw = pick.split("(")[1].replace(")", "")
                    name_raw = pick.split(" (")[0]
                    item = {"code": code_raw, "name": name_raw, "sector": "기타"}
                    st.session_state.active_item = item
                    add_to_history(item); st.rerun()

        if st.session_state.active_item:
            st.divider()
            render_report(fetcher, analyzer, exc_rate, st.session_state.active_item, key_suffix="tab1")

    with tab2:
        if not st.session_state.custom_stocks: st.info("관심종목을 추가해 보세요.")
        else:
            if st.button("🗑️ 리스트 전체 삭제"): st.session_state.custom_stocks = []; st.rerun()
            
            for i, s in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([5, 3, 2])
                c1.write(f"**{s['name']}** ({s['code']})")
                
                btn_label = "🔼 닫기" if st.session_state.port_active_code == s['code'] else "📊 분석"
                if c2.button(btn_label, key=f"port_an_{i}", use_container_width=True):
                    st.session_state.port_active_code = None if st.session_state.port_active_code == s['code'] else s['code']
                    st.rerun()
                    
                if c3.button("❌", key=f"port_del_{i}", use_container_width=True):
                    st.session_state.custom_stocks.pop(i); st.rerun()
                
                if st.session_state.port_active_code == s['code']:
                    render_report(fetcher, analyzer, exc_rate, s, key_suffix=f"tab2_{i}")
                    st.divider()
