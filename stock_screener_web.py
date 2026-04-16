import streamlit as st
import pandas as pd
import hashlib
import time
import urllib.parse
from datetime import datetime
from deep_translator import GoogleTranslator
import yfinance as yf
import requests
import xml.etree.ElementTree as ET

from modules.data_fetcher import DataFetcher, get_stock_db, search_candidates
from modules.analyzer import StockAnalyzer

# 🌟 최상단 설정
st.set_page_config(page_title="Stock Screener Pro", layout="wide")

# 🌟 휑한 느낌을 없애고 1차 때의 꽉 찬 느낌을 살리는 '카드형 UI' 및 테이블 CSS
st.markdown("""
    <meta name="format-detection" content="telephone=no">
    <style>
    div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
    
    /* 꽉 찬 느낌의 카드형 위젯 스타일 */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    .metric-title { color: #616161; font-size: 1.0rem; font-weight: 600; margin-bottom: 8px; }
    .metric-value { color: #212121; font-size: 1.9rem; font-weight: 800; }
    .metric-delta.red { color: #f44336; font-size: 1.1rem; font-weight: bold; margin-top: 5px; }
    .metric-delta.blue { color: #2196f3; font-size: 1.1rem; font-weight: bold; margin-top: 5px; }
    .metric-delta.gray { color: #9e9e9e; font-size: 1.1rem; font-weight: bold; margin-top: 5px; }
    .metric-caption { color: #9e9e9e; font-size: 0.85rem; margin-top: 5px; }

    /* 표(테이블) 디자인 깔끔하게 통일 */
    .custom-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .custom-table th, .custom-table td { border-bottom: 1px solid #eeeeee; padding: 12px 8px; text-align: center; font-size: 0.95rem; }
    .custom-table th { background-color: #f8f9fa; color: #424242; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

CORRECT_PASSWORD_HASH = "130568a3fc17054bfe36db359792c487f3a3debd226942fc2394688a7afe8339"

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return float(yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1])
    except: return 1420.0

@st.cache_data(ttl=3600)
def get_company_news(company_name):
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(company_name+' 주식')}&hl=ko&gl=KR&ceid=KR:ko"
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.text)
        return [{"title": i.find('title').text, "link": i.find('link').text} for i in root.findall('.//item')[:5]]
    except: return []

# 🌟 카드 UI를 그려주는 도우미 함수
def draw_card(title, value_str, diff_val, diff_str, caption=""):
    color_cls = "red" if diff_val > 0 else ("blue" if diff_val < 0 else "gray")
    arrow = "▲ " if diff_val > 0 else ("▼ " if diff_val < 0 else "")
    
    delta_html = f"<div class='metric-delta {color_cls}'>{arrow}{diff_str}</div>" if diff_str else ""
    caption_html = f"<div class='metric-caption'>{caption}</div>" if caption else ""
    
    return f"""
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value_str}</div>
        {delta_html}
        {caption_html}
    </div>
    """

def render_report(fetcher, analyzer, exc_rate, item, key_suffix=""):
    data = fetcher.get_stock_data(item['code'])
    if not data:
        st.error("⚠️ 실시간 데이터를 불러오지 못했습니다. 종목 코드나 네트워크를 확인해주세요.")
        return

    an = analyzer.analyze(item['code'], item['name'], item['sector'], data)
    
    # 🌟 핵심 방어막 복구: 분석 결과가 None이면 에러 뿜지 말고 여기서 차단!
    if not an:
        st.warning("⚠️ 상장 기간이 너무 짧거나 데이터가 부족하여 분석 지표를 계산할 수 없습니다.")
        return
        
    news = get_company_news(item['name'])
    
    st.subheader(f"📈 {item['name']} ({item['code']}) 리포트")
    
    curr, prev = data['current'], data['prev_close']
    diff = curr - prev
    chg = (diff / prev) * 100
    
    c1, c2, c3, c4 = st.columns(4)
    p_unit = "원" if curr > 1000 else "$"
    
    curr_txt = f"{curr:,.2f}" if p_unit == "$" else f"{int(curr):,}"
    diff_txt = f"{diff:+,.2f}" if p_unit == "$" else f"{int(diff):+,}"
    conv_txt = f"약 {int(curr * exc_rate):,}원" if p_unit == "$" else ""
    
    # 🌟 1차 버전의 꽉 찬 느낌을 주는 카드 디자인 적용
    c1.markdown(draw_card("현재가", f"{curr_txt}{p_unit}", diff, f"{diff_txt}{p_unit}", conv_txt), unsafe_allow_html=True)
    c2.markdown(draw_card("등락률", f"{chg:+.2f}%", diff, ""), unsafe_allow_html=True)
    
    rsi_val = an.get('rsi')
    rsi_txt = f"{rsi_val:.1f}" if rsi_val is not None else "-"
    c3.markdown(draw_card("RSI", rsi_txt, 0, ""), unsafe_allow_html=True)
    
    vol_txt = f"{int(data['volume']):,}"
    c4.markdown(draw_card("거래량", vol_txt, 0, ""), unsafe_allow_html=True)

    if len(data['dates']) >= 6:
        st.write("#### 🕒 최근 5거래일 추이")
        table_html = "<table class='custom-table'><tr><th>날짜</th><th>종가</th><th>변동</th><th>등락률</th><th>거래량</th></tr>"
        
        for i in range(-2, -7, -1):
            p, po = data['close_prices'][i], data['close_prices'][i-1]
            df_val, dc = p-po, ((p-po)/po)*100
            clr = "#f44336" if df_val > 0 else ("#2196f3" if df_val < 0 else "#616161")
            
            p_f = f"{p:,.2f}$" if p < 1000 else f"{int(p):,}원"
            df_f = f"{df_val:+,.2f}$" if p < 1000 else f"{int(df_val):+,}원"
            
            table_html += f"<tr>"
            table_html += f"<td>{data['dates'][i][5:]}</td>"
            table_html += f"<td><b>{p_f}</b></td>"
            table_html += f"<td style='color:{clr}; font-weight:bold;'>{df_f}</td>"
            table_html += f"<td style='color:{clr}; font-weight:bold;'>{dc:+.2f}%</td>"
            table_html += f"<td>{int(data['volumes'][i]):,}</td>"
            table_html += "</tr>"
            
        table_html += "</table>"
        st.markdown(table_html, unsafe_allow_html=True)

    st.divider()
    st.subheader("💡 종합 분석 의견")
    st.markdown(f"### {an['recommendation_color']} {an['recommendation']}")
    for d in an['details']: st.success(d)
    
    st.divider()
    judal_url = f"https://www.google.com/search?q=site:judal.co.kr+{urllib.parse.quote(item['name'])}+투자분석"
    st.info(f"💡 [주달(Judal) 테마 확인]({judal_url})")
    for n in news: st.markdown(f"🔗 [{n['title']}]({n['link']})")

    if not any(s["code"] == item['code'] for s in st.session_state.get("custom_stocks", [])):
        st.write("")
        if st.button("➕ 이 종목을 '관심종목'에 추가", key=f"add_{item['code']}_{key_suffix}", use_container_width=True, type="primary"):
            if "custom_stocks" not in st.session_state: st.session_state.custom_stocks = []
            st.session_state.custom_stocks.append(item); st.rerun()

# --- 메인 실행 로직 ---
if "pw_ok" not in st.session_state: st.session_state.pw_ok = False
if "custom_stocks" not in st.session_state: st.session_state.custom_stocks = []
if "search_history" not in st.session_state: st.session_state.search_history = []
if "active_item" not in st.session_state: st.session_state.active_item = None
if "port_code" not in st.session_state: st.session_state.port_code = None

if not st.session_state.pw_ok:
    st.title("🚀 Stock Screener Pro")
    st.write("---")
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.subheader("🔒 로그인")
        pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
        if st.button("들어가기", use_container_width=True, type="primary"):
            if hashlib.sha256(pw.encode()).hexdigest() == CORRECT_PASSWORD_HASH:
                st.session_state.pw_ok = True; st.rerun()
            else: st.error("비밀번호가 틀렸습니다.")
else:
    fetcher, analyzer, exc_rate = DataFetcher(), StockAnalyzer(), get_exchange_rate()
    
    if datetime.now().day == 13:
        st.info("📅 오늘은 매월 13일, 종목 리스트 업데이트 권장일입니다.")

    tab1, tab2, tab3 = st.tabs(["🔍 종목 분석", "⭐ 관심종목", "⚙️ 관리"])

    with tab1:
        st.markdown("### 🕒 최근 검색")
        if st.session_state.search_history:
            cols = st.columns(5)
            for i, h in enumerate(st.session_state.search_history):
                if cols[i%5].button(h['name'], key=f"h_{i}", use_container_width=True):
                    st.session_state.active_item = h; st.rerun()
        
        st.divider()
        query = st.text_input("종목명 입력 (삼성, LG, IREN...)", placeholder="검색어를 입력하면 아래에 후보가 나타납니다.")
        if query:
            cands = search_candidates(query)
            
            if cands.empty:
                st.warning(f"'{query}'에 대한 검색 결과가 없습니다. ⚙️관리 탭에서 CSV를 업로드하시거나 잠시 후 다시 시도해주세요.")
            else:
                options = [f"{r['회사명']} ({r['종목코드']})" for _, r in cands.iterrows()]
                pick = st.selectbox("정확한 종목을 선택하세요", options)
                if st.button("📊 즉시 분석", type="primary", use_container_width=True):
                    code = pick.split("(")[1].replace(")", "")
                    name = pick.split(" (")[0]
                    item = {"code": code, "name": name, "sector": "기타"}
                    st.session_state.active_item = item
                    st.session_state.search_history = [i for i in st.session_state.search_history if i['code'] != code]
                    st.session_state.search_history.insert(0, item)
                    st.session_state.search_history = st.session_state.search_history[:10]
                    st.rerun()

        if st.session_state.active_item:
            st.divider()
            render_report(fetcher, analyzer, exc_rate, st.session_state.active_item, "tab1")

    with tab2:
        st.markdown("### ⭐ 내 관심종목 리스트")
        if not st.session_state.custom_stocks: st.info("관심종목을 추가해 보세요.")
        else:
            col1, col2 = st.columns([8, 2])
            with col2:
                if st.button("🗑️ 전체 삭제", use_container_width=True): 
                    st.session_state.custom_stocks = []; st.rerun()
            
            for i, s in enumerate(st.session_state.custom_stocks):
                c1, c2, c3 = st.columns([5, 3, 2])
                c1.write(f"**{s['name']}** ({s['code']})")
                lbl = "🔼 닫기" if st.session_state.port_code == s['code'] else "📊 분석"
                if c2.button(lbl, key=f"p_an_{i}", use_container_width=True):
                    st.session_state.port_code = None if st.session_state.port_code == s['code'] else s['code']; st.rerun()
                if c3.button("❌", key=f"p_del_{i}", use_container_width=True):
                    st.session_state.custom_stocks.pop(i); st.rerun()
                
                # 🌟 관심종목 탭에서도 카드가 펼쳐지도록 적용
                if st.session_state.port_code == s['code']:
                    render_report(fetcher, analyzer, exc_rate, s, f"tab2_{i}")
                    st.divider()

    with tab3:
        st.subheader("📥 데이터베이스 관리")
        st.write("스트림릿 클라우드 환경에서는 한국거래소(KRX) 연결이 간헐적으로 차단될 수 있습니다. 종목 검색이 안 될 경우 직접 CSV 파일을 업로드해주세요.")
        
        uploaded_file = st.file_uploader("전체 종목 리스트 CSV 업로드", type=['csv'])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                col_map = {}
                for c in df.columns:
                    if "코드" in c or "code" in c.lower(): col_map[c] = "종목코드"
                    elif "명" in c or "name" in c.lower(): col_map[c] = "회사명"
                    elif "섹터" in c or "업종" in c: col_map[c] = "섹터"
                df = df.rename(columns=col_map)
                df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                if '섹터' not in df.columns: df['섹터'] = '기타'
                
                st.session_state.uploaded_db = df[['종목코드', '회사명', '섹터']].dropna()
                st.success(f"✅ {len(st.session_state.uploaded_db)}개의 종목 데이터가 성공적으로 반영되었습니다!")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

        st.write("---")
        db_df = get_stock_db()
        csv_data = db_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 현재 적용 중인 종목 리스트(CSV) 다운로드", data=csv_data, file_name=f"krx_stock_list_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        st.write("---")
        if st.button("🚪 로그아웃", type="primary"):
            st.session_state.pw_ok = False; st.rerun()
