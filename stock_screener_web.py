import streamlit as st
import pandas as pd
import requests
import hashlib
import time
import numpy as np

# --- 보안 및 설정 ---
# 비밀번호 'st0727@6816'의 SHA-256 해시
CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

# --- UI 메인 로직 ---
st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.title("🚀 고도화된 동적 주식 스크리너")

if check_password():
    screener = StockScreener()

    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.success("✅ 로그인 성공!")
        if st.button("로그아웃"):
            st.session_state["password_correct"] = False
            st.rerun()

        st.header("⚙️ 필터 설정")

        st.subheader("📊 기술적 지표")
        available_filters = [
            "RSI 과매도 (30 이하)",
            "RSI 과매수 (70 이상)",
            "MACD 골든크로스",
            "MACD 데드크로스",
            "MACD 0선 돌파",
            "RSI 과매도 + MACD 골든크로스 (강력 매수)",
            "Gap Down",
            "Volume Surge"
        ]

        selected_filters = st.multiselect(
            "적용할 스크리닝 조건을 선택하세요",
            options=available_filters,
            default=["RSI 과매도 (30 이하)"]
        )

        st.divider()
        st.subheader("🔧 세부 설정")

        params = {}
        if "Gap Down" in selected_filters:
            params["gap_threshold"] = st.slider("갭 하락 기준 (%)", 1.0, 15.0, 5.0)
        if "Volume Surge" in selected_filters:
            params["vol_ratio"] = st.number_input("거래량 배수 (평균 대비)", 1.0, 10.0, 2.0)

        st.divider()
        st.info("""
        **💡 지표 설명**
        - **RSI 과매도**: 공포 매도로 반등 가능성
        - **RSI 과매수**: 과열로 조정 가능성
        - **MACD 골든크로스**: 상승 추세 전환 신호
        - **MACD 데드크로스**: 하락 추세 전환 신호
        - **강력 매수**: RSI 과매도 + 골든크로스 동시 발생
        """)

    # ---------------- Tabs (가장 안전: tabs 리스트로 사용) ----------------
    tabs = st.tabs(["📋 기본 종목 리스트", "✏️ 내 종목 추가", "🔍 개별 종목 분석"])

    # =========================
    # Tab 1: 기본 리스트 스크리닝
    # =========================
    with tabs[0]:
        st.info("AI, 의약품, 양자컴퓨터 관련 주요 종목을 분석합니다.")

        if st.button("🔍 스크리닝 시작 (기본 리스트)", type="primary", key="basic_screen"):
            stocks = [
                # AI
                ("035420", "NAVER", "AI"),
                ("035720", "카카오", "AI"),
                ("373220", "LG에너지솔루션", "AI"),
                ("047050", "포스코인터내셔널", "AI"),
                ("058970", "엔케이맥스", "AI"),
                ("052860", "엔에프씨", "AI"),
                ("225570", "넥슨게임즈", "AI"),
                ("293490", "카카오게임즈", "AI"),
                ("018260", "삼성에스디에스", "AI"),
                ("000250", "삼보통상", "AI"),
                # 의약품
                ("207940", "삼성바이오로직스", "의약품"),
                ("068270", "셀트리온", "의약품"),
                ("091990", "셀트리온헬스케어", "의약품"),
                ("326030", "SK바이오팜", "의약품"),
                ("196170", "알테오젠", "의약품"),
                ("214450", "파마리서치", "의약품"),
                ("145020", "휴젤", "의약품"),
                ("000100", "유한양행", "의약품"),
                ("128940", "한미약품", "의약품"),
                ("185750", "종근당", "의약품"),
                ("214150", "클래시스", "의약품"),
                ("183490", "엔지켐생명과학", "의약품"),
                # 양자컴퓨터
                ("005930", "삼성전자", "양자컴퓨터"),
                ("000660", "SK하이닉스", "양자컴퓨터"),
                ("006400", "삼성SDI", "양자컴퓨터"),
                ("042700", "한미반도체", "양자컴퓨터"),
                ("095340", "ISC", "양자컴퓨터"),
                ("189300", "인텔리안테크", "양자컴퓨터"),
                ("067160", "아프리카TV", "양자컴퓨터"),
                ("053800", "안랩", "양자컴퓨터"),
                ("036930", "주성엔지니어링", "양자컴퓨터"),
                ("108320", "LX세미콘", "양자컴퓨터"),
            ]

            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, (code, name, sector) in enumerate(stocks):
                status_text.text(f"분석 중: {name} ({sector}) - ({i+1}/{len(stocks)})")
                data = screener.get_stock_data(code)
                if data:
                    res = screener.check_conditions(code, name, sector, data, selected_filters, params)
                    if res:
                        results.append(res)
                progress_bar.progress((i + 1) / len(stocks))
                time.sleep(0.3)

            status_text.empty()
            progress_bar.empty()

            if results:
                st.success(f"✅ 조건에 맞는 종목 **{len(results)}개**를 찾았습니다!")

                df_results = pd.DataFrame(results)
                sector_counts = df_results["섹터"].value_counts()

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("🤖 AI 관련주", int(sector_counts.get("AI", 0)))
                with c2:
                    st.metric("💊 의약품 관련주", int(sector_counts.get("의약품", 0)))
                with c3:
                    st.metric("⚛️ 양자컴퓨터 관련주", int(sector_counts.get("양자컴퓨터", 0)))

                st.divider()

                st.dataframe(
                    df_results,
                    use_container_width=True,
                    column_config={
                        "섹터": st.column_config.TextColumn("섹터", width="small"),
                        "종목코드": st.column_config.TextColumn("종목코드", width="small"),
                        "종목명": st.column_config.TextColumn("종목명", width="medium"),
                        "현재가": st.column_config.NumberColumn("현재가", format="%d원"),
                        "등락율": st.column_config.TextColumn("등락율", width="small"),
                        "RSI": st.column_config.TextColumn("RSI", width="small"),
                        "MACD": st.column_config.TextColumn("MACD", width="small"),
                        "Signal": st.column_config.TextColumn("Signal", width="small"),
                        "매매신호": st.column_config.TextColumn("매매신호", width="large"),
                        "거래량": st.column_config.NumberColumn("거래량", format="%d"),
                    },
                )
            else:
                st.warning("⚠️ 조건에 부합하는 종목이 현재 없습니다.")
                st.info("💡 필터 조건을 조정하거나 다른 조합을 시도해보세요.")

    # =========================
    # Tab 2: 내 종목 추가 + 관심종목 관리/일괄 스크리닝
    # =========================
    with tabs[1]:
        st.info("관심 있는 종목을 직접 추가하여 분석할 수 있습니다.")

        if "custom_stocks" not in st.session_state:
            st.session_state.custom_stocks = []

        company_search = st.text_input(
            "🔍 기업명을 입력하세요",
            placeholder="예: 삼성전자, NAVER, 카카오",
            help="기업명을 입력하면 종목코드와 섹터가 자동으로 검색됩니다.",
            key="company_search_tab2",
        )

        if company_search:
            code, name, sector = search_stock(company_search)

            if code:
                st.success(f"✅ 찾음: **{name}** (종목코드: {code}, 섹터: {sector})")

                col_add, col_preview = st.columns(2)
                with col_add:
                    if st.button("➕ 관심종목에 추가", use_container_width=True, key="add_to_list"):
                        if not any(stock[0] == code for stock in st.session_state.custom_stocks):
                            st.session_state.custom_stocks.append((code, name, sector))
                            st.success(f"✅ {name}이(가) 관심종목에 추가되었습니다!")
                            st.rerun()
                        else:
                            st.warning("⚠️ 이미 추가된 종목입니다.")

                # (선택) 검색한 종목 바로 미리 분석
                with col_preview:
                    if st.button("📌 지금 바로 미리 분석", use_container_width=True, key="preview_analyze"):
                        with st.spinner(f"{name} 분석 중..."):
                            data = screener.get_stock_data(code)
                            if data:
                                analysis = screener.analyze_stock(code, name, sector, data)
                                if analysis:
                                    st.divider()
                                    st.subheader(f"📈 {name} ({code}) 상세 분석")

                                    a1, a2, a3, a4 = st.columns(4)
                                    with a1:
                                        st.metric("현재가", f"{int(analysis['current']):,}원")
                                    with a2:
                                        change_color = "normal" if analysis["change"] >= 0 else "inverse"
                                        st.metric("등락율", f"{analysis['change']:.2f}%", delta=f"{analysis['change']:.2f}%", delta_color=change_color)
                                    with a3:
                                        st.metric("RSI", f"{analysis['rsi']:.1f}")
                                    with a4:
                                        st.metric("거래량", f"{int(analysis['volume']):,}")
                                else:
                                    st.error("분석 결과를 생성하는 중 오류가 발생했습니다.")
                            else:
                                st.error(f"⚠️ '{name} ({code})' 데이터를 가져올 수 없습니다.")
            else:
                st.warning("⚠️ 검색 결과가 없습니다. 기업명을 다시 확인해 주세요.")

        st.divider()

        # 관심종목 리스트
        if st.session_state.custom_stocks:
            st.subheader(f"⭐ 내 관심종목 ({len(st.session_state.custom_stocks)}개)")

            if st.button("🗑️ 전체 삭제", use_container_width=False, key="delete_all_custom"):
                st.session_state.custom_stocks = []
                st.success("모든 종목이 삭제되었습니다.")
                st.rerun()

            for idx, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.text(f"{idx+1}. [{sector}] {name} ({code})")
                with col_del:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.custom_stocks.pop(idx)
                        st.rerun()

            st.divider()

            # 관심종목 일괄 스크리닝
            if st.button("🔍 관심종목 일괄 스크리닝", type="primary", key="custom_screen"):
                results = []
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                    status_text.text(f"분석 중: {name} ({sector}) - ({i+1}/{len(st.session_state.custom_stocks)})")
                    data = screener.get_stock_data(code)
                    if data:
                        res = screener.check_conditions(code, name, sector, data, selected_filters, params)
                        if res:
                            results.append(res)
                    else:
                        st.warning(f"⚠️ {name} ({code}) 데이터를 가져올 수 없습니다.")
                    progress_bar.progress((i + 1) / len(st.session_state.custom_stocks))
                    time.sleep(0.3)

                status_text.empty()
                progress_bar.empty()

                if results:
                    st.success(f"✅ 조건에 맞는 종목 **{len(results)}개**를 찾았습니다!")
                    df_results = pd.DataFrame(results)

                    st.dataframe(
                        df_results,
                        use_container_width=True,
                        column_config={
                            "섹터": st.column_config.TextColumn("섹터", width="small"),
                            "종목코드": st.column_config.TextColumn("종목코드", width="small"),
                            "종목명": st.column_config.TextColumn("종목명", width="medium"),
                            "현재가": st.column_config.NumberColumn("현재가", format="%d원"),
                            "등락율": st.column_config.TextColumn("등락율", width="small"),
                            "RSI": st.column_config.TextColumn("RSI", width="small"),
                            "MACD": st.column_config.TextColumn("MACD", width="small"),
                            "Signal": st.column_config.TextColumn("Signal", width="small"),
                            "매매신호": st.column_config.TextColumn("매매신호", width="large"),
                            "거래량": st.column_config.NumberColumn("거래량", format="%d"),
                        },
                    )
                else:
                    st.warning("⚠️ 조건에 부합하는 종목이 현재 없습니다.")
                    st.info("💡 필터 조건을 조정하거나 다른 조합을 시도해보세요.")
        else:
            st.info("👆 위에서 기업명을 검색하여 관심종목에 추가해주세요.")

    # =========================
    # Tab 3: 개별 종목 분석
    # =========================
    with tabs[2]:
        st.info("종목 하나를 선택하여 상세 분석 및 매매 추천을 받아보세요.")

        search_query = st.text_input(
            "🔍 분석할 기업명 입력",
            placeholder="예: 삼성전자, NAVER, 셀트리온",
            key="individual_search"
        )

        if search_query:
            code, name, sector = search_stock(search_query)

            if not code:
                st.warning(f"⚠️ '{search_query}'에 대한 검색 결과가 없습니다.")
            else:
                st.success(f"✅ 찾음: **{name}** (종목코드: {code}, 섹터: {sector})")

                if st.button("📊 상세 분석 시작", type="primary", key="start_detail_analysis"):
                    with st.spinner(f"{name} 데이터 수집 및 분석 중..."):
                        data = screener.get_stock_data(code)

                        if not data:
                            st.error(f"⚠️ {name} ({code}) 데이터를 가져올 수 없습니다.")
                        else:
                            analysis = screener.analyze_stock(code, name, sector, data)

                            if not analysis:
                                st.error("분석 중 오류가 발생했습니다.")
                            else:
                                st.divider()
                                st.header(f"📈 {name} ({code}) 상세 분석 리포트")
                                st.caption(f"섹터: {sector}")

                                st.subheader("💰 현재 시세")
                                col1, col2, col3, col4 = st.columns(4)

                                with col1:
                                    st.metric("현재가", f"{int(analysis['current']):,}원")
                                with col2:
                                    change_color = "normal" if analysis["change"] >= 0 else "inverse"
                                    st.metric("등락율", f"{analysis['change']:.2f}%", delta=f"{analysis['change']:.2f}%", delta_color=change_color)
                                with col3:
                                    st.metric("RSI", f"{analysis['rsi']:.1f}")
                                with col4:
                                    st.metric("거래량", f"{int(analysis['volume']):,}")

                                st.divider()

                                st.subheader("💡 AI 매매 추천")
                                rec_col1, rec_col2 = st.columns([1, 4])
                                with rec_col1:
                                    st.markdown(f"# {analysis['recommendation_color']}")
                                with rec_col2:
                                    st.markdown(f"## **{analysis['recommendation']}**")

                                st.divider()

                                st.subheader("📊 기술적 지표 분석")
                                indicator_col1, indicator_col2 = st.columns(2)

                                with indicator_col1:
                                    st.markdown("### RSI (상대강도지수)")
                                    st.progress(int(analysis["rsi"]))
                                    if analysis["rsi"] <= 30:
                                        st.success(f"🟢 **RSI {analysis['rsi']:.1f}** - 과매도 구간")
                                    elif analysis["rsi"] >= 70:
                                        st.error(f"🔴 **RSI {analysis['rsi']:.1f}** - 과매수 구간")
                                    else:
                                        st.info(f"🟡 **RSI {analysis['rsi']:.1f}** - 중립 구간")

                                with indicator_col2:
                                    st.markdown("### MACD (추세 분석)")
                                    st.write(f"**MACD Line**: {analysis['macd']:.2f}")
                                    st.write(f"**Signal Line**: {analysis['signal']:.2f}")

                                    if analysis["macd_cross"] == "골든크로스":
                                        st.success("🟢 **골든크로스 발생!**")
                                    elif analysis["macd_cross"] == "데드크로스":
                                        st.error("🔴 **데드크로스 발생!**")
                                    elif analysis["macd"] > 0:
                                        st.success("🟢 **상승 추세 (MACD > 0)**")
                                    else:
                                        st.warning("🟡 **하락 추세 (MACD < 0)**")

                                if analysis.get("signals"):
                                    st.divider()
                                    st.subheader("🎯 감지된 추가 신호")
                                    for sig in analysis["signals"]:
                                        st.markdown(f"- {sig}")




