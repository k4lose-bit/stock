import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import hashlib

st.set_page_config(page_title="주식 스크리닝", page_icon="📈", layout="wide")

# 비밀번호 설정 (여기서 변경하세요!)
CORRECT_PASSWORD = "st0727@6816"  # 원하는 비밀번호로 변경

def check_password():
    """비밀번호 확인"""
    def password_entered():
        if hashlib.sha256(st.session_state["password"].encode()).hexdigest() == hashlib.sha256(CORRECT_PASSWORD.encode()).hexdigest():
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("## 🔐 로그인")
        st.text_input("비밀번호를 입력하세요", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("## 🔐 로그인")
        st.text_input("비밀번호를 입력하세요", type="password", on_change=password_entered, key="password")
        st.error("❌ 비밀번호가 틀렸습니다.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# 로그인 성공 후 메인 프로그램
class StockScreener:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
    def get_stock_list(self, max_pages=2):
        """코스피 전종목 리스트"""
        url = "https://finance.naver.com/sise/sise_market_sum.naver"
        stocks = []
        
        for page in range(1, max_pages + 1):
            try:
                response = requests.get(url, params={'sosok': '0', 'page': page}, headers=self.headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                table = soup.find('table', {'class': 'type_2'})
                rows = table.find_all('tr')[2:]
                
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) > 10 and cols[1].find('a'):
                        code = cols[1].find('a')['href'].split('=')[-1]
                        name = cols[1].get_text().strip()
                        stocks.append({'code': code, 'name': name})
                
                time.sleep(0.3)
            except:
                continue
        
        return stocks
    
    def get_stock_data(self, code):
        """개별 종목 데이터"""
        try:
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            current_price = soup.find('p', {'class': 'no_today'})
            if not current_price:
                return None
            current = int(current_price.find('span', {'class': 'blind'}).get_text().replace(',', ''))
            
            table = soup.find('table', {'class': 'no_info'})
            if not table:
                return None
                
            rows = table.find_all('tr')
            prev_close = None
            open_price = None
            volume = None
            
            for row in rows:
                ths = row.find_all('th')
                tds = row.find_all('td')
                for i, th in enumerate(ths):
                    text = th.get_text().strip()
                    if '전일' in text and i < len(tds):
                        prev_close = int(tds[i].get_text().replace(',', '').strip())
                    elif '시가' in text and i < len(tds):
                        open_price = int(tds[i].get_text().replace(',', '').strip())
                    elif '거래량' in text and i < len(tds):
                        volume_text = tds[i].get_text().replace(',', '').strip()
                        volume = int(volume_text) if volume_text.isdigit() else 0
            
            if not all([prev_close, open_price, volume]):
                return None
            
            prices = self.get_price_history(code, days=20)
            
            return {
                'current': current,
                'prev_close': prev_close,
                'open': open_price,
                'volume': volume,
                'price_history': prices
            }
        except:
            return None
    
    def get_price_history(self, code, days=20):
        """과거 주가 데이터"""
        try:
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}"
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = soup.find('table', {'class': 'type2'})
            if not table:
                return []
            
            rows = table.find_all('tr')[2:days+2]
            prices = []
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 5 and cols[0].get_text().strip():
                    high = cols[4].get_text().replace(',', '').strip()
                    volume = cols[5].get_text().replace(',', '').strip()
                    if high.isdigit() and volume.isdigit():
                        prices.append({'high': int(high), 'volume': int(volume)})
            
            return prices
        except:
            return []
    
    def check_conditions(self, stock_info, data, gap_threshold, volume_days, volume_ratio, box_days):
        """조건 체크"""
        try:
            gap_percent = ((data['open'] - data['prev_close']) / data['prev_close']) * 100
            if gap_percent > -gap_threshold:
                return None
            
            if len(data['price_history']) < volume_days:
                return None
            
            avg_volume = sum([p['volume'] for p in data['price_history'][:volume_days]]) / volume_days
            if avg_volume == 0 or data['volume'] < avg_volume * volume_ratio:
                return None
            
            if len(data['price_history']) < box_days:
                return None
            
            box_high = max([p['high'] for p in data['price_history'][:box_days]])
            breakout = data['current'] > box_high
            
            return {
                '종목코드': stock_info['code'],
                '종목명': stock_info['name'],
                '전일종가': f"{data['prev_close']:,}",
                '시가': f"{data['open']:,}",
                '현재가': f"{data['current']:,}",
                '갭%': f"{gap_percent:.2f}%",
                '거래량': f"{data['volume']:,}",
                '평균거래량': f"{int(avg_volume):,}",
                '거래량배수': f"{data['volume'] / avg_volume:.2f}배",
                '박스고가': f"{box_high:,}",
                '돌파여부': '✅ 돌파' if breakout else '❌ 미돌파'
            }
        except:
            return None

# Streamlit UI
st.title("📈 주식 스크리닝 프로그램")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    gap_threshold = st.number_input("갭 하락 기준 (%)", min_value=1, max_value=20, value=5)
    st.caption("전일 종가 대비 시가 하락률")

with col2:
    volume_days = st.number_input("거래량 평균 기간 (일)", min_value=3, max_value=30, value=5)
    st.caption("최근 N일 평균 거래량")

with col3:
    volume_ratio = st.number_input("거래량 증가 배수", min_value=1.0, max_value=5.0, value=1.5, step=0.1)
    st.caption("평균 대비 배수")

with col4:
    box_days = st.number_input("박스권 기간 (일)", min_value=10, max_value=60, value=20)
    st.caption("고가 기준 기간")

max_pages = st.slider("검색할 페이지 수 (1페이지 = 약 50종목)", min_value=1, max_value=10, value=2)

st.markdown("---")

if st.button("🔍 스크리닝 시작", type="primary", use_container_width=True):
    screener = StockScreener()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("종목 리스트 수집 중...")
    stocks = screener.get_stock_list(max_pages=max_pages)
    
    results = []
    total = len(stocks)
    
    for i, stock in enumerate(stocks):
        progress = (i + 1) / total
        progress_bar.progress(progress)
        status_text.text(f"분석 중: {stock['name']} ({i+1}/{total})")
        
        data = screener.get_stock_data(stock['code'])
        if data:
            result = screener.check_conditions(stock, data, gap_threshold, volume_days, volume_ratio, box_days)
            if result:
                results.append(result)
        
        time.sleep(0.3)
    
    progress_bar.empty()
    status_text.empty()
    
    st.success(f"✅ 스크리닝 완료! 총 {len(results)}개 종목 발견")
    
    if results:
        df = pd.DataFrame(results)
        
        st.markdown("### 📊 검색 결과")
        st.dataframe(df, use_container_width=True, height=400)
        
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 CSV 다운로드",
            data=csv,
            file_name=f'screening_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            mime='text/csv',
        )
        
        st.markdown("### 📈 주요 통계")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("발견 종목 수", f"{len(results)}개")
        with col2:
            breakout_count = sum(1 for r in results if '✅' in r['돌파여부'])
            st.metric("박스권 돌파", f"{breakout_count}개")
        with col3:
            st.metric("분석 종목 수", f"{total}개")
    else:
        st.warning("조건을 만족하는 종목이 없습니다.")

st.markdown("---")
st.caption("⚠️ 이 프로그램은 참고용이며, 투자 판단은 본인의 책임입니다.")