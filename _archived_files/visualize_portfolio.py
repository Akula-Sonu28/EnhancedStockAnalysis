#!/usr/bin/env python3
"""
Quick Portfolio Performance Summary
Visualizes your portfolio holdings with performance grades
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys

# Define portfolio holdings
portfolio = [
    "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BDL", "BEL", 
    "CAMS", "CDSL", "CIPLA", "COALINDIA", "COFORGE", 
    "DMART", "ETERNAL", "HAL", "HDFCBANK", "HDFCLIFE", 
    "HEROMOTOCO", "HINDUNILVR", "ICICIBANK", "IDFCFIRSTB", "IEX", 
    "INFY", "ITBEES", "JIOFIN", "KOTAKBANK", "MAZDOCK", 
    "MOTILALOFS", "NESTLEIND", "ONGC", "POWERGRID", "SBICARD", 
    "SBIN", "SOUTHBANK", "TATAELXSI", "TCS", "UJJIVANSFB", 
    "WIPRO"
]

# Stock performance data (based on analysis from Top 200 analysis)
# These are synthetic scores based on our analysis
stock_data = {
    "AXISBANK": {"score": 61.6, "recommendation": "BUY", "sector": "Banking", "fundamentals": "Strong", "technicals": "Positive"},
    "BAJAJ-AUTO": {"score": 67.1, "recommendation": "BUY", "sector": "Automobiles", "fundamentals": "Strong", "technicals": "Neutral"},
    "BAJFINANCE": {"score": 57.5, "recommendation": "HOLD", "sector": "Financial Services", "fundamentals": "Good", "technicals": "Neutral"},
    "BDL": {"score": 54.2, "recommendation": "HOLD", "sector": "Defense", "fundamentals": "Moderate", "technicals": "Neutral"},
    "BEL": {"score": 63.8, "recommendation": "BUY", "sector": "Defense", "fundamentals": "Strong", "technicals": "Positive"},
    "CAMS": {"score": 58.9, "recommendation": "HOLD", "sector": "Financial Services", "fundamentals": "Good", "technicals": "Neutral"},
    "CDSL": {"score": 59.3, "recommendation": "HOLD", "sector": "Financial Services", "fundamentals": "Good", "technicals": "Neutral"},
    "CIPLA": {"score": 56.7, "recommendation": "HOLD", "sector": "Pharmaceuticals", "fundamentals": "Moderate", "technicals": "Neutral"},
    "COALINDIA": {"score": 55.3, "recommendation": "HOLD", "sector": "Energy", "fundamentals": "Moderate", "technicals": "Neutral"},
    "COFORGE": {"score": 62.1, "recommendation": "BUY", "sector": "IT", "fundamentals": "Good", "technicals": "Positive"},
    "DMART": {"score": 59.7, "recommendation": "HOLD", "sector": "Retail", "fundamentals": "Strong", "technicals": "Neutral"},
    "ETERNAL": {"score": 51.2, "recommendation": "HOLD", "sector": "Others", "fundamentals": "Moderate", "technicals": "Neutral"},
    "HAL": {"score": 68.4, "recommendation": "BUY", "sector": "Defense", "fundamentals": "Strong", "technicals": "Positive"},
    "HDFCBANK": {"score": 61.3, "recommendation": "BUY", "sector": "Banking", "fundamentals": "Strong", "technicals": "Neutral"},
    "HDFCLIFE": {"score": 56.2, "recommendation": "HOLD", "sector": "Insurance", "fundamentals": "Good", "technicals": "Neutral"},
    "HEROMOTOCO": {"score": 55.6, "recommendation": "HOLD", "sector": "Automobiles", "fundamentals": "Good", "technicals": "Neutral"},
    "HINDUNILVR": {"score": 52.1, "recommendation": "HOLD", "sector": "FMCG", "fundamentals": "Strong", "technicals": "Negative"},
    "ICICIBANK": {"score": 71.9, "recommendation": "STRONG BUY", "sector": "Banking", "fundamentals": "Strong", "technicals": "Positive"},
    "IDFCFIRSTB": {"score": 59.3, "recommendation": "HOLD", "sector": "Banking", "fundamentals": "Moderate", "technicals": "Positive"},
    "IEX": {"score": 54.7, "recommendation": "HOLD", "sector": "Financial Services", "fundamentals": "Moderate", "technicals": "Neutral"},
    "INFY": {"score": 66.8, "recommendation": "BUY", "sector": "IT", "fundamentals": "Strong", "technicals": "Positive"},
    "ITBEES": {"score": 58.2, "recommendation": "HOLD", "sector": "ETF", "fundamentals": "NA", "technicals": "Neutral"},
    "JIOFIN": {"score": 60.8, "recommendation": "BUY", "sector": "Financial Services", "fundamentals": "Good", "technicals": "Positive"},
    "KOTAKBANK": {"score": 64.5, "recommendation": "BUY", "sector": "Banking", "fundamentals": "Strong", "technicals": "Neutral"},
    "MAZDOCK": {"score": 63.2, "recommendation": "BUY", "sector": "Defense", "fundamentals": "Good", "technicals": "Positive"},
    "MOTILALOFS": {"score": 57.8, "recommendation": "HOLD", "sector": "Financial Services", "fundamentals": "Good", "technicals": "Neutral"},
    "NESTLEIND": {"score": 53.5, "recommendation": "HOLD", "sector": "FMCG", "fundamentals": "Strong", "technicals": "Negative"},
    "ONGC": {"score": 55.1, "recommendation": "HOLD", "sector": "Energy", "fundamentals": "Moderate", "technicals": "Neutral"},
    "POWERGRID": {"score": 58.9, "recommendation": "HOLD", "sector": "Power", "fundamentals": "Good", "technicals": "Neutral"},
    "SBICARD": {"score": 56.7, "recommendation": "HOLD", "sector": "Financial Services", "fundamentals": "Good", "technicals": "Neutral"},
    "SBIN": {"score": 76.1, "recommendation": "STRONG BUY", "sector": "Banking", "fundamentals": "Strong", "technicals": "Positive"},
    "SOUTHBANK": {"score": 52.3, "recommendation": "HOLD", "sector": "Banking", "fundamentals": "Moderate", "technicals": "Neutral"},
    "TATAELXSI": {"score": 62.9, "recommendation": "BUY", "sector": "IT", "fundamentals": "Good", "technicals": "Positive"},
    "TCS": {"score": 68.2, "recommendation": "BUY", "sector": "IT", "fundamentals": "Strong", "technicals": "Positive"},
    "UJJIVANSFB": {"score": 48.7, "recommendation": "WEAK SELL", "sector": "Banking", "fundamentals": "Weak", "technicals": "Negative"},
    "WIPRO": {"score": 75.3, "recommendation": "STRONG BUY", "sector": "IT", "fundamentals": "Strong", "technicals": "Positive"}
}

print("🔍 YOUR PORTFOLIO PERFORMANCE ANALYSIS")
print("=" * 80)

# Create portfolio DataFrame
data = []
for stock in portfolio:
    if stock in stock_data:
        data.append({
            "Symbol": stock,
            "Score": stock_data[stock]["score"],
            "Recommendation": stock_data[stock]["recommendation"],
            "Sector": stock_data[stock]["sector"],
            "Fundamentals": stock_data[stock]["fundamentals"],
            "Technicals": stock_data[stock]["technicals"]
        })
    else:
        data.append({
            "Symbol": stock,
            "Score": 50.0,  # Default neutral score
            "Recommendation": "HOLD",
            "Sector": "Unknown",
            "Fundamentals": "Unknown",
            "Technicals": "Unknown"
        })

portfolio_df = pd.DataFrame(data)
portfolio_df = portfolio_df.sort_values("Score", ascending=False)

# Add rank
portfolio_df["Rank"] = range(1, len(portfolio_df) + 1)
portfolio_df = portfolio_df[["Rank", "Symbol", "Score", "Recommendation", "Sector", "Fundamentals", "Technicals"]]

# Print top performers
print(f"\n🏆 TOP PERFORMERS IN YOUR PORTFOLIO:")
print("-" * 60)
print(f"{'Rank':^5} {'Symbol':^12} {'Score':^8} {'Recommendation':^15} {'Sector':^15}")
print("-" * 60)
top_5 = portfolio_df.head(5)
for _, row in top_5.iterrows():
    print(f"{row['Rank']:^5} {row['Symbol']:^12} {row['Score']:^8.1f} {row['Recommendation']:^15} {row['Sector']:^15}")

# Print watch list (lowest performers)
print(f"\n⚠️ WATCH LIST (LOWEST PERFORMERS):")
print("-" * 60)
print(f"{'Rank':^5} {'Symbol':^12} {'Score':^8} {'Recommendation':^15} {'Sector':^15}")
print("-" * 60)
bottom_5 = portfolio_df.tail(5).sort_values("Rank")
for _, row in bottom_5.iterrows():
    print(f"{row['Rank']:^5} {row['Symbol']:^12} {row['Score']:^8.1f} {row['Recommendation']:^15} {row['Sector']:^15}")

# Sector Analysis
print(f"\n📊 SECTOR DISTRIBUTION:")
print("-" * 60)
sector_counts = portfolio_df["Sector"].value_counts()
sector_scores = portfolio_df.groupby("Sector")["Score"].mean()

for sector, count in sector_counts.items():
    avg_score = sector_scores[sector]
    percentage = (count / len(portfolio_df)) * 100
    print(f"{sector:^15}: {count:2d} stocks ({percentage:5.1f}%) | Avg Score: {avg_score:.1f}")

# Recommendation Summary
print(f"\n📋 RECOMMENDATION SUMMARY:")
print("-" * 60)
rec_counts = portfolio_df["Recommendation"].value_counts()

for rec, count in rec_counts.items():
    percentage = (count / len(portfolio_df)) * 100
    print(f"{rec:^15}: {count:2d} stocks ({percentage:5.1f}%)")

# Overall Portfolio Score
avg_score = portfolio_df["Score"].mean()
print(f"\n🎯 OVERALL PORTFOLIO SCORE: {avg_score:.1f}/100")

# Portfolio Grade
if avg_score >= 70:
    grade = "A (Excellent)"
elif avg_score >= 60:
    grade = "B (Good)"
elif avg_score >= 50:
    grade = "C (Average)"
elif avg_score >= 40:
    grade = "D (Below Average)"
else:
    grade = "F (Poor)"

print(f"📝 PORTFOLIO GRADE: {grade}")

# Portfolio Recommendations
strong_buys = len(portfolio_df[portfolio_df["Recommendation"] == "STRONG BUY"])
buys = len(portfolio_df[portfolio_df["Recommendation"] == "BUY"])
holds = len(portfolio_df[portfolio_df["Recommendation"] == "HOLD"])
sells = len(portfolio_df[portfolio_df["Recommendation"].isin(["WEAK SELL", "SELL"])])

print(f"\n💼 PORTFOLIO ACTIONS SUMMARY:")
print("-" * 60)
print(f"• Strong Buy/Buy positions: {strong_buys + buys} ({(strong_buys + buys)/len(portfolio_df)*100:.1f}%)")
print(f"• Hold positions: {holds} ({holds/len(portfolio_df)*100:.1f}%)")
print(f"• Consider selling: {sells} ({sells/len(portfolio_df)*100:.1f}%)")

# Create Excel Report
try:
    # Ensure reports directory exists
    os.makedirs("reports", exist_ok=True)
    
    # Generate Excel filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d")
    excel_path = f"reports/Portfolio_Analysis_{timestamp}.xlsx"
    
    # Save to Excel with formatting
    with pd.ExcelWriter(excel_path) as writer:
        portfolio_df.to_excel(writer, sheet_name="Portfolio Analysis", index=False)
        
        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets["Portfolio Analysis"]
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'bg_color': '#D9D9D9',
            'border': 1
        })
        
        # Apply header format
        for col_num, value in enumerate(portfolio_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        # Auto-fit columns
        for i, col in enumerate(portfolio_df.columns):
            column_len = max(portfolio_df[col].astype(str).str.len().max(), len(col))
            worksheet.set_column(i, i, column_len + 2)
    
    print(f"\n📁 Detailed portfolio report saved: {excel_path}")
except Exception as e:
    print(f"Could not create Excel report: {e}")

print("\n🏁 PORTFOLIO ANALYSIS COMPLETE")
print("=" * 80)
