from modules.indicators import TechnicalIndicators

class StockAnalyzer:
def init(self):
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
        recommendation = "관망"
        rec_color = "🟡"

        if rsi <= 30 and cross == "골든크로스":
            signals.append("⭐ 강력 매수 신호 (RSI 과매도 + 골든크로스)")
            recommendation = "적극 매수"
            rec_color = "🟢"
        elif rsi <= 30:
            signals.append("RSI 과매도 (반등 가능성)")
            recommendation = "매수 고려"
            rec_color = "🟢"
        elif cross == "골든크로스":
            signals.append("MACD 골든크로스 (상승 전환)")
            recommendation = "매수 고려"
            rec_color = "🟢"
        
        if rsi >= 70:
            signals.append("RSI 과매수 (조정 가능성)")
            recommendation = "매도 고려"
            rec_color = "🔴"
        if cross == "데드크로스":
            signals.append("MACD 데드크로스 (하락 전환)")
            recommendation = "매도 고려"
            rec_color = "🔴"

        if gap < -3:
            signals.append(f"갭 하락 {gap:.1f}%")
        if volume_surge:
            signals.append("거래량 급증 (최근 5일 평균 대비 2배↑)")

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
            "recommendation": recommendation,
            "recommendation_color": rec_color,
        }
    except Exception as e:
        print(f"[ERROR] 분석 실패: {e}")
        return None
