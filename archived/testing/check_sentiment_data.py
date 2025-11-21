"""
Quick script to verify sentiment analysis data in Excel report
"""
import pandas as pd
import sys

try:
    # Load the Complete Data sheet
    df = pd.read_excel('reports/Enhanced_Stock_Report_20251006_132844.xlsx', sheet_name='Complete Data')
    
    print(f"\n📊 Total columns in report: {len(df.columns)}")
    print(f"📊 Total stocks analyzed: {len(df)}")
    
    # Find sentiment columns
    sentiment_cols = [col for col in df.columns if 'sentiment' in col.lower()]
    
    print(f"\n🎭 SENTIMENT ANALYSIS COLUMNS ({len(sentiment_cols)} found):")
    print("="*60)
    for col in sentiment_cols:
        print(f"  ✅ {col}")
    
    # Show sample sentiment data
    if sentiment_cols:
        print(f"\n📊 SAMPLE SENTIMENT DATA (Top 5 stocks):")
        print("="*60)
        
        # Select key sentiment columns
        key_cols = ['Symbol', 'sentiment_composite_score', 'sentiment_signal', 
                    'sentiment_strength', 'sentiment_confidence']
        available_key_cols = [col for col in key_cols if col in df.columns]
        
        if available_key_cols:
            sample_df = df[available_key_cols].head(5)
            print(sample_df.to_string(index=False))
        else:
            print("⚠️  Key sentiment columns not found in expected format")
            print("\nAvailable sentiment columns:")
            for col in sentiment_cols:
                print(f"  - {col}: {df[col].iloc[0] if len(df) > 0 else 'N/A'}")
    else:
        print("\n⚠️  WARNING: No sentiment columns found in the report!")
        print("This may indicate the sentiment data is not being saved to Excel.")
    
    print("\n✅ Sentiment data verification complete!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
