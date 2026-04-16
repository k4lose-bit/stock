import pandas as pd

class TechnicalIndicators:
@staticmethod
def calculate_rsi(prices, period=14):
if len(prices) < period + 1:
return None
s = pd.Series(prices)
d = s.diff()
gain = (d.where(d > 0, 0)).rolling(window=period).mean()
loss = (-d.where(d < 0, 0)).rolling(window=period).mean()
loss_val = loss.iloc[-1]
if loss_val == 0:
return 100.0
rs = gain.iloc[-1] / loss_val
return float(100 - (100 / (1 + rs)))

@staticmethod
def calculate_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal:
        return None, None, None
    s = pd.Series(prices)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist.iloc[-1])

@staticmethod
def check_macd_crossover(prices):
    if len(prices) < 35:
        return None
    s = pd.Series(prices)
    ema_fast = s.ewm(span=12, adjust=False).mean()
    ema_slow = s.ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    macd_current = macd_line.iloc[-1]
    macd_prev = macd_line.iloc[-2]
    sig_current = signal_line.iloc[-1]
    sig_prev = signal_line.iloc[-2]

    if macd_prev <= sig_prev and macd_current > sig_current:
        return "골든크로스"
    if macd_prev >= sig_prev and macd_current < sig_current:
        return "데드크로스"
    return None
