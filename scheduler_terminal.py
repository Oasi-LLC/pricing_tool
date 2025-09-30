#!/usr/bin/env python3
"""
Terminal-friendly scheduler daemon with enhanced progress tracking
This version shows detailed progress information directly in the terminal
"""

import time
import logging
import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.scheduler import (
    load_scheduler_config, get_scheduler_status, 
    is_time_to_refresh, run_scheduled_refresh, get_lisbon_time
)

# Setup logging with enhanced terminal output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def print_enhanced_status():
    """Print enhanced status information to terminal"""
    try:
        from utils.progress_tracker import get_scheduler_status
        status = get_scheduler_status()
        
        if status.get("refresh_active", False):
            print("\n" + "="*60)
            print("🔄 SCHEDULER REFRESH IN PROGRESS")
            print("="*60)
            
            # Overall progress
            total_progress = status.get("total_progress", 0)
            print(f"📈 Overall Progress: {total_progress:.1f}%")
            
            # Current step
            current_step = status.get("current_step", "Unknown")
            step_progress = status.get("step_progress", 0)
            current_operation = status.get("current_operation", "")
            
            print(f"🔄 Current Step: {current_step.replace('_', ' ').title()}")
            print(f"📊 Step Progress: {step_progress:.1f}%")
            
            if current_operation:
                print(f"⚙️ Current Operation: {current_operation}")
            
            # Properties progress
            properties_total = status.get("properties_total", 0)
            properties_completed = status.get("properties_completed", 0)
            properties_failed = status.get("properties_failed", 0)
            properties_remaining = status.get("properties_remaining", 0)
            
            print(f"\n🏠 Properties Progress:")
            print(f"   ✅ Completed: {properties_completed}/{properties_total}")
            print(f"   ❌ Failed: {properties_failed}")
            print(f"   ⏳ Remaining: {properties_remaining}")
            
            # API calls progress
            api_calls_made = status.get("api_calls_made", 0)
            api_calls_total = status.get("api_calls_total", 0)
            
            if api_calls_total > 0:
                print(f"\n📡 API Calls Progress:")
                print(f"   📊 Made: {api_calls_made}/{api_calls_total} ({api_calls_made/api_calls_total*100:.1f}%)")
            
            # Time information
            start_time = status.get("start_time")
            estimated_completion = status.get("estimated_completion")
            
            if start_time:
                start_dt = datetime.fromisoformat(start_time)
                print(f"\n⏱️ Time Information:")
                print(f"   🚀 Started: {start_dt.strftime('%H:%M:%S')}")
                
                if estimated_completion:
                    est_dt = datetime.fromisoformat(estimated_completion)
                    now = datetime.now()
                    remaining = (est_dt - now).total_seconds()
                    print(f"   🎯 Estimated completion: {est_dt.strftime('%H:%M:%S')}")
                    if remaining > 0:
                        print(f"   ⏳ Time remaining: {remaining/60:.1f} minutes")
            
            print("="*60)
        else:
            print("💤 Scheduler is not currently running a refresh")
            
    except Exception as e:
        print(f"❌ Error getting enhanced status: {e}")

def main():
    """Main daemon loop with enhanced terminal output"""
    print("🚀 Starting Enhanced Scheduler Daemon...")
    print("📊 This version shows detailed progress in the terminal")
    print("="*60)
    
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    last_status_check = 0
    
    while True:
        try:
            # Check if scheduler is enabled
            config = load_scheduler_config()
            if not config.get('enabled', False):
                print("💤 Scheduler is disabled. Waiting 5 minutes before checking again...")
                time.sleep(300)  # Wait 5 minutes
                consecutive_errors = 0  # Reset error counter
                continue
            
            # Get current status
            status = get_scheduler_status()
            current_time = get_lisbon_time()
            
            # Show enhanced status every 30 seconds
            if time.time() - last_status_check > 30:
                print_enhanced_status()
                last_status_check = time.time()
            
            logger.info(f"Current Lisbon time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if status.get('next_refresh'):
                next_refresh = status['next_refresh']
                logger.info(f"Next scheduled refresh: {next_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check if it's time to refresh
            if is_time_to_refresh():
                print("\n🔄 IT'S TIME FOR SCHEDULED REFRESH!")
                print("="*60)
                logger.info("🔄 It's time for scheduled refresh! Starting...")
                
                success = run_scheduled_refresh()
                if success:
                    print("\n✅ SCHEDULER REFRESH COMPLETED SUCCESSFULLY!")
                    print("="*60)
                    logger.info("✅ Scheduled refresh completed successfully!")
                    consecutive_errors = 0  # Reset error counter on success
                else:
                    print("\n❌ SCHEDULER REFRESH FAILED!")
                    print("="*60)
                    logger.error("❌ Scheduled refresh failed!")
                    consecutive_errors += 1
            else:
                logger.info("Not time for refresh yet. Waiting 5 minutes...")
                consecutive_errors = 0  # Reset error counter
            
            # Wait 5 minutes before checking again
            time.sleep(300)
            
        except KeyboardInterrupt:
            print("\n👋 Enhanced scheduler daemon stopped by user")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Unexpected error in scheduler daemon: {e}")
            
            # If we have too many consecutive errors, wait longer
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Too many consecutive errors ({consecutive_errors}). Waiting 30 minutes before retrying...")
                time.sleep(1800)  # Wait 30 minutes
                consecutive_errors = 0  # Reset counter
            else:
                logger.info(f"Waiting 5 minutes before retrying... (Error {consecutive_errors}/{max_consecutive_errors})")
                time.sleep(300)

if __name__ == "__main__":
    main()

