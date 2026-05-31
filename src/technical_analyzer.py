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
    if df is None or df.empty:
        return {}
    try:
        indicators = {}
        
        # Current Price & Changes
        indicators['Close'] = df['Close'].iloc[-1]
        _d2 = df['Close'].iloc[-2] if len(df) >= 2 else df['Close'].iloc[-1]
        indicators['Daily_Change'] = ((df['Close'].iloc[-1] / _d2 - 1) * 100) if pd.notna(_d2) and _d2 != 0 else 0
        _d6 = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
        indicators['Weekly_Change'] = ((df['Close'].iloc[-1] / _d6 - 1) * 100) if pd.notna(_d6) and _d6 != 0 else 0
        
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
        last_roll_up = safe_float(roll_up.iloc[-1])
        if last_roll_down is not None and last_roll_up is not None and not np.isnan(last_roll_down) and not np.isnan(last_roll_up):
            if last_roll_down == 0:
                indicators['rsi14'] = 100.0 if last_roll_up > 0 else 50.0
            else:
                last_rs = last_roll_up / last_roll_down
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
        _stoch_denom = (high_14 - low_14).replace(0, np.nan)
        k = (100 * ((df['Close'] - low_14) / _stoch_denom)).fillna(50)
        indicators['stoch_k'] = safe_float(k.rolling(window=3).mean().iloc[-1])
        indicators['stoch_d'] = safe_float(k.rolling(window=3).mean().rolling(window=3).mean().iloc[-1])
        
        current_price = safe_float(df['Close'].iloc[-1])
        if pd.notna(current_price) and current_price != 0:
            bb_range = safe_float(upper_band.iloc[-1] - lower_band.iloc[-1])
            if pd.notna(bb_range) and bb_range != 0:
                indicators['volatility'] = bb_range / current_price
        
        # Support and Resistance Levels
        window = 20  # Look back period for S/R levels
        highs = df['High'].rolling(window=window, center=True).max()
        lows = df['Low'].rolling(window=window, center=True).min()
        
        # Find recent support levels (last 3 significant lows)
        support_levels = []
        for i in range(max(1, len(df)-window), len(df)):
            if i > 0 and i+1 < len(df) and lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i+1]:
                support_levels.append(float(lows.iloc[i]))
        
        # Safely handle empty or short support_levels
        if len(support_levels) > 0:
            unique_supports = list(set([round(x, 2) for x in support_levels[-min(3, len(support_levels)):]]))
            indicators['support_levels'] = sorted(unique_supports)[-min(3, len(unique_supports)):]
        else:
            indicators['support_levels'] = []
        
        # Find recent resistance levels (last 3 significant highs)
        resistance_levels = []
        for i in range(len(df)-window, len(df)):
            if i > 0 and i+1 < len(df) and highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i+1]:
                resistance_levels.append(float(highs.iloc[i]))
        
        # Safely handle empty or short resistance_levels
        if len(resistance_levels) > 0:
            # Take up to last 3 elements, convert to set to remove duplicates, then take up to 3
            unique_resistances = list(set([round(x, 2) for x in resistance_levels[-min(3, len(resistance_levels)):]]))
            indicators['resistance_levels'] = sorted(unique_resistances)[:min(3, len(unique_resistances))]
        else:
            indicators['resistance_levels'] = []
        
        # Volume Analysis
        indicators['volume_sma20'] = df['Volume'].rolling(window=20).mean().iloc[-1]
        indicators['current_volume'] = df['Volume'].iloc[-1]
        indicators['volume_trend'] = 'Increasing' if df['Volume'].iloc[-5:].mean() > indicators['volume_sma20'] else 'Decreasing'
        
        # Trend Direction
        if current_price is None or (isinstance(current_price, float) and np.isnan(current_price)):
            current_price = 0
        _ma_vals = {ma: indicators.get(ma) for ma in ['sma20', 'sma50', 'sma200']}
        _any_nan = any(v is None or (isinstance(v, float) and np.isnan(v)) for v in _ma_vals.values())
        if _any_nan or current_price == 0:
            indicators['trend'] = 'Sideways'
        elif all(_ma_vals[ma] < current_price for ma in ['sma20', 'sma50', 'sma200']):
            indicators['trend'] = 'Strong Uptrend'
        elif all(_ma_vals[ma] > current_price for ma in ['sma20', 'sma50', 'sma200']):
            indicators['trend'] = 'Strong Downtrend'
        elif _ma_vals['sma20'] > _ma_vals['sma50'] > _ma_vals['sma200']:
            indicators['trend'] = 'Uptrend'
        elif _ma_vals['sma20'] < _ma_vals['sma50'] < _ma_vals['sma200']:
            indicators['trend'] = 'Downtrend'
        else:
            indicators['trend'] = 'Sideways'
            
        return {k: safe_float(v) if not isinstance(v, (list, str)) else v for k, v in indicators.items()}
    except Exception as e:
        logging.error(f"Error calculating indicators: {str(e)}")
        return {}

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
    
    # Price Trend
    ema_keys = ['ema12', 'ema26']
    if all(k in indicators for k in ema_keys):
        if indicators['ema12'] > indicators['ema26']:  # Uptrend
            trend_score = 0.8
        else:  # Downtrend
            trend_score = 0.2
        score += trend_score * TECHNICAL_WEIGHTS['trend']
    
    # RSI Momentum
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
    if vol is not None and not np.isnan(vol):
        vol_score = max(0, 1 - vol)
        score += vol_score * TECHNICAL_WEIGHTS['volatility']
        if vol > 0.03:
            analysis_points.append("High volatility detected")
    
    # Combine analysis points into summary
    if len(analysis_points) > 3:
        analysis_points = analysis_points[:3]
    analysis_summary = " ".join(analysis_points)
    
    final = round(score / total_weight * 100, 2) if total_weight != 0 else 50.0
    if np.isnan(final):
        final = 50.0
    return final, analysis_summary

def generate_technical_summary(indicators):
    """
    Generate a comprehensive technical analysis summary
    Returns: dict with detailed technical analysis
    """
    if not indicators or not isinstance(indicators, dict):
        return {}
    _g = indicators.get
    _close = _g('Close', 0)
    summary = {
        'price_action': {
            'current_price': _close,
            'daily_change': _g('Daily_Change', 0),
            'weekly_change': _g('Weekly_Change', 0),
            '52w_high': _g('52W_High', 0),
            '52w_low': _g('52W_Low', 0),
            'all_time_high': _g('All_Time_High', 0),
            'all_time_low': _g('All_Time_Low', 0)
        },
        'moving_averages': {
            'position': {
                'vs_20d': 'Above' if _close > (_g('sma20') or 0) else 'Below',
                'vs_50d': 'Above' if _close > (_g('sma50') or 0) else 'Below',
                'vs_100d': 'Above' if _close > (_g('sma100') or 0) else 'Below',
                'vs_200d': 'Above' if _close > (_g('sma200') or 0) else 'Below'
            },
            'values': {
                'sma20': _g('sma20', 0),
                'sma50': _g('sma50', 0),
                'sma100': _g('sma100', 0),
                'sma200': _g('sma200', 0)
            }
        },
        'momentum_indicators': {
            'rsi': _g('rsi14', 50),
            'macd': {
                'value': _g('macd', 0),
                'signal': _g('macd_signal', 0),
                'histogram': _g('macd_hist', 0)
            },
            'stochastic': {
                'k': _g('stoch_k', 50),
                'd': _g('stoch_d', 50)
            }
        },
        'support_resistance': {
            'support': _g('support_levels', []),
            'resistance': _g('resistance_levels', [])
        },
        'volume_analysis': {
            'current_volume': _g('current_volume', 0),
            'volume_sma20': _g('volume_sma20', 0),
            'trend': _g('volume_trend', 'NEUTRAL')
        },
        'trend_analysis': {
            'primary_trend': _g('trend', 'NEUTRAL'),
            'volatility': _g('volatility', 0)
        }
    }
    
    return summary

def get_ohlcv(symbol, period="1y"):
    """
    Get historical OHLCV data for a stock
    Returns: DataFrame with OHLCV data
    """
    if _upstox_data_enabled():
        try:
            from src.upstox_data import fetch_historical_ohlcv

            df = fetch_historical_ohlcv(symbol, period=period)
            if df is not None and not df.empty:
                return df
            logging.warning(
                "Upstox OHLCV empty for %s — falling back to yfinance", symbol
            )
        except Exception as exc:
            logging.warning(
                "Upstox OHLCV failed for %s (%s) — falling back to yfinance",
                symbol,
                exc,
            )
    try:
        stock = yf.Ticker(f"{symbol}.NS")
        df = stock.history(period=period)
        if not df.empty:
            return df
        logging.warning(f"No historical data available for {symbol}")
    except Exception as e:
        logging.error(f"Error fetching historical data for {symbol}: {str(e)}")
    return None


def _upstox_data_enabled() -> bool:
    try:
        from pathlib import Path
        repo = Path(__file__).resolve().parents[1]
        env_path = repo / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
            except ImportError:
                pass
        from config import get_config
        if bool(getattr(get_config(), "UPSTOX_DATA_ENABLED", False)):
            return True
        from src.upstox_data import upstox_data_enabled
        return upstox_data_enabled()
    except Exception:
        return False