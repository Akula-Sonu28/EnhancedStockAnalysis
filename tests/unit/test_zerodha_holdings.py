"""Unit tests for Zerodha holdings → Kite CSV shape mapping."""
import unittest

from src.zerodha_holdings import (
    apply_todays_order_adjustments,
    effective_quantity,
    holdings_to_dataframe,
    kite_order_to_record,
    kite_row_to_record,
    orders_to_dataframe,
)
import pandas as pd


class TestZerodhaHoldings(unittest.TestCase):
    def test_kite_row_mapping(self):
        row = {
            "tradingsymbol": "RELIANCE",
            "quantity": 10,
            "average_price": 2500.0,
            "last_price": 2600.0,
            "pnl": 1000.0,
            "day_change_percentage": 1.5,
        }
        rec = kite_row_to_record(row)
        self.assertEqual(rec["Instrument"], "RELIANCE")
        self.assertEqual(rec["Qty."], 10.0)
        self.assertEqual(rec["Invested"], 25000.0)
        self.assertEqual(rec["Cur. val"], 26000.0)
        self.assertEqual(rec["P&L"], 1000.0)

    def test_broker_symbol_normalization(self):
        rows = [
            {
                "tradingsymbol": "GVTD",
                "quantity": 16,
                "average_price": 4732.68,
                "last_price": 4825.0,
                "pnl": 1477.15,
            }
        ]
        df = holdings_to_dataframe(rows)
        self.assertEqual(df.iloc[0]["Instrument"], "GVT&D")

    def test_order_mapping(self):
        row = {
            "tradingsymbol": "RELIANCE",
            "transaction_type": "BUY",
            "product": "CNC",
            "quantity": 10,
            "filled_quantity": 10,
            "average_price": 2500.5,
            "status": "COMPLETE",
            "order_timestamp": "2026-05-22 13:17:52",
        }
        rec = kite_order_to_record(row)
        self.assertEqual(rec["Instrument"], "RELIANCE")
        self.assertEqual(rec["Type"], "BUY")
        self.assertEqual(rec["Qty."], "10/10")
        df = orders_to_dataframe([row])
        self.assertEqual(len(df), 1)

    def test_t1_quantity_counts_as_held(self):
        row = {
            "tradingsymbol": "BSE",
            "quantity": 0,
            "t1_quantity": 13,
            "average_price": 4193.9,
            "last_price": 4279.0,
            "pnl": 1106.3,
        }
        self.assertEqual(effective_quantity(row), 13)
        rec = kite_row_to_record(row)
        self.assertEqual(rec["Qty."], 13.0)

    def test_sold_today_removed_via_orders(self):
        holdings = pd.DataFrame(
            [
                {"Instrument": "GROWW", "Qty.": 84, "Cur. val": 15960, "Invested": 15898, "P&L": 0},
                {"Instrument": "BSE", "Qty.": 13, "Cur. val": 55630, "Invested": 54520, "P&L": 1100},
            ]
        )
        orders = pd.DataFrame(
            [
                {"Time": "2026-05-25 11:03:05", "Type": "SELL", "Instrument": "GROWW", "Qty.": "84/84", "Status": "COMPLETE"},
            ]
        )
        out = apply_todays_order_adjustments(holdings, orders)
        self.assertNotIn("GROWW", out["Instrument"].values)
        self.assertIn("BSE", out["Instrument"].values)

    def test_zero_qty_filtered(self):
        df = holdings_to_dataframe(
            [{"tradingsymbol": "X", "quantity": 0, "average_price": 1, "last_price": 1}]
        )
        self.assertTrue(df.empty)


if __name__ == "__main__":
    unittest.main()
