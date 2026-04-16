import streamlit as st
import pandas as pd
import json
import time
import urllib.parse
from datetime import datetime
import yfinance as yf
import gspread
import requests
import xml.etree.ElementTree as ET
from oauth2client.service_account import ServiceAccountCredentials

from modules.data_fetcher import DataFetcher, search_candidates
from modules.analyzer import StockAnalyzer

# --- [1. DB 및 외부 데이터 설정] ---
@st.cache_resource(ttl=300)
def get_db_sheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open("StockScreener_DB").sheet1
    except Exception as e:
        st.error(f"❌ 데이터베이스 연결 실패: {e}")
        return None

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("USDKRW=X").history(period="1d")
        return float(rate['Close'].iloc[-1])
    except: return 1420.0

@st.cache_data(ttl=3600)
def get_company_news(company_name):
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(company_name+' 주식')}&hl=ko&gl=KR&ceid=KR:ko"
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.text)
        return [{"title": i.find('title').text, "link": i.find('link').text} for i in root.findall('.//item')[:5]]
    except: return []

# --- [2. 사용자 데이터 관리 함수] ---
def load_user_favs(sheet, nickname, pin):
    try:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get('Nickname')) == nickname:
                if str(row.get('PIN')) == pin:
                    return row.get('Favorites', "[]")
                else: return "AUTH_FAIL"
        return "NEW_USER"
    except: return "[]"

def save_user_favs(sheet, nickname, pin, favorites_list):
    try:
        fav_json = json.dumps(favorites_list, ensure_ascii=False)
        records = sheet.get_all_records()
        for idx, row in enumerate(records):
            if str(row.get('Nickname')) == nickname:
                sheet.update_cell(idx + 2, 3, fav_json)
                return
        sheet.append_row([nickname, pin, fav_json])
    except Exception as e:
        st.error(f"⚠️ 저장 중 오류 발생: {e}")

# --- [3. 앱 설정 및 스타일] ---
st.set_page_config(page_title="Stock Screener Pro", layout="wide")
st.markdown("""
<style>
    div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
    .metric-card { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .metric-title { color: #616161; font-size: 0.9rem; font-weight: 600; }
    .metric-value { color: #212121; font-size: 1.6rem; font-weight: 800; margin: 5px 0; }
    .red { color: #f44336; font-weight: bold; }
    .blue { color: #2196f3; font-weight: bold; }
    .stTable td { text-align: center !important; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# --- [4. 리포트 렌더링 함수 (복구 및 통합)] ---
def render_full_report(item, fetcher, analyzer, exc_rate, sheet, user, key_suffix):
    with st.spinner(f"{item['name']} 분석 리포트 생성 중..."):
        data = fetcher.get_stock_data(item['code'])
        if not data:
            st.error("⚠️ 데이터를 불러올 수 없습니다.")
            return

        # 분석 수행 (RSI, MACD, 볼린저밴드 등 포함됨)
        an = analyzer.analyze(item['code'], item['name'], "기타", data)
        news = get_company_news(item['name'])

        st.divider()
        st.subheader(f"📊 {item['name']} ({item['code']}) 상세 리포트")

        # 상단 주요 지표 (4컬럼)
        curr, prev = data['current'], data['prev_close']
        diff, chg = curr - prev, ((curr - prev) / prev) * 100
        p_unit = "$" if curr < 1000 else "원"
        color = "red" if diff > 0 else "blue"
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            conv_txt = f" (약 {int(curr * exc_rate):,}원)" if p_unit == "$" else ""
            st.markdown(f"""<div class="metric-card"><div class="metric-title">현재가</div><div class="metric-value">{curr:,.2f}{p_unit}</div><div class="{color}">{diff:+,.2f} ({chg:+.2f}%)</div><div style="font-size:0.8rem; color:gray;">{conv_txt}</div></div>""", unsafe_allow_html=True)
        with c2:
            rsi_val = an.get('rsi', 0)
            st.markdown(f"""<div class="metric-card"><div class="metric-title">RSI (14)</div><div class="metric-value">{rsi_val:.1f}</div><div style="font-size:0.8rem; color:gray;">100 기준</div></div>""", unsafe_allow_html=True)
        with c3:
            # 볼린저 밴드 또는 거래량
            vol = int(data['volume'])
            st.markdown(f"""<div class="metric-card"><div class="metric-title">당일 거래량</div><div class="metric-value">{vol:,}</div><div style="font-size:0.8rem; color:gray;">주(Share)</div></div>""", unsafe_allow_html=True)
        with c4:
            # 추천 등급
            st.markdown(f"""<div class="metric-card"><div class="metric-title">AI 의견</div><div class="metric-value" style="font-size:1.2rem;">{an.get('recommendation', '분석중')}</div><div>{an.get('recommendation_color', '')}</div></div>""", unsafe_allow_html=True)

        # 최근 5거래일 추이 테이블 (복구)
        if len(data['dates']) >= 6:
            st.write("#### 🕒 최근 5거래일 추이")
            rows = []
            for i in range(-1, -6, -1):
                p, po = data['close_prices'][i], data['close_prices'][i-1]
                df_val, dc = p-po, ((p-po)/po)*100
                clr = "red" if df_val > 0 else ("blue" if df_val < 0 else "black")
                p_f = f"{p:,.2f}$" if p < 1000 else f"{int(p):,}원"
                df_f = f"{df_val:+,.2f}$" if p < 1000 else f"{int(df_val):+,}원"
                rows.append([data['dates'][i], p_f, f"<span style='color:{clr}'>{df_f}</span>", f"<span style='color:{clr}'>{dc:+.2f}%</span>", f"{int(data['volumes'][i]):,}"])
            st.write(pd.DataFrame(rows, columns=["날짜", "종가", "변동", "등락률", "거래량"]).to_html(escape=False, index=False), unsafe_allow_html=True)

        # 상세 분석 코멘트
        st.write("#### 💡 기술적 지표 분석")
        for detail in an.get('details', []):
            st.success(detail)

        # 뉴스 및 외부 링크
        col_n, col_l = st.columns(2)
        with col_n:
            st.write("#### 📰 관련 최신 뉴스")
            for n in news: st.markdown(f"- [{n['title']}]({n['link']})")
        with col_l:
            st.write("#### 🔗 외부 분석 도구")
            judal_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(item['name'])}+투자분석"
            st.info(f"[주달(Judal) 테마/재료 확인하기]({judal_url})")

        # 관심종목 추가 버튼 (동기화 포함)
        is_fav = any(s['code'] == item['code'] for s in st.session_state.custom_stocks)
        if not is_fav:
            if st.button("➕ 이 종목을 내 관심종목에 저장", key=f"add_{item['code']}_{key_suffix}", use_container_width=True, type="primary"):
                st.session_state.custom_stocks.append(item)
                save_user_favs(sheet, user['nick'], user['pin'], st.session_state.custom_stocks)
                st.toast("✅ 구글 시트에 저장되었습니다!")
                time.sleep(1)
                st.rerun()

# --- [5. 로그인 및 메인 로직] ---
if "login_info" not in st.session_state:
    st.title("🚀 Stock Screener Pro")
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.subheader("🔒 개인 공간 로그인")
        nick = st.text_input("닉네임 (ID)")
        pin = st.text_input("보안 PIN (4자리)", type="password")
        if st.button("로그인 및 동기화", use_container_width=True, type="primary"):
            sheet = get_db_sheet()
            if sheet:
                res = load_user_favs(sheet, nick, pin)
                if res == "AUTH_FAIL": st.error("PIN 번호가 틀립니다.")
                else:
                    st.session_state.login_info = {"nick": nick, "pin": pin}
                    st.session_state.custom_stocks = json.loads(res) if res not in ["NEW_USER", "[]"] else []
                    st.rerun()
else:
    user = st.session_state.login_info
    fetcher, analyzer, exc_rate = DataFetcher(), StockAnalyzer(), get_exchange_rate()
    sheet = get_db_sheet()

    st.sidebar.write(f"👤 **{user['nick']}** 님")
    if st.sidebar.button("로그아웃"):
        del st.session_state.login_info
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🔍 종목 검색", "⭐ 내 관심종목", "⚙️ 설정"])

    with tab1:
        query = st.text_input("종목명 또는 티커 입력")
        if query:
            cands = search_candidates(query)
            if not cands.empty:
                pick = st.selectbox("종목 선택", [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()])
                if st.button("실시간 분석 실행", type="primary"):
                    code = pick.split("(")[1].replace(")", "")
                    name = pick.split(" (")[0]
                    render_full_report({"code": code, "name": name}, fetcher, analyzer, exc_rate, sheet, user, "search")

    with tab2:
        if not st.session_state.custom_stocks:
            st.info("저장된 종목이 없습니다.")
        else:
            for i, s in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([6, 2, 2])
                c1.markdown(f"**{s['name']}** ({s['code']})")
                if c2.button("📈 분석", key=f"f_an_{i}"):
                    render_full_report(s, fetcher, analyzer, exc_rate, sheet, user, f"fav_{i}")
                if c3.button("🗑️ 삭제", key=f"f_del_{i}"):
                    st.session_state.custom_stocks.pop(i)
                    save_user_favs(sheet, user['nick'], user['pin'], st.session_state.custom_stocks)
                    st.rerun()

    with tab3:
        st.write(f"접속 중인 계정: {user['nick']}")
        if st.button("🔄 구글 시트 데이터 강제 새로고침"):
            res = load_user_favs(sheet, user['nick'], user['pin'])
            st.session_state.custom_stocks = json.loads(res) if res not in ["NEW_USER", "[]"] else []
            st.rerun()
