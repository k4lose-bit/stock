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
            ko_sector, ko_industry, ko_summary = raw_sector, raw_industry, raw_summary + "\n\n(번역기 오류로 원문 제공)"
            
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
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        pw_input = st.sidebar.text_input("접속 비밀번호", type="password", key="pw_input")
        if st.sidebar.button("로그인", key="login_btn"):
            if hashlib.sha256(pw_input.encode("utf-8")).hexdigest() == CORRECT_PASSWORD_HASH:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.sidebar.error("❌ 비밀번호가 틀렸습니다.")
        return False
    return True

def add_to_history(code, name, sector):
    item = {"code": code, "name": name, "sector": sector}
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
            st.error("데이터를 가져올 수 없습니다. 종목 코드나 네트워크 상태를 확인해주세요.")
            return

        an = analyzer.analyze(code, name, sector, data)
        if not an: return

        st.header(f"📈 {name} 상세 분석 리포트")
        c1, c2, c3, c4 = st.columns(4)
        krw_price = f"{int(an['current']):,}원" if an['current'] > 1000 else f"${an['current']:.2f} (약 {int(an['current'] * exc_rate):,}원)"
        
        c1.metric("현재가", krw_price)
        c2.metric("등락율", f"{an['change']:.2f}%")
        c3.metric("RSI", f"{an['rsi']:.1f}")
        c4.metric("거래량", f"{int(an['volume']):,}")
        
        st.divider()
        st.subheader("🏢 기업 개요 및 펀더멘탈")
        if profile:
            st.markdown(f"**섹터:** {profile['sector']} &nbsp;|&nbsp; **산업군:** {profile['industry']}")
            if profile['website']: st.markdown(f"**웹사이트:** [{profile['website']}]({profile['website']})")
            
            f1, f2, f3, f4, f5 = st.columns(5)
            mc = profile.get('marketCap', 0)
            mc_str = (f"{mc // 100000000:,}억 원" if code.isdigit() else f"${mc // 1000000:,}M") if mc else "-"
            f1.metric("시가총액", mc_str)
            f2.metric("PER", f"{profile['pe']:.2f}" if profile.get('pe') else "-")
            f3.metric("EPS", f"{profile['eps']:.2f}" if profile.get('eps') else "-")
            dy = profile.get('div_yield')
            f4.metric("배당수익률", f"{dy*100:.2f}%" if dy else "-")
            h52, l52 = profile.get('high52'), profile.get('low52')
            f5.metric("52주 고/저", f"{l52:.1f} ~ {h52:.1f}" if h52 and l52 else "-")
            st.info(profile['summary'])
        else:
            st.write("해당 기업의 개요 정보를 불러올 수 없습니다.")

        st.divider()
        st.subheader("💡 종합 지표 분석 의견")
        st.markdown(f"### {an['recommendation_color']} **{an['recommendation']}**")
        for detail in an['details']: st.success(detail)
        
        st.divider()
        st.subheader(f"📰 '{name}' 주요 이슈 및 투자분석")
        judal_search_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(name)}+투자분석"
        st.info(f"💡 **AI 테마 및 추가 분석 확인하기:** [👉 주달(Judal)에서 '{name}' 분석 결과 보기]({judal_search_url})")

        if news_list:
            for news in news_list: st.markdown(f"🔗 [{news['title']}]({news['link']})")
        else:
            st.write("최근 일주일 이내 주요 뉴스가 없습니다.")

        st.divider()
        if not any(s["code"] == code for s in st.session_state.custom_stocks):
            if st.button("➕ 이 종목을 '내 관심종목'에 추가하기", type="primary", use_container_width=True, key=f"add_btn_{code}"):
                st.session_state.custom_stocks.append({"code": code, "name": name, "sector": sector})
                st.success("✅ 내 관심종목에 추가되었습니다!")
                time.sleep(1)
                st.rerun()
        else:
            st.button("✔️ 이미 관심종목에 추가된 종목입니다", disabled=True, use_container_width=True)

# ==========================================
# 메인 앱 시작
# ==========================================
st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.title("🚀 Stock Screener Pro (개인 맞춤형 UI 📊)")

# 🌟 에러 방지(호환성 패치): 과거의 소괄호 데이터가 있으면 새 방식으로 자동 변환해주는 부분
if "custom_stocks" not in st.session_state: 
    st.session_state.custom_stocks = []
else:
    migrated_stocks = []
    for s in st.session_state.custom_stocks:
        if isinstance(s, tuple) and len(s) == 3:
            migrated_stocks.append({"code": s[0], "name": s[1], "sector": s[2]})
        elif isinstance(s, dict):
            migrated_stocks.append(s)
    st.session_state.custom_stocks = migrated_stocks

if "search_history" not in st.session_state: st.session_state.search_history = []
if "active_analysis" not in st.session_state: st.session_state.active_analysis = None

if check_password():
    fetcher = DataFetcher()
    analyzer = StockAnalyzer()
    exc_rate = get_exchange_rate()

    with st.sidebar:
        st.success("✅ 로그인 성공!")
        if st.button("로그아웃", key="logout_btn"):
            st.session_state["password_correct"] = False
            st.rerun()

    tab1, tab2 = st.tabs(["🔍 종목 검색 및 상세분석", "⭐ 내 관심종목 & 포트폴리오 관리"])

    # -----------------------------------
    # 탭 1: 상세 분석 및 검색
    # -----------------------------------
    with tab1:
        st.markdown("### 🕒 최근 검색 기록 (최대 10개)")
        if st.session_state.search_history:
            cols = st.columns(5)
            for i, hist in enumerate(st.session_state.search_history):
                if cols[i % 5].button(f"{hist['name']}", key=f"hist_btn_{hist['code']}_{i}", use_container_width=True):
                    st.session_state.active_analysis = hist
                    st.rerun()
        else:
            st.caption("아직 검색 기록이 없습니다.")

        st.divider()

        st.markdown("### 🔍 새로운 종목 검색")
        query = st.text_input("기업명이나 영문 티커(IREN, BTQ)를 입력하세요", key="search_query")
        if query:
            cands = search_candidates(query, limit=10)
            if cands.empty:
                st.error("검색 결과가 없습니다.")
            else:
                options = [f"{row['회사명']} ({row['종목코드']})" for _, row in cands.iterrows()]
                pick = st.selectbox("✅ 정확한 종목을 선택하세요", options, key="pick_cand")
                idx = options.index(pick)
                
                code = str(cands.iloc[idx]["종목코드"])
                if code.isdigit(): code = code.zfill(6)
                name = str(cands.iloc[idx]["회사명"])
                sector = str(cands.iloc[idx].get("섹터", "기타"))

                if st.button("📊 상세 분석 시작", type="primary"):
                    item = {"code": code, "name": name, "sector": sector}
                    st.session_state.active_analysis = item
                    add_to_history(code, name, sector)
                    st.rerun()

        if st.session_state.active_analysis:
            st.divider()
            target = st.session_state.active_analysis
            render_analysis_report(fetcher, analyzer, exc_rate, target["code"], target["name"], target["sector"])

    # -----------------------------------
    # 탭 2: 내 관심종목 및 포트폴리오
    # -----------------------------------
    with tab2:
        st.markdown("### ⭐ 저장된 내 관심종목 리스트")
        if not st.session_state.custom_stocks:
            st.info("저장된 관심종목이 없습니다. '🔍 종목 검색 및 상세분석' 탭에서 종목을 추가해 보세요.")
        else:
            col1, col2 = st.columns([8, 2])
            with col2:
                if st.button("🗑️ 리스트 전체 비우기", use_container_width=True):
                    st.session_state.custom_stocks = []
                    st.rerun()

            for idx, stock in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([6, 2, 2])
                c1.markdown(f"**{stock['name']}** `{stock['code']}`")
                
                if c2.button("📊 분석하기", key=f"port_analyze_{stock['code']}_{idx}", use_container_width=True):
                    st.session_state.active_analysis = stock
                    add_to_history(stock["code"], stock["name"], stock["sector"])
                    st.success(f"{stock['name']} 분석 화면으로 이동합니다!")
                    time.sleep(0.5)
                    st.rerun() 
                    
                if c3.button("❌ 삭제", key=f"port_del_{stock['code']}_{idx}", use_container_width=True):
                    st.session_state.custom_stocks.pop(idx)
                    st.rerun()
            
            st.caption("※ '분석하기' 버튼을 누르면 첫 번째 탭에서 즉시 상세 리포트가 열립니다.")
