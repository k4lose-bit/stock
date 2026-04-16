from modules.indicators import TechnicalIndicators

class StockAnalyzer:
    def __init__(self):
        self.indicator = TechnicalIndicators()

    def analyze(self, code, name, sector, data):
        try:
            prices = data["close_prices"]

            rsi = self.indicator.calculate_rsi(prices)
            macd, sig, hist = self.indicator.calculate_macd(prices)
            cross = self.indicator.check_macd_crossover(prices)
            bb_upper, bb_mid, bb_lower = self.indicator.calculate_bollinger_bands(prices)
            ma20, ma60 = self.indicator.calculate_moving_averages(prices)
            
            if rsi is None or macd is None:
                return None

            gap = ((data["open"] - data["prev_close"]) / data["prev_close"]) * 100
            
            volume_surge = False
            if len(data["volumes"]) >= 5:
                avg_vol = sum(data["volumes"][-5:]) / 5
                if data["volume"] >= avg_vol * 2.0:
                    volume_surge = True

            signals = []
            details = []
            recommendation = "관망"
            rec_color = "🟡"

            # 기존 RSI & MACD 신호
            if rsi <= 30:
                signals.append("RSI 과매도")
                details.append("📉 **RSI 과매도 구간**: 현재 주가가 단기적으로 과도하게 하락한 상태입니다. 기술적 반등이 나올 확률이 높습니다.")
            elif rsi >= 70:
                signals.append("RSI 과매수")
                details.append("📈 **RSI 과매수 구간**: 주가가 단기적으로 과열된 상태입니다. 조정에 대비해야 합니다.")

            if cross == "골든크로스":
                signals.append("MACD 골든크로스")
                details.append("✨ **MACD 골든크로스**: 추세선이 위로 교차했습니다. 전형적인 상승 전환 신호입니다.")
            elif cross == "데드크로스":
                signals.append("MACD 데드크로스")
                details.append("⚠️ **MACD 데드크로스**: 추세선이 아래로 교차했습니다. 하락 위험이 있습니다.")

            # 🌟 새롭게 추가된 볼린저 밴드 신호 분석
            if bb_lower and data["current"] <= bb_lower * 1.03:
                signals.append("볼린저 밴드 하단 터치")
                details.append("📉 **볼린저 밴드 하단**: 주가가 밴드 하단에 도달했습니다. 통계적으로 반등할 확률이 높은 매수 급소입니다.")
            elif bb_upper and data["current"] >= bb_upper * 0.97:
                signals.append("볼린저 밴드 상단 터치")
                details.append("📈 **볼린저 밴드 상단**: 주가가 밴드 상단 저항에 부딪혔습니다. 단기 차익 실현 물량에 주의하세요.")

            # 🌟 새롭게 추가된 20일 이동평균선 돌파 분석
            if ma20 and data["prev_close"] < ma20 and data["current"] > ma20:
                signals.append("20일선 상향 돌파")
                details.append("🚀 **20일선 돌파**: 단기 생명선인 20일선을 강하게 뚫고 올라왔습니다. 본격적인 단기 상승 추세 진입을 의미합니다.")

            if volume_surge:
                signals.append("거래량 급증")
                details.append("🔥 **거래량 폭발**: 최근 5일 평균 대비 거래량이 급증했습니다. 강력한 시장의 관심이 쏠리고 있습니다.")

            # 종합 추천 판단
            if rsi <= 30 and cross == "골든크로스":
                recommendation = "적극 매수"
                rec_color = "🟢"
            elif rsi <= 30 or cross == "골든크로스" or "볼린저 밴드 하단 터치" in signals or "20일선 상향 돌파" in signals:
                recommendation = "매수 고려"
                rec_color = "🟢"
            elif rsi >= 70 or cross == "데드크로스" or "볼린저 밴드 상단 터치" in signals:
                recommendation = "매도 고려"
                rec_color = "🔴"

            if not details:
                details.append("📊 현재 특별한 기술적 과열이나 바닥 신호가 감지되지 않는 '중립' 구간입니다.")

            return {
                "sector": sector,
                "code": code,
                "name": name,
                "current": data["current"],
                "change": gap, # 당일 갭 변경률
                "rsi": rsi,
                "macd": macd,
                "signal": sig,
                "macd_cross": cross,
                "bb_upper": bb_upper,
                "bb_lower": bb_lower,
                "ma20": ma20,
                "volume": data["volume"],
                "signals": signals,
                "details": details,
                "recommendation": recommendation,
                "recommendation_color": rec_color,
            }
        except Exception as e:
            print(f"[ERROR] 분석 실패: {e}")
            return None
