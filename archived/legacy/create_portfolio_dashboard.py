"""
Portfolio Allocation Dashboard Generator - Fixed Version
"""

import pandas as pd
import json
from datetime import datetime
import os
import webbrowser

def create_dashboard():
    # Load data
    report_file = "reports/Enhanced_Stock_Report_20251017_115928.xlsx"
    print(f"Loading data from: {report_file}")
    
    df = pd.read_excel(report_file, sheet_name='Portfolio Allocation')
    df = df.fillna(0)
    
    # Convert numeric columns
    numeric_cols = ['INVEST_₹', 'BUY_SHARES', 'MY_SHARES', 'MY_VALUE_₹', 'MY_PROFIT_%', 
                    'BOOK_%_IF_SELL', 'SCORE', 'PRICE']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Calculate stats
    total_stocks = len(df)
    total_value = df['MY_VALUE_₹'].sum()
    total_investment = df['INVEST_₹'].sum()
    avg_score = df['SCORE'].mean()
    profitable = len(df[df['MY_PROFIT_%'] > 0])
    losses = len(df[df['MY_PROFIT_%'] < 0])
    avg_profit = df[df['MY_VALUE_₹'] > 0]['MY_PROFIT_%'].mean()
    
    # Get data for charts
    actions = df['ACTION'].value_counts().to_dict()
    timings = df['WHEN_TO_ACT'].value_counts().to_dict()
    types = df['TYPE'].value_counts().to_dict()
    sectors = df['sector'].value_counts().head(10).to_dict()
    
    # Get priority stocks
    urgent_sells = df[(df['ACTION'] == 'SELL') & (df['WHEN_TO_ACT'].str.contains('TODAY', na=False))].to_dict('records')
    urgent_buys = df[(df['ACTION'] == 'BUY') & (df['INVEST_₹'] > 0)].nlargest(10, 'INVEST_₹').to_dict('records')
    warnings = df[(df['ACTION'] == 'KEEP') & (df['WHEN_TO_ACT'].str.contains('TODAY', na=False))].to_dict('records')
    profit_booking = df[df['BOOK_%_IF_SELL'] > 0].to_dict('records')
    all_stocks = df.to_dict('records')
    
    print(f"Loaded {total_stocks} stocks")
    print(f"Creating HTML dashboard...")
    
    # Create HTML file
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Portfolio Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header h1 { color: #667eea; font-size: 2.5em; margin-bottom: 10px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.3s; }
        .card:hover { transform: translateY(-5px); }
        .card-title { color: #666; font-size: 0.9em; text-transform: uppercase; margin-bottom: 10px; }
        .card-value { color: #667eea; font-size: 2.5em; font-weight: bold; margin-bottom: 5px; }
        .card-subtitle { color: #999; font-size: 0.85em; }
        .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .chart-card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .chart-card h3 { margin-bottom: 20px; color: #333; }
        .chart-container { position: relative; height: 300px; }
        .stocks-section { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .stocks-section h2 { color: #667eea; margin-bottom: 20px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { padding: 12px 25px; background: #f0f0f0; border: none; border-radius: 8px; cursor: pointer; font-size: 1em; }
        .tab:hover { background: #e0e0e0; }
        .tab.active { background: #667eea; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .stock-list { max-height: 600px; overflow-y: auto; }
        .stock-item { background: #f9f9f9; padding: 20px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid #667eea; }
        .stock-item:hover { background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stock-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .stock-symbol { font-size: 1.3em; font-weight: bold; }
        .stock-badge { padding: 5px 15px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }
        .badge-sell { background: #ff6b6b; color: white; }
        .badge-buy { background: #51cf66; color: white; }
        .badge-keep { background: #ffd43b; color: #333; }
        .stock-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 15px; }
        .detail-label { color: #666; font-size: 0.85em; }
        .detail-value { font-weight: bold; color: #333; }
        .profit-positive { color: #51cf66; }
        .profit-negative { color: #ff6b6b; }
        .search-box { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1em; margin-bottom: 20px; }
        .search-box:focus { outline: none; border-color: #667eea; }
        .empty { text-align: center; padding: 40px; color: #999; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Portfolio Allocation Dashboard</h1>
            <p>Generated on """ + datetime.now().strftime('%B %d, %Y at %I:%M %p') + """</p>
        </div>
        
        <div class="summary">
            <div class="card">
                <div class="card-title">Total Stocks</div>
                <div class="card-value">""" + str(total_stocks) + """</div>
                <div class="card-subtitle">In portfolio</div>
            </div>
            <div class="card">
                <div class="card-title">Portfolio Value</div>
                <div class="card-value">Rs """ + f"{total_value:,.0f}" + """</div>
                <div class="card-subtitle">Current holdings</div>
            </div>
            <div class="card">
                <div class="card-title">Average Score</div>
                <div class="card-value">""" + f"{avg_score:.1f}" + """</div>
                <div class="card-subtitle">Out of 100</div>
            </div>
            <div class="card">
                <div class="card-title">Capital Needed</div>
                <div class="card-value">Rs """ + f"{total_investment:,.0f}" + """</div>
                <div class="card-subtitle">For BUY stocks</div>
            </div>
            <div class="card">
                <div class="card-title">Profitable</div>
                <div class="card-value">""" + str(profitable) + """</div>
                <div class="card-subtitle">""" + str(losses) + """ in loss</div>
            </div>
            <div class="card">
                <div class="card-title">Avg Profit</div>
                <div class="card-value" style="color: """ + ('#51cf66' if avg_profit > 0 else '#ff6b6b') + """">""" + f"{avg_profit:.1f}%" + """</div>
                <div class="card-subtitle">Across portfolio</div>
            </div>
        </div>
        
        <div class="charts">
            <div class="chart-card">
                <h3>Action Breakdown</h3>
                <div class="chart-container"><canvas id="chart1"></canvas></div>
            </div>
            <div class="chart-card">
                <h3>Timing Priority</h3>
                <div class="chart-container"><canvas id="chart2"></canvas></div>
            </div>
            <div class="chart-card">
                <h3>Portfolio Types</h3>
                <div class="chart-container"><canvas id="chart3"></canvas></div>
            </div>
            <div class="chart-card">
                <h3>Top Sectors</h3>
                <div class="chart-container"><canvas id="chart4"></canvas></div>
            </div>
        </div>
        
        <div class="stocks-section">
            <h2>Priority Actions</h2>
            <div class="tabs">
                <button class="tab active" onclick="showTab(0)">Urgent Sells (""" + str(len(urgent_sells)) + """)</button>
                <button class="tab" onclick="showTab(1)">Top Buys (""" + str(len(urgent_buys)) + """)</button>
                <button class="tab" onclick="showTab(2)">Warnings (""" + str(len(warnings)) + """)</button>
                <button class="tab" onclick="showTab(3)">Profit Booking (""" + str(len(profit_booking)) + """)</button>
                <button class="tab" onclick="showTab(4)">All Stocks (""" + str(len(all_stocks)) + """)</button>
            </div>
            <div id="tab0" class="tab-content active"></div>
            <div id="tab1" class="tab-content"></div>
            <div id="tab2" class="tab-content"></div>
            <div id="tab3" class="tab-content"></div>
            <div id="tab4" class="tab-content">
                <input type="text" class="search-box" id="search" placeholder="Search stocks...">
                <div id="all-list"></div>
            </div>
        </div>
    </div>
    
    <script>
        const data = {
            actions: """ + json.dumps(actions) + """,
            timings: """ + json.dumps(timings) + """,
            types: """ + json.dumps(types) + """,
            sectors: """ + json.dumps(sectors) + """,
            urgentSells: """ + json.dumps(urgent_sells) + """,
            topBuys: """ + json.dumps(urgent_buys) + """,
            warnings: """ + json.dumps(warnings) + """,
            profitBooking: """ + json.dumps(profit_booking) + """,
            allStocks: """ + json.dumps(all_stocks) + """
        };
        
        const colors = { primary: '#667eea', success: '#51cf66', danger: '#ff6b6b', warning: '#ffd43b' };
        
        new Chart(document.getElementById('chart1'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(data.actions),
                datasets: [{
                    data: Object.values(data.actions),
                    backgroundColor: [colors.success, colors.danger, colors.warning]
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
        
        new Chart(document.getElementById('chart2'), {
            type: 'bar',
            data: {
                labels: Object.keys(data.timings),
                datasets: [{
                    label: 'Stocks',
                    data: Object.values(data.timings),
                    backgroundColor: colors.primary
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
        
        new Chart(document.getElementById('chart3'), {
            type: 'pie',
            data: {
                labels: Object.keys(data.types),
                datasets: [{
                    data: Object.values(data.types),
                    backgroundColor: [colors.primary, colors.warning, colors.danger]
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
        
        new Chart(document.getElementById('chart4'), {
            type: 'bar',
            data: {
                labels: Object.keys(data.sectors),
                datasets: [{
                    data: Object.values(data.sectors),
                    backgroundColor: colors.primary
                }]
            },
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false }
        });
        
        function createStockCard(s) {
            const pClass = s['MY_PROFIT_%'] > 0 ? 'profit-positive' : 'profit-negative';
            const pSign = s['MY_PROFIT_%'] > 0 ? '+' : '';
            const badgeClass = s.ACTION === 'SELL' ? 'badge-sell' : s.ACTION === 'BUY' ? 'badge-buy' : 'badge-keep';
            
            return `<div class="stock-item">
                <div class="stock-header">
                    <div>
                        <div class="stock-symbol">${s.symbol}</div>
                        <div style="color:#666;margin-top:5px;">${s.company_name}</div>
                    </div>
                    <span class="stock-badge ${badgeClass}">${s.ACTION}</span>
                </div>
                <div class="stock-details">
                    ${s['INVEST_₹'] > 0 ? `<div><span class="detail-label">Invest:</span> <span class="detail-value">Rs ${s['INVEST_₹'].toLocaleString()}</span></div>` : ''}
                    ${s['MY_VALUE_₹'] > 0 ? `<div><span class="detail-label">Value:</span> <span class="detail-value">Rs ${s['MY_VALUE_₹'].toLocaleString()}</span></div>` : ''}
                    ${s['MY_VALUE_₹'] > 0 ? `<div><span class="detail-label">Profit/Loss:</span> <span class="detail-value ${pClass}">${pSign}${s['MY_PROFIT_%'].toFixed(2)}%</span></div>` : ''}
                    <div><span class="detail-label">Score:</span> <span class="detail-value">${s.SCORE.toFixed(1)}/100</span></div>
                    <div><span class="detail-label">Price:</span> <span class="detail-value">Rs ${s.PRICE.toLocaleString()}</span></div>
                    <div><span class="detail-label">Sector:</span> <span class="detail-value">${s.sector}</span></div>
                    <div><span class="detail-label">Type:</span> <span class="detail-value">${s.TYPE}</span></div>
                </div>
                ${s.WHY ? `<div style="margin-top:15px;padding-top:15px;border-top:1px solid #ddd;"><span class="detail-label">Reason:</span> ${s.WHY}</div>` : ''}
            </div>`;
        }
        
        function showList(id, stocks) {
            const html = stocks.length === 0 ? '<div class="empty">No stocks in this category</div>' : 
                '<div class="stock-list">' + stocks.map(s => createStockCard(s)).join('') + '</div>';
            document.getElementById(id).innerHTML = html;
        }
        
        showList('tab0', data.urgentSells);
        showList('tab1', data.topBuys);
        showList('tab2', data.warnings);
        showList('tab3', data.profitBooking);
        showList('all-list', data.allStocks);
        
        function showTab(n) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById('tab' + n).classList.add('active');
            document.querySelectorAll('.tab')[n].classList.add('active');
        }
        
        document.getElementById('search').addEventListener('input', function(e) {
            const term = e.target.value.toLowerCase();
            const filtered = data.allStocks.filter(s => 
                s.symbol.toLowerCase().includes(term) || 
                s.company_name.toLowerCase().includes(term) ||
                s.sector.toLowerCase().includes(term)
            );
            showList('all-list', filtered);
        });
        
        console.log('Dashboard loaded:', data.allStocks.length, 'stocks');
    </script>
</body>
</html>"""
    
    # Save file
    output = "Portfolio_Allocation_Dashboard.html"
    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Dashboard created: {output}")
    print("Opening in browser...")
    
    webbrowser.open(output)
    return output

if __name__ == "__main__":
    try:
        create_dashboard()
        print("\nDashboard is ready!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
