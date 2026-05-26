"""Cooldown policy unit tests."""

from datetime import date
import unittest

from backtest.cooldown import CooldownPolicy, resolve_policy, should_suppress_sell


class TestCooldown(unittest.TestCase):
    def test_off_never_suppresses(self):
        p = resolve_policy('off')
        sup, _ = should_suppress_sell(
            policy=p, entry_date=date(2026, 5, 20), as_of=date(2026, 5, 22),
            profit_pct=0.05, current_v2_score=70.0, current_regime='SIDEWAYS',
        )
        self.assertFalse(sup)

    def test_prod_5d_suppresses_inside_window(self):
        p = resolve_policy('prod_5d')
        sup, reason = should_suppress_sell(
            policy=p, entry_date=date(2026, 5, 21), as_of=date(2026, 5, 25),
            profit_pct=0.04, current_v2_score=72.0, current_regime='SIDEWAYS',
            exit_reason='score below threshold',
        )
        self.assertTrue(sup)
        self.assertIn('RECENT_BUY_COOLDOWN', reason)

    def test_hard_loss_bypasses(self):
        p = resolve_policy('prod_5d')
        sup, _ = should_suppress_sell(
            policy=p, entry_date=date(2026, 5, 24), as_of=date(2026, 5, 25),
            profit_pct=-0.12, current_v2_score=50.0, current_regime='SIDEWAYS',
        )
        self.assertFalse(sup)

    def test_profit_bypass_allows_sell(self):
        p = CooldownPolicy(
            name='t', enabled=True, cooldown_days=5, profit_bypass_pct=0.03,
        )
        sup, _ = should_suppress_sell(
            policy=p, entry_date=date(2026, 5, 21), as_of=date(2026, 5, 23),
            profit_pct=0.05, current_v2_score=72.0, current_regime='SIDEWAYS',
        )
        self.assertFalse(sup)


    def test_exhaustion_reason_not_auto_bypassed(self):
        p = resolve_policy('prod_5d')
        sup, _ = should_suppress_sell(
            policy=p, entry_date=date(2026, 5, 24), as_of=date(2026, 5, 26),
            profit_pct=0.04, current_v2_score=72.0, current_regime='SIDEWAYS',
            exit_reason='MOMENTUM EXHAUSTION: RSI overbought',
        )
        self.assertTrue(sup)


if __name__ == '__main__':
    unittest.main()
