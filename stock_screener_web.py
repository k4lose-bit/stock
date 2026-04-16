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
            title = item.find('title').text
            link = item.find('link').text
            news_list.append({"title": title, "link": link})
        return news_list
    except Exception as e:
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
            ko_sector = raw_sector
            ko_industry = raw_industry
            ko_summary = raw_summary + "\n\n(일시적인 번역기 오류로 원문을 제공합니다.)"
            
        return {
            "sector": ko_sector,
            "industry": ko_industry,
            "summary": ko_summary,
            "website": info.get("website", ""),
            "marketCap": info.get("marketCap", 0),
            "pe": info.get("trailingPE", 0),
            "eps": info.get("trailingEps", 0),
            "div_yield": info.get("dividendYield", 0),
            "high52": info.get("fiftyTwoWeekHigh", 0),
            "low52": info.get("fiftyTwoWeekLow", 0)
        }
    except Exception:
        return None

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        pw_input = st.sidebar.text_input("접속 비밀번호", type="password", key="pw_input")
        if st.sidebar.button("로그인", key="login_btn"):
            if pw_input:
                entered_hash = hashlib.sha256(pw_input.encode("utf-8")).hexdigest()
                if entered_hash == CORRECT_PASSWORD_HASH:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.sidebar.error("❌ 비밀번호가 틀렸습니다.")
        return False
    return True

st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.title("🚀 Stock Screener Pro (풀옵션 스크리너 📊)")

if "custom_stocks" not in st.session_state:
    st.session_state.custom_stocks = []
if "offline_price_data" not in st.session_state:
    st.session_state.offline_price_data = {}

if check_password():
    fetcher = DataFetcher()
    analyzer = StockAnalyzer()
    exc_rate = get_exchange_rate()

    with st.sidebar:
        st.success("✅ 로그인 성공!")
        if st.button("로그아웃", key="logout_btn"):
            st.session_state["password_correct"] = False
            st.rerun()

        st.header("⚙️ 필터 설정")
        # 🌟 새로운 지표들이 필터에 추가되었습니다
        available_filters = [
            "RSI 과매도 (30 이하)", "RSI 과매수 (70 이상)",
            "MACD 골든크로스", "MACD 데드크로스",
            "볼린저 밴드 하단 터치", "20일선 상향 돌파",
            "거래량 급증"
        ]
        selected_filters = st.multiselect(
            "적용할 조건을 선택하세요", options=available_filters, default=["RSI 과매도 (30 이하)"]
        )

    tab1, tab2, tab3 = st.tabs(["✏️ 내 종목 추가", "⭐ 관심종목 스크리닝", "🔍 개별 종목 상세분석"])

    with tab1:
        st.info("기업명을 검색해 관심종목에 추가합니다.")
        query = st.text_input("🔍 기업명 입력", placeholder="예: 삼성전자, IREN", key="add_query")
        if query:
            cands = search_candidates(query, limit=20)
            if cands.empty:
                st.error("검색 결과가 없습니다.")
            else:
                options = [f"{row['회사명']} ({row['종목코드']})" for _, row in cands.iterrows()]
                pick = st.selectbox("✅ 후보 선택", options, key="add_pick")
                idx = options.index(pick)
                
                code = str(cands.iloc[idx]["종목코드"])
                if code.isdigit():
                    code = code.zfill(6)
                
                name = str(cands.iloc[idx]["회사명"])
                sector = str(cands.iloc[idx].get("섹터", "기타"))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("➕ 관심종목에 추가", use_container_width=True):
                        if not any(s[0] == code for s in st.session_state.custom_stocks):
                            st.session_state.custom_stocks.append((code, name, sector))
                            st.success("✅ 추가 완료!")
                            st.rerun()
                        else:
                            st.warning("⚠️ 이미 추가된 종목입니다.")
                with col2:
                    if st.button("📌 지금 바로 미리 분석", use_container_width=True):
                        with st.spinner(f"{name} 수집 중..."):
                            data = fetcher.get_stock_data(code)
                        if data:
                            an = analyzer.analyze(code, name, sector, data)
                            if an:
                                st.divider()
                                m1, m2, m3, m4 = st.columns(4)
                                
                                krw_price = f"{int(an['current']):,}원" if an['current'] > 1000 else f"${an['current']:.2f} (약 {int(an['current'] * exc_rate):,}원)"
                                m1.metric("현재가", krw_price)
                                m2.metric("등락율", f"{an['change']:.2f}%")
                                m3.metric("RSI", f"{an['rsi']:.1f}")
                                m4.metric("거래량", f"{int(an['volume']):,}")
                                st.markdown(f"### {an['recommendation_color']} **{an['recommendation']}**")

        st.divider()
        db = get_stock_db()
        st.caption(f"현재 인식된 기본 종목 수: {len(db):,}개")
        st.dataframe(db.head(20), use_container_width=True)

    with tab2:
        if not st.session_state.custom_stocks:
            st.warning("관심종목이 없습니다. '내 종목 추가'에서 먼저 추가하세요.")
        else:
            if st.button("🗑️ 전체 삭제"):
                st.session_state.custom_stocks = []
                st.rerun()
            for idx, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                a, b = st.columns([6, 1])
                a.text(f"{idx+1}. {name} ({code}) [{sector}]")
                if b.button("❌", key=f"del_{idx}"):
                    st.session_state.custom_stocks.pop(idx)
                    st.rerun()

            st.divider()
            if st.button("🔍 관심종목 일괄 스크리닝", type="primary"):
                results = []
                progress = st.progress(0)
                total = len(st.session_state.custom_stocks)
                
                for i, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                    data = fetcher.get_stock_data(code)
                    if data:
                        an = analyzer.analyze(code, name, sector, data)
                        if an:
                            pass_all = True
                            match_signals = []
                            
                            # 필터 검사
                            for f in selected_filters:
                                if f == "RSI 과매도 (30 이하)" and an['rsi'] <= 30: match_signals.append("RSI 과매도")
                                elif f == "MACD 골든크로스" and an['macd_cross'] == "골든크로스": match_signals.append("MACD 골든크로스")
                                elif f in an['signals']: match_signals.append(f)
                                else: pass_all = False
                                
                            if pass_all and (selected_filters == [] or match_signals):
                                krw_price = f"{int(an['current']):,}원" if an['current'] > 1000 else f"${an['current']:.2f} ({int(an['current'] * exc_rate):,}원)"
                                results.append({
                                    "종목명": name, "현재가": krw_price,
                                    "RSI": f"{an['rsi']:.1f}",
                                    "신호": " | ".join(match_signals) if match_signals else "-"
                                })
                    progress.progress((i + 1) / total)
                    time.sleep(0.1)
                
                progress.empty()
                if results:
                    st.success(f"✅ 조건 부합: {len(results)}개")
                    st.dataframe(pd.DataFrame(results), use_container_width=True)
                else:
                    st.warning("조건에 맞는 종목이 없습니다.")

    with tab3:
        query = st.text_input("🔍 분석할 기업명", key="single_query", placeholder="기업명이나 티커(IREN)를 입력하세요")
        if query:
            cands = search_candidates(query, limit=20)
            if not cands.empty:
                opts = [f"{row['회사명']} ({row['종목코드']})" for _, row in cands.iterrows()]
                pick = st.selectbox("✅ 후보 선택", opts, key="single_pick")
                idx = opts.index(pick)
                
                code = str(cands.iloc[idx]["종목코드"])
                if code.isdigit():
                    code = code.zfill(6)
                
                name = str(cands.iloc[idx]["회사명"])
                sector = str(cands.iloc[idx].get("섹터", "기타"))

                if st.button("📊 상세 분석 시작", type="primary"):
                    with st.spinner(f"{name} 데이터를 분석 중입니다..."):
                        data = fetcher.get_stock_data(code)
                        news_list = get_company_news(name)
                        profile = get_company_profile(code)
                        
                        if data:
                            an = analyzer.analyze(code, name, sector, data)
                            if an:
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
                                    if profile['website']:
                                        st.markdown(f"**웹사이트:** [{profile['website']}]({profile['website']})")
                                    
                                    st.markdown("**📊 주요 재무/시장 지표**")
                                    # 🌟 N/A 거슬림 해결: 야후 파이낸스 미제공 시 깔끔하게 '-'로 출력되도록 수정
                                    f1, f2, f3, f4, f5 = st.columns(5)
                                    
                                    mc = profile.get('marketCap', 0)
                                    if mc and mc > 0:
                                        mc_str = f"{mc // 100000000:,}억 원" if code.isdigit() else f"${mc // 1000000:,}M"
                                    else:
                                        mc_str = "-"
                                        
                                    f1.metric("시가총액", mc_str)
                                    f2.metric("PER", f"{profile['pe']:.2f}" if profile.get('pe') else "-")
                                    f3.metric("EPS", f"{profile['eps']:.2f}" if profile.get('eps') else "-")
                                    
                                    dy = profile.get('div_yield')
                                    f4.metric("배당수익률", f"{dy*100:.2f}%" if dy else "-")
                                    
                                    h52, l52 = profile.get('high52'), profile.get('low52')
                                    if h52 and l52:
                                        f5.metric("52주 고/저", f"{l52:.1f} ~ {h52:.1f}")
                                    else:
                                        f5.metric("52주 고/저", "-")
                                        
                                    # 한국 주식 데이터 부재에 대한 안내 캡션 추가
                                    st.caption("※ 정보가 '-'로 표시되는 항목은 야후 파이낸스에서 해당 종목의 재무 데이터를 제공하지 않는 경우입니다.")

                                    st.info(profile['summary'])
                                else:
                                    st.write("해당 기업의 개요 정보를 불러올 수 없습니다.")

                                st.divider()
                                
                                st.subheader("💡 종합 지표 분석 의견")
                                st.markdown(f"### {an['recommendation_color']} **{an['recommendation']}**")
                                for detail in an['details']:
                                    st.success(detail)
                                
                                st.divider()

                                st.subheader(f"📰 '{name}' 주요 이슈 및 투자분석")
                                judal_search_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(name)}+투자분석"
                                st.info(f"💡 **AI 테마 및 추가 분석 확인하기:** [👉 주달(Judal)에서 '{name}' 분석 결과 보기]({judal_search_url})")

                                if news_list:
                                    for news in news_list:
                                        st.markdown(f"🔗 [{news['title']}]({news['link']})")
                                else:
                                    st.write("최근 일주일 이내에 등록된 주요 뉴스가 없습니다.")
                        else:
                            st.error("데이터를 가져올 수 없습니다. 종목 코드나 네트워크 상태를 확인해주세요.")
else:
    st.info("🔒 로그인해 주세요.")
