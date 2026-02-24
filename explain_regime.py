"""
Show how market regime is determined
"""

print("="*80)
print("🎯 HOW MARKET REGIME IS DETERMINED")
print("="*80)

print("\n📊 STEP 1: CALCULATE 4 SIGNALS (Each ranges from -1 to +1)")
print("-" * 80)

print("\n1️⃣ TREND SIGNAL (Weight: 35%)")
print("   Checks: Price vs Moving Averages")
print("   • Current price > MA-20 (short-term): +0.25 or -0.25")
print("   • Current price > MA-50 (medium-term): +0.25 or -0.25")
print("   • MA-50 > MA-100 (trend strength): +0.25 or -0.25")
print("   • MA-100 > MA-200 (long-term): +0.25 or -0.25")
print("   → Score: -1.0 (all bearish) to +1.0 (all bullish)")

print("\n2️⃣ MOMENTUM SIGNAL (Weight: 25%)")
print("   Checks: RSI + 20-day Rate of Change")
print("   • RSI: (RSI - 50) / 50")
print("   • ROC: Price change % over 20 days")
print("   → Score: -1.0 (bearish) to +1.0 (bullish)")

print("\n3️⃣ VOLATILITY SIGNAL (Weight: 20%)")
print("   Checks: 20-day Historical Volatility vs Average")
print("   • Very Low (<80% avg): +1.0 (bullish)")
print("   • Low (<100% avg): +0.5 (moderately bullish)")
print("   • High (>100% avg): -0.5 (moderately bearish)")
print("   • Very High (>120% avg): -1.0 (bearish)")

print("\n4️⃣ BREADTH SIGNAL (Weight: 20%)")
print("   Checks: New Highs vs New Lows (20-day)")
print("   • More new highs: Positive score")
print("   • More new lows: Negative score")
print("   → Score: -1.0 to +1.0")

print("\n" + "="*80)
print("📊 STEP 2: CALCULATE WEIGHTED REGIME SCORE")
print("="*80)
print("\nRegime Score = (Trend × 0.35) + (Momentum × 0.25) + (Volatility × 0.20) + (Breadth × 0.20)")
print("\nRange: -1.0 (maximum bearish) to +1.0 (maximum bullish)")

print("\n" + "="*80)
print("🎯 STEP 3: CLASSIFY REGIME BASED ON SCORE")
print("="*80)
print("\n✅ BULL MARKET:")
print("   • Regime Score > +0.6")
print("   • Strong Bull: Score > +0.8")
print("   • Moderate Bull: Score +0.6 to +0.8")

print("\n⚠️  SIDEWAYS MARKET:")
print("   • Regime Score: -0.6 to +0.6")
print("   • Choppy/Range-bound")
print("   • No clear trend")

print("\n❌ BEAR MARKET:")
print("   • Regime Score < -0.6")
print("   • Strong Bear: Score < -0.8")
print("   • Moderate Bear: Score -0.8 to -0.6")

print("\n" + "="*80)
print("📊 YOUR CURRENT MARKET (Feb 3, 2026)")
print("="*80)
print("\nRegime Score: -0.22")
print("→ Falls in SIDEWAYS range (-0.6 to +0.6)")
print("\nBreakdown:")
print("  • Score is slightly negative (-0.22)")
print("  • Not bearish enough (<-0.6) to be BEAR")
print("  • Not bullish enough (>+0.6) to be BULL")
print("  • Market is choppy/consolidating")

print("\n💡 TRADING IMPLICATIONS:")
print("   ❌ Avoid: Momentum chasing, breakout trades")
print("   ✅ Focus: Quality stocks, support/resistance levels")
print("   ⚠️  Risk: False breakouts, whipsaws")

print("\n" + "="*80)
