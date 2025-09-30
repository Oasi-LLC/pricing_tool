"""
Scheduler utility for automated data refresh
Handles scheduled data pulls for nightly overrides and pl_daily data
"""

import yaml
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import pytz
import os
from .progress_tracker import progress_tracker

# Setup logging
logger = logging.getLogger(__name__)

class SchedulerError(Exception):
    """Custom exception for scheduler errors"""
    pass

def load_scheduler_config() -> Dict:
    """Load scheduler configuration from YAML file"""
    config_path = Path("config/scheduler.yaml")
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config.get('scheduler', {})
    except FileNotFoundError:
        logger.warning(f"Scheduler config not found at {config_path}, using defaults")
        return {
            'enabled': False,
            'refresh_times': ["01:00", "13:00"],
            'timezone': "Europe/Lisbon",
            'max_retries': 3,
            'retry_delay_minutes': 1
        }
    except yaml.YAMLError as e:
        logger.error(f"Error parsing scheduler config: {e}")
        raise SchedulerError(f"Invalid scheduler configuration: {e}")

def save_scheduler_config(config: Dict) -> bool:
    """Save scheduler configuration to YAML file"""
    config_path = Path("config/scheduler.yaml")
    try:
        # Ensure config directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump({'scheduler': config}, f, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"Error saving scheduler config: {e}")
        return False

def get_lisbon_time() -> datetime:
    """Get current time in Lisbon timezone"""
    lisbon_tz = pytz.timezone('Europe/Lisbon')
    return datetime.now(lisbon_tz)

def get_next_refresh_time() -> Optional[datetime]:
    """Calculate the next scheduled refresh time"""
    config = load_scheduler_config()
    if not config.get('enabled', False):
        return None
    
    refresh_times = config.get('refresh_times', ["01:00", "13:00"])
    timezone = config.get('timezone', 'Europe/Lisbon')
    tz = pytz.timezone(timezone)
    
    now = datetime.now(tz)
    today = now.date()
    
    # Convert refresh times to datetime objects for today
    refresh_datetimes = []
    for time_str in refresh_times:
        try:
            hour, minute = map(int, time_str.split(':'))
            refresh_time = tz.localize(datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute)))
            refresh_datetimes.append(refresh_time)
        except ValueError as e:
            logger.error(f"Invalid time format in config: {time_str}")
            continue
    
    # Add tomorrow's times as well
    tomorrow = today + timedelta(days=1)
    for time_str in refresh_times:
        try:
            hour, minute = map(int, time_str.split(':'))
            refresh_time = tz.localize(datetime.combine(tomorrow, datetime.min.time().replace(hour=hour, minute=minute)))
            refresh_datetimes.append(refresh_time)
        except ValueError as e:
            logger.error(f"Invalid time format in config: {time_str}")
            continue
    
    # Find the next refresh time
    for refresh_time in sorted(refresh_datetimes):
        if refresh_time > now:
            return refresh_time
    
    return None

def is_time_to_refresh() -> bool:
    """Check if it's time to run a scheduled refresh"""
    try:
        config = load_scheduler_config()
        if not config.get('enabled', False):
            return False
        
        # Get last refresh time from session state or file
        last_refresh_file = Path("logs/last_scheduler_refresh.txt")
        if last_refresh_file.exists():
            try:
                with open(last_refresh_file, 'r') as f:
                    last_refresh_str = f.read().strip()
                    last_refresh = datetime.fromisoformat(last_refresh_str)
                    # Ensure timezone awareness for comparison
                    if last_refresh.tzinfo is None:
                        lisbon_tz = pytz.timezone('Europe/Lisbon')
                        last_refresh = lisbon_tz.localize(last_refresh)
            except Exception as e:
                logger.error(f"Error reading last refresh time: {e}")
                last_refresh = None
        else:
            last_refresh = None
        
        now = get_lisbon_time()
        
        # Validate that now is timezone-aware
        if now.tzinfo is None:
            logger.error("Current time is not timezone-aware, using Lisbon timezone")
            lisbon_tz = pytz.timezone('Europe/Lisbon')
            now = lisbon_tz.localize(now.replace(tzinfo=None))
        
        # Check if we're within the refresh window (1 hour after scheduled time)
        refresh_times = config.get('refresh_times', ["01:00", "13:00"])
        for time_str in refresh_times:
            try:
                hour, minute = map(int, time_str.split(':'))
                # Create timezone-aware scheduled time by using the same timezone as now
                scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                # Ensure timezone awareness is preserved
                if scheduled_time.tzinfo is None:
                    scheduled_time = now.tzinfo.localize(scheduled_time.replace(tzinfo=None))
                
                # Check if we're within 1 hour of the scheduled time
                time_diff = abs((now - scheduled_time).total_seconds() / 3600)
                if time_diff <= 1:  # Within 1 hour of scheduled time
                    # Check if we haven't already refreshed in this window (reduced to 5 minutes for testing)
                    if last_refresh is None or (now - last_refresh).total_seconds() > 300:  # More than 5 minutes ago
                        logger.info(f"✅ Time to refresh! Current time: {now}, Scheduled time: {scheduled_time}")
                        return True
            except Exception as e:
                logger.error(f"Error checking refresh time {time_str}: {e}")
                continue
        
        return False
    except Exception as e:
        logger.error(f"Critical error in is_time_to_refresh: {e}")
        return False

def get_dynamic_date_range() -> tuple:
    """Calculate dynamic date range: from last month to end of current year"""
    from utils.date_manager import get_scheduler_dynamic_range
    
    start_date, end_date = get_scheduler_dynamic_range()
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def get_properties_needing_refresh() -> list:
    """Get list of properties that need refreshing based on data age"""
    config = load_scheduler_config()
    properties_config = config.get('properties', 'all')
    smart_refresh = config.get('smart_refresh', True)
    max_age_hours = config.get('max_data_age_hours', 24)
    
    # If not using smart refresh or properties is 'all', return all properties
    if not smart_refresh or properties_config == 'all':
        try:
            import yaml
            with open('config/properties.yaml', 'r') as f:
                yaml_config = yaml.safe_load(f)
            return list(yaml_config['properties'].keys())
        except Exception as e:
            logger.error(f"Error loading all properties: {e}")
            return []
    
    # If specific properties are configured, use those
    if isinstance(properties_config, list):
        return properties_config
    
    # Smart refresh: check which properties need updating
    try:
        import yaml
        with open('config/properties.yaml', 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        all_properties = list(yaml_config['properties'].keys())
        properties_needing_refresh = []
        
        now = datetime.now()
        max_age_seconds = max_age_hours * 3600
        
        for property_name in all_properties:
            # Check if property data is old enough to need refreshing
            pl_daily_path = Path(f"data/{property_name}/pl_daily_{property_name}.csv")
            nightly_path = Path(f"data/{property_name}/{property_name}_nightly_pulled_overrides.csv")
            
            needs_refresh = False
            
            # Check if files exist and are old enough
            if pl_daily_path.exists():
                file_age = now.timestamp() - pl_daily_path.stat().st_mtime
                if file_age > max_age_seconds:
                    needs_refresh = True
            else:
                needs_refresh = True  # File doesn't exist, needs refresh
            
            if nightly_path.exists():
                file_age = now.timestamp() - nightly_path.stat().st_mtime
                if file_age > max_age_seconds:
                    needs_refresh = True
            else:
                needs_refresh = True  # File doesn't exist, needs refresh
            
            if needs_refresh:
                properties_needing_refresh.append(property_name)
        
        logger.info(f"Smart refresh: {len(properties_needing_refresh)}/{len(all_properties)} properties need refreshing")
        return properties_needing_refresh
        
    except Exception as e:
        logger.error(f"Error in smart refresh logic: {e}")
        return []

def estimate_api_call_volume() -> dict:
    """Estimate the number of API calls that will be made"""
    try:
        import yaml
        config_path = Path("config/properties.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        total_listings = sum(len(prop.get('listings', [])) for prop in config['properties'].values())
        
        # Nightly pull: 1 API call per listing
        nightly_calls = total_listings
        
        # PL daily generation: 2 API calls per listing (daily data + overrides)
        pl_daily_calls = total_listings * 2
        
        # Total API calls
        total_calls = nightly_calls + pl_daily_calls
        
        return {
            'total_properties': len(config['properties']),
            'total_listings': total_listings,
            'nightly_pull_calls': nightly_calls,
            'pl_daily_calls': pl_daily_calls,
            'total_api_calls': total_calls,
            'estimated_duration_minutes': (total_calls * 1.5) / 60  # Assuming 1.5 seconds per call
        }
    except Exception as e:
        logger.error(f"Error estimating API call volume: {e}")
        return {
            'total_properties': 0,
            'total_listings': 0,
            'nightly_pull_calls': 0,
            'pl_daily_calls': 0,
            'total_api_calls': 0,
            'estimated_duration_minutes': 0
        }

def run_nightly_pull_with_retry() -> bool:
    """Run nightly pull with retry logic and enhanced progress tracking"""
    config = load_scheduler_config()
    max_retries = config.get('max_retries', 3)
    retry_delay = config.get('retry_delay_minutes', 1) * 60  # Convert to seconds
    
    # Get dynamic date range
    start_date, end_date = get_dynamic_date_range()
    logger.info(f"📅 Date range: {start_date} to {end_date}")
    
    # Get total listings for progress tracking
    try:
        import yaml
        with open('config/properties.yaml', 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        total_listings = 0
        for prop in progress_tracker.properties_to_process:
            if prop in yaml_config['properties']:
                total_listings += len(yaml_config['properties'][prop].get('listings', []))
        
        logger.info(f"📊 Processing {total_listings} listings across {len(progress_tracker.properties_to_process)} properties")
        
    except Exception as e:
        logger.error(f"Error counting listings: {e}")
        total_listings = 0
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Running nightly pull (attempt {attempt + 1}/{max_retries})")
            progress_tracker.update_step_progress(10, f"Starting nightly pull (attempt {attempt + 1})")
            
            # Run the nightly pull script with date range
            start_time = time.time()
            result = subprocess.run([
                sys.executable, "rates/pull/nightly_pull.py", start_date, end_date
            ], capture_output=True, text=True, cwd=".")
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"✅ Nightly pull completed successfully in {duration/60:.1f} minutes")
                progress_tracker.update_step_progress(100, "Nightly pull completed")
                
                # Update API calls made (1 per listing)
                progress_tracker.api_calls_made += total_listings
                progress_tracker._update_status_file()
                
                return True
            else:
                error_msg = f"Nightly pull failed (attempt {attempt + 1}): {result.stderr}"
                logger.error(error_msg)
                progress_tracker.add_error(error_msg)
                
        except Exception as e:
            error_msg = f"Nightly pull error (attempt {attempt + 1}): {e}"
            logger.error(error_msg)
            progress_tracker.add_error(error_msg)
        
        # Wait before retry (except on last attempt)
        if attempt < max_retries - 1:
            logger.info(f"⏳ Waiting {retry_delay} seconds before retry...")
            progress_tracker.update_step_progress(50, f"Waiting before retry (attempt {attempt + 1})")
            time.sleep(retry_delay)
    
    logger.error(f"❌ Nightly pull failed after {max_retries} attempts")
    progress_tracker.update_step_progress(0, "Nightly pull failed")
    return False

def run_pl_daily_generation_with_retry() -> bool:
    """Run pl_daily generation with retry logic, rate limiting, and enhanced progress tracking"""
    config = load_scheduler_config()
    max_retries = config.get('max_retries', 3)
    retry_delay = config.get('retry_delay_minutes', 1) * 60  # Convert to seconds
    
    # Get dynamic date range
    start_date, end_date = get_dynamic_date_range()
    logger.info(f"📅 Date range: {start_date} to {end_date}")
    
    # Get properties that need refreshing
    properties_to_refresh = get_properties_needing_refresh()
    if not properties_to_refresh:
        logger.info("No properties need PL daily generation. Skipping.")
        progress_tracker.update_step_progress(100, "No properties needed PL daily generation")
        return True
    
    logger.info(f"📊 Processing PL daily generation for {len(properties_to_refresh)} properties individually")
    
    # Get total listings for progress tracking
    try:
        import yaml
        with open('config/properties.yaml', 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        total_listings = 0
        property_listings = {}
        for prop in properties_to_refresh:
            if prop in yaml_config['properties']:
                listings_count = len(yaml_config['properties'][prop].get('listings', []))
                property_listings[prop] = listings_count
                total_listings += listings_count
        
        logger.info(f"📈 Total listings to process: {total_listings}")
        
    except Exception as e:
        logger.error(f"Error counting listings: {e}")
        total_listings = 0
        property_listings = {}
    
    # Add rate limiting delay before starting PL daily generation
    rate_limiting_config = config.get('rate_limiting', {})
    delay_between_ops = rate_limiting_config.get('delay_between_operations', 30)
    logger.info(f"⏳ Waiting {delay_between_ops} seconds before PL daily generation to respect API rate limits...")
    progress_tracker.update_step_progress(5, f"Waiting {delay_between_ops}s for rate limit reset")
    time.sleep(delay_between_ops)
    
    successful_properties = []
    failed_properties = []
    
    # Process each property individually to avoid timeouts
    for i, property_key in enumerate(properties_to_refresh):
        property_start_time = time.time()
        listings_count = property_listings.get(property_key, 0)
        
        logger.info(f"🔄 Property {i+1}/{len(properties_to_refresh)}: {property_key} ({listings_count} listings)")
        progress_tracker.update_step_progress(
            (i / len(properties_to_refresh)) * 100, 
            f"Processing {property_key} ({listings_count} listings)"
        )
        
        # Retry logic for individual property
        property_success = False
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Running PL daily generation for {property_key} (attempt {attempt + 1}/{max_retries})")
                
                # Run the pl_daily generation script for individual property
                result = subprocess.run([
                    sys.executable, "generate_pl_daily_comprehensive.py", 
                    property_key, start_date, end_date
                ], capture_output=True, text=True, cwd=".")
                
                if result.returncode == 0:
                    duration = time.time() - property_start_time
                    logger.info(f"✅ PL daily generation completed successfully for {property_key} in {duration/60:.1f}m")
                    successful_properties.append(property_key)
                    property_success = True
                    
                    # Update progress tracker
                    progress_tracker.complete_property(property_key, True, duration, listings_count * 2)
                    break
                else:
                    error_msg = f"PL daily generation failed for {property_key} (attempt {attempt + 1}): {result.stderr}"
                    logger.error(error_msg)
                    progress_tracker.add_error(error_msg)
                    
                    # Check if it's a rate limit error
                    if "rate limit" in result.stderr.lower() or "429" in result.stderr:
                        delay_on_rate_limit = rate_limiting_config.get('delay_on_rate_limit', 300)
                        logger.warning(f"⚠️ Rate limit detected for {property_key}. Waiting {delay_on_rate_limit} seconds before retry...")
                        progress_tracker.update_step_progress(
                            (i / len(properties_to_refresh)) * 100, 
                            f"Rate limit hit for {property_key}, waiting {delay_on_rate_limit}s"
                        )
                        time.sleep(delay_on_rate_limit)  # Wait for rate limit to reset
                    
            except Exception as e:
                error_msg = f"PL daily generation error for {property_key} (attempt {attempt + 1}): {e}"
                logger.error(error_msg)
                progress_tracker.add_error(error_msg)
            
            # Wait before retry (except on last attempt)
            if attempt < max_retries - 1:
                logger.info(f"⏳ Waiting {retry_delay} seconds before retry for {property_key}...")
                progress_tracker.update_step_progress(
                    (i / len(properties_to_refresh)) * 100, 
                    f"Waiting {retry_delay}s before retry for {property_key}"
                )
                time.sleep(retry_delay)
        
        if not property_success:
            failed_properties.append(property_key)
            logger.error(f"❌ PL daily generation failed for {property_key} after {max_retries} attempts")
            progress_tracker.complete_property(property_key, False, time.time() - property_start_time, 0)
        
        # Add delay between properties to avoid overwhelming the API
        if i < len(properties_to_refresh) - 1:  # Don't delay after the last property
            delay_between_properties = rate_limiting_config.get('delay_between_properties', 10)
            logger.info(f"⏳ Waiting {delay_between_properties} seconds before next property...")
            progress_tracker.update_step_progress(
                ((i + 1) / len(properties_to_refresh)) * 100, 
                f"Waiting {delay_between_properties}s before next property"
            )
            time.sleep(delay_between_properties)
    
    # Summary
    logger.info(f"📊 PL daily generation summary:")
    logger.info(f"  - Successful: {len(successful_properties)} properties")
    logger.info(f"  - Failed: {len(failed_properties)} properties")
    
    if failed_properties:
        logger.warning(f"⚠️ Failed properties: {failed_properties}")
    
    # Update final progress
    progress_tracker.update_step_progress(100, "PL daily generation completed")
    
    # Return True if at least some properties succeeded
    return len(successful_properties) > 0

def verify_refresh_success() -> bool:
    """Verify that the refresh was successful by checking file timestamps"""
    try:
        # Check if data directories have recent files
        data_dir = Path("data")
        if not data_dir.exists():
            logger.error("Data directory not found")
            return False
        
        now = datetime.now()
        recent_files_found = False
        
        # Check each property directory
        for property_dir in data_dir.iterdir():
            if property_dir.is_dir():
                # Check for pl_daily file
                pl_daily_file = property_dir / f"pl_daily_{property_dir.name}.csv"
                nightly_file = property_dir / f"{property_dir.name}_nightly_pulled_overrides.csv"
                
                if pl_daily_file.exists():
                    file_time = datetime.fromtimestamp(pl_daily_file.stat().st_mtime)
                    if (now - file_time).total_seconds() < 3600:  # File updated in last hour
                        recent_files_found = True
                        break
                
                if nightly_file.exists():
                    file_time = datetime.fromtimestamp(nightly_file.stat().st_mtime)
                    if (now - file_time).total_seconds() < 3600:  # File updated in last hour
                        recent_files_found = True
                        break
        
        return recent_files_found
        
    except Exception as e:
        logger.error(f"Error verifying refresh success: {e}")
        return False

def log_refresh_attempt(success: bool, error_message: str = None):
    """Log the refresh attempt"""
    try:
        # Ensure logs directory exists
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log to scheduler log file
        log_file = log_dir / "scheduler.log"
        timestamp = datetime.now().isoformat()
        
        with open(log_file, 'a') as f:
            status = "SUCCESS" if success else "FAILED"
            f.write(f"{timestamp} - {status}")
            if error_message:
                f.write(f" - {error_message}")
            f.write("\n")
        
        # Update last refresh time if successful
        if success:
            last_refresh_file = log_dir / "last_scheduler_refresh.txt"
            with open(last_refresh_file, 'w') as f:
                f.write(datetime.now().isoformat())
                
    except Exception as e:
        logger.error(f"Error logging refresh attempt: {e}")

def run_scheduled_refresh() -> bool:
    """Run the complete scheduled refresh process with enhanced progress tracking"""
    logger.info("Starting scheduled data refresh")
    
    # Get properties that need refreshing
    properties_to_refresh = get_properties_needing_refresh()
    if not properties_to_refresh:
        logger.info("No properties need refreshing. Skipping scheduled refresh.")
        log_refresh_attempt(True, "No properties needed refresh")
        return True
    
    logger.info(f"Properties needing refresh: {properties_to_refresh}")
    
    # Estimate API call volume for these specific properties
    total_calls = 0
    try:
        import yaml
        with open('config/properties.yaml', 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        total_listings = 0
        for prop in properties_to_refresh:
            if prop in yaml_config['properties']:
                total_listings += len(yaml_config['properties'][prop].get('listings', []))
        
        # Nightly pull: 1 API call per listing
        nightly_calls = total_listings
        # PL daily generation: 2 API calls per listing (daily data + overrides)
        pl_daily_calls = total_listings * 2
        total_calls = nightly_calls + pl_daily_calls
        
        logger.info(f"API Call Volume Estimate for {len(properties_to_refresh)} properties:")
        logger.info(f"  - Properties to refresh: {len(properties_to_refresh)}")
        logger.info(f"  - Total listings: {total_listings}")
        logger.info(f"  - Nightly pull calls: {nightly_calls}")
        logger.info(f"  - PL daily calls: {pl_daily_calls}")
        logger.info(f"  - Total API calls: {total_calls}")
        logger.info(f"  - Estimated duration: {(total_calls * 1.5) / 60:.1f} minutes")
        
        # Warn if API call volume is high
        if total_calls > 200:
            logger.warning(f"⚠️ High API call volume detected: {total_calls} calls")
            logger.warning("Consider running operations separately or during off-peak hours")
    
    except Exception as e:
        logger.error(f"Error estimating API call volume: {e}")
    
    # Initialize progress tracker
    progress_tracker.start_refresh(properties_to_refresh, total_calls)
    
    try:
        # Step 1: Run nightly pull
        progress_tracker.start_step("nightly_pull", 1)
        nightly_success = run_nightly_pull_with_retry()
        if not nightly_success:
            error_msg = "Nightly pull failed after all retries"
            progress_tracker.add_error(error_msg)
            progress_tracker.complete_refresh(False)
            log_refresh_attempt(False, error_msg)
            return False
        
        # Step 2: Run pl_daily generation
        progress_tracker.start_step("pl_daily_generation", 2)
        pl_daily_success = run_pl_daily_generation_with_retry()
        if not pl_daily_success:
            error_msg = "PL daily generation failed after all retries"
            progress_tracker.add_error(error_msg)
            progress_tracker.complete_refresh(False)
            log_refresh_attempt(False, error_msg)
            return False
        
        # Step 3: Verify refresh success
        logger.info("🔍 Verifying refresh success...")
        progress_tracker.update_step_progress(95, "Verifying refresh success")
        if not verify_refresh_success():
            error_msg = "Refresh verification failed - files not updated"
            progress_tracker.add_error(error_msg)
            progress_tracker.complete_refresh(False)
            log_refresh_attempt(False, error_msg)
            return False
        
        # Success
        progress_tracker.update_step_progress(100, "Refresh completed successfully")
        progress_tracker.complete_refresh(True)
        log_refresh_attempt(True)
        return True
        
    except Exception as e:
        error_msg = f"Unexpected error during scheduled refresh: {e}"
        progress_tracker.add_error(error_msg)
        progress_tracker.complete_refresh(False)
        logger.error(error_msg)
        log_refresh_attempt(False, error_msg)
        return False

def get_scheduler_status() -> Dict:
    """Get current scheduler status"""
    config = load_scheduler_config()
    enabled = config.get('enabled', False)
    
    status = {
        'enabled': enabled,
        'next_refresh': None,
        'last_refresh': None,
        'refresh_times': config.get('refresh_times', ["01:00", "13:00"]),
        'timezone': config.get('timezone', 'Europe/Lisbon')
    }
    
    if enabled:
        status['next_refresh'] = get_next_refresh_time()
        
        # Get last refresh time
        last_refresh_file = Path("logs/last_scheduler_refresh.txt")
        if last_refresh_file.exists():
            try:
                with open(last_refresh_file, 'r') as f:
                    last_refresh_str = f.read().strip()
                    status['last_refresh'] = datetime.fromisoformat(last_refresh_str)
            except Exception as e:
                logger.error(f"Error reading last refresh time: {e}")
    
    return status 