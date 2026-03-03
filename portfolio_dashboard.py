"""
portfolio_dashboard.py  — v2.0
===============================
Generates a rich, interactive HTML Portfolio Guide from the latest report.
Run:  python portfolio_dashboard.py
"""

import pandas as pd
import glob
import os
import webbrowser
import math
import json
import re

# ── Find latest report ────────────────────────────────────────────────────────
files = sorted([f for f in glob.glob("reports/*.xlsx") if not os.path.basename(f).startswith("~$")])
if not files:
    print("❌ No report found in reports/. Run the main analysis first.")
    exit(1)
report_path = files[-1]
report_name = os.path.basename(report_path)
print(f"📊 Reading: {report_name}")

df = pd.read_excel(report_path, sheet_name="Portfolio Allocation")

# ── Normalise ₹ encoding ──────────────────────────────────────────────────────
df.rename(columns={c: c.replace("Γé╣","₹") for c in df.columns}, inplace=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def s(v, d="—"):
    if v is None: return d
    try:
        if math.isnan(float(v)) if isinstance(v,(int,float)) else False: return d
    except: pass
    sv = str(v).strip()
    return d if sv in ("","nan","NaN","None") else sv

def rs(v, d="—"):
    try: return f"₹{float(v):,.0f}" if float(v) != 0 else d
    except: return d

def pct(v, mult=False, d="—"):
    try:
        f = float(v)*(100 if mult else 1)
        return f"{f:+.2f}%"
    except: return d

def num(v, dec=1, d="—"):
    try: return f"{float(v):.{dec}f}"
    except: return d

def clean_signals(raw):
    """Decode garbled emoji bytes then split by pipe"""
    if not raw or str(raw).strip() in ("","nan","NONE","None"): return []
    t = str(raw)
    replacements = [
        ("≡ƒÄ»","🎯"), ("≡ƒôè","📊"), ("ΓÜá∩╕Å","⚠️"), ("Γ√°","⚡"),
        ("≡ƒÆÄ","💎"), ("Γ¡É","⭐"), ("≡ƒôê","📈"), ("≡ƒÄ¿","🔍"),
        ("ΓÜí","⚡"), ("Γ£à","✅"), ("Γ£ü","❌"), ("≡ƒÜÇ","🚀"),
        ("≡ƒôÿ","📉"), ("≡ƒÜá","🔥"), ("≡ƒô╢","📆"),
        ("ΓÇö","—"), ("ΓÇô","–"),
    ]
    for old, new in replacements: t = t.replace(old, new)
    parts = [p.strip() for p in re.split(r"\s*\|\s*", t) if p.strip()]
    return parts

def action_meta(raw):
    a = str(raw).upper()
    if "PRE-BREAKOUT" in a:
        return "PRE_BREAKOUT","🚀 PRE-BREAKOUT BUY","#1565C0","#E3F2FD","Buy BEFORE the breakout. Price is very close to resistance. Once it breaks, rapid gains follow."
    if "SWAP" in a:
        tgt = str(raw).split("->")[-1].strip() if "->" in str(raw) else "?"
        return "SWAP",f"🔄 SWAP → {tgt}","#E65100","#FFF3E0",f"Sell this stock → immediately buy <b>{tgt}</b>. Your money upgrades to a better opportunity."
    if "SELL" in a:
        return "SELL","🔴 SELL","#B71C1C","#FFEBEE","Exit this position now. Take profits or cut losses before they deepen."
    if "INCREASE" in a:
        return "INCREASE","📈 INCREASE","#1B5E20","#E8F5E9","Already in profit — add more shares to ride the momentum higher."
    if "NEW POSITION" in a:
        return "NEW","🆕 NEW POSITION","#0D47A1","#E3F2FD","Fresh entry. Strong signals say this is a good time to build a new position."
    if "HOLD" in a:
        return "HOLD","🟡 HOLD","#F57F17","#FFFDE7","Do nothing. Keep existing shares, no buys, no sells. Wait for a clearer signal."
    if "KEEP" in a:
        return "KEEP","🤝 KEEP","#4A148C","#F3E5F5","Hold your existing shares. No urgency. Similar to HOLD."
    if "SKIP" in a:
        return "SKIP","⬜ SKIP","#546E7A","#ECEFF1","Not worth acting on right now. Revisit next week."
    return "OTHER",str(raw)[:30],"#455A64","#ECEFF1","Review manually."

def score_bars_html(fund, mom, val, total):
    def bar(label, v, color):
        try: w = min(float(v), 100)
        except: w = 0
        return f"""<div style="margin-bottom:6px">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:#555;margin-bottom:2px">
            <span>{label}</span><span style="font-weight:700;color:{color}">{num(v,0)}/100</span>
          </div>
          <div style="background:#e9ecef;border-radius:4px;height:6px">
            <div style="background:{color};width:{w:.0f}%;height:6px;border-radius:4px"></div>
          </div>
        </div>"""
    def total_bar(v):
        try: w = min(float(v), 100)
        except: w = 0
        color = "#27ae60" if w>=70 else "#f39c12" if w>=50 else "#e74c3c"
        return f"""<div style="margin-top:8px;padding-top:8px;border-top:1px solid #dee2e6">
          <div style="display:flex;justify-content:space-between;font-size:12px;font-weight:700;margin-bottom:3px">
            <span>Overall Score</span><span style="color:{color}">{num(v,1)}/100</span>
          </div>
          <div style="background:#e9ecef;border-radius:6px;height:10px">
            <div style="background:{color};width:{w:.0f}%;height:10px;border-radius:6px"></div>
          </div>
        </div>"""
    return (bar("Fundamentals", fund, "#1565C0") +
            bar("Momentum",     mom,  "#6A1B9A") +
            bar("Value",        val,  "#00695C") +
            total_bar(total))

def rsi_html(v):
    try:
        r = float(v)
        if r > 70:   col,lbl = "#C62828","🔴 Overbought"
        elif r < 30: col,lbl = "#2E7D32","🟢 Oversold"
        else:        col,lbl = "#F57F17","🟡 Neutral"
        return f'<span style="background:{col};color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600">{r:.0f} — {lbl}</span>'
    except: return "—"

def price_range_html(price, lo, hi):
    try:
        p,l,h = float(price), float(lo), float(hi)
        pct_pos = (p-l)/(h-l)*100 if h>l else 50
        color = "#27ae60" if pct_pos < 40 else "#f39c12" if pct_pos < 75 else "#e74c3c"
        return f"""<div>
          <span style="font-size:18px;font-weight:800;color:{color}">₹{p:.2f}</span>
          <div style="margin-top:5px;position:relative;background:#e9ecef;border-radius:6px;height:8px;width:100%">
            <div style="position:absolute;left:{pct_pos:.0f}%;top:-3px;width:14px;height:14px;background:{color};border-radius:50%;transform:translateX(-50%);border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.3)"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:10px;color:#888;margin-top:6px">
            <span>52W Low ₹{l:.0f}</span><span>52W High ₹{h:.0f}</span>
          </div>
        </div>"""
    except: return rs(price)

def ml_html(sig, conf):
    col = {"BUY":"#1B5E20","SELL":"#B71C1C","HOLD":"#F57F17"}.get(str(sig).upper(),"#546E7A")
    try: bar_w = min(float(conf),100)
    except: bar_w = 0
    return f"""<span style="background:{col};color:white;padding:3px 8px;border-radius:10px;font-size:12px;font-weight:700">{s(sig)}</span>
    <span style="font-size:11px;color:#666;margin-left:4px">{num(conf,1)}% confident</span>
    <div style="background:#e9ecef;border-radius:4px;height:4px;margin-top:4px">
      <div style="background:{col};width:{bar_w:.0f}%;height:4px;border-radius:4px"></div>
    </div>"""

def breakout_html(bp):
    try:
        b = min(float(bp),100)
        col = "#27ae60" if b>=80 else "#f39c12" if b>=60 else "#e74c3c"
        return f"""<div style="display:flex;align-items:center;gap:8px">
          <div style="flex:1;background:#e9ecef;border-radius:6px;height:10px">
            <div style="background:{col};width:{b:.0f}%;height:10px;border-radius:6px"></div>
          </div>
          <span style="font-weight:700;color:{col};font-size:13px">{b:.0f}%</span>
        </div>"""
    except: return "—"

# ── Build per-stock card ──────────────────────────────────────────────────────
def make_card(row, idx):
    sym   = s(row.get("symbol"),"?")
    name  = s(row.get("company_name"), sym)
    raw_a = s(row.get("ACTION"),"HOLD")
    atype, alabel, acol, abg, adesc = action_meta(raw_a)
    when  = s(row.get("WHEN_TO_ACT"))

    price = row.get("PRICE", 0)
    hi52  = row.get("52W_HIGH", 0)
    lo52  = row.get("52W_LOW", 0)
    rsi   = row.get("RSI")
    risk  = s(row.get("RISK"),"—")
    sector= s(row.get("sector"),"—")
    chg20 = row.get("20D_CHANGE_%")
    vol   = row.get("VOLATILITY_%")

    score      = row.get("SCORE")
    fund_sc    = row.get("FUND_SCORE")
    mom_sc     = row.get("MOM_SCORE")
    val_sc     = row.get("VALUE_SCORE")

    pe   = row.get("PE")
    roe  = row.get("ROE_%")
    de   = row.get("DEBT/EQUITY")

    my_sh  = row.get("MY_SHARES", 0)
    my_val = row.get("MY_VALUE_₹", 0)
    my_pnl = row.get("MY_PROFIT_%", 0)

    invest    = row.get("INVEST_₹", 0)
    buy_sh    = row.get("BUY_SHARES", 0)
    book_pct  = row.get("BOOK_%_IF_SELL")
    book_rs   = row.get("BOOK_₹_AMOUNT", 0)
    stop_loss = row.get("STOP_LOSS")
    sup       = row.get("SUPPORT")
    res       = row.get("RESISTANCE")
    bp        = row.get("BREAKOUT_%")

    ml_sig  = row.get("ML_SIGNAL","—")
    ml_conf = row.get("ML_CONF_%", 0)
    ml_adj  = row.get("ML_ADJ", 0)
    sec_adj = row.get("SECTOR_ADJ", 0)
    sent_adj= row.get("SENT_ADJ", 0)
    vol_adj = row.get("VOL_ADJ", 0)
    pat_adj = row.get("PATTERN_ADJ", 0)

    rot_tgt = s(row.get("ROTATION_TARGET"))
    rot_trg = row.get("ROTATION_TRIGGER_PRICE")

    setup_parts = clean_signals(row.get("SETUP_SIGNALS"))
    exit_parts  = clean_signals(row.get("EXIT_SIGNALS"))
    why_raw     = s(row.get("WHY"),"")
    exhaust     = str(row.get("EXHAUSTION?","0")) not in ("0","0.0","False","nan","")

    # ── My Holding ────────────────────────────────────────────────────────────
    holding_html = ""
    try:
        if float(str(my_sh)) > 0:
            pnl_f = float(my_pnl)*100
            pnl_col = "#1B5E20" if pnl_f >= 0 else "#B71C1C"
            pnl_icon = "▲" if pnl_f >= 0 else "▼"
            pnl_lbl = f"{pnl_icon} {abs(pnl_f):.2f}%"
            pnl_rupees_est = float(my_val)*abs(pnl_f)/100*(1 if pnl_f>=0 else -1)
            pnl_rs_lbl = f"{'Gain' if pnl_f>=0 else 'Loss'}: {rs(pnl_rupees_est)}"

            sl_html = ""
            try:
                sl_f = float(stop_loss)
                if sl_f > 0:
                    sl_html = f"""
                    <div style="background:#FFEBEE;border:1px solid #EF9A9A;border-radius:6px;padding:8px 12px;margin-top:8px;display:flex;align-items:center;gap:8px">
                      <span style="font-size:18px">🛑</span>
                      <div>
                        <div style="font-size:11px;color:#B71C1C;font-weight:700;text-transform:uppercase;letter-spacing:.5px">Stop Loss — Exit if price drops to:</div>
                        <div style="font-size:18px;font-weight:800;color:#B71C1C">₹{sl_f:.2f}</div>
                        <div style="font-size:11px;color:#C62828">Set a price alert at this level in your broker app</div>
                      </div>
                    </div>"""
            except: pass

            holding_html = f"""
            <div style="background:#F8F9FA;border-left:4px solid #1565C0;border-radius:0 8px 8px 0;padding:12px 16px;margin:10px 0">
              <div style="font-size:11px;font-weight:700;color:#1565C0;text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">📦 Your Current Holding</div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px" class="card-3col">
                <div><div style="font-size:10px;color:#888;text-transform:uppercase">Shares Owned</div>
                     <div style="font-size:20px;font-weight:800;color:#1A237E">{int(float(my_sh))}</div></div>
                <div><div style="font-size:10px;color:#888;text-transform:uppercase">Current Value</div>
                     <div style="font-size:18px;font-weight:800;color:#1A237E">{rs(my_val)}</div></div>
                <div><div style="font-size:10px;color:#888;text-transform:uppercase">Profit / Loss</div>
                     <div style="font-size:18px;font-weight:800;color:{pnl_col}">{pnl_lbl}</div>
                     <div style="font-size:11px;color:{pnl_col}">{pnl_rs_lbl}</div></div>
              </div>
              {sl_html}
            </div>"""
    except: pass

    # ── Action instruction box ────────────────────────────────────────────────
    action_html = ""
    if atype == "SELL":
        try:
            sh_int = int(float(my_sh)); val_f = float(my_val); price_f = float(price)
            pnl_f  = float(my_pnl)*100
            pnl_str= f"(+{pnl_f:.1f}% profit)" if pnl_f>=0 else f"({pnl_f:.1f}% loss)"
            action_html = f"""
            <div style="background:#FFEBEE;border:2px solid #EF5350;border-radius:10px;padding:14px;margin:10px 0">
              <div style="font-size:13px;font-weight:800;color:#B71C1C;margin-bottom:10px">🔴 HOW TO SELL THIS STOCK</div>
              <table style="width:100%;font-size:13px;border-collapse:collapse">
                <tr><td style="padding:4px 8px;color:#555">Sell ALL shares:</td>
                    <td style="padding:4px 8px;font-weight:700">{sh_int} shares of {sym}</td></tr>
                <tr style="background:#fff5f5"><td style="padding:4px 8px;color:#555">At current price:</td>
                    <td style="padding:4px 8px;font-weight:700">₹{price_f:.2f} per share</td></tr>
                <tr><td style="padding:4px 8px;color:#555">You will receive:</td>
                    <td style="padding:4px 8px;font-weight:700;color:#B71C1C">{rs(val_f)} {pnl_str}</td></tr>
                <tr style="background:#fff5f5"><td style="padding:4px 8px;color:#555">Act by:</td>
                    <td style="padding:4px 8px;font-weight:700;color:#E53935">{when}</td></tr>
              </table>
            </div>"""
        except: pass

    elif atype == "SWAP":
        try:
            sh_int = int(float(my_sh)); val_f = float(my_val); price_f = float(price)
            pnl_f  = float(my_pnl)*100
            pnl_str= f"(+{pnl_f:.1f}% profit)" if pnl_f>=0 else f"({pnl_f:.1f}% loss)"
            tgt    = str(raw_a).split("->")[-1].strip() if "->" in str(raw_a) else rot_tgt
            rot_price_str = f" near ₹{float(rot_trg):.2f}" if rot_trg and str(rot_trg) not in ("nan","—") else ""
            action_html = f"""
            <div style="background:#FFF3E0;border:2px solid #FF9800;border-radius:10px;padding:14px;margin:10px 0">
              <div style="font-size:13px;font-weight:800;color:#E65100;margin-bottom:10px">🔄 SWAP STEP-BY-STEP INSTRUCTIONS</div>
              <div style="display:flex;flex-direction:column;gap:8px">
                <div style="background:white;border-radius:8px;padding:10px;display:flex;align-items:flex-start;gap:10px">
                  <span style="font-size:20px;min-width:28px;text-align:center">1️⃣</span>
                  <div><b>SELL {sym}</b> — Place a SELL order for {sh_int} shares at ₹{price_f:.2f}<br>
                  <span style="color:#666;font-size:12px">You'll receive approx. {rs(val_f)} {pnl_str}</span></div>
                </div>
                <div style="background:white;border-radius:8px;padding:10px;display:flex;align-items:flex-start;gap:10px">
                  <span style="font-size:20px;min-width:28px;text-align:center">2️⃣</span>
                  <div><b>BUY {tgt}</b> — Use proceeds to buy <b>{tgt}</b>{rot_price_str}<br>
                  <span style="color:#666;font-size:12px">Check the {tgt} card for exact shares and price</span></div>
                </div>
                <div style="background:#FFF8E1;border-radius:8px;padding:10px;display:flex;align-items:flex-start;gap:10px">
                  <span style="font-size:20px;min-width:28px;text-align:center">⏰</span>
                  <div><b>Timeline:</b> {when}<br>
                  <span style="color:#666;font-size:12px">Why swap? {s(why_raw,"Better opportunity available")}</span></div>
                </div>
              </div>
            </div>"""
        except: pass

    elif atype in ("PRE_BREAKOUT","NEW","INCREASE"):
        try:
            inv_f   = float(invest); sh_int = int(float(buy_sh)); price_f = float(price)
            res_f   = float(res)
            pct_to_res = (res_f-price_f)/price_f*100 if price_f>0 else 0
            col  = "#1565C0" if atype=="PRE_BREAKOUT" else "#1B5E20"
            icon = "🚀" if atype=="PRE_BREAKOUT" else "🆕" if atype=="NEW" else "📈"
            action_html = f"""
            <div style="background:#E3F2FD;border:2px solid #42A5F5;border-radius:10px;padding:14px;margin:10px 0">
              <div style="font-size:13px;font-weight:800;color:{col};margin-bottom:10px">{icon} HOW TO BUY THIS STOCK</div>
              <table style="width:100%;font-size:13px;border-collapse:collapse">
                <tr><td style="padding:4px 8px;color:#555">Amount to invest:</td>
                    <td style="padding:4px 8px;font-weight:700;font-size:16px;color:{col}">{rs(inv_f)}</td></tr>
                <tr style="background:#F3F8FF"><td style="padding:4px 8px;color:#555">Number of shares:</td>
                    <td style="padding:4px 8px;font-weight:700">{sh_int} shares</td></tr>
                <tr><td style="padding:4px 8px;color:#555">At current price:</td>
                    <td style="padding:4px 8px;font-weight:700">₹{price_f:.2f} per share</td></tr>
                <tr style="background:#F3F8FF"><td style="padding:4px 8px;color:#555">Resistance target:</td>
                    <td style="padding:4px 8px;font-weight:700">₹{res_f:.2f} (+{pct_to_res:.1f}% upside)</td></tr>
                {"<tr><td style='padding:4px 8px;color:#555'>Act by:</td><td style='padding:4px 8px;font-weight:700;color:#E53935'>" + when + "</td></tr>" if when != "—" else ""}
              </table>
            </div>"""
        except: pass

    # ── Profit booking ────────────────────────────────────────────────────────
    booking_html = ""
    try:
        bp_f = float(book_pct)
        if bp_f > 0:
            booking_html = f"""
            <div style="background:#F3E5F5;border-left:4px solid #9C27B0;padding:10px 14px;border-radius:0 8px 8px 0;margin:8px 0">
              <div style="font-size:11px;font-weight:700;color:#6A1B9A;text-transform:uppercase;margin-bottom:4px">💰 Profit Booking Guide</div>
              <span style="font-size:13px">Book <b>{bp_f:.0f}%</b> of your holding
              {"= approximately <b>" + rs(book_rs) + "</b>" if float(book_rs)>0 else ""}</span>
              <div style="font-size:11px;color:#777;margin-top:3px">Sell {bp_f:.0f}% of shares, keep the rest for further gains</div>
            </div>"""
    except: pass

    # ── Setup signals ──────────────────────────────────────────────────────────
    setup_html = ""
    if setup_parts:
        items = "".join(f'<li style="padding:3px 0;font-size:12px;color:#333">{p}</li>' for p in setup_parts)
        setup_html = f"""
        <div style="margin-top:8px">
          <div style="font-size:11px;font-weight:700;color:#1565C0;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px">📡 Setup Signals</div>
          <ul style="padding-left:18px;margin:0">{items}</ul>
        </div>"""

    # ── Exit signals ───────────────────────────────────────────────────────────
    exit_html = ""
    if exit_parts and exit_parts != ["NONE"]:
        items = "".join(f'<li style="padding:3px 0;font-size:12px;color:#B71C1C">{p}</li>' for p in exit_parts)
        exit_html = f"""
        <div style="margin-top:8px;background:#FFEBEE;padding:8px 12px;border-radius:6px">
          <div style="font-size:11px;font-weight:700;color:#B71C1C;text-transform:uppercase;margin-bottom:4px">⚠️ Exit Warning Signals</div>
          <ul style="padding-left:18px;margin:0">{items}</ul>
        </div>"""

    # ── Exhaustion warning ────────────────────────────────────────────────────
    exhaust_html = ""
    if exhaust:
        exhaust_html = """<div style="background:#FFF3E0;border:1px solid #FF9800;border-radius:6px;padding:8px 12px;margin-top:6px;font-size:12px;color:#E65100">
          ⚠️ <b>Rally Exhaustion Detected</b> — Recent uptrend is losing momentum. Be cautious about buying more.
        </div>"""

    # ── WHY note ──────────────────────────────────────────────────────────────
    why_html = ""
    if why_raw and why_raw != "—":
        why_clean = re.sub(r'[Γé╣≡ƒÜÇ≡ƒôÿΓ£àΓ£ü]', '', why_raw)
        why_html = f"""<div style="background:#F5F5F5;border-radius:6px;padding:8px 12px;margin-top:6px;font-size:12px;color:#444">
          <b>ℹ️ Reason:</b> {why_clean}
        </div>"""

    # ── Score adjustments ──────────────────────────────────────────────────────
    adj_html = ""
    adjs = []
    try:
        if float(ml_adj)  != 0: adjs.append(f"AI Model: {float(ml_adj):+.1f}")
        if float(sec_adj) != 0: adjs.append(f"Sector: {float(sec_adj):+.1f}")
        if float(sent_adj)!= 0: adjs.append(f"Sentiment: {float(sent_adj):+.1f}")
        if float(vol_adj) != 0: adjs.append(f"Volume: {float(vol_adj):+.1f}")
        if float(pat_adj) != 0: adjs.append(f"Pattern: {float(pat_adj):+.1f}")
    except: pass
    if adjs:
        items = " &nbsp;|&nbsp; ".join(
            f'<span style="font-size:11px;background:#ecf0f1;padding:2px 6px;border-radius:8px">{a}</span>'
            for a in adjs)
        adj_html = f'<div style="margin-top:6px"><div style="font-size:10px;color:#888;text-transform:uppercase;margin-bottom:4px">Score Adjustments</div>{items}</div>'

    # ── Risk badge colour ─────────────────────────────────────────────────────
    risk_colors = {"LOW":"#1B5E20","MEDIUM":"#F57F17","MODERATE":"#F57F17","HIGH":"#B71C1C"}
    risk_col = risk_colors.get(str(risk).upper(), "#546E7A")

    # ── Breakout probability bar ───────────────────────────────────────────────
    bp_html = ""
    if atype in ("PRE_BREAKOUT","SWAP","SELL","NEW"):
        bp_html = f"""
        <div style="background:#F8F9FA;padding:10px;border-radius:8px">
          <div style="font-size:10px;color:#888;text-transform:uppercase;margin-bottom:4px">Breakout Probability</div>
          {breakout_html(bp)}
        </div>"""

    # ── 20D change colour ──────────────────────────────────────────────────────
    try:
        chg_col = "#1B5E20" if float(chg20) >= 0 else "#B71C1C"
    except:
        chg_col = "#546E7A"

    return f"""
    <div class="stock-card" data-action="{atype}" data-sym="{sym}" data-sector="{sector}"
         style="background:white;border-radius:14px;box-shadow:0 2px 16px rgba(0,0,0,.08);
                margin-bottom:20px;overflow:hidden;border-top:4px solid {acol}">

      <!-- HEADER -->
      <div style="background:{abg};padding:14px 18px;display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
        <div>
          <span style="font-size:24px;font-weight:900;color:{acol}">{sym}</span>
          <span style="font-size:13px;color:#555;margin-left:8px">{name}</span><br>
          <span style="font-size:11px;background:white;color:#555;padding:2px 8px;border-radius:10px;margin-top:4px;display:inline-block">{sector}</span>
          <span style="font-size:11px;background:{risk_col};color:white;padding:2px 8px;border-radius:10px;margin-left:4px;display:inline-block">{risk}</span>
          {"<span style='font-size:11px;background:#FF6F00;color:white;padding:2px 8px;border-radius:10px;margin-left:4px;display:inline-block'>🔥 Rally Exhausting</span>" if exhaust else ""}
        </div>
        <div style="text-align:right">
          <div style="font-size:14px;font-weight:800;color:{acol};background:white;padding:7px 16px;border-radius:20px;border:2px solid {acol}">{alabel}</div>
          {"<div style='font-size:11px;color:#E53935;font-weight:700;margin-top:4px'>⏰ " + when + "</div>" if when != "—" else ""}
        </div>
      </div>

      <!-- ACTION DESC -->
      <div style="background:{abg}aa;padding:8px 18px;font-size:13px;color:#333;border-bottom:1px solid #eee">
        💡 {adesc}
      </div>

      <!-- BODY -->
      <div style="padding:14px 18px">

        {holding_html}
        {action_html}
        {booking_html}
        {why_html}

        <!-- PRICE + SCORES -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0" class="card-2col">

          <div style="background:#F8F9FA;padding:12px;border-radius:10px">
            <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Current Price &amp; 52-Week Range</div>
            {price_range_html(price, lo52, hi52)}
          </div>

          <div style="background:#F8F9FA;padding:12px;border-radius:10px">
            <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Score Breakdown</div>
            {score_bars_html(fund_sc, mom_sc, val_sc, score)}
          </div>

        </div>

        <!-- INDICATORS -->
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0" class="card-3col">

          <div style="background:#F8F9FA;padding:10px;border-radius:8px">
            <div style="font-size:10px;color:#888;text-transform:uppercase;margin-bottom:6px">RSI</div>
            {rsi_html(rsi)}
          </div>

          <div style="background:#F8F9FA;padding:10px;border-radius:8px">
            <div style="font-size:10px;color:#888;text-transform:uppercase;margin-bottom:6px">AI Signal</div>
            {ml_html(ml_sig, ml_conf)}
          </div>

          <div style="background:#F8F9FA;padding:10px;border-radius:8px">
            <div style="font-size:10px;color:#888;text-transform:uppercase;margin-bottom:6px">20-Day Change</div>
            <div style="font-size:16px;font-weight:800;color:{chg_col}">{pct(chg20)}</div>
          </div>

        </div>

        {bp_html}

        <!-- FUNDAMENTALS CHIPS -->
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0">
          <div style="background:#E8EAF6;padding:7px 12px;border-radius:8px;font-size:12px"><b>PE</b> {num(pe,1)}</div>
          <div style="background:#E8F5E9;padding:7px 12px;border-radius:8px;font-size:12px"><b>ROE</b> {num(roe,1)}%</div>
          <div style="background:#FCE4EC;padding:7px 12px;border-radius:8px;font-size:12px"><b>Debt/Eq</b> {num(de,2)}</div>
          <div style="background:#FFF3E0;padding:7px 12px;border-radius:8px;font-size:12px"><b>Volatility</b> {num(vol,1)}%</div>
          <div style="background:#E0F7FA;padding:7px 12px;border-radius:8px;font-size:12px"><b>Support</b> {rs(sup)}</div>
          <div style="background:#E0F7FA;padding:7px 12px;border-radius:8px;font-size:12px"><b>Resistance</b> {rs(res)}</div>
        </div>

        {adj_html}
        {setup_html}
        {exit_html}
        {exhaust_html}

      </div>
    </div>"""

# ── Portfolio summary stats ───────────────────────────────────────────────────
owned_df  = df[df["MY_SHARES"].fillna(0).astype(float) > 0]
total_val = owned_df["MY_VALUE_₹"].fillna(0).astype(float).sum()
gainers   = len(owned_df[owned_df["MY_PROFIT_%"].fillna(0).astype(float) > 0])
losers    = len(owned_df[owned_df["MY_PROFIT_%"].fillna(0).astype(float) < 0])
best_row  = owned_df.loc[owned_df["MY_PROFIT_%"].fillna(0).astype(float).idxmax()] if len(owned_df) else None
worst_row = owned_df.loc[owned_df["MY_PROFIT_%"].fillna(0).astype(float).idxmin()] if len(owned_df) else None
best_str  = f"{s(best_row['symbol'],'?')} (+{float(best_row['MY_PROFIT_%'])*100:.1f}%)" if best_row is not None else "—"
worst_str = f"{s(worst_row['symbol'],'?')} ({float(worst_row['MY_PROFIT_%'])*100:.1f}%)" if worst_row is not None else "—"

def atype_of(r):
    a = str(r.get("ACTION","")).upper()
    if "PRE-BREAKOUT" in a: return "PRE_BREAKOUT"
    if "SWAP"         in a: return "SWAP"
    if "SELL"         in a: return "SELL"
    if "INCREASE"     in a: return "INCREASE"
    if "NEW POSITION" in a: return "NEW"
    if "HOLD"         in a: return "HOLD"
    if "KEEP"         in a: return "KEEP"
    if "SKIP"         in a: return "SKIP"
    return "OTHER"

action_counts = {}
for _, r in df.iterrows():
    k = atype_of(r.to_dict())
    action_counts[k] = action_counts.get(k,0)+1

# ── Build all cards HTML ──────────────────────────────────────────────────────
all_cards_html = ""
for i, (_, row) in enumerate(df.iterrows()):
    all_cards_html += make_card(row.to_dict(), i)

urgent_count = action_counts.get("SELL",0) + action_counts.get("SWAP",0)
buy_count    = action_counts.get("PRE_BREAKOUT",0) + action_counts.get("NEW",0) + action_counts.get("INCREASE",0)

# ── Filter buttons ────────────────────────────────────────────────────────────
filter_defs = [
    ("ALL",        "⬤ All",           "#455A64"),
    ("SELL",       "🔴 Sell",          "#B71C1C"),
    ("SWAP",       "🔄 Swap",          "#E65100"),
    ("PRE_BREAKOUT","🚀 Pre-Breakout", "#1565C0"),
    ("NEW",        "🆕 New",           "#0D47A1"),
    ("INCREASE",   "📈 Increase",      "#1B5E20"),
    ("HOLD",       "🟡 Hold",          "#F57F17"),
    ("KEEP",       "🤝 Keep",          "#4A148C"),
    ("SKIP",       "⬜ Skip",          "#546E7A"),
]
filter_btns = ""
for akey, albl, acol in filter_defs:
    cnt = action_counts.get(akey, len(df)) if akey != "ALL" else len(df)
    filter_btns += f"""<button onclick="filterCards('{akey}')" id="btn-{akey}"
      style="background:#F5F5F5;border:2px solid {acol};color:{acol};padding:7px 14px;
             border-radius:20px;cursor:pointer;font-size:13px;font-weight:600;transition:all .2s">
      {albl} <span style="font-size:11px;opacity:.8">({cnt})</span></button>"""

# ── Glossary HTML ─────────────────────────────────────────────────────────────
glossary = [
    ("SCORE",           "0–100",    "#1565C0", "Overall stock quality. Considers fundamentals, momentum and value. 80+ is excellent."),
    ("FUND_SCORE",      "0–100",    "#0D47A1", "Fundamentals score — PE ratio, ROE, Debt levels, financial health."),
    ("MOM_SCORE",       "0–100",    "#6A1B9A", "Momentum score — how strongly the stock has been trending recently."),
    ("VALUE_SCORE",     "0–100",    "#00695C", "Value score — is the stock cheap relative to earnings and assets?"),
    ("RSI",             "0–100",    "#9C27B0", "Relative Strength Index. >70 = overbought (may fall). <30 = oversold (may rise). 40–65 = healthy zone."),
    ("SUPPORT",         "₹ price",  "#27AE60", "Floor price where buyers step in strongly. Strong stocks bounce off support repeatedly."),
    ("RESISTANCE",      "₹ price",  "#E74C3C", "Ceiling price where sellers dominate. PRE-BREAKOUT = price is about to crack this ceiling."),
    ("STOP LOSS",       "₹ price",  "#C62828", "Your safety net. If price drops here — exit immediately. Always set a price alert in your broker."),
    ("52W RANGE BAR",   "Visual",   "#2980B9", "Blue dot on the slider = current price between 52-week low and high. Near left = cheap, near right = expensive."),
    ("BREAKOUT %",      "0–100%",   "#1B5E20", "Probability the stock breaks above resistance. 80%+ = high-confidence breakout setup."),
    ("BOOK % IF SELL",  "Percent",  "#8E24AA", "Don't sell everything. Book this % and keep the rest riding. E.g., 50% = sell half."),
    ("ML SIGNAL",       "BUY/SELL/HOLD","#1A237E","AI model prediction from 65 technical features. Confidence bar shows how sure the model is."),
    ("PE RATIO",        "Number",   "#16A085", "Price-to-Earnings. Lower = cheaper stock. Under 12 for PSU banks is cheap. Over 35 is expensive."),
    ("ROE %",           "Percent",  "#117A65", "Return on Equity. How efficiently the company uses shareholder money. 15%+ is healthy."),
    ("DEBT/EQUITY",     "Ratio",    "#C62828", "0 for banks (normal). For others: under 1 is healthy, over 2 is risky."),
    ("VOLATILITY %",    "Percent",  "#E67E22", "Daily price swing range. 15–25% = moderate. Over 40% = high risk / high reward."),
    ("20D CHANGE %",    "Percent",  "#2ECC71", "Price change over last 20 trading days (~1 month). Shows recent momentum."),
    ("SWAP TARGET",     "Symbol",   "#FF6F00", "Sell the current stock and immediately buy this target. Money moves to a better-ranked opportunity."),
    ("EXHAUSTION",      "Flag",     "#D32F2F", "Recent rally is running out of steam. Buyers are tired. Avoid adding more right now."),
    ("SENT_ADJ",        "+/- pts",  "#0288D1", "Sentiment score adjustment — positive if news/social mood is bullish on this stock."),
    ("PATTERN_ADJ",     "+/- pts",  "#0277BD", "Chart pattern bonus. Recognises 15+ patterns like head-and-shoulders, flags, triangles."),
]
glos_html = "".join(f"""<div style="background:white;border-radius:10px;padding:12px 16px;border-left:4px solid {c};box-shadow:0 1px 6px rgba(0,0,0,.07)">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
    <span style="font-weight:800;font-size:14px;color:{c}">{t}</span>
    <span style="font-size:10px;background:#F5F5F5;padding:2px 8px;border-radius:8px;color:#666">{u}</span>
  </div>
  <div style="font-size:13px;color:#444;line-height:1.5">{d}</div>
</div>""" for t,u,c,d in glossary)

# ── Cheat sheet HTML ──────────────────────────────────────────────────────────
cheat_rows_data = [
    ("🔴 SELL",         "Exit position",              "Sell all MY_SHARES. Capture value before it falls."),
    ("🔄 SWAP → XYZ",   "Move money to better stock", "Sell this → buy XYZ immediately with proceeds."),
    ("🚀 PRE-BREAKOUT", "Time-sensitive buy",         "Buy INVEST_₹ ÷ PRICE = BUY_SHARES. Act within WHEN_TO_ACT."),
    ("🆕 NEW POSITION",  "Fresh entry",                "Buy INVEST_₹ worth. Always set stop loss first."),
    ("📈 INCREASE",      "Add to winner",              "Top-up with INVEST_₹. Only if in profit already."),
    ("🟡 HOLD / KEEP",   "Do nothing",                 "No buy, no sell. Set stop loss price alert."),
    ("⬜ SKIP",          "Ignore",                      "Not a priority. Re-check next analysis run."),
    ("RSI 🔴 >70",       "Overbought",                  "Don't buy more. Consider booking partial profits."),
    ("RSI 🟢 <30",       "Oversold / Cheap",            "Potential buying opportunity. Confirm with setup signals."),
    ("🛑 STOP LOSS",     "Exit trigger",               "Set price alert in broker app. Exit the moment it's hit."),
    ("Score 80+",        "Excellent",                   "Top-tier stock. High confidence recommendation."),
    ("Score 60–79",      "Good",                        "Solid stock. Moderate confidence."),
    ("Score <60",        "Weak",                        "Treat with caution. Only hold if already owned."),
]
cheat_html = "".join(f"""<tr style="border-bottom:1px solid #f0f0f0">
  <td style="padding:9px 12px;font-weight:700;white-space:nowrap;color:#1565C0">{r[0]}</td>
  <td style="padding:9px 12px;color:#555">{r[1]}</td>
  <td style="padding:9px 12px;color:#333">{r[2]}</td>
</tr>""" for r in cheat_rows_data)

# ── Step blocks for How-To ────────────────────────────────────────────────────
steps = [
    ("🔴","#B71C1C","Sell First",
     "Open <b>Urgent</b> tab → find SELL stocks<br>Sell ALL shares listed in <b>MY_SHARES</b><br>Note rupees received — this is your freed capital<br>This must happen BEFORE any buying"),
    ("🔄","#E65100","Execute Swaps",
     "In <b>Urgent</b> tab → find SWAP stocks<br>Sell the stock (same as Step 1)<br>Immediately buy the <b>→ TARGET</b> stock shown<br>Your capital upgrades to a higher-ranked stock"),
    ("🚀","#1565C0","Buy PRE-BREAKOUT",
     "Open <b>Buy</b> tab → PRE-BREAKOUT stocks first<br>Buy <b>BUY_SHARES</b> quantity at market<br>These are time-sensitive — act within <b>WHEN_TO_ACT</b><br>Set a stop loss price alert immediately after buying"),
    ("🛑","#C62828","Set Stop Losses",
     "Every stock you own or buy has a <b>STOP LOSS ₹</b><br>Open your broker app → set a price alert<br>If price touches that level: exit immediately<br>No second-guessing — stop loss is your insurance"),
    ("📈","#1B5E20","Add to Winners",
     "Open <b>Buy</b> tab → INCREASE stocks<br>Only after Steps 1–4 are done<br>Invest the <b>INVEST ₹</b> amount shown<br>Only add to stocks already in profit"),
    ("🟡","#F57F17","Monitor HOLDs",
     "Open <b>Hold</b> tab — no trades today<br>Check RSI badge — if 🔴 >70, start watching for exit<br>Check stop loss is set for each holding<br>Re-run the full analysis every week"),
]
steps_html = "".join(f"""<div style="border:2px solid {col};border-radius:12px;padding:16px">
  <div style="font-size:16px;font-weight:800;color:{col};margin-bottom:10px">{icon} Step {i+1} — {title}</div>
  <div style="font-size:13px;color:#444;line-height:2">{body}</div>
</div>""" for i,(icon,col,title,body) in enumerate(steps))

# ═══════════════════════════════════════════════════════════════════════════════
# FULL HTML OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portfolio Guide — {report_name}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#F0F4F8;color:#2C3E50;line-height:1.5}}
  .page{{display:none}}.page.active{{display:block}}
  .nav-btn{{background:none;border:none;padding:12px 18px;font-size:14px;font-weight:600;color:#7f8c8d;cursor:pointer;
            border-bottom:3px solid transparent;transition:all .2s;white-space:nowrap}}
  .nav-btn.active,.nav-btn:hover{{color:#1565C0;border-bottom-color:#1565C0}}
  .search-box{{padding:10px 16px;border:2px solid #e0e0e0;border-radius:25px;font-size:14px;
               outline:none;transition:border .2s;width:100%;max-width:380px}}
  .search-box:focus{{border-color:#1565C0}}
  @media(max-width:640px){{
    .stat-grid{{grid-template-columns:repeat(3,1fr)!important}}
    .card-2col{{grid-template-columns:1fr!important}}
    .card-3col{{grid-template-columns:1fr 1fr!important}}
  }}
</style>
</head>
<body>

<!-- BANNER -->
<div style="background:linear-gradient(135deg,#0D47A1,#1565C0 50%,#1976D2);color:white;padding:22px 24px">
  <div style="max-width:1100px;margin:0 auto">
    <div style="font-size:26px;font-weight:900;letter-spacing:-.5px">📊 Portfolio Allocation — Complete Guide</div>
    <div style="font-size:13px;margin-top:4px;opacity:.85">Report: <b>{report_name}</b> &nbsp;|&nbsp; {len(df)} stocks analysed</div>
  </div>
</div>

<!-- SUMMARY BAR -->
<div style="background:#1A237E;color:white;padding:14px 24px">
  <div style="max-width:1100px;margin:0 auto">
    <div class="stat-grid" style="display:grid;grid-template-columns:repeat(6,1fr);gap:12px;text-align:center">
      <div><div style="font-size:22px;font-weight:800">{len(owned_df)}</div><div style="font-size:11px;opacity:.75">Stocks Owned</div></div>
      <div><div style="font-size:20px;font-weight:800">{rs(total_val)}</div><div style="font-size:11px;opacity:.75">Portfolio Value</div></div>
      <div><div style="font-size:22px;font-weight:800;color:#81C784">{gainers}</div><div style="font-size:11px;opacity:.75">In Profit</div></div>
      <div><div style="font-size:22px;font-weight:800;color:#EF9A9A">{losers}</div><div style="font-size:11px;opacity:.75">At Loss</div></div>
      <div><div style="font-size:13px;font-weight:700;color:#81C784">{best_str}</div><div style="font-size:11px;opacity:.75">Best Performer</div></div>
      <div><div style="font-size:13px;font-weight:700;color:#EF9A9A">{worst_str}</div><div style="font-size:11px;opacity:.75">Worst Performer</div></div>
    </div>
  </div>
</div>

<!-- TODAY'S PRIORITY BANNER -->
<div style="background:#FFF3E0;border-bottom:2px solid #FFB74D;padding:10px 24px">
  <div style="max-width:1100px;margin:0 auto;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <span style="font-weight:800;color:#E65100;font-size:13px">⚡ TODAY'S PRIORITY:</span>
    {"<span style='background:#B71C1C;color:white;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:700'>🔴 SELL: " + str(action_counts.get('SELL',0)) + "</span>" if action_counts.get('SELL',0) else ""}
    {"<span style='background:#E65100;color:white;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:700'>🔄 SWAP: " + str(action_counts.get('SWAP',0)) + "</span>" if action_counts.get('SWAP',0) else ""}
    {"<span style='background:#1565C0;color:white;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:700'>🚀 PRE-BREAKOUT: " + str(action_counts.get('PRE_BREAKOUT',0)) + "</span>" if action_counts.get('PRE_BREAKOUT',0) else ""}
    {"<span style='background:#0D47A1;color:white;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:700'>🆕 NEW: " + str(action_counts.get('NEW',0)) + "</span>" if action_counts.get('NEW',0) else ""}
    {"<span style='background:#1B5E20;color:white;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:700'>📈 INCREASE: " + str(action_counts.get('INCREASE',0)) + "</span>" if action_counts.get('INCREASE',0) else ""}
    {"<span style='background:#F57F17;color:white;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:700'>🟡 HOLD/KEEP: " + str(action_counts.get('HOLD',0)+action_counts.get('KEEP',0)) + "</span>" if action_counts.get('HOLD',0)+action_counts.get('KEEP',0) else ""}
  </div>
</div>

<!-- NAV TABS (sticky) -->
<div style="background:white;border-bottom:1px solid #e0e0e0;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.08)">
  <div style="max-width:1100px;margin:0 auto;display:flex;overflow-x:auto;padding:0 8px">
    <button class="nav-btn active" onclick="showPage('pg-all',this)">📋 All Stocks ({len(df)})</button>
    <button class="nav-btn" onclick="showPage('pg-urgent',this)">🔴 Urgent ({urgent_count})</button>
    <button class="nav-btn" onclick="showPage('pg-buy',this)">🛒 Buy ({buy_count})</button>
    <button class="nav-btn" onclick="showPage('pg-hold',this)">🟡 Hold ({action_counts.get('HOLD',0)+action_counts.get('KEEP',0)+action_counts.get('SKIP',0)})</button>
    <button class="nav-btn" onclick="showPage('pg-glossary',this)">📖 Glossary</button>
    <button class="nav-btn" onclick="showPage('pg-howto',this)">🧭 How To Use</button>
  </div>
</div>

<div style="max-width:1100px;margin:0 auto;padding:20px 16px">

<!-- ═══ PAGE: ALL STOCKS ═══ -->
<div id="pg-all" class="page active">
  <div style="background:white;border-radius:12px;padding:16px;box-shadow:0 2px 10px rgba(0,0,0,.07);margin-bottom:20px">
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px">
      <input type="text" id="search-box" class="search-box"
             placeholder="🔍  Search by stock symbol, name or sector..." oninput="applyFilters()">
      <span style="font-size:13px;color:#888" id="count-label">{len(df)} stocks shown</span>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">{filter_btns}</div>
  </div>
  <div id="cards-container">{all_cards_html}</div>
  <div id="no-results" style="display:none;text-align:center;padding:40px;color:#888;font-size:16px">No stocks match your search.</div>
</div>

<!-- ═══ PAGE: URGENT ═══ -->
<div id="pg-urgent" class="page">
  <div style="background:#FFEBEE;border-left:5px solid #B71C1C;border-radius:0 12px 12px 0;padding:16px 20px;margin-bottom:20px">
    <div style="font-size:18px;font-weight:800;color:#B71C1C;margin-bottom:6px">🔴 Act on these FIRST — before any buying</div>
    <div style="font-size:13px;color:#555">SELL frees cash. SWAP moves money to a better stock. Both are time-sensitive.</div>
  </div>
  {"".join(make_card(r.to_dict(),i) for i,(_,r) in enumerate(df.iterrows()) if atype_of(r.to_dict()) in ("SELL","SWAP"))
    or "<p style='color:#888;padding:20px;font-size:15px'>✅ No urgent sell or swap actions today.</p>"}
</div>

<!-- ═══ PAGE: BUY ═══ -->
<div id="pg-buy" class="page">
  <div style="background:#E3F2FD;border-left:5px solid #1565C0;border-radius:0 12px 12px 0;padding:16px 20px;margin-bottom:20px">
    <div style="font-size:18px;font-weight:800;color:#1565C0;margin-bottom:6px">🛒 Buy Opportunities — after clearing SELL / SWAP</div>
    <div style="font-size:13px;color:#555">PRE-BREAKOUT = time-sensitive (act today or tomorrow). NEW / INCREASE = can wait a day or two.</div>
  </div>
  {"".join(make_card(r.to_dict(),i) for i,(_,r) in enumerate(df.iterrows()) if atype_of(r.to_dict()) in ("PRE_BREAKOUT","NEW","INCREASE"))
    or "<p style='color:#888;padding:20px;font-size:15px'>No buy opportunities right now.</p>"}
</div>

<!-- ═══ PAGE: HOLD ═══ -->
<div id="pg-hold" class="page">
  <div style="background:#FFFDE7;border-left:5px solid #F57F17;border-radius:0 12px 12px 0;padding:16px 20px;margin-bottom:20px">
    <div style="font-size:18px;font-weight:800;color:#F57F17;margin-bottom:6px">🟡 No action needed today — just monitor</div>
    <div style="font-size:13px;color:#555">Set stop loss price alerts if not done. Check RSI — if >70 on any, be ready to sell next week.</div>
  </div>
  {"".join(make_card(r.to_dict(),i) for i,(_,r) in enumerate(df.iterrows()) if atype_of(r.to_dict()) in ("HOLD","KEEP","SKIP"))
    or "<p style='color:#888;padding:20px;font-size:15px'>No holds.</p>"}
</div>

<!-- ═══ PAGE: GLOSSARY ═══ -->
<div id="pg-glossary" class="page">
  <div style="background:white;border-radius:12px;padding:22px;box-shadow:0 2px 10px rgba(0,0,0,.07)">
    <div style="font-size:20px;font-weight:800;margin-bottom:18px">📖 Every Term Explained in Plain English</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px">{glos_html}</div>
  </div>
</div>

<!-- ═══ PAGE: HOW TO USE ═══ -->
<div id="pg-howto" class="page">
  <div style="background:white;border-radius:12px;padding:24px;box-shadow:0 2px 10px rgba(0,0,0,.07)">
    <div style="font-size:22px;font-weight:800;margin-bottom:20px">🧭 Complete Step-by-Step Guide</div>

    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:28px">
      {steps_html}
    </div>

    <!-- Cheat Sheet -->
    <div style="font-size:18px;font-weight:800;margin-bottom:14px">⚡ Quick Reference Cheat Sheet</div>
    <div style="overflow-x:auto;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,.08)">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr style="background:#1565C0;color:white">
          <th style="padding:10px 14px;text-align:left">If you see...</th>
          <th style="padding:10px 14px;text-align:left">It means...</th>
          <th style="padding:10px 14px;text-align:left">Do this</th>
        </tr>
        {cheat_html}
      </table>
    </div>

    <!-- Score guide -->
    <div style="margin-top:24px;background:#E8F5E9;border-radius:10px;padding:18px">
      <div style="font-size:16px;font-weight:800;color:#1B5E20;margin-bottom:12px">💡 Understanding the Score Breakdown Bars</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;font-size:13px">
        <div><span style="display:inline-block;width:12px;height:12px;background:#1565C0;border-radius:2px;vertical-align:middle;margin-right:6px"></span><b>Fundamentals</b> — PE, ROE, debt quality, financial health</div>
        <div><span style="display:inline-block;width:12px;height:12px;background:#6A1B9A;border-radius:2px;vertical-align:middle;margin-right:6px"></span><b>Momentum</b> — Price trend strength, RSI, volume</div>
        <div><span style="display:inline-block;width:12px;height:12px;background:#00695C;border-radius:2px;vertical-align:middle;margin-right:6px"></span><b>Value</b> — Is the stock cheap vs sector peers?</div>
        <div><span style="display:inline-block;width:12px;height:12px;background:#27ae60;border-radius:2px;vertical-align:middle;margin-right:6px"></span><b>Overall Score</b> — Weighted composite (regime-adaptive)</div>
      </div>
    </div>

    <!-- RSI guide -->
    <div style="margin-top:16px;background:#F3E5F5;border-radius:10px;padding:18px">
      <div style="font-size:16px;font-weight:800;color:#6A1B9A;margin-bottom:12px">📊 RSI Quick Guide</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;font-size:13px">
        <div><span style="background:#2E7D32;color:white;padding:2px 8px;border-radius:8px;font-size:11px">Below 30</span> &nbsp;Oversold — potential buy zone</div>
        <div><span style="background:#F57F17;color:white;padding:2px 8px;border-radius:8px;font-size:11px">30 – 65</span> &nbsp;Healthy neutral zone</div>
        <div><span style="background:#C62828;color:white;padding:2px 8px;border-radius:8px;font-size:11px">Above 70</span> &nbsp;Overbought — avoid buying more</div>
        <div><span style="background:#B71C1C;color:white;padding:2px 8px;border-radius:8px;font-size:11px">Above 80</span> &nbsp;Very overbought — consider booking profits</div>
      </div>
    </div>

  </div>
</div>

<div style="text-align:center;padding:24px;color:#aaa;font-size:12px">
  Generated from {report_name} — For personal research only. Always verify before trading.
</div>

</div><!-- /container -->

<script>
function showPage(id, btn) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if(btn) btn.classList.add('active');
  window.scrollTo(0,0);
}}

var activeFilter = 'ALL';

function filterCards(atype) {{
  activeFilter = atype;
  // Reset all buttons
  document.querySelectorAll('[id^="btn-"]').forEach(function(b) {{
    var key = b.id.replace('btn-','');
    var border = b.style.borderColor;
    b.style.background = '#F5F5F5';
    b.style.color = border;
    b.classList.remove('active');
  }});
  // Highlight active
  var ab = document.getElementById('btn-'+atype);
  if(ab) {{
    ab.style.background = ab.style.borderColor;
    ab.style.color = 'white';
    ab.classList.add('active');
  }}
  applyFilters();
}}

function applyFilters() {{
  var q = (document.getElementById('search-box').value||'').toLowerCase().trim();
  var cards = document.querySelectorAll('#cards-container .stock-card');
  var shown = 0;
  cards.forEach(function(card) {{
    var sym    = (card.dataset.sym    ||'').toLowerCase();
    var sector = (card.dataset.sector ||'').toLowerCase();
    var atype  = (card.dataset.action ||'');
    var text   = card.innerText.toLowerCase();
    var matchQ = !q || sym.includes(q) || sector.includes(q) || text.includes(q);
    var matchF = (activeFilter === 'ALL') || (atype === activeFilter);
    if(matchQ && matchF) {{ card.style.display=''; shown++; }}
    else {{ card.style.display='none'; }}
  }});
  var lbl = document.getElementById('count-label');
  if(lbl) lbl.textContent = shown + ' stock' + (shown===1?'':'s') + ' shown';
  var nr = document.getElementById('no-results');
  if(nr) nr.style.display = (shown===0)?'block':'none';
}}
</script>
</body>
</html>"""

out = "portfolio_guide.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ Guide written to: {out}")
webbrowser.open(os.path.abspath(out))
print("Done! 🎉")
