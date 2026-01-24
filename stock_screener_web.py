import streamlit as st
import pandas as pd
import requests
import hashlib
import time
import re

# =========================================================
# ✅ 완전 안정형: 종목검색 "다중 소스" + 네이버 시세 수집 안정화
# - 1순위: KRX(KIND) 다운로드
# - 2순위: GitHub Raw(대체 CSV/TSV) 3개 후보를 순서대로 시도
# - 3순위: 네이버 금융 검색(HTML 테이블)
# - 4순위: 내장 최소 DB fallback
#
# 검색 결과가 여러 개면 드롭다운 선택
# =========================================================


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
# Fallback 내장 DB (최소)
# =============================
STOCK_DATABASE = {
    "삼성전자": ("005930", "기타"),
    "SK하이닉스": ("000660", "기타"),
    "네이버": ("035420", "기타"),
    "NAVER": ("035420", "기타"),
    "카카오": ("035720", "기타"),
    "셀트리온": ("068270", "기타"),
    "삼성바이오로직스": ("207940", "기타"),
    "현대차": ("005380", "기타"),
    "기아": ("000270", "기타"),
}


def _norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "", s)
    return s


def _safe_get(url, params=None, headers=None, timeout=10, retries=2, sleep=0.3):
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


# =============================
# 종목 리스트 로딩 (완전 안정형)
# =============================

@st.cache_data(ttl=60 * 60 * 24)
def load_symbol_master():
    """
    회사명-종목코드 마스터를 가능한 많은 소스에서 확보.
    반환: DataFrame(columns=['name','code','market'])  (market은 없으면 'KR')
    """
    # 공통 헤더
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # 1) KRX(KIND) 다운로드 (가장 정확)
    try:
        kind_url = "https://kind.krx.co.kr/corpgeneral/corpList.do"
        # method=download + searchType=13
        r = _safe_get(kind_url, params={"method": "download", "searchType": "13"}, headers=headers, timeout=15, retries=2)
        # pd.read_html은 content를 직접 넣는게 더 안정적
        df = pd.read_html(r.text, header=0)[0]
        if df is not None and not df.empty and "회사명" in df.columns and "종목코드" in df.columns:
            df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
            df["회사명"] = df["회사명"].astype(str).str.strip()
            out = pd.DataFrame({
                "name": df["회사명"],
                "code": df["종목코드"],
                "market": "KRX"
            })
            out = out.dropna().drop_duplicates(subset=["code"]).reset_index(drop=True)
            if len(out) >= 2000:
                return out
    except Exception:
        pass

    # 2) GitHub raw 대체 소스들 (환경/방화벽에서 KIND가 막히는 경우 대비)
    #    ※ 여러 레포/포맷이 존재하고 언제든 바뀔 수 있어 "여러 후보"를 순차 시도합니다.
    github_candidates = [
        # (a) DataHub - krx listed companies (가끔 CORS/차단 될 수 있어 후보로)
        "https://raw.githubusercontent.com/datasets/krx-listed-companies/master/data/data.csv",

        # (b) FinanceDataReader 제공 심볼 (포맷이 바뀔 수 있어 후보로)
        "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/src/FinanceDataReader/resources/krx_code.csv",

        # (c) 또 다른 공개 KRX code 리스트 후보
        "https://raw.githubusercontent.com/areumjo/stock-code/master/stock_code.csv",
    ]

    for url in github_candidates:
        try:
            r = _safe_get(url, headers=headers, timeout=15, retries=2)
            text = r.text

            # CSV로 파싱 시도
            try:
                df = pd.read_csv(pd.compat.StringIO(text))
            except Exception:
                # pandas 버전에 따라 StringIO 위치가 다를 수 있어 안전처리
                from io import StringIO
                df = pd.read_csv(StringIO(text))

            if df is None or df.empty:
                continue

            # 다양한 컬럼명 대응
            # 가능한 후보: Name/Company/회사명, Symbol/Code/종목코드
            col_name = None
            col_code = None

            for c in df.columns:
                sc = str(c).strip().lower()
                if sc in ["회사명", "name", "company", "companyname", "corp_name", "corpname"]:
                    col_name = c
                if sc in ["종목코드", "symbol", "code", "ticker", "stock_code", "short_code"]:
                    col_code = c

            # FinanceDataReader krx_code.csv 같은 경우: 'code','name'
            if col_name is None:
                for c in df.columns:
                    if "name" == str(c).strip().lower():
                        col_name = c
            if col_code is None:
                for c in df.columns:
                    if "code" == str(c).strip().lower():
                        col_code = c

            if col_name is None or col_code is None:
                continue

            df[col_code] = df[col_code].astype(str).str.extract(r"(\d+)")[0].fillna(df[col_code].astype(str))
            df[col_code] = df[col_code].astype(str).str.zfill(6)
            df[col_name] = df[col_name].astype(str).str.strip()

            out = pd.DataFrame({
                "name": df[col_name],
                "code": df[col_code],
                "market": "KR"
            })
            out = out.dropna().drop_duplicates(subset=["code"]).reset_index(drop=True)

            # 너무 작으면 실패로 간주
            if len(out) >= 1000:
                return out
        except Exception:
            continue

    # 3) 마지막: 내장 DB를 DataFrame으로 반환(최소 동작 보장)
    out = pd.DataFrame([{"name": k, "code": v[0], "market": "DB"} for k, v in STOCK_DATABASE.items()])
    out = out.drop_duplicates(subset=["code"]).reset_index(drop=True)
    return out


def search_candidates(query: str, limit: int = 20):
    """
    검색어로 후보 종목 리스트 반환 (여러개면 선택)
    반환: list[dict] = {name, code, market}
    """
    q = (query or "").strip()
    if not q:
        return []

    nq = _norm(q).upper()
    master = load_symbol_master()

    if master is None or master.empty:
        # fallback: 내장 DB 부분검색
        cands = []
        for name, (code, _) in STOCK_DATABASE.items():
            if nq in _norm(name).upper():
                cands.append({"name": name, "code": code, "market": "DB"})
        return cands[:limit]

    # 정확 일치 우선
    exact = master[master["name"].apply(lambda x: _norm(str(x)).upper() == nq)]
    if not exact.empty:
        exact = exact.head(limit)
        return [{"name": str(r["name"]), "code": str(r["code"]).zfill(6), "market": str(r.get("market", "KR"))} for _, r in exact.iterrows()]

    # 부분 일치
    part = master[master["name"].apply(lambda x: nq in _norm(str(x)).upper())]
    if not part.empty:
        part = part.head(limit)
        return [{"name": str(r["name"]), "code": str(r["code"]).zfill(6), "market": str(r.get("market", "KR"))} for _, r in part.iterrows()]

    # 4) 네이버 금융 검색 (마스터에 없거나 이름이 비표준인 경우)
    #    ※ 네이버 검색도 종종 막혀서 "후순위"로만 사용
    nav = search_naver_finance_candidates(q, limit=limit)
    return nav


def search_naver_finance_candidates(query: str, limit: int = 10):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        url = "https://finance.naver.com/search/searchList.naver"
        r = _safe_get(url, params={"query": query}, headers=headers, timeout=12, retries=2)
        # 인코딩 이슈 방지
        r.encoding = "euc-kr"
        tables = pd.read_html(r.text)
        if not tables:
            return []
        df = tables[0]
        if df is None or df.empty:
            return []

        # 보통 컬럼: 종목명 / 종목코드 / 시장구분
        col_name = None
        col_code = None
        col_market = None
        for c in df.columns:
            sc = str(c)
            if "종목명" in sc:
                col_name = c
            if "종목코드" in sc:
                col_code = c
            if "시장" in sc or "구분" in sc:
                col_market = c

        if col_name is None or col_code is None:
            return []

        out = []
        for _, row in df.head(limit).iterrows():
            name = str(row[col_name]).strip()
            code = str(row[col_code]).strip().zfill(6)
            market = "NAVER"
            if col_market is not None:
                market = f"NAVER:{str(row[col_market]).strip()}"
            out.append({"name": name, "code": code, "market": market})
        return out
    except Exception:
        return []


# =============================
# 스크리닝 엔진 (네이버 일별시세)
# =============================
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
    def get_stock_data(_self, code: str):
        """
        네이버 금융 일별시세(최근 약 60일)
        실패가 잦아 아래 안정화:
        - 재시도
        - 빈 테이블/차단 감지
        """
        all_data = []
        try:
            for page in range(1, 4):
                url = f"https://finance.naver.com/item/sise_day.naver"
                r = _safe_get(url, params={"code": code, "page": page}, headers=_self.headers, timeout=12, retries=2)
                # 차단/비정상 페이지면 tables가 비거나 엉뚱해짐
                df_list = pd.read_html(r.text)
                if not df_list:
                    break
                df = df_list[0].dropna()
                if df is None or df.empty:
                    break
                all_data.append(df)
                time.sleep(0.1)

            if not all_data:
                return None

            combined = pd.concat(all_data, ignore_index=True)
            combined = combined.sort_values("날짜").reset_index(drop=True)

            if len(combined) < 2:
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
        except Exception:
            return None

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
# UI
# =============================
st.set_page_config(page_title="Stock Screener Pro (Stable)", layout="wide")
st.title("🚀 Stock Screener Pro (완전 안정형)")

if "custom_stocks" not in st.session_state:
    st.session_state.custom_stocks = []

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
        st.caption("✅ 종목 검색 소스: KRX(KIND) → GitHub Raw → 네이버 검색 → 내장DB")

    tabs = st.tabs(["✏️ 내 종목 추가", "⭐ 관심종목 스크리닝", "🔍 개별 종목 분석"])

    # =========================================================
    # Tab 0: 내 종목 추가
    # =========================================================
    with tabs[0]:
        st.info("기업명을 입력하면 상장사 전체에서 검색합니다. 후보가 여러 개면 드롭다운으로 선택하세요.")

        query = st.text_input(
            "🔍 기업명 입력",
            placeholder="예: 휴림로봇, 두산로보틱스, 에코프로비엠, 삼성전자",
            key="add_query",
        )

        candidates = []
        if query:
            with st.spinner("검색 중... (KRX/GitHub/네이버 순으로 시도)"):
                candidates = search_candidates(query, limit=20)

        if query and not candidates:
            st.error("검색 결과가 없습니다. (네트워크 차단/기업명 오타 가능)")
            st.caption("팁: 정확한 회사명을 입력하거나 띄어쓰기/기호를 빼고 다시 시도해보세요.")

        if candidates:
            options = [f"{c['name']} ({c['code']}) · {c['market']}" for c in candidates]
            picked = st.selectbox("✅ 후보 선택", options=options, key="add_pick")
            idx = options.index(picked)

            code = candidates[idx]["code"]
            name = candidates[idx]["name"]
            sector = "기타"

            st.success(f"선택: **{name}** / 코드: **{code}**")

            c1, c2 = st.columns(2)

            with c1:
                if st.button("➕ 관심종목에 추가", use_container_width=True, key="add_btn"):
                    if not any(s[0] == code for s in st.session_state.custom_stocks):
                        st.session_state.custom_stocks.append((code, name, sector))
                        st.success("✅ 관심종목에 추가했습니다.")
                        st.rerun()
                    else:
                        st.warning("⚠️ 이미 추가된 종목입니다.")

            with c2:
                if st.button("📌 지금 바로 미리 분석", use_container_width=True, key="preview_btn"):
                    with st.spinner(f"{name} 데이터 수집 및 분석 중..."):
                        data = screener.get_stock_data(code)
                        if not data:
                            st.error("⚠️ 네이버 금융에서 시세 데이터를 못 가져왔습니다. (일시차단/네트워크/구조변경 가능)")
                        else:
                            analysis = screener.analyze_stock(code, name, sector, data)
                            if not analysis:
                                st.error("⚠️ 분석 결과 생성 실패(데이터 부족/계산 오류)")
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

    # =========================================================
    # Tab 1: 관심종목 스크리닝
    # =========================================================
    with tabs[1]:
        if st.session_state.custom_stocks:
            st.subheader(f"⭐ 내 관심종목 ({len(st.session_state.custom_stocks)}개)")

            if st.button("🗑️ 전체 삭제", key="delete_all"):
                st.session_state.custom_stocks = []
                st.success("모든 종목이 삭제되었습니다.")
                st.rerun()

            for idx, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                a, b = st.columns([6, 1])
                with a:
                    st.text(f"{idx+1}. {name} ({code})")
                with b:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.custom_stocks.pop(idx)
                        st.rerun()

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
                        st.warning(f"⚠️ {name} ({code}) 데이터 수집 실패")

                    progress.progress((i + 1) / total)
                    time.sleep(0.15)

                status.empty()
                progress.empty()

                if results:
                    st.success(f"✅ 조건에 맞는 종목 **{len(results)}개**를 찾았습니다!")
                    st.dataframe(pd.DataFrame(results), use_container_width=True)
                else:
                    st.warning("⚠️ 조건에 부합하는 종목이 없습니다.")
        else:
            st.info("👆 '내 종목 추가' 탭에서 관심종목을 먼저 추가해주세요.")

    # =========================================================
    # Tab 2: 개별 종목 분석
    # =========================================================
    with tabs[2]:
        st.info("기업명 검색 → 후보 선택 → 상세 분석")

        q = st.text_input(
            "🔍 분석할 기업명 입력",
            placeholder="예: 휴림로봇, 두산로보틱스, 삼성전자",
            key="single_query",
        )

        cands = []
        if q:
            with st.spinner("검색 중..."):
                cands = search_candidates(q, limit=20)

        if q and not cands:
            st.error("검색 결과가 없습니다.")
        elif cands:
            opts = [f"{c['name']} ({c['code']}) · {c['market']}" for c in cands]
            pick = st.selectbox("✅ 후보 선택", options=opts, key="single_pick")
            idx = opts.index(pick)

            code = cands[idx]["code"]
            name = cands[idx]["name"]
            sector = "기타"

            st.success(f"선택: **{name}** / 코드: **{code}**")

            if st.button("📊 상세 분석 시작", type="primary", key="start_analysis"):
                with st.spinner(f"{name} 데이터 수집 및 분석 중..."):
                    data = screener.get_stock_data(code)
                    if not data:
                        st.error("⚠️ 네이버 금융에서 시세 데이터를 못 가져왔습니다. (일시차단/네트워크/구조변경 가능)")
                    else:
                        analysis = screener.analyze_stock(code, name, sector, data)
                        if not analysis:
                            st.error("⚠️ 분석 결과 생성 실패")
                        else:
                            st.divider()
                            st.header(f"📈 {name} ({code}) 상세 분석 리포트")

                            c1, c2, c3, c4 = st.columns(4)
                            with c1:
                                st.metric("현재가", f"{int(analysis['current']):,}원")
                            with c2:
                                change_color = "normal" if analysis["change"] >= 0 else "inverse"
                                st.metric("등락율", f"{analysis['change']:.2f}%", delta=f"{analysis['change']:.2f}%", delta_color=change_color)
                            with c3:
                                st.metric("RSI", f"{analysis['rsi']:.1f}")
                            with c4:
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
                                st.progress(int(analysis["rsi"]))
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
