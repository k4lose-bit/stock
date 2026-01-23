import streamlit as st
import pandas as pd
import requests
import hashlib
import time

# --- 보안 및 설정 ---
# 실제 운영 시 환경변수나 보안된 저장소에 해시값을 저장하는 것이 권장됩니다. [5]
CORRECT_PASSWORD_HASH = "81216e5077271e1645e759247f485078508e75877f68508a8e75877f68508a8e"

def check_password():
    if "password_correct" not in st.session_state:
        st.sidebar.text_input("접속 비밀번호", type="password", key="pw_input")
        if st.sidebar.button("로그인"):
            # 입력된 비밀번호의 SHA-256 해시를 생성하여 비교 [5]
            st.session_state["password_correct"] = hashlib.sha256(st.session_state.pw_input.encode()).hexdigest() == CORRECT_PASSWORD_HASH
            st.rerun()
        return False
    return st.session_state["password_correct"]

# --- 스크리닝 엔진 클래스 ---
class StockScreener:
    def __init__(self):
        # 봇 차단 방지를 위한 User-Agent 설정 [7]
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    @st.cache_data(ttl=600) # 10분간 데이터 캐싱하여 속도 개선 [1]
    def get_stock_data(_self, code):
        """네이버 금융에서 주가 및 히스토리 데이터 수집 [8, 9]"""
        try:
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
            res = requests.get(url, headers=_self.headers)
            df = pd.read_html(res.text).dropna() # 첫 번째 테이블 선택 및 결측치 제거
            
            if df.empty: return None
            
            return {
                'current': df.iloc['종가'],
                'open': df.iloc['시가'],
                'prev_close': df.iloc[1]['종가'],
                'volume': df.iloc['거래량'],
                'history': df['종가'].tolist()[::-1] # 시간순 정렬
            }
        except Exception:
            return None

    def calculate_rsi(self, prices, period=14):
        """Pandas를 이용한 RSI 계산 (TA-Lib 미설치 대응)"""
        if len(prices) < period + 1: return 50
        series = pd.Series(prices)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        return rsi

    def check_conditions(self, code, name, data, selected_filters, params):
        """사용자가 선택한 필터 조건만 검사 [10, 4]"""
        try:
            # 1. 갭 하락 조건
            if "Gap Down" in selected_filters:
                gap = ((data['open'] - data['prev_close']) / data['prev_close']) * 100
                if gap > -params['gap_threshold']: return None
            
            # 2. 거래량 급증 조건
            if "Volume Surge" in selected_filters:
                avg_vol = sum(data['history'][-5:]) / 5 # 5일 평균 거래량
                if data['volume'] < avg_vol * params['vol_ratio']: return None
                
            # 3. RSI 과매도 조건
            if "RSI Overbought/Oversold" in selected_filters:
                rsi = self.calculate_rsi(data['history'])
                if not (params['rsi_min'] <= rsi <= params['rsi_max']): return None

            return {
                '종목코드': code,
                '종목명': name,
                '현재가': format(int(data['current']), ','),
                '등락율': f"{round(((data['current'] - data['prev_close']) / data['prev_close']) * 100, 2)}%",
                '거래량': format(int(data['volume']), ',')
            }
        except Exception:
            return None

# --- UI 메인 로직 ---
st.set_page_config(page_title="주식 스크리너 Pro", layout="wide")
st.title("🚀 고도화된 동적 주식 스크리너")

if check_password():
    screener = StockScreener()
    
    with st.sidebar:
        st.header("⚙️ 필터 및 조건")
        # 동적 필터 선택 (SyntaxError 수정됨) [6]
        available_filters =
        selected_filters = st.multiselect(
            "적용할 스크리닝 조건을 선택하세요",
            options=available_filters,
            default=
        )
        
        params = {}
        if "Gap Down" in selected_filters:
            params['gap_threshold'] = st.slider("갭 하락 기준 (%)", 1.0, 15.0, 5.0, help="시가가 전일 종가 대비 얼마나 하락했는지 설정합니다.")
        if "Volume Surge" in selected_filters:
            params['vol_ratio'] = st.number_input("거래량 배수 (5일 평균 대비)", 1.0, 10.0, 2.0)
        if "RSI Overbought/Oversold" in selected_filters:
            params['rsi_min'], params['rsi_max'] = st.slider("RSI 탐색 범위", 0, 100, (0, 30))

    if st.button("🔍 스크리닝 시작"):
        # 샘플 종목 (실제 운영 시 상장사 전체 리스트 연동 가능) [11]
        stocks =
        
        results =
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (code, name) in enumerate(stocks):
            status_text.text(f"분석 중: {name} ({code})...")
            data = screener.get_stock_data(code)
            if data:
                res = screener.check_conditions(code, name, data, selected_filters, params)
                if res: results.append(res)
            
            progress_bar.progress((i + 1) / len(stocks))
            time.sleep(0.2) # IP 차단 방지를 위한 지연 [12]

        status_text.empty()
        if results:
            st.success(f"총 {len(results)}개의 종목을 찾았습니다.")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("선택한 조건에 부합하는 종목이 없습니다.")

## 깃허브 기반 배포 프로세스 및 CI/CD 고도화

수정된 스크리너를 깃허브를 통해 지속적으로 업데이트하고 배포하는 과정은 안정적인 서비스 운영을 위한 핵심 단계이다.[13] 스트림릿 커뮤니티 클라우드는 깃허브 리포지토리와 연동되어 푸시(Push) 이벤트 발생 시 자동으로 앱을 재배포하는 기능을 제공한다.[14]

### 지속적 배포 및 의존성 관리 전략

새로운 스크리닝 필터나 라이브러리를 추가했다면, 반드시 `requirements.txt`에 해당 패키지와 버전을 명시해야 한다.[13] 스트림릿 클라우드는 배포 시 이 파일을 참조하여 가상 환경을 구축하기 때문이다.[4]

## 스크리너 고도화를 위한 전략적 제언 및 결론

본 연구를 통해 분석한 결과, 깃허브에 배포된 기존 스트림릿 스크리너를 수정하여 다중 조건을 선택 가능하게 만드는 것은 투자 전략의 질적 향상을 의미한다. 동적 필터 시스템을 구축함으로써 사용자는 시장 상황에 맞춰 즉각적으로 검색 식을 변경할 수 있으며, 이는 급변하는 금융 환경에서 중요한 경쟁 우위가 된다.[15, 16]

결론적으로, 깃허브와 스트림릿 클라우드를 활용한 현대적인 배포 파이프라인은 이러한 고도화된 기능을 신속하게 전달할 수 있는 최적의 도구이다. 개발자는 지속적인 코드 리팩토링과 성능 튜닝을 통해 시스템의 견고함을 유지해야 하며, 합리적인 의사결정을 돕는 필수적인 조력자가 되어야 한다.[17]
