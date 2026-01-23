import streamlit as st
import pandas as pd
import requests
import hashlib
import time

# --- 보안 및 설정 ---
# 비밀번호 'st0727@6816'의 SHA-256 해시
CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        pw_input = st.sidebar.text_input("접속 비밀번호", type="password", key="pw_input")
        if st.sidebar.button("로그인"):
            if pw_input:
                entered_hash = hashlib.sha256(pw_input.encode('utf-8')).hexdigest()
                if entered_hash == CORRECT_PASSWORD_HASH:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.sidebar.error("❌ 비밀번호가 틀렸습니다.")
        return False
    return True

# --- 스크리닝 엔진 클래스 ---
class StockScreener:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    @st.cache_data(ttl=600)
    def get_stock_data(_self, code):
        """네이버 금융 일별 시세 수집"""
        try:
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
            res = requests.get(url, headers=_self.headers, timeout=10)
            df_list = pd.read_html(res.text)
            
            if not df_list:
                return None
            
            df = df_list[0]
            df = df.dropna()
            
            if df.empty:
                return None
            
            return {
                'current': float(df.iloc[0]['종가']),
                'open': float(df.iloc[0]['시가']),
                'prev_close': float(df.iloc[1]['종가']) if len(df) > 1 else float(df.iloc[0]['종가']),
                'volume': float(df.iloc[0]['거래량']),
                'history': df['종가'].tolist()[::-1]
            }
        except Exception as e:
            return None

    def calculate_rsi(self, prices, period=14):
        """RSI 지표 계산"""
        if len(prices) < period + 1:
            return 50
        
        series = pd.Series(prices)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        if loss.iloc[-1] == 0:
            return 100
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        return rsi

    def check_conditions(self, code, name, data, selected_filters, params):
        """다중 조건 AND 로직 필터링"""
        try:
            if "Gap Down" in selected_filters:
                gap = ((data['open'] - data['prev_close']) / data['prev_close']) * 100
                if gap > -params['gap_threshold']:
                    return None
            
            if "Volume Surge" in selected_filters:
                if len(data['history']) >= 5:
                    avg_vol = sum(data['history'][-5:]) / 5
                    if data['volume'] < avg_vol * params['vol_ratio']:
                        return None
                
            if "RSI Condition" in selected_filters:
                rsi = self.calculate_rsi(data['history'])
                if not (params['rsi_min'] <= rsi <= params['rsi_max']):
                    return None

            return {
                '종목코드': code,
                '종목명': name,
                '현재가': int(data['current']),
                '등락율': f"{round(((data['current'] - data['prev_close']) / data['prev_close']) * 100, 2)}%",
                '거래량': int(data['volume'])
            }
        except Exception as e:
            return None

# --- UI 메인 로직 ---
st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.title("🚀 고도화된 동적 주식 스크리너")

if check_password():
    screener = StockScreener()
    
    with st.sidebar:
        st.success("✅ 로그인 성공!")
        if st.button("로그아웃"):
            st.session_state["password_correct"] = False
            st.rerun()
        
        st.header("⚙️ 필터 설정")
        
        # 사용 가능한 필터 리스트
        available_filters = ["Gap Down", "Volume Surge", "RSI Condition"]
        selected_filters = st.multiselect(
            "적용할 스크리닝 조건을 선택하세요",
            options=available_filters,
            default=["Gap Down"]
        )
        
        params = {}
        if "Gap Down" in selected_filters:
            params['gap_threshold'] = st.slider("갭 하락 기준 (%)", 1.0, 15.0, 5.0)
        if "Volume Surge" in selected_filters:
            params['vol_ratio'] = st.number_input("거래량 배수 (평균 대비)", 1.0, 10.0, 2.0)
        if "RSI Condition" in selected_filters:
            params['rsi_min'], params['rsi_max'] = st.slider("RSI 탐색 범위", 0, 100, (0, 30))

    if st.button("🔍 스크리닝 시작"):
        # 분석 대상 종목 리스트 (예시: 주요 종목)
        stocks = [
            ("005930", "삼성전자"),
            ("000660", "SK하이닉스"),
            ("035720", "카카오"),
            ("035420", "NAVER"),
            ("051910", "LG화학"),
            ("006400", "삼성SDI"),
            ("207940", "삼성바이오로직스"),
            ("005380", "현대차"),
            ("000270", "기아"),
            ("068270", "셀트리온")
        ]
        
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (code, name) in enumerate(stocks):
            status_text.text(f"분석 중: {name} ({i+1}/{len(stocks)})")
            data = screener.get_stock_data(code)
            if data:
                res = screener.check_conditions(code, name, data, selected_filters, params)
                if res:
                    results.append(res)
            progress_bar.progress((i + 1) / len(stocks))
            time.sleep(0.3)  # IP 차단 방지

        status_text.empty()
        
        if results:
            st.success(f"조건에 맞는 종목 {len(results)}개를 찾았습니다.")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("조건에 부합하는 종목이 현재 없습니다.")
else:
    st.info("👈 사이드바에서 비밀번호를 입력하세요")
