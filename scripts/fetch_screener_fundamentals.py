#!/usr/bin/env python3
"""Fetch 10+ years of annual fundamentals from Screener.in for Nifty 200.

Outputs: data/screener_fundamentals.pkl (DataFrame)
         data/screener_fundamentals.csv (human-readable)

Columns per (symbol, fiscal_year):
  roe, debt_to_equity, net_profit, equity, borrowings,
  revenue, revenue_growth_pct, earnings_growth_pct,
  book_value_per_share (approx), pe_approx (price / EPS at fiscal year end)

Usage:
    python3 scripts/fetch_screener_fundamentals.py
    python3 scripts/fetch_screener_fundamentals.py --limit 10  # test run
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

NIFTY200_CSV = REPO / 'stock_list_template.csv'
OUT_PKL = REPO / 'data' / 'screener_fundamentals.pkl'
OUT_CSV = REPO / 'data' / 'screener_fundamentals.csv'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

logging.basicConfig(level=logging.INFO, format='[screener] %(message)s')


def _parse_table(sec) -> tuple[list[str], dict]:
    table = sec.find('table')
    if not table:
        return [], {}
    thead = table.find('thead')
    years = [th.text.strip() for th in thead.find_all('th')] if thead else []
    tbody = table.find('tbody')
    if not tbody:
        return years, {}
    rows = {}
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        cells = [
            td.text.strip()
            .replace(',', '')
            .replace('%', '')
            .replace('\xa0', '')
            .replace('+', '')
            for td in tds
        ]
        if len(cells) >= 2:
            label = cells[0].strip()
            vals = {}
            for i, yr in enumerate(years[1:], 1):
                if i < len(cells) and cells[i]:
                    try:
                        vals[yr] = float(cells[i])
                    except ValueError:
                        pass
            rows[label] = vals
    return years, rows


def fetch_one(symbol: str) -> list[dict]:
    """Return list of {symbol, fiscal_year, roe, debt_to_equity, ...} rows."""
    for suffix in ['consolidated/', '']:
        url = f'https://www.screener.in/company/{symbol}/{suffix}'
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
        except Exception as e:
            logging.warning('%s: request failed: %s', symbol, e)
            return []
        if r.status_code == 200:
            break
    else:
        logging.warning('%s: HTTP %d', symbol, r.status_code)
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    pnl: dict = {}
    bs: dict = {}

    for sec in soup.find_all('section'):
        h2 = sec.find('h2')
        if not h2:
            continue
        t = h2.text.strip().lower()
        _, rows = _parse_table(sec)
        if 'profit' in t and 'loss' in t:
            pnl = rows
        elif 'balance' in t:
            bs = rows

    net_profit = pnl.get('Net Profit', {})
    sales = pnl.get('Sales', {})
    equity_cap = bs.get('Equity Capital', {})
    reserves = bs.get('Reserves', {})
    borrowings = bs.get('Borrowings', {})
    shares_out = bs.get('Equity Capital', {})

    all_years = sorted(set(
        list(net_profit.keys()) + list(equity_cap.keys()) + list(sales.keys())
    ))

    prev_revenue = None
    prev_profit = None
    out = []
    for yr in all_years:
        # Detect non-standard fiscal periods (15m, 9m, etc.)
        is_standard = not re.search(r'\d+m', yr)

        np_val = net_profit.get(yr)
        eq = (equity_cap.get(yr) or 0) + (reserves.get(yr) or 0)
        debt = borrowings.get(yr) or 0
        rev = sales.get(yr)
        eq_capital = equity_cap.get(yr) or 0

        row = {'symbol': symbol, 'fiscal_year': yr, 'is_standard_period': is_standard}

        if np_val is not None and eq > 0:
            row['roe'] = round(np_val / eq * 100, 2)
        if eq > 0:
            row['debt_to_equity'] = round(debt / eq * 100, 2)
            row['book_value_cr'] = round(eq, 2)
        if eq_capital > 0 and eq > 0:
            face_value = 10.0
            approx_shares = eq_capital / face_value * 1e5
            if approx_shares > 0:
                row['bv_per_share'] = round(eq * 1e7 / approx_shares, 2)
                if np_val is not None:
                    row['eps'] = round(np_val * 1e7 / approx_shares, 2)

        row['net_profit_cr'] = np_val
        row['equity_cr'] = eq if eq > 0 else None
        row['borrowings_cr'] = debt
        row['revenue_cr'] = rev
        row['interest_expense_cr'] = pnl.get('Interest', {}).get(yr)

        if is_standard and rev and prev_revenue and prev_revenue > 0:
            row['revenue_growth_pct'] = round((rev / prev_revenue - 1) * 100, 2)
        if is_standard and np_val and prev_profit and prev_profit > 0:
            row['earnings_growth_pct'] = round((np_val / prev_profit - 1) * 100, 2)

        if is_standard:
            prev_revenue = rev
            prev_profit = np_val
        out.append(row)

    return out


def load_universe() -> list[str]:
    df = pd.read_csv(NIFTY200_CSV)
    col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
    return [str(s).strip().upper() for s in df[col].dropna().tolist()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='Limit symbols (0=all)')
    ap.add_argument('--delay', type=float, default=0.4, help='Seconds between requests')
    args = ap.parse_args()

    universe = load_universe()
    if args.limit:
        universe = universe[:args.limit]

    logging.info('Fetching fundamentals for %d symbols from Screener.in', len(universe))
    all_rows = []
    ok = 0
    for i, sym in enumerate(universe):
        rows = fetch_one(sym)
        if rows:
            all_rows.extend(rows)
            ok += 1
        if (i + 1) % 25 == 0:
            logging.info('  %d/%d done (%d ok)', i + 1, len(universe), ok)
        time.sleep(args.delay)

    logging.info('Done: %d symbols, %d total year-rows', ok, len(all_rows))

    df = pd.DataFrame(all_rows)
    OUT_PKL.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(OUT_PKL)
    df.to_csv(OUT_CSV, index=False)
    logging.info('Saved %s (%d rows) and %s', OUT_PKL.name, len(df), OUT_CSV.name)

    logging.info('\nSample (RELIANCE):')
    sample = df[df['symbol'] == 'RELIANCE'][['symbol', 'fiscal_year', 'roe', 'debt_to_equity',
                                              'revenue_growth_pct', 'earnings_growth_pct']]
    print(sample.to_string(index=False))


if __name__ == '__main__':
    main()
