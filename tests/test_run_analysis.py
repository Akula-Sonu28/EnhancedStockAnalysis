"""Tests for scripts/run_analysis.py defaults."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_analysis import _default_analyzer_argv


class TestRunAnalysisDefaults(unittest.TestCase):
    def test_kite_auto_defaults_to_live(self):
        argv = _default_analyzer_argv(kite_auto=True)
        self.assertIn('--portfolio-amount', argv)
        self.assertNotIn('--dry-run', argv)
        self.assertNotIn('--fast', argv)

    def test_bare_invocation_defaults_to_preview(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ANALYSIS_LIVE_DEFAULT', None)
            argv = _default_analyzer_argv(kite_auto=False)
        self.assertEqual(argv, ['--dry-run', '--fast'])

    def test_env_live_default(self):
        with patch.dict(os.environ, {'ANALYSIS_LIVE_DEFAULT': 'true'}):
            argv = _default_analyzer_argv(kite_auto=False)
        self.assertIn('--portfolio-amount', argv)
        self.assertNotIn('--dry-run', argv)


if __name__ == '__main__':
    unittest.main()
