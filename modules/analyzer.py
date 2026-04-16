import pandas as pd
import ta
import yfinance as yf

class StockAnalyzer:
    def analyze(self, code, name, sector, data):
        try:
            # 1. 남이 주는 데이터 기다리지 않고, 직접 야후 파이낸스에서 차트 다운로드!
            hist = pd.DataFrame()
            
            if code.isdigit() and len(code) == 6:
                # 한국 주식인 경우 (코스피 우선 시도, 안 되면 코스닥)
                ticker = yf.Ticker(f"{code}.KS")
                hist = ticker.history(period="6mo")
                if hist.empty:
                    ticker = yf.Ticker(f"{code}.KQ")
                    hist = ticker.history(period="6mo")
            else:
                # 해외 주식인 경우 (AAPL, NOK 등)
                ticker = yf.Ticker(code)
                hist = ticker.history(period="6mo")

            # 다운로드 실패 확인
            if hist.empty or len(hist) < 14:
                return {
                    "rsi": None,
                    "recommendation": "야후 파이낸스 서버에서 과거 차트 기록을 받아오지 못했습니다.",
                    "details": []
                }

            # 2. RSI 계산 (ta 라이브러리)
            close_prices = hist['Close']
            rsi_series = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
            current_rsi = float(rsi_series.dropna().iloc[-1])

            # 3. 분석 의견 생성
            opinion = "✅ 중립 추세 (Neutral)"
            if current_rsi <= 30:
                opinion = "⚠️ 과매도 구간 (Oversold)"
            elif current_rsi >= 70:
                opinion = "⚠️ 과매수 구간 (Overbought)"

            return {
                "rsi": current_rsi,
                "recommendation": opinion,
                "details": [f"최근 14일 데이터를 분석한 결과, 현재 RSI 지수는 {current_rsi:.1f}입니다."]
            }

        except Exception as e:
            return {
                "rsi": None,
                "recommendation": f"분석 모듈 내부 에러: {str(e)}",
                "details": []
            }
