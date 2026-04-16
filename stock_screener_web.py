import streamlit as st
import pandas as pd
import json
import time
import urllib.parse
from datetime import datetime
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from modules.data_fetcher import DataFetcher, search_candidates
from modules.analyzer import StockAnalyzer

# --- [DB 연결 및 데이터 관리 함수] ---
@st.cache_resource(ttl=300)
def get_db_sheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        # 🌟 구글 시트 이름 확인 필수!
        return client.open("StockScreener_DB").sheet1
    except Exception as e:
        st.error(f"DB 연결 실패: {e}")
        return None

def load_user_favs(sheet, nickname, pin):
    records = sheet.get_all_records()
    for row in records:
        if str(row.get('Nickname')) == nickname:
            if str(row.get('PIN')) == pin:
                return row.get('Favorites', "[]")
            else: return "AUTH_FAIL"
    return "NEW_USER"

def save_user_favs(sheet, nickname, pin, favorites_list):
    fav_json = json.dumps(favorites_list, ensure_ascii=False)
    records = sheet.get_all_records()
    for idx, row in enumerate(records):
        if str(row.get('Nickname')) == nickname:
            sheet.update_cell(idx + 2, 3, fav_json)
            return
    sheet.append_row([nickname, pin, fav_json])

# --- [앱 기본 설정] ---
st.set_page_config(page_title="Stock Screener Pro", layout="wide")

# CSS 스타일 적용
st.markdown("""
<style>
    div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
    .metric-card { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .metric-title { color: #616161; font-size: 1.0rem; font-weight: 600; margin-bottom: 8px; }
    .metric-value { color: #212121; font-size: 1.9rem; font-weight: 800; }
    .custom-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .custom-table th, .custom-table td { border-bottom: 1px solid #eeeeee; padding: 12px 8px; text-align: center; font-size: 0.95rem; }
    .guide-box { background-color: #f0f7ff; border-left: 5px solid #1E90FF; padding: 15px; border-radius: 5px; margin-top: 15px; font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

# --- [로그인 세션 관리] ---
if "login_info" not in st.session_state:
    st.title("🚀 Stock Screener Pro")
    st.info("나만의 관심종목을 안전하게 보관하려면 닉네임과 PIN번호를 입력하세요.")
    
    _, col, _ = st.columns([1, 1, 1])
    with col:
        nick = st.text_input("닉네임 (ID)", placeholder="예: 스톡마스터, 투자왕, user01 등")
        pin = st.text_input("보안 PIN 번호 (숫자 4자리)", type="password", placeholder="숫자 4자리 입력")
        
        if st.button("로그인 및 데이터 동기화", use_container_width=True, type="primary"):
            if not nick or not pin:
                st.warning("닉네임과 보안 PIN을 모두 입력해 주세요.")
            elif not pin.isdigit() or len(pin) != 4:
                st.warning("PIN 번호는 숫자 4자리여야 합니다.")
            else:
                sheet = get_db_sheet()
                if sheet:
                    res = load_user_favs(sheet, nick, pin)
                    if res == "AUTH_FAIL":
                        st.error("이미 등록된 닉네임입니다. PIN 번호가 틀렸거나 다른 닉네임을 사용해 주세요.")
                    else:
                        st.session_state.login_info = {"nick": nick, "pin": pin}
                        try:
                            st.session_state.custom_stocks = json.loads(res) if res != "NEW_USER" else []
                        except: st.session_state.custom_stocks = []
                        st.success(f"반갑습니다, {nick}님!")
                        time.sleep(1)
                        st.rerun()

else:
    # --- [메인 앱 대시보드] ---
    user = st.session_state.login_info
    fetcher, analyzer = DataFetcher(), StockAnalyzer()
    sheet = get_db_sheet()

    # 사이드바 설정
    st.sidebar.write(f"👤 **{user['nick']}** 님 접속 중")
    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.login_info
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🔍 종목 분석", "⭐ 내 관심종목", "⚙️ 관리"])

    # --- 공통 리포트 출력 함수 ---
    def render_report(item, key_suffix):
        data = fetcher.get_stock_data(item['code'])
        if not data:
            st.error("데이터를 가져올 수 없습니다.")
            return

        an = analyzer.analyze(item['code'], item['name'], "기타", data)
        st.subheader(f"📈 {item['name']} ({item['code']}) 리포트")
        
        # (현재가, 등락률 등 카드 출력 로직 생략 - 이전과 동일)
        st.write(f"현재가: {data['current']:,}")

        # 관심종목 버튼
        is_fav = any(s['code'] == item['code'] for s in st.session_state.custom_stocks)
        if not is_fav:
            if st.button("➕ 관심종목 추가", key=f"add_{item['code']}_{key_suffix}", use_container_width=True):
                st.session_state.custom_stocks.append(item)
                save_user_favs(sheet, user['nick'], user['pin'], st.session_state.custom_stocks)
                st.success("관심종목이 저장되었습니다.")
                st.rerun()

    # --- 탭 1: 종목 검색 ---
    with tab1:
        st.subheader("🔍 종목 검색")
        query = st.text_input("종목명 또는 티커(예: 삼성전자, AAPL, NOK) 입력")
        if query:
            cands = search_candidates(query)
            if not cands.empty:
                options = [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()]
                pick = st.selectbox("검색 결과", options)
                if st.button("📊 분석하기"):
                    code = pick.split("(")[1].replace(")", "")
                    name = pick.split(" (")[0]
                    render_report({"code": code, "name": name}, "search")

    # --- 탭 2: 관심종목 ---
    with tab2:
        st.subheader("⭐ 저장된 관심종목")
        if not st.session_state.custom_stocks:
            st.info("아직 저장된 종목이 없습니다.")
        else:
            for i, s in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([6, 2, 2])
                c1.write(f"**{s['name']}** ({s['code']})")
                if c2.button("📊 분석", key=f"fav_an_{i}"):
                    render_report(s, f"fav_{i}")
                if c3.button("❌ 삭제", key=f"fav_del_{i}"):
                    st.session_state.custom_stocks.pop(i)
                    save_user_favs(sheet, user['nick'], user['pin'], st.session_state.custom_stocks)
                    st.rerun()

    # --- 탭 3: 관리 ---
    with tab3:
        st.subheader("⚙️ 관리")
        st.write(f"현재 접속 닉네임: **{user['nick']}**")
        st.write("관심종목 데이터가 구글 스프레드시트와 실시간 동기화 중입니다.")
        
    st.markdown("---")
    st.caption("⚠️ **투자 주의:** 본 리포트는 참고용이며 투자 책임은 본인에게 있습니다.")
