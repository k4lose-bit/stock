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

st.set_page_config(page_title="Stock Screener Pro", layout="wide")

st.markdown('<meta name="format-detection" content="telephone=no">', unsafe_allow_html=True)
st.markdown("""
<style>
div[data-baseweb="input"] { border: 2px solid #1E90FF !important; }
.metric-card { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 15px; }
.metric-title { color: #616161; font-size: 1.0rem; font-weight: 600; margin-bottom: 8px; }
.metric-value { color: #212121; font-size: 1.9rem; font-weight: 800; }
.metric-delta.red { color: #f44336; font-size: 1.1rem; font-weight: bold; margin-top: 5px; }
.metric-delta.blue { color: #2196f3; font-size: 1.1rem; font-weight: bold; margin-top: 5px; }
.metric-delta.gray { color: #9e9e9e; font-size: 1.1rem; font-weight: bold; margin-top: 5px; }
.metric-caption { color: #9e9e9e; font-size: 0.85rem; margin-top: 5px; }
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
    
    c1.markdown(draw_card("현재가", f"{curr_txt}{p_unit}", diff, f"{diff_txt}{p_unit}", conv_txt), unsafe_allow_html=True)
    c2.markdown(draw_card("등락률", f"{chg:+.2f}%", diff, ""), unsafe_allow_html=True)
    
    rsi_val = an.get('rsi')
    rsi_txt = f"{rsi_val:.1f}" if rsi_val is not None else "-"
    c3.markdown(draw_card("RSI", rsi_txt, 0, ""), unsafe_allow_html=True)
    
    vol_txt = f"{int(data['volume']):,}"
    c4.markdown(draw_card("거래량", vol_txt, 0, ""), unsafe_allow_html=True)

    if len(data['dates']) >= 6:
        st.write("#### 🕒 최근 5거래일 추이 (RSI & MACD 포함)")
        df_pr = pd.DataFrame({'Close': data['close_prices']})
        
        ema12 = df_pr['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df_pr['Close'].ewm(span=26, adjust=False).mean()
        df_pr['MACD'] = ema12 - ema26
        
        delta_pr = df_pr['Close'].diff()
        gain = delta_pr.where(delta_pr > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta_pr.where(delta_pr < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df_pr['RSI'] = 100 - (100 / (1 + rs))
        
        rsi_list = df_pr['RSI'].tolist()
        macd_list = df_pr['MACD'].tolist()

        table_html = "<table class='custom-table'><tr><th>날짜</th><th>종가</th><th>변동</th><th>등락률</th><th>거래량</th><th>RSI</th><th>MACD</th></tr>"
        
        for i in range(-2, -7, -1):
            p, po = data['close_prices'][i], data['close_prices'][i-1]
            df_val, dc = p-po, ((p-po)/po)*100
            clr = "#f44336" if df_val > 0 else ("#2196f3" if df_val < 0 else "#616161")
            
            p_f = f"{p:,.2f}$" if p < 1000 else f"{int(p):,}원"
            df_f = f"{df_val:+,.2f}$" if p < 1000 else f"{int(df_val):+,}원"
            
            d_rsi = rsi_list[i]
            if pd.notna(d_rsi):
                rsi_clr = "#f44336" if d_rsi >= 70 else ("#2196f3" if d_rsi <= 30 else "#424242")
                rsi_str = f"<span style='color:{rsi_clr}; font-weight:bold;'>{d_rsi:.1f}</span>"
            else: rsi_str = "-"
                
            d_macd = macd_list[i]
            if pd.notna(d_macd):
                macd_clr = "#f44336" if d_macd > 0 else ("#2196f3" if d_macd < 0 else "#424242")
                macd_str = f"<span style='color:{macd_clr}; font-weight:bold;'>{d_macd:.2f}</span>"
            else: macd_str = "-"
            
            table_html += f"<tr><td>{data['dates'][i][5:]}</td><td><b>{p_f}</b></td><td style='color:{clr}; font-weight:bold;'>{df_f}</td><td style='color:{clr}; font-weight:bold;'>{dc:+.2f}%</td><td>{int(data['volumes'][i]):,}</td><td>{rsi_str}</td><td>{macd_str}</td></tr>"
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
        
        _, search_col, _ = st.columns([1, 2, 1])
        with search_col:
            query = st.text_input("종목명 입력 (삼성, LG, IREN...)", placeholder="검색어를 입력하면 아래에 후보가 나타납니다.")
            if query:
                cands = search_candidates(query)
                if cands.empty:
                    st.warning(f"'{query}'에 대한 검색 결과가 없습니다. 잠시 후 다시 시도해주세요.")
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
                
                if st.session_state.port_code == s['code']:
                    render_report(fetcher, analyzer, exc_rate, s, f"tab2_{i}")
                    st.divider()

    with tab3:
        st.subheader("📥 데이터베이스 관리")
        st.info("""
        **💡 관리자 전용 DB 갱신 안내**
        보안 및 안정성을 위해 종목 데이터베이스 갱신은 앱 외부(서버/깃허브)에서 진행됩니다.
        1. [KRX 정보데이터시스템](http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020101) 접속 > [기본통계] > [주식] > [종목정보] > [전종목 기본정보]
        2. 우측 상단의 [⬇️ 다운로드] 버튼을 눌러 **CSV 파일**을 다운받습니다.
        3. 다운받은 파일 이름을 **`krx_stock_list.csv`** 로 변경합니다.
        4. GitHub 등 앱 소스 코드가 있는 저장소에 해당 파일을 덮어쓰기(업로드) 하시면 자동으로 앱에 반영됩니다.
        """)
        st.write("---")
        db_df = get_stock_db()
        csv_data = db_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 현재 앱에 적용된 종목 리스트 확인용 다운로드", data=csv_data, file_name=f"krx_stock_list_active.csv", mime="text/csv")
        st.write("---")
        if st.button("🚪 로그아웃", type="primary"):
            st.session_state.pw_ok = False; st.rerun()
