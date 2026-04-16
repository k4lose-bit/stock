import pandas as pd
import ta
import numpy as np

class StockAnalyzer:
    def analyze(self, code, name, sector, data):
        try:
            # 1. 히스토리 데이터 확인
            hist = data.get('history')
            if hist is None or hist.empty or len(hist) < 14:
                return {
                    "rsi": None, 
                    "recommendation": "최근 14일 이상의 거래 데이터가 부족하여 기술적 분석을 수행할 수 없습니다.", 
                    "details": []
                }

            # 2. RSI 계산 (정상 설치된 ta 라이브러리 사용)
            close_prices = hist['Close']
            rsi_series = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
            current_rsi = float(rsi_series.iloc[-1])

            # 3. MACD 계산 (추가 지표)
            macd_series = ta.trend.MACD(close_prices).macd()
            current_macd = float(macd_series.iloc[-1])

            # 4. 자체 알고리즘(Rule-based) 분석 의견 생성 (외부 API 불필요)
            details = []
            
            # RSI 기반 판단
            if current_rsi <= 30:
                opinion = "⚠️ 과매도 구간 (Oversold)"
                details.append(f"RSI 지표가 {current_rsi:.1f}로 30 이하입니다. 단기적인 기술적 반등이 나올 수 있는 자리입니다.")
            elif current_rsi >= 70:
                opinion = "⚠️ 과매수 구간 (Overbought)"
                details.append(f"RSI 지표가 {current_rsi:.1f}로 70 이상입니다. 단기 고점일 확률이 높으므로 차익 실현 및 조정에 주의하십시오.")
            else:
                opinion = "✅ 중립 추세 (Neutral)"
                details.append(f"RSI 지표가 {current_rsi:.1f}로 안정적인 수준(30~70 사이)을 유지하고 있습니다.")

            # MACD 기반 판단
            if current_macd > 0:
                details.append("MACD 지표가 양수(+) 구간에 위치하여 단기 상승 모멘텀이 살아있습니다.")
            else:
                details.append("MACD 지표가 음수(-) 구간에 위치하여 하락 압력을 받고 있습니다.")

            return {
                "rsi": current_rsi,
                "recommendation": opinion,
                "details": details
            }

        except Exception as e:
            # 코드 에러 발생 시 앱 강제 종료 방지
            return {
                "rsi": None, 
                "recommendation": f"분석 모듈 내부 에러 발생: {str(e)}", 
                "details": ["분석 엔진 코드를 확인해야 합니다."]
            }
