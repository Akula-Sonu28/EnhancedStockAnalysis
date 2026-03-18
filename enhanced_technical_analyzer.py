#!/usr/bin/env python3
"""
Enhanced Technical Analyzer with Short-term Pattern Recognition
Focus: Days to 3 months analysis with pattern detection
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

def get_short_term_technical_analysis(symbol, period_days=90, bundle=None):
    """
    Comprehensive short-term technical analysis (1 day to 3 months)
    If *bundle* (StockDataBundle) is supplied, reuse its pre-fetched hist
    to avoid a duplicate yfinance API call.
    """
    try:
        if bundle is not None:
            hist = bundle.hist_6mo
        else:
            ticker_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="6mo", interval="1d")
        
        if hist.empty or len(hist) < 20:
            print(f"   ⚠️  Insufficient data for {symbol}")
            return None
        
        # Focus on last 3 months for analysis
        recent_data = hist.tail(period_days) if len(hist) > period_days else hist
        
        print(f"   📊 Analyzing {len(recent_data)} days of data")
        
        # Initialize analysis results
        analysis = {
            'symbol': symbol,
            'analysis_period_days': len(recent_data),
            'data_start_date': recent_data.index[0].strftime('%Y-%m-%d'),
            'data_end_date': recent_data.index[-1].strftime('%Y-%m-%d')
        }
        
        # 1. PRICE ACTION ANALYSIS
        analysis.update(analyze_price_action(recent_data))
        
        # 2. SHORT-TERM MOMENTUM INDICATORS
        analysis.update(calculate_short_term_indicators(recent_data))
        
        # 3. CANDLESTICK PATTERNS
        analysis.update(detect_candlestick_patterns(recent_data))
        
        # 4. CHART PATTERNS
        analysis.update(detect_chart_patterns(recent_data))
        
        # 5. VOLUME PATTERNS
        analysis.update(analyze_volume_patterns(recent_data))
        
        # 6. SUPPORT AND RESISTANCE LEVELS
        analysis.update(find_support_resistance_levels(recent_data))
        
        # 7. SHORT-TERM TREND ANALYSIS
        analysis.update(analyze_short_term_trends(recent_data))
        
        # 8. BREAKOUT AND BREAKDOWN SIGNALS
        analysis.update(detect_breakout_signals(recent_data))
        
        # 9. ICHIMOKU CLOUD
        analysis.update(calculate_ichimoku(recent_data))
        
        # 10. FIBONACCI RETRACEMENT LEVELS
        analysis.update(calculate_fibonacci_levels(recent_data))
        
        # 11. BOLLINGER BANDS
        analysis.update(calculate_bollinger_bands(recent_data))
        
        # 12. OVERALL SHORT-TERM SCORE
        analysis['short_term_score'] = calculate_short_term_score(analysis)
        analysis['short_term_signal'] = get_short_term_signal(analysis['short_term_score'])
        
        return analysis
        
    except Exception as e:
        print(f"   ❌ Technical analysis failed for {symbol}: {e}")
        return None

def analyze_price_action(df):
    """Analyze recent price action and volatility"""
    current_price = df['Close'].iloc[-1]
    
    # Price changes over different periods
    def _pchg(series, offset):
        if len(series) <= offset: return 0
        d = series.iloc[-1 - offset]
        return ((series.iloc[-1] / d) - 1) * 100 if d != 0 else 0
    price_analysis = {
        'current_price': current_price,
        'price_change_1d': _pchg(df['Close'], 1),
        'price_change_5d': _pchg(df['Close'], 5),
        'price_change_10d': _pchg(df['Close'], 10),
        'price_change_20d': _pchg(df['Close'], 20),
        'price_change_30d': _pchg(df['Close'], 30),
        'price_change_60d': _pchg(df['Close'], 60),
    }
    
    # Volatility measures
    returns = df['Close'].pct_change().dropna()
    def _vol(r, n):
        v = r.tail(n).std() * 100 * (n**0.5) if len(r) >= n else 0.0
        return v if not (isinstance(v, float) and np.isnan(v)) else 0.0
    price_analysis.update({
        'volatility_5d': _vol(returns, 5),
        'volatility_10d': _vol(returns, 10),
        'volatility_20d': _vol(returns, 20),
        'avg_daily_range': (lambda _v: 0.0 if pd.isna(_v) else float(_v))(((df['High'] - df['Low']) / df['Close'].replace(0, np.nan) * 100).tail(20).mean()),
    })
    
    # Price position relative to recent ranges
    recent_high = df['High'].tail(20).max()
    recent_low = df['Low'].tail(20).min()
    _denom = recent_high - recent_low
    price_analysis['price_position_20d'] = ((current_price - recent_low) / _denom * 100) if _denom > 0 else 50.0

    # Corporate action detection: flag extreme single-day moves (possible split/bonus)
    _daily_rets = df['Close'].pct_change().tail(5)
    _max_drop = float(_daily_rets.min()) if not _daily_rets.empty else 0.0
    _max_jump = float(_daily_rets.max()) if not _daily_rets.empty else 0.0
    if pd.isna(_max_drop): _max_drop = 0.0
    if pd.isna(_max_jump): _max_jump = 0.0
    price_analysis['corporate_action_warning'] = (_max_drop < -0.40 or _max_jump > 0.60)
    if price_analysis['corporate_action_warning']:
        price_analysis['corporate_action_detail'] = f"Extreme move: {_max_drop*100:.1f}% to {_max_jump*100:.1f}%"
        logging.warning(f"Possible corporate action: extreme daily move ({_max_drop*100:.1f}% to {_max_jump*100:.1f}%)")

    return price_analysis

def calculate_short_term_indicators(df):
    """Calculate short-term momentum and trend indicators"""
    indicators = {}
    
    # RSI (14-day and 7-day for short-term)
    def calculate_rsi(prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        all_gains = (loss == 0) & (gain > 0)
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.where(~all_gains, 100.0).fillna(50.0)
        return rsi
    
    _rsi14 = calculate_rsi(df['Close'], 14).iloc[-1]
    indicators['rsi_14'] = 50.0 if (np.isnan(_rsi14) or _rsi14 == 0.0) else _rsi14
    _rsi7 = calculate_rsi(df['Close'], 7).iloc[-1]
    indicators['rsi_7'] = 50.0 if (np.isnan(_rsi7) or _rsi7 == 0.0) else _rsi7
    
    # MACD for short-term signals
    ema_12 = df['Close'].ewm(span=12).mean()
    ema_26 = df['Close'].ewm(span=26).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9).mean()
    histogram = macd - signal
    
    _macd_val = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0.0
    _sig_val = signal.iloc[-1] if not pd.isna(signal.iloc[-1]) else 0.0
    _hist_val = histogram.iloc[-1] if not pd.isna(histogram.iloc[-1]) else 0.0
    _macd_cross = 'none'
    if len(macd) >= 2 and not any(pd.isna(v) for v in [macd.iloc[-1], macd.iloc[-2], signal.iloc[-1], signal.iloc[-2]]):
        if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
            _macd_cross = 'bullish'
        elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
            _macd_cross = 'bearish'
    indicators.update({
        'macd': _macd_val,
        'macd_signal': _sig_val,
        'macd_histogram': _hist_val,
        'macd_crossover': _macd_cross,
    })
    
    # Moving averages for short-term trend (NaN-safe: fall back to current price)
    _cur = float(df['Close'].iloc[-1])
    def _safe_ma(series):
        v = series.iloc[-1]
        return _cur if pd.isna(v) else float(v)
    indicators.update({
        'sma_5': _safe_ma(df['Close'].rolling(5).mean()),
        'sma_10': _safe_ma(df['Close'].rolling(10).mean()),
        'sma_20': _safe_ma(df['Close'].rolling(20).mean()),
        'ema_5': _safe_ma(df['Close'].ewm(span=5).mean()),
        'ema_10': _safe_ma(df['Close'].ewm(span=10).mean()),
        'ema_20': _safe_ma(df['Close'].ewm(span=20).mean()),
    })
    
    # Stochastic oscillator
    low_14 = df['Low'].rolling(14).min()
    high_14 = df['High'].rolling(14).max()
    _stoch_denom = (high_14 - low_14).replace(0, np.nan)
    k_percent = 100 * ((df['Close'] - low_14) / _stoch_denom)
    _sk = k_percent.rolling(3).mean().iloc[-1]
    _sd = k_percent.rolling(3).mean().rolling(3).mean().iloc[-1]
    indicators['stoch_k'] = _sk if not (np.isnan(_sk) if isinstance(_sk, float) else False) else 50.0
    indicators['stoch_d'] = _sd if not (np.isnan(_sd) if isinstance(_sd, float) else False) else 50.0
    
    return indicators

def detect_candlestick_patterns(df):
    """Detect common candlestick patterns"""
    patterns = {
        'candlestick_patterns': [],
        'pattern_strength': 0
    }
    
    if len(df) < 5:
        return patterns
    
    # Get last 5 candles for pattern detection
    recent = df.tail(5)
    
    for i in range(len(recent)):
        candle = recent.iloc[i]
        
        # Calculate candle properties
        body = abs(candle['Close'] - candle['Open'])
        upper_shadow = candle['High'] - max(candle['Close'], candle['Open'])
        lower_shadow = min(candle['Close'], candle['Open']) - candle['Low']
        total_range = candle['High'] - candle['Low']
        
        # Pattern detection
        if total_range > 0:
            body_ratio = body / total_range
            upper_ratio = upper_shadow / total_range
            lower_ratio = lower_shadow / total_range
            
            # Doji pattern
            if body_ratio < 0.1:
                patterns['candlestick_patterns'].append(f"Doji (Day {i+1})")
                patterns['pattern_strength'] += 20
            
            # Hammer/Hanging Man
            elif lower_ratio > 0.6 and upper_ratio < 0.1:
                if candle['Close'] > candle['Open']:
                    patterns['candlestick_patterns'].append(f"Hammer (Day {i+1})")
                    patterns['pattern_strength'] += 30
                else:
                    patterns['candlestick_patterns'].append(f"Hanging Man (Day {i+1})")
                    patterns['pattern_strength'] -= 20
            
            # Shooting Star/Inverted Hammer
            elif upper_ratio > 0.6 and lower_ratio < 0.1:
                if candle['Close'] < candle['Open']:
                    patterns['candlestick_patterns'].append(f"Shooting Star (Day {i+1})")
                    patterns['pattern_strength'] -= 30
                else:
                    patterns['candlestick_patterns'].append(f"Inverted Hammer (Day {i+1})")
                    patterns['pattern_strength'] += 20
            
            # Strong bullish/bearish candles
            elif body_ratio > 0.7:
                if candle['Close'] > candle['Open']:
                    patterns['candlestick_patterns'].append(f"Strong Bullish (Day {i+1})")
                    patterns['pattern_strength'] += 15
                else:
                    patterns['candlestick_patterns'].append(f"Strong Bearish (Day {i+1})")
                    patterns['pattern_strength'] -= 15
    
    # Multi-candle patterns
    if len(recent) >= 3:
        closes = recent['Close'].values
        if all(closes[i] > closes[i-1] for i in range(1, len(closes))):
            patterns['candlestick_patterns'].append("Three Rising Candles")
            patterns['pattern_strength'] += 25
        elif all(closes[i] < closes[i-1] for i in range(1, len(closes))):
            patterns['candlestick_patterns'].append("Three Falling Candles")
            patterns['pattern_strength'] -= 25

    # --- Engulfing patterns (2 candles) ---
    if len(recent) >= 2:
        prev = recent.iloc[-2]
        curr = recent.iloc[-1]
        prev_body_top = max(prev['Open'], prev['Close'])
        prev_body_bot = min(prev['Open'], prev['Close'])
        curr_body_top = max(curr['Open'], curr['Close'])
        curr_body_bot = min(curr['Open'], curr['Close'])
        prev_bearish = prev['Close'] < prev['Open']
        curr_bullish = curr['Close'] > curr['Open']

        if prev_bearish and curr_bullish and curr_body_bot <= prev_body_bot and curr_body_top >= prev_body_top:
            patterns['candlestick_patterns'].append("Bullish Engulfing")
            patterns['pattern_strength'] += 30

        prev_bullish = prev['Close'] > prev['Open']
        curr_bearish = curr['Close'] < curr['Open']
        if prev_bullish and curr_bearish and curr_body_bot <= prev_body_bot and curr_body_top >= prev_body_top:
            patterns['candlestick_patterns'].append("Bearish Engulfing")
            patterns['pattern_strength'] -= 30

    # --- Morning Star / Evening Star (3 candles) ---
    if len(recent) >= 3:
        c1 = recent.iloc[-3]
        c2 = recent.iloc[-2]
        c3 = recent.iloc[-1]
        c1_body = abs(c1['Close'] - c1['Open'])
        c2_body = abs(c2['Close'] - c2['Open'])
        c3_body = abs(c3['Close'] - c3['Open'])
        c1_range = c1['High'] - c1['Low'] if c1['High'] != c1['Low'] else 1
        c2_ratio = c2_body / c1_range if c1_range > 0 else 0
        c1_mid = (c1['Open'] + c1['Close']) / 2

        # Morning Star: bearish, small-body, bullish closing above c1 midpoint
        if c1['Close'] < c1['Open'] and c2_ratio < 0.3 and c3['Close'] > c3['Open'] and c3['Close'] > c1_mid:
            patterns['candlestick_patterns'].append("Morning Star")
            patterns['pattern_strength'] += 35

        # Evening Star: bullish, small-body, bearish closing below c1 midpoint
        if c1['Close'] > c1['Open'] and c2_ratio < 0.3 and c3['Close'] < c3['Open'] and c3['Close'] < c1_mid:
            patterns['candlestick_patterns'].append("Evening Star")
            patterns['pattern_strength'] -= 35

    return patterns

def detect_chart_patterns(df):
    """Detect chart patterns like triangles, flags, etc."""
    patterns = {
        'chart_patterns': [],
        'pattern_signals': []
    }
    
    if len(df) < 20:
        return patterns
    
    # Get recent data for pattern analysis
    recent = df.tail(20)
    highs = recent['High']
    lows = recent['Low']
    closes = recent['Close']
    
    # Simple trend channel detection
    high_trend = np.polyfit(range(len(highs)), highs, 1)[0]
    low_trend = np.polyfit(range(len(lows)), lows, 1)[0]
    
    # Ascending/Descending triangles
    if high_trend > 0.1 and abs(low_trend) < 0.1:
        patterns['chart_patterns'].append("Ascending Triangle Formation")
        patterns['pattern_signals'].append("Bullish breakout potential")
    elif low_trend < -0.1 and abs(high_trend) < 0.1:
        patterns['chart_patterns'].append("Descending Triangle Formation")
        patterns['pattern_signals'].append("Bearish breakdown potential")
    elif abs(high_trend) < 0.1 and abs(low_trend) < 0.1:
        patterns['chart_patterns'].append("Horizontal Range/Rectangle")
        patterns['pattern_signals'].append("Consolidation phase")
    
    # Flag pattern detection (after strong move)
    _d11 = closes.iloc[-11] if len(closes) > 10 else 0
    price_change_10d = ((closes.iloc[-1] / _d11) - 1) * 100 if (len(closes) > 10 and _d11 != 0) else 0
    
    if abs(price_change_10d) > 5:  # Strong prior move
        _5d_mean = closes.tail(5).mean()
        recent_5d_volatility = (closes.tail(5).std() / _5d_mean * 100) if _5d_mean != 0 else 0
        if recent_5d_volatility < 2:  # Low volatility consolidation
            if price_change_10d > 0:
                patterns['chart_patterns'].append("Bull Flag Formation")
                patterns['pattern_signals'].append("Continuation pattern - bullish")
            else:
                patterns['chart_patterns'].append("Bear Flag Formation")
                patterns['pattern_signals'].append("Continuation pattern - bearish")
    
    return patterns

def analyze_volume_patterns(df):
    """Analyze volume patterns and price-volume relationships"""
    volume_analysis = {}
    
    if 'Volume' not in df.columns:
        return {'volume_analysis': 'Volume data not available'}
    
    volume = df['Volume']
    prices = df['Close']
    
    # Volume trend
    volume_sma_10 = volume.rolling(10).mean()
    current_volume = volume.iloc[-1]
    avg_volume = volume_sma_10.iloc[-1]
    smoothed_volume = volume.tail(3).mean()

    raw_ratio = current_volume / avg_volume if avg_volume > 0 else 0
    smoothed_ratio = smoothed_volume / avg_volume if avg_volume > 0 else 0

    volume_analysis.update({
        'current_volume': current_volume,
        'avg_volume_10d': avg_volume,
        'volume_ratio': smoothed_ratio,
        'volume_ratio_raw': raw_ratio,
        'volume_trend': 'High' if smoothed_volume > avg_volume * 1.5 else 'Normal' if smoothed_volume > avg_volume * 0.8 else 'Low'
    })
    
    # Price-Volume correlation
    recent_price_change = prices.pct_change().tail(10)
    recent_volume_change = volume.pct_change().tail(10)
    
    correlation = recent_price_change.corr(recent_volume_change)
    volume_analysis['price_volume_correlation'] = 0.0 if pd.isna(correlation) else float(correlation)
    
    # Volume breakout signals
    volume_breakouts = []
    for i in range(5, len(volume)):
        if volume.iloc[i] > volume.iloc[i-5:i].max() * 2:
            _prev = prices.iloc[i-1]
            if pd.isna(_prev) or _prev == 0:
                continue
            price_change = ((prices.iloc[i] / _prev) - 1) * 100
            volume_breakouts.append(f"Volume spike: {price_change:.1f}% price change")
    
    volume_analysis['recent_volume_breakouts'] = volume_breakouts[-3:] if volume_breakouts else []
    
    return volume_analysis

def find_support_resistance_levels(df):
    """Find recent support and resistance levels"""
    levels = {
        'support_levels': [],
        'resistance_levels': [],
        'key_levels': []
    }
    
    if len(df) < 10:
        return levels
    
    highs = df['High']
    lows = df['Low']
    current_price = df['Close'].iloc[-1]
    
    # Find pivot highs and lows
    window = 5
    
    # Support levels (pivot lows)
    for i in range(window, len(lows) - window):
        if lows.iloc[i] == lows.iloc[i-window:i+window+1].min():
            support_level = lows.iloc[i]
            if support_level < current_price * 1.05:  # Within 5% of current price
                levels['support_levels'].append(round(support_level, 2))
    
    # Resistance levels (pivot highs)
    for i in range(window, len(highs) - window):
        if highs.iloc[i] == highs.iloc[i-window:i+window+1].max():
            resistance_level = highs.iloc[i]
            if resistance_level > current_price * 0.95:  # Within 5% of current price
                levels['resistance_levels'].append(round(resistance_level, 2))
    
    # Remove duplicates and sort - handle edge cases with empty lists
    support_set = list(set(levels['support_levels']))
    resistance_set = list(set(levels['resistance_levels']))
    
    # Safely take last 3 support levels (if available)
    if len(support_set) > 0:
        levels['support_levels'] = sorted(support_set)[-min(3, len(support_set)):]
    else:
        levels['support_levels'] = []
        
    # Safely take first 3 resistance levels (if available)
    if len(resistance_set) > 0:
        levels['resistance_levels'] = sorted(resistance_set)[:min(3, len(resistance_set))]
    else:
        levels['resistance_levels'] = []
    
    # ATR-based fallback when pivot-based levels are empty
    if not levels['support_levels'] or not levels['resistance_levels']:
        try:
            tr = pd.concat([
                highs - lows,
                (highs - df['Close'].shift(1)).abs(),
                (lows - df['Close'].shift(1)).abs()
            ], axis=1).max(axis=1)
            atr_14 = tr.rolling(14).mean().iloc[-1] if len(tr) >= 14 else tr.mean()
            if not pd.isna(atr_14) and atr_14 > 0:
                if not levels['support_levels']:
                    levels['support_levels'] = [
                        round(current_price - atr_14 * m, 2)
                        for m in [1.0, 1.5, 2.0]
                    ]
                if not levels['resistance_levels']:
                    levels['resistance_levels'] = [
                        round(current_price + atr_14 * m, 2)
                        for m in [1.0, 1.5, 2.0]
                    ]
        except Exception:
            pass
    
    # Key psychological levels (round numbers)
    price_range = [current_price * 0.9, current_price * 1.1]
    _pr_start = int(price_range[0]) if price_range[0] > 0 else 0
    _pr_end = int(price_range[1]) + 100 if price_range[1] > 0 else 100
    for level in range(_pr_start, _pr_end, 50):
        if price_range[0] <= level <= price_range[1]:
            levels['key_levels'].append(level)
    
    return levels

def analyze_short_term_trends(df):
    """Analyze short-term trend strength and direction"""
    trend_analysis = {}
    
    if len(df) < 10:
        return trend_analysis
    
    prices = df['Close']
    
    # Trend strength over different periods
    trends = {}
    for period in [5, 10, 20]:
        if len(prices) >= period:
            start_price = prices.iloc[-period]
            end_price = prices.iloc[-1]
            trend_strength = ((end_price / start_price) - 1) * 100 if start_price != 0 else 0
            trends[f'trend_{period}d'] = trend_strength
    
    trend_analysis.update(trends)
    
    # Moving average alignment (NaN-safe: fall back to current price)
    if len(df) >= 20:
        current = float(prices.iloc[-1])
        _ma = lambda n: float(v) if not pd.isna(v := prices.rolling(n).mean().iloc[-1]) else current
        sma_5 = _ma(5)
        sma_10 = _ma(10)
        sma_20 = _ma(20)
        
        if current > sma_5 > sma_10 > sma_20:
            trend_analysis['ma_alignment'] = 'Strong Uptrend'
        elif current < sma_5 < sma_10 < sma_20:
            trend_analysis['ma_alignment'] = 'Strong Downtrend'
        elif current > sma_5 > sma_10:
            trend_analysis['ma_alignment'] = 'Short-term Uptrend'
        elif current < sma_5 < sma_10:
            trend_analysis['ma_alignment'] = 'Short-term Downtrend'
        else:
            trend_analysis['ma_alignment'] = 'Sideways/Mixed'
    
    return trend_analysis

def detect_breakout_signals(df):
    """Detect potential breakout and breakdown signals"""
    signals = {
        'breakout_signals': [],
        'breakdown_signals': [],
        'signal_strength': 0
    }
    
    if len(df) < 20:
        return signals
    
    current_price = df['Close'].iloc[-1]
    recent_volume = df['Volume'].iloc[-1] if 'Volume' in df.columns else 0
    avg_volume = df['Volume'].rolling(10).mean().iloc[-1] if 'Volume' in df.columns else 1
    
    # 20-day high/low breakout
    high_20 = df['High'].tail(20).max()
    low_20 = df['Low'].tail(20).min()
    
    if current_price > high_20 * 0.999:  # Near or above 20-day high
        signals['breakout_signals'].append("20-day high breakout")
        if recent_volume > avg_volume * 1.5:
            signals['breakout_signals'].append("High volume breakout")
            signals['signal_strength'] += 30
        else:
            signals['signal_strength'] += 15
    
    if current_price < low_20 * 1.001:  # Near or below 20-day low
        signals['breakdown_signals'].append("20-day low breakdown")
        if recent_volume > avg_volume * 1.5:
            signals['breakdown_signals'].append("High volume breakdown")
            signals['signal_strength'] -= 30
        else:
            signals['signal_strength'] -= 15
    
    # Consolidation breakout
    recent_range = df['High'].tail(10).max() - df['Low'].tail(10).min()
    price_range = df['High'].tail(20).max() - df['Low'].tail(20).min()
    
    if recent_range < price_range * 0.5:  # Consolidation
        if current_price > df['High'].tail(10).max():
            signals['breakout_signals'].append("Consolidation breakout")
            signals['signal_strength'] += 25
        elif current_price < df['Low'].tail(10).min():
            signals['breakdown_signals'].append("Consolidation breakdown")
            signals['signal_strength'] -= 25
    
    return signals

def calculate_short_term_score(analysis):
    """Calculate overall short-term technical score (0-100)"""
    score = 50  # Start with neutral

    # Price momentum (max +-15 pts = 30% of the 50-pt half-range)
    momentum_raw = 0
    if 'price_change_5d' in analysis:
        momentum_raw += min(max(analysis['price_change_5d'] * 2, -30), 30)
    if 'price_change_20d' in analysis:
        momentum_raw += min(max(analysis['price_change_20d'], -20), 20)
    score += max(-15, min(15, momentum_raw * 0.3))

    # Technical indicators (max +-12.5 pts = 25% of 50-pt half-range)
    tech_raw = 0
    if 'rsi_14' in analysis:
        rsi = analysis['rsi_14']
        if 30 <= rsi <= 70:
            tech_raw += 5
        elif rsi < 30:
            tech_raw += 15
        elif rsi > 70:
            tech_raw -= 10
    if 'macd_crossover' in analysis:
        if analysis['macd_crossover'] == 'bullish':
            tech_raw += 10
        elif analysis['macd_crossover'] == 'bearish':
            tech_raw -= 10
    score += max(-12.5, min(12.5, tech_raw))

    # Pattern strength (max +-10 pts = 20% of 50-pt half-range)
    if 'pattern_strength' in analysis:
        score += max(-10, min(10, analysis['pattern_strength'] * 0.2))

    # Signal strength (max +-7.5 pts = 15% of 50-pt half-range)
    if 'signal_strength' in analysis:
        score += max(-7.5, min(7.5, analysis['signal_strength'] * 0.15))

    # Trend alignment (max +-5 pts = 10% of 50-pt half-range)
    if 'ma_alignment' in analysis:
        alignment = str(analysis['ma_alignment'] or '')
        if 'Strong Uptrend' in alignment:
            score += 5
        elif 'Strong Downtrend' in alignment:
            score -= 5
        elif 'Short-term Uptrend' in alignment:
            score += 2.5
        elif 'Short-term Downtrend' in alignment:
            score -= 2.5

    if pd.isna(score) or (isinstance(score, (float, np.floating)) and np.isnan(score)):
        score = 50
    return max(0, min(100, score))

def get_short_term_signal(score):
    """Get trading signal based on short-term score"""
    if score >= 70:
        return "🟢 STRONG BUY"
    elif score >= 60:
        return "🟢 BUY"
    elif score >= 55:
        return "🟡 WEAK BUY"
    elif score >= 45:
        return "🟡 HOLD"
    elif score >= 40:
        return "🟠 WEAK SELL"
    elif score >= 30:
        return "🔴 SELL"
    else:
        return "🔴 STRONG SELL"

def display_short_term_analysis(analysis):
    """Display comprehensive short-term technical analysis"""
    if not analysis:
        print("❌ No analysis data available")
        return
    
    symbol = analysis.get('symbol', 'UNKNOWN')
    period = analysis.get('analysis_period_days', 0)
    
    print(f"\n📈 SHORT-TERM TECHNICAL ANALYSIS FOR {symbol}")
    print(f"📅 Analysis Period: {period} days ({analysis.get('data_start_date')} to {analysis.get('data_end_date')})")
    print("=" * 70)
    
    # Price Action
    print("\n📊 PRICE ACTION & MOMENTUM:")
    print("-" * 40)
    price_metrics = [
        ('Current Price', 'current_price', '₹'),
        ('1 Day Change', 'price_change_1d', '%'),
        ('5 Day Change', 'price_change_5d', '%'),
        ('10 Day Change', 'price_change_10d', '%'),
        ('20 Day Change', 'price_change_20d', '%'),
        ('30 Day Change', 'price_change_30d', '%'),
        ('20D Position', 'price_position_20d', '%'),
        ('Volatility (20D)', 'volatility_20d', '%')
    ]
    
    for name, key, unit in price_metrics:
        if key in analysis:
            value = analysis[key]
            if unit == '₹':
                print(f"   {name:<18}: ₹{value:,.2f}")
            elif unit == '%':
                color = "📈" if value > 0 else "📉" if value < 0 else "➡️"
                print(f"   {name:<18}: {color} {value:+.2f}%")
    
    # Technical Indicators
    print("\n🔍 TECHNICAL INDICATORS:")
    print("-" * 40)
    tech_metrics = [
        ('RSI (14)', 'rsi_14'),
        ('RSI (7)', 'rsi_7'),
        ('MACD', 'macd'),
        ('MACD Signal', 'macd_signal'),
        ('MACD Crossover', 'macd_crossover'),
        ('Stochastic %K', 'stoch_k'),
        ('SMA 5', 'sma_5'),
        ('SMA 10', 'sma_10'),
        ('SMA 20', 'sma_20'),
        ('MA Alignment', 'ma_alignment')
    ]
    
    for name, key in tech_metrics:
        if key in analysis:
            value = analysis[key]
            if isinstance(value, (int, float)):
                print(f"   {name:<18}: {value:.2f}")
            else:
                print(f"   {name:<18}: {value}")
    
    # Patterns
    print("\n🕯️ CANDLESTICK PATTERNS:")
    print("-" * 40)
    patterns = analysis.get('candlestick_patterns', [])
    if patterns:
        for pattern in patterns:
            print(f"   • {pattern}")
        print(f"   Pattern Strength  : {analysis.get('pattern_strength', 0)}")
    else:
        print("   No significant candlestick patterns detected")
    
    print("\n📈 CHART PATTERNS:")
    print("-" * 40)
    chart_patterns = analysis.get('chart_patterns', [])
    pattern_signals = analysis.get('pattern_signals', [])
    if chart_patterns:
        for i, pattern in enumerate(chart_patterns):
            signal = pattern_signals[i] if i < len(pattern_signals) else ""
            print(f"   • {pattern}")
            if signal:
                print(f"     → {signal}")
    else:
        print("   No chart patterns detected")
    
    # Support/Resistance
    print("\n🎯 SUPPORT & RESISTANCE:")
    print("-" * 40)
    supports = analysis.get('support_levels', [])
    resistances = analysis.get('resistance_levels', [])
    
    if supports:
        print(f"   Support Levels    : {', '.join(f'₹{s}' for s in supports)}")
    if resistances:
        print(f"   Resistance Levels : {', '.join(f'₹{r}' for r in resistances)}")
    
    # Breakout Signals
    print("\n🚀 BREAKOUT SIGNALS:")
    print("-" * 40)
    breakouts = analysis.get('breakout_signals', [])
    breakdowns = analysis.get('breakdown_signals', [])
    
    if breakouts:
        for signal in breakouts:
            print(f"   🟢 {signal}")
    if breakdowns:
        for signal in breakdowns:
            print(f"   🔴 {signal}")
    
    if not breakouts and not breakdowns:
        print("   No significant breakout signals")
    
    # Volume Analysis
    print("\n📊 VOLUME ANALYSIS:")
    print("-" * 40)
    if 'volume_trend' in analysis:
        print(f"   Volume Trend      : {analysis['volume_trend']}")
        if 'volume_ratio' in analysis:
            print(f"   Volume vs Avg     : {analysis['volume_ratio']:.2f}x")
    
    volume_breakouts = analysis.get('recent_volume_breakouts', [])
    if volume_breakouts:
        for breakout in volume_breakouts:
            print(f"   • {breakout}")
    
    # Final Score and Signal
    print(f"\n🎯 SHORT-TERM ANALYSIS SUMMARY:")
    print("=" * 40)
    score = analysis.get('short_term_score', 0)
    signal = analysis.get('short_term_signal', 'N/A')
    print(f"   Short-term Score  : {score:.1f}/100")
    print(f"   Trading Signal    : {signal}")
    
    # Trend analysis
    for period in [5, 10, 20]:
        trend_key = f'trend_{period}d'
        if trend_key in analysis:
            trend = analysis[trend_key]
            emoji = "📈" if trend > 0 else "📉" if trend < 0 else "➡️"
            print(f"   {period}D Trend       : {emoji} {trend:+.2f}%")

def calculate_ichimoku(df):
    """Calculate Ichimoku Cloud components."""
    result = {}
    try:
        high = df['High']
        low = df['Low']
        close = df['Close']

        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
        chikou = close.shift(-26)

        cur = close.iloc[-1]
        t = tenkan.iloc[-1] if not pd.isna(tenkan.iloc[-1]) else cur
        k = kijun.iloc[-1] if not pd.isna(kijun.iloc[-1]) else cur
        sa = senkou_a.iloc[-1] if len(senkou_a.dropna()) > 0 and not pd.isna(senkou_a.dropna().iloc[-1]) else cur
        sb = senkou_b.iloc[-1] if len(senkou_b.dropna()) > 0 and not pd.isna(senkou_b.dropna().iloc[-1]) else cur

        cloud_top = max(sa, sb)
        cloud_bottom = min(sa, sb)

        if cur > cloud_top:
            cloud_signal = 'ABOVE_CLOUD'
        elif cur < cloud_bottom:
            cloud_signal = 'BELOW_CLOUD'
        else:
            cloud_signal = 'INSIDE_CLOUD'

        tk_cross = 'BULLISH' if t > k else ('BEARISH' if t < k else 'NEUTRAL')

        result.update({
            'ichimoku_tenkan': round(t, 2),
            'ichimoku_kijun': round(k, 2),
            'ichimoku_senkou_a': round(sa, 2),
            'ichimoku_senkou_b': round(sb, 2),
            'ichimoku_cloud_signal': cloud_signal,
            'ichimoku_tk_cross': tk_cross,
        })
    except Exception:
        result.update({
            'ichimoku_tenkan': 0, 'ichimoku_kijun': 0,
            'ichimoku_senkou_a': 0, 'ichimoku_senkou_b': 0,
            'ichimoku_cloud_signal': 'N/A', 'ichimoku_tk_cross': 'N/A',
        })
    return result


def calculate_fibonacci_levels(df):
    """Calculate Fibonacci retracement levels from recent swing high/low."""
    result = {}
    try:
        close = df['Close']
        swing_high = df['High'].max()
        swing_low = df['Low'].min()
        diff = swing_high - swing_low

        levels = {
            'fib_0': swing_high,
            'fib_236': swing_high - diff * 0.236,
            'fib_382': swing_high - diff * 0.382,
            'fib_500': swing_high - diff * 0.500,
            'fib_618': swing_high - diff * 0.618,
            'fib_786': swing_high - diff * 0.786,
            'fib_100': swing_low,
        }
        for k, v in levels.items():
            result[k] = round(v, 2)

        cur = close.iloc[-1]
        nearest_level = min(levels.items(), key=lambda x: abs(x[1] - cur))
        result['fib_nearest_level'] = nearest_level[0]
        result['fib_nearest_price'] = nearest_level[1]

        pct_from_high = ((swing_high - cur) / diff * 100) if diff > 0 else 0
        result['fib_retracement_pct'] = round(pct_from_high, 2)
    except Exception:
        result.update({
            'fib_0': 0, 'fib_236': 0, 'fib_382': 0, 'fib_500': 0,
            'fib_618': 0, 'fib_786': 0, 'fib_100': 0,
            'fib_nearest_level': 'N/A', 'fib_nearest_price': 0,
            'fib_retracement_pct': 0,
        })
    return result


def calculate_bollinger_bands(df, window=20, num_std=2):
    """Calculate Bollinger Bands with squeeze detection."""
    result = {}
    try:
        close = df['Close']
        sma = close.rolling(window).mean()
        std = close.rolling(window).std()

        upper = sma + num_std * std
        lower = sma - num_std * std

        cur = close.iloc[-1]
        u = upper.iloc[-1]
        l = lower.iloc[-1]
        m = sma.iloc[-1]

        if any(pd.isna(v) for v in (u, l, m)):
            raise ValueError("Insufficient data for Bollinger Bands")

        width = (u - l) / m * 100 if m > 0 else 0
        pct_b = (cur - l) / (u - l) * 100 if (u - l) > 0 else 50

        avg_width = ((upper - lower) / sma * 100).rolling(50).mean()
        avg_w = avg_width.iloc[-1] if not pd.isna(avg_width.iloc[-1]) else width
        squeeze = width < avg_w * 0.75

        if cur > u:
            bb_signal = 'OVERBOUGHT'
        elif cur < l:
            bb_signal = 'OVERSOLD'
        elif squeeze:
            bb_signal = 'SQUEEZE'
        else:
            bb_signal = 'NEUTRAL'

        result.update({
            'bb_upper': round(u, 2),
            'bb_middle': round(m, 2),
            'bb_lower': round(l, 2),
            'bb_width': round(width, 2),
            'bb_pct_b': round(pct_b, 2),
            'bb_signal': bb_signal,
            'bb_squeeze': squeeze,
        })
    except Exception:
        result.update({
            'bb_upper': 0, 'bb_middle': 0, 'bb_lower': 0,
            'bb_width': 0, 'bb_pct_b': 50, 'bb_signal': 'N/A', 'bb_squeeze': False,
        })
    return result


if __name__ == "__main__":
    # Test the short-term technical analysis
    print("🔧 TESTING SHORT-TERM TECHNICAL ANALYSIS")
    print("=" * 60)
    
    symbol = "RELIANCE"
    print(f"📊 Analyzing {symbol} for short-term patterns...")
    
    analysis = get_short_term_technical_analysis(symbol, period_days=90)
    
    if analysis:
        display_short_term_analysis(analysis)
        print(f"\n✅ Short-term technical analysis complete for {symbol}!")
    else:
        print(f"\n❌ Failed to analyze {symbol}")
