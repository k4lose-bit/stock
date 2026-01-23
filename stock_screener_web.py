import streamlit as st
import pandas as pd
import requests
import hashlib
import time
import numpy as np

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
        """네이버 금융 일별 시세 수집 (최근 60일)"""
        try:
            all_data = []
            for page in range(1, 4):  # 3페이지 = 약 60일치 데이터
                url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={page}"
                res = requests.get(url, headers=_self.headers, timeout=10)
                df_list = pd.read_html(res.text)
                
                if not df_list:
                    break
                
                df = df_list[0]
                df = df.dropna()
                
                if df.empty:
                    break
                    
                all_data.append(df)
                time.sleep(0.1)
            
            if not all_data:
                return None
            
            combined_df = pd.concat(all_data, ignore_index=True)
            combined_df = combined_df.sort_values('날짜').reset_index(drop=True)
            
            return {
                'current': float(combined_df.iloc[-1]['종가']),
                'open': float(combined_df.iloc[-1]['시가']),
                'prev_close': float(combined_df.iloc[-2]['종가']) if len(combined_df) > 1 else float(combined_df.iloc[-1]['종가']),
                'volume': float(combined_df.iloc[-1]['거래량']),
                'close_prices': combined_df['종가'].astype(float).tolist(),
                'volumes': combined_df['거래량'].astype(float).tolist()
            }
        except Exception as e:
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
        """MACD 골든크로스/데드크로스 확인"""
        if len(prices) < 35:
            return None
        
        series = pd.Series(prices)
        ema_fast = series.ewm(span=12, adjust=False).mean()
        ema_slow = series.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        
        # 현재와 이전 값 비교
        macd_current = macd_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        signal_current = signal_line.iloc[-1]
        signal_prev = signal_line.iloc[-2]
        
        # 골든크로스: MACD가 Signal을 아래에서 위로 돌파
        if macd_prev <= signal_prev and macd_current > signal_current:
            return "골든크로스"
        # 데드크로스: MACD가 Signal을 위에서 아래로 돌파
        elif macd_prev >= signal_prev and macd_current < signal_current:
            return "데드크로스"
        
        return None

    def check_conditions(self, code, name, sector, data, selected_filters, params):
        """다중 조건 AND 로직 필터링"""
        try:
            prices = data['close_prices']
            signals = []
            
            # RSI 계산
            rsi = self.calculate_rsi(prices)
            if rsi is None:
                return None
            
            # MACD 계산
            macd, signal, histogram = self.calculate_macd(prices)
            if macd is None:
                return None
            
            macd_cross = self.check_macd_crossover(prices)
            
            # 필터 조건 체크
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
                gap = ((data['open'] - data['prev_close']) / data['prev_close']) * 100
                if gap > -params.get('gap_threshold', 5.0):
                    return None
                signals.append(f"갭하락 {gap:.1f}%")
            
            if "Volume Surge" in selected_filters:
                if len(data['volumes']) >= 5:
                    avg_vol = sum(data['volumes'][-5:]) / 5
                    if data['volume'] < avg_vol * params.get('vol_ratio', 2.0):
                        return None
                    signals.append(f"거래량 급증")
            
            return {
                '섹터': sector,
                '종목코드': code,
                '종목명': name,
                '현재가': int(data['current']),
                '등락율': f"{round(((data['current'] - data['prev_close']) / data['prev_close']) * 100, 2)}%",
                'RSI': f"{rsi:.1f}",
                'MACD': f"{macd:.2f}",
                'Signal': f"{signal:.2f}",
                '매매신호': " | ".join(signals) if signals else "-",
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
        
        st.subheader("📊 기술적 지표")
        # 사용 가능한 필터 리스트
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
            params['gap_threshold'] = st.slider("갭 하락 기준 (%)", 1.0, 15.0, 5.0)
        if "Volume Surge" in selected_filters:
            params['vol_ratio'] = st.number_input("거래량 배수 (평균 대비)", 1.0, 10.0, 2.0)
        
        st.divider()
        st.info("""
        **💡 지표 설명**
        - **RSI 과매도**: 공포 매도로 반등 가능성
        - **RSI 과매수**: 과열로 조정 가능성
        - **MACD 골든크로스**: 상승 추세 전환 신호
        - **MACD 데드크로스**: 하락 추세 전환 신호
        - **강력 매수**: RSI 과매도 + 골든크로스 동시 발생
        """)

    # 탭 생성
    tab1, tab2 = st.tabs(["📋 기본 종목 리스트", "✏️ 내 종목 추가"])
    
    with tab1:
        st.info("AI, 의약품, 양자컴퓨터 관련 주요 종목을 분석합니다.")
        
        if st.button("🔍 스크리닝 시작 (기본 리스트)", type="primary", key="basic_screen"):
            # 분석 대상 종목 리스트 (AI, 의약품, 양자컴퓨터 관련주)
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
                
                # 의약품/바이오 관련주
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
                
                # 양자컴퓨터 관련주
                ("005930", "삼성전자", "양자컴퓨터"),
                ("000660", "SK하이닉스", "양자컴퓨터"),
                ("006400", "삼성SDI", "양자컴퓨터"),
                ("042700", "한미반도체", "양자컴퓨터"),
                ("095340", "ISC", "양자컴퓨터"),
                ("189300", "인텔리안테크", "양자컴퓨터"),
                ("067160", "아프리카TV", "양자컴퓨터"),
                ("053800", "안랩", "양자컴퓨터"),
                ("036930", "주성엔지니어링", "양자컴퓨터"),
                ("108320", "LX세미콘", "양자컴퓨터")
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
                time.sleep(0.5)  # IP 차단 방지

            status_text.empty()
            progress_bar.empty()
            
            if results:
                st.success(f"✅ 조건에 맞는 종목 **{len(results)}개**를 찾았습니다!")
                
                # 섹터별 통계
                df_results = pd.DataFrame(results)
                sector_counts = df_results['섹터'].value_counts()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🤖 AI 관련주", sector_counts.get("AI", 0))
                with col2:
                    st.metric("💊 의약품 관련주", sector_counts.get("의약품", 0))
                with col3:
                    st.metric("⚛️ 양자컴퓨터 관련주", sector_counts.get("양자컴퓨터", 0))
                
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
                        "거래량": st.column_config.NumberColumn("거래량", format="%d")
                    }
                )
            else:
                st.warning("⚠️ 조건에 부합하는 종목이 현재 없습니다.")
                st.info("💡 필터 조건을 조정하거나 다른 조합을 시도해보세요.")
    
    with tab2:
        st.info("관심 있는 종목을 직접 추가하여 분석할 수 있습니다.")
        
        # 종목 추가 UI
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            custom_code = st.text_input("종목코드", placeholder="예: 005930", key="custom_code")
        with col2:
            custom_name = st.text_input("종목명", placeholder="예: 삼성전자", key="custom_name")
        with col3:
            custom_sector = st.selectbox("섹터", ["AI", "의약품", "양자컴퓨터", "기타"], key="custom_sector")
        
        # 세션 상태에 커스텀 종목 리스트 저장
        if "custom_stocks" not in st.session_state:
            st.session_state.custom_stocks = []
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("➕ 종목 추가", use_container_width=True):
                if custom_code and custom_name:
                    # 6자리 숫자 확인
                    if custom_code.isdigit() and len(custom_code) == 6:
                        st.session_state.custom_stocks.append((custom_code, custom_name, custom_sector))
                        st.success(f"✅ {custom_name} ({custom_code}) 추가됨!")
                        st.rerun()
                    else:
                        st.error("❌ 종목코드는 6자리 숫자여야 합니다.")
                else:
                    st.error("❌ 종목코드와 종목명을 모두 입력하세요.")
        
        with col_btn2:
            if st.button("🗑️ 전체 삭제", use_container_width=True):
                st.session_state.custom_stocks = []
                st.success("모든 종목이 삭제되었습니다.")
                st.rerun()
        
        # 현재 추가된 종목 표시
        if st.session_state.custom_stocks:
            st.divider()
            st.subheader(f"📝 추가된 종목 ({len(st.session_state.custom_stocks)}개)")
            
            # 삭제 기능이 있는 테이블
            for idx, (code, name, sector) in enumerate(st.session_state.custom_stocks):
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.text(f"{idx+1}. [{sector}] {name} ({code})")
                with col_del:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.custom_stocks.pop(idx)
                        st.rerun()
            
            st.divider()
            
            # 커스텀 종목 스크리닝 시작
            if st.button("🔍 내 종목 스크리닝 시작", type="primary", key="custom_screen"):
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
                    time.sleep(0.5)  # IP 차단 방지

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
                            "거래량": st.column_config.NumberColumn("거래량", format="%d")
                        }
                    )
                else:
                    st.warning("⚠️ 조건에 부합하는 종목이 현재 없습니다.")
                    st.info("💡 필터 조건을 조정하거나 다른 조합을 시도해보세요.")
        else:
            st.info("👆 위에서 종목을 추가해주세요.")
            
else:
    st.info("👈 사이드바에서 비밀번호를 입력하세요")
