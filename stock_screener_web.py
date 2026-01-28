import streamlit as st
import pandas as pd
import requests
import hashlib
import time
import numpy as np
from io import StringIO
from datetime import datetime

# =============================
# 보안 및 설정
# =============================
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
# (옵션) 최소 내장 DB (CSV 없을 때도 앱은 뜨게)
# =============================
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


# =============================
# 종목 DB 로딩 (완전 안정형)
# - 1순위: 레포 내 파일 krx_stock_list.csv
# - 2순위: 앱에서 업로드한 CSV (세션 유지)
# - 3순위: 내장 최소 CSV
# =============================
@st.cache_data(ttl=60 * 60 * 24)
def load_stock_db_from_repo(filepath: str = "krx_stock_list.csv") -> pd.DataFrame | None:
    try:
        df = pd.read_csv(filepath)
        return df
    except Exception:
        return None


def normalize_stock_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    요구 컬럼: 회사명, 종목코드, (선택) 섹터
    """
    df = df.copy()

    # 다양한 컬럼명을 허용하고 표준화
    col_map = {}
    lower_cols = {c.lower(): c for c in df.columns}

    # 회사명 후보
    for cand in ["회사명", "name", "corp_name", "company", "companyname"]:
        if cand.lower() in lower_cols:
            col_map[lower_cols[cand.lower()]] = "회사명"
            break

    # 종목코드 후보
    for cand in ["종목코드", "code", "symbol", "ticker", "stock_code"]:
        if cand.lower() in lower_cols:
            col_map[lower_cols[cand.lower()]] = "종목코드"
            break

    # 섹터 후보(없으면 생성)
    for cand in ["섹터", "sector", "업종", "industry"]:
        if cand.lower() in lower_cols:
            col_map[lower_cols[cand.lower()]] = "섹터"
            break

    df = df.rename(columns=col_map)

    # 필수 컬럼 확인
    if "회사명" not in df.columns or "종목코드" not in df.columns:
        raise ValueError("CSV에 '회사명'과 '종목코드' 컬럼이 필요합니다.")

    if "섹터" not in df.columns:
        df["섹터"] = "기타"

    df["회사명"] = df["회사명"].astype(str).str.strip()
    df["종목코드"] = df["종목코드"].astype(str).str.extract(r"(\d+)")[0].fillna(df["종목코드"].astype(str))
    df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
    df["섹터"] = df["섹터"].astype(str).fillna("기타")

    df = df.dropna(subset=["회사명", "종목코드"]).drop_duplicates(subset=["종목코드"]).reset_index(drop=True)
    return df


def get_stock_db() -> pd.DataFrame:
    # 1) 세션 업로드 DB
    if "uploaded_stock_db" in st.session_state and isinstance(st.session_state.uploaded_stock_db, pd.DataFrame):
        try:
            return normalize_stock_db(st.session_state.uploaded_stock_db)
        except Exception:
            pass

    # 2) 레포 파일 DB
    repo_df = load_stock_db_from_repo("krx_stock_list.csv")
    if repo_df is not None and not repo_df.empty:
        try:
            return normalize_stock_db(repo_df)
        except Exception:
            pass

    # 3) 내장 미니 DB
    df = pd.read_csv(StringIO(EMBEDDED_MINI_CSV))
    return normalize_stock_db(df)


def search_candidates(query: str, limit: int = 20) -> pd.DataFrame:
    df = get_stock_db()
    q = (query or "").strip()
    if not q:
        return df.head(0)

    q2 = q.replace(" ", "").upper()
    name_norm = df["회사명"].astype(str).str.replace(" ", "", regex=False).str.upper()

    exact = df[name_norm == q2]
    if not exact.empty:
        return exact.head(limit)

    part = df[name_norm.str.contains(q2, na=False)]
    return part.head(limit)


# =============================
# (완전 안정형) 시세 데이터: 라이브 + 업로드(오프라인)
# =============================
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


def parse_ohlcv_csv(file) -> dict | None:
    """
    업로드 OHLCV CSV 지원
    컬럼 후보:
    - date/날짜
    - open/시가
    - close/종가
    - volume/거래량
    (필수: close, volume)
    """
    try:
        df = pd.read_csv(file)
        print(f"[INFO] Parsing OHLCV CSV: {file.name if hasattr(file, 'name') else 'unknown'}")
        print(f"[INFO] Columns found: {df.columns.tolist()}")

        # 컬럼 표준화
        cols = {c.lower(): c for c in df.columns}
        def pick(*names):
            for n in names:
                if n in cols:
                    return cols[n]
            return None

        c_date = pick("date", "날짜")
        c_open = pick("open", "시가")
        c_close = pick("close", "종가")
        c_vol = pick("volume", "거래량")

        if c_close is None or c_vol is None:
            print(f"[ERROR] Missing required columns. Need 'close' and 'volume'")
            return None

        print(f"[INFO] Mapped columns - close: {c_close}, volume: {c_vol}, open: {c_open}, date: {c_date}")

        # 날짜 정렬(있으면)
        if c_date is not None:
            df[c_date] = pd.to_datetime(df[c_date], errors="coerce")
            df = df.dropna(subset=[c_date]).sort_values(c_date)

        closes = df[c_close].astype(float).tolist()
        vols = df[c_vol].astype(float).tolist()

        if len(closes) < 35:  # MACD 계산 최소 길이
            print(f"[ERROR] Not enough data rows: {len(closes)} (need at least 35)")
            return None

        current = float(closes[-1])
        prev_close = float(closes[-2])
        volume = float(vols[-1])

        if c_open is not None:
            openp = float(df[c_open].astype(float).iloc[-1])
        else:
            openp = prev_close  # open이 없으면 대충 prev_close로

        print(f"[SUCCESS] OHLCV parsed successfully. Rows: {len(closes)}, Current: {current}")
        return {
            "current": current,
            "open": openp,
            "prev_close": prev_close,
            "volume": volume,
            "close_prices": closes,
            "volumes": vols,
        }
    except Exception as e:
        print(f"[ERROR] Failed to parse OHLCV CSV: {str(e)}")
        return None


class StockScreener:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.naver.com/",
        }

    @st.cache_data(ttl=600)
    def get_stock_data_live(_self, code: str) -> dict | None:
        """
        네이버 금융(라이브) - Streamlit Cloud에서 막힐 수 있음
        """
        all_data = []
        try:
            for page in range(1, 4):
                url = "https://finance.naver.com/item/sise_day.naver"
                r = safe_get(url, params={"code": code, "page": page}, headers=_self.headers, timeout=12, retries=1)
                df_list = pd.read_html(r.text)
                if not df_list:
                    break
                df = df_list[0].dropna()
                if df.empty:
                    break
                all_data.append(df)
                time.sleep(0.1)

            if not all_data:
                return None

            combined = pd.concat(all_data, ignore_index=True).sort_values("날짜").reset_index(drop=True)
            if len(combined) < 35:
                return None

            closes = combined["종가"].astype(float).tolist()
            vols = combined["거래량"].astype(float).tolist()

            return {
                "current": float(combined.iloc[-1]["종가"]),
                "open": float(combined.iloc[-1]["시가"]),
                "prev_close": float(combined.iloc[-2]["종가"]),
                "volume": float(combined.iloc[-1]["거래량"]),
                "close_prices": closes,
                "volumes": vols,
            }
        except Exception as e:
            print(f"[ERROR] Live data fetch failed ({code}): {str(e)}")
            return None

    def get_stock_data(self, code: str) -> dict | None:
        """
        완전 안정형:
        1) 업로드된 오프라인 데이터가 있으면 그걸 우선
        2) 없으면 라이브 시도
        """
        # 오프라인 데이터 확인 (더 명확한 로깅)
        offline_map = st.session_state.get("offline_price_data", {})
        if isinstance(offline_map, dict) and code in offline_map:
            print(f"[INFO] Using offline data: {code}")
            return offline_map[code]

        # 라이브 시도
        print(f"[INFO] Attempting live data fetch: {code}")
        live_data = self.get_stock_data_live(code)
        if live_data:
            print(f"[SUCCESS] Live data fetch successful: {code}")
        else:
            print(f"[WARNING] Live data fetch failed: {code}")
        return live_data

    def calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return None
        s = pd.Series(prices)
        d = s.diff()
        gain = (d.where(d > 0, 0)).rolling(window=period).mean()
        loss = (-d.where(d < 0, 0)).rolling(window=period).mean()
        loss_val = loss.iloc[-1]
        if loss_val == 0:
            return 100.0
        rs = gain.iloc[-1] / loss_val
        return float(100 - (100 / (1 + rs)))

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        if len(prices) < slow + signal:
            return None, None, None
        s = pd.Series(prices)
        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist.iloc[-1])

    def check_macd_crossover(self, prices):
        if len(prices) < 35:
            return None
        s = pd.Series(prices)
        ema_fast = s.ewm(span=12, adjust=False).mean()
        ema_slow = s.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_current = macd_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        sig_current = signal_line.iloc[-1]
        sig_prev = signal_line.iloc[-2]

        if macd_prev <= sig_prev and macd_current > sig_current:
            return "골든크로스"
        if macd_prev >= sig_prev and macd_current < sig_current:
            return "데드크로스"
        return None

    def analyze_stock(self, code, name, sector, data):
        try:
            prices = data["close_prices"]

            rsi = self.calculate_rsi(prices)
            if rsi is None:
                return None

            macd, sig, hist = self.calculate_macd(prices)
            if macd is None:
                return None

            cross = self.check_macd_crossover(prices)
            gap = ((data["open"] - data["prev_close"]) / data["prev_close"]) * 100

            volume_surge = False
            if len(data["volumes"]) >= 5:
                avg_vol = sum(data["volumes"][-5:]) / 5
                if data["volume"] >= avg_vol * 2.0:
                    volume_surge = True

            signals = []
            recommendation = "관망"
            rec_color = "🟡"

            if rsi <= 30 and cross == "골든크로스":
                signals.append("⭐ 강력 매수 신호 (RSI 과매도 + 골든크로스)")
                recommendation = "적극 매수"
                rec_color = "🟢"
            elif rsi <= 30:
                signals.append("RSI 과매도 (반등 가능성)")
                recommendation = "매수 고려"
                rec_color = "🟢"
            elif cross == "골든크로스":
                signals.append("MACD 골든크로스 (상승 전환)")
                recommendation = "매수 고려"
                rec_color = "🟢"
            elif macd > 0 and rsi < 70:
                signals.append("상승 추세 지속 (MACD > 0)")
                recommendation = "보유/추가 매수"
                rec_color = "🟢"

            if rsi >= 70:
                signals.append("RSI 과매수 (조정 가능성)")
                recommendation = "매도 고려"
                rec_color = "🔴"
            if cross == "데드크로스":
                signals.append("MACD 데드크로스 (하락 전환)")
                recommendation = "매도 고려"
                rec_color = "🔴"

            if gap < -3:
                signals.append(f"갭 하락 {gap:.1f}%")
            if volume_surge:
                signals.append("거래량 급증 (최근 5일 평균 대비 2배↑)")
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
                "signal": sig,
                "macd_cross": cross,
                "gap": gap,
                "volume": data["volume"],
                "signals": signals,
                "recommendation": recommendation,
                "recommendation_color": rec_color,
            }
        except Exception:
            return None

    def check_conditions(self, code, name, sector, data, selected_filters, params):
        try:
            prices = data["close_prices"]

            rsi = self.calculate_rsi(prices)
            if rsi is None:
                return None

            macd, sig, hist = self.calculate_macd(prices)
            if macd is None:
                return None

            cross = self.check_macd_crossover(prices)
            signals = []

            if "RSI 과매도 (30 이하)" in selected_filters:
                if rsi > 30:
                    return None
                signals.append("RSI 과매도")

            if "RSI 과매수 (70 이상)" in selected_filters:
                if rsi < 70:
                    return None
                signals.append("RSI 과매수")

            if "MACD 골든크로스" in selected_filters:
                if cross != "골든크로스":
                    return None
                signals.append("MACD 골든크로스")

            if "MACD 데드크로스" in selected_filters:
                if cross != "데드크로스":
                    return None
                signals.append("MACD 데드크로스")

            if "MACD 0선 돌파" in selected_filters:
                if macd <= 0:
                    return None
                signals.append("MACD 0선 돌파")

            if "RSI 과매도 + MACD 골든크로스 (강력 매수)" in selected_filters:
                if not (rsi <= 30 and cross == "골든크로스"):
                    return None
                signals.append("⭐ 강력 매수 신호")

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
                "Signal": f"{sig:.2f}",
                "매매신호": " | ".join(signals) if signals else "-",
                "거래량": int(data["volume"]),
            }
        except Exception:
            return None


# =============================
# UI 메인
# =============================
st.set_page_config(page_title="Stock Screener Pro (Cloud Stable)", layout="wide")
st.title("🚀 Stock Screener Pro (Streamlit Cloud 안정형)")

if "custom_stocks" not in st.session_state:
    st.session_state.custom_stocks = []

if "offline_price_data" not in st.session_state:
    st.session_state.offline_price_data = {}  # {code: data_dict}


if check_password():
    screener = StockScreener()

    with st.sidebar:
        st.success("✅ 로그인 성공!")
        if st.button("로그아웃", key="logout_btn"):
            st.session_state["password_correct"] = False
            st.rerun()

        st.header("⚙️ 필터 설정")
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
        st.subheader("📌 종목 DB 세팅(중요)")
        st.caption("Streamlit Cloud에서는 외부 크롤링이 막힐 수 있어 종목 DB를 로컬 CSV로 쓰는 게 가장 안정적입니다.")

        stock_db_file = st.file_uploader(
            "📎 종목 리스트 CSV 업로드 (회사명, 종목코드, 섹터)",
            type=["csv"],
            key="stock_db_uploader",
        )
        if stock_db_file is not None:
            try:
                df_up = pd.read_csv(stock_db_file)
                st.session_state.uploaded_stock_db = df_up
                st.success("✅ 종목 DB 업로드 완료! (이 세션에서 즉시 검색에 반영됩니다)")
            except Exception as e:
                st.error("❌ 종목 DB CSV 파싱 실패")
                st.write(e)

        st.caption("레포에 `krx_stock_list.csv` 파일을 넣어두면 업로드 없이도 항상 동작합니다.")
        st.divider()

        st.subheader("📌 시세 데이터(오프라인) 업로드")
        st.caption("라이브가 막히면, 종목별 OHLCV CSV 업로드로 분석/스크리닝이 가능합니다.")
        st.caption("필수 컬럼: close(또는 종가), volume(또는 거래량). date/날짜 있으면 정렬에 사용.")

    tab1, tab2, tab3 = st.tabs(["✏️ 내 종목 추가", "⭐ 관심종목 스크리닝", "🔍 개별 종목 분석"])

    # =========================================================
    # Tab1: 내 종목 추가
    # =========================================================
    with tab1:
        st.info("기업명을 검색해 관심종목에 추가합니다. (종목 DB는 로컬 CSV 기반으로 안정 동작)")

        query = st.text_input("🔍 기업명 입력", placeholder="예: 휴림로봇, 삼성전자", key="add_query")

        if query:
            cands = search_candidates(query, limit=20)

            if cands.empty:
                st.error("검색 결과가 없습니다.")
                st.caption("✅ 해결: 사이드바에서 종목 리스트 CSV 업로드 또는 레포에 krx_stock_list.csv 추가")
            else:
                options = [f"{row['회사명']} ({row['종목코드']}) · {row.get('섹터','기타')}" for _, row in cands.iterrows()]
                pick = st.selectbox("✅ 후보 선택", options, key="add_pick")
                idx = options.index(pick)

                code = str(cands.iloc[idx]["종목코드"]).zfill(6)
                name = str(cands.iloc[idx]["회사명"])
                sector = str(cands.iloc[idx].get("섹터", "기타"))

                st.success(f"선택됨: **{name}** ({code})")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("➕ 관심종목에 추가", use_container_width=True, key="add_btn"):
                        if not any(s[0] == code for s in st.session_state.custom_stocks):
                            st.session_state.custom_stocks.append((code, name, sector))
                            st.success("✅ 추가 완료!")
                            st.rerun()
                        else:
                            st.warning("⚠️ 이미 추가된 종목입니다.")

                with col2:
                    if st.button("📌 지금 바로 미리 분석", use_container_width=True, key="preview_btn"):
                        with st.spinner(f"{name} 데이터 수집 및 분석 중..."):
                            data = screener.get_stock_data(code)

                        if not data:
                            st.warning("⚠️ 라이브 시세를 못 가져왔습니다(Cloud 차단 가능).")
                            st.info("✅ 아래에서 OHLCV CSV를 업로드하면 분석이 가능합니다.")
                            up = st.file_uploader("📎 이 종목 OHLCV CSV 업로드", type=["csv"], key=f"up_{code}")
                            if up is not None:
                                parsed = parse_ohlcv_csv(up)
                                if parsed:
                                    st.session_state.offline_price_data[code] = parsed
                                    st.success("✅ 오프라인 시세 등록 완료! 다시 '미리 분석'을 눌러주세요.")
                                else:
                                    st.error("❌ OHLCV CSV 형식이 올바르지 않습니다. (close/volume 필수)")
                        else:
                            analysis = screener.analyze_stock(code, name, sector, data)
                            if not analysis:
                                st.error("분석 실패(데이터 부족/계산 오류)")
                            else:
                                st.divider()
                                st.subheader(f"📈 {name} ({code}) 미리 분석")

                                m1, m2, m3, m4 = st.columns(4)
                                with m1:
                                    st.metric("현재가", f"{int(analysis['current']):,}원")
                                with m2:
                                    change_color = "normal" if analysis["change"] >= 0 else "inverse"
                                    st.metric("등락율", f"{analysis['change']:.2f}%", delta=f"{analysis['change']:.2f}%", delta_color=change_color)
                                with m3:
                                    st.metric("RSI", f"{analysis['rsi']:.1f}")
                                with m4:
                                    st.metric("거래량", f"{int(analysis['volume']):,}")

                                st.subheader("💡 매매 추천")
                                r1, r2 = st.columns([1, 3])
                                with r1:
                                    st.markdown(f"## {analysis['recommendation_color']}")
                                with r2:
                                    st.markdown(f"### **{analysis['recommendation']}**")

                                if analysis.get("signals"):
                                    st.subheader("🎯 감지된 신호")
                                    for s in analysis["signals"]:
                                        st.markdown(f"- {s}")

        st.divider()
        st.subheader("📌 현재 종목 DB 상태")
        db = get_stock_db()
        st.caption(f"현재 로드된 종목 수: {len(db):,}개")
        st.dataframe(db.head(30), use_container_width=True)

    # =========================================================
    # Tab2: 관심종목 스크리닝
    # =========================================================
    with tab2:
        st.info("관심종목 전체를 필터 조건으로 스크리닝합니다. (라이브가 막히면 개별 OHLCV 업로드 필요)")

        if not st.session_state.custom_stocks:
            st.warning("관심종목이 없습니다. '내 종목 추가'에서 먼저 추가하세요.")
        else:
            st.subheader(f"⭐ 내 관심종목 ({len(st.session_state.custom_stocks)}개)")

            if st.button("🗑️ 전체 삭제", key="delete_all"):
                st.session_state.custom_stocks = []
                st.success("모든 종목이 삭제되었습니다.")
                st.rerun()

            for idx, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                a, b = st.columns([6, 1])
                with a:
                    st.text(f"{idx+1}. {name} ({code}) [{sector}]")
                with b:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.custom_stocks.pop(idx)
                        st.rerun()

            st.divider()

            st.subheader("📎 (옵션) 관심종목 OHLCV 업로드")
            st.caption("라이브 차단 시, 여기서 업로드해두면 '일괄 스크리닝'이 안정적으로 가능합니다.")
            up_bulk = st.file_uploader("OHLCV CSV 여러 개 업로드(각 파일은 1종목)", type=["csv"], accept_multiple_files=True, key="bulk_ohlcv")
            if up_bulk:
                loaded = 0
                for f in up_bulk:
                    parsed = parse_ohlcv_csv(f)
                    if parsed:
                        # 파일명에 코드가 포함되면 그걸 우선으로
                        # 예: 005930.csv / samsung_005930.csv 등
                        fname = f.name
                        found = None
                        for (code, _, _) in st.session_state.custom_stocks:
                            if code in fname:
                                found = code
                                break
                        if found:
                            st.session_state.offline_price_data[found] = parsed
                            loaded += 1
                st.success(f"✅ 오프라인 시세 등록 완료: {loaded}개 (파일명에 종목코드가 포함된 경우 자동 매칭)")

            st.divider()

            if st.button("🔍 관심종목 일괄 스크리닝", type="primary", key="bulk_screen"):
                results = []
                progress = st.progress(0)
                status = st.empty()

                total = len(st.session_state.custom_stocks)
                for i, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                    status.text(f"분석 중: {name} ({i+1}/{total})")
                    data = screener.get_stock_data(code)

                    if data:
                        res = screener.check_conditions(code, name, sector, data, selected_filters, params)
                        if res:
                            results.append(res)
                    else:
                        st.warning(f"⚠️ {name} ({code}) 데이터 없음 (라이브 차단 또는 업로드 필요)")

                    progress.progress((i + 1) / total)
                    time.sleep(0.1)

                status.empty()
                progress.empty()

                if results:
                    st.success(f"✅ 조건에 맞는 종목 **{len(results)}개**를 찾았습니다!")
                    st.dataframe(pd.DataFrame(results), use_container_width=True)
                else:
                    st.warning("⚠️ 조건에 부합하는 종목이 없습니다. (또는 시세 데이터가 없는 종목이 많음)")

    # =========================================================
    # Tab3: 개별 종목 분석
    # =========================================================
    with tab3:
        st.info("종목을 검색/선택 후 상세 분석 리포트를 봅니다. (라이브 막히면 OHLCV 업로드로 100% 가능)")

        query = st.text_input("🔍 분석할 기업명 입력", placeholder="예: 삼성전자, 휴림로봇", key="single_query")

        if query:
            cands = search_candidates(query, limit=20)

            if cands.empty:
                st.error("검색 결과가 없습니다.")
                st.caption("✅ 해결: 사이드바에서 종목 리스트 CSV 업로드 또는 레포에 krx_stock_list.csv 추가")
            else:
                opts = [f"{row['회사명']} ({row['종목코드']}) · {row.get('섹터','기타')}" for _, row in cands.iterrows()]
                pick = st.selectbox("✅ 후보 선택", opts, key="single_pick")
                idx = opts.index(pick)

                code = str(cands.iloc[idx]["종목코드"]).zfill(6)
                name = str(cands.iloc[idx]["회사명"])
                sector = str(cands.iloc[idx].get("섹터", "기타"))

                st.success(f"선택됨: **{name}** ({code})")

                st.subheader("📎 (필요 시) 이 종목 OHLCV 업로드")
                up_one = st.file_uploader("OHLCV CSV 업로드", type=["csv"], key=f"one_{code}")
                if up_one is not None:
                    parsed = parse_ohlcv_csv(up_one)
                    if parsed:
                        st.session_state.offline_price_data[code] = parsed
                        st.success("✅ 오프라인 시세 등록 완료! (이제 분석 가능)")
                    else:
                        st.error("❌ OHLCV CSV 형식이 올바르지 않습니다. (close/volume 필수)")

                if st.button("📊 상세 분석 시작", type="primary", key="start_analysis"):
                    with st.spinner(f"{name} 데이터 수집 및 분석 중..."):
                        data = screener.get_stock_data(code)

                    if not data:
                        st.error("⚠️ 시세 데이터를 가져올 수 없습니다.")
                        st.caption("Streamlit Cloud에서 네이버/거래소가 차단될 수 있습니다. 위에서 OHLCV CSV 업로드 후 다시 시도하세요.")
                    else:
                        analysis = screener.analyze_stock(code, name, sector, data)

                        if not analysis:
                            st.error("⚠️ 분석 실패(데이터 부족/계산 오류)")
                        else:
                            st.divider()
                            st.header(f"📈 {name} ({code}) 상세 분석 리포트")
                            st.caption(f"섹터: {sector}")

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
                            st.subheader("💡 매매 추천")
                            r1, r2 = st.columns([1, 3])
                            with r1:
                                st.markdown(f"# {analysis['recommendation_color']}")
                            with r2:
                                st.markdown(f"## **{analysis['recommendation']}**")

                            st.divider()
                            st.subheader("📊 기술적 지표")

                            i1, i2 = st.columns(2)
                            with i1:
                                st.markdown("### RSI")
                                st.progress(int(min(max(analysis["rsi"], 0), 100)))
                                if analysis["rsi"] <= 30:
                                    st.success(f"🟢 RSI {analysis['rsi']:.1f} - 과매도")
                                elif analysis["rsi"] >= 70:
                                    st.error(f"🔴 RSI {analysis['rsi']:.1f} - 과매수")
                                else:
                                    st.info(f"🟡 RSI {analysis['rsi']:.1f} - 중립")

                            with i2:
                                st.markdown("### MACD")
                                st.write(f"**MACD Line**: {analysis['macd']:.2f}")
                                st.write(f"**Signal Line**: {analysis['signal']:.2f}")

                                if analysis["macd_cross"] == "골든크로스":
                                    st.success("🟢 골든크로스")
                                elif analysis["macd_cross"] == "데드크로스":
                                    st.error("🔴 데드크로스")
                                elif analysis["macd"] > 0:
                                    st.success("🟢 상승 추세(MACD>0)")
                                else:
                                    st.warning("🟡 하락 추세(MACD<0)")

                            if analysis.get("signals"):
                                st.divider()
                                st.subheader("🎯 감지된 신호")
                                for s in analysis["signals"]:
                                    st.markdown(f"- {s}")

else:
    st.info("🔒 왼쪽 사이드바에서 비밀번호로 로그인해 주세요.")
