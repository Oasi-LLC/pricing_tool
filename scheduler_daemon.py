#!/usr/bin/env python3
"""
Background scheduler daemon for automated data refresh
This script runs independently of the Streamlit app for maximum reliability.
Run this script in the background to ensure data is always refreshed on schedule.
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main daemon loop"""
    logger.info("Starting scheduler daemon...")
    
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            # Check if scheduler is enabled
            config = load_scheduler_config()
            if not config.get('enabled', False):
                logger.info("Scheduler is disabled. Waiting 5 minutes before checking again...")
                time.sleep(300)  # Wait 5 minutes
                consecutive_errors = 0  # Reset error counter
                continue
            
            # Get current status
            status = get_scheduler_status()
            current_time = get_lisbon_time()
            
            logger.info(f"Current Lisbon time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if status.get('next_refresh'):
                next_refresh = status['next_refresh']
                logger.info(f"Next scheduled refresh: {next_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check if it's time to refresh
            if is_time_to_refresh():
                logger.info("🔄 It's time for scheduled refresh! Starting...")
                
                success = run_scheduled_refresh()
                if success:
                    logger.info("✅ Scheduled refresh completed successfully!")
                    consecutive_errors = 0  # Reset error counter on success
                else:
                    logger.error("❌ Scheduled refresh failed!")
                    consecutive_errors += 1
            else:
                logger.info("Not time for refresh yet. Waiting 5 minutes...")
                consecutive_errors = 0  # Reset error counter
            
            # Wait 5 minutes before checking again
            time.sleep(300)
            
        except KeyboardInterrupt:
            logger.info("Scheduler daemon stopped by user")
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