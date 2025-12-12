import yfinance as yf

def check_history():
    symbol = "RELIANCE.NS"
    print(f"Checking data availability for {symbol}...")
    
    # Check 2008 Crash
    try:
        df_2008 = yf.download(symbol, start="2008-01-01", end="2009-01-01", progress=False)
        print(f"2008 Data: {len(df_2008)} rows found.")
        if not df_2008.empty:
            print("   (2008 Crash Data Available ✅)")
        else:
            print("   (2008 Data Missing ❌)")
    except Exception as e:
        print(f"   Error fetching 2008: {e}")

    # Check 2019
    try:
        df_2019 = yf.download(symbol, start="2019-01-01", end="2020-01-01", progress=False)
        print(f"2019 Data: {len(df_2019)} rows found.")
        if not df_2019.empty:
            print("   (2019 Data Available ✅)")
        else:
            print("   (2019 Data Missing ❌)")
    except Exception as e:
        print(f"   Error fetching 2019: {e}")

if __name__ == "__main__":
    check_history()
