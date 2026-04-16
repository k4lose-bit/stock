import streamlit as st
import pandas as pd
import json
import time
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from modules.data_fetcher import DataFetcher, search_candidates
from modules.analyzer import StockAnalyzer

# --- [1. DB 연결 및 데이터 관리] ---
@st.cache_resource(ttl=300)
def get_db_sheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open("StockScreener_DB").sheet1
    except Exception as e:
        st.error(f"❌ DB 연결 실패: {e}")
        return None

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
    except: pass

# --- [2. 앱 설정 및 스타일] ---
st.set_page_config(page_title="Stock Screener Pro", layout="wide")

st.markdown("""
<style>
    div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
    .metric-card { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .metric-title { color: #616161; font-size: 1.0rem; font-weight: 600; margin-bottom: 8px; }
    .metric-value { color: #212121; font-size: 1.8rem; font-weight: 800; }
    .metric-delta.red { color: #f44336; font-size: 1.1rem; font-weight: bold; }
    .metric-delta.blue { color: #2196f3; font-size: 1.1rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- [3. 로그인 화면] ---
if "login_info" not in st.session_state:
    st.title("🚀 Stock Screener Pro")
    st.info("나만의 관심종목을 안전하게 보관하려면 닉네임과 PIN번호를 입력하세요.")
    _, col, _ = st.columns([1, 1, 1])
    with col:
        nick = st.text_input("닉네임 (ID)", placeholder="예: 스톡마스터")
        pin = st.text_input("보안 PIN 번호 (숫자 4자리)", type="password")
        if st.button("로그인 및 데이터 동기화", use_container_width=True, type="primary"):
            sheet = get_db_sheet()
            if sheet:
                res = load_user_favs(sheet, nick, pin)
                if res == "AUTH_FAIL": 
                    st.error("PIN 번호가 틀렸습니다.")
                else:
                    st.session_state.login_info = {"nick": nick, "pin": pin}
                    try:
                        st.session_state.custom_stocks = json.loads(res) if res not in ["NEW_USER", "[]", ""] else []
                    except: 
                        st.session_state.custom_stocks = []
                    st.rerun()
else:
    # --- [4. 메인 대시보드] ---
    user = st.session_state.login_info
    fetcher, analyzer = DataFetcher(), StockAnalyzer()
    sheet = get_db_sheet()
    
    if "custom_stocks" not in st.session_state: 
        st.session_state.custom_stocks = []

    st.sidebar.write(f"👤 **{user['nick']}** 님 접속 중")
    if st.sidebar.button("🚪 로그아웃"):
        del st.session_state.login_info
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["🔍 종목 분석", "⭐ 내 관심종목", "⚙️ 관리"])

    # --- 공통 리포트 함수 ---
    def render_report(item, key_suffix):
        with st.spinner("AI가 차트 및 기술적 지표를 분석 중입니다..."):
            data = fetcher.get_stock_data(item['code'])
            if not data:
                st.error("⚠️ 야후 파이낸스(Yahoo Finance)에서 데이터를 불러오지 못했습니다. 잠시 후 다시 시도하거나 다른 종목을 검색해 보세요.")
                return

            an_raw = analyzer.analyze(item['code'], item['name'], "기타", data)
            
            an = {}
            if isinstance(an_raw, dict):
                an = an_raw
            elif isinstance(an_raw, str):
                try:
                    an = json.loads(an_raw)
                except:
                    an = {"recommendation": an_raw, "details": []}

            st.divider()
            st.subheader(f"📊 {item['name']} ({item['code']}) 실시간 리포트")
            
            curr, prev = data['current'], data['prev_close']
            diff, chg = curr - prev, ((curr - prev) / prev) * 100
            p_unit = "$" if curr < 1000 else "원"
            
            rsi_raw = an.get('rsi')
            try:
                rsi_display = f"{float(rsi_raw):.1f}"
            except:
                rsi_display = str(rsi_raw) if rsi_raw else "계산불가"
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                color = "red" if diff > 0 else "blue"
                arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "")
                st.markdown(f"""<div class="metric-card"><div class="metric-title">현재가</div><div class="metric-value">{curr:,.2f}{p_unit}</div><div class="metric-delta {color}">{arrow} {abs(diff):,.2f}</div></div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""<div class="metric-card"><div class="metric-title">등락률</div><div class="metric-value">{chg:+.2f}%</div></div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""<div class="metric-card"><div class="metric-title">RSI (14일)</div><div class="metric-value">{rsi_display}</div></div>""", unsafe_allow_html=True)
            with c4:
                st.markdown(f"""<div class="metric-card"><div class="metric-title">거래량</div><div class="metric-value">{int(data['volume']):,}</div></div>""", unsafe_allow_html=True)

            rec = an.get('recommendation') or an.get('opinion') or "AI 분석 엔진에서 응답을 받지 못했습니다."
            st.info(f"💡 **AI 분석 의견:** {rec}")
            
            for detail in an.get('details', []):
                st.write(f"- {detail}")

            is_fav = any(s['code'] == item['code'] for s in st.session_state.custom_stocks)
            if not is_fav:
                if st.button("➕ 내 관심종목에 추가", key=f"add_{item['code']}_{key_suffix}", use_container_width=True, type="primary"):
                    st.session_state.custom_stocks.append(item)
                    save_user_favs(sheet, user['nick'], user['pin'], st.session_state.custom_stocks)
                    st.rerun()

    # --- 탭 내용 ---
    with tab1:
        query = st.text_input("종목명/티커 입력", placeholder="예: 휴림로봇, 삼성전자, AAPL 등")
        if query:
            cands = search_candidates(query)
            if not cands.empty:
                options = [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()]
                pick = st.selectbox("종목 선택", options)
                # 🌟 버튼을 다시 예쁜 빨간색(primary)으로 복구하고 공백 제거 추가!
                if st.button("🚀 분석 시작", use_container_width=True, type="primary"):
                    code = pick.split("(")[1].replace(")", "").strip()
                    name = pick.split(" (")[0].strip()
                    render_report({"code": code, "name": name}, "search")

    with tab2:
        if not st.session_state.custom_stocks: 
            st.info("아직 저장된 관심종목이 없습니다.")
        else:
            for i, s in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([6, 2, 2])
                c1.write(f"### **{s['name']}** ({s['code']})")
                if c2.button("분석", key=f"fav_an_{i}", use_container_width=True): 
                    render_report(s, f"fav_{i}")
                if c3.button("삭제", key=f"fav_del_{i}", use_container_width=True):
                    st.session_state.custom_stocks.pop(i)
                    save_user_favs(sheet, user['nick'], user['pin'], st.session_state.custom_stocks)
                    st.rerun()
                st.divider()

    with tab3:
        st.write(f"현재 계정: **{user['nick']}**")
        st.success("✅ 구글 스프레드시트와 실시간 동기화가 완료되었습니다.")
