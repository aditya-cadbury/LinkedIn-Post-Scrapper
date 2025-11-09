"""
Scheduler module for running the LinkedIn scraper periodically.
Supports both cron-style scheduling and Python schedule library.
"""
import asyncio
import schedule
import time
from datetime import datetime
import sys
import os

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main as run_scraper


def run_scheduled_scrape():
    """Wrapper to run the async scraper in a scheduled context."""
    print(f"\n{'='*80}")
    print(f"Scheduled run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    try:
        # Run the async main function
        asyncio.run(run_scraper())
        print(f"\nScheduled scrape completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"\nERROR: Error in scheduled scrape: {e}")
        import traceback
        traceback.print_exc()


def setup_daily_schedule(hour: int = 9, minute: int = 0):
    """
    Set up daily schedule at specified time.
    
    Args:
        hour: Hour of day (0-23)
        minute: Minute of hour (0-59)
    """
    schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(run_scheduled_scrape)
    print(f"Scheduled daily runs at {hour:02d}:{minute:02d}")


def setup_hourly_schedule():
    """Set up hourly schedule."""
    schedule.every().hour.do(run_scheduled_scrape)
    print("Scheduled hourly runs")


def setup_custom_schedule(interval_minutes: int):
    """
    Set up custom interval schedule.
    
    Args:
        interval_minutes: Minutes between runs
    """
    schedule.every(interval_minutes).minutes.do(run_scheduled_scrape)
    print(f"Scheduled runs every {interval_minutes} minutes")


def run_scheduler():
    """Main scheduler loop."""
    print("="*80)
    print("LinkedIn Scraper Scheduler")
    print("="*80)
    print("\nChoose scheduling option:")
    print("1. Daily at 9:00 AM")
    print("2. Hourly")
    print("3. Every 6 hours")
    print("4. Every 12 hours")
    print("5. Custom interval (in minutes)")
    print("6. Run once immediately (for testing)")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == "1":
        setup_daily_schedule(9, 0)
    elif choice == "2":
        setup_hourly_schedule()
    elif choice == "3":
        setup_custom_schedule(360)  # 6 hours
    elif choice == "4":
        setup_custom_schedule(720)  # 12 hours
    elif choice == "5":
        minutes = int(input("Enter interval in minutes: "))
        setup_custom_schedule(minutes)
    elif choice == "6":
        print("\nRunning scraper once...")
        run_scheduled_scrape()
        return
    else:
        print("Invalid choice. Exiting.")
        return
    
    print("\nScheduler started. Press Ctrl+C to stop.\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\n\nScheduler stopped by user.")


if __name__ == "__main__":
    run_scheduler()

