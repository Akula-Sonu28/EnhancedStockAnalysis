"""
Portfolio Reporter - Comprehensive Report Generation

This module generates actionable portfolio reports including:
- Executive summaries
- Detailed analysis
- Action plans
- Risk assessments
- Performance tracking
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List
import logging
import os
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logging.warning("yfinance not available. Trading sheet will have limited functionality.")

class PortfolioReporter:
    """Comprehensive Portfolio Report Generator"""
    
    def __init__(self, portfolio_analyzer, portfolio_insights):
        """
        Initialize Portfolio Reporter
        
        Args:
            portfolio_analyzer: Instance of PortfolioAnalyzer
            portfolio_insights: Instance of PortfolioInsights
        """
        self.analyzer = portfolio_analyzer
        self.insights = portfolio_insights
        self.consolidation_data = None  # Will be set externally
        self.logger = logging.getLogger('PortfolioReporter')
        
    def generate_executive_summary(self) -> str:
        """Generate executive summary with key metrics and immediate actions"""
        try:
            performance = self.analyzer.portfolio_metrics
            exit_analysis = self.insights.analyze_exit_strategies()
            buy_analysis = self.insights.analyze_buy_recommendations()
            health_score = self.insights.calculate_portfolio_health_score()
            
            action_count = len(exit_analysis.get('immediate_exits', [])) + len(buy_analysis.get('top_buy_recommendations', [])[:3])
            
            summary = f"""
📊 PORTFOLIO EXECUTIVE SUMMARY
Date: {datetime.now().strftime('%B %d, %Y at %H:%M')}
════════════════════════════════════════════════════════

💰 FINANCIAL OVERVIEW
├─ Total Investment: ₹{performance.get('total_invested', 0):,.0f}
├─ Current Value: ₹{performance.get('current_value', 0):,.0f}  
├─ Total P&L: ₹{performance.get('total_pnl', 0):,.0f} ({performance.get('total_return_pct', 0):+.1f}%)
├─ Available Funds: ₹{self.analyzer.available_funds:,.0f}
└─ Portfolio Health Score: {health_score.get('overall_score', 0):.0f}/100

📈 TODAY'S PERFORMANCE
├─ Day P&L: ₹{performance.get('day_pnl', 0):,.0f} ({performance.get('day_return_pct', 0):+.2f}%)

🎯 IMMEDIATE ACTION ITEMS ({action_count} items)
"""
            
            # Immediate exits
            immediate_exits = exit_analysis.get('immediate_exits', [])
            if immediate_exits:
                summary += "\n🚨 URGENT EXITS REQUIRED:\n"
                for exit in immediate_exits[:3]:
                    summary += f"   • SELL {exit['instrument']} | {exit['current_return']:+.1f}% | {exit['rationale']}\n"
            
            # Top buy recommendations
            top_buys = buy_analysis.get('top_buy_recommendations', [])[:3]
            if top_buys:
                summary += "\n💡 TOP BUY OPPORTUNITIES:\n"
                for buy in top_buys:
                    summary += f"   • BUY {buy['symbol']} | ₹{buy.get('suggested_amount', 0):,.0f} | {buy['rationale']}\n"
            
            # Performance highlights
            top_performers = performance.get('top_performers', [])[:3]
            worst_performers = performance.get('worst_performers', [])[:2]
            
            if top_performers:
                summary += "\n🏆 TOP PERFORMERS:\n"
                for stock in top_performers:
                    summary += f"   • {stock['Instrument']}: {stock['Return_Pct']:+.1f}% (₹{stock['P&L']:,.0f})\n"
            
            if worst_performers:
                summary += "\n📉 NEEDS ATTENTION:\n"
                for stock in worst_performers:
                    summary += f"   • {stock['Instrument']}: {stock['Return_Pct']:+.1f}% (₹{stock['P&L']:,.0f})\n"
            
            summary += f"""
════════════════════════════════════════════════════════
⏰ Next Review: {(datetime.now() + pd.Timedelta(days=7)).strftime('%B %d, %Y')}
📊 Detailed analysis and action plan available below
"""
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating executive summary: {str(e)}")
            return "Error generating executive summary"
    
    def generate_detailed_analysis(self) -> str:
        """Generate detailed portfolio analysis"""
        try:
            performance = self.analyzer.portfolio_metrics
            sector_analysis = self.analyzer.analyze_sector_allocation()
            exit_analysis = self.insights.analyze_exit_strategies()
            buy_analysis = self.insights.analyze_buy_recommendations()
            rebalancing = self.insights.analyze_rebalancing_strategies()
            health_score = self.insights.calculate_portfolio_health_score()
            
            analysis = f"""
📊 DETAILED PORTFOLIO ANALYSIS
════════════════════════════════════════════════════════

🎯 PORTFOLIO HEALTH BREAKDOWN
├─ Performance Score: {health_score.get('performance_score', 0)}/30 
├─ Diversification Score: {health_score.get('diversification_score', 0)}/25
├─ Risk Management Score: {health_score.get('risk_score', 0)}/25
└─ Asset Allocation Score: {health_score.get('allocation_score', 0)}/20

📊 PERFORMANCE ANALYSIS
├─ Total Holdings: {performance.get('number_of_holdings', 0)} stocks
├─ Portfolio Volatility: {performance.get('portfolio_volatility', 0):.1f}%
├─ Top 5 Concentration: {performance.get('top_5_concentration', 0):.1f}%
├─ Sharpe Ratio Estimate: {performance.get('sharpe_estimate', 0):.2f}
"""
            
            # Sector allocation analysis
            sector_data = sector_analysis.get('sector_allocation', [])
            if sector_data:
                analysis += "\n🏭 SECTOR ALLOCATION:\n"
                for sector in sorted(sector_data, key=lambda x: x['Weight_Pct'], reverse=True)[:5]:
                    analysis += f"   • {sector['Sector']}: {sector['Weight_Pct']:.1f}% | Return: {sector['Return_Pct']:+.1f}%\n"
            
            # Risk analysis
            concentration_risks = rebalancing.get('concentration_risks', [])
            if concentration_risks:
                analysis += "\n⚠️ CONCENTRATION RISKS:\n"
                for risk in concentration_risks:
                    analysis += f"   • {risk['sector']}: {risk['current_weight']:.1f}% (Reduce by ₹{risk['excess_amount']:,.0f})\n"
            
            # Performance breakdown
            analysis += f"""
════════════════════════════════════════════════════════
📈 PERFORMANCE METRICS
├─ Best Performing Sector: {sector_analysis.get('best_performing_sector', 'N/A')}
├─ Worst Performing Sector: {sector_analysis.get('worst_performing_sector', 'N/A')}  
├─ Most Allocated Sector: {sector_analysis.get('most_allocated_sector', 'N/A')}
└─ Sector Risk Level: {sector_analysis.get('sector_concentration_risk', 0):.1f}%
"""
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error generating detailed analysis: {str(e)}")
            return "Error generating detailed analysis"
    
    def generate_action_plan(self) -> str:
        """Generate specific action plan with timelines and enhanced sell signals"""
        try:
            exit_analysis = self.insights.analyze_exit_strategies()
            buy_analysis = self.insights.analyze_buy_recommendations()
            rebalancing = self.insights.analyze_rebalancing_strategies()
            
            # Get enhanced sell recommendations
            enhanced_sells = self.insights.get_enhanced_sell_recommendations()
            
            action_plan = f"""
🎯 ACTIONABLE PORTFOLIO PLAN
════════════════════════════════════════════════════════

📅 IMMEDIATE ACTIONS (Next 1-3 days)
"""
            
            # Enhanced immediate sell signals with price targets
            immediate_sells = enhanced_sells.get('immediate_sells', [])
            if immediate_sells:
                action_plan += "🚨 URGENT SELL Orders (With Price Targets):\n"
                for i, sell in enumerate(immediate_sells, 1):
                    current_price = sell.get('current_price', 0)
                    target_price = sell.get('target_price', current_price)
                    expected_proceeds = sell.get('expected_proceeds', 0)
                    
                    action_plan += f"   {i}. SELL {sell['instrument']} | Target: ₹{target_price:.2f} | Proceeds: ₹{expected_proceeds:,.0f}\n"
                    action_plan += f"      └─ Current: ₹{current_price:.2f} | Reason: {sell['rationale']}\n"
                    action_plan += f"      └─ Timeline: {sell.get('timeline', 'ASAP')} | Stop Loss: ₹{sell.get('stop_loss_price', 0):.2f}\n"
            else:
                # Fallback to old format if enhanced not available
                immediate_exits = exit_analysis.get('immediate_exits', [])
                if immediate_exits:
                    action_plan += "🚨 URGENT SELL Orders:\n"
                    for i, exit in enumerate(immediate_exits, 1):
                        action_plan += f"   {i}. SELL {exit['instrument']} | Current: ₹{exit['current_value']:,.0f} | Return: {exit['current_return']:+.1f}%\n"
                        action_plan += f"      └─ Reason: {exit['rationale']}\n"
                else:
                    action_plan += "✅ No urgent sell actions required\n"
            
            action_plan += f"""
📅 SHORT TERM ACTIONS (Next 1-2 weeks)
"""
            
            # Portfolio Consolidation (25-30 stocks optimization)
            if self.consolidation_data and self.consolidation_data.get('action_needed'):
                consolidation_sells = self.consolidation_data.get('sell_recommendations', [])
                if consolidation_sells:
                    action_plan += "🎯 PORTFOLIO CONSOLIDATION (Target: 25-30 stocks):\n"
                    for sell in consolidation_sells[:5]:  # Show top 5
                        urgency_icon = {'IMMEDIATE': '📍', 'HIGH': '⚡', 'MEDIUM': '📅'}.get(sell.get('urgency', 'MEDIUM'), '📅')
                        action_plan += f"   {urgency_icon} SELL {sell['symbol']} | Target: ₹{sell['target_price']:.2f} | Proceeds: ₹{sell['expected_proceeds']:,.0f}\n"
                        action_plan += f"     └─ Priority: {sell.get('urgency', 'MEDIUM')} | {sell['rationale']}\n"
                    
                    total_proceeds = sum(sell['expected_proceeds'] for sell in consolidation_sells)
                    action_plan += f"   💰 Total Consolidation Proceeds: ₹{total_proceeds:,.0f}\n"
            
            # Enhanced profit booking with price targets
            profit_booking_enhanced = enhanced_sells.get('profit_booking', [])
            if profit_booking_enhanced:
                action_plan += "💰 PROFIT BOOKING with Price Targets:\n"
                for book in profit_booking_enhanced[:3]:
                    target_price = book.get('target_price', 0)
                    resistance = book.get('resistance_level', book.get('next_resistance', 0))
                    sell_type = book.get('sell_type', 'PARTIAL')
                    
                    action_plan += f"   • {book['instrument']} | Target: ₹{target_price:.2f} | Type: {sell_type}\n"
                    action_plan += f"     └─ Current: ₹{book.get('current_price', 0):.2f} | Next R: ₹{resistance:.2f} | {book['rationale']}\n"
            
            # Consider exits (fallback)
            consider_exits = exit_analysis.get('consider_exits', [])
            if consider_exits:
                action_plan += "⚠️ MONITOR for Exit:\n"
                for exit in consider_exits[:3]:
                    action_plan += f"   • {exit['instrument']} | {exit['rationale']}\n"
            
            action_plan += f"""
📅 MEDIUM TERM ACTIONS (Next 2-4 weeks)
"""
            
            # Buy recommendations
            top_buys = buy_analysis.get('top_buy_recommendations', [])
            if top_buys:
                action_plan += "💡 BUY Recommendations:\n"
                total_investment = 0
                for i, buy in enumerate(top_buys[:5], 1):
                    suggested_amount = buy.get('suggested_amount', 0)
                    total_investment += suggested_amount
                    action_plan += f"   {i}. BUY {buy['symbol']} | Amount: ₹{suggested_amount:,.0f} | Sector: {buy['sector']}\n"
                    action_plan += f"      └─ Score: {buy['priority_score']:.0f} | {buy['rationale']}\n"
                
                action_plan += f"\n   💰 Total Investment Required: ₹{total_investment:,.0f}\n"
                action_plan += f"   💳 Available Funds: ₹{self.analyzer.available_funds:,.0f}\n"
            
            # Enhanced Capital Rotation Strategy
            rotation_strategies = enhanced_sells.get('rotation_strategies', [])
            total_sale_proceeds = enhanced_sells.get('total_proceeds_available', 0)
            
            # Add consolidation rotation strategy
            consolidation_rotation = None
            if self.consolidation_data and self.consolidation_data.get('capital_rotation'):
                consolidation_rotation = self.consolidation_data['capital_rotation']
                consolidation_proceeds = consolidation_rotation.get('total_amount', 0)
                total_sale_proceeds += consolidation_proceeds
            
            if rotation_strategies or total_sale_proceeds > 0 or consolidation_rotation:
                action_plan += f"\n💫 CAPITAL ROTATION STRATEGY:\n"
                if total_sale_proceeds > 0:
                    action_plan += f"   📊 Expected Sale Proceeds: ₹{total_sale_proceeds:,.0f}\n"
                
                # Consolidation rotation first (highest priority)
                if consolidation_rotation:
                    allocation_plan = consolidation_rotation.get('allocation_plan', [])
                    action_plan += f"   🎯 CONSOLIDATION ROTATION (Top Performers):\n"
                    for allocation in allocation_plan[:3]:  # Show top 3
                        symbol = allocation['symbol']
                        amount = allocation['allocation_amount']
                        percentage = allocation['allocation_percentage']
                        action_plan += f"     └─ Strengthen {symbol}: +₹{amount:,.0f} ({percentage:.1f}%)\n"
                
                # Regular rotation strategies
                for rotation in rotation_strategies[:3]:  # Show top 3
                    source_stock = rotation.get('source_stock', 'Unknown')
                    proceeds = rotation.get('sale_proceeds', 0)
                    strategies = rotation.get('rotation_strategy', [])
                    
                    action_plan += f"   • From {source_stock} sale (₹{proceeds:,.0f}):\n"
                    for strategy in strategies[:2]:  # Top 2 strategies per stock
                        if strategy.get('type') == 'SECTOR_DIVERSIFICATION':
                            sectors = ', '.join(strategy.get('target_sectors', []))
                            action_plan += f"     └─ Diversify {strategy.get('allocation_pct', 0):.0f}% to {sectors}\n"
                        elif strategy.get('type') == 'UPGRADE_POSITIONS':
                            stocks = ', '.join(strategy.get('target_stocks', []))
                            action_plan += f"     └─ Upgrade {strategy.get('allocation_pct', 0):.0f}% to {stocks}\n"
            
            # Rebalancing
            capital_deployment = rebalancing.get('capital_deployment', {})
            if capital_deployment:
                priority_sectors = capital_deployment.get('priority_sectors', [])
                if priority_sectors:
                    action_plan += f"\n🎯 SECTOR REBALANCING Priority:\n"
                    for sector in priority_sectors:
                        action_plan += f"   • Increase allocation in {sector}\n"
            
            action_plan += f"""
════════════════════════════════════════════════════════
📊 EXPECTED OUTCOMES
├─ Risk Reduction: Improved diversification
├─ Performance: Optimized sector allocation  
├─ Cash Utilization: {min(100, self.analyzer.available_funds/10000*5):.0f}% deployment recommended
└─ Timeline: Full implementation in 4-6 weeks
"""
            
            return action_plan
            
        except Exception as e:
            self.logger.error(f"Error generating action plan: {str(e)}")
            return "Error generating action plan"
    
    def generate_risk_assessment(self) -> str:
        """Generate comprehensive risk assessment"""
        try:
            performance = self.analyzer.portfolio_metrics
            rebalancing = self.insights.analyze_rebalancing_strategies()
            health_score = self.insights.calculate_portfolio_health_score()
            
            risk_assessment = f"""
⚠️ PORTFOLIO RISK ASSESSMENT
════════════════════════════════════════════════════════

🎯 OVERALL RISK LEVEL: {self._calculate_risk_level(health_score)}

📊 RISK METRICS
├─ Portfolio Volatility: {performance.get('portfolio_volatility', 0):.1f}%
├─ Concentration Risk: {performance.get('top_5_concentration', 0):.1f}% in top 5 holdings
├─ Number of Holdings: {performance.get('number_of_holdings', 0)} stocks
└─ Sector Concentration: {self.analyzer.analyze_sector_allocation().get('sector_concentration_risk', 0):.1f}%

⚠️ IDENTIFIED RISKS
"""
            
            # Concentration risks
            concentration_risks = rebalancing.get('concentration_risks', [])
            position_risks = rebalancing.get('position_sizing', [])
            
            if concentration_risks or position_risks:
                risk_assessment += "🚨 CONCENTRATION RISKS:\n"
                
                for risk in concentration_risks:
                    risk_assessment += f"   • {risk['sector']} sector: {risk['current_weight']:.1f}% (Target: {risk['target_weight']:.1f}%)\n"
                
                for risk in position_risks:
                    risk_assessment += f"   • {risk['instrument']}: {risk['current_weight']:.1f}% of portfolio\n"
            else:
                risk_assessment += "✅ No significant concentration risks identified\n"
            
            # Performance risks
            worst_performers = performance.get('worst_performers', [])
            if worst_performers:
                losing_stocks = [stock for stock in worst_performers if stock['Return_Pct'] < -5]
                if losing_stocks:
                    risk_assessment += "\n📉 PERFORMANCE RISKS:\n"
                    for stock in losing_stocks[:3]:
                        risk_assessment += f"   • {stock['Instrument']}: {stock['Return_Pct']:+.1f}% loss\n"
            
            # Risk mitigation recommendations
            recommendations = health_score.get('recommendations', [])
            if recommendations:
                risk_assessment += "\n🛡️ RISK MITIGATION RECOMMENDATIONS:\n"
                for i, rec in enumerate(recommendations, 1):
                    risk_assessment += f"   {i}. {rec}\n"
            
            risk_assessment += f"""
════════════════════════════════════════════════════════
🎯 RISK MANAGEMENT SCORE: {health_score.get('risk_score', 0)}/25
📊 Action Required: {"HIGH" if health_score.get('risk_score', 0) < 15 else "MEDIUM" if health_score.get('risk_score', 0) < 20 else "LOW"}
"""
            
            return risk_assessment
            
        except Exception as e:
            self.logger.error(f"Error generating risk assessment: {str(e)}")
            return "Error generating risk assessment"
    
    def _calculate_risk_level(self, health_score: Dict) -> str:
        """Calculate overall portfolio risk level"""
        risk_score = health_score.get('risk_score', 0)
        diversification_score = health_score.get('diversification_score', 0)
        
        combined_score = (risk_score + diversification_score) / 2
        
        if combined_score >= 20:
            return "LOW RISK ✅"
        elif combined_score >= 15:
            return "MEDIUM RISK ⚠️"
        else:
            return "HIGH RISK 🚨"
    
    def generate_consolidation_report(self) -> str:
        """Generate portfolio consolidation recommendations"""
        try:
            if not self.consolidation_data or not self.consolidation_data.get('action_needed', False):
                return """
📊 PORTFOLIO CONSOLIDATION ANALYSIS
════════════════════════════════════════════════════════

✅ PORTFOLIO OPTIMALLY SIZED
Your portfolio is already within the optimal range of 25-30 stocks.
No consolidation actions required at this time.
"""
            
            current_count = self.consolidation_data.get('current_holdings', 0)
            removal_candidates = self.consolidation_data.get('removal_candidates', [])
            consolidation_impact = self.consolidation_data.get('consolidation_impact', {})
            
            # Simple consolidation report without detailed parsing
            return f"""
📊 PORTFOLIO CONSOLIDATION ANALYSIS
════════════════════════════════════════════════════════

🎯 CONSOLIDATION RECOMMENDED
Current Holdings: {current_count} stocks
Target Range: 25-30 stocks
Candidates for Removal: {len(removal_candidates)} stocks

Expected Impact:
• Total Proceeds: ₹{consolidation_impact.get('total_proceeds', 0):,.0f}
• Portfolio Optimization: Enhanced focus on top performers
• Risk Reduction: Improved diversification metrics

📋 Detailed consolidation recommendations are shown in the main action plan above.
"""
            
        except Exception as e:
            self.logger.error(f"Error generating consolidation report: {str(e)}")
            return f"Error generating consolidation report: {str(e)}"
    
    def generate_complete_report(self) -> str:
        """Generate complete comprehensive report"""
        try:
            report = f"""
{'='*60}
🏦 COMPREHENSIVE PORTFOLIO ANALYSIS REPORT
{'='*60}

{self.generate_executive_summary()}

{self.generate_detailed_analysis()}

{self.generate_action_plan()}

{self.generate_consolidation_report()}

{self.generate_risk_assessment()}

{'='*60}
📝 REPORT GENERATED: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}
🔄 NEXT REVIEW: {(datetime.now() + pd.Timedelta(days=7)).strftime('%B %d, %Y')}
{'='*60}
"""
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating complete report: {str(e)}")
            return f"Error generating complete report: {str(e)}"
    
    def save_report_to_file(self, report_content: str, filename: str = None) -> str:
        """Save report to file"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"Portfolio_Analysis_Report_{timestamp}.txt"
            
            # Create reports directory if it doesn't exist
            reports_dir = "reports/portfolio"
            os.makedirs(reports_dir, exist_ok=True)
            
            filepath = os.path.join(reports_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            self.logger.info(f"Report saved to: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error saving report to file: {str(e)}")
            return ""
    
    def calculate_support_resistance(self, symbol: str, period: str = "3mo") -> Dict:
        """Calculate support and resistance levels using Enhanced Stock Report or technical analysis"""
        # First try to get from Enhanced Stock Report
        enhanced_data = self._get_technical_from_enhanced_report(symbol)
        if enhanced_data:
            return enhanced_data
            
        # Fallback to real-time calculation
        if not YFINANCE_AVAILABLE:
            return self._default_technical_levels()
            
        try:
            stock = yf.Ticker(f"{symbol}.NS")
            # Reduced period and timeout for faster processing
            hist = stock.history(period=period, timeout=2)
            
            if hist.empty:
                return self._default_technical_levels()
            
            # Calculate pivot points
            high = hist['High'].max()
            low = hist['Low'].min()
            close = hist['Close'].iloc[-1]
            
            # Calculate pivot point
            pivot = (high + low + close) / 3
            
            # Calculate support and resistance levels
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)
            
            # Moving averages
            ma20 = hist['Close'].rolling(20).mean().iloc[-1] if len(hist) >= 20 else close
            ma50 = hist['Close'].rolling(50).mean().iloc[-1] if len(hist) >= 50 else close
            
            return {
                'current_price': close,
                'support_1': s1,
                'support_2': s2,
                'resistance_1': r1,
                'resistance_2': r2,
                'pivot_point': pivot,
                'ma_20': ma20,
                'ma_50': ma50,
                'volatility': hist['Close'].pct_change().std() * 100 * np.sqrt(252)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating technical levels for {symbol}: {str(e)}")
            return self._default_technical_levels()
    
    def _get_technical_from_enhanced_report(self, symbol: str) -> Dict:
        """Get technical data from Enhanced Stock Report for faster processing"""
        try:
            if not hasattr(self.analyzer, 'enhanced_report_df') or self.analyzer.enhanced_report_df is None:
                return {}
                
            # Check if Technical Analysis sheet exists
            if 'Technical Analysis' not in self.analyzer.enhanced_report_df:
                return {}
            
            tech_df = self.analyzer.enhanced_report_df['Technical Analysis']
            stock_data = tech_df[tech_df['symbol'] == symbol]
            
            if stock_data.empty:
                return {}
            
            stock_row = stock_data.iloc[0]
            
            return {
                'current_price': stock_row.get('current_price', 0),
                'support_1': stock_row.get('support_1', 0),
                'support_2': stock_row.get('support_2', 0),
                'resistance_1': stock_row.get('resistance_1', 0),
                'resistance_2': stock_row.get('resistance_2', 0),
                'pivot_point': stock_row.get('pivot_point', 0),
                'ma_20': stock_row.get('sma_20', 0),
                'ma_50': stock_row.get('sma_50', 0),
                'volatility': stock_row.get('volatility', 0)
            }
            
        except Exception as e:
            self.logger.debug(f"Could not get enhanced report data for {symbol}: {str(e)}")
            return {}
    
    def _default_technical_levels(self) -> Dict:
        """Return default technical levels when calculation fails"""
        return {
            'current_price': 0, 'support_1': 0, 'support_2': 0,
            'resistance_1': 0, 'resistance_2': 0, 'pivot_point': 0,
            'ma_20': 0, 'ma_50': 0, 'volatility': 0
        }
    
    def calculate_rsi(self, symbol: str, period: int = 14) -> float:
        """Calculate RSI indicator using Enhanced Stock Report or real-time data"""
        # First try Enhanced Stock Report
        try:
            if hasattr(self.analyzer, 'enhanced_report_df') and self.analyzer.enhanced_report_df is not None:
                if 'Technical Analysis' in self.analyzer.enhanced_report_df:
                    tech_df = self.analyzer.enhanced_report_df['Technical Analysis']
                    stock_data = tech_df[tech_df['symbol'] == symbol]
                    if not stock_data.empty:
                        return stock_data.iloc[0].get('rsi', 50.0)
        except Exception:
            pass
            
        if not YFINANCE_AVAILABLE:
            return 50.0
            
        try:
            stock = yf.Ticker(f"{symbol}.NS")
            hist = stock.history(period="3mo", timeout=2)
            
            if len(hist) < period:
                return 50.0
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1] if not rsi.empty else 50.0
            
        except Exception as e:
            self.logger.error(f"Error calculating RSI for {symbol}: {str(e)}")
            return 50.0
    
    def generate_trading_signals(self, symbol: str, holding_data: pd.Series) -> Dict:
        """Generate trading signals for a stock"""
        try:
            current_price = holding_data.get('LTP', 0)
            return_pct = holding_data.get('Return_Pct', 0)
            
            # Get technical levels
            tech_levels = self.calculate_support_resistance(symbol)
            rsi = self.calculate_rsi(symbol)
            
            # Calculate stop loss and targets
            stop_loss = max(tech_levels['support_1'], current_price * 0.9)
            target_1 = min(tech_levels['resistance_1'], current_price * 1.15)
            target_2 = tech_levels['resistance_2']
            
            # Generate signals
            entry_signal = "HOLD"
            if current_price <= tech_levels['support_1'] * 1.02 and rsi < 40:
                entry_signal = "STRONG BUY"
            elif current_price <= tech_levels['ma_20'] * 1.01 and rsi < 50:
                entry_signal = "BUY"
            elif current_price >= tech_levels['resistance_1'] * 0.98 and rsi > 70:
                entry_signal = "SELL"
            elif return_pct > 25:
                entry_signal = "PROFIT BOOKING"
            
            exit_signal = "HOLD"
            if return_pct < -10 or current_price <= stop_loss:
                exit_signal = "STOP LOSS"
            elif return_pct > 30 and rsi > 65:
                exit_signal = "PROFIT BOOKING"
            elif current_price >= target_1 and rsi > 60:
                exit_signal = "PARTIAL SELL"
            
            return {
                'entry_signal': entry_signal,
                'exit_signal': exit_signal,
                'stop_loss': round(stop_loss, 2),
                'target_1': round(target_1, 2),
                'target_2': round(target_2, 2),
                'support_1': round(tech_levels['support_1'], 2),
                'support_2': round(tech_levels['support_2'], 2),
                'resistance_1': round(tech_levels['resistance_1'], 2),
                'resistance_2': round(tech_levels['resistance_2'], 2),
                'rsi': round(rsi, 1),
                'rsi_signal': 'OVERSOLD' if rsi < 30 else 'OVERBOUGHT' if rsi > 70 else 'NEUTRAL',
                'trend': 'BULLISH' if current_price > tech_levels['ma_20'] else 'BEARISH'
            }
            
        except Exception as e:
            self.logger.error(f"Error generating trading signals for {symbol}: {str(e)}")
            return {}
    
    def generate_comprehensive_trading_sheet(self) -> pd.DataFrame:
        """Generate comprehensive trading sheet with technical analysis"""
        try:
            if self.analyzer.holdings_df is None:
                return pd.DataFrame()
            
            trading_data = []
            total_holdings = len(self.analyzer.holdings_df)
            self.logger.info(f"Generating trading sheet for {total_holdings} holdings...")
            
            for index, holding in self.analyzer.holdings_df.iterrows():
                symbol = holding['Instrument']
                
                # Show progress every 10 stocks
                if (index + 1) % 10 == 0 or index == 0:
                    print(f"   └─ Processing {index + 1}/{total_holdings}: {symbol}")
                
                # Generate trading signals (with timeout handling)
                try:
                    signals = self.generate_trading_signals(symbol, holding)
                except Exception as e:
                    self.logger.debug(f"Skipping technical analysis for {symbol}: {str(e)[:50]}...")
                    signals = {}  # Use empty signals if technical analysis fails
                
                # Get enhanced sell signal for this stock
                enhanced_sell_signal = 'HOLD'
                enhanced_target_price = 0
                enhanced_timeline = 'N/A'
                
                try:
                    enhanced_sells = self.insights.get_enhanced_sell_recommendations()
                    
                    # Check if this stock is in immediate sells
                    for sell in enhanced_sells.get('immediate_sells', []):
                        if sell['instrument'] == symbol:
                            enhanced_sell_signal = 'IMMEDIATE SELL'
                            enhanced_target_price = sell.get('target_price', 0)
                            enhanced_timeline = sell.get('timeline', 'ASAP')
                            break
                    
                    # Check if this stock is in profit booking
                    if enhanced_sell_signal == 'HOLD':
                        for profit in enhanced_sells.get('profit_booking', []):
                            if profit['instrument'] == symbol:
                                enhanced_sell_signal = f"{profit.get('sell_type', 'PARTIAL')} SELL"
                                enhanced_target_price = profit.get('target_price', 0)
                                enhanced_timeline = profit.get('timeline', '1-2 weeks')
                                break
                                
                except Exception as e:
                    self.logger.debug(f"Could not get enhanced sell signal for {symbol}: {str(e)}")
                
                # Compile trading data
                stock_data = {
                    'Symbol': symbol,
                    'Current_Price': holding.get('LTP', 0),
                    'Quantity': holding.get('Qty.', 0),
                    'Avg_Cost': holding.get('Avg. cost', 0),
                    'Invested': holding.get('Invested', 0),
                    'Current_Value': holding.get('Cur. val', 0),
                    'PnL': holding.get('P&L', 0),
                    'Return_Pct': holding.get('Return_Pct', 0),
                    'Day_Change_Pct': holding.get('Day chg.', 0),
                    
                    # Technical Analysis
                    'Support_1_S1': signals.get('support_1', 0),
                    'Support_2_S2': signals.get('support_2', 0),
                    'Resistance_1_R1': signals.get('resistance_1', 0),
                    'Resistance_2_R2': signals.get('resistance_2', 0),
                    
                    # Trading Signals
                    'Entry_Signal': signals.get('entry_signal', 'HOLD'),
                    'Exit_Signal': signals.get('exit_signal', 'HOLD'),
                    'Stop_Loss': signals.get('stop_loss', 0),
                    'Target_1': signals.get('target_1', 0),
                    'Target_2': signals.get('target_2', 0),
                    
                    # Enhanced Sell Signals (NEW)
                    'Enhanced_Sell_Signal': enhanced_sell_signal,
                    'Enhanced_Target_Price': enhanced_target_price,
                    'Enhanced_Timeline': enhanced_timeline,
                    
                    # Technical Indicators
                    'RSI': signals.get('rsi', 50),
                    'RSI_Signal': signals.get('rsi_signal', 'NEUTRAL'),
                    'Trend': signals.get('trend', 'NEUTRAL'),
                    
                    # Portfolio Context
                    'Weight_in_Portfolio': holding.get('Weight', 0),
                    'Sector': holding.get('Sector', 'Unknown')
                }
                
                trading_data.append(stock_data)
            
            # Create DataFrame
            trading_df = pd.DataFrame(trading_data)
            
            # Add new buy recommendations
            buy_analysis = self.insights.analyze_buy_recommendations()
            buy_recommendations = buy_analysis.get('top_buy_recommendations', [])
            
            for rec in buy_recommendations[:5]:
                new_buy_data = {
                    'Symbol': f"💡 {rec['symbol']} (NEW BUY)",
                    'Current_Price': rec.get('current_price', 0),
                    'Entry_Signal': 'RECOMMENDED BUY',
                    'Sector': rec.get('sector', 'Unknown'),
                    'Target_1': rec.get('current_price', 0) * 1.15,
                    'Stop_Loss': rec.get('current_price', 0) * 0.9,
                    'Investment_Amount': rec.get('suggested_amount', 0)
                }
                trading_df = pd.concat([trading_df, pd.DataFrame([new_buy_data])], ignore_index=True)
            
            # Sort by Return_Pct
            trading_df = trading_df.sort_values('Return_Pct', ascending=False, na_position='last')
            
            self.logger.info(f"Generated comprehensive trading sheet with {len(trading_df)} entries")
            return trading_df
            
        except Exception as e:
            self.logger.error(f"Error generating comprehensive trading sheet: {str(e)}")
            return pd.DataFrame()

    def generate_excel_report(self, include_trading_sheet: bool = True) -> str:
        """Generate detailed Excel report with multiple sheets including trading sheet"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"Portfolio_Analysis_{timestamp}.xlsx"
            
            reports_dir = "reports/portfolio"
            os.makedirs(reports_dir, exist_ok=True)
            filepath = os.path.join(reports_dir, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Holdings Summary
                holdings_summary = self.analyzer.holdings_df.copy()
                holdings_summary.to_excel(writer, sheet_name='Holdings_Summary', index=False)
                
                # Comprehensive Trading Sheet - ADD THIS AS THE MAIN FEATURE
                if include_trading_sheet:
                    self.logger.info("Generating comprehensive trading sheet...")
                    trading_df = self.generate_comprehensive_trading_sheet()
                    if not trading_df.empty:
                        trading_df.to_excel(writer, sheet_name='Trading_Sheet', index=False)
                        self.logger.info(f"Trading sheet added with {len(trading_df)} entries")
                
                # Performance Analysis
                performance_df = pd.DataFrame([self.analyzer.portfolio_metrics])
                performance_df.to_excel(writer, sheet_name='Performance_Metrics', index=False)
                
                # Sector Analysis
                if self.analyzer.sector_data is not None:
                    self.analyzer.sector_data.to_excel(writer, sheet_name='Sector_Analysis', index=False)
                
                # Exit Recommendations
                exit_analysis = self.insights.analyze_exit_strategies()
                if exit_analysis.get('immediate_exits'):
                    exits_df = pd.DataFrame(exit_analysis['immediate_exits'] + exit_analysis.get('consider_exits', []))
                    exits_df.to_excel(writer, sheet_name='Exit_Recommendations', index=False)
                
                # Buy Recommendations
                buy_analysis = self.insights.analyze_buy_recommendations()
                if buy_analysis.get('top_buy_recommendations'):
                    buys_df = pd.DataFrame(buy_analysis['top_buy_recommendations'])
                    buys_df.to_excel(writer, sheet_name='Buy_Recommendations', index=False)
                
                # Enhanced Sell Signals - NEW FEATURE
                try:
                    enhanced_sells = self.insights.get_enhanced_sell_recommendations()
                    self.logger.info("Adding enhanced sell signals to Excel...")
                    
                    # Immediate Sells with Price Targets
                    immediate_sells = enhanced_sells.get('immediate_sells', [])
                    if immediate_sells:
                        immediate_df = pd.DataFrame(immediate_sells)
                        immediate_df.to_excel(writer, sheet_name='Immediate_Sells', index=False)
                        self.logger.info(f"Added {len(immediate_df)} immediate sell recommendations")
                    
                    # Profit Booking with Price Targets
                    profit_booking = enhanced_sells.get('profit_booking', [])
                    if profit_booking:
                        profit_df = pd.DataFrame(profit_booking)
                        profit_df.to_excel(writer, sheet_name='Profit_Booking', index=False)
                        self.logger.info(f"Added {len(profit_df)} profit booking recommendations")
                    
                    # Capital Rotation Strategies
                    rotation_strategies = enhanced_sells.get('rotation_strategies', [])
                    if rotation_strategies:
                        # Flatten rotation strategies for Excel
                        rotation_data = []
                        for strategy in rotation_strategies:
                            source_stock = strategy.get('source_stock', 'Unknown')
                            proceeds = strategy.get('sale_proceeds', 0)
                            for rotation in strategy.get('rotation_strategy', []):
                                rotation_data.append({
                                    'Source_Stock': source_stock,
                                    'Sale_Proceeds': proceeds,
                                    'Rotation_Type': rotation.get('type', 'Unknown'),
                                    'Target_Sectors': ', '.join(rotation.get('target_sectors', [])),
                                    'Target_Stocks': ', '.join(rotation.get('target_stocks', [])),
                                    'Allocation_Percent': rotation.get('allocation_pct', 0),
                                    'Rationale': rotation.get('rationale', '')
                                })
                        
                        if rotation_data:
                            rotation_df = pd.DataFrame(rotation_data)
                            rotation_df.to_excel(writer, sheet_name='Capital_Rotation', index=False)
                            self.logger.info(f"Added {len(rotation_df)} capital rotation strategies")
                    
                    # Enhanced Sell Summary
                    sell_summary = {
                        'Total_Immediate_Sells': len(immediate_sells),
                        'Total_Profit_Booking': len(profit_booking),
                        'Total_Expected_Proceeds': enhanced_sells.get('total_proceeds_available', 0),
                        'Total_Rotation_Strategies': len(rotation_strategies),
                        'Analysis_Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    sell_summary_df = pd.DataFrame([sell_summary])
                    sell_summary_df.to_excel(writer, sheet_name='Enhanced_Sell_Summary', index=False)
                    
                except Exception as e:
                    self.logger.warning(f"Could not add enhanced sell signals to Excel: {str(e)}")
                
                # Health Score
                health_score = self.insights.calculate_portfolio_health_score()
                health_df = pd.DataFrame([health_score])
                health_df.to_excel(writer, sheet_name='Portfolio_Health', index=False)
                
                # Consolidation Analysis
                if hasattr(self, 'consolidation_data') and self.consolidation_data and self.consolidation_data.get('action_needed', False):
                    consolidation_candidates = self.consolidation_data.get('removal_candidates', [])
                    if consolidation_candidates:
                        consolidation_df = pd.DataFrame(consolidation_candidates)
                        consolidation_df.to_excel(writer, sheet_name='Consolidation_Plan', index=False)
                        self.logger.info(f"Added {len(consolidation_candidates)} consolidation candidates")
                    
                    # Add consolidation sell recommendations
                    consolidation_sells = self.consolidation_data.get('sell_recommendations', [])
                    if consolidation_sells:
                        consolidation_sells_df = pd.DataFrame(consolidation_sells)
                        consolidation_sells_df.to_excel(writer, sheet_name='Consolidation_Sells', index=False)
                        self.logger.info(f"Added {len(consolidation_sells)} consolidation sell recommendations")
                    
                    # Add capital rotation plan
                    capital_rotation = self.consolidation_data.get('capital_rotation', {})
                    if capital_rotation and capital_rotation.get('allocation_plan'):
                        rotation_plan_df = pd.DataFrame(capital_rotation['allocation_plan'])
                        rotation_plan_df.to_excel(writer, sheet_name='Capital_Rotation_Plan', index=False)
                        self.logger.info(f"Added capital rotation plan with {len(rotation_plan_df)} allocations")
                
                # Trading Summary with Enhanced Signals
                if include_trading_sheet and not trading_df.empty:
                    summary_data = {
                        'Total_Stocks': len(trading_df[trading_df['Quantity'] > 0]),
                        'Strong_Buy_Signals': len(trading_df[trading_df['Entry_Signal'] == 'STRONG BUY']),
                        'Profit_Booking_Candidates': len(trading_df[trading_df['Exit_Signal'] == 'PROFIT BOOKING']),
                        'Stop_Loss_Required': len(trading_df[trading_df['Exit_Signal'] == 'STOP LOSS']),
                        'High_RSI_Stocks': len(trading_df[trading_df['RSI'] > 70]),
                        'Low_RSI_Stocks': len(trading_df[trading_df['RSI'] < 30]),
                        
                        # Enhanced Sell Signal Counts (NEW)
                        'Enhanced_Immediate_Sells': len(trading_df[trading_df['Enhanced_Sell_Signal'] == 'IMMEDIATE SELL']),
                        'Enhanced_Partial_Sells': len(trading_df[trading_df['Enhanced_Sell_Signal'].str.contains('PARTIAL SELL', na=False)]),
                        'Enhanced_Full_Sells': len(trading_df[trading_df['Enhanced_Sell_Signal'].str.contains('FULL SELL', na=False)]),
                        
                        'Available_Funds': self.analyzer.available_funds
                    }
                    summary_df = pd.DataFrame([summary_data])
                    summary_df.to_excel(writer, sheet_name='Trading_Summary', index=False)
            
            self.logger.info(f"Excel report with trading sheet saved to: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error generating Excel report: {str(e)}")
            return ""