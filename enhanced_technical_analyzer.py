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

def get_short_term_technical_analysis(symbol, period_days=90):
    """
    Comprehensive short-term technical analysis (1 day to 3 months)
    Focus on patterns, momentum, and short-term signals
    """
    try:
        # Add .NS suffix for NSE stocks if not present
        ticker_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
        
        # Get data for the specified period plus extra for calculations
        ticker = yf.Ticker(ticker_symbol)
        
        # Get detailed data for pattern analysis
        hist = ticker.history(period="6mo", interval="1d")  # 6 months for better pattern detection
        
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
        
        # 9. OVERALL SHORT-TERM SCORE
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
    price_analysis = {
        'current_price': current_price,
        'price_change_1d': ((df['Close'].iloc[-1] / df['Close'].iloc[-2]) - 1) * 100 if len(df) > 1 else 0,
        'price_change_5d': ((df['Close'].iloc[-1] / df['Close'].iloc[-6]) - 1) * 100 if len(df) > 5 else 0,
        'price_change_10d': ((df['Close'].iloc[-1] / df['Close'].iloc[-11]) - 1) * 100 if len(df) > 10 else 0,
        'price_change_20d': ((df['Close'].iloc[-1] / df['Close'].iloc[-21]) - 1) * 100 if len(df) > 20 else 0,
        'price_change_30d': ((df['Close'].iloc[-1] / df['Close'].iloc[-31]) - 1) * 100 if len(df) > 30 else 0,
        'price_change_60d': ((df['Close'].iloc[-1] / df['Close'].iloc[-61]) - 1) * 100 if len(df) > 60 else 0,
    }
    
    # Volatility measures
    returns = df['Close'].pct_change().dropna()
    price_analysis.update({
        'volatility_5d': returns.tail(5).std() * 100 * (5**0.5),
        'volatility_10d': returns.tail(10).std() * 100 * (10**0.5),
        'volatility_20d': returns.tail(20).std() * 100 * (20**0.5),
        'avg_daily_range': ((df['High'] - df['Low']) / df['Close'] * 100).tail(20).mean(),
    })
    
    # Price position relative to recent ranges
    recent_high = df['High'].tail(20).max()
    recent_low = df['Low'].tail(20).min()
    price_analysis['price_position_20d'] = ((current_price - recent_low) / (recent_high - recent_low)) * 100
    
    return price_analysis

def calculate_short_term_indicators(df):
    """Calculate short-term momentum and trend indicators"""
    indicators = {}
    
    # RSI (14-day and 7-day for short-term)
    def calculate_rsi(prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    indicators['rsi_14'] = calculate_rsi(df['Close'], 14).iloc[-1]
    indicators['rsi_7'] = calculate_rsi(df['Close'], 7).iloc[-1]
    
    # MACD for short-term signals
    ema_12 = df['Close'].ewm(span=12).mean()
    ema_26 = df['Close'].ewm(span=26).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9).mean()
    histogram = macd - signal
    
    indicators.update({
        'macd': macd.iloc[-1],
        'macd_signal': signal.iloc[-1],
        'macd_histogram': histogram.iloc[-1],
        'macd_crossover': 'bullish' if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2] else 
                         'bearish' if macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2] else 'none'
    })
    
    # Moving averages for short-term trend
    indicators.update({
        'sma_5': df['Close'].rolling(5).mean().iloc[-1],
        'sma_10': df['Close'].rolling(10).mean().iloc[-1],
        'sma_20': df['Close'].rolling(20).mean().iloc[-1],
        'ema_5': df['Close'].ewm(span=5).mean().iloc[-1],
        'ema_10': df['Close'].ewm(span=10).mean().iloc[-1],
        'ema_20': df['Close'].ewm(span=20).mean().iloc[-1],
    })
    
    # Stochastic oscillator
    low_14 = df['Low'].rolling(14).min()
    high_14 = df['High'].rolling(14).max()
    k_percent = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
    indicators['stoch_k'] = k_percent.rolling(3).mean().iloc[-1]
    indicators['stoch_d'] = k_percent.rolling(3).mean().rolling(3).mean().iloc[-1]
    
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
        # Three consecutive higher/lower closes
        closes = recent['Close'].values
        if all(closes[i] > closes[i-1] for i in range(1, len(closes))):
            patterns['candlestick_patterns'].append("Three Rising Candles")
            patterns['pattern_strength'] += 25
        elif all(closes[i] < closes[i-1] for i in range(1, len(closes))):
            patterns['candlestick_patterns'].append("Three Falling Candles")
            patterns['pattern_strength'] -= 25
    
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
    price_change_10d = ((closes.iloc[-1] / closes.iloc[-11]) - 1) * 100 if len(closes) > 10 else 0
    
    if abs(price_change_10d) > 5:  # Strong prior move
        recent_5d_volatility = closes.tail(5).std() / closes.tail(5).mean() * 100
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
    
    volume_analysis.update({
        'current_volume': current_volume,
        'avg_volume_10d': avg_volume,
        'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
        'volume_trend': 'High' if current_volume > avg_volume * 1.5 else 'Normal' if current_volume > avg_volume * 0.8 else 'Low'
    })
    
    # Price-Volume correlation
    recent_price_change = prices.pct_change().tail(10)
    recent_volume_change = volume.pct_change().tail(10)
    
    correlation = recent_price_change.corr(recent_volume_change)
    volume_analysis['price_volume_correlation'] = correlation
    
    # Volume breakout signals
    volume_breakouts = []
    for i in range(5, len(volume)):
        if volume.iloc[i] > volume.iloc[i-5:i].max() * 2:
            price_change = ((prices.iloc[i] / prices.iloc[i-1]) - 1) * 100
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
    
    # Key psychological levels (round numbers)
    price_range = [current_price * 0.9, current_price * 1.1]
    for level in range(int(price_range[0]), int(price_range[1]) + 100, 50):
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
            trend_strength = ((end_price / start_price) - 1) * 100
            trends[f'trend_{period}d'] = trend_strength
    
    trend_analysis.update(trends)
    
    # Moving average alignment
    if len(df) >= 20:
        sma_5 = prices.rolling(5).mean().iloc[-1]
        sma_10 = prices.rolling(10).mean().iloc[-1]
        sma_20 = prices.rolling(20).mean().iloc[-1]
        current = prices.iloc[-1]
        
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
    
    # Price momentum (30% weight)
    momentum_score = 0
    if 'price_change_5d' in analysis:
        momentum_score += min(max(analysis['price_change_5d'] * 2, -30), 30)
    if 'price_change_20d' in analysis:
        momentum_score += min(max(analysis['price_change_20d'], -20), 20)
    
    score += momentum_score * 0.3
    
    # Technical indicators (25% weight)
    if 'rsi_14' in analysis:
        rsi = analysis['rsi_14']
        if 30 <= rsi <= 70:
            score += 5  # Neutral RSI is positive
        elif rsi < 30:
            score += 15  # Oversold - potential bounce
        elif rsi > 70:
            score -= 10  # Overbought
    
    if 'macd_crossover' in analysis:
        if analysis['macd_crossover'] == 'bullish':
            score += 10
        elif analysis['macd_crossover'] == 'bearish':
            score -= 10
    
    # Pattern strength (20% weight)
    if 'pattern_strength' in analysis:
        score += analysis['pattern_strength'] * 0.2
    
    # Signal strength (15% weight)
    if 'signal_strength' in analysis:
        score += analysis['signal_strength'] * 0.15
    
    # Trend alignment (10% weight)
    if 'ma_alignment' in analysis:
        alignment = analysis['ma_alignment']
        if 'Strong Uptrend' in alignment:
            score += 10
        elif 'Strong Downtrend' in alignment:
            score -= 10
        elif 'Short-term Uptrend' in alignment:
            score += 5
        elif 'Short-term Downtrend' in alignment:
            score -= 5
    
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
