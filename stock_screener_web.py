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

st.set_page_config(page_title="Stock Screener Pro", layout="wide")

CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("USDKRW=X").history(period="1d")
        return float(rate['Close'].iloc[-1])
    except Exception:
        return 1400.0

@st.cache_data(ttl=3600)
def get_company_news(company_name, limit=5):
    try:
        search_query = urllib.parse.quote(f"{company_name} 주식 when:7d")
        url = f"https://news.google.com/rss/search?q={search_query}&hl=ko&gl=KR&ceid=KR:ko"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        root = ET.fromstring(response.text)
        news_list = []
        for item in root.findall('.//item')[:limit]:
            news_list.append({"title": item.find('title').text, "link": item.find('link').text})
        return news_list
    except Exception:
        return []

@st.cache_data(ttl=3600*24)
def get_company_profile(code):
    try:
        if code.isdigit() and len(code) == 6:
            stock = yf.Ticker(code + ".KS")
            info = stock.info
            if 'longBusinessSummary' not in info:
                stock = yf.Ticker(code + ".KQ")
                info = stock.info
        else:
            stock = yf.Ticker(code)
            info = stock.info
            
        raw_sector = info.get("sector", "알 수 없음")
        raw_industry = info.get("industry", "알 수 없음")
        raw_summary = info.get("longBusinessSummary", "기업 개요 데이터가 제공되지 않습니다.")
        
        translator = GoogleTranslator(source='auto', target='ko')
        try:
            ko_sector = translator.translate(raw_sector) if raw_sector != "알 수 없음" else raw_sector
            ko_industry = translator.translate(raw_industry) if raw_industry != "알 수 없음" else raw_industry
            ko_summary = translator.translate(raw_summary) if raw_summary != "기업 개요 데이터가 제공되지 않습니다." else raw_summary
        except Exception:
            ko_sector, ko_industry, ko_summary = raw_sector, raw_industry, raw_summary
            
        return {
            "sector": ko_sector, "industry": ko_industry, "summary": ko_summary,
            "website": info.get("website", ""), "marketCap": info.get("marketCap", 0),
            "pe": info.get("trailingPE", 0), "eps": info.get("trailingEps", 0),
            "div_yield": info.get("dividendYield", 0), "high52": info.get("fiftyTwoWeekHigh", 0),
            "low52": info.get("fiftyTwoWeekLow", 0)
        }
    except Exception:
        return None

def check_password():
    if "password_correct" not in st.session_state: 
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.warning("🔒 안전한 사용을 위해 비밀번호를 입력해 주세요.")
        pw_input = st.text_input("접속 비밀번호", type="password", key="pw_input")
        if st.button("로그인", key="login_btn", type="primary"):
            if hashlib.sha256(pw_input.encode("utf-8")).hexdigest() == CORRECT_PASSWORD_HASH:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 틀렸습니다.")
        return False
    return True

def add_to_history(code, name, sector):
    item = {"code": code, "name": name, "sector": sector}
    if "search_history" not in st.session_state: st.session_state.search_history = []
    if item in st.session_state.search_history:
        st.session_state.search_history.remove(item)
    st.session_state.search_history.insert(0, item)
    if len(st.session_state.search_history) > 10:
        st.session_state.search_history.pop()

def render_analysis_report(fetcher, analyzer, exc_rate, code, name, sector):
    with st.spinner(f"{name} 데이터를 분석 중입니다..."):
        data = fetcher.get_stock_data(code)
        news_list = get_company_news(name)
        profile = get_company_profile(code)
        
        if not data:
            st.error("데이터를 가져올 수 없습니다.")
            return

        an = analyzer.analyze(code, name, sector, data)
        if not an: return

        st.header(f"📈 {name} 상세 분석 리포트")
        c1, c2, c3, c4 = st.columns(4)
        curr = an['current']
        krw_price = f"{int(curr):,}원" if curr > 1000 else f"${curr:.2f} (약 {int(curr * exc_rate):,}원)"
        
        c1.metric("현재가", krw_price)
        c2.metric("당일 등락률", f"{an['change']:.2f}%")
        c3.metric("RSI", f"{an['rsi']:.1f}")
        c4.metric("거래량", f"{int(an['volume']):,}")
        
        dates = data.get("dates", [])
        prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        
        if len(dates) >= 20: 
            for c in [c1, c2, c3, c4]: c.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
            
            # 과거 5일 추이 (오류 수정 패치 적용)
            for i in range(-2, -7, -1):
                d_short = dates[i][5:]
                p_past = prices[i]
                diff = curr - p_past
                
                # 🌟 에러가 났던 숫자 포맷팅 부분을 안전하게 수정했습니다.
                if curr > 1000:
                    diff_str = f"({int(diff):+,}원)"
                    p_str = f"{int(p_past):,}원"
                else:
                    diff_str = f"(${diff:+.2f})"
                    p_str = f"${p_past:.2f}"
                
                diff_color = "#e53935" if diff > 0 else ("#1e88e5" if diff < 0 else "#666")
                c1.markdown(f"<div style='font-size:0.8rem; color:#666;'>{d_short} | {p_str} <span style='color:{diff_color}; font-weight:bold;'>{diff_str}</span></div>", unsafe_allow_html=True)
                
                chg = ((prices[i] - prices[i-1]) / prices[i-1]) * 100
                chg_color = "#e53935" if chg > 0 else ("#1e88e5" if chg < 0 else "#666")
                c2.markdown(f"<div style='font-size:0.8rem; color:{chg_color};'>{d_short} | <b>{chg:+.2f}%</b></div>", unsafe_allow_html=True)
                
                rsi_val = analyzer.indicator.calculate_rsi(prices[:i+1])
                c3.markdown(f"<div style='font-size:0.8rem; color:#666;'>{d_short} | <b>{rsi_val:.1f if rsi_val else '-'}</b></div>", unsafe_allow_html=True)
                
                c4.markdown(f"<div style='font-size:0.8rem; color:#666;'>{d_short} | <b>{int(volumes[i]):,}</b></div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("🏢 기업 개요 및 펀더멘탈")
        if profile:
            st.markdown(f"**섹터:** {profile['sector']} | **산업군:** {profile['industry']}")
            if profile['website']: st.markdown(f"**웹사이트:** [{profile['website']}]({profile['website']})")
            f1, f2, f3, f4, f5 = st.columns(5)
            mc = profile.get('marketCap', 0)
            mc_str = (f"{mc // 100000000:,}억 원" if code.isdigit() else f"${mc // 1000000:,}M") if mc else "-"
            f1.metric("시가총액", mc_str); f2.metric("PER", f"{profile['pe']:.2f}" if profile.get('pe') else "-")
            f3.metric("EPS", f"{profile['eps']:.2f}" if profile.get('eps') else "-"); dy = profile.get('div_yield')
            f4.metric("배당률", f"{dy*100:.2f}%" if dy else "-"); h52, l52 = profile.get('high52'), profile.get('low52')
            f5.metric("52주 고/저", f"{l52:.1f}~{h52:.1f}" if h52 and l52 else "-")
            st.info(profile['summary'])

        st.divider()
        st.subheader("💡 분석 의견")
        st.markdown(f"### {an['recommendation_color']} **{an['recommendation']}**")
        for detail in an['details']: st.success(detail)
        
        st.divider()
        st.subheader(f"📰 '{name}' 최근 뉴스")
        judal_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(name)}+투자분석"
        st.info(f"💡 [주달(Judal)에서 '{name}' 테마 확인하기]({judal_url})")
        if news_list:
            for news in news_list: st.markdown(f"🔗 [{news['title']}]({news['link']})")
        else: st.write("최근 뉴스가 없습니다.")

        st.divider()
        if not any(s["code"] == code for s in st.session_state.custom_stocks):
            if st.button("➕ 관심종목 추가", type="primary", use_container_width=True, key=f"add_{code}"):
                st.session_state.custom_stocks.append({"code": code, "name": name, "sector": sector})
                st.success("추가되었습니다!"); time.sleep(1); st.rerun()

# --- App UI ---
st.markdown("<style>div[data-baseweb='input'] { border: 2px solid #1E90FF !important; }</style>", unsafe_allow_html=True)
st.title("🚀 Stock Screener Pro")

if "custom_stocks" not in st.session_state: st.session_state.custom_stocks = []
if "search_history" not in st.session_state: st.session_state.search_history = []
if "active_analysis" not in st.session_state: st.session_state.active_analysis = None

if check_password():
    fetcher, analyzer, exc_rate = DataFetcher(), StockAnalyzer(), get_exchange_rate()
    with st.sidebar:
        if st.button("로그아웃"): st.session_state["password_correct"] = False; st.rerun()

    tab1, tab2 = st.tabs(["🔍 분석", "⭐ 관심종목"])

    with tab1:
        if st.session_state.search_history:
            cols = st.columns(5)
            for i, h in enumerate(st.session_state.search_history):
                if cols[i%5].button(h['name'], key=f"h_{i}", use_container_width=True):
                    st.session_state.active_analysis = h; st.rerun()
        st.divider()
        query = st.text_input("종목 검색", placeholder="삼성전자, IREN...", key="q")
        if query:
            cands = search_candidates(query, limit=10)
            if not cands.empty:
                opts = [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()]
                pick = st.selectbox("종목 선택", opts)
                idx = opts.index(pick)
                code = str(cands.iloc[idx]["종목코드"]).zfill(6) if str(cands.iloc[idx]["종목코드"]).isdigit() else str(cands.iloc[idx]["종목코드"])
                name, sector = str(cands.iloc[idx]["회사명"]), str(cands.iloc[idx].get("섹터", "기타"))
                if st.button("📊 분석 시작", type="primary", use_container_width=True):
                    st.session_state.active_analysis = {"code": code, "name": name, "sector": sector}
                    add_to_history(code, name, sector); st.rerun()

        if st.session_state.active_analysis:
            st.divider()
            t = st.session_state.active_analysis
            render_analysis_report(fetcher, analyzer, exc_rate, t["code"], t["name"], t["sector"])

    with tab2:
        if not st.session_state.custom_stocks: st.info("관심종목을 추가해 보세요.")
        else:
            if st.button("🗑️ 리스트 비우기"): st.session_state.custom_stocks = []; st.rerun()
            for i, s in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([5, 3, 2])
                c1.markdown(f"**{s['name']}**")
                if c2.button("📊 분석", key=f"pa_{i}", use_container_width=True):
                    st.session_state.active_analysis = s; add_to_history(s['code'], s['name'], s['sector']); st.rerun()
                if c3.button("❌", key=f"pd_{i}", use_container_width=True): st.session_state.custom_stocks.pop(i); st.rerun()
