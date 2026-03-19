#!/usr/bin/env python3
"""
Static Validator v2 — scans Layer 1 & Layer 2 Python files for 7 bug categories.
Tuned to minimize false positives.

Usage:
    python tests/static_validator.py            # scan all target files
    python tests/static_validator.py --summary  # counts only
"""
import re, sys, argparse
from pathlib import Path
from typing import List, Tuple, Dict

ROOT = Path(__file__).resolve().parent.parent

TARGET_FILES = [
    "analyze_top200_stocks_enhanced.py",
    "hybrid_optimized_scoring.py",
    "ml_predictor.py",
    "sentiment_analyzer.py",
    "volume_analyzer.py",
    "pattern_recognition.py",
    "early_breakout_detector.py",
    "market_regime_detector.py",
    "adaptive_market_strategy.py",
    "crisis_detector.py",
    "recommendation_history.py",
    "run_backtest_v2.py",
    "backtest_engine.py",
    "config.py",
    "enhanced_technical_analyzer.py",
    "src/technical_analyzer.py",
    "src/enhanced_fundamental_analyzer.py",
    "src/nse_scraper.py",
]

Issue = Tuple[str, int, str, str]


def _lines(fpath: Path) -> List[str]:
    with open(fpath, encoding="utf-8", errors="replace") as f:
        return f.readlines()


def _is_code_line(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
        return False
    if s.startswith("print(") or s.startswith("logging.") or s.startswith("self.logger"):
        return False
    if s.startswith("f\"") or s.startswith("f'"):
        return False
    return True


def _strip_comment(line: str) -> str:
    """Return line with trailing # comment removed (naively)."""
    in_sq = in_dq = False
    for j, c in enumerate(line):
        if c == "'" and not in_dq:
            in_sq = not in_sq
        elif c == '"' and not in_sq:
            in_dq = not in_dq
        elif c == '#' and not in_sq and not in_dq:
            return line[:j]
    return line


_DOCSTRING_MARKERS = ('"""', "'''")

def _in_docstring(lines: List[str], idx: int) -> bool:
    count = 0
    for j in range(idx):
        for marker in _DOCSTRING_MARKERS:
            count += lines[j].count(marker)
    return count % 2 == 1


def _in_string(line: str, col: int) -> bool:
    in_sq = False
    in_dq = False
    for j in range(col):
        c = line[j]
        if c == "'" and not in_dq:
            in_sq = not in_sq
        elif c == '"' and not in_sq:
            in_dq = not in_dq
    return in_sq or in_dq


def _in_try_block(lines: List[str], idx: int) -> bool:
    for j in range(max(0, idx - 20), idx):
        s = lines[j].strip()
        if s == "try:":
            for k in range(j + 1, min(len(lines), idx + 20)):
                if lines[k].strip().startswith("except"):
                    return True
    return False


def _has_guard(lines: List[str], idx: int, patterns: List[str], window: int = 5, forward: int = 0) -> bool:
    start = max(0, idx - window)
    end = min(len(lines), idx + 1 + forward)
    block = " ".join(l.strip() for l in lines[start:end])
    return any(p in block for p in patterns)


# ─── DIV: unguarded division by variable ─────────────────────────────

def check_div(lines: List[str], fname: str) -> List[Issue]:
    issues = []
    div_pat = re.compile(r'(?<![/=!<>])/(?![/=*])')
    guards = ["!= 0", "> 0", "<= 0", "isnan", "replace(0", "== 0", "not.*0", "max(", "or 1"]

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        if _in_docstring(lines, i):
            continue
        code = _strip_comment(line)
        for m in div_pat.finditer(code):
            col = m.start()
            if _in_string(code, col):
                continue
            after = code[col + 1:].strip()
            # Literal number denominator → safe
            if re.match(r'\s*[\d\.]+', after):
                continue
            # Denominator is 1 + something → safe (RSI formula)
            if re.match(r'\s*\(1\s*\+', after):
                continue
            before = code[:col].rstrip()
            if before.endswith(('*', '+', '-', '%')):
                continue
            # Extract denominator variable name
            denom_match = re.match(r'\s*(\w+)', after)
            if not denom_match:
                continue
            denom_var = denom_match.group(1)
            # Safe constants/builtins
            if denom_var in ('len', 'np', 'pd', 'total', 'count', 'num', 'self',
                             'max', 'min', 'abs', 'sum', 'float', 'int'):
                continue
            if _has_guard(lines, i, guards, window=6):
                continue
            if _in_try_block(lines, i):
                continue
            issues.append((fname, i + 1, "DIV", code.strip()[:120]))
    return issues


# ─── NAN_TRUTHY: val or default where val could be NaN ────────────────

def check_nan_truthy(lines: List[str], fname: str) -> List[Issue]:
    issues = []
    float_keys = re.compile(
        r"(score|ratio|price|volume|rsi|pe_|pb_|roe|debt|margin|yield|change|"
        r"adj|confidence|cap|growth|return|drawdown|volatility|profit|"
        r"earnings|revenue|momentum|strength|weight)", re.I
    )
    safe_pats = ["isnan", "is not None", "is None", "isinstance", "_sf(", "_safe_float(", "safe_float(", "_nv("]
    int_keys = {"data_quality_score", "analysis_completeness_pct"}

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        s = line.strip()

        # Pattern: float( .get(...) or NUM ) — the `or` doesn't guard NaN
        fp = re.compile(r'float\s*\(.*\.get\([^)]+\)\s+or\s+\d')
        if fp.search(s):
            if not any(p in s for p in safe_pats):
                issues.append((fname, i + 1, "NAN_TRUTHY", s[:120]))
                continue

        # Pattern: .get(...) or NUM  (outside float())
        gp = re.compile(r'\.get\([^)]+\)\s+or\s+\d')
        if gp.search(s) and float_keys.search(s):
            if not any(p in s for p in safe_pats):
                if any(k in s for k in int_keys):
                    continue
                if "float(" not in s:
                    issues.append((fname, i + 1, "NAN_TRUTHY", s[:120]))
                    continue

        # Pattern: `if var and` where var is known float
        ifp = re.compile(r'if\s+(\w+)\s+and\s+')
        m = ifp.search(s)
        if m:
            var = m.group(1)
            known_floats = {"pe", "pb", "roe", "pe_ratio", "pb_ratio", "debt",
                            "rsi", "price", "volume", "margin", "div_yield",
                            "last_pe", "current_pe", "last_roe", "current_roe",
                            "last_debt", "current_debt", "earnings_growth"}
            if var in known_floats:
                if not any(p in s for p in safe_pats):
                    # `if val and val > 0` is safe: NaN > 0 is False
                    if re.search(rf'{var}\s*[><=]', s):
                        continue
                    issues.append((fname, i + 1, "NAN_TRUTHY", s[:120]))

    return issues


# ─── UNSAFE_STR: .lower()/.upper() on potentially None ─────────────

def check_unsafe_str(lines: List[str], fname: str) -> List[Issue]:
    issues = []
    pat = re.compile(r'(\w+)\.(lower|upper|strip)\(\)')

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        s = line.strip()
        for m in pat.finditer(s):
            var = m.group(1)
            col = m.start()
            if _in_string(s, col):
                continue
            # Safe: string methods on known string types
            if var in ("self", "cls", "str", "symbol", "key", "name", "col",
                       "action", "signal", "recommendation", "status"):
                continue
            # Chained: .astype(str).str.strip() → safe
            if ".str." in s:
                continue
            # Wrapped in str()
            prefix = s[:col]
            if "str(" in prefix[-15:]:
                continue
            if "('" in prefix[-10:] or '("' in prefix[-10:]:
                continue
            # Check context for safety
            safe_ctx = ["str(" + var, var + " = str(", var + " = '", var + ' = "',
                         "or ''", 'or ""', var + " if "]
            if _has_guard(lines, i, safe_ctx, window=4):
                continue
            # Only flag if var could be None (from .get() or parameter)
            if _has_guard(lines, i, [".get(", "= None", ": str", "param"], window=10):
                issues.append((fname, i + 1, "UNSAFE_STR", s[:120]))

    return issues


# ─── UNSAFE_CAST: float()/int() on .get() without NaN handling ──────

def check_unsafe_cast(lines: List[str], fname: str) -> List[Issue]:
    issues = []
    pat = re.compile(r'(?:^|[^_a-zA-Z])(?:float|int)\s*\(.*\.get\(')

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        s = line.strip()
        if pat.search(s):
            safe = ["_sf(", "_safe_float(", "safe_float(", "isnan", "isinf",
                    "is None", "isinstance"]
            if any(p in s for p in safe):
                continue
            if _in_try_block(lines, i):
                continue
            # Only flag if looks like numeric context
            if re.search(r'float\s*\(.*\.get\(', s):
                issues.append((fname, i + 1, "UNSAFE_CAST", s[:120]))

    return issues


# ─── DICT_BRACKET: external_dict['key'] without .get() ──────────────

def check_dict_bracket(lines: List[str], fname: str) -> List[Issue]:
    issues = []
    pat = re.compile(r"(\w+)\[(['\"])(\w+)\2\]")
    ext_dicts = {"stock_data", "regime_data", "validated_data",
                 "info", "fundamentals", "prediction"}
    # "data" is excluded because it's almost always a DataFrame in this codebase
    df_indicators = [".iloc", ".rolling", ".mean()", ".sum()", ".std()", ".tail(",
                     ".head(", ".diff()", ".cumsum()", ".ffill()", ".fillna(",
                     "pd.cut", "pd.qcut", "np.where", ".pct_change()", ".dropna()",
                     ".min()", ".max()", ".shift(", ".ewm(", ".apply("]

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        s = line.strip()
        for m in pat.finditer(s):
            dictname = m.group(1)
            if dictname not in ext_dicts:
                continue
            # Assignment target → safe
            after = s[m.end():].lstrip()
            if after.startswith("=") and not after.startswith("=="):
                continue
            # DataFrame column access → safe
            if any(ind in s for ind in df_indicators):
                continue
            # Inside try block
            if _in_try_block(lines, i):
                continue
            key = m.group(3)
            if _has_guard(lines, i, ["'" + key + "' in " + dictname,
                                      '"' + key + '" in ' + dictname,
                                      dictname + ".get('" + key + "'",
                                      "if " + dictname], window=5):
                continue
            issues.append((fname, i + 1, "DICT_BRACKET", s[:120]))

    return issues


# ─── UNSAFE_ILOC: .iloc[negative] without len guard ────────────────

def check_unsafe_iloc(lines: List[str], fname: str) -> List[Issue]:
    issues = []
    pat = re.compile(r'\.iloc\[(-\d+)\]')

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        s = line.strip()
        for m in pat.finditer(s):
            idx_val = int(m.group(1))
            abs_idx = abs(idx_val)
            if abs_idx <= 1:
                continue  # iloc[-1] on non-empty data is usually safe in context
            guards = ["len(", "> " + str(abs_idx), ">= " + str(abs_idx),
                      "if not.*empty", "if len("]
            if _has_guard(lines, i, guards, window=10):
                continue
            if _in_try_block(lines, i):
                continue
            issues.append((fname, i + 1, "UNSAFE_ILOC", s[:120]))

    return issues


# ─── CLAMP_NAN: min/max clamping without isnan ──────────────────────

def check_clamp_nan(lines: List[str], fname: str) -> List[Issue]:
    issues = []
    pat = re.compile(r'(?:min|max)\s*\(\s*\d+\s*,\s*(?:min|max)\s*\(')

    for i, line in enumerate(lines):
        if not _is_code_line(line):
            continue
        s = line.strip()
        if pat.search(s):
            if "isnan" in s:
                continue
            if _has_guard(lines, i, ["isnan", "np.isnan", "_nv("], window=4, forward=3):
                continue
            # Check if the value being clamped is from safe arithmetic
            if re.search(r'(len\(|int\(|count|\.count|random|score\s*/\s*\d)', s):
                continue
            issues.append((fname, i + 1, "CLAMP_NAN", s[:120]))

    return issues


# ─── Main ────────────────────────────────────────────────────────────

ALL_CHECKS = [
    ("DIV", check_div),
    ("NAN_TRUTHY", check_nan_truthy),
    ("UNSAFE_STR", check_unsafe_str),
    ("UNSAFE_CAST", check_unsafe_cast),
    ("DICT_BRACKET", check_dict_bracket),
    ("UNSAFE_ILOC", check_unsafe_iloc),
    ("CLAMP_NAN", check_clamp_nan),
]


def run(summary_only: bool = False) -> Dict[str, List[Issue]]:
    all_issues: Dict[str, List[Issue]] = {}
    for rel in TARGET_FILES:
        fpath = ROOT / rel
        if not fpath.exists():
            print(f"  SKIP (not found): {rel}")
            continue
        file_lines = _lines(fpath)
        file_issues: List[Issue] = []
        for _name, checker in ALL_CHECKS:
            file_issues.extend(checker(file_lines, rel))
        if file_issues:
            all_issues[rel] = file_issues

    total = sum(len(v) for v in all_issues.values())
    cats: Dict[str, int] = {}
    for iss in all_issues.values():
        for _, _, cat, _ in iss:
            cats[cat] = cats.get(cat, 0) + 1

    print("=" * 80)
    print(f"  STATIC VALIDATOR — {total} issues across {len(all_issues)} files")
    print("=" * 80)
    print()
    print("  Category Breakdown:")
    for cat in ["DIV", "NAN_TRUTHY", "UNSAFE_STR", "UNSAFE_CAST",
                "DICT_BRACKET", "UNSAFE_ILOC", "CLAMP_NAN"]:
        c = cats.get(cat, 0)
        bar = "#" * min(c, 50)
        print(f"    {cat:15s} : {c:3d}  {bar}")
    print()

    if not summary_only:
        for fname, iss in sorted(all_issues.items()):
            print(f"  --- {fname} ({len(iss)} issues) ---")
            for _, line_no, cat, snippet in sorted(iss, key=lambda x: x[1]):
                print(f"    L{line_no:5d} [{cat:13s}] {snippet}")
            print()

    if total == 0:
        print("  *** ALL CLEAN — 0 ISSUES ***")
    print("=" * 80)
    return all_issues


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    issues = run(summary_only=args.summary)
    sys.exit(0 if not issues else 1)
