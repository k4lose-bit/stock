import streamlit as st
import pandas as pd
import requests
import hashlib
import time
import numpy as np

# =============================
# 보안 및 설정
# =============================
# 비밀번호 'st0727@6816'의 SHA-256 해시
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


# =============================
# 한국 주요 종목 데이터베이스
# =============================
STOCK_DATABASE = {
    # AI 관련주
    "NAVER": ("035420", "AI"),
    "네이버": ("035420", "AI"),
    "카카오": ("035720", "AI"),
    "LG에너지솔루션": ("373220", "AI"),
    "포스코인터내셔널": ("047050", "AI"),
    "엔케이맥스": ("058970", "AI"),
    "엔에프씨": ("052860", "AI"),
    "넥슨게임즈": ("225570", "AI"),
    "카카오게임즈": ("293490", "AI"),
    "삼성에스디에스": ("018260", "AI"),
    "삼성SDS": ("018260", "AI"),
    "삼보통상": ("000250", "AI"),

    # 의약품/바이오 관련주
    "삼성바이오로직스": ("207940", "의약품"),
    "셀트리온": ("068270", "의약품"),
    "셀트리온헬스케어": ("091990", "의약품"),
    "SK바이오팜": ("326030", "의약품"),
    "알테오젠": ("196170", "의약품"),
    "파마리서치": ("214450", "의약품"),
    "휴젤": ("145020", "의약품"),
    "유한양행": ("000100", "의약품"),
    "한미약품": ("128940", "의약품"),
    "종근당": ("185750", "의약품"),
    "클래시스": ("214150", "의약품"),
    "엔지켐생명과학": ("183490", "의약품"),

    # 양자컴퓨터/반도체 관련주
    "삼성전자": ("005930", "양자컴퓨터"),
    "SK하이닉스": ("000660", "양자컴퓨터"),
    "삼성SDI": ("006400", "양자컴퓨터"),
    "한미반도체": ("042700", "양자컴퓨터"),
    "ISC": ("095340", "양자컴퓨터"),
    "인텔리안테크": ("189300", "양자컴퓨터"),
    "아프리카TV": ("067160", "양자컴퓨터"),
    "안랩": ("053800", "양자컴퓨터"),
    "주성엔지니어링": ("036930", "양자컴퓨터"),
    "LX세미콘": ("108320", "양자컴퓨터"),

    # 기타 주요 종목
    "LG화학": ("051910", "기타"),
    "현대차": ("005380", "기타"),
    "기아": ("000270", "기타"),
    "POSCO홀딩스": ("005490", "기타"),
    "포스코홀딩스": ("005490", "기타"),
    "삼성물산": ("028260", "기타"),
    "현대모비스": ("012330", "기타"),
    "LG전자": ("066570", "기타"),
    "SK이노베이션": ("096770", "기타"),
    "LG": ("003550", "기타"),
    "SK텔레콤": ("017670", "기타"),
    "SK": ("034730", "기타"),
    "KT&G": ("033780", "기타"),
}


def search_stock(query: str):
    """기업명으로 종목코드와 섹터 검색"""
    if not query:
        return None, None, None

    q = query.strip().upper()

    # 정확 일치
    for name, (code, sector) in STOCK_DATABASE.items():
        if name.upper() == q:
            return code, name, sector

    # 부분 일치(첫 매칭 반환)
    matches = []
    for name, (code, sector) in STOCK_DATABASE.items():
        if q in name.upper():
            matches.append((code, name, sector))

    if matches:
        return matches[0]

    return None, None, None


# =============================
# 스크리닝 엔진
# =============================
class StockScreener:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

    @st.cache_data(ttl=600)
    def get_stock_data(_self, code):
        """네이버 금융 일별 시세 수집 (최근 약 60일)"""
        try:
            all_data = []
            for page in range(1, 4):  # 3페이지 = 약 60일
                url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={page}"
                res = requests.get(url, headers=_self.headers, timeout=10)
                df_list = pd.read_html(res.text)

                if not df_list:
                    break

                df = df_list[0].dropna()
                if df.empty:
                    break

                all_data.append(df)
                time.sleep(0.1)

            if not all_data:
                return None

            combined_df = pd.concat(all_data, ignore_index=True)
            combined_df = combined_df.sort_values("날짜").reset_index(drop=True)

            return {
                "current": float(combined_df.iloc[-1]["종가"]),
                "open": float(combined_df.iloc[-1]["시가"]),
                "prev_close": float(combined_df.iloc[-2]["종가"]) if len(combined_df) > 1 else float(combined_df.iloc[-1]["종가"]),
                "volume": float(combined_df.iloc[-1]["거래량"]),
                "close_prices": combined_df["종가"].astype(float).tolist(),
                "volumes": combined_df["거래량"].astype(float).tolist(),
            }
        except Exception:
            return None

    def calculate_rsi(self, prices, period=14):
        """RSI 지표 계산"""
        if len(prices) < period + 1:
            return None

        series = pd.Series(prices)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        loss_val = loss.iloc[-1]
        if loss_val == 0:
            return 100

        rs = gain.iloc[-1] / loss_val
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """MACD 지표 계산"""
        if len(prices) < slow + signal:
            return None, None, None

        series = pd.Series(prices)
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

    def check_macd_crossover(self, prices):
        """MACD 골든/데드 크로스 확인"""
        if len(prices) < 35:
            return None

        series = pd.Series(prices)
        ema_fast = series.ewm(span=12, adjust=False).mean()
        ema_slow = series.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()

        macd_current = macd_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        signal_current = signal_line.iloc[-1]
        signal_prev = signal_line.iloc[-2]

        if macd_prev <= signal_prev and macd_current > signal_current:
            return "골든크로스"
        elif macd_prev >= signal_prev and macd_current < signal_current:
            return "데드크로스"

        return None

    def analyze_stock(self, code, name, sector, data):
        """개별 종목 상세 분석"""
        try:
            prices = data["close_prices"]

            rsi = self.calculate_rsi(prices)
            if rsi is None:
                return None

            macd, signal, histogram = self.calculate_macd(prices)
            if macd is None:
                return None

            macd_cross = self.check_macd_crossover(prices)

            gap = ((data["open"] - data["prev_close"]) / data["prev_close"]) * 100

            # 거래량 급증 확인
            volume_surge = False
            if len(data["volumes"]) >= 5:
                avg_vol = sum(data["volumes"][-5:]) / 5
                if data["volume"] >= avg_vol * 2.0:
                    volume_surge = True

            signals = []
            recommendation = "관망"
            recommendation_color = "🟡"

            # 강력 매수
            if rsi <= 30 and macd_cross == "골든크로스":
                signals.append("⭐ 강력 매수 신호")
                recommendation = "적극 매수"
                recommendation_color = "🟢"
            elif rsi <= 30:
                signals.append("RSI 과매도 (반등 가능성)")
                recommendation = "매수 고려"
                recommendation_color = "🟢"
            elif macd_cross == "골든크로스":
                signals.append("MACD 골든크로스 (상승 전환)")
                recommendation = "매수 고려"
                recommendation_color = "🟢"
            elif macd > 0 and rsi < 70:
                signals.append("상승 추세 지속")
                recommendation = "보유/추가 매수"
                recommendation_color = "🟢"

            # 매도 신호 우선 적용
            if rsi >= 70:
                signals.append("RSI 과매수 (조정 가능성)")
                recommendation = "매도 고려"
                recommendation_color = "🔴"
            if macd_cross == "데드크로스":
                signals.append("MACD 데드크로스 (하락 전환)")
                recommendation = "매도 고려"
                recommendation_color = "🔴"

            # 추가 신호
            if gap < -3:
                signals.append(f"갭 하락 {gap:.1f}%")
            if volume_surge:
                signals.append("거래량 급증")
            if macd > 0:
                signals.append("MACD 0선 상단 (강세)")

            return {
                "sector": sector,
                "code": code,
                "name": name,
                "current": data["current"],
                "change": ((data["current"] - data["prev_close"]) / data["prev_close"]) * 100,
                "rsi": rsi,
                "macd": macd,
                "signal": signal,
                "macd_cross": macd_cross,
                "gap": gap,
                "volume": data["volume"],
                "signals": signals,
                "recommendation": recommendation,
                "recommendation_color": recommendation_color,
            }
        except Exception:
            return None

    def check_conditions(self, code, name, sector, data, selected_filters, params):
        """다중 조건 AND 로직 필터링"""
        try:
            prices = data["close_prices"]
            signals = []

            rsi = self.calculate_rsi(prices)
            if rsi is None:
                return None

            macd, signal, histogram = self.calculate_macd(prices)
            if macd is None:
                return None

            macd_cross = self.check_macd_crossover(prices)

            if "RSI 과매도 (30 이하)" in selected_filters:
                if rsi > 30:
                    return None
                signals.append("RSI 과매도")

            if "RSI 과매수 (70 이상)" in selected_filters:
                if rsi < 70:
                    return None
                signals.append("RSI 과매수")

            if "MACD 골든크로스" in selected_filters:
                if macd_cross != "골든크로스":
                    return None
                signals.append("MACD 골든크로스")

            if "MACD 데드크로스" in selected_filters:
                if macd_cross != "데드크로스":
                    return None
                signals.append("MACD 데드크로스")

            if "RSI 과매도 + MACD 골든크로스 (강력 매수)" in selected_filters:
                if not (rsi <= 30 and macd_cross == "골든크로스"):
                    return None
                signals.append("⭐ 강력 매수 신호")

            if "MACD 0선 돌파" in selected_filters:
                if macd <= 0:
                    return None
                signals.append("MACD 0선 돌파")

            if "Gap Down" in selected_filters:
                gap = ((data["open"] - data["prev_close"]) / data["prev_close"]) * 100
                if gap > -params.get("gap_threshold", 5.0):
                    return None
                signals.append(f"갭하락 {gap:.1f}%")

            if "Volume Surge" in selected_filters:
                if len(data["volumes"]) >= 5:
                    avg_vol = sum(data["volumes"][-5:]) / 5
                    if data["volume"] < avg_vol * params.get("vol_ratio", 2.0):
                        return None
                    signals.append("거래량 급증")

            return {
                "섹터": sector,
                "종목코드": code,
                "종목명": name,
                "현재가": int(data["current"]),
                "등락율": f"{round(((data['current'] - data['prev_close']) / data['prev_close']) * 100, 2)}%",
                "RSI": f"{rsi:.1f}",
                "MACD": f"{macd:.2f}",
                "Signal": f"{signal:.2f}",
                "매매신호": " | ".join(signals) if signals else "-",
                "거래량": int(data["volume"]),
            }
        except Exception:
            return None


# =============================
# UI 메인
# =============================
st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.title("🚀 고도화된 동적 주식 스크리너")

# 관심종목 세션 초기화(로그인 전에도 안전)
if "custom_stocks" not in st.session_state:
    st.session_state.custom_stocks = []

if check_password():
    screener = StockScreener()

    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.success("✅ 로그인 성공!")
        if st.button("로그아웃", key="logout_btn"):
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
            "Volume Surge",
        ]

        selected_filters = st.multiselect(
            "적용할 스크리닝 조건을 선택하세요",
            options=available_filters,
            default=["RSI 과매도 (30 이하)"],
            key="selected_filters",
        )

        st.divider()
        st.subheader("🔧 세부 설정")

        params = {}
        if "Gap Down" in selected_filters:
            params["gap_threshold"] = st.slider("갭 하락 기준 (%)", 1.0, 15.0, 5.0, key="gap_threshold")
        if "Volume Surge" in selected_filters:
            params["vol_ratio"] = st.number_input("거래량 배수 (평균 대비)", 1.0, 10.0, 2.0, key="vol_ratio")

        st.divider()
        st.info(
            """
            **💡 지표 설명**
            - **RSI 과매도**: 공포 매도로 반등 가능성
            - **RSI 과매수**: 과열로 조정 가능성
            - **MACD 골든크로스**: 상승 추세 전환 신호
            - **MACD 데드크로스**: 하락 추세 전환 신호
            - **강력 매수**: RSI 과매도 + 골든크로스 동시 발생
            """
        )

    # ---------------- Tabs (안전: tabs 리스트로) ----------------
    tabs = st.tabs(["📋 기본 종목 리스트", "✏️ 내 종목 추가", "🔍 개별 종목 분석"])

    # =============================
    # Tab 1: 기본 종목 리스트
    # =============================
    with tabs[0]:
        st.info("AI, 의약품, 양자컴퓨터 관련 주요 종목을 분석합니다.")

        if st.button("🔍 스크리닝 시작 (기본 리스트)", type="primary", key="basic_screen"):
            stocks = [
                # AI 관련주
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

                # 의약품/바이오
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

    # =============================
    # Tab 2: 내 종목 추가 + 관심종목 관리/일괄 스크리닝
    # =============================
    with tabs[1]:
        st.info("관심 있는 종목을 직접 추가하여 분석할 수 있습니다.")

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

                                    st.divider()

                                    st.subheader("💡 매매 추천")
                                    r1, r2 = st.columns([1, 3])
                                    with r1:
                                        st.markdown(f"## {analysis.get('recommendation_color', '🟡')}")
                                    with r2:
                                        st.markdown(f"### **{analysis.get('recommendation', '관망')}**")

                                    if analysis.get("signals"):
                                        st.divider()
                                        st.subheader("🎯 감지된 신호")
                                        for sig in analysis["signals"]:
                                            st.markdown(f"- {sig}")
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

    # =============================
    # Tab 3: 개별 종목 분석
    # =============================
    with tabs[2]:
        st.info("종목 하나를 선택하여 상세 분석 및 매매 추천을 받아보세요.")

        search_query = st.text_input(
            "🔍 분석할 기업명 입력",
            placeholder="예: 삼성전자, NAVER, 셀트리온",
            key="individual_search",
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
                                r1, r2 = st.columns([1, 4])
                                with r1:
                                    st.markdown(f"# {analysis['recommendation_color']}")
                                with r2:
                                    st.markdown(f"## **{analysis['recommendation']}**")

                                st.divider()
                                st.subheader("📊 기술적 지표 분석")
                                i1, i2 = st.columns(2)

                                with i1:
                                    st.markdown("### RSI (상대강도지수)")
                                    st.progress(int(analysis["rsi"]))
                                    if analysis["rsi"] <= 30:
                                        st.success(f"🟢 **RSI {analysis['rsi']:.1f}** - 과매도 구간")
                                    elif analysis["rsi"] >= 70:
                                        st.error(f"🔴 **RSI {analysis['rsi']:.1f}** - 과매수 구간")
                                    else:
                                        st.info(f"🟡 **RSI {analysis['rsi']:.1f}** - 중립 구간")

                                with i2:
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
else:
    st.info("🔒 왼쪽 사이드바에서 비밀번호로 로그인해 주세요.")
