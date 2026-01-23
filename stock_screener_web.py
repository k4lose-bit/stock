import streamlit as st
import pandas as pd
import requests
import hashlib
import time

# --- 보안 및 설정 ---
CORRECT_PASSWORD_HASH = "81216e5077271e1645e759247f485078508e75877f68508a8e75877f68508a8e"

def check_password():
    if "password_correct" not in st.session_state:
        st.sidebar.text_input("비밀번호", type="password", key="pw_input")
        if st.sidebar.button("로그인"):
            st.session_state["password_correct"] = hashlib.sha256(st.session_state.pw_input.encode()).hexdigest() == CORRECT_PASSWORD_HASH
            st.rerun()
        return False
    return st.session_state["password_correct"]

# --- 스크리닝 엔진 클래스 ---
class StockScreener:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def get_stock_data(self, code):
        """네이버 금융 데이터 수집 [20, 25]"""
        try:
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
            res = requests.get(url, headers=self.headers)
            df_list = pd.read_html(res.text)
            df = df_list.dropna()
            
            if df.empty: return None
            
            return {
                'current': df.iloc['종가'],
                'open': df.iloc['시가'],
                'prev_close': df.iloc[1]['종가'],
                'volume': df.iloc['거래량'],
                'history': df['종가'].tolist()[::-1]
            }
        except:
            return None

    def calculate_rsi(self, prices, period=14):
        """RSI 계산 """
        if len(prices) < period + 1: return 50
        delta = pd.Series(prices).diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs.iloc[-1]))

    def check_conditions(self, code, name, data, selected_filters, params):
        """필터 조건 판별 로직 """
        try:
            if "Gap Down" in selected_filters:
                gap = ((data['open'] - data['prev_close']) / data['prev_close']) * 100
                if gap > -params['gap_threshold']: return None
            
            if "Volume Surge" in selected_filters:
                avg_vol = sum(data['history'][-5:]) / 5
                if data['volume'] < avg_vol * params['vol_ratio']: return None
                
            if "RSI Condition" in selected_filters:
                rsi = self.calculate_rsi(data['history'])
                if not (params['rsi_min'] <= rsi <= params['rsi_max']): return None

            return {
                '종목코드': code,
                '종목명': name,
                '현재가': data['current'],
                '등락율': round(((data['current'] - data['prev_close']) / data['prev_close']) * 100, 2),
                '거래량': int(data['volume'])
            }
        except:
            return None

# --- UI 메인 로직 ---
st.set_page_config(page_title="주식 스크리너 Pro", layout="wide")
st.title("🚀 고도화된 동적 주식 스크리너")

if check_password():
    screener = StockScreener()
    
    with st.sidebar:
        st.header("⚙️ 필터 설정")
        # 구문 오류 수정된 multiselect 
        selected_filters = st.multiselect(
            "적용할 스크리닝 조건을 선택하세요",
           ,
            default=
        )
        
        params = {}
        if "Gap Down" in selected_filters:
            params['gap_threshold'] = st.slider("갭 하락 기준 (%)", 1.0, 15.0, 5.0)
        if "Volume Surge" in selected_filters:
            params['vol_ratio'] = st.number_input("거래량 배수 (5일 평균 대비)", 1.0, 10.0, 1.5)
        if "RSI Condition" in selected_filters:
            params['rsi_min'], params['rsi_max'] = st.slider("RSI 범위", 0, 100, (0, 30))

    if st.button("🔍 스크리닝 시작"):
        # 샘플 종목 리스트 (실제 운영 시 확장 가능)
        stocks =
        results =
        progress_bar = st.progress(0)
        
        for i, (code, name) in enumerate(stocks):
            data = screener.get_stock_data(code)
            if data:
                res = screener.check_conditions(code, name, data, selected_filters, params)
                if res: results.append(res)
            progress_bar.progress((i + 1) / len(stocks))
            time.sleep(0.1) # IP 차단 방지 [26]

        if results:
            st.success(f"{len(results)}개의 종목이 발견되었습니다.")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("조건에 맞는 종목이 없습니다.")
