import streamlit as st
import pandas as pd
import hashlib
import json
import urllib.parse
from datetime import datetime
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from modules.data_fetcher import DataFetcher, get_stock_db, search_candidates
from modules.analyzer import StockAnalyzer

# --- 구글 시트 DB 연결 함수 ---
@st.cache_resource
def get_db_sheet():
    try:
        # 스트림릿 Secrets에서 TOML 형식의 키 가져오기
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        
        # 🌟 구글 시트 이름이 정확해야 합니다!
        sheet = client.open("StockScreener_DB").sheet1 
        return sheet
    except Exception as e:
        st.error(f"❌ DB 연결 실패: {e}")
        return None

def load_user_favs(sheet, nickname, pin):
    records = sheet.get_all_records()
    for row in records:
        if str(row.get('Nickname')) == nickname:
            if str(row.get('PIN')) == pin:
                return row.get('Favorites', "[]")
            else:
                return "AUTH_FAIL"
    return "NEW_USER"

def save_user_favs(sheet, nickname, pin, favorites_list):
    fav_json = json.dumps(favorites_list, ensure_ascii=False)
    records = sheet.get_all_records()
    for idx, row in enumerate(records):
        if str(row.get('Nickname')) == nickname:
            sheet.update_cell(idx + 2, 3, fav_json)
            return
    sheet.append_row([nickname, pin, fav_json])

# --- 앱 설정 ---
st.set_page_config(page_title="Stock Screener Pro", layout="wide")

# CSS 스타일 (이전과 동일)
st.markdown("""<style>
div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
.metric-card { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 15px; }
.metric-title { color: #616161; font-size: 1.0rem; font-weight: 600; margin-bottom: 8px; }
.metric-value { color: #212121; font-size: 1.9rem; font-weight: 800; }
.custom-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
.custom-table th, .custom-table td { border-bottom: 1px solid #eeeeee; padding: 12px 8px; text-align: center; font-size: 0.95rem; }
.guide-box { background-color: #f0f7ff; border-left: 5px solid #1E90FF; padding: 15px; border-radius: 5px; margin-top: 15px; font-size: 0.95rem; }
</style>""", unsafe_allow_html=True)

# (이전 코드 상단 생략)

# --- 로그인 세션 관리 ---
if "login_info" not in st.session_state:
    st.title("🚀 Stock Screener Pro")
    st.info("나만의 관심종목을 안전하게 보관하려면 닉네임과 PIN번호를 입력하세요.")
    
    _, col, _ = st.columns([1, 1, 1])
    with col:
        # 🌟 닉네임 예시를 더 범용적이고 깔끔하게 수정했습니다.
        nick = st.text_input("닉네임 (ID)", placeholder="예: 스톡마스터, 투자왕, user01 등")
        pin = st.text_input("보안 PIN 번호 (숫자 4자리)", type="password", placeholder="숫자 4자리 입력")
        
        if st.button("로그인 및 데이터 동기화", use_container_width=True, type="primary"):
            if not nick or not pin:
                st.warning("닉네임과 보안 PIN을 모두 입력해 주세요.")
            elif not pin.isdigit() or len(pin) != 4:
                st.warning("PIN 번호는 숫자 4자리로 입력해야 합니다.")
            else:
                with st.spinner("구글 클라우드 데이터베이스에 연결 중..."):
                    sheet = get_db_sheet()
                    if sheet:
                        res = load_user_favs(sheet, nick, pin)
                        if res == "AUTH_FAIL":
                            st.error("이미 등록된 닉네임입니다. PIN 번호가 틀렸거나 다른 닉네임을 사용해 주세요.")
                        else:
                            st.session_state.login_info = {"nick": nick, "pin": pin}
                            try:
                                st.session_state.custom_stocks = json.loads(res) if res != "NEW_USER" else []
                                st.success(f"반갑습니다, {nick}님! 데이터 로딩 완료.")
                                time.sleep(1) # 성공 메시지를 잠시 보여줌
                            except: 
                                st.session_state.custom_stocks = []
                            st.rerun()

else:
    # --- 메인 앱 ---
    user = st.session_state.login_info
    fetcher, analyzer = DataFetcher(), StockAnalyzer()
    sheet = get_db_sheet()

    st.sidebar.write(f"👤 **{user['nick']}** 님")
    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.login_info
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🔍 종목 분석", "⭐ 내 관심종목", "⚙️ 관리"])

    # --- 공통 리포트 렌더링 함수 ---
    def render_report(item, key_suffix):
        # (기본 리포트 코드는 이전과 동일하되, 관심종목 추가 버튼에서 DB 저장을 호출)
        # ... (생략된 리포트 로직) ...
        if st.button("➕ 관심종목 추가", key=f"add_{item['code']}_{key_suffix}", use_container_width=True):
            if not any(s['code'] == item['code'] for s in st.session_state.custom_stocks):
                st.session_state.custom_stocks.append(item)
                save_user_favs(sheet, user['nick'], user['pin'], st.session_state.custom_stocks)
                st.rerun()

    # (이후 탭별 로직 및 종목 검색 코드는 이전과 동일하게 유지)
    # ⚠️ 단, 관심종목 삭제 버튼에서도 save_user_favs를 호출해야 함
    # 예: if c3.button("❌"): st.session_state.custom_stocks.pop(i); save_user_favs(...); st.rerun()

    st.markdown("---")
    st.caption("⚠️ **투자 주의 및 면책 조항** 본 서비스의 데이터는 참고용이며 투자 판단의 최종 책임은 사용자에게 있습니다.")
