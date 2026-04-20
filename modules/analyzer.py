import pandas as pd
import ta
import yfinance as yf
import requests
import xml.etree.ElementTree as ET

class StockAnalyzer:
    def analyze(self, code, name, sector, data):
        try:
            hist = pd.DataFrame()
            
            if code.isdigit() and len(code) == 6:
                # 🌟 한국 주식 RSI 계산을 위한 차트 데이터도 네이버에서 로드!
                url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=100&requestType=0"
                res = requests.get(url, timeout=5)
                root = ET.fromstring(res.text)
                
                records = []
                for item in root.findall('.//item'):
                    d = item.attrib['data'].split('|')
                    records.append({'Close': float(d[4])})
                hist = pd.DataFrame(records)
            else:
                # 🌟 해외 주식
                ticker = yf.Ticker(code)
                hist = ticker.history(period="6mo")

            if hist.empty or len(hist) < 14:
                return {
                    "rsi": None,
                    "recommendation": "최근 14일 이상의 거래 데이터가 부족하여 기술적 분석을 수행할 수 없습니다.",
                    "details": []
                }

            close_prices = hist['Close']
            rsi_series = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
            current_rsi = float(rsi_series.dropna().iloc[-1])

            opinion = "✅ 중립 추세 (Neutral)"
            color = ""
            if current_rsi <= 30:
                opinion = "⚠️ 과매도 구간 (Oversold)"
                color = "🟢"
            elif current_rsi >= 70:
                opinion = "⚠️ 과매수 구간 (Overbought)"
                color = "🔴"

            return {
                "rsi": current_rsi,
                "recommendation": opinion,
                "recommendation_color": color,
                "details": [f"최근 14일 데이터를 분석한 결과, 현재 RSI 지수는 {current_rsi:.1f}입니다."]
            }

        except Exception as e:
            return {
                "rsi": None,
                "recommendation": f"분석 모듈 내부 에러: {str(e)}",
                "recommendation_color": "🔴",
                "details": []
            }
