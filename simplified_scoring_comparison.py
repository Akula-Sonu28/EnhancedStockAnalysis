#!/usr/bin/env python3
"""
SIMPLIFIED SCORING COMPARISON USING EXISTING BACKTESTS
======================================================

Instead of trying to integrate all systems directly, let's:
1. Run each existing backtest system separately
2. Compare their results
3. Generate a unified comparison report

This uses the proven backtest systems we already have.
"""

import pandas as pd
import numpy as np
import subprocess
import os
import glob
from datetime import datetime
import json

class SimplifiedScoringComparison:
    def __init__(self):
        self.results = {}
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def run_backtest_comparison(self):
        """Run all available backtest systems and compare results"""
        print("=" * 100)
        print("🔍 SIMPLIFIED SCORING SYSTEMS COMPARISON")
        print("=" * 100)
        
        # List of backtest systems to run
        backtest_systems = [
            {
                'name': 'Comprehensive System',
                'file': 'comprehensive_backtest.py',
                'description': 'Full enhanced analysis system'
            },
            {
                'name': 'Corrected Scoring',
                'file': 'backtest_scoring_system.py', 
                'description': 'CorrectedScoringEngine backtest'
            }
        ]
        
        # Check which systems are available
        available_systems = []
        for system in backtest_systems:
            if os.path.exists(system['file']):
                available_systems.append(system)
                print(f"✅ Found {system['name']}: {system['file']}")
            else:
                print(f"❌ Missing {system['name']}: {system['file']}")
        
        if not available_systems:
            print("❌ No backtest systems found!")
            return
        
        print(f"\n🚀 Running {len(available_systems)} backtest systems...")
        
        # Run each system and capture results
        for system in available_systems:
            print(f"\n" + "="*50)
            print(f"🧪 Running {system['name']}")
            print("="*50)
            
            try:
                result = subprocess.run(
                    ['python', system['file']], 
                    capture_output=True, 
                    text=True, 
                    timeout=300  # 5 minute timeout
                )
                
                self.results[system['name']] = {
                    'success': result.returncode == 0,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'file': system['file']
                }
                
                if result.returncode == 0:
                    print(f"✅ {system['name']} completed successfully")
                    # Show key metrics from output
                    self._extract_key_metrics(system['name'], result.stdout)
                else:
                    print(f"❌ {system['name']} failed with error:")
                    print(result.stderr[:500])  # First 500 chars of error
                    
            except subprocess.TimeoutExpired:
                print(f"⏰ {system['name']} timed out (>5 minutes)")
                self.results[system['name']] = {
                    'success': False,
                    'stdout': '',
                    'stderr': 'Timeout after 5 minutes',
                    'file': system['file']
                }
            except Exception as e:
                print(f"❌ {system['name']} crashed: {e}")
                self.results[system['name']] = {
                    'success': False,
                    'stdout': '',
                    'stderr': str(e),
                    'file': system['file']
                }
        
        # Generate comparison report
        self._generate_comparison_report()
        
        print(f"\n✅ COMPARISON COMPLETE!")
        print(f"📊 Results saved to: scoring_comparison_report_{self.timestamp}.txt")
        
    def _extract_key_metrics(self, system_name, output):
        """Extract key performance metrics from system output"""
        lines = output.split('\n')
        metrics = {}
        
        # Look for common performance indicators
        for line in lines:
            line = line.strip()
            
            # Average return
            if 'Average Return:' in line or 'avg return:' in line.lower():
                try:
                    # Extract percentage
                    parts = line.split(':')
                    if len(parts) > 1:
                        value = parts[1].strip().replace('%', '').replace('+', '')
                        metrics['avg_return'] = float(value.split()[0])
                except:
                    pass
            
            # Success rate
            elif 'Success Rate' in line or 'success rate' in line.lower():
                try:
                    parts = line.split(':')
                    if len(parts) > 1:
                        value = parts[1].strip().replace('%', '')
                        metrics['success_rate'] = float(value.split()[0])
                except:
                    pass
                    
            # Total tests
            elif 'Total Tests:' in line or 'total tests:' in line.lower():
                try:
                    parts = line.split(':')
                    if len(parts) > 1:
                        value = parts[1].strip()
                        metrics['total_tests'] = int(value.split()[0])
                except:
                    pass
            
            # Correlation
            elif 'correlation' in line.lower() and ':' in line:
                try:
                    parts = line.split(':')
                    if len(parts) > 1:
                        value = parts[1].strip()
                        if 'NOT SIGNIFICANT' not in value:
                            metrics['correlation'] = float(value.split()[0])
                except:
                    pass
        
        if metrics:
            print(f"\n📊 Key Metrics for {system_name}:")
            for key, value in metrics.items():
                if key == 'avg_return':
                    print(f"   Average Return: {value:+.2f}%")
                elif key == 'success_rate':
                    print(f"   Success Rate: {value:.1f}%")
                elif key == 'total_tests':
                    print(f"   Total Tests: {value}")
                elif key == 'correlation':
                    print(f"   Correlation: {value:.3f}")
        
        self.results[system_name]['metrics'] = metrics
    
    def _generate_comparison_report(self):
        """Generate a comprehensive comparison report"""
        report_filename = f'scoring_comparison_report_{self.timestamp}.txt'
        
        with open(report_filename, 'w') as f:
            f.write("="*100 + "\n")
            f.write("SCORING SYSTEMS COMPARISON REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*100 + "\n\n")
            
            # Executive Summary
            f.write("📊 EXECUTIVE SUMMARY\n")
            f.write("-"*50 + "\n")
            
            successful_systems = [name for name, result in self.results.items() if result['success']]
            failed_systems = [name for name, result in self.results.items() if not result['success']]
            
            f.write(f"✅ Successful runs: {len(successful_systems)}\n")
            f.write(f"❌ Failed runs: {len(failed_systems)}\n\n")
            
            if successful_systems:
                f.write("Successful Systems:\n")
                for system in successful_systems:
                    f.write(f"  • {system}\n")
            
            if failed_systems:
                f.write(f"\nFailed Systems:\n")
                for system in failed_systems:
                    f.write(f"  • {system}: {self.results[system]['stderr'][:100]}...\n")
            
            # Performance Comparison
            f.write(f"\n\n📈 PERFORMANCE COMPARISON\n")
            f.write("-"*50 + "\n")
            
            # Create comparison table
            comparison_data = []
            for system_name, result in self.results.items():
                if result['success'] and 'metrics' in result:
                    metrics = result['metrics']
                    comparison_data.append({
                        'System': system_name,
                        'Avg Return': metrics.get('avg_return', 'N/A'),
                        'Success Rate': metrics.get('success_rate', 'N/A'),
                        'Total Tests': metrics.get('total_tests', 'N/A'),
                        'Correlation': metrics.get('correlation', 'N/A')
                    })
            
            if comparison_data:
                # Sort by average return
                comparison_data.sort(key=lambda x: x['Avg Return'] if isinstance(x['Avg Return'], (int, float)) else -999, reverse=True)
                
                f.write(f"{'System':<20} {'Avg Return':<12} {'Success Rate':<12} {'Tests':<8} {'Correlation':<12}\n")
                f.write("-"*70 + "\n")
                
                for row in comparison_data:
                    avg_ret = f"{row['Avg Return']:+.2f}%" if isinstance(row['Avg Return'], (int, float)) else str(row['Avg Return'])
                    success = f"{row['Success Rate']:.1f}%" if isinstance(row['Success Rate'], (int, float)) else str(row['Success Rate'])
                    corr = f"{row['Correlation']:.3f}" if isinstance(row['Correlation'], (int, float)) else str(row['Correlation'])
                    
                    f.write(f"{row['System']:<20} {avg_ret:<12} {success:<12} {str(row['Total Tests']):<8} {corr:<12}\n")
            else:
                f.write("❌ No performance metrics available for comparison\n")
            
            # Detailed Results
            f.write(f"\n\n📋 DETAILED RESULTS\n")
            f.write("="*50 + "\n")
            
            for system_name, result in self.results.items():
                f.write(f"\n{system_name.upper()}\n")
                f.write("-"*30 + "\n")
                f.write(f"File: {result['file']}\n")
                f.write(f"Success: {result['success']}\n")
                
                if result['success']:
                    f.write("Key Output:\n")
                    # Write last 20 lines of output (usually contains summary)
                    lines = result['stdout'].split('\n')[-20:]
                    for line in lines:
                        if line.strip():
                            f.write(f"  {line}\n")
                else:
                    f.write(f"Error: {result['stderr']}\n")
            
            # Recommendations
            f.write(f"\n\n💡 RECOMMENDATIONS\n")
            f.write("-"*50 + "\n")
            
            if len(successful_systems) > 1:
                f.write("1. Multiple systems ran successfully - compare their approaches\n")
                f.write("2. Consider combining best elements from each system\n")
                f.write("3. Focus on the system with highest average return AND correlation\n")
            elif len(successful_systems) == 1:
                f.write(f"1. Only {successful_systems[0]} ran successfully\n")
                f.write("2. Fix other systems and re-run comparison\n")
                f.write("3. Use working system as baseline for improvements\n")
            else:
                f.write("1. All systems failed - check dependencies and data availability\n")
                f.write("2. Start with simplest backtest system first\n")
                f.write("3. Debug issues one system at a time\n")
        
        # Also save results as JSON for programmatic access
        json_filename = f'scoring_comparison_data_{self.timestamp}.json'
        with open(json_filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"📋 Detailed report: {report_filename}")
        print(f"📊 Data export: {json_filename}")

if __name__ == "__main__":
    comparator = SimplifiedScoringComparison()
    comparator.run_backtest_comparison()