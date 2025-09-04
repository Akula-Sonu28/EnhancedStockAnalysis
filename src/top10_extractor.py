#!/usr/bin/env python3
"""Extract top 10 technically and fundamentally strong stocks from latest reports.

Priority order of sources:
1. Latest portfolio_analysis_*.xlsx (sheet: 'Portfolio Summary')
2. Latest Stock_Report_*.xlsx (sheet guess: 'Summary' or first sheet containing 'Symbol')

Outputs plain text plus optional JSON file in reports/top10_extraction.json
"""
import os, glob, json, sys, argparse
from datetime import datetime
import pandas as pd

REPORTS_DIR = os.path.join(os.getcwd(), 'reports')

def find_latest(pattern):
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, pattern)))
    return files[-1] if files else None

def load_any_summary(path):
    """Attempt to load a suitable sheet from the Excel file.
    Enhanced: scan each sheet for a header row containing a symbol-like token.
    Returns (DataFrame, sheet_name) or (None, None).
    """
    try:
        xl = pd.ExcelFile(path)
        preferred = ['Portfolio Summary', 'Summary']
        # Helper to scan a sheet for header row
        def scan_sheet(name):
            try:
                preview = pd.read_excel(path, sheet_name=name, header=None, nrows=40)
            except Exception:
                return None
            symbol_tokens = {'symbol','ticker','scrip','instrument','stock','code'}
            header_row_index = None
            for i, row in preview.iterrows():
                vals = [str(v).strip() for v in row.tolist()]
                lower = [v.lower() for v in vals]
                if any(v in symbol_tokens for v in lower):
                    header_row_index = i
                    break
            if header_row_index is not None:
                try:
                    df_full = pd.read_excel(path, sheet_name=name, header=header_row_index)
                    # Drop completely empty columns
                    df_full = df_full.loc[:, ~df_full.columns.to_series().astype(str).str.startswith('Unnamed')]
                    # Standardize Symbol column name
                    for col in df_full.columns:
                        if str(col).strip().lower() in symbol_tokens:
                            df_full.rename(columns={col: 'Symbol'}, inplace=True)
                    if 'Symbol' in df_full.columns:
                        return df_full
                except Exception:
                    return None
            return None
        # Try preferred names first
        for name in preferred:
            if name in xl.sheet_names:
                df = scan_sheet(name)
                if df is not None:
                    return df, name
        # Fallback: scan all sheets
        for name in xl.sheet_names:
            df = scan_sheet(name)
            if df is not None:
                return df, name
        return None, None
    except Exception as e:
        print(f"ERROR reading {path}: {e}")
        return None, None

def detect_score_columns(df):
    tech_col = None
    fund_col = None
    for c in df.columns:
        lc = c.lower()
        if tech_col is None and ('technical score' in lc or 'short_term' in lc or 'techscore' in lc):
            tech_col = c
        if fund_col is None and ('fundamental score' in lc or 'fundscore' in lc):
            fund_col = c
    return tech_col, fund_col

def extract_top(df, tech_col, fund_col, n=10):
    result = {}
    if tech_col:
        result['top_technical'] = df.sort_values(tech_col, ascending=False)[['Symbol', tech_col]].head(n)
    else:
        result['top_technical'] = pd.DataFrame(columns=['Symbol', 'Score'])
    if fund_col:
        result['top_fundamental'] = df.sort_values(fund_col, ascending=False)[['Symbol', fund_col]].head(n)
    else:
        result['top_fundamental'] = pd.DataFrame(columns=['Symbol', 'Score'])
    return result

def main():
    parser = argparse.ArgumentParser(description="Extract top 10 technical & fundamental stocks from analysis report")
    parser.add_argument('-f', '--file', help='Specific Excel report file to use (relative or absolute path)')
    parser.add_argument('-n', '--count', type=int, default=10, help='Number of top rows to show (default 10)')
    parser.add_argument('--csv', action='store_true', help='Also export a CSV with the two top lists')
    args = parser.parse_args()

    if not os.path.isdir(REPORTS_DIR):
        print("No reports directory found.")
        return 1

    if args.file:
        source = args.file
        if not os.path.isabs(source):
            source = os.path.join(REPORTS_DIR, os.path.basename(source)) if not os.path.exists(source) else source
    else:
        portfolio_file = find_latest('portfolio_analysis_*.xlsx')
        stock_file = find_latest('Stock_Report_*.xlsx')
        source = portfolio_file or stock_file
        if not source:
            print("No analysis Excel files found in reports/.")
            return 1

    if not os.path.exists(source):
        print(f"Specified file not found: {source}")
        return 1

    print(f"Using source file: {os.path.basename(source)}")
    df, sheet_used = load_any_summary(source)
    if df is None or 'Symbol' not in df.columns or df.empty:
        print("Could not load a valid sheet with 'Symbol' column (sheet may be empty or header not detected).")
        return 1
    print(f"Sheet used: {sheet_used}")

    tech_col, fund_col = detect_score_columns(df)
    if not tech_col and 'enhanced_short_term_score' in df.columns:
        tech_col = 'enhanced_short_term_score'
    if not fund_col and 'fundamental_score' in df.columns:
        fund_col = 'fundamental_score'

    # Fill missing values to avoid sort issues
    if tech_col and df[tech_col].isna().any():
        df[tech_col] = df[tech_col].fillna(0)
    if fund_col and df[fund_col].isna().any():
        df[fund_col] = df[fund_col].fillna(0)

    tops = extract_top(df, tech_col, fund_col, args.count)

    print(f"\nTop {args.count} Technically Strong:")
    if not tops['top_technical'].empty:
        print(tops['top_technical'].to_string(index=False))
    else:
        print("No technical score column found.")

    print(f"\nTop {args.count} Fundamentally Strong:")
    if not tops['top_fundamental'].empty:
        print(tops['top_fundamental'].to_string(index=False))
    else:
        print("No fundamental score column found.")

    # Save JSON summary
    json_out = {
        'source_file': os.path.basename(source),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'technical_score_column': tech_col,
        'fundamental_score_column': fund_col,
        'top_technical': tops['top_technical'].to_dict(orient='records'),
        'top_fundamental': tops['top_fundamental'].to_dict(orient='records'),
        'count': args.count,
        'sheet': sheet_used
    }
    out_path = os.path.join(REPORTS_DIR, 'top10_extraction.json')
    with open(out_path, 'w') as f:
        json.dump(json_out, f, indent=2)
    print(f"\nSaved JSON summary to reports/top10_extraction.json")

    if args.csv:
        csv_path = os.path.join(REPORTS_DIR, 'top10_extraction.csv')
        # Flatten and label type
        tech_df = tops['top_technical'].copy()
        if not tech_df.empty:
            tech_label = tech_df.columns[-1]
            tech_df.rename(columns={tech_df.columns[-1]: 'Score'}, inplace=True)
            tech_df['Type'] = 'TECHNICAL'
        fund_df = tops['top_fundamental'].copy()
        if not fund_df.empty:
            fund_label = fund_df.columns[-1]
            fund_df.rename(columns={fund_df.columns[-1]: 'Score'}, inplace=True)
            fund_df['Type'] = 'FUNDAMENTAL'
        combined = pd.concat([d for d in [tech_df, fund_df] if not d.empty], ignore_index=True)
        combined.to_csv(csv_path, index=False)
        print(f"Saved CSV summary to reports/top10_extraction.csv")

if __name__ == '__main__':
    sys.exit(main())
