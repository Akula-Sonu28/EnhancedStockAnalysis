import pandas as pd
import json
import os
import traceback
import sys
import io

try:
    csv_path = r'c:\Users\Sanji\Extract\data\nse_top150_20250822_235232.csv'
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Reading file: {csv_path}")
    print(f"File exists: {os.path.exists(csv_path)}")
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    with open(csv_path, 'rb') as f:
        content = f.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(content), engine='python')
    df = df.sort_values('OverallScore', ascending=False).head(25)

    print('\nDetailed Analysis of Top 25 Stocks:\n')
    print('=' * 120)

    for _, row in df.iterrows():
        support_levels = sorted([float(x) for x in json.loads(row['support_levels'].replace('\'', '"'))])
        resistance_levels = sorted([float(x) for x in json.loads(row['resistance_levels'].replace('\'', '"'))])
        
        print(f'\n{row["symbol"]} (Score: {row["OverallScore"]:.2f})')
        print('-' * 80)
        print(f'Current Price: ₹{row["Close"]:.2f}')
        print(f'Daily Change: {row["Daily_Change"]:.2f}%')
        print(f'52W Range: ₹{row["52W_Low"]:.2f} - ₹{row["52W_High"]:.2f}')
        print(f'Support Levels: S1: ₹{support_levels[0]:.2f}, S2: ₹{support_levels[1]:.2f}, S3: ₹{support_levels[2]:.2f}')
        print(f'Resistance Levels: R1: ₹{resistance_levels[0]:.2f}, R2: ₹{resistance_levels[1]:.2f}, R3: ₹{resistance_levels[2]:.2f}')
        print(f'RSI: {row["rsi14"]:.2f}')
        print(f'Trend: {row["trend"]}')
        print(f'Volume Trend: {row["volume_trend"]}')
except Exception as e:
    print(f"Error: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
except Exception as e:
    print(f"Error reading CSV file: {e}")
df = df.sort_values('OverallScore', ascending=False).head(25)

print('\nDetailed Analysis of Top 25 Stocks:\n')
print('=' * 120)

for _, row in df.iterrows():
    support_levels = sorted([float(x) for x in json.loads(row['support_levels'].replace('\'', '"'))])
    resistance_levels = sorted([float(x) for x in json.loads(row['resistance_levels'].replace('\'', '"'))])
    
    print(f'\n{row["symbol"]} (Score: {row["OverallScore"]:.2f})')
    print('-' * 80)
    print(f'Current Price: ₹{row["Close"]:.2f}')
    print(f'Daily Change: {row["Daily_Change"]:.2f}%')
    print(f'52W Range: ₹{row["52W_Low"]:.2f} - ₹{row["52W_High"]:.2f}')
    print(f'Support Levels: S1: ₹{support_levels[0]:.2f}, S2: ₹{support_levels[1]:.2f}, S3: ₹{support_levels[2]:.2f}')
    print(f'Resistance Levels: R1: ₹{resistance_levels[0]:.2f}, R2: ₹{resistance_levels[1]:.2f}, R3: ₹{resistance_levels[2]:.2f}')
    print(f'RSI: {row["rsi14"]:.2f}')
    print(f'Trend: {row["trend"]}')
    print(f'Volume Trend: {row["volume_trend"]}')
