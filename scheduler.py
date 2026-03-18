#!/usr/bin/env python3
"""
Scheduler — Automated daily analysis and outcome tracking.

Usage:
    python scheduler.py start           # Start the scheduler (blocks)
    python scheduler.py run-now         # Run analysis immediately then exit
    python scheduler.py update-outcomes # Update recommendation outcomes then exit
"""

import sys
import os
import argparse
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('scheduler')


def run_analysis():
    """Execute the full stock analysis."""
    logger.info("Starting scheduled analysis run...")
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from analyze_top200_stocks_enhanced import main as analysis_main
        analysis_main()
        logger.info("Analysis run completed successfully")
    except Exception as e:
        logger.error(f"Analysis run failed: {e}")


def run_outcome_update():
    """Update recommendation history outcomes."""
    logger.info("Starting outcome update...")
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from recommendation_history import RecommendationHistory
        rh = RecommendationHistory()
        updated = rh.update_outcomes()
        logger.info(f"Outcome update completed: {updated} fields updated")
    except Exception as e:
        logger.error(f"Outcome update failed: {e}")


def start_scheduler(analysis_hour=19, analysis_minute=0,
                    outcome_hour=9, outcome_minute=0):
    """Start the blocking scheduler with cron jobs."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("apscheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler()

    scheduler.add_job(
        run_analysis,
        CronTrigger(hour=analysis_hour, minute=analysis_minute),
        id='daily_analysis',
        name=f'Daily Analysis ({analysis_hour:02d}:{analysis_minute:02d})',
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_outcome_update,
        CronTrigger(hour=outcome_hour, minute=outcome_minute),
        id='daily_outcomes',
        name=f'Daily Outcome Update ({outcome_hour:02d}:{outcome_minute:02d})',
        misfire_grace_time=3600,
    )

    logger.info("=" * 60)
    logger.info("STOCK ANALYSIS SCHEDULER STARTED")
    logger.info("=" * 60)
    logger.info(f"  Analysis      : Daily at {analysis_hour:02d}:{analysis_minute:02d}")
    logger.info(f"  Outcome Update: Daily at {outcome_hour:02d}:{outcome_minute:02d}")
    logger.info("  Press Ctrl+C to stop")
    logger.info("=" * 60)

    jobs = scheduler.get_jobs()
    for job in jobs:
        logger.info(f"  Job: {job.name} | Next run: {job.next_run_time}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
        scheduler.shutdown(wait=False)


def main():
    parser = argparse.ArgumentParser(description='Stock Analysis Scheduler')
    parser.add_argument('command', choices=['start', 'run-now', 'update-outcomes'],
                        help='start: run scheduler; run-now: run analysis immediately; update-outcomes: backfill outcomes')
    parser.add_argument('--analysis-hour', type=int, default=19, help='Hour for daily analysis (default: 19)')
    parser.add_argument('--outcome-hour', type=int, default=9, help='Hour for outcome update (default: 9)')
    args = parser.parse_args()

    if args.command == 'start':
        start_scheduler(analysis_hour=args.analysis_hour, outcome_hour=args.outcome_hour)
    elif args.command == 'run-now':
        run_analysis()
    elif args.command == 'update-outcomes':
        run_outcome_update()


if __name__ == '__main__':
    main()
