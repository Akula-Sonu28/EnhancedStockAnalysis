#!/usr/bin/env python3
"""
Generate Individual Action Plans for All Portfolio Stocks
Creates detailed action plans for each stock with specific recommendations
"""

import pandas as pd
import os
from datetime import datetime, timedelta

def format_currency(value):
    """Format Indian currency"""
    if pd.isna(value) or value == 0:
        return "₹0"
    return f"₹{value:,.2f}"

def get_action_emoji(action):
    """Get emoji for action type"""
    action_map = {
        'BUY': '💰',
        'INCREASE': '📈',
        'KEEP': '✅',
        'HOLD': '⚪',
        'SELL': '🔴',
        'SKIP': '⏭️'
    }
    return action_map.get(action, '📊')

def get_priority_level(action, when_to_act, profit_pct):
    """Determine priority level"""
    if action == 'SELL':
        if 'TODAY' in str(when_to_act).upper():
            return '🔴 CRITICAL - TODAY'
        elif 'WEEK' in str(when_to_act).upper():
            return '🟠 HIGH - This Week'
        else:
            return '🟡 MEDIUM - Next 1-2 Days'
    elif action == 'INCREASE':
        if when_to_act and 'week' in str(when_to_act).lower():
            return '🟢 OPPORTUNITY - Within 3 Weeks'
        return '🟢 OPPORTUNITY - NOW'
    elif action == 'KEEP':
        if 'TODAY' in str(when_to_act).upper() or 'cut losses' in str(when_to_act).lower():
            return '🟡 MONITOR - TODAY'
        elif profit_pct and profit_pct < 0:
            return '🟡 WATCH - Monitor Closely'
        return '🟢 STABLE - Regular Review'
    elif action == 'HOLD':
        return '🟢 STABLE - Hold Position'
    else:
        return '⚪ NEUTRAL'

def generate_action_steps(row):
    """Generate specific action steps based on stock situation"""
    action = row['ACTION']
    when_to_act = str(row['WHEN_TO_ACT'])
    invest = row['INVEST_₹']
    buy_shares = row['BUY_SHARES']
    my_shares = row['MY_SHARES']
    my_value = row['MY_VALUE_₹']
    profit_pct = row['MY_PROFIT_%']
    book_pct = row['BOOK_%_IF_SELL']
    score = row['SCORE']
    new_score = row['NEW_SCORE']
    stock_type = row['TYPE']
    
    steps = []
    
    # Calculate per share price
    price_per_share = my_value / my_shares if my_shares > 0 else 0
    
    if action == 'INCREASE':
        steps.append(f"**BUY MORE**: Add {int(buy_shares)} shares for {format_currency(invest)}")
        steps.append(f"**Target Price**: Around ₹{price_per_share:.2f} per share or lower")
        steps.append(f"**Strategy**: {when_to_act if pd.notna(when_to_act) else 'Buy on dips'}")
        steps.append(f"**Total Position After**: {my_shares + int(buy_shares)} shares worth ~{format_currency(my_value + invest)}")
        
    elif action == 'SELL':
        sell_value = my_value * (book_pct / 100) if pd.notna(book_pct) else my_value
        steps.append(f"**SELL**: {int(book_pct) if pd.notna(book_pct) else 100}% of position")
        steps.append(f"**Timing**: {when_to_act if pd.notna(when_to_act) else 'Next 1-2 days'}")
        steps.append(f"**Expected Proceeds**: {format_currency(sell_value)}")
        if profit_pct > 0:
            steps.append(f"**Book Profit**: Lock in +{profit_pct:.2f}% gain")
        else:
            steps.append(f"**Cut Loss**: Minimize loss at {profit_pct:.2f}%")
        
    elif action == 'KEEP':
        if 'TODAY' in when_to_act.upper() or 'cut losses' in when_to_act.lower():
            steps.append(f"**MONITOR CLOSELY**: Watch price movement today")
            steps.append(f"**Stop Loss**: Set at {price_per_share * 0.90:.2f} per share (-10%)")
            steps.append(f"**Decision Point**: Review at end of trading day")
            if profit_pct < 0:
                steps.append(f"**Current Loss**: {profit_pct:.2f}% - Recover or Exit")
        elif pd.notna(when_to_act) and 'days' in when_to_act.lower():
            steps.append(f"**HOLD & WAIT**: Keep position for {when_to_act}")
            steps.append(f"**Price Alert**: Set at ₹{price_per_share * 1.05:.2f} (+5% gain)")
            if pd.notna(book_pct) and book_pct == 100:
                steps.append(f"**Exit Strategy**: Prepare to sell 100% if score drops")
        else:
            steps.append(f"**MAINTAIN**: Continue holding current position")
            steps.append(f"**Review**: Monitor in next portfolio analysis")
            
    elif action == 'HOLD':
        steps.append(f"**HOLD STEADY**: No action needed now")
        steps.append(f"**Current Gain**: +{profit_pct:.2f}%" if profit_pct > 0 else f"**Current Status**: {profit_pct:.2f}%")
        steps.append(f"**Next Review**: Check in next portfolio update")
        
    return steps

def generate_risk_alerts(row):
    """Generate risk alerts and warnings"""
    alerts = []
    
    profit_pct = row['MY_PROFIT_%']
    score = row['SCORE']
    new_score = row['NEW_SCORE']
    action = row['ACTION']
    stock_type = row['TYPE']
    
    # Loss alerts
    if profit_pct < -10:
        alerts.append(f"⚠️ **MAJOR LOSS**: Down {profit_pct:.2f}% - Consider immediate exit")
    elif profit_pct < -5:
        alerts.append(f"⚠️ **LOSS WARNING**: Down {profit_pct:.2f}% - Set strict stop-loss")
    elif profit_pct < 0:
        alerts.append(f"⚠️ **MINOR LOSS**: Down {profit_pct:.2f}% - Monitor for recovery")
    
    # Score alerts
    if new_score < 50:
        alerts.append(f"🔻 **LOW SCORE**: {new_score:.1f}/100 - Fundamentals weak")
    elif score < 30 and new_score > 60:
        alerts.append(f"📈 **IMPROVING**: Score jumped from {score:.1f} to {new_score:.1f}")
    
    # Type risk
    if stock_type == 'SPECULATIVE':
        alerts.append(f"⚡ **HIGH RISK**: Speculative stock - High volatility expected")
    elif stock_type == 'OPPORTUNISTIC':
        alerts.append(f"🛡️ **DEFENSIVE**: Opportunistic play - Lower risk")
    
    # Action urgency
    if action == 'SELL':
        alerts.append(f"🔴 **URGENT**: Sell recommendation - Take action soon")
    
    return alerts

def create_stock_action_plan(row, output_dir):
    """Create detailed action plan for a single stock"""
    
    symbol = row['symbol']
    company = row['company_name']
    action = row['ACTION']
    when_to_act = str(row['WHEN_TO_ACT'])
    my_shares = row['MY_SHARES']
    my_value = row['MY_VALUE_₹']
    profit_pct = row['MY_PROFIT_%']
    score = row['SCORE']
    new_score = row['NEW_SCORE']
    stock_type = row['TYPE']
    rank = row['RANK']
    
    # Calculate metrics
    price_per_share = my_value / my_shares if my_shares > 0 else 0
    entry_price = price_per_share / (1 + profit_pct/100) if profit_pct != 0 else price_per_share
    
    # Get action emoji and priority
    emoji = get_action_emoji(action)
    priority = get_priority_level(action, when_to_act, profit_pct)
    
    # Get action steps and alerts
    action_steps = generate_action_steps(row)
    risk_alerts = generate_risk_alerts(row)
    
    # Create markdown content
    content = f"""# {emoji} {symbol} - Action Plan
## {company}

---

## 📊 Current Position Summary

| Metric | Value |
|--------|-------|
| **Action Required** | **{action}** |
| **Priority Level** | {priority} |
| **Timing** | {when_to_act if pd.notna(when_to_act) and when_to_act != 'nan' else 'No specific timeline'} |
| **Shares Owned** | {int(my_shares)} shares |
| **Current Value** | {format_currency(my_value)} |
| **Price per Share** | ₹{price_per_share:.2f} |
| **Entry Price** | ₹{entry_price:.2f} |
| **Current P&L** | {'+' if profit_pct >= 0 else ''}{profit_pct:.2f}% |
| **Quality Score** | {new_score:.1f}/100 (Old: {score:.1f}) |
| **Stock Type** | {stock_type} |
| **Portfolio Rank** | #{int(rank)}/35 |

---

## 🎯 Action Steps

"""
    
    for i, step in enumerate(action_steps, 1):
        content += f"{i}. {step}\n"
    
    content += f"""
---

## ⚠️ Risk Alerts & Warnings

"""
    
    if risk_alerts:
        for alert in risk_alerts:
            content += f"- {alert}\n"
    else:
        content += "✅ No major risk alerts - Position looks stable\n"
    
    # Add specific guidance based on action
    content += f"""
---

## 📋 Detailed Guidance

"""
    
    if action == 'INCREASE':
        invest = row['INVEST_₹']
        buy_shares = row['BUY_SHARES']
        content += f"""
### Why Increase Position?

This stock is performing well and deserves more capital allocation:
- **Strong Score**: {new_score:.1f}/100 indicates good fundamentals
- **Portfolio Rank**: #{int(rank)}/35 - Among top performers
- **Recommended Addition**: {int(buy_shares)} shares for {format_currency(invest)}

### Buying Strategy

1. **Place Limit Orders**: Set buy orders at ₹{price_per_share * 0.98:.2f} (2% below current)
2. **Split Purchases**: Buy in 2-3 tranches to average price
3. **Timeline**: {when_to_act if pd.notna(when_to_act) and when_to_act != 'nan' else 'Within next 2 weeks'}
4. **Max Price**: Don't buy above ₹{price_per_share * 1.02:.2f} per share

### Post-Purchase Targets

- **Target 1**: +10% gain = ₹{price_per_share * 1.10:.2f} per share
- **Target 2**: +25% gain = ₹{price_per_share * 1.25:.2f} per share
- **Stop Loss**: -8% = ₹{price_per_share * 0.92:.2f} per share
"""
    
    elif action == 'SELL':
        book_pct = row['BOOK_%_IF_SELL']
        sell_value = my_value * (book_pct / 100) if pd.notna(book_pct) else my_value
        content += f"""
### Why Sell?

This position needs to be exited:
- **Timing**: {when_to_act if pd.notna(when_to_act) and when_to_act != 'nan' else 'Next 1-2 days'}
- **Sell Amount**: {int(book_pct) if pd.notna(book_pct) else 100}% of position
- **Expected Proceeds**: {format_currency(sell_value)}
{'- **Profit Booking**: Lock in gains and reallocate to better opportunities' if profit_pct > 0 else '- **Loss Cutting**: Minimize losses and protect capital'}

### Selling Strategy

1. **Market Order**: Sell at market open if urgent
2. **Limit Order**: Set at ₹{price_per_share * 1.01:.2f} if time permits
3. **Timeline**: Execute {when_to_act if pd.notna(when_to_act) and when_to_act != 'nan' else 'within next 2 trading days'}
4. **Confirm Sale**: Verify order execution same day

### Post-Sale Plan

- **Proceeds Available**: {format_currency(sell_value)}
- **Reinvestment**: Check top-ranked INCREASE stocks for reallocation
- **Tax Planning**: {'Consider LTCG if held >1 year' if profit_pct > 0 else 'Use losses for tax harvesting'}
"""
    
    elif action == 'KEEP':
        content += f"""
### Why Keep?

This position requires careful monitoring:
- **Current Status**: {'+' if profit_pct >= 0 else ''}{profit_pct:.2f}% P&L
- **Score**: {new_score:.1f}/100 - {'Decent quality' if new_score >= 60 else 'Needs improvement'}
- **Watch Period**: {when_to_act if pd.notna(when_to_act) and when_to_act != 'nan' else 'Regular monitoring'}

### Monitoring Plan

**Daily (Next 5 Trading Days):**
- [ ] Check price at market close (3:30 PM)
- [ ] Monitor volume and price action
- [ ] Watch for news/announcements

**Weekly Review:**
- [ ] Compare against portfolio performance
- [ ] Check if score improves/deteriorates
- [ ] Reassess position size

### Decision Triggers

**🔴 SELL IF:**
- Loss exceeds -10% (₹{price_per_share * 0.90:.2f} per share)
- Score drops below 45
- Better opportunities emerge with 15+ score difference

**🟢 HOLD/INCREASE IF:**
- Price recovers to breakeven
- Score improves above 65
- Sector shows positive momentum
"""
    
    elif action == 'HOLD':
        content += f"""
### Why Hold?

This position is stable and performing adequately:
- **Current Status**: {'+' if profit_pct >= 0 else ''}{profit_pct:.2f}% P&L
- **Score**: {new_score:.1f}/100 - Solid fundamentals
- **No Action Needed**: Continue monitoring

### Passive Monitoring

**Weekly Check:**
- Review portfolio allocation sheet
- Check if status changes to SELL/INCREASE
- Monitor major company announcements

**Monthly Assessment:**
- Compare performance vs portfolio average
- Evaluate if position size is appropriate
- Consider rebalancing if needed

### Optional Actions

- **Set Price Alerts**: ₹{price_per_share * 0.95:.2f} (down 5%) and ₹{price_per_share * 1.10:.2f} (up 10%)
- **Review Quarterly**: Check fundamentals after earnings
- **Rebalance**: If position grows >10% of portfolio, consider partial booking
"""
    
    # Price alerts section
    content += f"""
---

## 🔔 Recommended Price Alerts

Set these alerts in your trading app:

| Alert Type | Price | Purpose |
|------------|-------|---------|
| 🔴 Stop Loss | ₹{price_per_share * 0.90:.2f} | Exit if drops 10% |
| 🟡 Watch | ₹{price_per_share * 0.95:.2f} | Monitor closely if drops 5% |
| 🟢 Target 1 | ₹{price_per_share * 1.05:.2f} | First profit target |
| 🟢 Target 2 | ₹{price_per_share * 1.15:.2f} | Major profit milestone |
| 🎯 Breakeven | ₹{entry_price:.2f} | Recovery to entry price |

---

## 📅 Review Schedule

| Timeframe | Action |
|-----------|--------|
| **Daily** | {'✅ Check price and news' if action in ['SELL', 'KEEP'] else '⏭️ No daily check needed'} |
| **Weekly** | ✅ Review in next portfolio analysis |
| **Monthly** | ✅ Fundamental reassessment |
| **Quarterly** | ✅ Earnings review and score update |

---

## 💡 Quick Reference Card

```
SYMBOL: {symbol}
ACTION: {action}
TIMING: {when_to_act if pd.notna(when_to_act) and when_to_act != 'nan' else 'As needed'}
PRIORITY: {priority}
CURRENT: {int(my_shares)} shares @ ₹{price_per_share:.2f} = {format_currency(my_value)}
P&L: {'+' if profit_pct >= 0 else ''}{profit_pct:.2f}%
RANK: #{int(rank)}/35
SCORE: {new_score:.1f}/100
```

---

**Generated on**: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}  
**Next Review**: {(datetime.now() + timedelta(days=7)).strftime("%B %d, %Y")}  
**Portfolio Analysis Date**: October 17, 2025

---

## 📞 Need Help?

- Review full portfolio in: `Enhanced_Stock_Report_20251017_114430.xlsx`
- Check master summary: `ALL_STOCKS_ACTION_SUMMARY.md`
- Run fresh analysis: `python analyze_top200_stocks_enhanced.py`
"""
    
    # Write to file
    filename = f"{symbol}_Action_Plan.md"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filepath

def create_master_summary(df, output_dir):
    """Create master summary of all action plans"""
    
    content = f"""# 📊 Complete Portfolio Action Plan Summary
## All 35 Stocks - October 17, 2025

---

## 🎯 Executive Summary

**Total Portfolio Value**: {format_currency(df['MY_VALUE_₹'].sum())}  
**Total Stocks**: {len(df)}  
**Average Score**: {df['NEW_SCORE'].mean():.1f}/100  
**Overall P&L**: {df['MY_PROFIT_%'].mean():.2f}%

### Action Breakdown

"""
    
    action_counts = df['ACTION'].value_counts()
    for action, count in action_counts.items():
        emoji = get_action_emoji(action)
        content += f"- {emoji} **{action}**: {count} stocks\n"
    
    content += f"""
---

## 🔴 URGENT ACTIONS (Priority Order)

### Immediate Attention Required

"""
    
    # Urgent sells
    urgent_sells = df[df['ACTION'] == 'SELL'].sort_values('RANK')
    if len(urgent_sells) > 0:
        content += f"\n**📛 {len(urgent_sells)} STOCKS TO SELL:**\n\n"
        for _, row in urgent_sells.iterrows():
            content += f"- **{row['symbol']}** - Rank #{int(row['RANK'])} - {row['WHEN_TO_ACT'] if pd.notna(row['WHEN_TO_ACT']) else 'Next 1-2 days'} - P&L: {row['MY_PROFIT_%']:.2f}%\n"
    
    # Monitor closely (KEEP with warnings)
    monitor = df[(df['ACTION'] == 'KEEP') & (df['MY_PROFIT_%'] < 0)].sort_values('MY_PROFIT_%')
    if len(monitor) > 0:
        content += f"\n**⚠️ {len(monitor)} STOCKS TO MONITOR CLOSELY:**\n\n"
        for _, row in monitor.iterrows():
            content += f"- **{row['symbol']}** - Rank #{int(row['RANK'])} - Loss: {row['MY_PROFIT_%']:.2f}% - Score: {row['NEW_SCORE']:.1f}\n"
    
    content += f"""
---

## 🟢 OPPORTUNITIES

### Stocks to Increase Position

"""
    
    increase = df[df['ACTION'] == 'INCREASE'].sort_values('RANK')
    if len(increase) > 0:
        total_investment = increase['INVEST_₹'].sum()
        content += f"\n**💰 {len(increase)} STOCKS TO ADD** (Total: {format_currency(total_investment)}):\n\n"
        for _, row in increase.iterrows():
            content += f"- **{row['symbol']}** - Rank #{int(row['RANK'])} - Add {format_currency(row['INVEST_₹'])} ({int(row['BUY_SHARES'])} shares) - Score: {row['NEW_SCORE']:.1f}\n"
    
    content += f"""
---

## ⚪ STABLE POSITIONS

### Stocks to Hold/Keep

"""
    
    stable = df[df['ACTION'].isin(['HOLD', 'KEEP']) & (df['MY_PROFIT_%'] >= 0)].sort_values('RANK')
    if len(stable) > 0:
        content += f"\n**✅ {len(stable)} STABLE STOCKS:**\n\n"
        for _, row in stable.iterrows():
            content += f"- **{row['symbol']}** - Rank #{int(row['RANK'])} - Gain: +{row['MY_PROFIT_%']:.2f}% - Score: {row['NEW_SCORE']:.1f}\n"
    
    content += f"""
---

## 📊 Portfolio Analysis by Category

### By Action Type

"""
    
    for action in ['SELL', 'INCREASE', 'KEEP', 'HOLD']:
        action_stocks = df[df['ACTION'] == action]
        if len(action_stocks) > 0:
            avg_score = action_stocks['NEW_SCORE'].mean()
            avg_pnl = action_stocks['MY_PROFIT_%'].mean()
            total_value = action_stocks['MY_VALUE_₹'].sum()
            content += f"""
#### {get_action_emoji(action)} {action} ({len(action_stocks)} stocks)
- **Total Value**: {format_currency(total_value)}
- **Avg Score**: {avg_score:.1f}/100
- **Avg P&L**: {avg_pnl:+.2f}%
"""
    
    content += f"""
---

## 🏆 Top 10 Performers

"""
    
    top10 = df.nsmallest(10, 'RANK')
    content += "\n| Rank | Symbol | Score | P&L | Action | Value |\n"
    content += "|------|--------|-------|-----|--------|-------|\n"
    for _, row in top10.iterrows():
        content += f"| #{int(row['RANK'])} | {row['symbol']} | {row['NEW_SCORE']:.1f} | {row['MY_PROFIT_%']:+.2f}% | {row['ACTION']} | {format_currency(row['MY_VALUE_₹'])} |\n"
    
    content += f"""
---

## ⚠️ Bottom 10 Performers

"""
    
    bottom10 = df.nlargest(10, 'RANK')
    content += "\n| Rank | Symbol | Score | P&L | Action | Value |\n"
    content += "|------|--------|-------|-----|--------|-------|\n"
    for _, row in bottom10.iterrows():
        content += f"| #{int(row['RANK'])} | {row['symbol']} | {row['NEW_SCORE']:.1f} | {row['MY_PROFIT_%']:+.2f}% | {row['ACTION']} | {format_currency(row['MY_VALUE_₹'])} |\n"
    
    content += f"""
---

## 📅 Action Timeline

### TODAY
"""
    
    today_actions = df[df['WHEN_TO_ACT'].str.contains('TODAY', na=False, case=False)]
    if len(today_actions) > 0:
        for _, row in today_actions.iterrows():
            content += f"- {get_action_emoji(row['ACTION'])} **{row['symbol']}** - {row['ACTION']} - {row['WHEN_TO_ACT']}\n"
    else:
        content += "- No urgent actions required today\n"
    
    content += f"""
### NEXT 1-2 DAYS
"""
    
    next_days = df[df['WHEN_TO_ACT'].str.contains('days', na=False, case=False)]
    if len(next_days) > 0:
        for _, row in next_days.iterrows():
            content += f"- {get_action_emoji(row['ACTION'])} **{row['symbol']}** - {row['ACTION']} - {row['WHEN_TO_ACT']}\n"
    else:
        content += "- No specific actions for next few days\n"
    
    content += f"""
### NEXT 1-3 WEEKS
"""
    
    next_weeks = df[df['WHEN_TO_ACT'].str.contains('week', na=False, case=False)]
    if len(next_weeks) > 0:
        for _, row in next_weeks.iterrows():
            content += f"- {get_action_emoji(row['ACTION'])} **{row['symbol']}** - {row['ACTION']} - {row['WHEN_TO_ACT']}\n"
    else:
        content += "- No specific actions for next few weeks\n"
    
    content += f"""
---

## 💰 Capital Allocation Plan

### Required Capital

"""
    
    total_investment = df[df['ACTION'] == 'INCREASE']['INVEST_₹'].sum()
    total_sell_proceeds = df[df['ACTION'] == 'SELL']['MY_VALUE_₹'].sum()
    
    content += f"""
- **New Investment Needed**: {format_currency(total_investment)}
- **Expected from Sales**: {format_currency(total_sell_proceeds)}
- **Net Capital Required**: {format_currency(max(0, total_investment - total_sell_proceeds))}
- **Surplus after Rebalancing**: {format_currency(max(0, total_sell_proceeds - total_investment))}

### Rebalancing Strategy

1. **Execute Sells First**: Free up {format_currency(total_sell_proceeds)} from {len(df[df['ACTION'] == 'SELL'])} stocks
2. **Deploy to INCREASE stocks**: Allocate {format_currency(total_investment)} to {len(df[df['ACTION'] == 'INCREASE'])} opportunities
3. **Keep Surplus**: Maintain cash buffer for future opportunities

---

## 📁 Individual Stock Action Plans

All detailed action plans are available in the `action_plans/` folder:

"""
    
    for _, row in df.sort_values('RANK').iterrows():
        emoji = get_action_emoji(row['ACTION'])
        content += f"- {emoji} [`{row['symbol']}_Action_Plan.md`](action_plans/{row['symbol']}_Action_Plan.md) - {row['company_name'][:40]}\n"
    
    content += f"""
---

## 🎯 Quick Action Checklist

### This Week

- [ ] Review all SELL stocks - Execute sales as per timing
- [ ] Monitor KEEP stocks daily for next 3-5 days
- [ ] Set price alerts for all positions
- [ ] Place buy orders for INCREASE stocks

### This Month

- [ ] Review portfolio allocation after sells/buys
- [ ] Check sector concentration
- [ ] Rebalance if any position exceeds 10% of portfolio
- [ ] Run fresh portfolio analysis (mid-month)

---

**Report Generated**: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}  
**Based on Analysis**: October 17, 2025  
**Next Portfolio Review**: October 24, 2025 (Weekly) / October 31, 2025 (Monthly)

---

## 📞 Resources

- **Full Report**: `reports/Enhanced_Stock_Report_20251017_114430.xlsx`
- **Portfolio Data**: `portfolio_data_for_plans.csv`
- **Analysis Script**: `analyze_top200_stocks_enhanced.py`
- **Individual Plans**: `action_plans/` folder (35 files)

---

*This is an automated portfolio analysis. Always verify with real-time market data before executing trades.*
"""
    
    # Write master summary
    filepath = os.path.join(output_dir, '../ALL_STOCKS_ACTION_SUMMARY.md')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filepath

def main():
    """Main execution"""
    print("="*100)
    print("📊 GENERATING ACTION PLANS FOR ALL PORTFOLIO STOCKS")
    print("="*100)
    
    # Read portfolio data
    try:
        df = pd.read_csv('portfolio_data_for_plans.csv')
        print(f"\n✅ Loaded {len(df)} stocks from portfolio")
    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        print("Make sure to run extract_portfolio_data.py first!")
        return
    
    # Create output directory
    output_dir = 'action_plans'
    os.makedirs(output_dir, exist_ok=True)
    print(f"✅ Created output directory: {output_dir}/")
    
    # Generate individual action plans
    print(f"\n📝 Generating individual action plans...")
    print("-" * 100)
    
    for idx, row in df.iterrows():
        symbol = row['symbol']
        try:
            filepath = create_stock_action_plan(row, output_dir)
            action_emoji = get_action_emoji(row['ACTION'])
            print(f"  {action_emoji} {idx+1:2d}/35 - {symbol:12s} - {row['ACTION']:8s} - Created: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"  ❌ {idx+1:2d}/35 - {symbol:12s} - ERROR: {e}")
    
    print("-" * 100)
    print(f"✅ Generated {len(df)} individual action plans")
    
    # Generate master summary
    print(f"\n📋 Generating master summary...")
    try:
        summary_path = create_master_summary(df, output_dir)
        print(f"✅ Created master summary: {os.path.basename(summary_path)}")
    except Exception as e:
        print(f"❌ Error creating master summary: {e}")
    
    # Summary statistics
    print("\n" + "="*100)
    print("📊 SUMMARY")
    print("="*100)
    
    action_counts = df['ACTION'].value_counts()
    print(f"\n📈 Action Distribution:")
    for action, count in action_counts.items():
        emoji = get_action_emoji(action)
        pct = (count / len(df)) * 100
        print(f"  {emoji} {action:10s}: {count:2d} stocks ({pct:5.1f}%)")
    
    print(f"\n💰 Portfolio Metrics:")
    print(f"  Total Value: {format_currency(df['MY_VALUE_₹'].sum())}")
    print(f"  Avg Score: {df['NEW_SCORE'].mean():.1f}/100")
    print(f"  Avg P&L: {df['MY_PROFIT_%'].mean():+.2f}%")
    
    urgent = len(df[df['WHEN_TO_ACT'].str.contains('TODAY|days', na=False, case=False)])
    print(f"\n⚠️  Urgent Actions: {urgent} stocks need attention")
    
    print("\n" + "="*100)
    print("✅ ALL ACTION PLANS GENERATED SUCCESSFULLY!")
    print("="*100)
    print(f"\n📁 Check these files:")
    print(f"  1. Individual plans: action_plans/*.md (35 files)")
    print(f"  2. Master summary: ALL_STOCKS_ACTION_SUMMARY.md")
    print(f"  3. Quick reference: portfolio_data_for_plans.csv")
    print("\n🎯 Next Steps:")
    print("  1. Read ALL_STOCKS_ACTION_SUMMARY.md for overview")
    print("  2. Check individual stock plans for detailed actions")
    print("  3. Set price alerts in your trading app")
    print("  4. Execute actions as per priority and timing")
    print("\n" + "="*100)

if __name__ == "__main__":
    main()
