<div style="border: 1px solid #d3d3d3; padding: 15px; border-radius: 5px; font-family: monospace; line-height: 1.5; background-color: transparent; white-space: pre; overflow-x: auto;">
import streamlit as st
import pandas as pd
import hashlib
import time

from modules.data_fetcher import DataFetcher, get_stock_db, search_candidates, parse_ohlcv_csv
from modules.analyzer import StockAnalyzer

CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

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
st.title("🚀 Stock Screener Pro (CSV 없는 자동화 버전 ⚡)")

if "custom_stocks" not in st.session_state:
st.session_state.custom_stocks = []
if "offline_price_data" not in st.session_state:
st.session_state.offline_price_data = {}

if check_password():
fetcher = DataFetcher()
analyzer = StockAnalyzer()

with st.sidebar:
    st.success("✅ 로그인 성공!")
    if st.button("로그아웃", key="logout_btn"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.header("⚙️ 필터 설정")
    available_filters = [
        "RSI 과매도 (30 이하)", "RSI 과매수 (70 이상)",
        "MACD 골든크로스", "MACD 데드크로스", "MACD 0선 돌파",
        "RSI 과매도 + MACD 골든크로스 (강력 매수)", "Gap Down", "Volume Surge"
    ]
    selected_filters = st.multiselect(
        "적용할 스크리닝 조건을 선택하세요", options=available_filters, default=["RSI 과매도 (30 이하)"]
    )

    st.divider()
    st.subheader("🔧 세부 설정")
    params = {}
    if "Gap Down" in selected_filters:
        params["gap_threshold"] = st.slider("갭 하락 기준 (%)", 1.0, 15.0, 5.0)
    if "Volume Surge" in selected_filters:
        params["vol_ratio"] = st.number_input("거래량 배수 (평균 대비)", 1.0, 10.0, 2.0)

    # CSV 업로드 창은 삭제했습니다!

tab1, tab2, tab3 = st.tabs(["✏️ 내 종목 추가", "⭐ 관심종목 스크리닝", "🔍 개별 종목 분석"])

with tab1:
    st.info("기업명을 검색해 관심종목에 추가합니다.")
    query = st.text_input("🔍 기업명 입력", placeholder="예: 삼성전자", key="add_query")
    if query:
        cands = search_candidates(query, limit=20)
        if cands.empty:
            st.error("검색 결과가 없습니다.")
        else:
            options = [f"{row['회사명']} ({row['종목코드']})" for _, row in cands.iterrows()]
            pick = st.selectbox("✅ 후보 선택", options, key="add_pick")
            idx = options.index(pick)
            code = str(cands.iloc[idx]["종목코드"]).zfill(6)
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
                            m1.metric("현재가", f"{int(an['current']):,}원")
                            m2.metric("등락율", f"{an['change']:.2f}%")
                            m3.metric("RSI", f"{an['rsi']:.1f}")
                            m4.metric("거래량", f"{int(an['volume']):,}")
                            st.markdown(f"### {an['recommendation_color']} **{an['recommendation']}**")

    st.divider()
    db = get_stock_db()
    st.caption(f"현재 인식된 기본 종목 수: {len(db):,}개")
    st.dataframe(db.head(30), use_container_width=True)

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
                        
                        if "RSI 과매도 (30 이하)" in selected_filters:
                            if an['rsi'] > 30: pass_all = False
                            else: match_signals.append("RSI 과매도")
                        
                        if "MACD 골든크로스" in selected_filters:
                            if an['macd_cross'] != "골든크로스": pass_all = False
                            else: match_signals.append("MACD 골든크로스")
                            
                        if pass_all and (selected_filters == [] or match_signals):
                            results.append({
                                "종목명": name, "현재가": int(an["current"]),
                                "등락율": f"{an['change']:.2f}%", "RSI": f"{an['rsi']:.1f}",
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
    query = st.text_input("🔍 분석할 기업명", key="single_query")
    if query:
        cands = search_candidates(query, limit=20)
        if not cands.empty:
            opts = [f"{row['회사명']} ({row['종목코드']})" for _, row in cands.iterrows()]
            pick = st.selectbox("✅ 후보 선택", opts, key="single_pick")
            idx = opts.index(pick)
            code = str(cands.iloc[idx]["종목코드"]).zfill(6)
            name = str(cands.iloc[idx]["회사명"])
            sector = str(cands.iloc[idx].get("섹터", "기타"))

            if st.button("📊 상세 분석 시작", type="primary"):
                with st.spinner(f"{name} 분석 중..."):
                    data = fetcher.get_stock_data(code)
                    if data:
                        an = analyzer.analyze(code, name, sector, data)
                        if an:
                            st.header(f"📈 {name} 상세 분석")
                            c1, c2, c3 = st.columns(3)
                            c1.metric("현재가", f"{int(an['current']):,}원")
                            c2.metric("RSI", f"{an['rsi']:.1f}")
                            c3.metric("추천", an['recommendation'])
                            if an.get("signals"):
                                for s in an["signals"]: st.markdown(f"- {s}")
else:
st.info("🔒 로그인해 주세요.")

</div>
