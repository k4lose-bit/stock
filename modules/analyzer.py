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
            
            if rsi is None or macd is None:
                return None

            gap = ((data["open"] - data["prev_close"]) / data["prev_close"]) * 100
            
            volume_surge = False
            if len(data["volumes"]) >= 5:
                avg_vol = sum(data["volumes"][-5:]) / 5
                if data["volume"] >= avg_vol * 2.0:
                    volume_surge = True

            signals = []
            details = [] # 상세 설명을 담을 바구니
            recommendation = "관망"
            rec_color = "🟡"

            # 1. RSI 기반 상세 설명
            if rsi <= 30:
                signals.append("RSI 과매도")
                details.append("📉 **RSI 과매도 구간**: 현재 주가가 단기적으로 과도하게 하락한 상태입니다. 조만간 기술적 반등(저점 매수세 유입)이 나올 확률이 높습니다.")
            elif rsi >= 70:
                signals.append("RSI 과매수")
                details.append("📈 **RSI 과매수 구간**: 주가가 단기적으로 많이 올라 과열된 상태입니다. 차익 실현(매도) 물량이 나와 조정을 받을 수 있으니 신규 진입은 신중해야 합니다.")

            # 2. MACD 기반 상세 설명
            if cross == "골든크로스":
                signals.append("MACD 골든크로스")
                details.append("✨ **MACD 골든크로스**: 단기 추세선이 장기 추세선을 뚫고 올라갔습니다. 전형적인 상승 전환 신호로, 새로운 매수 타이밍으로 볼 수 있습니다.")
            elif cross == "데드크로스":
                signals.append("MACD 데드크로스")
                details.append("⚠️ **MACD 데드크로스**: 단기 추세선이 장기 추세선을 뚫고 내려갔습니다. 하락 추세로 꺾일 위험이 있으므로 보유 비중 축소를 고려해볼 만합니다.")

            # 3. 거래량 기반 상세 설명
            if volume_surge:
                signals.append("거래량 급증")
                details.append("🔥 **거래량 폭발**: 최근 5일 평균 대비 거래량이 2배 이상 급증했습니다. 시장의 강력한 관심(호재 또는 악재)이 쏠리고 있어 주가 변동성이 매우 클 것입니다.")

            # 4. 종합 추천 판별
            if rsi <= 30 and cross == "골든크로스":
                recommendation = "적극 매수"
                rec_color = "🟢"
            elif rsi <= 30 or cross == "골든크로스":
                recommendation = "매수 고려"
                rec_color = "🟢"
            elif rsi >= 70 or cross == "데드크로스":
                recommendation = "매도 고려"
                rec_color = "🔴"

            # 특별한 신호가 없을 때
            if not details:
                details.append("📊 현재 특별한 기술적 과열이나 바닥 신호가 감지되지 않는 '중립' 구간입니다. 뉴스나 기업의 실적, 향후 성장성을 중심으로 판단하는 것이 좋습니다.")

            return {
                "sector": sector,
                "code": code,
                "name": name,
                "current": data["current"],
                "change": ((data["current"] - data["prev_close"]) / data["prev_close"]) * 100,
                "rsi": rsi,
                "macd": macd,
                "signal": sig,
                "macd_cross": cross,
                "gap": gap,
                "volume": data["volume"],
                "signals": signals,
                "details": details, # 추가된 상세 설명 데이터
                "recommendation": recommendation,
                "recommendation_color": rec_color,
            }
        except Exception as e:
            print(f"[ERROR] 분석 실패: {e}")
            return None
