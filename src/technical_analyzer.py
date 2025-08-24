# Technical Analyzer: Calculate indicators and compute score
import numpy as np
import pandas as pd
import yfinance as yf
import logging
from config import TECHNICAL_WEIGHTS

def safe_float(val):
    """Convert pandas Series or scalar to float"""
    if isinstance(val, pd.Series):
        return float(val.iloc[0]) if not val.empty else None
    return float(val) if val is not None else None

def calculate_indicators(df):
    """
    Calculate comprehensive technical indicators for a stock DataFrame (OHLCV).
    Returns: dict of indicators with detailed technical analysis
    """
    try:
        indicators = {}
        
        # Current Price & Changes
        indicators['Close'] = df['Close'].iloc[-1]
        indicators['Daily_Change'] = (df['Close'].iloc[-1] / df['Close'].iloc[-2] - 1) * 100
        indicators['Weekly_Change'] = (df['Close'].iloc[-1] / df['Close'].iloc[-6] - 1) * 100
        
        # 52-Week High & Low, All-time High & Low
        indicators['52W_High'] = df['High'].rolling(window=252).max().iloc[-1]
        indicators['52W_Low'] = df['Low'].rolling(window=252).min().iloc[-1]
        indicators['All_Time_High'] = df['High'].max()
        indicators['All_Time_Low'] = df['Low'].min()
        
        # Moving Averages
        indicators['sma20'] = df['Close'].rolling(window=20).mean().iloc[-1]
        indicators['sma50'] = df['Close'].rolling(window=50).mean().iloc[-1]
        indicators['sma100'] = df['Close'].rolling(window=100).mean().iloc[-1]
        indicators['sma200'] = df['Close'].rolling(window=200).mean().iloc[-1]
        indicators['ema12'] = df['Close'].ewm(span=12, adjust=False).mean().iloc[-1]
        indicators['ema26'] = df['Close'].ewm(span=26, adjust=False).mean().iloc[-1]
        
        # RSI
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        roll_up = up.rolling(14).mean()
        roll_down = down.rolling(14).mean()
        
        last_roll_down = safe_float(roll_down.iloc[-1])
        if last_roll_down and last_roll_down != 0:
            last_rs = safe_float(roll_up.iloc[-1]) / last_roll_down
            indicators['rsi14'] = 100 - (100 / (1 + last_rs))
        else:
            indicators['rsi14'] = 50
        
        # MACD with Signal and Histogram
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        indicators['macd'] = safe_float(macd.iloc[-1])
        indicators['macd_signal'] = safe_float(signal.iloc[-1])
        indicators['macd_hist'] = safe_float(macd.iloc[-1] - signal.iloc[-1])
        
        # Bollinger Bands (20-day, 2 standard deviations)
        sma20 = df['Close'].rolling(window=20).mean()
        std20 = df['Close'].rolling(window=20).std()
        upper_band = sma20 + (std20 * 2)
        lower_band = sma20 - (std20 * 2)
        
        # Stochastic Oscillator (14,3,3)
        low_14 = df['Low'].rolling(window=14).min()
        high_14 = df['High'].rolling(window=14).max()
        k = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
        indicators['stoch_k'] = safe_float(k.rolling(window=3).mean().iloc[-1])
        indicators['stoch_d'] = safe_float(k.rolling(window=3).mean().rolling(window=3).mean().iloc[-1])
        
        current_price = safe_float(df['Close'].iloc[-1])
        if current_price:
            bb_range = safe_float(upper_band.iloc[-1] - lower_band.iloc[-1])
            if bb_range:
                indicators['volatility'] = bb_range / current_price
        
        # Support and Resistance Levels
        window = 20  # Look back period for S/R levels
        highs = df['High'].rolling(window=window, center=True).max()
        lows = df['Low'].rolling(window=window, center=True).min()
        
        # Find recent support levels (last 3 significant lows)
        support_levels = []
        for i in range(len(df)-window, len(df)):
            if i > 0 and lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i+1]:
                support_levels.append(lows.iloc[i])
        indicators['support_levels'] = sorted(list(set([round(x, 2) for x in support_levels[-3:]]))[:3])
        
        # Find recent resistance levels (last 3 significant highs)
        resistance_levels = []
        for i in range(len(df)-window, len(df)):
            if i > 0 and highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i+1]:
                resistance_levels.append(highs.iloc[i])
        indicators['resistance_levels'] = sorted(list(set([round(x, 2) for x in resistance_levels[-3:]]))[:3])
        
        # Volume Analysis
        indicators['volume_sma20'] = df['Volume'].rolling(window=20).mean().iloc[-1]
        indicators['current_volume'] = df['Volume'].iloc[-1]
        indicators['volume_trend'] = 'Increasing' if df['Volume'].iloc[-5:].mean() > indicators['volume_sma20'] else 'Decreasing'
        
        # Trend Direction
        if all(indicators[ma] < current_price for ma in ['sma20', 'sma50', 'sma200']):
            indicators['trend'] = 'Strong Uptrend'
        elif all(indicators[ma] > current_price for ma in ['sma20', 'sma50', 'sma200']):
            indicators['trend'] = 'Strong Downtrend'
        elif indicators['sma20'] > indicators['sma50'] > indicators['sma200']:
            indicators['trend'] = 'Uptrend'
        elif indicators['sma20'] < indicators['sma50'] < indicators['sma200']:
            indicators['trend'] = 'Downtrend'
        else:
            indicators['trend'] = 'Sideways'
            
        return {k: safe_float(v) if not isinstance(v, (list, str)) else v for k, v in indicators.items()}
    except Exception as e:
        logging.error(f"Error calculating indicators: {str(e)}")
        return None

def compute_technical_score(indicators):
    """
    Compute a comprehensive 0-100 technical score based on weighted indicators.
    Returns: tuple of (score, analysis_summary)
    """
    if not indicators:
        return 0, "Insufficient data for analysis"
        
    score = 0
    total_weight = sum(TECHNICAL_WEIGHTS.values())
    analysis_points = []
    
    # Moving Average Trend (ma_trend)
    ma_keys = ['sma20', 'sma50', 'sma100', 'sma200', 'Close']
    if all(k in indicators for k in ma_keys):
        ma_signals = [
            indicators['Close'] > indicators['sma20'],  # Short-term trend
            indicators['sma20'] > indicators['sma50'],  # Medium-term trend
            indicators['sma50'] > indicators['sma100'],  # Intermediate trend
            indicators['sma100'] > indicators['sma200']  # Long-term trend
        ]
        ma_score = sum(ma_signals) / len(ma_signals)
        score += ma_score * TECHNICAL_WEIGHTS['ma_trend']
        
        if ma_score > 0.7:
            analysis_points.append("Strong bullish trend across multiple timeframes")
        elif ma_score < 0.3:
            analysis_points.append("Strong bearish trend across multiple timeframes")
    
    # RSI (rsi)
    rsi = indicators.get('rsi14')
    if rsi is not None:
        if rsi < 30:  # Oversold
            rsi_score = 0.8
        elif rsi > 70:  # Overbought
            rsi_score = 0.2
        else:  # Neutral
            rsi_score = 0.5
        score += rsi_score * TECHNICAL_WEIGHTS['rsi']
    
    # MACD Trend
    macd = indicators.get('macd')
    if macd is not None:
        if macd > 0:  # Bullish
            macd_score = 0.8
        else:  # Bearish
            macd_score = 0.2
        score += macd_score * TECHNICAL_WEIGHTS['macd']
    
    # Price Trend
    ema_keys = ['ema12', 'ema26']
    if all(k in indicators for k in ema_keys):
        if indicators['ema12'] > indicators['ema26']:  # Uptrend
            trend_score = 0.8
        else:  # Downtrend
            trend_score = 0.2
        score += trend_score * TECHNICAL_WEIGHTS['trend']
    
    # Momentum Indicators
    # RSI
    rsi = indicators.get('rsi14')
    if rsi is not None:
        if rsi < 30:  # Oversold
            rsi_score = 0.8
            analysis_points.append("RSI indicates oversold conditions")
        elif rsi > 70:  # Overbought
            rsi_score = 0.2
            analysis_points.append("RSI indicates overbought conditions")
        else:  # Neutral
            rsi_score = 0.5
        score += rsi_score * TECHNICAL_WEIGHTS['rsi']
    
    # MACD
    if all(k in indicators for k in ['macd', 'macd_signal', 'macd_hist']):
        macd_crossover = indicators['macd'] > indicators['macd_signal']
        macd_hist_increasing = indicators['macd_hist'] > 0
        
        if macd_crossover and macd_hist_increasing:
            macd_score = 0.8
            analysis_points.append("Bullish MACD crossover")
        elif not macd_crossover and not macd_hist_increasing:
            macd_score = 0.2
            analysis_points.append("Bearish MACD crossover")
        else:
            macd_score = 0.5
        score += macd_score * TECHNICAL_WEIGHTS['macd']
    
    # Stochastic
    if all(k in indicators for k in ['stoch_k', 'stoch_d']):
        if indicators['stoch_k'] < 20 and indicators['stoch_d'] < 20:
            stoch_score = 0.8
            analysis_points.append("Stochastic indicates oversold conditions")
        elif indicators['stoch_k'] > 80 and indicators['stoch_d'] > 80:
            stoch_score = 0.2
            analysis_points.append("Stochastic indicates overbought conditions")
        else:
            stoch_score = 0.5
        score += stoch_score * TECHNICAL_WEIGHTS.get('stochastic', 10)  # Give 10% weight to stochastic by default
    
    # Volume Analysis
    if 'volume_trend' in indicators:
        if indicators['volume_trend'] == 'Increasing':
            volume_score = 0.8
            analysis_points.append("Strong volume supporting price action")
        else:
            volume_score = 0.4
            analysis_points.append("Declining volume suggests weakening trend")
        score += volume_score * TECHNICAL_WEIGHTS['volume']
    
    # Volatility (lower is better)
    vol = indicators.get('volatility')
    if vol is not None:
        vol_score = max(0, 1 - vol)  # Normalize between 0 and 1
        score += vol_score * TECHNICAL_WEIGHTS['volatility']
        if vol > 0.03:
            analysis_points.append("High volatility detected")
    
    # Combine analysis points into summary
    if len(analysis_points) > 3:
        analysis_points = analysis_points[:3]  # Keep top 3 most significant points
    analysis_summary = " ".join(analysis_points)
    
    return round(score / total_weight * 100, 2), analysis_summary

def generate_technical_summary(indicators):
    """
    Generate a comprehensive technical analysis summary
    Returns: dict with detailed technical analysis
    """
    summary = {
        'price_action': {
            'current_price': indicators['Close'],
            'daily_change': indicators['Daily_Change'],
            'weekly_change': indicators['Weekly_Change'],
            '52w_high': indicators['52W_High'],
            '52w_low': indicators['52W_Low'],
            'all_time_high': indicators['All_Time_High'],
            'all_time_low': indicators['All_Time_Low']
        },
        'moving_averages': {
            'position': {
                'vs_20d': 'Above' if indicators['Close'] > indicators['sma20'] else 'Below',
                'vs_50d': 'Above' if indicators['Close'] > indicators['sma50'] else 'Below',
                'vs_100d': 'Above' if indicators['Close'] > indicators['sma100'] else 'Below',
                'vs_200d': 'Above' if indicators['Close'] > indicators['sma200'] else 'Below'
            },
            'values': {
                'sma20': indicators['sma20'],
                'sma50': indicators['sma50'],
                'sma100': indicators['sma100'],
                'sma200': indicators['sma200']
            }
        },
        'momentum_indicators': {
            'rsi': indicators.get('rsi14'),
            'macd': {
                'value': indicators['macd'],
                'signal': indicators['macd_signal'],
                'histogram': indicators['macd_hist']
            },
            'stochastic': {
                'k': indicators['stoch_k'],
                'd': indicators['stoch_d']
            }
        },
        'support_resistance': {
            'support': indicators['support_levels'],
            'resistance': indicators['resistance_levels']
        },
        'volume_analysis': {
            'current_volume': indicators['current_volume'],
            'volume_sma20': indicators['volume_sma20'],
            'trend': indicators['volume_trend']
        },
        'trend_analysis': {
            'primary_trend': indicators['trend'],
            'volatility': indicators['volatility']
        }
    }
    
    return summary

def get_ohlcv(symbol, period="1y"):
    """
    Get historical OHLCV data for a stock
    Returns: DataFrame with OHLCV data
    """
    try:
        stock = yf.Ticker(f"{symbol}.NS")
        df = stock.history(period=period)
        if not df.empty:
            return df
        logging.warning(f"No historical data available for {symbol}")
    except Exception as e:
        logging.error(f"Error fetching historical data for {symbol}: {str(e)}")
    return None