import pandas as pd
import ta

class StockAnalyzer:
    def analyze(self, code, name, sector, data):
        try:
            # 1. 과거 차트 데이터(DataFrame) 유연하게 찾기
            hist = None
            for key in ['history', 'hist', 'df', 'dataframe', 'data']:
                if key in data and isinstance(data[key], pd.DataFrame):
                    hist = data[key]
                    break

            if hist is None or hist.empty or len(hist) < 14:
                return {
                    "rsi": None,
                    "recommendation": "과거 차트 데이터가 전달되지 않았습니다. data_fetcher.py의 출력 형식을 확인해야 합니다.",
                    "details": []
                }

            # 2. RSI 계산 (ta 라이브러리 사용)
            close_prices = hist['Close']
            rsi_series = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
            current_rsi = float(rsi_series.iloc[-1])

            # 3. 자체 알고리즘 분석 의견 생성
            opinion = "✅ 중립 추세 (Neutral)"
            if current_rsi <= 30:
                opinion = "⚠️ 과매도 구간 (Oversold)"
            elif current_rsi >= 70:
                opinion = "⚠️ 과매수 구간 (Overbought)"

            return {
                "rsi": current_rsi,
                "recommendation": opinion,
                "details": [f"현재 RSI 지수는 {current_rsi:.1f}입니다."]
            }

        except Exception as e:
            return {
                "rsi": None,
                "recommendation": f"분석 모듈 내부 에러: {str(e)}",
                "details": []
            }
